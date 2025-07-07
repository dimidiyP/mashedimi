#!/bin/bash

# Deployment script for demondimi.ru VPS
# This script deploys the Telegram bot to the production server

set -e  # Exit on any error

# Configuration
VPS_HOST="83.222.18.104"
VPS_USER="root"
VPS_PASSWORD="Y5(wP)Fr5Ggx"
DOMAIN="demondimi.ru"
BOT_DIR="/var/www/telegram-bot"
WEBHOOK_DIR="/var/www/$DOMAIN/bot"

# Check for required tools
if ! command -v sshpass &> /dev/null; then
    echo "❌ Error: sshpass is required but not installed"
    echo "   Install with: sudo apt-get install sshpass (Ubuntu/Debian)"
    echo "   Or: brew install sshpass (macOS)"
    exit 1
fi

# Check required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY environment variable is required"
    echo "   Set it with: export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_TOKEN environment variable is required"
    echo "   Set it with: export TELEGRAM_TOKEN='your-token-here'"
    exit 1
fi

echo "🚀 Starting deployment to $DOMAIN..."
echo "📡 Testing SSH connection..."

# Function to run commands on VPS
run_on_vps() {
    sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no "$VPS_USER@$VPS_HOST" "$1"
}

# Function to copy files to VPS
copy_to_vps() {
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no -r "$1" "$VPS_USER@$VPS_HOST:$2"
}

echo "📋 Step 1: Preparing VPS environment..."

# Create directories
run_on_vps "mkdir -p $BOT_DIR"
run_on_vps "mkdir -p $WEBHOOK_DIR" 
run_on_vps "mkdir -p /var/log/telegram-bot"

echo "📂 Step 2: Copying application files..."

# Copy bot files
copy_to_vps "./backend" "$BOT_DIR/"
copy_to_vps "./config" "$BOT_DIR/"
copy_to_vps "./core" "$BOT_DIR/"
copy_to_vps "./features" "$BOT_DIR/"
copy_to_vps "./scripts" "$BOT_DIR/"

# Copy webhook proxy
copy_to_vps "./deployment/webhook_proxy/demondimi_webhook.php" "$WEBHOOK_DIR/index.php"

echo "🔧 Step 3: Setting up environment and installing dependencies..."

# Create .env file on server
cat > .env << EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot_db"
STRIPE_API_KEY="sk_test_emergent"
OPENAI_API_KEY="$OPENAI_API_KEY"
TELEGRAM_TOKEN="$TELEGRAM_TOKEN"
EOF

copy_to_vps ".env" "$BOT_DIR/backend/"

# Install Python dependencies
run_on_vps "cd $BOT_DIR/backend && pip3 install -r requirements.txt"

echo "⚙️ Step 4: Setting up systemd service..."

# Create systemd service file
cat > telegram-bot.service << EOF
[Unit]
Description=Telegram Bot with Modular Architecture
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=$BOT_DIR/backend
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$BOT_DIR
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Copy and enable service
copy_to_vps "telegram-bot.service" "/etc/systemd/system/"
run_on_vps "systemctl daemon-reload"
run_on_vps "systemctl enable telegram-bot"

echo "🌐 Step 5: Configuring Nginx..."

# Create Nginx configuration for bot webhook
cat > demondimi-bot.conf << EOF
# Bot webhook configuration for demondimi.ru
location /bot/ {
    try_files \$uri \$uri/ @php;
    index index.php;
}

location @php {
    try_files \$uri =404;
    fastcgi_split_path_info ^(.+\.php)(/.+)\$;
    fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
    include fastcgi_params;
}

# Health check endpoint
location /bot/health {
    proxy_pass http://127.0.0.1:8001/api/health;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
}
EOF

copy_to_vps "demondimi-bot.conf" "/etc/nginx/snippets/"

# Update main Nginx config to include bot configuration
run_on_vps "grep -q 'include /etc/nginx/snippets/demondimi-bot.conf' /etc/nginx/sites-available/$DOMAIN || sed -i '/server_name $DOMAIN/a\\    include /etc/nginx/snippets/demondimi-bot.conf;' /etc/nginx/sites-available/$DOMAIN"

echo "🔄 Step 6: Starting services..."

# Test Nginx configuration
run_on_vps "nginx -t"

# Reload Nginx
run_on_vps "systemctl reload nginx"

# Start bot service
run_on_vps "systemctl restart telegram-bot"

# Wait a moment for service to start
sleep 5

echo "✅ Step 7: Verifying deployment..."

# Check service status
if run_on_vps "systemctl is-active --quiet telegram-bot"; then
    echo "✅ Telegram bot service is running"
else
    echo "❌ Telegram bot service failed to start"
    run_on_vps "systemctl status telegram-bot"
    exit 1
fi

# Test API endpoint
if run_on_vps "curl -f http://127.0.0.1:8001/api/test >/dev/null 2>&1"; then
    echo "✅ API endpoint is responding"
else
    echo "❌ API endpoint is not responding"
    exit 1
fi

# Test webhook endpoint
if run_on_vps "curl -f https://$DOMAIN/bot/ >/dev/null 2>&1"; then
    echo "✅ Webhook endpoint is accessible"
else
    echo "⚠️ Webhook endpoint test failed (SSL might not be ready yet)"
fi

echo "📊 Step 8: Deployment summary..."
echo "
🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!

🌐 Domain: https://$DOMAIN
🤖 Webhook URL: https://$DOMAIN/bot/
🔧 API Health Check: https://$DOMAIN/bot/health
📊 Local API: http://127.0.0.1:8001/api/test

📋 Service Management:
- Start: systemctl start telegram-bot
- Stop: systemctl stop telegram-bot  
- Restart: systemctl restart telegram-bot
- Status: systemctl status telegram-bot
- Logs: journalctl -u telegram-bot -f

📝 Log Files:
- Service logs: journalctl -u telegram-bot
- Webhook logs: /var/log/telegram_webhook.log
- Nginx logs: /var/log/nginx/access.log

🔧 Next Steps:
1. Set Telegram webhook: https://$DOMAIN/bot/
2. Test bot functionality
3. Monitor logs for any issues
"

# Cleanup temporary files
rm -f telegram-bot.service demondimi-bot.conf

echo "🚀 Deployment script completed!"