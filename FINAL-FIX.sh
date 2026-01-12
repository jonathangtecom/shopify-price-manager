#!/bin/bash
set -e

# ONE COMMAND FIX - No git pull needed, run this directly
echo "Enter password (e.g., 1234): "
read -s PW
echo ""

cd /opt/shopify-price-manager

# Generate hash and escape $ as $$
HASH=$(python3 -c "import bcrypt; h=bcrypt.hashpw('$PW'.encode(), bcrypt.gensalt()).decode(); print(h.replace('\$', '\$\$'))")

# Get existing session secret or generate new
if [ -f .env ] && grep -q "^session_secret=" .env; then
    SECRET=$(grep "^session_secret=" .env | cut -d= -f2 | sed 's/\$\$/$/g')
    SECRET_ESC="${SECRET//\$/\$\$}"
else
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    SECRET_ESC="${SECRET//\$/\$\$}"
fi

# Write .env (no quotes, just escaped $$)
cat > .env << EOF
admin_password_hash=$HASH
session_secret=$SECRET_ESC
database_path=/app/data/app.db
EOF

echo "✓ .env written"
echo ""
echo "Restarting..."
docker compose down
docker compose up -d
sleep 3

echo ""
echo "Testing login..."
RESULT=$(docker compose exec -T app python3 << PYEOF
import bcrypt
from app.config import settings
password = "$PW"
try:
    match = bcrypt.checkpw(password.encode(), settings.admin_password_hash.encode())
    print("SUCCESS" if match else "FAILED")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF
)

if [ "$RESULT" = "SUCCESS" ]; then
    echo "✓✓✓ LOGIN WORKS ✓✓✓"
    echo ""
    echo "Go to: https://pricemanager.gtecombv.com"
else
    echo "❌ Still failed: $RESULT"
    echo ""
    echo "Check .env file:"
    cat .env
fi
