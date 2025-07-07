# Telegram Bot with Modular Architecture

## 🚀 Quick Start

### 1. Настройка окружения
```bash
# Скопируйте файл примера
cp backend/.env.example backend/.env

# Отредактируйте backend/.env и укажите:
# - OPENAI_API_KEY (получить на platform.openai.com)
# - TELEGRAM_TOKEN (получить у @BotFather)
```

### 2. Установка зависимостей
```bash
cd backend
pip install -r requirements.txt
```

### 3. Запуск локально
```bash
cd backend
python server.py
```

## 🏗️ Архитектура

### Модульная структура:
- **config/** - настройки, база данных, константы
- **core/** - основной framework бота
- **features/** - основные функции:
  - **food_health** - анализ еды, профили здоровья
  - **movie_expert** - фильмы и рекомендации  
  - **message_management** - автоудаление, теги

## 🌐 Deployment

### Деплой на demondimi.ru:
```bash
# Установите переменные окружения
export OPENAI_API_KEY="your-key-here"
export TELEGRAM_TOKEN="your-token-here"

# Запустите деплой
./deployment/scripts/deploy-demondimi.sh
```

## 📋 Features

### 🍽️ Food/Health AI
- Анализ изображений еды через OpenAI Vision API
- Профили здоровья пользователей
- Персональные AI рекомендации
- Отслеживание тренировок и шагов

### 🎬 Movie Expert  
- Сохранение просмотренных фильмов
- AI рекомендации на основе истории
- Статистика просмотров
- Поиск в коллекции

### ⚙️ Message Management
- Автоматическое удаление сообщений
- Система тегов для сообщений
- Настройки AI для топиков
- Автомодерация

## 🔧 API Endpoints

- `GET /api/test` - статус системы
- `GET /api/features` - информация о возможностях
- `GET /api/health` - health check
- `POST /api/webhook` - Telegram webhook

## 📚 Документация

- [Environment Setup](ENVIRONMENT_SETUP.md) - настройка окружения
- [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) - техническая документация
- [deployment/](deployment/) - скрипты и конфигурации для деплоя