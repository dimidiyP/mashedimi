# Настройка постоянного webhook для домена baseshinomontaz.store

## Текущая ситуация
- Домен `baseshinomontaz.store` не разрешается через DNS
- Webhook временно установлен на `preview.emergentagent.com` URL
- Созданы PHP скрипты для проксирования webhook запросов

## Необходимые шаги для настройки постоянного webhook

### 1. Проверить DNS настройки домена
```bash
# Проверить разрешение домена
nslookup baseshinomontaz.store

# Проверить доступность
curl -I https://baseshinomontaz.store/
```

### 2. Настроить HTTPS на домене
- Домен должен поддерживать HTTPS (обязательно для Telegram webhooks)
- Убедиться, что SSL сертификат действителен

### 3. Загрузить PHP скрипты на сервер
Скрипты созданы в папке `/app/`:
- `webhook.php` - базовый прокси скрипт
- `smart_webhook.php` - умный скрипт с возможностью обновления URL

### 4. Настроить webhook через API
```bash
# Установить webhook на постоянный домен
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://baseshinomontaz.store/webhook.php"}'
```

### 5. Обновление URL VPS (для smart_webhook.php)
```bash
# Обновить URL VPS в smart_webhook.php
curl -X POST "https://baseshinomontaz.store/smart_webhook.php" \
  -d "action=update_url" \
  -d "new_url=https://NEW_VPS_URL"
```

## Альтернативные решения
1. **Использовать подменный домен**: Если основной домен недоступен
2. **Настроить ngrok**: Для временного туннеля 
3. **Использовать Cloudflare Tunnel**: Для стабильного соединения

## Мониторинг webhook
- Логи webhook сохраняются в `webhook_log.txt`
- Конфигурация VPS URL в `webhook_config.json` (для smart_webhook.php)

## Текущий статус
- ✅ Webhook активен на temporary URL
- ❌ Постоянный домен не доступен
- ✅ PHP скрипты созданы
- ❌ Необходима настройка DNS/хостинга