#!/bin/bash
# Quick diagnostic - check .env and test password

echo "=============================================="
echo "  Password Diagnostic"
echo "=============================================="
echo ""

cd /opt/shopify-price-manager

echo "1. Current .env file (with hidden secrets):"
echo "---"
cat .env | sed 's/admin_password_hash=.*/admin_password_hash=<hidden>/' | sed 's/session_secret=.*/session_secret=<hidden>/' | sed 's/ADMIN_PASSWORD_HASH=.*/ADMIN_PASSWORD_HASH=<hidden>/' | sed 's/SECRET_KEY=.*/SECRET_KEY=<hidden>/'
echo "---"
echo ""

echo "2. Checking variable names (should be lowercase):"
if grep -q "^admin_password_hash=" .env; then
    echo "✓ Correct: admin_password_hash (lowercase)"
elif grep -q "^ADMIN_PASSWORD_HASH=" .env; then
    echo "✗ WRONG: ADMIN_PASSWORD_HASH (uppercase) - app won't read this!"
else
    echo "✗ ERROR: No password hash found!"
fi
echo ""

echo "3. Testing password verification:"
read -sp "Enter the password you're trying to use: " TEST_PW
echo ""

# Get the hash from .env (try both cases)
HASH=$(grep "^admin_password_hash=" .env | cut -d= -f2)
if [ -z "$HASH" ]; then
    HASH=$(grep "^ADMIN_PASSWORD_HASH=" .env | cut -d= -f2)
fi

if [ -z "$HASH" ]; then
    echo "✗ ERROR: Could not find password hash in .env"
    exit 1
fi

# Test if password matches hash
echo "Testing password against hash..."
python3 << EOF
import bcrypt
password = b'$TEST_PW'
hash_str = '$HASH'
try:
    result = bcrypt.checkpw(password, hash_str.encode('utf-8'))
    if result:
        print("✓ PASSWORD MATCHES HASH - The problem is variable names!")
    else:
        print("✗ PASSWORD DOES NOT MATCH - Need to reset password")
except Exception as e:
    print(f"✗ ERROR checking password: {e}")
EOF

echo ""
echo "4. What to do:"
echo "   If variable names are uppercase → Run: sudo ./troubleshoot-login.sh"
echo "   If password doesn't match → Run: sudo ./reset-password.sh"
echo ""
