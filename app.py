from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import docker
import os
import subprocess
import json
import glob
from dotenv import load_dotenv

# Raspberry Pi specific imports (graceful fallback for non-Pi systems)
RPI_AVAILABLE = os.getenv('RPI_AVAILABLE', 'true').lower() == 'true'

if RPI_AVAILABLE:
    try:
        import RPi.GPIO as GPIO
        from gpiozero import CPUTemperature, LED, Button, MCP3008
        print("🍓 Raspberry Pi GPIO modules loaded successfully")
    except ImportError:
        RPI_AVAILABLE = False
        print("⚠️  RPi.GPIO not available - falling back to mock mode")
else:
    print("🖥️  Running in Mac/Development mode - GPIO disabled")

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

# Raspberry Pi Hardware Stats
@app.route('/api/stats/rpi', methods=['GET'])
@login_required
def rpi_stats():
    try:
        stats = {}
        
        if RPI_AVAILABLE:
            # CPU Temperature
            cpu_temp = CPUTemperature()
            stats['cpu_temperature'] = round(cpu_temp.temperature, 2)
            
            # GPU Temperature (if available)
            try:
                gpu_temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                               capture_output=True, text=True, timeout=5)
                if gpu_temp_result.returncode == 0:
                    gpu_temp_str = gpu_temp_result.stdout.strip()
                    gpu_temp = float(gpu_temp_str.split('=')[1].split("'")[0])
                    stats['gpu_temperature'] = round(gpu_temp, 2)
            except:
                stats['gpu_temperature'] = None
        else:
            # Mock data for development
            import random
            stats['cpu_temperature'] = round(45 + random.random() * 15, 2)
            stats['gpu_temperature'] = round(40 + random.random() * 10, 2)
        
        # CPU frequency and voltage
        try:
            # CPU frequency
            freq_result = subprocess.run(['vcgencmd', 'measure_clock', 'arm'], 
                                       capture_output=True, text=True, timeout=5)
            if freq_result.returncode == 0:
                freq_hz = int(freq_result.stdout.strip().split('=')[1])
                stats['cpu_frequency_mhz'] = freq_hz // 1000000
            
            # Core voltage
            volt_result = subprocess.run(['vcgencmd', 'measure_volts', 'core'], 
                                       capture_output=True, text=True, timeout=5)
            if volt_result.returncode == 0:
                volt_str = volt_result.stdout.strip()
                voltage = float(volt_str.split('=')[1].replace('V', ''))
                stats['core_voltage'] = round(voltage, 2)
        except:
            stats['cpu_frequency_mhz'] = 1500  # Default Pi 4 frequency
            stats['core_voltage'] = 1.2
        
        # Throttling status
        try:
            throttle_result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                           capture_output=True, text=True, timeout=5)
            if throttle_result.returncode == 0:
                throttle_hex = throttle_result.stdout.strip().split('=')[1]
                throttle_int = int(throttle_hex, 16)
                stats['throttling'] = {
                    'under_voltage': bool(throttle_int & 0x1),
                    'frequency_capped': bool(throttle_int & 0x2),
                    'currently_throttled': bool(throttle_int & 0x4),
                    'temperature_limit': bool(throttle_int & 0x8)
                }
        except:
            stats['throttling'] = {
                'under_voltage': False,
                'frequency_capped': False,
                'currently_throttled': False,
                'temperature_limit': False
            }
        
        return jsonify(success=True, stats=stats)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# GPIO Control Routes
@app.route('/api/gpio/status', methods=['GET'])
@login_required
@roles_required('read-only','operator','admin')
def gpio_status():
    try:
        if not RPI_AVAILABLE:
            return jsonify(success=False, error='GPIO not available on this system'), 400
        
        # Read common GPIO pins status
        pins_status = {}
        common_pins = [2, 3, 4, 17, 27, 22, 10, 9, 11, 5, 6, 13, 19, 26, 14, 15, 18, 23, 24, 25, 8, 7, 12, 16, 20, 21]
        
        GPIO.setmode(GPIO.BCM)
        for pin in common_pins:
            try:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                pins_status[pin] = {
                    'value': GPIO.input(pin),
                    'mode': 'input'
                }
            except:
                pins_status[pin] = {'value': None, 'mode': 'unknown'}
        
        return jsonify(success=True, pins=pins_status)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

@app.route('/api/gpio/pin/<int:pin>/set', methods=['POST'])
@login_required
@roles_required('operator','admin')
def gpio_set_pin(pin):
    try:
        if not RPI_AVAILABLE:
            return jsonify(success=False, error='GPIO not available on this system'), 400
        
        data = request.get_json()
        value = data.get('value', 0)
        mode = data.get('mode', 'output')
        
        GPIO.setmode(GPIO.BCM)
        
        if mode == 'output':
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, int(value))
        elif mode == 'input':
            pull = GPIO.PUD_UP if data.get('pull_up') else GPIO.PUD_DOWN
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
        
        return jsonify(success=True, pin=pin, value=value, mode=mode)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Project Management Routes
