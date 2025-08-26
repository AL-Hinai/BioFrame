#!/bin/bash

# BioFrame Container-Based System Test Runner
# This script runs the comprehensive system test inside the workflow-orchestrator container

echo "🧪 Starting BioFrame Container-Based System Test..."
echo "=================================================="

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

# Build the workflow-orchestrator container first
echo "🔨 Building workflow-orchestrator container..."
docker-compose build workflow-orchestrator

if [ $? -ne 0 ]; then
    echo "❌ Failed to build workflow-orchestrator container. Please check the error messages above."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data workflows logs

# Copy the test script to the container
echo "📋 Copying test script to container..."
docker-compose run --rm workflow-orchestrator bash -c "
    # Install required Python packages
    pip install docker pyyaml requests
    
    # Run the system test
    python /workflows/test_system.py
"

# Check if the test was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Container-based system test completed successfully!"
    echo "Your BioFrame system is working correctly."
    
    # Show test results if available
    if [ -f "logs/test_results.json" ]; then
        echo ""
        echo "📊 Test Results Summary:"
        echo "========================"
        python3 -c "
import json
try:
    with open('logs/test_results.json', 'r') as f:
        results = json.load(f)
    print(f'Overall Status: {results.get(\"overall_status\", \"Unknown\")}')
    print(f'Timestamp: {results.get(\"timestamp\", \"Unknown\")}')
    print('\\nTest Results:')
    for test_name, result in results.get('tests', {}).items():
        if isinstance(result, dict):
            print(f'  {test_name}:')
            for container, status in result.items():
                status_icon = '✅' if status else '❌'
                print(f'    {container}: {status_icon}')
        else:
            status_icon = '✅' if result else '❌'
            print(f'  {test_name}: {status_icon}')
except Exception as e:
    print(f'Could not read test results: {e}')
"
    fi
else
    echo ""
    echo "❌ Container-based system test failed. Please check the logs above for details."
    echo "You can also check the logs/ directory for detailed test results."
    exit 1
fi

echo ""
echo "📖 For more information, see the README.md file"
echo "🚀 To start the full system, run: ./start.sh"
