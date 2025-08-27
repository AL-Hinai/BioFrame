#!/bin/bash

# BioFrame System Startup Script
# This script starts the complete BioFrame bioinformatics workflow system

echo "🚀 Starting BioFrame System..."
echo "=============================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data workflows logs

# Build all containers
echo "🔨 Building all containers..."
docker-compose build

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