# Shopify Price Manager

Automatically manage `compare_at_price` for products across multiple Shopify stores based on sales history and product age.

## Business Rules

| Condition | Action |
|-----------|--------|
| Product sold in last 60 days | `compare_at_price = price × 2` |
| Product created in last 30 days | `compare_at_price = price × 2` |
| Neither condition met | Remove `compare_at_price` |

## Local Development (macOS/Linux)

```bash
unzip shopify-price-manager.zip
cd shopify-price-manager
bash dev.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Ask you to set a password
- Start dev server with auto-reload

Open http://localhost:8000

## Production (VPS)

### One-Command Setup

Upload the files to your VPS (Ubuntu/Debian), then:

```bash
cd shopify-price-manager
sudo bash setup.sh
```

The script will:
- Install Python, nginx, and dependencies
- Ask you to set an admin password
- Configure systemd service
- Set up nginx reverse proxy
- Schedule daily sync at 1 AM
- Optionally set up SSL

That's it! Open your browser to `http://your-server-ip`

### After Setup

1. Login with the password you set
2. Click **"Add Store"**
3. Enter:
   - Store name (e.g., "US Store")
   - Shopify domain (e.g., `mystore.myshopify.com`)
   - Admin API token (see below)
4. Click **"Sync"** to run the first sync

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

## Useful Commands

```bash
# Check status
sudo systemctl status shopify-price-manager

# View live logs
sudo journalctl -u shopify-price-manager -f

# Restart app
sudo systemctl restart shopify-price-manager

# View sync logs
cat /var/log/shopify-sync.log

# Manually trigger sync
cd /path/to/app && source venv/bin/activate && python scripts/run_sync.py
```

## Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/hash_password.py yourpassword  # Copy output to .env
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000
