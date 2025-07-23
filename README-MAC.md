# 🍓 Raspberry Pi Control Panel - Mac Development Setup

This version of the Raspberry Pi Control Panel is configured to run on Mac/development systems without requiring actual Raspberry Pi GPIO hardware.

## 🚀 Quick Start

### Option 1: Automated Setup
```bash
./run-mac.sh
```

### Option 2: Manual Setup
```bash
# 1. Create projects directory
mkdir -p ./projects

# 2. Create .env file (if needed)
cp .env.example .env  # Edit as needed

# 3. Build and run
docker-compose -f docker-compose.mac.yml up --build
```

## 🎯 Features Available in Mac Mode

### ✅ Fully Functional
- **Docker Container Management** - Start, stop, restart, view logs
- **System Monitoring** - CPU, memory, disk usage
- **Project Management** - Git repositories in `./projects/` folder
- **Network Monitoring** - Interface status, network scanning
- **Service Management** - Systemd services (within container)

### 🔄 Mock/Simulated
- **GPIO Control** - Shows simulated GPIO pins for testing UI
- **Temperature Monitoring** - Generates mock CPU/GPU temperatures
- **Hardware Stats** - Simulated Pi-specific metrics

### ❌ Disabled
- **Actual GPIO Hardware** - No real GPIO pin control
- **Pi-specific Commands** - vcgencmd and similar tools

## 🌐 Access

- **Web Interface:** http://localhost:5000
- **Default Login:**
  - Username: `admin`
  - Password: `admin123`

## 📁 Directory Structure

```
./projects/          # Your development projects (auto-created)
├── project1/        # Example: git repositories
├── project2/        # Will be visible in Projects tab
└── project3/
```

## 🛠️ Development Commands

```bash
# Start services
docker-compose -f docker-compose.mac.yml up -d

# View logs
docker-compose -f docker-compose.mac.yml logs -f

# Stop services
docker-compose -f docker-compose.mac.yml down

# Rebuild after changes
docker-compose -f docker-compose.mac.yml up --build

# Shell access
docker-compose -f docker-compose.mac.yml exec web bash
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
FLASK_SECRET_KEY=your-secret-key
FLASK_DEBUG=True
DOCKER_API_VERSION=1.41
ADMIN_PASSWORD=your-admin-password
RPI_AVAILABLE=false  # Important: Keep false for Mac
```

### Adding Projects
1. Clone/create projects in `./projects/` directory
2. They'll automatically appear in the Projects tab
3. Git operations (pull, status, reset) work normally

## 🚀 Deployment to Raspberry Pi

To deploy this to an actual Raspberry Pi:

1. Copy project to Pi
2. Use original `docker-compose.yml` instead
3. Set `RPI_AVAILABLE=true` in .env
4. Install Pi-specific packages:
   ```bash
   pip install RPi.GPIO gpiozero w1thermsensor
   ```

## 🎨 UI Features

- **Tabbed Interface** - Easy navigation between features
- **Real-time Updates** - System stats refresh automatically
- **Responsive Design** - Works on desktop and mobile
- **Dark Mode Support** - System preference detection

## 🧪 Testing GPIO Features

Even in Mac mode, you can:
- View the GPIO pin layout
- Test the UI interactions
- Simulate pin toggles (visual feedback only)
- Develop GPIO-related features safely

## 📦 Dependencies

### Mac-compatible packages only:
- Flask ecosystem
- Docker SDK
- psutil (system monitoring)
- GitPython (repository management)

### Excluded from Mac build:
- RPi.GPIO
- gpiozero  
- w1thermsensor
- speedtest-cli

## 🐛 Troubleshooting

### Docker Socket Permission
If you get Docker socket errors:
```bash
sudo chmod 666 /var/run/docker.sock
```

### Port Already in Use
```bash
# Find and kill process using port 5000
sudo lsof -ti:5000 | xargs kill -9
```

### Container Won't Start
```bash
# Clean rebuild
docker-compose -f docker-compose.mac.yml down
docker system prune -f
docker-compose -f docker-compose.mac.yml up --build
```

## 🎯 Development Workflow

1. **Edit Code** - Make changes to Python/HTML/JS files
2. **Auto-reload** - Flask dev server reloads automatically
3. **Test Features** - Use the web interface
4. **Check Logs** - Monitor container logs for errors
5. **Git Commit** - Version control your changes

Happy coding! 🚀