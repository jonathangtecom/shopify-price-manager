#!/bin/bash
set -e

echo "=============================================="
echo "  Shopify Price Manager - VPS Setup Script"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER="$(whoami)"
fi

echo "Running as: $ACTUAL_USER"
echo ""

# Step 1: Get configuration from user
echo -e "${YELLOW}[1/7] Configuration${NC}"
echo "Please provide the following information:"
echo ""

read -p "Enter your domain (e.g., shopify.yourdomain.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Domain is required!${NC}"
    exit 1
fi

read -p "Enter your admin username [admin]: " ADMIN_USERNAME
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}

read -sp "Enter your admin password: " ADMIN_PASSWORD
echo ""
if [ -z "$ADMIN_PASSWORD" ]; then
    echo -e "${RED}Password is required!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Configuration collected${NC}"
echo ""

# Step 2: Clone repository
echo -e "${YELLOW}[2/7] Cloning repository${NC}"
cd /opt
if [ -d "shopify-price-manager" ]; then
    echo "Directory already exists. Pulling latest..."
    cd shopify-price-manager
    git pull
else
    git clone https://github.com/jonathangtecom/shopify-price-manager.git
    cd shopify-price-manager
fi
echo -e "${GREEN}✓ Repository ready${NC}"
echo ""

# Step 3: Generate secrets
echo -e "${YELLOW}[3/7] Generating secrets${NC}"

# Check if bcrypt is already available
if ! python3 -c "import bcrypt" 2>/dev/null; then
    echo "Installing Python bcrypt (via apt)..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-bcrypt > /dev/null
fi

echo "Generating password hash..."
ADMIN_PASSWORD_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$ADMIN_PASSWORD', bcrypt.gensalt()).decode())")

echo "Generating secret key..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo -e "${GREEN}✓ Secrets generated${NC}"
echo ""

# Step 4: Create .env file
echo -e "${YELLOW}[4/7] Creating .env file${NC}"
cat > .env << EOF
# Database
database_path=/app/data/app.db

# Session
session_secret=$SECRET_KEY

# Admin credentials (note: no username, app only uses password)
admin_password_hash=$ADMIN_PASSWORD_HASH

# Application
HOST=0.0.0.0
PORT=8000
EOF

chmod 600 .env
echo -e "${GREEN}✓ .env file created${NC}"
echo ""

# Step 5: Configure Caddy
echo -e "${YELLOW}[5/7] Configuring Caddy${NC}"
cat > /etc/caddy/Caddyfile << EOF
$DOMAIN {
    reverse_proxy localhost:8000
}
EOF

systemctl restart caddy
systemctl enable caddy
echo -e "${GREEN}✓ Caddy configured for $DOMAIN${NC}"
echo ""

# Step 6: Start application
echo -e "${YELLOW}[6/7] Starting application${NC}"
docker compose up -d --build

echo "Waiting for application to start..."
sleep 10

echo -e "${GREEN}✓ Application started${NC}"
echo ""

# Step 7: Verify deployment
echo -e "${YELLOW}[7/8] Verifying deployment${NC}"

# Check health endpoint
if curl -sf http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Check logs with: docker compose logs"
    exit 1
fi

# Check if containers are running
if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Containers running${NC}"
else
    echo -e "${RED}✗ Containers not running${NC}"
    docker compose ps
    exit 1
fi

echo ""

# Step 8: Set up cron job for daily sync at 1 AM CET
echo -e "${YELLOW}[8/8] Setting up daily sync schedule${NC}"

# Create log directory
mkdir -p /var/log/shopify-price-manager
chown $ACTUAL_USER:$ACTUAL_USER /var/log/shopify-price-manager

# Create cron job (1 AM CET = 0 1 * * * in CET timezone)
CRON_JOB="0 1 * * * cd /opt/shopify-price-manager && /usr/bin/docker compose exec -T app python scripts/run_sync.py >> /var/log/shopify-price-manager/sync.log 2>&1"

# Add to user's crontab
(crontab -u $ACTUAL_USER -l 2>/dev/null | grep -v "shopify-price-manager" ; echo "$CRON_JOB") | crontab -u $ACTUAL_USER -

echo -e "${GREEN}✓ Daily sync scheduled for 1 AM CET${NC}"

echo ""
echo "=============================================="
echo -e "${GREEN}  ✓ Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Your Shopify Price Manager is ready!"
echo ""
echo "📱 Access your app at: https://$DOMAIN"
echo "🔑 Password: [the password you entered]"
echo "⏰ Daily sync: 1 AM CET (automated)"
echo ""
echo "Useful commands:"
echo "  View logs:        cd /opt/shopify-price-manager && docker compose logs -f"
echo "  View sync logs:   tail -f /var/log/shopify-price-manager/sync.log"
echo "  Restart:          cd /opt/shopify-price-manager && docker compose restart"
echo "  Update app:       cd /opt/shopify-price-manager && git pull && docker compose up -d --build"
echo "  Run manual sync:  cd /opt/shopify-price-manager && docker compose exec app python scripts/run_sync.py"
echo "  Change password:  cd /opt/shopify-price-manager && ./set-password.sh"
echo ""
echo "Next steps:"
echo "1. Visit https://$DOMAIN in your browser"
echo "2. Login with your password"
echo "3. Add your Shopify store(s)"
echo "4. Run your first sync!"
echo ""
