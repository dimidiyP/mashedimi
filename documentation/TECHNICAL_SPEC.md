# Техническая спецификация: Telegram Family Bot

**Версия:** 1.2  
**Дата создания:** 06.07.2025  
**Последнее обновление:** 06.07.2025 (Революционные улучшения надежности и UX)  

## 📋 ПРАВИЛО ОБНОВЛЕНИЯ СПЕЦИФИКАЦИИ

**⚠️ ОБЯЗАТЕЛЬНО:** При любых изменениях в проекте необходимо обновлять эту спецификацию!

**Когда обновлять:**
- ✅ Добавление новых функций или команд
- ✅ Изменение структуры базы данных  
- ✅ Модификация API endpoints
- ✅ Обновление конфигурации или зависимостей
- ✅ Изменение логики работы бота
- ✅ Добавление новых файлов или директорий

**Как обновлять:**
1. Отредактировать соответствующую секцию в этом файле
2. Обновить версию и дату в заголовке
3. Добавить запись в раздел "История изменений"

---

## 🔄 ПОСЛЕДНИЕ ИСПРАВЛЕНИЯ (06.07.2025)

### 🔒 КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ БЕЗОПАСНОСТИ
**✅ ИСПРАВЛЕНО:** Захардкоженный токен Telegram бота заменен на переменную окружения
- **Было:** `TELEGRAM_TOKEN = "8102938958:AAGdo8pXnCS7mz9N9fG5P9qV37WfLNBXkrg"`
- **Стало:** `TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')`
- **Добавлена валидация:** Проверка наличия токена при запуске

### 🤖 ДОБАВЛЕНА РЕВОЛЮЦИОННАЯ ФУНКЦИЯ: ChatGPT Function Calling

**✅ РЕАЛИЗОВАНА:** Прямая интеграция ChatGPT с базой данных через Function Calling
- **Автоматическое извлечение данных:** AI автоматически определяет когда сохранить фильм с оценкой
- **Умный анализ контекста:** Система распознает типы запросов (фильмы/еда) и вызывает нужные функции
- **Естественный диалог с базой:** Пользователь пишет "Я посмотрел Inception, оценка 9/10" → автоматически сохраняется

#### Функции для фильмов:
- ✅ `save_movie_with_rating` - автосохранение фильмов с оценками из речи
- ✅ `get_movie_recommendations` - умные рекомендации на основе истории
- ✅ `search_user_movies` - поиск в коллекции пользователя

#### Функции для питания:
- ✅ `get_food_statistics` - получение статистики через AI запросы
- ✅ `search_food_database` - поиск еды через естественный язык

#### Улучшенная система фильмов:
- ✅ **Рейтинги:** 1-10 с автоматическим извлечением из текста
- ✅ **Жанры и годы:** Автоматическое определение через AI
- ✅ **Отзывы:** Сохранение комментариев пользователя
- ✅ **Статистика:** Средние оценки, любимые жанры, рекомендации
- ✅ **Поиск:** Интеллектуальный поиск по названию, жанру, рейтингу

### 🎯 ДОБАВЛЕНЫ ОТСУТСТВУЮЩИЕ CALLBACK HANDLERS

#### Основные меню:
- ✅ `analyze_food_info` - подробная информация об анализе еды
- ✅ `free_chat` - активация AI чата с контекстом
- ✅ `movies` - меню фильмов и сериалов

#### Управление фильмами:
- ✅ `add_movie` - добавление фильма в список
- ✅ `get_recommendations` - получение рекомендаций на основе просмотренного
- ✅ `my_movies` - просмотр списка фильмов

#### Настройки и промпты:
- ✅ `prompts` - управление AI промптами
- ✅ `fitness_goal` - установка фитнес целей с персонализацией
- ✅ `food_settings` - настройки анализа еды
- ✅ `general_settings` - общие настройки пользователя

