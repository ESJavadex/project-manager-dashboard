from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
import docker
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Docker client
docker_client = docker.from_env(version=os.getenv('DOCKER_API_VERSION'))

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    containers = docker_client.containers.list(all=True)
    container_info = []
    for container in containers:
        try:
            image_name = container.attrs['Config']['Image']
        except (KeyError, TypeError):
            image_name = 'unknown'

        # Get the first mapped host port (if any)
        ports = container.attrs['NetworkSettings']['Ports']
        host_port = None
        if ports:
            for container_port, mappings in ports.items():
                if mappings and isinstance(mappings, list):
                    host_port = mappings[0].get('HostPort')
                    break

        # Build URL on same host instead of localhost
        container_url = None
        if host_port:
            base = request.host_url.rstrip('/').rsplit(':', 1)[0]
            container_url = f"{base}:{host_port}"

        container_info.append({
            'id': container.id,
            'name': container.name,
            'status': container.status,
            'image': image_name,
            'host_port': host_port,
            'url': container_url
        })
    return render_template('admin.html', containers=container_info)

# Container Info Route
@app.route('/container/<container_id>/info', methods=['GET'])
def container_info(container_id):
    try:
        container = docker_client.containers.get(container_id)
        info = {
            'id': container.id,
            'name': container.name,
            'status': container.status,
            'image': container.attrs['Config']['Image'],
            'created': container.attrs['Created'],
            'ports': container.attrs['NetworkSettings']['Ports'],
            'labels': container.attrs['Config'].get('Labels', {}),
            'env': container.attrs['Config'].get('Env', []),
            'command': container.attrs['Config'].get('Cmd', []),
            'volumes': container.attrs['HostConfig'].get('Binds', []),
            'networks': list(container.attrs['NetworkSettings']['Networks'].keys()),
            'restart_policy': container.attrs['HostConfig'].get('RestartPolicy', {}),
        }
        return jsonify(success=True, info=info)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Container Logs Route
@app.route('/container/<container_id>/logs', methods=['GET'])
def container_logs(container_id):
    try:
        container = docker_client.containers.get(container_id)
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        return jsonify(success=True, logs=logs)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Container Stats Route
@app.route('/container/<container_id>/stats', methods=['GET'])
def container_stats(container_id):
    try:
        container = docker_client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        # Calculate CPU percentage
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1])) * 100.0
        
        # Calculate memory usage
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0
        
        # Network stats
        rx_bytes = 0
        tx_bytes = 0
        if 'networks' in stats:
            for interface, data in stats['networks'].items():
                rx_bytes += data.get('rx_bytes', 0)
                tx_bytes += data.get('tx_bytes', 0)
        
        result = {
            'cpu_percent': round(cpu_percent, 2),
            'mem_usage': mem_usage,
            'mem_limit': mem_limit,
            'mem_percent': round(mem_percent, 2),
            'rx_bytes': rx_bytes,
            'tx_bytes': tx_bytes
        }
        
        return jsonify(success=True, stats=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Container Control Routes
@app.route('/container/<container_id>/start', methods=['POST'])
def start_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.start()
        return {'success': True, 'status': 'running'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@app.route('/container/<container_id>/stop', methods=['POST'])
def stop_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.stop()
        return {'success': True, 'status': 'stopped'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@app.route('/container/<container_id>/restart', methods=['POST'])
def restart_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.restart()
        return {'success': True, 'status': 'running'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
