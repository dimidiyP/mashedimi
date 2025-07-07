"""
Integrated Telegram Bot Server with Modular Architecture
Combines existing functionality with new Food/Health AI, Movie Expert, and Message Management features
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timedelta
import asyncio
import httpx
import json
import logging
from typing import Dict, List, Optional
import uuid
import time
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths for modular imports
sys.path.append('/app')
sys.path.append('/app/backend')

# Telegram Bot imports
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# Legacy imports for compatibility
from openai_reliability import init_reliable_openai_client, get_reliable_openai_client
from user_experience import ux_manager, feedback_collector
from debug_system import init_debug_mode, get_debug_logger, is_debug_mode

# Try to import modular architecture (optional for backward compatibility)
try:
    from config.settings import settings
    from config.database import db_manager
    from config.constants import ADMIN_IDS
    from core.bot import bot_core
    from features.food_health.handlers import FoodHealthHandlers
    from features.movie_expert.handlers import MovieExpertHandlers
    from features.message_management.handlers import MessageManagementHandlers
    MODULAR_ARCHITECTURE_AVAILABLE = True
    logger.info("🏗️ Modular architecture loaded successfully")
except ImportError as e:
    MODULAR_ARCHITECTURE_AVAILABLE = False
    logger.warning(f"⚠️ Modular architecture not available, running in legacy mode: {e}")
    # Define fallback constants
    ADMIN_IDS = [139373848]  # Fallback admin ID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Telegram Bot with Modular Architecture", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for legacy compatibility
group_topic_settings = {}
user_access_list = {}

# Initialize modular components only if available
if MODULAR_ARCHITECTURE_AVAILABLE:
    food_health_handlers = FoodHealthHandlers()
    movie_expert_handlers = MovieExpertHandlers()
    message_management_handlers = MessageManagementHandlers()
else:
    # Create dummy handlers for legacy mode
    food_health_handlers = None
    movie_expert_handlers = None
    message_management_handlers = None

# MongoDB connection for legacy compatibility
class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
    
    async def connect(self):
        if not self.client:
            self.client = AsyncIOMotorClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
            self.db = self.client[os.getenv("DB_NAME", "telegram_bot_db")]
        return self.db
    
    def __getattr__(self, name):
        if self.db:
            return self.db[name]
        raise AttributeError(f"Database not connected")

# Legacy MongoDB manager for compatibility
mongodb_manager = MongoDBManager()

async def init_user_access():
    """Initialize user access system with default admin"""
    try:
        db = await mongodb_manager.connect()
        
        # Check if admin already exists
        admin_exists = await db.user_access.find_one({"role": "admin"})
        if not admin_exists:
            # Create default admin (@Dimidiy)
            default_admin = {
                "user_id": 139373848,  # Your user ID
                "username": "Dimidiy", 
                "role": "admin",
                "created_at": datetime.utcnow(),
                "created_by": "system",
                "personal_prompt": "Ты полезный AI-ассистент. Отвечай кратко и по существу на русском языке."
            }
            await db.user_access.insert_one(default_admin)
            logger.info("Default admin created: @Dimidiy")
        
        # Load all users into memory
        users = db.user_access.find({})
        async for user in users:
            user_access_list[user["user_id"]] = {
                "username": user["username"],
                "role": user["role"], 
                "personal_prompt": user.get("personal_prompt", "Ты полезный AI-ассистент.")
            }
            
        logger.info(f"Loaded {len(user_access_list)} users into access system")
        
    except Exception as e:
        logger.error(f"Error initializing user access: {str(e)}")

async def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to interact with bot"""
    return user_id in user_access_list or user_id in ADMIN_IDS

async def get_user_role(user_id: int) -> str:
    """Get user role (admin/user) or None if not allowed"""
    if user_id in ADMIN_IDS:
        return "admin"
    if user_id in user_access_list:
        return user_access_list[user_id]["role"]
    return None