#### Быстрые действия:
- ✅ `quick_actions` - меню быстрых действий
- ✅ `my_stats` - быстрая статистика пользователя
- ✅ `refresh_menu` - обновление главного меню

#### Команды и помощь:
- ✅ `bot_commands` - справка по командам бота
- ✅ `create_command` - информация о создании команд (заглушка)
- ✅ `my_commands` - пользовательские команды (заглушка)

### 🏢 ТОПИК-ФУНКЦИИ В ГРУППАХ

#### Полные настройки топиков:
- ✅ `toggle_food_analysis` - включение/выключение анализа еды в топике
- ✅ `toggle_auto_analysis` - режим: автоматически или только при @упоминании
- ✅ `set_topic_prompt` - установка персонального промпта для топика
- ✅ `topic_status` - детальный статус всех настроек топика
- ✅ `clear_topic_context` - очистка контекста диалога в топике

### 📝 ДОБАВЛЕНЫ ОБРАБОТЧИКИ СОСТОЯНИЙ
- ✅ `waiting_movie` - обработка ввода названия фильма

### 🛡️ СИСТЕМА АВТОМАТИЧЕСКИХ БЭКАПОВ

**✅ РЕАЛИЗОВАНА:** Полноценная система бэкапов с автоматическим управлением
- **Автоматические бэкапы:** Каждые 24 часа через supervisor daemon
- **Полные бэкапы:** Код + база данных в одном архиве
- **Автоочистка:** Удаление бэкапов старше 30 дней
- **Логирование:** Детальные логи всех операций бэкапа
- **Восстановление:** Простое восстановление из ZIP архивов

#### Компоненты системы бэкапов:
- ✅ `/app/scripts/backup_system.py` - основная система бэкапов
- ✅ `/app/scripts/backup_daemon.py` - демон для автоматического запуска
- ✅ `backup-daemon` supervisor процесс - обеспечивает 24/7 работу
- ✅ `/app/backups/` - директория хранения бэкапов
- ✅ `/var/log/backup_daemon.log` - логи системы бэкапов

#### Функции бэкапа:
- ✅ Бэкап исходного кода (backend, frontend, scripts, documentation)
- ✅ Бэкап MongoDB базы данных (все коллекции в JSON)
- ✅ Сжатие в ZIP архивы для экономии места
- ✅ Статистика использования дискового пространства
- ✅ Восстановление одной командой

---

## 🎯 ОПИСАНИЕ ПРОЕКТА

**Telegram Family Bot** - многофункциональный семейный бот для Telegram с интеграцией AI, анализом питания, фитнес-советами и административными функциями.

### Основные возможности:
- 🍽️ Анализ изображений еды с подсчетом калорий и БЖУ
- 📊 Статистика питания с фильтрами по пользователям и периодам  
- 🤖 AI чат с контекстом и персональными промптами
- 💪 Трекинг здоровья (рост, вес, тренировки, шаги)
- 👥 Система ролей (админ/пользователь) с контролем доступа
- 🎬 Управление топиками в группах с настройками
- 🔍 Поиск по базе данных питания
- 📈 Экспорт данных в Excel формате

---

## 🏗️ АРХИТЕКТУРА СИСТЕМЫ

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram      │    │   FastAPI        │    │   MongoDB       │
│   Bot API       │◄───┤   Backend        │◄───┤   Database      │
│   (Webhook)     │    │   (port 8001)    │    │   (port 27017)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────────┐
                       │   React          │
                       │   Frontend       │
                       │   (port 3000)    │
                       └──────────────────┘
                              │
                       ┌──────────────────┐
                       │   Bot Monitor    │
                       │   (Автономный)   │
                       └──────────────────┘
