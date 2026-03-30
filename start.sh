#!/bin/bash

# coJournalist Local Development Startup Script

echo "🚀 Starting coJournalist..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your credentials:"
    echo "  cp .env.example .env"
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running!"
    echo "Please start Docker and try again."
    echo ""
    exit 1
fi

echo "✅ Environment file found"
echo "✅ Docker is running"
echo ""
echo "Starting services..."
echo ""

# Start docker-compose
docker-compose up --build

echo ""
echo "✅ coJournalist is running!"
echo ""
echo "📝 Access the application:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the services"
