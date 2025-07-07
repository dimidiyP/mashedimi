# 🌐 ПЛАН ВНЕДРЕНИЯ ДОМЕНА demondimi.ru

**Дата:** 06.07.2025  
**Статус:** В ПРОЦЕССЕ  
**Проблема:** SSL сертификат не соответствует домену  

---

## 🚨 ОБНАРУЖЕННАЯ ПРОБЛЕМА

### SSL Сертификат:
```
Домен: demondimi.ru
Сертификат выдан для: baseshinomontaz.ru
Issuer: Let's Encrypt R10
IP: 83.222.18.104

Ошибка Telegram: "SSL error certificate verify failed"
```

---

## 🔧 РЕШЕНИЯ

### Вариант 1: Обновить SSL сертификат (РЕКОМЕНДУЕТСЯ)
```bash
# На хостинге demondimi.ru:
1. Зайти в панель управления хостингом
2. Перевыпустить SSL сертификат для demondimi.ru
3. Подождать обновления (до 24 часов)
4. Проверить сертификат: openssl s_client -connect demondimi.ru:443
```

### Вариант 2: Использовать HTTP proxy (ВРЕМЕННО)
```bash
# Если HTTPS недоступен, можно использовать HTTP
# НО: Telegram требует HTTPS для webhook!
```

### Вариант 3: Cloudflare Proxy (АЛЬТЕРНАТИВА)
```bash
# Настроить Cloudflare перед доменом
1. Добавить домен в Cloudflare
2. Обновить nameservers
3. Включить Cloudflare SSL
```

---

## 📋 ПОДГОТОВЛЕННЫЕ ФАЙЛЫ

### Webhook Proxy для demondimi.ru:
```
Файл: /app/deployment/webhook_proxy/demondimi_webhook.php
Функция: Перенаправляет Telegram webhook на VPS
Статус: ГОТОВ К ИСПОЛЬЗОВАНИЮ (после исправления SSL)
```

### Обновленный код:
```
✅ server.py: set_webhook() обновлен для demondimi.ru
✅ system_webhook callback: обновлен текст
✅ PHP скрипт: создан для нового домена
```

---

## 🚀 ШАГИ ДЛЯ АКТИВАЦИИ

### Когда SSL сертификат будет исправлен:

1. **Проверить SSL:**
```bash
curl -I https://demondimi.ru/
openssl s_client -connect demondimi.ru:443 -servername demondimi.ru
```

2. **Загрузить PHP скрипт на хостинг:**
```bash
# Скопировать файл /app/deployment/webhook_proxy/demondimi_webhook.php
# на хостинг demondimi.ru как webhook.php
```

3. **Установить webhook:**
```bash
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -d '{"url": "https://demondimi.ru/webhook.php"}'
```

4. **Проверить статус:**
```bash
curl "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
```

---

## 📊 ТЕКУЩИЙ СТАТУС

### Активный webhook:
```
URL: https://8867069a-d008-4da6-8b30-bdb8e855fcb4.preview.emergentagent.com/api/webhook
Статус: ✅ РАБОТАЕТ (временное решение)
```

### Готовность к переходу:
```
demondimi.ru domain: ✅ Зарегистрирован
DNS resolution: ✅ Работает  
HTTPS: ❌ SSL сертификат некорректный
PHP скрипт: ✅ Готов
Код обновлен: ✅ Готов
```

---

## 🎯 ДЕЙСТВИЯ

### Для пользователя:
1. **Обратиться к хостинг провайдеру** для исправления SSL сертификата
2. **Запросить перевыпуск** сертификата для demondimi.ru
3. **Загрузить PHP скрипт** на хостинг после исправления SSL

### После исправления SSL:
```bash
# Автоматически активируем новый домен
1. Установим webhook на demondimi.ru
2. Остановим Cloudflare tunnel
3. Обновим всю документацию
4. Протестируем работу бота
```

---

## 📝 ВРЕМЕННЫЕ ФАЙЛЫ

### Готовые к использованию:
```
/app/deployment/webhook_proxy/demondimi_webhook.php
- Полностью настроен для demondimi.ru
- Логирование для отладки
- Корректное перенаправление на VPS
```

### Обновленный код:
```
✅ /app/backend/server.py (строки 6090-6096, 5880)
✅ Webhook endpoint изменен на demondimi.ru
✅ System webhook info обновлена
```

---

## 🔮 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После исправления SSL сертификата:
- ✅ **Постоянный webhook** на собственном домене
- ✅ **Независимость** от временных сервисов
- ✅ **Профессиональный вид** (demondimi.ru)
- ✅ **Полный контроль** над инфраструктурой

**ETA: 24 часа** (время обновления SSL сертификата)

---

*План готов к исполнению после исправления SSL сертификата*  
*Все необходимые файлы подготовлены*