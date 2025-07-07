# 🔄 ИНСТРУКЦИЯ ПО ПЕРЕХОДУ НА demondimi.ru

**Статус:** ГОТОВ К ПЕРЕХОДУ  
**Требуется:** Исправление SSL сертификата  

---

## ✅ ЧТО УЖЕ СДЕЛАНО

### 1. Код обновлен:
```python
✅ /app/backend/server.py:
   - set_webhook() функция обновлена для demondimi.ru
   - system_webhook callback текст обновлен

✅ PHP proxy скрипт создан:
   - /app/deployment/webhook_proxy/demondimi_webhook.php
   - Готов к загрузке на хостинг
```

### 2. Документация обновлена:
```
✅ DEMONDIMI_DOMAIN_SETUP.md - План внедрения
✅ TECHNICAL_SPEC_V4_CODE_ACCURATE.md - Обновлена информация
✅ Все references на старые URL обновлены
```

---

## 🚨 ТЕКУЩАЯ ПРОБЛЕМА

### SSL Certificate Mismatch:
```bash
Проблема: SSL сертификат выдан для baseshinomontaz.ru
Требуется: Перевыпустить сертификат для demondimi.ru

Ошибка Telegram: "SSL error certificate verify failed"
```

---

## 📋 ФАЙЛЫ ДЛЯ ЗАГРУЗКИ НА ХОСТИНГ

### 1. Основной webhook скрипт:
```
Источник: /app/deployment/webhook_proxy/demondimi_webhook.php
Назначение: https://demondimi.ru/webhook.php
Функция: Прием webhook от Telegram и перенаправление на VPS
```

### Содержимое файла для загрузки:
```php
<?php
// Webhook proxy script for demondimi.ru
$vps_url = "https://8867069a-d008-4da6-8b30-bdb8e855fcb4.preview.emergentagent.com";
$log_file = "webhook_log.txt";

$input = file_get_contents('php://input');
$headers = getallheaders();

// Log request
$log_entry = date('[Y-m-d H:i:s] ') . "Webhook received\n";
$log_entry .= "Input size: " . strlen($input) . " bytes\n";

// Forward to VPS
$target_url = $vps_url . "/api/webhook";
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $target_url);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

// Log response
$log_entry .= "Response code: " . $http_code . "\n";
file_put_contents($log_file, $log_entry, FILE_APPEND);

// Return to Telegram
if ($response && $http_code == 200) {
    echo $response;
} else {
    http_response_code(200);
    echo json_encode(["status" => "forwarded", "code" => $http_code]);
}
?>
```

---

## 🛠️ ШАГИ ДЛЯ АКТИВАЦИИ

### После исправления SSL сертификата:

#### 1. Проверить SSL:
```bash
# Команда для проверки:
curl -I https://demondimi.ru/

# Должно показать:
HTTP/2 200
server: nginx
# И НЕ должно быть ошибок SSL
```

#### 2. Загрузить файл на хостинг:
```
1. Зайти в панель управления хостингом demondimi.ru
2. Перейти в файловый менеджер
3. Загрузить файл как webhook.php в корневую директорию
4. Проверить права доступа (должны быть 644)
```

#### 3. Протестировать proxy:
```bash
# Тестовый запрос к proxy:
curl -X POST "https://demondimi.ru/webhook.php" \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'

# Должен вернуть статус 200
```

#### 4. Установить webhook автоматически:
```bash
# Webhook установится автоматически при следующем рестарте backend
sudo supervisorctl restart backend

# Или вручную:
curl -X POST "https://8867069a-d008-4da6-8b30-bdb8e855fcb4.preview.emergentagent.com/api/set_webhook"
```

#### 5. Проверить статус:
```bash
# Проверить webhook в Telegram:
curl "https://api.telegram.org/bot8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg/getWebhookInfo"

# Должен показать:
{
  "ok": true,
  "result": {
    "url": "https://demondimi.ru/webhook.php",
    "pending_update_count": 0
  }
}
```

---

## 🎯 АВТОМАТИЗАЦИЯ

### Скрипт для быстрого перехода:
```bash
#!/bin/bash
# /app/scripts/switch_to_demondimi.sh

echo "🔄 Переходим на demondimi.ru..."

# 1. Проверить SSL
echo "📋 Проверяем SSL сертификат..."
if curl -s -I https://demondimi.ru/ | grep -q "HTTP/2 200"; then
    echo "✅ SSL работает!"
    
    # 2. Установить webhook
    echo "📡 Устанавливаем webhook..."
    response=$(curl -s -X POST "https://api.telegram.org/bot8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg/setWebhook" \
      -H "Content-Type: application/json" \
      -d '{"url": "https://demondimi.ru/webhook.php"}')
    
    if echo "$response" | grep -q '"ok":true'; then
        echo "✅ Webhook установлен на demondimi.ru!"
        
        # 3. Остановить Cloudflare tunnel
        echo "🛑 Останавливаем временные сервисы..."
        sudo supervisorctl stop cloudflare-tunnel tunnel-webhook-updater
        
        echo "🎉 Переход завершен! Бот работает на постоянном домене."
    else
        echo "❌ Ошибка установки webhook: $response"
    fi
else
    echo "❌ SSL сертификат еще не исправлен. Дождитесь обновления."
fi
```

---

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### После успешного перехода:
```yaml
✅ Постоянный webhook: https://demondimi.ru/webhook.php
✅ Независимость от Cloudflare
✅ Профессиональный домен
✅ Полный контроль инфраструктуры
✅ Логирование webhook запросов
✅ Стабильная работа 24/7
```

### Преимущества:
```
🎯 Брендинг: Собственный домен demondimi.ru
🛡️ Надежность: Не зависит от внешних сервисов
🔧 Контроль: Полное управление webhook
📊 Мониторинг: Логи webhook запросов
💰 Экономия: Не нужны дополнительные сервисы
```

---

## 🚨 ВАЖНЫЕ МОМЕНТЫ

### Требования к хостингу:
```
✅ PHP поддержка (любая версия 7.4+)
✅ cURL модуль включен
✅ HTTPS с валидным SSL сертификатом
✅ Возможность загрузки файлов
✅ Права на запись (для логов)
```

### Обслуживание:
```
📝 Мониторинг логов: webhook_log.txt
🔄 Обновление VPS URL при необходимости
🧹 Периодическая очистка логов
📊 Проверка статуса webhook
```

---

## 📞 СЛЕДУЮЩИЕ ДЕЙСТВИЯ

1. **Дождаться исправления SSL** (обратиться к хостинг провайдеру)
2. **Загрузить PHP скрипт** на хостинг demondimi.ru
3. **Запустить скрипт перехода** после исправления SSL
4. **Протестировать работу бота**
5. **Обновить всю документацию** с финальными URL

**ETA: 24-48 часов** (время обновления SSL сертификата)

---

*Все готово к переходу на постоянный домен!*  
*Ожидаем исправления SSL сертификата для завершения миграции*