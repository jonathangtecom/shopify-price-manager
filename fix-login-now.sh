#!/bin/bash
set -e

echo "=============================================="
echo "  ONE-SHOT FIX - Fixing Login Issue"
echo "=============================================="
echo ""

cd /opt/shopify-price-manager

# Get the current password hash (try both cases)
HASH=$(grep "admin_password_hash=" .env | head -1 | cut -d= -f2)
if [ -z "$HASH" ]; then
    HASH=$(grep "ADMIN_PASSWORD_HASH=" .env | head -1 | cut -d= -f2)
fi

# Get session secret (try both cases)
SECRET=$(grep "session_secret=" .env | head -1 | cut -d= -f2)
if [ -z "$SECRET" ]; then
    SECRET=$(grep "SECRET_KEY=" .env | head -1 | cut -d= -f2)
fi

echo "1. Backing up old .env..."
cp .env .env.backup-$(date +%Y%m%d-%H%M%S)

echo "2. Creating fresh .env with correct variable names..."
cat > .env << EOF
# Application settings (all lowercase as required by config.py)
database_path=/app/data/app.db
session_secret=$SECRET
admin_password_hash=$HASH
host=0.0.0.0
port=8000
log_level=INFO
EOF

chmod 600 .env

echo "3. Stopping all containers..."
docker compose down

echo "4. Removing any cached data..."
docker compose rm -f 2>/dev/null || true

echo "5. Starting containers fresh..."
docker compose up -d --build

echo "6. Waiting for app to start..."
sleep 15

echo "7. Testing health endpoint..."
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✓ App is running"
else
    echo "✗ App failed to start. Showing logs:"
    docker compose logs --tail=30
    exit 1
fi

echo ""
echo "=============================================="
echo "  ✓ FIXED! Try logging in now."
echo "=============================================="
echo ""
echo "Your app is ready at: https://pricemanager.gtecombv.com"
echo "Just enter your password (no username needed)"
echo ""
