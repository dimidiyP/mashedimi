# 🚀 CI/CD PIPELINE SETUP
# Development → GitHub → Production

**Схема:** 34.58.165.144 (dev) → GitHub → 83.222.18.104 (prod)  
**Репозиторий:** https://github.com/dimidiyP/mashedimi (PRIVATE)  
**Домен:** baseshinomontaz.store → 83.222.18.104  

---

## 🏗️ АРХИТЕКТУРА CI/CD

### Development Environment (Emergent):
```yaml
Server: 34.58.165.144
Purpose: Development & Testing
Features:
  - Live coding and testing
  - Hot reload development
  - Supervisor monitoring
  - Automatic backups
  - Real-time debugging
```

### GitHub Repository (Central):
```yaml
Repo: github.com/dimidiyP/mashedimi
Access: Private repository
Branches:
  - main: Production-ready code
  - dev: Development branch
  - features/*: Feature branches
```

### Production Environment (Your VPS):
```yaml
Server: 83.222.18.104 (root access)
Domain: baseshinomontaz.store
Purpose: Production deployment
Features:
  - Stable 24/7 operation
  - Custom PHP scripts deployment
  - Full file system access
  - Production webhook endpoint
```

---

## 🔧 CI/CD WORKFLOW

### Phase 1: Development → GitHub
```mermaid
Development (Emergent) → "Save to GitHub" → Private Repo
```

### Phase 2: GitHub → Production
```mermaid
GitHub → GitHub Actions → SSH Deploy → Production VPS
```

### Complete Flow:
```
1. Code changes on 34.58.165.144
2. Test locally with supervisor
3. Click "Save to GitHub" button
4. GitHub Actions triggers
5. Automatic deployment to 83.222.18.104
6. baseshinomontaz.store webhook active
```

---

## 📂 REPOSITORY STRUCTURE

```
mashedimi/
├── .github/
│   └── workflows/
│       ├── deploy-production.yml
│       ├── test-development.yml
│       └── backup-production.yml
├── backend/
│   ├── server.py
│   ├── requirements.txt
│   ├── .env.example
│   └── config/
├── frontend/
│   ├── src/
│   ├── package.json
│   └── build/
├── deployment/
│   ├── scripts/
│   │   ├── deploy.sh
│   │   ├── setup-production.sh
│   │   └── backup.sh
│   ├── nginx/
│   │   └── baseshinomontaz.store.conf
│   ├── webhook_proxy/
│   │   └── webhook.php
│   └── systemd/
│       └── telegram-bot.service
├── docs/
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
└── scripts/
    ├── monitor_bot.py
    └── backup_system.py
```

---

## 🔑 GITHUB ACTIONS CONFIGURATION

### 1. Production Deployment Workflow
```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install -r backend/requirements.txt
        
    - name: Run tests
      run: |
        python -m pytest tests/ -v
        
    - name: Deploy to Production
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: 83.222.18.104
        username: root
        key: ${{ secrets.PRODUCTION_SSH_KEY }}
        script: |
          cd /opt/telegram-bot
          git pull origin main
          ./deployment/scripts/deploy.sh
          systemctl restart telegram-bot
          systemctl status telegram-bot
```

### 2. Test Development Workflow
```yaml
# .github/workflows/test-development.yml
name: Test Development

on:
  push:
    branches: [dev, 'features/*']
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: pip install -r backend/requirements.txt
      
    - name: Lint code
      run: |
        pip install flake8 black
        flake8 backend/
        black --check backend/
        
    - name: Run tests
      run: python -m pytest tests/ -v --cov=backend/
```

---

## 🚀 PRODUCTION DEPLOYMENT SCRIPTS

### 1. Main Deployment Script
```bash
#!/bin/bash
# deployment/scripts/deploy.sh

set -e

echo "🚀 Starting deployment to production..."

# Configuration
APP_DIR="/opt/telegram-bot"
SERVICE_NAME="telegram-bot"
DOMAIN="baseshinomontaz.store"

# Backup current version
echo "📦 Creating backup..."
cp -r $APP_DIR /opt/backups/telegram-bot-$(date +%Y%m%d_%H%M%S)

# Update dependencies
echo "📚 Installing dependencies..."
cd $APP_DIR
pip install -r backend/requirements.txt --upgrade

# Update nginx configuration
echo "🌐 Updating nginx configuration..."
cp deployment/nginx/baseshinomontaz.store.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/baseshinomontaz.store.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Deploy webhook PHP script
echo "📄 Deploying webhook script..."
cp deployment/webhook_proxy/webhook.php /var/www/baseshinomontaz.store/webhook.php
chown www-data:www-data /var/www/baseshinomontaz.store/webhook.php

# Update systemd service
echo "⚙️ Updating systemd service..."
cp deployment/systemd/telegram-bot.service /etc/systemd/system/
systemctl daemon-reload

# Test configuration
echo "🧪 Testing configuration..."
python backend/server.py --test-config

# Restart services
echo "🔄 Restarting services..."
systemctl restart $SERVICE_NAME
systemctl enable $SERVICE_NAME

# Update webhook
echo "📡 Updating Telegram webhook..."
curl -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://$DOMAIN/webhook.php\"}"

# Health check
echo "🏥 Running health check..."
sleep 10
if curl -f "https://$DOMAIN/webhook.php"; then
  echo "✅ Deployment successful!"
else
  echo "❌ Deployment failed!"
  exit 1
fi

echo "🎉 Production deployment completed!"
```