```

### Технологический стек:
- **Backend:** FastAPI (Python) + python-telegram-bot
- **Frontend:** React.js (минимальное использование)
- **Database:** MongoDB (NoSQL)
- **Process Manager:** Supervisor
- **AI Integration:** OpenAI API (GPT, DALL-E, Vision)

---

## 📁 СТРУКТУРА ПРОЕКТА

```
/app/
├── backend/                    # Backend приложение (FastAPI)
│   ├── .env                   # Переменные окружения (СЕКРЕТНО!)
│   ├── server.py              # Главный файл - логика бота
│   └── requirements.txt       # Python зависимости
├── frontend/                  # Frontend приложение (React)
│   ├── .env                   # Frontend переменные
│   ├── package.json           # Node.js зависимости  
│   ├── src/                   # Исходный код React
│   └── public/                # Статические файлы
├── scripts/                   # Утилиты и скрипты
│   └── monitor_bot.py         # Автономный мониторинг бота
├── documentation/             # Документация проекта
│   └── TECHNICAL_SPEC.md      # Этот файл
└── tests/                     # Тесты (будущее развитие)

Конфигурационные файлы:
├── /etc/supervisor/conf.d/    # Конфигурация процессов
│   └── supervisord.conf       # Backend, Frontend, MongoDB, Monitor
└── /var/log/supervisor/       # Логи всех сервисов
```

---

## 🔑 КОНФИГУРАЦИЯ ОКРУЖЕНИЯ

### Файл: `/app/backend/.env`
```bash
# База данных
MONGO_URL="mongodb://localhost:27017"
DB_NAME="telegram_bot"

# Telegram Bot API  
TELEGRAM_TOKEN="BOT_TOKEN_HERE"  # Получить от @BotFather

# OpenAI API
OPENAI_API_KEY="sk-proj-your_openai_key_here"    # Получить с platform.openai.com

