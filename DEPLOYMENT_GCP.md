# Google Cloud Platform (GCP) Deployment Guide

This guide walks you through deploying the Shopify Price Manager on Google Cloud Platform using Cloud Run.

## Why GCP Cloud Run?

- **Serverless**: No server management
- **Auto-scaling**: Scales to zero when not in use
- **Cost-effective**: Pay only for actual usage
- **SQLite support**: Persistent volumes available
- **Integrated scheduling**: Cloud Scheduler for automated syncs

## Prerequisites

- Google Cloud account
- `gcloud` CLI installed ([install guide](https://cloud.google.com/sdk/docs/install))
- Domain name (optional, for custom domain)
- Docker installed locally (for testing)

## Cost Estimate

- **Cloud Run**: ~$5-10/month (mostly idle)
- **Cloud Scheduler**: $0.10/month
- **Cloud Storage** (backups): ~$1/month
- **Total**: ~$6-11/month

## 1. Initial Setup

### Install and Configure gcloud

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Initialize gcloud
gcloud init

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### Create Project Structure

```bash
# Clone your repo
git clone https://github.com/yourusername/shopify-price-manager.git
cd shopify-price-manager
```

## 2. Configure Secrets

GCP Cloud Run uses Secret Manager instead of `.env` files:

```bash
# Generate bcrypt password hash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'your_password_here', bcrypt.gensalt()).decode())"

# Generate secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Create secrets
gcloud secrets create ADMIN_PASSWORD_HASH --data-file=- <<EOF
$2b$12$your_bcrypt_hash_here
EOF

gcloud secrets create SESSION_SECRET --data-file=- <<EOF
your_generated_secret_key_here
EOF

# Grant Cloud Run access to secrets
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ADMIN_PASSWORD_HASH \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding SESSION_SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## 3. Update Dockerfile for GCP

No changes needed! The existing Dockerfile works perfectly with Cloud Run.

## 4. Deploy to Cloud Run

### First Deployment

```bash
# Build and deploy
gcloud run deploy shopify-price-manager \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --set-secrets="ADMIN_PASSWORD_HASH=ADMIN_PASSWORD_HASH:latest,SESSION_SECRET=SESSION_SECRET:latest" \
  --set-env-vars="HOST=0.0.0.0,PORT=8080,DATABASE_PATH=/data/app.db"
```

**Note:** Cloud Run uses `/data` for persistent storage (if configured).

### For Persistent SQLite Database

Cloud Run is stateless by default. For SQLite persistence, you need Cloud SQL or mounted storage:

**Option A: Use Cloud SQL (PostgreSQL) - Recommended for production**

```bash
# Create Cloud SQL instance
gcloud sql instances create shopify-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=europe-west1

# Deploy with Cloud SQL
gcloud run deploy shopify-price-manager \
  --source . \
  --add-cloudsql-instances=YOUR_PROJECT_ID:europe-west1:shopify-db \
  --set-env-vars="DATABASE_URL=postgresql://user:pass@/shopify?host=/cloudsql/YOUR_PROJECT_ID:europe-west1:shopify-db"
```

**Option B: Use Cloud Storage + Local SQLite (Simpler)**

Create a startup script that syncs SQLite from Cloud Storage:

```bash
# Create bucket
gsutil mb -l europe-west1 gs://YOUR_PROJECT_ID-shopify-db

# Update Dockerfile to add sync script (see below)
```

**For this app, I recommend keeping VPS deployment** since it's designed for SQLite and local storage. Cloud Run works better with Cloud SQL.

## 5. Set Up Scheduled Syncs (1 AM CET)

### Create Cloud Scheduler Job

```bash
# Get your Cloud Run service URL
SERVICE_URL=$(gcloud run services describe shopify-price-manager \
  --region=europe-west1 \
  --format='value(status.url)')

# Create scheduler job for 1 AM CET (midnight UTC in winter, 23:00 UTC in summer)
# Using 1 AM UTC to handle CET timezone (adjust for DST if needed)
gcloud scheduler jobs create http shopify-sync-daily \
  --location=europe-west1 \
  --schedule="0 1 * * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/api/sync/all" \
  --http-method=POST \
  --oidc-service-account-email="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --description="Daily Shopify price sync at 1 AM CET"
```

**Important:** The schedule `0 1 * * *` means 1:00 AM in the specified timezone (CET/CEST).

### Manual Trigger (for testing)

```bash
gcloud scheduler jobs run shopify-sync-daily --location=europe-west1
```

## 6. Monitor and Logs

### View Logs

```bash
# Real-time logs
gcloud run services logs tail shopify-price-manager --region=europe-west1

# Recent logs
gcloud run services logs read shopify-price-manager --region=europe-west1 --limit=100
```

### Access the Web UI

```bash
# Get service URL
gcloud run services describe shopify-price-manager \
  --region=europe-west1 \
  --format='value(status.url)'
```

Visit the URL and login with your admin credentials.

## 7. Custom Domain (Optional)

### Map Custom Domain

```bash
# Add domain mapping
gcloud run domain-mappings create \
  --service=shopify-price-manager \
  --domain=shopify.yourdomain.com \
  --region=europe-west1
```

Follow the instructions to add DNS records.

## 8. Database Backups

### Automated Backups to Cloud Storage

Create a backup script:

```bash
# Create backup bucket
gsutil mb -l europe-west1 gs://YOUR_PROJECT_ID-shopify-backups

# Add to Cloud Scheduler (daily at 2 AM CET)
gcloud scheduler jobs create http shopify-backup-daily \
  --location=europe-west1 \
  --schedule="0 2 * * *" \
  --time-zone="Europe/Paris" \
  --uri="${SERVICE_URL}/api/backup" \
  --http-method=POST \
  --oidc-service-account-email="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --description="Daily database backup at 2 AM CET"
```

## 9. Update Deployment

When you want to deploy updates:

```bash
cd /path/to/shopify-price-manager
git pull
gcloud run deploy shopify-price-manager --source .
```

Cloud Run will:
1. Build new container
2. Deploy with zero downtime
3. Route traffic to new version
4. Keep old version for rollback

### Rollback to Previous Version

```bash
# List revisions
gcloud run revisions list --service=shopify-price-manager --region=europe-west1

# Rollback to specific revision
gcloud run services update-traffic shopify-price-manager \
  --to-revisions=shopify-price-manager-00001-abc=100 \
  --region=europe-west1
```

## 10. Security Best Practices

### Restrict Access

```bash
# Require authentication (if you only access via scheduler)
gcloud run services update shopify-price-manager \
  --no-allow-unauthenticated \
  --region=europe-west1
```

### Enable HTTPS

Cloud Run automatically provides HTTPS with managed certificates. No configuration needed!

## 11. Troubleshooting

### Service Won't Start

```bash
# Check logs
gcloud run services logs read shopify-price-manager --region=europe-west1 --limit=50

# Check service status
gcloud run services describe shopify-price-manager --region=europe-west1
```

### Database Issues

If using SQLite on Cloud Run, remember that the filesystem is ephemeral. Consider:
1. Migrating to Cloud SQL (PostgreSQL)
2. Using Cloud Storage for persistence
3. Keeping VPS deployment for simplicity

### Scheduler Not Triggering

```bash
# Check scheduler job status
gcloud scheduler jobs describe shopify-sync-daily --location=europe-west1

# View scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=shopify-sync-daily" --limit=50
```

## Comparison: GCP vs VPS

| Feature | GCP Cloud Run | VPS (Hetzner) |
|---------|---------------|---------------|
| **Cost** | $6-11/month | $4-5/month |
| **Setup** | Medium (secrets, scheduler) | Simple (Docker + Cron) |
| **SQLite** | Difficult (needs Cloud SQL) | Native support |
| **Scaling** | Automatic | Manual |
| **Maintenance** | Minimal | OS updates needed |
| **Best For** | Multiple apps, PostgreSQL | Simple SQLite apps |

## Recommendation

**For this specific app (Shopify Price Manager):**

Given that:
- App is designed for SQLite
- Database is small (<50MB)
- Traffic is minimal (just you + daily sync)
- Needs persistent storage

**I recommend VPS deployment** (Hetzner + Docker) as documented in [DEPLOYMENT.md](DEPLOYMENT.md).

**Use GCP Cloud Run if:**
- You want to migrate to PostgreSQL
- You need auto-scaling
- You're already on GCP
- You want serverless architecture

## Alternative: GCP Compute Engine

If you want GCP but prefer VPS-style deployment:

```bash
# Create VM instance
gcloud compute instances create shopify-price-manager \
  --machine-type=e2-micro \
  --zone=europe-west1-b \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB

# SSH and follow DEPLOYMENT.md instructions
gcloud compute ssh shopify-price-manager --zone=europe-west1-b
```

Then follow the standard [DEPLOYMENT.md](DEPLOYMENT.md) guide - it works identically on GCP Compute Engine!

**GCP Compute Engine e2-micro**: ~$7/month (similar to Hetzner but on GCP infrastructure)
