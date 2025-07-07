#!/bin/bash

# Production Setup Script for VPS 83.222.18.104
# Run this ONCE on the production server to prepare environment

set -e

echo "🏗️ Setting up production environment on $(hostname)..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "📚 Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    git \
    curl \
    jq \
    certbot \
    python3-certbot-nginx \
    mongodb \
    supervisor \
    htop \
    ufw

# Setup firewall
echo "🔥 Configuring firewall..."
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

# Create application directory
echo "📁 Creating application directories..."
mkdir -p /opt/telegram-bot
mkdir -p /opt/backups
mkdir -p /var/www/baseshinomontaz.store
mkdir -p /var/log/telegram-bot

# Setup SSH key for GitHub (if not exists)
if [ ! -f /root/.ssh/id_ed25519 ]; then
    echo "🔑 Generating SSH key for GitHub..."
    ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
    echo "📋 Add this public key to your GitHub account:"
    cat /root/.ssh/id_ed25519.pub
    echo ""
    echo "⏸️  Press Enter after adding the key to GitHub..."
    read
fi

# Clone repository
echo "📥 Cloning repository..."
cd /opt
if [ ! -d "telegram-bot" ]; then
    git clone git@github.com:dimidiyP/mashedimi.git telegram-bot
else
    cd telegram-bot
    git pull origin main
fi

cd /opt/telegram-bot

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r backend/requirements.txt

# Setup MongoDB
echo "🗃️ Configuring MongoDB..."
systemctl enable mongodb
systemctl start mongodb

# Create MongoDB user (optional)
mongo --eval "
use admin
db.createUser({
  user: 'telegrambot',
  pwd: 'securepassword123',
  roles: ['readWriteAnyDatabase']
})
" || echo "MongoDB user might already exist"

# Setup environment file
echo "⚙️ Creating environment configuration..."
if [ ! -f backend/.env ]; then
    cat > backend/.env << 'EOF'
TELEGRAM_TOKEN="WILL_BE_SET_BY_GITHUB_ACTIONS"
OPENAI_API_KEY="WILL_BE_SET_BY_GITHUB_ACTIONS"
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot_prod"
ENVIRONMENT="production"
LOG_LEVEL="INFO"
EOF
    echo "📝 Environment file created at backend/.env"
fi

# Setup nginx configuration
echo "🌐 Configuring nginx..."
cat > /etc/nginx/sites-available/baseshinomontaz.store << 'EOF'
server {
    listen 80;
    server_name baseshinomontaz.store;
    
    # Document root
    root /var/www/baseshinomontaz.store;
    index index.php index.html;
    
    # PHP handling
    location ~ \.php$ {
        try_files $uri =404;
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        
        # Telegram webhook specific
        client_max_body_size 20M;
        fastcgi_read_timeout 30s;
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "OK Production Server\n";
        add_header Content-Type text/plain;
    }
    
    # Security
    location ~ /\.ht {
        deny all;
    }
    
    # Logging
    access_log /var/log/nginx/baseshinomontaz.store.access.log;
    error_log /var/log/nginx/baseshinomontaz.store.error.log;
}
EOF

# Enable nginx site
ln -sf /etc/nginx/sites-available/baseshinomontaz.store /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Install PHP for webhook
echo "🐘 Installing PHP for webhook..."
apt install -y php-fpm php-curl php-json php-mbstring

# Test nginx configuration
nginx -t && systemctl restart nginx

# Setup SSL certificate
echo "🔒 Setting up SSL certificate..."
certbot --nginx -d baseshinomontaz.store --non-interactive --agree-tos --email admin@baseshinomontaz.store || {
    echo "⚠️ SSL setup failed. You may need to configure DNS first."
    echo "📝 Run this after DNS is configured: certbot --nginx -d baseshinomontaz.store"
}

# Create systemd service template
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/telegram-bot.service << 'EOF'
[Unit]
Description=Telegram Family Bot
After=network.target mongodb.service
Wants=mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-bot
ExecStart=/usr/bin/python3 /opt/telegram-bot/backend/server.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telegram-bot
EnvironmentFile=/opt/telegram-bot/backend/.env

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable telegram-bot

# Setup log rotation
echo "📋 Setting up log rotation..."
cat > /etc/logrotate.d/telegram-bot << 'EOF'
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

# Create simple monitoring script
echo "📊 Creating monitoring script..."
cat > /opt/telegram-bot/scripts/monitor-production.sh << 'EOF'
#!/bin/bash
# Simple production monitoring

echo "=== Telegram Bot Production Status ==="
echo "Date: $(date)"
echo ""

echo "🔧 Service Status:"
systemctl status telegram-bot --no-pager -l | head -10

echo ""
echo "🌐 Nginx Status:"
systemctl status nginx --no-pager | head -5

echo ""
echo "🗃️ MongoDB Status:"
systemctl status mongodb --no-pager | head -5

echo ""
echo "💾 Disk Usage:"
df -h / | tail -1

echo ""
echo "🧠 Memory Usage:"
free -h | head -2

echo ""
echo "📡 Webhook Test:"
curl -s -o /dev/null -w "%{http_code}" https://baseshinomontaz.store/webhook.php || echo "Failed"

echo ""
echo "📊 Recent Logs:"
journalctl -u telegram-bot --no-pager -l -n 5
EOF

chmod +x /opt/telegram-bot/scripts/monitor-production.sh

# Setup cron for monitoring
echo "⏰ Setting up monitoring cron..."
(crontab -l 2>/dev/null; echo "*/15 * * * * /opt/telegram-bot/scripts/monitor-production.sh >> /var/log/telegram-bot/monitor.log 2>&1") | crontab -

# Final permissions
echo "🔐 Setting up permissions..."
chown -R www-data:www-data /var/www/baseshinomontaz.store/
chown -R root:root /opt/telegram-bot/
chmod +x /opt/telegram-bot/scripts/*.sh

echo ""
echo "✅ Production environment setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Verify DNS: baseshinomontaz.store → 83.222.18.104"
echo "2. Add GitHub Deploy Key:"
echo "   - Go to GitHub repo Settings → Deploy keys"
echo "   - Add this public key:"
cat /root/.ssh/id_ed25519.pub
echo ""
echo "3. Add GitHub Secrets:"
echo "   - PRODUCTION_SSH_KEY (private key below)"
echo "   - TELEGRAM_TOKEN"
echo "   - OPENAI_API_KEY"
echo ""
echo "🔑 Private key for GitHub secrets:"
echo "-----"
cat /root/.ssh/id_ed25519
echo "-----"
echo ""
echo "4. Test deployment: git push to main branch"
echo "5. Monitor: /opt/telegram-bot/scripts/monitor-production.sh"
echo ""
echo "🎉 Ready for CI/CD deployment!"