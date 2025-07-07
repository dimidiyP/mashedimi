import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TelegramError
from typing import Dict, Any, Optional, Callable
from config.settings import settings
from config.constants import ADMIN_IDS
from config.database import db_manager

logger = logging.getLogger(__name__)

class TelegramBotCore:
    """Core Telegram bot functionality"""
    
    def __init__(self):
        self.app: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.handlers: Dict[str, Callable] = {}
        self.middleware: list = []
        
    def initialize(self) -> Application:
        """Initialize the Telegram bot application"""
        if not settings.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN is required")
            
        # Create application
        self.app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
        self.bot = self.app.bot
        
        # Initialize database
        db_manager.connect()
        db_manager.create_indexes()
        
        # Register core handlers
        self._register_core_handlers()
        
        logger.info("Telegram bot initialized successfully")
        return self.app
    
    def _register_core_handlers(self):
        """Register core bot handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("menu", self._handle_menu))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        
        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(self._handle_callback_query))
        
        # Error handler
        self.app.add_error_handler(self._handle_error)
    
    def register_handler(self, name: str, handler: Callable):
        """Register a custom handler"""
        self.handlers[name] = handler
    
    def add_middleware(self, middleware: Callable):
        """Add middleware function"""
        self.middleware.append(middleware)
    
    async def _handle_start(self, update: Update, context) -> None:
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Initialize user in database
        await self._ensure_user_exists(user_id, update.effective_user)
        
        welcome_message = (
            "🤖 Добро пожаловать в AI-помощник!\n\n"
            "Я умею:\n"
            "🍽️ Анализировать еду и считать калории\n"
            "🎬 Рекомендовать фильмы\n"
            "💪 Помогать с фитнесом\n"
            "📊 Вести статистику\n\n"
            "Используйте /menu для доступа к функциям"
        )
        
        await update.message.reply_text(welcome_message)
    
    async def _handle_help(self, update: Update, context) -> None:
        """Handle /help command"""
        help_text = (
            "🤖 Доступные команды:\n\n"
            "/start - Начать работу\n"
            "/menu - Главное меню\n"
            "/help - Показать помощь\n"
            "/stats - Статистика питания\n"
            "/search - Поиск еды\n"
            "/health - Профиль здоровья\n"
            "/movies - Фильмы и рекомендации\n\n"
            "Или просто отправьте фото еды для анализа! 📸"
        )
        
        await update.message.reply_text(help_text)
    
    async def _handle_menu(self, update: Update, context) -> None:
        """Handle /menu command"""
        # This will be implemented by features
        if "menu" in self.handlers:
            await self.handlers["menu"](update, context)
        else:
            await update.message.reply_text("Меню временно недоступно")
    
    async def _handle_message(self, update: Update, context) -> None:
        """Handle text messages"""
        # Apply middleware
        for middleware in self.middleware:
            if not await middleware(update, context):
                return
        
        # Route to appropriate handler
        if "message" in self.handlers:
            await self.handlers["message"](update, context)
        else:
            await update.message.reply_text("Сообщение получено, но обработчик не найден")
    
    async def _handle_photo(self, update: Update, context) -> None:
        """Handle photo messages"""
        # Route to food analysis handler
        if "photo" in self.handlers:
            await self.handlers["photo"](update, context)
        else:
            await update.message.reply_text("Фото получено, но обработчик не найден")
    
    async def _handle_document(self, update: Update, context) -> None:
        """Handle document messages"""
        if "document" in self.handlers:
            await self.handlers["document"](update, context)
        else:
            await update.message.reply_text("Документ получен, но обработчик не найден")
    
    async def _handle_callback_query(self, update: Update, context) -> None:
        """Handle callback queries"""
        if "callback_query" in self.handlers:
            await self.handlers["callback_query"](update, context)
        else:
            await update.callback_query.answer("Обработчик не найден")
    
    async def _handle_error(self, update: Update, context) -> None:
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Произошла ошибка. Попробуйте еще раз."
            )
    
    async def _ensure_user_exists(self, user_id: int, user_data) -> None:
        """Ensure user exists in database"""
        try:
            users_collection = db_manager.get_collection("users")
            
            # Check if user exists
            existing_user = users_collection.find_one({"user_id": user_id})
            
            if not existing_user:
                # Create new user
                user_doc = {
                    "user_id": user_id,
                    "username": user_data.username,
                    "first_name": user_data.first_name,
                    "last_name": user_data.last_name,
                    "is_admin": user_id in ADMIN_IDS,
                    "created_at": None,  # Will be set by features
                    "settings": {
                        "language": "ru",
                        "notifications": True
                    }
                }
                
                users_collection.insert_one(user_doc)
                logger.info(f"Created new user: {user_id}")
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    def get_app(self) -> Application:
        """Get the Telegram application"""
        return self.app
    
    def get_bot(self) -> Bot:
        """Get the Telegram bot"""
        return self.bot

# Global bot instance
bot_core = TelegramBotCore()