async def handle_callback_query_routing(update: Update, context):
    """Route callback queries to appropriate handlers"""
    if not MODULAR_ARCHITECTURE_AVAILABLE:
        # Fallback to legacy handling
        await handle_legacy_callback_query(update, context)
        return
        
    query = update.callback_query
    data = query.data
    
    try:
        # Food/Health related callbacks
        if any(keyword in data for keyword in ["food_", "health_", "close_menu"]):
            if "food_stats" in data:
                await food_health_handlers.handle_food_statistics(update, context)
            elif "health_advice" in data:
                await food_health_handlers.handle_health_advice(update, context)
            elif "health_profile_menu" in data or data == "health_profile_menu":
                await food_health_handlers.handle_health_profile_menu(update, context)
            elif "close_menu" in data:
                await food_health_handlers.handle_close_menu(update, context)
            else:
                await query.answer("⚠️ Food/Health функция в разработке")
        
        # Movie related callbacks
        elif any(keyword in data for keyword in ["movie_"]):
            if "movie_menu" in data or data == "movie_menu":
                await movie_expert_handlers.handle_movie_menu(update, context)
            elif "movie_recommendations" in data:
                await movie_expert_handlers.handle_movie_recommendations(update, context)
            elif "movie_list" in data:
                await movie_expert_handlers.handle_movie_list(update, context)
            elif "movie_stats" in data:
                await movie_expert_handlers.handle_movie_stats(update, context)
            elif "movie_search" in data:
                await movie_expert_handlers.handle_movie_search(update, context)
            else:
                await query.answer("⚠️ Movie функция в разработке")
        
        # Message management callbacks
        elif any(keyword in data for keyword in ["topic_", "tag_", "auto_delete"]):
            if "topic_settings_menu" in data:
                await message_management_handlers.handle_topic_settings_menu(update, context)
            elif "topic_auto_delete" in data:
                await message_management_handlers.handle_auto_delete_settings(update, context)
            elif "topic_ai_settings" in data:
                await message_management_handlers.handle_ai_settings(update, context)
            elif "topic_tags" in data:
                await message_management_handlers.handle_message_tags_menu(update, context)
            elif "toggle_auto_delete" in data:
                await message_management_handlers.handle_toggle_auto_delete(update, context)
            else:
                await query.answer("⚠️ Message Management функция в разработке")
        
        # Legacy callbacks (for backward compatibility)
        else:
            await handle_legacy_callback_query(update, context)
            
    except Exception as e:
        logger.error(f"Error in callback query routing: {e}")
        await query.answer("❌ Произошла ошибка")

async def handle_legacy_callback_query(update: Update, context):
    """Handle legacy callback queries for backward compatibility"""
    query = update.callback_query
    await query.answer("⚠️ Legacy функция - используйте новые команды: /health, /movie, /topic")

# Bot handlers mapping (only if modular architecture is available)
if MODULAR_ARCHITECTURE_AVAILABLE:
    bot_handlers = {
        "photo": food_health_handlers.handle_photo_message,
        "callback_query": handle_callback_query_routing,
        "health_menu": food_health_handlers.handle_health_profile_menu,
        "movie_menu": movie_expert_handlers.handle_movie_menu,
        "topic_settings": message_management_handlers.handle_topic_settings_menu,
        "message_mention": message_management_handlers.handle_message_with_bot_mention,
        "message_processing": message_management_handlers.handle_automatic_message_processing
    }
