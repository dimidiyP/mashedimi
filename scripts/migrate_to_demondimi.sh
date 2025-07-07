#!/bin/bash

# Автоматический переход на домен demondimi.ru
# Запускать после исправления SSL сертификата

TELEGRAM_TOKEN="8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"
NEW_DOMAIN="demondimi.ru"
WEBHOOK_URL="https://${NEW_DOMAIN}/webhook.php"
LOG_FILE="/var/log/demondimi_migration.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 Начинаем миграцию на домен $NEW_DOMAIN"

# 1. Проверить доступность домена
log "📋 Проверяем доступность домена..."
if curl -s -I "https://$NEW_DOMAIN/" | grep -q "HTTP.*200"; then
    log "✅ Домен $NEW_DOMAIN доступен!"
else
    log "❌ Домен $NEW_DOMAIN недоступен. Миграция прервана."
    exit 1
fi

# 2. Проверить SSL сертификат
log "🔒 Проверяем SSL сертификат..."
ssl_subject=$(openssl s_client -connect "$NEW_DOMAIN:443" -servername "$NEW_DOMAIN" </dev/null 2>/dev/null | openssl x509 -noout -subject 2>/dev/null)

if echo "$ssl_subject" | grep -q "$NEW_DOMAIN"; then
    log "✅ SSL сертификат корректный для $NEW_DOMAIN"
else
    log "❌ SSL сертификат некорректный. Найдено: $ssl_subject"
    log "⚠️  Продолжаем миграцию, но могут быть проблемы с webhook"
fi

# 3. Проверить, что PHP скрипт загружен на хостинг
log "🔍 Проверяем PHP скрипт на хостинге..."
if curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{"test":"migration"}' | grep -q -E "(forwarded|status)"; then
    log "✅ PHP скрипт работает на $NEW_DOMAIN"
else
    log "❌ PHP скрипт не найден или не работает на $WEBHOOK_URL"
    log "📝 Убедитесь, что файл webhook.php загружен в корневую директорию $NEW_DOMAIN"
    exit 1
fi

# 4. Установить новый webhook
log "📡 Устанавливаем webhook на $WEBHOOK_URL..."
response=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$WEBHOOK_URL\"}")

if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
    log "✅ Webhook успешно установлен на $WEBHOOK_URL"
else
    log "❌ Ошибка установки webhook: $response"
    exit 1
fi

# 5. Проверить статус webhook
log "🔍 Проверяем статус webhook..."
webhook_info=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getWebhookInfo")
webhook_url=$(echo "$webhook_info" | jq -r '.result.url')
pending_count=$(echo "$webhook_info" | jq -r '.result.pending_update_count')

if [ "$webhook_url" = "$WEBHOOK_URL" ]; then
    log "✅ Webhook активен: $webhook_url"
    log "📊 Ожидающих обновлений: $pending_count"
else
    log "❌ Webhook URL не соответствует ожидаемому"
    log "Expected: $WEBHOOK_URL"
    log "Actual: $webhook_url"
fi

# 6. Остановить временные сервисы
log "🛑 Останавливаем временные сервисы..."
sudo supervisorctl stop cloudflare-tunnel 2>/dev/null && log "✅ Cloudflare tunnel остановлен" || log "ℹ️  Cloudflare tunnel не запущен"
sudo supervisorctl stop tunnel-webhook-updater 2>/dev/null && log "✅ Tunnel updater остановлен" || log "ℹ️  Tunnel updater не запущен"

# 7. Тестировать webhook
log "🧪 Тестируем работу webhook..."
test_response=$(curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"update_id": 999999, "message": {"message_id": 1, "from": {"id": 1, "first_name": "Test", "is_bot": false}, "chat": {"id": 1, "type": "private"}, "date": 1625000000, "text": "test"}}')

if [ $? -eq 0 ]; then
    log "✅ Webhook отвечает на тестовые запросы"
else
    log "⚠️  Webhook может иметь проблемы с обработкой запросов"
fi

# 8. Создать файл статуса миграции
cat > "/app/migration_status.txt" << EOF
Миграция на домен $NEW_DOMAIN завершена
Дата: $(date)
Webhook URL: $WEBHOOK_URL
Статус: АКТИВЕН
Логи: $LOG_FILE
EOF

log "🎉 Миграция на $NEW_DOMAIN завершена успешно!"
log "📊 Статус сохранен в /app/migration_status.txt"
log "📝 Полные логи доступны в $LOG_FILE"

echo ""
echo "🎯 РЕЗУЛЬТАТ МИГРАЦИИ:"
echo "✅ Домен: $NEW_DOMAIN"
echo "✅ Webhook: $WEBHOOK_URL"
echo "✅ Статус: АКТИВЕН"
echo ""
echo "📋 Следующие шаги:"
echo "1. Протестировать бота в Telegram"
echo "2. Проверить логи webhook: tail -f https://$NEW_DOMAIN/webhook_log.txt"
echo "3. Мониторить работу в течение 24 часов"
echo ""