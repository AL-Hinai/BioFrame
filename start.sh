#!/bin/bash

# BioFrame System Startup Script
# This script starts the complete BioFrame bioinformatics workflow system

echo "🚀 Starting BioFrame System..."
echo "=============================="

# Function to check and start Docker
check_and_start_docker() {
    echo "🔍 Checking Docker status..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed."
        echo "Please install Docker Desktop for Windows or Docker Engine for Linux."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        echo "⚠️  Docker is not running. Attempting to start Docker..."
        
        # Detect OS and try to start Docker
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
            # Windows
            echo "🪟 Detected Windows environment"
            if command -v "C:\Program Files\Docker\Docker\Docker Desktop.exe" &> /dev/null; then
                echo "🚀 Starting Docker Desktop..."
                "C:\Program Files\Docker\Docker\Docker Desktop.exe" &
                sleep 10
            elif command -v "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe" &> /dev/null; then
                echo "🚀 Starting Docker Desktop..."
                "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe" &
                sleep 10
            else
                echo "❌ Docker Desktop not found. Please start Docker Desktop manually."
                exit 1
            fi
        else
            # Linux/Unix
            echo "🐧 Detected Linux/Unix environment"
            echo "🚀 Attempting to start Docker service..."
            if command -v systemctl &> /dev/null; then
                sudo systemctl start docker
                sleep 5
            elif command -v service &> /dev/null; then
                sudo service docker start
                sleep 5
            else
                echo "❌ Cannot start Docker service. Please start Docker manually."
                exit 1
            fi
        fi
        
        # Wait for Docker to start and verify
        echo "⏳ Waiting for Docker to start..."
        for i in {1..30}; do
            if docker info > /dev/null 2>&1; then
                echo "✅ Docker is now running!"
                return 0
            fi
            echo -n "."
            sleep 2
        done
        
        echo ""
        echo "❌ Docker failed to start. Please check Docker installation and start it manually."
        exit 1
    else
        echo "✅ Docker is running"
    fi
}

# Check and start Docker
check_and_start_docker

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    echo "Please install Docker Compose:"
    echo "  - Windows: Usually included with Docker Desktop"
    echo "  - Linux: sudo apt-get install docker-compose (Ubuntu/Debian) or equivalent for your distro"
    echo "  - Or use: docker compose (newer Docker versions include compose as a plugin)"
    
    # Try the newer docker compose command
    if docker compose version &> /dev/null; then
        echo "✅ Found 'docker compose' plugin, using that instead..."
        # Create a wrapper function for docker-compose
        docker-compose() {
            docker compose "$@"
        }
    else
        exit 1
    fi
fi

echo "✅ Docker and Docker Compose are available"


# Build all containers with reduced parallelism
echo "🔨 Building all containers..."
docker-compose build --parallel 2

if [ $? -ne 0 ]; then
    echo "❌ Failed to build containers. Please check the error messages above."
    exit 1
fi

echo "✅ All containers built successfully"

# Start the system
echo "🚀 Starting BioFrame system..."
docker-compose up -d

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 BioFrame system started successfully!"
    echo ""
    echo "📊 System Status:"
    echo "=================="
    docker-compose ps
    echo ""
    echo "🌐 Access the portal at: http://localhost:8000"
    echo "📊 PostgreSQL database: localhost:5432"
    echo "🔴 Redis: localhost:6380"
    echo ""
    echo "📖 For more information, see the README.md file"
    echo "🧪 To test the system, run: ./test_containers.sh"
    echo ""
    echo "To stop the system, run: docker-compose down"
    echo "To view logs, run: docker-compose logs -f"
else
    echo "❌ Failed to start BioFrame system. Please check the error messages above."
    exit 1
fi