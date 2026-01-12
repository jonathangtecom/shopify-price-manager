#!/bin/bash

# FINAL PASSWORD FIX - Generate correct hash and update .env
# This will ask for your password, generate the hash, update .env, and restart

set -e

echo "=== FINAL PASSWORD FIX ==="
echo ""
echo "This will:"
echo "1. Ask for your password"
echo "2. Generate the correct bcrypt hash"
echo "3. Update .env file"
echo "4. Restart containers"
echo "5. Verify login works"
echo ""

# Step 1: Get password
read -sp "Enter your desired admin password: " PASSWORD
echo ""

if [ -z "$PASSWORD" ]; then
    echo "❌ Password cannot be empty"
    exit 1
fi

# Step 2: Generate hash using Python bcrypt
echo ""
echo "Generating bcrypt hash..."
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw('$PASSWORD'.encode(), bcrypt.gensalt()).decode())")

if [ -z "$HASH" ]; then
    echo "❌ Failed to generate hash"
    exit 1
fi

echo "✓ Hash generated: ${HASH:0:20}..."

# Step 3: Backup and update .env
echo ""
echo "Backing up .env..."
cp .env .env.backup.$(date +%s)

# Extract session_secret from current .env (keep it unchanged)
if grep -q "^session_secret=" .env; then
    SESSION_SECRET=$(grep "^session_secret=" .env | cut -d= -f2)
else
    # Generate new session secret if missing
    SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "⚠ Generated new session_secret"
fi

# Step 4: Create new .env with correct values
echo ""
echo "Writing new .env file..."
cat > .env << EOF
admin_password_hash="$HASH"
session_secret="$SESSION_SECRET"
database_path="/app/data/app.db"
EOF

echo "✓ .env updated"

# Step 5: Restart containers
echo ""
echo "Restarting containers..."
docker compose down
sleep 2
docker compose up -d
sleep 3

# Step 6: Test health endpoint
echo ""
echo "Testing health endpoint..."
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ App is running"
else
    echo "❌ App failed to start"
    exit 1
fi

# Step 7: Verify the hash in settings
echo ""
echo "Verifying password in app..."
VERIFICATION=$(docker compose exec -T app python3 << 'PYEOF'
import bcrypt
from app.config import settings
import sys

password = sys.stdin.read().strip()
try:
    result = bcrypt.checkpw(password.encode(), settings.admin_password_hash.encode())
    print("SUCCESS" if result else "FAILED")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF
)

echo "$PASSWORD" | VERIFICATION_RESULT=$(docker compose exec -T app python3 -c "
import bcrypt
from app.config import settings
import sys
password = sys.stdin.read().strip()
result = bcrypt.checkpw(password.encode(), settings.admin_password_hash.encode())
print('SUCCESS' if result else 'FAILED')
")

if [ "$VERIFICATION_RESULT" = "SUCCESS" ]; then
    echo "✓ Password verification: SUCCESS"
    echo ""
    echo "=========================================="
    echo "✓✓✓ ALL DONE! ✓✓✓"
    echo "=========================================="
    echo ""
    echo "Your password is now set correctly."
    echo "Login at: http://$(hostname -I | awk '{print $1}'):8000"
    echo "Or: https://pricemanager.gtecombv.com"
    echo ""
else
    echo "❌ Password verification: FAILED"
    echo "Something went wrong. Check logs: docker compose logs app"
    exit 1
fi
