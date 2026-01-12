#!/bin/bash
set -e

echo "=============================================="
echo "  Reset Admin Password"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: Must be run from /opt/shopify-price-manager directory"
    exit 1
fi

# Get new password
read -sp "Enter new admin password: " NEW_PASSWORD
echo ""
if [ -z "$NEW_PASSWORD" ]; then
    echo "Error: Password cannot be empty"
    exit 1
fi

read -sp "Confirm password: " CONFIRM_PASSWORD
echo ""
if [ "$NEW_PASSWORD" != "$CONFIRM_PASSWORD" ]; then
    echo "Error: Passwords do not match"
    exit 1
fi

echo ""
echo "Generating password hash..."

# Check if bcrypt is available
if ! python3 -c "import bcrypt" 2>/dev/null; then
    echo "Installing Python bcrypt..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-bcrypt > /dev/null
fi

# Generate new hash
NEW_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$NEW_PASSWORD', bcrypt.gensalt()).decode())")

# Update .env file
if [ -f ".env" ]; then
    if grep -q "^ADMIN_PASSWORD_HASH=" .env; then
        # Replace existing hash
        sed -i "s|^ADMIN_PASSWORD_HASH=.*|ADMIN_PASSWORD_HASH=$NEW_HASH|" .env
        echo "✓ Password hash updated in .env"
    else
        # Add hash if missing
        echo "ADMIN_PASSWORD_HASH=$NEW_HASH" >> .env
        echo "✓ Password hash added to .env"
    fi
else
    echo "Error: .env file not found"
    exit 1
fi

# Restart application
echo "Restarting application..."
docker compose restart

echo ""
echo "=============================================="
echo "  ✓ Password Reset Complete!"
echo "=============================================="
echo ""
echo "You can now log in with your new password."
echo ""
