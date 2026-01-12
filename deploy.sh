#!/bin/bash

# Deployment script for Shopify Price Manager
# Run this on your VPS to update the application

set -e

echo "🚀 Deploying Shopify Price Manager..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull

# Rebuild and restart containers
echo "🔨 Building and restarting containers..."
docker compose up -d --build

# Wait for health check
echo "⏳ Waiting for application to be ready..."
sleep 5

# Check health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Deployment successful!"
    echo "📊 Container status:"
    docker compose ps
else
    echo "❌ Health check failed!"
    echo "📋 Recent logs:"
    docker compose logs --tail=50
    exit 1
fi
