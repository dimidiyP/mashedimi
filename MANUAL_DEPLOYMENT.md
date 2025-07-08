# Manual Deployment Guide for demondimi.ru

Если автоматический скрипт деплоя не работает из-за проблем с SSH, используйте ручной деплой.

## 🔧 Подключение к VPS

### Вариант 1: SSH с паролем
```bash
ssh root@83.222.18.104
# Пароль: Y5(wP)Fr5Ggx
```

### Вариант 2: Через веб-панель управления
Если SSH не работает, используйте веб-панель хостинга для доступа к файлам.

## 📂 Ручная установка

### 1. Создайте директории на сервере:
```bash
mkdir -p /var/www/telegram-bot
mkdir -p /var/www/demondimi.ru/bot
mkdir -p /var/log/telegram-bot
```

### 2. Скопируйте файлы проекта:
Загрузите через FTP, SFTP или веб-панель:
- `backend/` → `/var/www/telegram-bot/backend/`
- `config/` → `/var/www/telegram-bot/config/`
- `core/` → `/var/www/telegram-bot/core/`
- `features/` → `/var/www/telegram-bot/features/`
- `deployment/webhook_proxy/demondimi_webhook.php` → `/var/www/demondimi.ru/bot/index.php`

### 3. Создайте .env файл:
```bash
cat > /var/www/telegram-bot/backend/.env << EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot_db"
STRIPE_API_KEY="sk_test_emergent"
OPENAI_API_KEY="ваш-openai-ключ"
TELEGRAM_TOKEN="ваш-telegram-токен"
EOF
```

### 4. Установите зависимости:
```bash
cd /var/www/telegram-bot/backend
pip3 install -r requirements.txt
```

### 5. Создайте systemd сервис:
```bash
cat > /etc/systemd/system/telegram-bot.service << EOF
[Unit]
Description=Telegram Bot with Modular Architecture
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/telegram-bot/backend
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/var/www/telegram-bot
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### 6. Настройте Nginx:
```bash
cat > /etc/nginx/snippets/demondimi-bot.conf << EOF
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
```

Добавьте в конфигурацию Nginx для demondimi.ru:
```bash
# В файл /etc/nginx/sites-available/demondimi.ru добавьте строку:
include /etc/nginx/snippets/demondimi-bot.conf;
```

### 7. Запустите сервисы:
```bash
# Проверьте конфигурацию Nginx
nginx -t

# Перезагрузите Nginx
systemctl reload nginx

# Включите и запустите бот
systemctl daemon-reload
systemctl enable telegram-bot
systemctl start telegram-bot

# Проверьте статус
systemctl status telegram-bot
```

### 8. Проверьте работу:
```bash
# Проверьте API
curl http://127.0.0.1:8001/api/test

# Проверьте webhook
curl https://demondimi.ru/bot/

# Проверьте логи
journalctl -u telegram-bot -f
```

## 🔧 Установка Telegram webhook

После успешного деплоя установите webhook:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://demondimi.ru/bot/"}'
```

## 📊 Мониторинг

### Проверка статуса:
```bash
systemctl status telegram-bot
```

### Просмотр логов:
```bash
# Логи бота
journalctl -u telegram-bot -f

# Логи webhook
tail -f /var/log/telegram_webhook.log

# Логи Nginx
tail -f /var/log/nginx/access.log
```

### Управление сервисом:
```bash
# Остановить
systemctl stop telegram-bot

# Запустить
systemctl start telegram-bot

# Перезапустить
systemctl restart telegram-bot
```