@app.route('/api/projects', methods=['GET'])
@login_required
@roles_required('read-only','operator','admin')
def list_projects():
    try:
        projects_dir = os.path.expanduser('~/projects')
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)
        
        projects = []
        for item in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, item)
            if os.path.isdir(project_path):
                # Check if it's a git repository
                is_git = os.path.exists(os.path.join(project_path, '.git'))
                
                project_info = {
                    'name': item,
                    'path': project_path,
                    'is_git': is_git,
                    'size': get_directory_size(project_path),
                    'modified': os.path.getmtime(project_path)
                }
                
                if is_git:
                    try:
                        import git
                        repo = git.Repo(project_path)
                        project_info['git_info'] = {
                            'branch': repo.active_branch.name,
                            'commit': repo.head.commit.hexsha[:8],
                            'dirty': repo.is_dirty(),
                            'remote': repo.remotes.origin.url if repo.remotes else None
                        }
                    except:
                        project_info['git_info'] = {'error': 'Unable to read git info'}
                
                projects.append(project_info)
        
        return jsonify(success=True, projects=projects)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

@app.route('/api/projects/<project_name>/git/<action>', methods=['POST'])
@login_required
@roles_required('operator','admin')
def git_action(project_name, action):
    try:
        import git
        projects_dir = os.path.expanduser('~/projects')
        project_path = os.path.join(projects_dir, project_name)
        
        if not os.path.exists(project_path) or not os.path.exists(os.path.join(project_path, '.git')):
            return jsonify(success=False, error='Project not found or not a git repository'), 400
        
        repo = git.Repo(project_path)
        result = {}
        
        if action == 'pull':
            origin = repo.remotes.origin
            pull_info = origin.pull()
            result['message'] = f"Pulled {len(pull_info)} commits"
        elif action == 'status':
            result['status'] = {
                'branch': repo.active_branch.name,
                'commit': repo.head.commit.hexsha[:8],
                'dirty': repo.is_dirty(),
                'untracked': [item.a_path for item in repo.index.diff(None)],
                'modified': [item.a_path for item in repo.index.diff(repo.head.commit)]
            }
        elif action == 'reset':
            repo.git.reset('--hard', 'HEAD')
            result['message'] = 'Repository reset to HEAD'
        else:
            return jsonify(success=False, error='Unknown git action'), 400
        
        return jsonify(success=True, result=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# Network Monitoring Routes
@app.route('/api/network/status', methods=['GET'])
@login_required
@roles_required('read-only','operator','admin')
def network_status():
    try:
        import psutil
        
        # Get network interfaces
        interfaces = {}
        for interface, addrs in psutil.net_if_addrs().items():
            if interface != 'lo':  # Skip loopback
                interfaces[interface] = {
                    'addresses': [addr.address for addr in addrs],
                    'is_up': psutil.net_if_stats()[interface].isup
                }
        
        # Get WiFi signal strength (if available)
        wifi_signal = None
        try:
            iwconfig_result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
            if iwconfig_result.returncode == 0:
                output = iwconfig_result.stdout
                for line in output.split('\n'):
                    if 'Signal level' in line:
                        signal_match = line.split('Signal level=')[1].split(' ')[0]
                        wifi_signal = signal_match
                        break
        except:
            pass
        
        # Get network statistics
        net_stats = psutil.net_io_counters()
        
        result = {
            'interfaces': interfaces,
            'wifi_signal': wifi_signal,
            'stats': {
                'bytes_sent': net_stats.bytes_sent,
                'bytes_recv': net_stats.bytes_recv,
                'packets_sent': net_stats.packets_sent,
                'packets_recv': net_stats.packets_recv
            }
        }
        
        return jsonify(success=True, network=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

@app.route('/api/network/scan', methods=['POST'])
@login_required
@roles_required('operator','admin')
def network_scan():
    try:
        data = request.get_json()
        target = data.get('target', '192.168.1.0/24')
        
        # Basic network scan using nmap if available
        try:
            nmap_result = subprocess.run(['nmap', '-sn', target], 
                                       capture_output=True, text=True, timeout=30)
            if nmap_result.returncode == 0:
                hosts = []
                for line in nmap_result.stdout.split('\n'):
                    if 'Nmap scan report for' in line:
                        host = line.split('for ')[1]
                        hosts.append(host)
                return jsonify(success=True, hosts=hosts)
        except:
            pass
        
        # Fallback: ping sweep
        import ipaddress
        network = ipaddress.IPv4Network(target, strict=False)
        active_hosts = []
        
        for host in list(network.hosts())[:20]:  # Limit to first 20 hosts
            try:
                ping_result = subprocess.run(['ping', '-c', '1', '-W', '1', str(host)], 
                                           capture_output=True, timeout=2)
                if ping_result.returncode == 0:
                    active_hosts.append(str(host))
            except:
                pass
        
        return jsonify(success=True, hosts=active_hosts)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# System Services Management
@app.route('/api/services', methods=['GET'])
@login_required
@roles_required('read-only','operator','admin')
def list_services():
    try:
        # Get systemd services
        services = []
        systemctl_result = subprocess.run(['systemctl', 'list-units', '--type=service', '--no-pager'], 
                                        capture_output=True, text=True, timeout=10)
        
        if systemctl_result.returncode == 0:
            lines = systemctl_result.stdout.split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip() and not line.startswith('●'):
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            'name': parts[0],
                            'load': parts[1],
                            'active': parts[2],
                            'sub': parts[3],
                            'description': ' '.join(parts[4:]) if len(parts) > 4 else ''
                        })
        
        return jsonify(success=True, services=services[:50])  # Limit to 50 services
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