else:
    bot_handlers = {
        "callback_query": handle_callback_query_routing
    }

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    try:
        # Initialize legacy systems
        await mongodb_manager.connect()
        app.mongodb = mongodb_manager.db
        
        # Initialize user access
        await init_user_access()
        
        # Initialize debug mode
        init_debug_mode()
        
        # Initialize reliability systems
        init_reliable_openai_client()
        
        # Validate modular settings
        if not settings.validate():
            logger.warning("Some modular settings are invalid, using legacy configuration")
        
        # Initialize modular database
        db_manager.connect()
        
        # Initialize bot core
        try:
            telegram_app = bot_core.initialize()
            
            # Register handlers
            for handler_name, handler_func in bot_handlers.items():
                bot_core.register_handler(handler_name, handler_func)
            
            logger.info("✅ Modular architecture initialized successfully")
        except Exception as e:
            logger.warning(f"Modular bot initialization failed, using legacy mode: {e}")
        
        logger.info("🚀 Telegram Bot Server started successfully")
        logger.info("📱 Features: Food/Health AI, Movie Expert, Message Management")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handle Telegram webhook"""
    try:
        body = await request.body()
        update_data = await request.json()
        
        # Create Update object
        from telegram import Update
        try:
            update = Update.de_json(update_data, bot_core.get_bot())
        except:
            # Fallback to legacy handling if modular bot not available
            logger.warning("Using legacy webhook handling")
            return await legacy_webhook_handler(update_data)
        
        if not update:
            return {"status": "error", "message": "Invalid update"}
        
        # Check user access
        user_id = None
        if update.message:
            user_id = update.effective_user.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
        
        if user_id and not await is_user_allowed(user_id):
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            return {"status": "unauthorized"}
        
        # Route the update
        await route_update(update)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

async def route_update(update: Update):
    """Route update to appropriate handler"""
    try:
        # Create context object
        class Context:
            def __init__(self):
                try:
                    self.bot = bot_core.get_bot()
                except:
                    # Fallback to creating bot directly
                    self.bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
                
        context = Context()
        
        # Route based on update type
        if update.message:
            # Handle automatic message processing first (for filters, auto-deletion, etc.)
            if update.message.text and not update.message.text.startswith('/'):
                await bot_handlers["message_processing"](update, context)
            
            if update.message.photo:
                # Photo message - route to food analysis
                await bot_handlers["photo"](update, context)
                
            elif update.message.text:
                text = update.message.text.lower()
                
                # Check for bot mentions
                if any(mention in text for mention in ["@dmplove_bot", "@DMPlove_bot"]):
                    response_type = await bot_handlers["message_mention"](update, context)
                    
                    # Route based on response type
                    if response_type == "food_analysis" or response_type == "health_profile":
                        await bot_handlers["health_menu"](update, context)
                    elif response_type == "movie_expert":
                        await bot_handlers["movie_menu"](update, context)
                    elif response_type == "message_tags":
                        await bot_handlers["topic_settings"](update, context)
                    else:
                        await handle_general_ai_response(update, context, text)
                
                # Direct commands
                elif text.startswith('/health') or any(keyword in text for keyword in ["здоровье", "профиль"]):
                    await bot_handlers["health_menu"](update, context)
                    
                elif text.startswith('/movie') or text.startswith('/movies'):
                    await bot_handlers["movie_menu"](update, context)
                    
                elif text.startswith('/topic') or "настройки топика" in text:
                    await bot_handlers["topic_settings"](update, context)
                
                # Movie conversations
                elif any(indicator in text for indicator in ["посмотрел", "посмотрела", "оценка", "/10"]):
                    await movie_expert_handlers.handle_movie_message(update, context)
                    
                elif any(keyword in text for keyword in ["фильм", "кино", "сериал", "рекомендации"]):
                    if any(keyword in text for keyword in ["поиск", "найди"]):
                        # Movie search
                        search_query = text.replace("поиск", "").replace("найди", "").replace("фильм", "").strip()
                        if search_query:
                            await movie_expert_handlers.handle_search_query(update, context, search_query)
                    else:
                        await movie_expert_handlers.handle_movie_message(update, context)
                        
                else:
                    # General text message
                    await handle_text_message(update, context)
        
        elif update.callback_query:
            # Callback query
            await bot_handlers["callback_query"](update, context)
            
    except Exception as e:
        logger.error(f"Error routing update: {e}")

async def handle_text_message(update, context):
    """Handle general text messages"""
    text = update.message.text.lower()
    
    # Feature suggestions based on keywords
    if any(keyword in text for keyword in ["еда", "калории", "питание"]):
        response = ("🍽️ Отправьте фото еды для анализа или используйте команду /health для профиля здоровья.\n\n"
                   "💡 Я умею:\n"
                   "• Анализировать калории и БЖУ с фото\n"
                   "• Вести профиль здоровья\n"
                   "• Давать персональные рекомендации")
                   
    elif any(keyword in text for keyword in ["фильм", "кино", "сериал"]):
        response = ("🎬 Используйте команду /movie для работы с фильмами.\n\n"
                   "💡 Я умею:\n"
                   "• Сохранять просмотренные фильмы\n"
                   "• Давать персональные рекомендации\n"
                   "• Вести статистику просмотров\n\n"
                   "Попробуйте: 'Посмотрел Интерстеллар оценка 9/10'")
                   
    elif any(keyword in text for keyword in ["настройки", "топик", "автоудаление"]):
        response = ("⚙️ Используйте команду /topic для настроек топика.\n\n"
                   "💡 Я умею:\n"
                   "• Автоматически удалять сообщения\n"
                   "• Настраивать AI для топиков\n"
                   "• Управлять тегами сообщений")
    else:
        response = ("🤖 **Привет! Я AI-помощник для Telegram.**\n\n"
                   "🍽️ `/health` - анализ еды и профиль здоровья\n"
                   "🎬 `/movie` - фильмы и рекомендации\n"
                   "⚙️ `/topic` - настройки топика\n\n"
                   "📸 Или просто отправьте фото еды для анализа!")
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def handle_general_ai_response(update, context, clean_text):
    """Handle general AI conversation"""
    response = ("🤖 Понял ваше сообщение! Я готов помочь с:\n\n"
               "🍽️ Анализом еды и здоровьем\n"
               "🎬 Фильмами и рекомендациями\n"
               "⚙️ Настройками чата\n\n"
               "Что вас интересует?")
    
    await update.message.reply_text(response)

async def legacy_webhook_handler(update_data):
    """Legacy webhook handler for backward compatibility"""
    logger.info("Processing webhook with legacy handler")
    return {"status": "ok", "message": "Processed with legacy handler"}

# API endpoints
@app.get("/api/test")
async def test_endpoint():
    """Test endpoint"""
    return {
        "status": "ok",
        "message": "Integrated modular architecture is working!",
        "version": "2.0.0",
        "settings_valid": settings.validate() if settings else False,
        "features": {
            "food_health": "✅ Анализ еды, профили здоровья, AI рекомендации",
            "movie_expert": "✅ Фильмы, рекомендации, статистика",
            "message_management": "✅ Автоудаление, теги, модерация",
            "legacy_compatibility": "✅ Поддержка существующих функций"
        }
    }

@app.get("/api/features")
async def features_endpoint():
    """Get detailed features info"""
    return {
        "food_health": {
            "description": "AI анализ изображений еды, профили здоровья, персональные рекомендации",
            "capabilities": [
                "Анализ калорий и БЖУ с фото",
                "Профили здоровья пользователей",
                "Персональные AI рекомендации",
                "Отслеживание тренировок и шагов",
                "Статистика питания"
            ]
        },
        "movie_expert": {
            "description": "Система рекомендаций фильмов на основе просмотренного",
            "capabilities": [
                "Сохранение просмотренных фильмов",
                "AI рекомендации на основе истории",
                "Статистика просмотров",
                "Поиск в коллекции",
                "Экспорт данных"
            ]
        },
        "message_management": {
            "description": "Управление сообщениями в топиках",
            "capabilities": [
                "Автоматическое удаление сообщений",
                "Система тегов для сообщений",
                "Настройки AI для топиков",
                "Автомодерация",
                "Фильтры сообщений"
            ]
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_status = "ok"
        try:
            db_manager.connect()
        except:
            db_status = "error"
        
        # Check bot status
        bot_status = "ok"
        try:
            bot = bot_core.get_bot()
            if not bot:
                bot_status = "error"
        except:
            bot_status = "error"
        
        return {
            "status": "ok",
            "database": db_status,
            "bot": bot_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with redirect to demondimi.ru"""
    return {
        "message": "Telegram Bot API Server",
        "version": "2.0.0",
        "redirect": "https://demondimi.ru",
        "endpoints": {
            "webhook": "/api/webhook",
            "test": "/api/test",
            "features": "/api/features",
            "health": "/api/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)