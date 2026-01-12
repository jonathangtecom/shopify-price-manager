# Shopify Price Manager

Automatically manage `compare_at_price` for products across multiple Shopify stores based on sales history and product age.

## Business Rules

| Condition | Action |
|-----------|--------|
| Product sold in last 60 days | `compare_at_price = price × 2` |
| Product created in last 30 days | `compare_at_price = price × 2` |
| Neither condition met | Remove `compare_at_price` |

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/jonathangtecom/shopify-price-manager.git
cd shopify-price-manager

# Run dev setup
bash dev.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Ask you to set a password
- Start dev server with auto-reload

Open http://localhost:8000

### Production Deployment (VPS with Docker)

**Requirements:** Ubuntu/Debian VPS with Docker installed

```bash
# On your VPS
git clone https://github.com/jonathangtecom/shopify-price-manager.git
cd shopify-price-manager

# Run automated setup
sudo bash setup-vps.sh
```

The script will:
- Install Docker and dependencies
- Set up the application
- Ask you to set an admin password
- Configure Caddy reverse proxy with SSL
- Schedule daily sync at 1 AM CET
- Start the application

Your app will be available at `https://your-domain.com`

### Setting Admin Password

After deployment, you can change your password anytime:

```bash
cd /opt/shopify-price-manager
./set-password.sh
```

Or pass password directly:
```bash
./set-password.sh YourNewPassword
```

## Getting Shopify API Token

For each store:

1. Go to Shopify admin → **Settings** → **Apps and sales channels**
2. Click **"Develop apps"** → **"Create an app"**
3. Click **"Configure Admin API scopes"** and enable:
   - `read_orders`
   - `read_products`
   - `write_products`
4. Click **"Install app"**
5. Copy the **"Admin API access token"** (starts with `shpat_`)

## Usage

1. Login at `https://your-domain.com`
2. Click **"Add Store"**
3. Enter:
   - Store name (e.g., "US Store")
   - Shopify domain (e.g., `mystore.myshopify.com`)
   - Admin API token
4. Click **"Sync"** to run the first sync

The app automatically syncs all stores daily at 1 AM CET.

## Useful Commands

```bash
# Update to latest version
cd /opt/shopify-price-manager
git pull
docker compose down && docker compose up -d --build

# View logs
docker compose logs -f

# Check status
docker compose ps

# Manually trigger sync for all stores
docker compose exec app python scripts/run_sync.py

# Restart
docker compose restart
```

## Security Features

- Bcrypt password hashing
- Session-based authentication
- Brute force protection (5 attempts, 5-minute lockout)
- SSL/HTTPS via Caddy (automatic Let's Encrypt)
- API rate limiting (Shopify bucket-based)

## Architecture

- **Backend:** FastAPI (Python 3.13)
- **Database:** SQLite (persistent Docker volume)
- **Deployment:** Docker + docker-compose
- **Reverse Proxy:** Caddy (SSL/HTTPS)
- **Scheduling:** cron (1 AM CET daily)
- **API:** Shopify GraphQL Admin API 2025-01

## Environment Variables

The app uses a `.env` file for configuration:

```bash
admin_password_hash=$$2b$$12$$...  # Bcrypt hash (set via set-password.sh)
session_secret=...                  # Auto-generated secure token
database_path=/app/data/app.db     # SQLite database location
```

**Note:** Use `set-password.sh` to manage passwords - don't edit `.env` manually.

## License

Proprietary - All rights reserved

Open http://localhost:8000
