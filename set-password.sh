#!/bin/bash
# Set admin password for Shopify Price Manager
# Usage: ./set-password.sh [password]
# If no password provided, will prompt for it

set -e
cd /opt/shopify-price-manager

# Get password from argument or prompt
if [ -n "$1" ]; then
    PASSWORD="$1"
else
    read -sp "Enter new admin password: " PASSWORD
    echo ""
fi

if [ -z "$PASSWORD" ]; then
    echo "❌ Password cannot be empty"
    exit 1
fi

echo "Generating hash..."

# Generate bcrypt hash and escape $ as $$ for docker-compose
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$PASSWORD', bcrypt.gensalt()).decode().replace('\$', '\$\$'))")

# Generate or keep session secret
if [ -f .env ] && grep -q "^session_secret=" .env; then
    SECRET=$(grep "^session_secret=" .env | cut -d= -f2)
else
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

# Write .env
cat > .env << EOF
admin_password_hash=$HASH
session_secret=$SECRET
database_path=/app/data/app.db
EOF

echo "✓ Password set"

# Restart containers
echo "Restarting app..."
docker compose down 2>/dev/null || true
docker compose up -d
sleep 3

# Verify
echo "Verifying..."
RESULT=$(docker compose exec -T app python3 -c "import bcrypt; from app.config import settings; print('SUCCESS' if bcrypt.checkpw(b'$PASSWORD', settings.admin_password_hash.encode()) else 'FAILED')" 2>/dev/null)

if [ "$RESULT" = "SUCCESS" ]; then
    echo "✓✓✓ Password set successfully! ✓✓✓"
else
    echo "❌ Verification failed: $RESULT"
    exit 1
fi
