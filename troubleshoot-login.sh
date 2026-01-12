#!/bin/bash
# Troubleshooting script for login issues

echo "=============================================="
echo "  Login Troubleshooting"
echo "=============================================="
echo ""

cd /opt/shopify-price-manager

echo "1. Checking .env file..."
if [ -f ".env" ]; then
    echo "✓ .env file exists"
    if grep -q "admin_password_hash=" .env; then
        echo "✓ Found admin_password_hash (lowercase)"
    elif grep -q "ADMIN_PASSWORD_HASH=" .env; then
        echo "⚠ Found ADMIN_PASSWORD_HASH (uppercase) - needs to be lowercase!"
        echo "  Fixing..."
        sed -i 's/ADMIN_PASSWORD_HASH=/admin_password_hash=/g' .env
        sed -i 's/ADMIN_USERNAME=/admin_username=/g' .env
        sed -i 's/SECRET_KEY=/session_secret=/g' .env
        echo "✓ Fixed environment variable names"
    else
        echo "✗ No password hash found in .env"
        exit 1
    fi
else
    echo "✗ .env file not found"
    exit 1
fi

echo ""
echo "2. Current .env contents (sanitized):"
grep -v "admin_password_hash" .env | grep -v "session_secret"
echo "admin_password_hash=<hidden>"
echo "session_secret=<hidden>"

echo ""
echo "3. Stopping containers..."
docker compose down

echo ""
echo "4. Starting containers with fresh environment..."
docker compose up -d --build

echo ""
echo "5. Waiting for app to start..."
sleep 10

echo ""
echo "6. Testing health endpoint..."
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✓ App is running"
else
    echo "✗ App is not responding"
    echo "Logs:"
    docker compose logs --tail=20
    exit 1
fi

echo ""
echo "=============================================="
echo "  ✓ Troubleshooting Complete"
echo "=============================================="
echo ""
echo "Try logging in now."
echo "If it still doesn't work, let's reset the password:"
echo "  sudo ./reset-password.sh"
echo ""