@app.route('/api/services/<service_name>/<action>', methods=['POST'])
@login_required
@roles_required('admin')
def service_action(service_name, action):
    try:
        if action not in ['start', 'stop', 'restart', 'status']:
            return jsonify(success=False, error='Invalid action'), 400
        
        result = subprocess.run(['sudo', 'systemctl', action, service_name], 
                              capture_output=True, text=True, timeout=10)
        
        return jsonify(success=True, 
                      output=result.stdout, 
                      error=result.stderr,
                      returncode=result.returncode)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

def get_directory_size(path):
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except:
        pass
    return total_size

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
from flask import request, abort
import time

# Simple in-memory rate limit store
login_attempts = {}
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 600  # 10 minutes in seconds

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    client_ip = request.remote_addr
    now = time.time()
    # Clean up old attempts
    attempts = login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now - t < LOGIN_ATTEMPT_WINDOW]
    if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
        flash('Too many login attempts. Please try again later.', 'danger')
        return render_template('login.html')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(username=username).first()
        if user and user.password and check_password_hash(user.password, password):
            login_attempts[client_ip] = []  # Reset on successful login
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin'))
        attempts.append(now)
        login_attempts[client_ip] = attempts
        flash('Login failed. Check username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Debug route for testing - REMOVE IN PRODUCTION
@app.route('/debug-create-user')
def debug_create_user():
    # Create a test user with a fixed password
    try:
        # Check if user exists
        test_user = User.query.filter_by(username='testadmin').first()
        if test_user:
            # Update password if user exists
            test_user.password = generate_password_hash('test123')
        else:
            # Create new user if doesn't exist
            test_user = User(username='testadmin', password=generate_password_hash('test123'), role='admin')
            db.session.add(test_user)
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Test user created successfully',
            'username': 'testadmin',
            'password': 'test123',
            'role': 'admin'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Debug route to reset login attempts - REMOVE IN PRODUCTION
@app.route('/debug-reset-login-attempts')
def debug_reset_login_attempts():
    global login_attempts
    login_attempts.clear()
    return jsonify({
        'success': True,
        'message': 'All login attempts have been reset',
        'cleared_ips': 'all'
    })

# Debug route to view login attempt status - REMOVE IN PRODUCTION  
@app.route('/debug-login-status')
def debug_login_status():
    global login_attempts
    now = time.time()
    status = {}
    
    for ip, attempts in login_attempts.items():
        # Clean up old attempts for display
        recent_attempts = [t for t in attempts if now - t < LOGIN_ATTEMPT_WINDOW]
        remaining_time = 0
        if recent_attempts:
            oldest_attempt = min(recent_attempts)
            remaining_time = max(0, LOGIN_ATTEMPT_WINDOW - (now - oldest_attempt))
        
        status[ip] = {
            'total_attempts': len(recent_attempts),
            'max_attempts': LOGIN_ATTEMPT_LIMIT,
            'blocked': len(recent_attempts) >= LOGIN_ATTEMPT_LIMIT,
            'remaining_lockout_seconds': int(remaining_time) if len(recent_attempts) >= LOGIN_ATTEMPT_LIMIT else 0
        }
    
    return jsonify({
        'success': True,
        'login_attempt_status': status,
        'window_seconds': LOGIN_ATTEMPT_WINDOW,
        'max_attempts': LOGIN_ATTEMPT_LIMIT
    })

with app.app_context():
    db.create_all()
    
    # Create default users if no users exist
    if not User.query.first():
        # Admin user with full permissions
        admin_pw = os.getenv('ADMIN_PASSWORD')
        print(f"DEBUG: Admin password from env: '{admin_pw}'")
        
        # WARNING: Using default admin password. This is insecure and not recommended for production use.
        if not admin_pw:
            admin_pw = '1234admin'
            print(f"DEBUG: Using default admin password: '{admin_pw}'")
        admin_user = User(username='admin', password=generate_password_hash(admin_pw), role='admin')
        db.session.add(admin_user)
        
        # Regular user with read-only permissions
        regular_user = User(username='user', password=generate_password_hash('1234'), role='read-only')
        db.session.add(regular_user)
        
        db.session.commit()
        print("Default users created:")
        print(f"- Admin: username='admin', password='{admin_pw}', role='admin'")
        print("- User: username='user', password='1234', role='read-only'")
        print("Role permissions:")
        print("- admin: Full access to all features")
        print("- operator: Can view everything and control containers")
        print("- read-only: Can only view information, no control actions")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