### 2. Production Setup Script
```bash
#!/bin/bash
# deployment/scripts/setup-production.sh

echo "🏗️ Setting up production environment..."

# Install system dependencies
apt update
apt install -y python3 python3-pip nginx git supervisor curl jq

# Create application directory
mkdir -p /opt/telegram-bot
mkdir -p /opt/backups
mkdir -p /var/www/baseshinomontaz.store
mkdir -p /var/log/telegram-bot

# Clone repository (will need SSH key setup)
cd /opt
git clone git@github.com:dimidiyP/mashedimi.git telegram-bot

# Install Python dependencies
cd /opt/telegram-bot
pip3 install -r backend/requirements.txt

# Setup environment variables
cp backend/.env.example backend/.env
echo "⚠️  Please edit /opt/telegram-bot/backend/.env with production values"

# Create systemd service
cp deployment/systemd/telegram-bot.service /etc/systemd/system/
systemctl daemon-reload

# Setup nginx
cp deployment/nginx/baseshinomontaz.store.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/baseshinomontaz.store.conf /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# Setup SSL certificate
certbot --nginx -d baseshinomontaz.store

# Setup log rotation
cat > /etc/logrotate.d/telegram-bot << EOF
/var/log/telegram-bot/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 root root
    postrotate
        systemctl reload telegram-bot
    endscript
}
EOF

echo "✅ Production environment setup completed!"
echo "📝 Next steps:"
echo "1. Edit /opt/telegram-bot/backend/.env"
echo "2. Run: systemctl start telegram-bot"
echo "3. Check: systemctl status telegram-bot"
```

---

## 🌐 NGINX CONFIGURATION

```nginx
# deployment/nginx/baseshinomontaz.store.conf
server {
    listen 80;
    server_name baseshinomontaz.store;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name baseshinomontaz.store;
    
    # SSL Configuration (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/baseshinomontaz.store/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/baseshinomontaz.store/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Root directory
    root /var/www/baseshinomontaz.store;
    index index.php index.html;
    
    # PHP webhook handling
    location = /webhook.php {
        try_files $uri =404;
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        
        # Telegram webhook specific
        client_max_body_size 20M;
        fastcgi_read_timeout 30s;
    }
    
    # Bot API proxy (optional)
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
    
    # Block unnecessary access
    location ~ /\.ht {
        deny all;
    }
    
    # Logging
    access_log /var/log/nginx/baseshinomontaz.store.access.log;
    error_log /var/log/nginx/baseshinomontaz.store.error.log;
}
```

---

## ⚙️ SYSTEMD SERVICE

```ini
# deployment/systemd/telegram-bot.service
[Unit]
Description=Telegram Family Bot
After=network.target mongodb.service
Wants=mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-bot
Environment=PYTHONPATH=/opt/telegram-bot
ExecStart=/usr/bin/python3 /opt/telegram-bot/backend/server.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telegram-bot

# Environment file
EnvironmentFile=/opt/telegram-bot/backend/.env

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/telegram-bot /var/log/telegram-bot /tmp

[Install]
WantedBy=multi-user.target
```

---

## 🔒 GITHUB SECRETS SETUP

### Required Secrets (Repository Settings → Secrets):
```yaml
PRODUCTION_SSH_KEY: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  [Your SSH private key for root@83.222.18.104]
  -----END OPENSSH PRIVATE KEY-----

TELEGRAM_TOKEN: "8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"

OPENAI_API_KEY: "your-openai-api-key"

MONGO_URL: "mongodb://localhost:27017"
```

---

## 📋 PRODUCTION ENVIRONMENT VARIABLES

```bash
# backend/.env (production)
TELEGRAM_TOKEN="8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"
OPENAI_API_KEY="your-openai-api-key"
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot_prod"
ENVIRONMENT="production"
LOG_LEVEL="INFO"
WEBHOOK_URL="https://baseshinomontaz.store/webhook.php"
```

---

## 🎯 DEPLOYMENT WORKFLOW

### 1. Development Phase:
```
1. Code changes on 34.58.165.144 (Emergent)
2. Test with supervisor: supervisorctl status
3. Test webhook: curl /api/health
4. Commit changes locally
```

### 2. GitHub Push:
```
1. Click "Save to GitHub" (push to main branch)
2. GitHub Actions automatically triggered
3. Tests run on GitHub runners
4. If tests pass → auto-deploy to production
```

### 3. Production Deployment:
```
1. SSH to 83.222.18.104
2. Pull latest code from GitHub
3. Install/update dependencies  
4. Deploy PHP webhook script
5. Restart systemd service
6. Update Telegram webhook URL
7. Health check verification
```

---

## 🚀 NEXT STEPS

### 1. Prepare Production Server (83.222.18.104):
```bash
# Run once on production server
curl -s https://raw.githubusercontent.com/dimidiyP/mashedimi/main/deployment/scripts/setup-production.sh | bash
```

### 2. Setup GitHub Repository:
```bash
# Add deployment workflows to repo
mkdir -p .github/workflows
# Copy workflow files
# Add secrets to GitHub repo settings
```

### 3. Configure SSH Access:
```bash
# Generate SSH key for GitHub Actions
ssh-keygen -t ed25519 -f github_deploy_key
# Add public key to production server
# Add private key to GitHub secrets
```

### 4. Test Deployment:
```bash
# Push to main branch
git push origin main
# Monitor GitHub Actions
# Verify production deployment
```

---

## 🎉 BENEFITS OF THIS SETUP

```yaml
✅ Professional CI/CD pipeline
✅ Automatic testing before deployment
✅ Zero-downtime deployments
✅ Full control over production server
✅ Private repository security
✅ Rollback capabilities
✅ Monitoring and logging
✅ SSL/HTTPS automatically managed
✅ Production-grade nginx configuration
✅ Systemd service management
```

**Ready to implement this CI/CD pipeline?** 🚀