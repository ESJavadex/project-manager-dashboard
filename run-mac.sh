#!/bin/bash

# Mac Development Setup Script for Raspberry Pi Control Panel
echo "🍓 Setting up Raspberry Pi Control Panel for Mac Development..."

# Create projects directory if it doesn't exist
mkdir -p ./projects

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
FLASK_SECRET_KEY=dev-secret-key-change-in-production
FLASK_DEBUG=True
DOCKER_API_VERSION=1.41
ADMIN_PASSWORD=admin123
RPI_AVAILABLE=false
EOF
    echo "✅ .env file created"
fi

# Build and start the container
echo "🐳 Building and starting Docker containers..."
docker-compose -f docker-compose.mac.yml down
docker-compose -f docker-compose.mac.yml build
docker-compose -f docker-compose.mac.yml up -d

echo "🎉 Setup complete!"
echo ""
echo "📝 Access the control panel at: http://localhost:5000"
echo "👤 Default login:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "🔧 Available commands:"
echo "   - Start: docker-compose -f docker-compose.mac.yml up -d"
echo "   - Stop:  docker-compose -f docker-compose.mac.yml down"
echo "   - Logs:  docker-compose -f docker-compose.mac.yml logs -f"
echo ""
echo "📁 Projects directory: ./projects (mapped to /root/projects in container)"
echo "🐳 Docker containers can be managed through the web interface"