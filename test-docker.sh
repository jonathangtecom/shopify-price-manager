#!/bin/bash
set -e

echo "🧪 Testing Docker Setup Locally..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true
echo ""

# Build the image
echo "🏗️  Building Docker image..."
docker-compose build
echo ""

# Start the container
echo "🚀 Starting container..."
docker-compose up -d
echo ""

# Wait for app to be ready
echo "⏳ Waiting for app to be ready..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ App is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ App failed to start. Check logs with: docker-compose logs"
        docker-compose down
        exit 1
    fi
    sleep 1
done
echo ""

# Run tests
echo "🧪 Running health checks..."
echo ""

# Test health endpoint
echo "1. Testing /health endpoint..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "   ✅ Health check passed"
else
    echo "   ❌ Health check failed"
    docker-compose logs
    docker-compose down
    exit 1
fi

# Test login page
echo "2. Testing /login page..."
if curl -f -s http://localhost:8000/login > /dev/null; then
    echo "   ✅ Login page accessible"
else
    echo "   ❌ Login page failed"
    docker-compose down
    exit 1
fi

# Check database persistence
echo "3. Checking database persistence..."
if [ -f "./data/app.db" ]; then
    echo "   ✅ Database file created"
else
    echo "   ❌ Database file not found"
    docker-compose down
    exit 1
fi

# Check logs
echo "4. Checking container logs..."
if docker-compose logs | grep -q "Application ready"; then
    echo "   ✅ Application started successfully"
else
    echo "   ⚠️  Warning: Startup message not found in logs"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ ALL TESTS PASSED!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📱 App running at: http://localhost:8000"
echo "🔑 Default password: admin"
echo ""
echo "Commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart"
echo ""
echo "Ready for VPS deployment! 🚀"
