# VPS Deployment Guide

This guide walks you through deploying the Shopify Price Manager on a VPS with Docker.

## Prerequisites

- VPS running Ubuntu 20.04+ (or any Linux distro)
- Domain name pointed to your VPS IP (A record)
- SSH access to your VPS

## 1. Initial VPS Setup

SSH into your VPS:
```bash
ssh root@your-server-ip
```

Update system packages:
```bash
apt update && apt upgrade -y
```

## 2. Install Docker & Docker Compose

Install Docker:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

Start Docker service:
```bash
systemctl start docker
systemctl enable docker
```

Verify installation:
```bash
docker --version
docker compose version
```

## 3. Install Caddy (Web Server with Auto-SSL)

Install Caddy:
```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy
```

## 4. Clone Repository

```bash
cd /opt
git clone https://github.com/yourusername/shopify-price-manager.git
cd shopify-price-manager
```

## 5. Configure Environment

Create `.env` file:
```bash
nano .env
```

Add your configuration:
```
# Database
DATABASE_PATH=/app/data/app.db

# Session
SECRET_KEY=your-super-secret-key-here-generate-a-random-one

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$your_bcrypt_hash_here

# Application
HOST=0.0.0.0
PORT=8000
```

**Generate a bcrypt hash for your password:**
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'your_password_here', bcrypt.gensalt()).decode())"
```

Copy the output and paste it as `ADMIN_PASSWORD_HASH` in your `.env` file.

**Generate a secret key:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as `SECRET_KEY` in your `.env` file.

## 6. Configure Caddy for Your Domain

Edit Caddy configuration:
```bash
nano /etc/caddy/Caddyfile
```

Add this configuration (replace `yourdomain.com` with your actual domain):
```
yourdomain.com {
    reverse_proxy localhost:8000
}
```

**That's it!** Caddy automatically handles SSL certificates from Let's Encrypt.

Restart Caddy:
```bash
systemctl restart caddy
systemctl enable caddy
```

## 7. Start the Application

Build and start the Docker container:
```bash
docker compose up -d --build
```

Check if it's running:
```bash
docker compose ps
docker compose logs -f
```

## 8. Verify Deployment

Check health endpoint:
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

Visit your domain in a browser:
```
https://yourdomain.com
```

You should see the login page with automatic HTTPS!

## Updating the Application

When you want to deploy updates:

```bash
cd /opt/shopify-price-manager
git pull
docker compose up -d --build
```

This will:
1. Pull the latest code
2. Rebuild the Docker image
3. Restart the container with zero downtime

## Managing the Application

**View logs:**
```bash
docker compose logs -f
```

**Restart the application:**
```bash
docker compose restart
```

**Stop the application:**
```bash
docker compose down
```

**Start the application:**
```bash
docker compose up -d
```

## Scheduled Syncs (1 AM CET Daily)

Set up automatic daily syncs at 1 AM CET using cron:

```bash
# Install Python dependencies in the container (if not already done)
docker compose exec app pip install -r requirements.txt

# Add cron job for 1 AM CET (adjust for your timezone)
# For CET (UTC+1), 1 AM CET = 00:00 UTC (midnight UTC in winter)
# For CEST (UTC+2 in summer), 1 AM CEST = 23:00 UTC (11 PM UTC)

# Open crontab
crontab -e

# Add this line (runs at 1 AM CET timezone)
0 1 * * * cd /opt/shopify-price-manager && docker compose exec -T app python scripts/run_sync.py >> /var/log/shopify-sync.log 2>&1
```

**Alternative: Use host timezone**

If your VPS is set to CET timezone:
```bash
# Check current timezone
timedatectl

# Set to CET if needed
timedatectl set-timezone Europe/Paris

# Then the cron job is simpler (1 AM local time)
0 1 * * * cd /opt/shopify-price-manager && docker compose exec -T app python scripts/run_sync.py >> /var/log/shopify-sync.log 2>&1
```

**Verify cron job:**
```bash
# List current cron jobs
crontab -l

# Check sync logs
tail -f /var/log/shopify-sync.log
```

**Manual sync (for testing):**
```bash
cd /opt/shopify-price-manager
docker compose exec app python scripts/run_sync.py
```

## Database Backups

Your SQLite database is stored in `./data/app.db`. To back it up:

```bash
# Create backup
cp ./data/app.db ./data/app.db.backup-$(date +%Y%m%d-%H%M%S)

# Or use a cron job for daily backups at 2 AM CET (after sync completes)
echo "0 2 * * * cd /opt/shopify-price-manager && cp ./data/app.db ./data/app.db.backup-\$(date +\%Y\%m\%d)" | crontab -e
```

## Troubleshooting

**Container won't start:**
```bash
docker compose logs
```

**Check if port 8000 is in use:**
```bash
netstat -tulpn | grep 8000
```

**Caddy SSL issues:**
```bash
systemctl status caddy
journalctl -u caddy -f
```

Make sure:
- Your domain's A record points to your VPS IP
- Port 80 and 443 are open in your firewall
- Caddy service is running

**Reset everything:**
```bash
docker compose down
docker compose up -d --build
```

## Security Recommendations

1. **Set up a firewall:**
```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

2. **Disable root SSH login:**
```bash
nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
systemctl restart sshd
```

3. **Keep system updated:**
```bash
apt update && apt upgrade -y
```

## Domain Setup (Answering Your Question)

**Do we need the domain in Docker?**

No! The domain is NOT configured in Docker at all. Here's how it works:

1. **Docker** runs your app on `localhost:8000` (internal port)
2. **Caddy** (running directly on the VPS) listens on ports 80/443
3. **Caddy** forwards requests from `yourdomain.com` → `localhost:8000`
4. **Caddy** automatically handles SSL certificates

So the flow is:
```
User visits https://yourdomain.com
         ↓
Caddy receives request (port 443)
         ↓
Caddy forwards to localhost:8000
         ↓
Docker container responds
         ↓
Caddy sends response back to user with SSL
```

You ONLY configure the domain in `/etc/caddy/Caddyfile`, not in Docker!

## Cost Estimate

- VPS (2GB RAM): $4-6/month (Hetzner, Vultr, DigitalOcean)
- Domain: $10-15/year
- Total: ~$5/month

Much cheaper than Platform-as-a-Service options ($12-20/month) and you get full control!
