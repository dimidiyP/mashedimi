# 🚀 Telegram Family Bot - Production Deployment

## 📋 CI/CD Pipeline Overview

```
Development (34.58.165.144) → GitHub → Production (83.222.18.104)
        ↓                       ↓              ↓
   Emergent Platform      Private Repo    Your VPS + baseshinomontaz.store
```

## 🏗️ Infrastructure

### Development Environment
- **Server**: 34.58.165.144 (Emergent Platform)
- **Purpose**: Development, testing, hot reload
- **Domain**: preview.emergentagent.com (temporary)

### Production Environment  
- **Server**: 83.222.18.104 (Your VPS)
- **Domain**: baseshinomontaz.store
- **Purpose**: 24/7 production operation

### GitHub Repository
- **URL**: https://github.com/dimidiyP/mashedimi
- **Type**: Private repository
- **CI/CD**: GitHub Actions

## 🚀 Quick Start

### 1. Setup Production Server (One Time)
```bash
# On production server (83.222.18.104)
curl -s https://raw.githubusercontent.com/dimidiyP/mashedimi/main/deployment/scripts/setup-production.sh | bash
```

### 2. Configure GitHub Repository
1. Add deploy key to GitHub repo settings
2. Add secrets to GitHub repo:
   - `PRODUCTION_SSH_KEY`: SSH private key for server access
   - `TELEGRAM_TOKEN`: Your Telegram bot token
   - `OPENAI_API_KEY`: Your OpenAI API key

### 3. Deploy
```bash
# From development environment or local machine
git push origin main
```

GitHub Actions will automatically:
- Run tests
- Deploy to production server
- Restart services
- Update webhook URL

## 📁 Project Structure

```
mashedimi/
├── .github/workflows/          # GitHub Actions
│   └── deploy-production.yml   # Main deployment workflow
├── backend/                    # Python FastAPI application
│   ├── server.py              # Main bot application
│   ├── requirements.txt       # Python dependencies
│   └── .env.example          # Environment variables template
├── deployment/                # Deployment configuration
│   ├── scripts/              # Deployment scripts
│   │   └── setup-production.sh
│   └── webhook_proxy/        # PHP webhook proxy
│       └── baseshinomontaz_webhook.php
├── scripts/                   # Operational scripts
│   ├── monitor_bot.py        # Bot monitoring
│   └── backup_system.py      # Backup system
└── documentation/            # Project documentation
```

## 🔄 Deployment Workflow

### Automatic Deployment (Recommended)
1. **Code changes** on development environment
2. **Test locally** with supervisor
3. **Commit & push** to main branch
4. **GitHub Actions** automatically deploys
5. **Production ready** on baseshinomontaz.store

### Manual Deployment (Backup)
```bash
# On production server
cd /opt/telegram-bot
git pull origin main
pip3 install -r backend/requirements.txt --upgrade
systemctl restart telegram-bot
```

## 🌐 Webhook Configuration

### Production Webhook Flow
```
Telegram → baseshinomontaz.store/webhook.php → localhost:8001/api/webhook
```

The PHP proxy script automatically forwards Telegram webhooks to the local FastAPI application.

## 📊 Monitoring

### Service Status
```bash
# Check bot service
systemctl status telegram-bot

# Check nginx
systemctl status nginx

# Check logs
journalctl -u telegram-bot -f

# Monitor webhook
tail -f /var/log/telegram-bot/webhook.log
```

### Health Checks
- **Bot Health**: `https://baseshinomontaz.store/health`
- **Webhook Test**: `https://baseshinomontaz.store/webhook.php`
- **Service Status**: `systemctl status telegram-bot`

## 🔧 Configuration

### Environment Variables (Production)
```bash
# /opt/telegram-bot/backend/.env
TELEGRAM_TOKEN="your-telegram-bot-token"
OPENAI_API_KEY="your-openai-api-key"
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot_prod"
ENVIRONMENT="production"
```

### Nginx Configuration
- **Config**: `/etc/nginx/sites-available/baseshinomontaz.store`
- **SSL**: Managed by Certbot (Let's Encrypt)
- **Logs**: `/var/log/nginx/baseshinomontaz.store.*.log`

## 🔒 Security

### SSL/TLS
- **Provider**: Let's Encrypt (Certbot)
- **Auto-renewal**: Configured
- **HTTPS redirect**: Enabled

### Firewall
```bash
# UFW rules
ufw allow ssh
ufw allow http
ufw allow https
```

### Access Control
- **SSH**: Key-based authentication only
- **GitHub**: Private repository with deploy keys
- **Secrets**: Stored in GitHub Actions secrets

## 📋 Maintenance

### Regular Tasks
- **Updates**: Automatic via GitHub Actions on push
- **SSL renewal**: Automatic via Certbot
- **Log rotation**: Configured via logrotate
- **Monitoring**: Automated health checks

### Backup
```bash
# Manual backup
cp -r /opt/telegram-bot /opt/backups/telegram-bot-$(date +%Y%m%d_%H%M%S)

# Database backup
mongodump --db telegram_bot_prod --out /opt/backups/mongodb-$(date +%Y%m%d_%H%M%S)
```

## 🚨 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs
journalctl -u telegram-bot --no-pager -l

# Check Python dependencies
cd /opt/telegram-bot && python3 -c "import server"

# Check environment file
cat /opt/telegram-bot/backend/.env
```

#### Webhook Not Working
```bash
# Test webhook endpoint
curl -X POST https://baseshinomontaz.store/webhook.php \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Check nginx logs
tail -f /var/log/nginx/baseshinomontaz.store.error.log

# Check PHP logs
tail -f /var/log/php8.1-fpm.log
```

#### Deployment Failed
```bash
# Check GitHub Actions logs in repository
# Check SSH access to production server
ssh root@83.222.18.104

# Verify GitHub deploy key
ssh -T git@github.com
```

### Emergency Procedures

#### Rollback to Previous Version
```bash
# Restore from backup
cd /opt/backups
ls -la | grep telegram-bot
cp -r telegram-bot-YYYYMMDD_HHMMSS /opt/telegram-bot
systemctl restart telegram-bot
```

#### Manual Webhook Reset
```bash
# Reset webhook to production
curl -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://baseshinomontaz.store/webhook.php"}'
```

## 📞 Support

### Logs Location
- **Application**: `journalctl -u telegram-bot`
- **Webhook**: `/var/log/telegram-bot/webhook.log`
- **Nginx**: `/var/log/nginx/baseshinomontaz.store.*.log`
- **System**: `/var/log/syslog`

### Useful Commands
```bash
# Check all services
systemctl status telegram-bot nginx mongodb

# Monitor in real-time
watch 'systemctl status telegram-bot --no-pager -l'

# Check webhook status
curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getWebhookInfo" | jq .

# Test bot health
curl https://baseshinomontaz.store/health
```

---

## 🎉 Success Metrics

When everything is working correctly:
- ✅ **Service Status**: `systemctl status telegram-bot` shows "active (running)"
- ✅ **Webhook Active**: Telegram webhook info shows baseshinomontaz.store URL
- ✅ **SSL Valid**: HTTPS certificate valid and auto-renewing
- ✅ **Bot Responsive**: Bot responds to commands in Telegram
- ✅ **Logs Clean**: No error messages in application logs
- ✅ **Auto-deployment**: GitHub push triggers successful deployment

**Your Telegram Family Bot is now running in a professional production environment!** 🚀