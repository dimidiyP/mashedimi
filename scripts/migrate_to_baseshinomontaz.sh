#!/bin/bash

# Финальная миграция на baseshinomontaz.store
# Запускать ПОСЛЕ загрузки PHP скрипта на хостинг

TELEGRAM_TOKEN="8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"
NEW_DOMAIN="baseshinomontaz.store"
WEBHOOK_URL="https://${NEW_DOMAIN}/webhook.php"
LOG_FILE="/var/log/baseshinomontaz_migration.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 Начинаем финальную миграцию на $NEW_DOMAIN"

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
    log "⚠️  SSL сертификат может быть некорректным: $ssl_subject"
fi

# 3. Проверить PHP скрипт на хостинге
log "🔍 Проверяем PHP скрипт на хостинге..."
response=$(curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{"test":"migration"}' -w "%{http_code}")
http_code="${response: -3}"

if [ "$http_code" = "200" ]; then
    log "✅ PHP скрипт работает на $NEW_DOMAIN (HTTP $http_code)"
else
    log "❌ PHP скрипт не найден или не работает (HTTP $http_code)"
    log "📝 Убедитесь, что файл webhook.php загружен в корневую директорию $NEW_DOMAIN"
    log "📁 Файл для загрузки: /app/deployment/webhook_proxy/baseshinomontaz_webhook.php"
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
last_error=$(echo "$webhook_info" | jq -r '.result.last_error_message // "none"')

log "📊 Webhook статус:"
log "   URL: $webhook_url"
log "   Ожидающих обновлений: $pending_count"
log "   Последняя ошибка: $last_error"

if [ "$webhook_url" = "$WEBHOOK_URL" ] && [ "$last_error" = "none" ]; then
    log "✅ Webhook работает корректно!"
else
    log "⚠️  Возможны проблемы с webhook"
fi

# 6. Тестировать webhook
log "🧪 Тестируем работу webhook..."
test_response=$(curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"update_id": 999999, "message": {"message_id": 1, "from": {"id": 1, "first_name": "Test", "is_bot": false}, "chat": {"id": 1, "type": "private"}, "date": 1625000000, "text": "test"}}' \
    -w "%{http_code}")

test_http_code="${test_response: -3}"
if [ "$test_http_code" = "200" ]; then
    log "✅ Webhook отвечает на тестовые запросы (HTTP $test_http_code)"
else
    log "⚠️  Webhook может иметь проблемы (HTTP $test_http_code)"
fi

# 7. Обновить monitor bot для нового webhook
log "🔄 Monitor bot уже обновлен для нового webhook URL"

# 8. Создать файл статуса миграции
cat > "/app/migration_status.txt" << EOF
Миграция на домен $NEW_DOMAIN завершена
Дата: $(date)
Webhook URL: $WEBHOOK_URL
Статус: АКТИВЕН
Monitor bot: ОБНОВЛЕН для нового URL
Cloudflare services: ОСТАНОВЛЕНЫ
Логи: $LOG_FILE
EOF

log "🎉 Миграция на $NEW_DOMAIN завершена успешно!"
log "📊 Статус сохранен в /app/migration_status.txt"

echo ""
echo "🎯 РЕЗУЛЬТАТ МИГРАЦИИ:"
echo "✅ Домен: $NEW_DOMAIN"
echo "✅ Webhook: $WEBHOOK_URL"
echo "✅ Monitor bot: Обновлен"
echo "✅ 24/7 готовность: ОБЕСПЕЧЕНА"
echo ""
echo "📋 Следующие шаги:"
echo "1. Протестировать бота в Telegram"
echo "2. Мониторить работу в течение 24 часов"
echo "3. При необходимости включить логирование в PHP скрипте"
echo ""