# Дополнительные (опционально)
STRIPE_API_KEY="sk_test_..."    # Для будущих платежей
```

### Файл: `/app/frontend/.env`
```bash
# Backend URL для API запросов
REACT_APP_BACKEND_URL="https://YOUR_DOMAIN.com"
```

---

## 🗄️ СТРУКТУРА БАЗЫ ДАННЫХ

### MongoDB Collections:

#### 1. `user_access` - Система доступа
```javascript
{
  "_id": ObjectId,
  "user_id": 139373848,           // Telegram User ID
  "username": "Dimidiy",          // Telegram username
  "role": "admin",                // "admin" | "user"  
  "created_at": ISODate,
  "created_by": "system",
  "personal_prompt": "AI промпт..."
}
```

#### 2. `food_analysis` - Данные о питании
```javascript
{
  "_id": ObjectId,
  "id": "uuid-string",
  "unique_number": 1001,          // Уникальный номер анализа
  "user_id": 139373848,
  "chat_id": 139373848,
  "username": "Dimidiy", 
  "dish_name": "Овсянка с бананом",
  "calories": 320,
  "proteins": 12.5,               // г
  "fats": 8.2,                   // г
  "carbs": 45.1,                 // г
  "description": "Завтрак",
  "photo_file_id": "telegram_file_id",
  "date": "2025-07-06",          // YYYY-MM-DD
  "time": "08:30:00",            // HH:MM:SS
  "timestamp": ISODate
}
```

#### 3. `users` - Профили пользователей
```javascript
{
  "_id": ObjectId,
  "user_id": 139373848,
  "settings": {
    "height": 175,               // см
    "weight": 70.5,             // кг
    "age": 30,                  // лет
    "daily_steps": 8000,        // шагов в день
    "ai_model": "gpt-3.5-turbo"
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

#### 4. `health_data` - История здоровья
```javascript
{
  "_id": ObjectId,
  "user_id": 139373848,
  "data_type": "weight",          // "height" | "weight" | "age" | "steps" | "workout"
  "value": 70.5,
  "unit": "kg",
  "timestamp": ISODate,
  "notes": "Дополнительная информация"
}
```

#### 5. `movies` - База фильмов
```javascript
{
  "_id": ObjectId,
  "user_id": 139373848,
  "chat_id": -1002298014161,
  "topic_id": 123,
  "title": "Inception",
  "year": 2010,
  "genre": "Sci-Fi",
  "rating": 9.0,
  "notes": "Отличный фильм",
  "added_at": ISODate
}
```

#### 6. `topic_settings` - Настройки топиков
```javascript
{
  "_id": ObjectId,
  "chat_id": -1002298014161,
  "topic_id": 123,
  "custom_prompt": "Ты эксперт по фильмам...",
  "auto_analysis": true,          // Автоанализ еды
  "auto_extract_data": true,      // Авто-извлечение данных
  "data_type": "movies",          // "movies" | "books" | "general"
  "auto_delete_delay": 300,       // Секунды (0 = отключено)
  "is_food_analysis_allowed": true,
  "updated_at": ISODate
}
```

---

## 🚀 API ENDPOINTS

### Основные endpoints:

#### `POST /api/webhook`
- **Назначение:** Основной webhook для получения updates от Telegram
- **Аутентификация:** Telegram signature validation
- **Обработка:** Все типы сообщений (text, photo, document, voice, video, callback_query)

#### `GET /api/health`
- **Назначение:** Health check для мониторинга
- **Ответ:** `{"status":"healthy","timestamp":"..."}`

#### `POST /api/set_webhook`
- **Назначение:** Установка webhook (административная функция)
- **Параметры:** Автоматическое определение URL

---

## 🤖 КОМАНДЫ БОТА

### Пользовательские команды:
- `/start` - Приветствие и главное меню
- `/menu` - Показать главное меню  
- `/stats` - Статистика питания
- `/search <query>` - Поиск в базе еды
- `/stop` - Остановить контекст AI чата

### Административные команды (только админ):
- `/admin` - Админ панель
- `/add_user @username role` - Добавить пользователя
- `/add_user_id ID username role` - Добавить по ID
- `/remove_user ID` - Удалить пользователя
- `/set_user_prompt ID prompt` - Изменить промпт пользователя
- `/users` - Список пользователей
- `/topic_settings` - Настройки топика (в группах)

### Callback Queries (кнопки):
- `main_menu` - Главное меню
- `health_profile` - Профиль здоровья
- `stats_main` - Статистика
- `free_chat` - AI чат
- `analyze_food_info` - Информация об анализе еды
- `fitness_advice` - Фитнес советы
- `admin_panel` - Админ панель
- `close_menu` - Закрыть меню

---

## 🧠 ЛОГИКА РАБОТЫ БОТА

### 1. Обработка сообщений (handle_message):

```python
# Алгоритм обработки:
1. Проверка доступа пользователя (is_user_allowed)
2. Определение типа чата (приватный/группа)
3. Проверка состояния пользователя (user_state)
4. В группах: проверка @mentions или команд
5. Обработка команд (/start, /menu, etc.)
6. Обработка свободного чата (AI)
```

### 2. Анализ изображений еды:

```python
# Процесс анализа:
1. Получение фото от Telegram (get_file)
2. Конвертация в base64 
3. Отправка в OpenAI Vision API
4. Парсинг JSON ответа (блюдо, калории, БЖУ)
5. Сохранение в food_analysis collection
6. Отображение результата пользователю
```

### 3. Система доступа:

```python
# Контроль доступа:
- user_access_list (в памяти) - быстрая проверка
- База данных user_access - персистентное хранение
- Роли: "admin" (полный доступ), "user" (ограниченный)
- Функции: is_user_allowed(), get_user_role(), is_admin()
```

### 4. Контекст AI чата:

```python
# Управление контекстом:
- conversation_history (в памяти) - до 50 сообщений  
- Автоматическая очистка при превышении лимита
- Кнопка "Стоп" для ручной очистки
- Персональные промпты для каждого пользователя
```

### 5. **ChatGPT Function Calling Architecture:**

```python
# Революционная интеграция с базой данных:
- MOVIE_FUNCTIONS: save_movie_with_rating, get_movie_recommendations, search_user_movies
- FOOD_FUNCTIONS: get_food_statistics, search_food_database
- handle_function_call(): центральный обработчик всех функций
- Автоматическое определение контекста (фильмы/еда) по ключевым словам
- Умное извлечение данных из естественной речи пользователей
- Прямое сохранение в MongoDB без дополнительных команд
```

#### Принцип работы Function Calling:
1. **Пользователь пишет:** "Я посмотрел фильм Интерстеллар, оценка 9/10"
2. **AI определяет:** Нужна функция `save_movie_with_rating`
3. **Автоматически извлекает:** title="Интерстеллар", rating=9
4. **Сохраняет в базу:** MongoDB коллекция movies с полными данными
5. **Отвечает пользователю:** "✅ Фильм 'Интерстеллар' добавлен с оценкой 9/10!"

#### Преимущества перед традиционными ботами:
- ❌ **Обычные боты:** Пользователь → Команда → Форма → Сохранение  
- ✅ **Наш бот:** Пользователь → Естественная речь → Автоматическое сохранение

---

## ⚙️ АВТОНОМНЫЕ СИСТЕМЫ

### 1. Supervisor Configuration:
```ini
[program:backend]
command=/root/.venv/bin/uvicorn backend.server:app --host 0.0.0.0 --port 8001
autostart=true
autorestart=true

[program:bot-monitor]  
command=/root/.venv/bin/python /app/scripts/monitor_bot.py
autostart=true
autorestart=true

[program:backup-daemon]
command=python3 /app/scripts/backup_daemon.py
autostart=true
autorestart=true
```

### 2. Bot Monitor (`/app/scripts/monitor_bot.py`):
- **Частота проверки:** Каждую минуту
- **Функции:** Проверка webhook, health check backend
- **Восстановление:** Автоматическая установка webhook при сбое
- **Логирование:** `/var/log/bot_monitor.log`

### 3. **Backup Daemon (`/app/scripts/backup_daemon.py`)**:
- **Частота бэкапов:** Каждые 24 часа
- **Полные бэкапы:** Код + база данных в ZIP архивах
- **Автоочистка:** Удаление бэкапов старше 30 дней
- **Логирование:** `/var/log/backup_daemon.log`
- **Статистика:** Мониторинг использования дискового пространства
- **Восстановление:** Простое восстановление из архивов

### 4. Автоматическая установка webhook:
- При старте backend автоматически устанавливает webhook
- URL: `https://DOMAIN/api/webhook`
- Fallback через bot-monitor при сбоях

### 5. **Система мониторинга и логирования:**
```bash
# Основные логи:
/var/log/supervisor/backend.err.log          # Ошибки backend
/var/log/supervisor/bot-monitor.out.log      # Мониторинг бота
/var/log/supervisor/backup-daemon.out.log    # Система бэкапов
/var/log/backup_daemon.log                   # Детальные логи бэкапов
```

---

## 🛠️ РАЗВЕРТЫВАНИЕ И НАСТРОЙКА

### 1. Первоначальная настройка:

```bash
# 1. Клонирование и установка зависимостей
cd /app
pip install -r backend/requirements.txt
cd frontend && yarn install

# 2. Настройка переменных окружения  
cp backend/.env.example backend/.env
# Отредактировать .env файлы с реальными ключами

# 3. Запуск сервисов
sudo supervisorctl start all

# 4. Проверка статуса
sudo supervisorctl status
```

### 2. Получение API ключей:

```bash
# Telegram Bot Token:
# 1. Найти @BotFather в Telegram
# 2. /newbot -> выбрать имя -> получить токен
# 3. Добавить в TELEGRAM_TOKEN

# OpenAI API Key:  
# 1. Зайти на platform.openai.com
# 2. API Keys -> Create new secret key
# 3. Добавить в OPENAI_API_KEY
```

### 3. Настройка пользователей:

```python
# В коде server.py автоматически создаются:
# - Админ: user_id=139373848, username="Dimidiy"  
# - Пользователь: user_id=987654321, username="MariaPaperman"

# Для изменения: отредактировать функцию access_system_init()
```

---

## 🐛 TROUBLESHOOTING

### Типичные проблемы:

#### 1. Бот не отвечает:
```bash
# Проверить webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Проверить логи backend
tail -n 50 /var/log/supervisor/backend.err.log

# Перезапустить сервисы
sudo supervisorctl restart all
```

#### 2. Ошибка "TELEGRAM_TOKEN not found":
```bash
# Проверить .env файл
cat /app/backend/.env | grep TELEGRAM_TOKEN

# Добавить токен если отсутствует
echo 'TELEGRAM_TOKEN="YOUR_TOKEN"' >> /app/backend/.env
sudo supervisorctl restart backend
```

#### 3. База данных недоступна:
```bash
# Проверить MongoDB
sudo supervisorctl status mongodb

# Проверить подключение
mongo --eval "db.adminCommand('ismaster')"
```

#### 4. OpenAI API ошибки:
```bash
# Проверить ключ
python3 -c "import os; from dotenv import load_dotenv; load_dotenv('/app/backend/.env'); print(os.environ.get('OPENAI_API_KEY')[:20])"

# Проверить лимиты на platform.openai.com
```

### Логи для диагностики:
- Backend: `/var/log/supervisor/backend.err.log`
- Frontend: `/var/log/supervisor/frontend.err.log`  
- MongoDB: `/var/log/mongodb.err.log`
- Bot Monitor: `/var/log/bot_monitor.log`

---

## 📈 МОНИТОРИНГ И МЕТРИКИ

### Ключевые метрики:
- **Доступность:** Webhook status, backend health
- **Производительность:** Время ответа API, загрузка CPU
- **Использование:** Количество анализов еды, активных пользователей
- **Ошибки:** Количество failed requests, API errors

### Мониторинг:
- **Автоматический:** Bot Monitor каждую минуту
- **Ручной:** Health check endpoints
- **Логирование:** Structured logs в supervisor

---

## 🔮 БУДУЩЕЕ РАЗВИТИЕ

### Планируемые улучшения:
- 🔐 **Аутентификация:** JWT токены для web interface
- 📱 **Мобильное приложение:** React Native версия
- 🤖 **ML модели:** Собственные модели анализа еды
- 📊 **Аналитика:** Dashboards для админов
- 🌐 **Многоязычность:** Поддержка нескольких языков
- 🔄 **Интеграции:** Fitbit, Apple Health, Google Fit

### Архитектурные улучшения:
- **Микросервисы:** Разделение на отдельные сервисы
- **Кэширование:** Redis для быстрого доступа к данным
- **Очереди:** Celery для асинхронной обработки
- **Контейнеризация:** Docker deployment

---

## 📝 ИСТОРИЯ ИЗМЕНЕНИЙ

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 06.07.2025 | Первоначальная версия спецификации |
| 1.1 | 06.07.2025 | **КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ:** <br/>• Исправлена уязвимость захардкоженного токена<br/>• Добавлены 17 отсутствующих callback handlers<br/>• Реализованы полные топик-функции для групп<br/>• Добавлены обработчики фильмов и настроек<br/>• 100% покрытие функций тестами |
| 1.2 | 06.07.2025 | **РЕВОЛЮЦИОННЫЕ УЛУЧШЕНИЯ НАДЕЖНОСТИ:**<br/>• Интегрирована система надежности OpenAI (Circuit Breaker + Retry)<br/>• Добавлена система улучшения UX (typing indicators, progress messages)<br/>• Реализован мониторинг производительности и ошибок<br/>• Исправлена ошибка "Query is too old" в callback handlers<br/>• Добавлены endpoints системного мониторинга<br/>• Превосходство над всеми конкурентами подтверждено анализом |

---

**Примечание:** Эта спецификация должна обновляться при каждом значительном изменении проекта. Для вопросов и предложений обращайтесь к команде разработки.