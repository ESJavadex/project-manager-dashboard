from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
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
    role = db.Column(db.String(20), nullable=False, default='read-only')

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    container_id = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs')

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                return jsonify(success=False, error='Forbidden'), 403
            return f(*args, **kwargs)
        return wrapped_function
    return decorator

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
@login_required
@roles_required('read-only','operator','admin')
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
@login_required
@roles_required('read-only','operator','admin')
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
@login_required
@roles_required('read-only','operator','admin')
def container_logs(container_id):
    try:
        container = docker_client.containers.get(container_id)
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        return jsonify(success=True, logs=logs)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Container Stats Route
@app.route('/container/<container_id>/stats', methods=['GET'])
@login_required
@roles_required('read-only','operator','admin')
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

# Global Stats Route
@app.route('/api/stats/global', methods=['GET'])
def global_stats():
    try:
        # Get container stats
        containers = docker_client.containers.list(all=True)
        running_containers = [c for c in containers if c.status == 'running']
        
        # Get system stats
        import psutil
        
        # CPU stats
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # Memory stats
        memory = psutil.virtual_memory()
        memory_used = memory.used
        memory_total = memory.total
        
        # Disk stats
        disk = psutil.disk_usage('/')
        disk_used = disk.used
        disk_total = disk.total
        
        # Network stats
        net_io = psutil.net_io_counters()
        network_rx = net_io.bytes_recv
        network_tx = net_io.bytes_sent
        
        stats = {
            'containers': {
                'total': len(containers),
                'running': len(running_containers),
                'stopped': len(containers) - len(running_containers)
            },
            'system': {
                'cpu_percent': cpu_percent,
                'memory_used': memory_used,
                'memory_total': memory_total,
                'disk_used': disk_used,
                'disk_total': disk_total,
                'network_rx': network_rx,
                'network_tx': network_tx
            }
        }
        
        return jsonify(success=True, stats=stats)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Container Control Routes
@app.route('/container/<container_id>/start', methods=['POST'])
@login_required
@roles_required('operator','admin')
def start_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.start()
        log = AuditLog(user_id=current_user.id, action='start', container_id=container_id)
        db.session.add(log)
        db.session.commit()
        return {'success': True, 'status': 'running'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@app.route('/container/<container_id>/stop', methods=['POST'])
@login_required
@roles_required('operator','admin')
def stop_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.stop()
        log = AuditLog(user_id=current_user.id, action='stop', container_id=container_id)
        db.session.add(log)
        db.session.commit()
        return {'success': True, 'status': 'stopped'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@app.route('/container/<container_id>/restart', methods=['POST'])
@login_required
@roles_required('operator','admin')
def restart_container(container_id):
    try:
        container = docker_client.containers.get(container_id)
        container.restart()
        log = AuditLog(user_id=current_user.id, action='restart', container_id=container_id)
        db.session.add(log)
        db.session.commit()
        return {'success': True, 'status': 'running'}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(username=username).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin'))
        flash('Login failed. Check username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# REMOVE UNSAFE USER CREATION ROUTE

with app.app_context():
    db.create_all()
    
    # Create default users if no users exist
    if not User.query.first():
        # Admin user with full permissions
        admin_user = User(username='admin', password=generate_password_hash('1234admin'), role='admin')
        db.session.add(admin_user)
        
        # Regular user with read-only permissions
        regular_user = User(username='user', password=generate_password_hash('1234'), role='read-only')
        db.session.add(regular_user)
        
        db.session.commit()
        print("Default users created:")
        print("- Admin: username='admin', password='1234admin', role='admin'")
        print("- User: username='user', password='1234', role='read-only'")
        print("Role permissions:")
        print("- admin: Full access to all features")
        print("- operator: Can view everything and control containers")
        print("- read-only: Can only view information, no control actions")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
