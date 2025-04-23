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
            
        container_info.append({
            'id': container.id,
            'name': container.name,
            'status': container.status,
            'image': image_name
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
        }
        return jsonify(success=True, info=info)
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
