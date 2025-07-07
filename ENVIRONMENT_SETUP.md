# Environment Setup Instructions

## Локальная разработка

1. Скопируйте файл примера:
   ```bash
   cp backend/.env.example backend/.env
   ```

2. Заполните необходимые переменные в `backend/.env`:

   - `OPENAI_API_KEY` - получите на https://platform.openai.com/
   - `TELEGRAM_TOKEN` - получите у @BotFather в Telegram
   - `MONGO_URL` - URL MongoDB (по умолчанию локальный)
   - `DB_NAME` - название базы данных
   - `STRIPE_API_KEY` - ключ Stripe (если используете платежи)

## Продакшен (VPS)

На продакшен сервере переменные окружения настраиваются через systemd сервис или в отдельном файле окружения.

### Пример для systemd:

```bash
sudo systemctl edit telegram-bot
```

Добавьте:
```
[Service]
Environment=OPENAI_API_KEY=your_actual_key_here
Environment=TELEGRAM_TOKEN=your_actual_token_here
Environment=MONGO_URL=mongodb://localhost:27017
Environment=DB_NAME=telegram_bot_db
```

## Безопасность

- ❌ Никогда не коммитьте файлы .env в git
- ✅ Используйте .env.example для документирования необходимых переменных
- ✅ На продакшене используйте переменные окружения или защищенные конфиги
- ✅ Регулярно обновляйте API ключи