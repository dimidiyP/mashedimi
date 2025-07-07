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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot imports
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# Enhanced reliability imports
import sys
import os
sys.path.append('/app/backend')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openai_reliability import init_reliable_openai_client, get_reliable_openai_client
from user_experience import ux_manager, feedback_collector
from debug_system import init_debug_mode, get_debug_logger, is_debug_mode

# OpenAI import
import openai

# Global variables
group_topic_settings = {}

# User management and access control
user_access_list = {}

async def init_user_access():
    """Initialize user access system with default admin"""
    try:
        # Check if admin already exists
        admin_exists = await app.mongodb.user_access.find_one({"role": "admin"})
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
            await app.mongodb.user_access.insert_one(default_admin)
            logger.info("Default admin created: @Dimidiy")
        
        # Check if default user exists
        maria_exists = await app.mongodb.user_access.find_one({"username": "MariaPaperman"})
        if not maria_exists:
            # Add @MariaPaperman as default user
            maria_user = {
                "user_id": 987654321,  # Placeholder ID - will be updated when she writes to bot
                "username": "MariaPaperman",
                "role": "user", 
                "created_at": datetime.utcnow(),
                "created_by": "system",
                "personal_prompt": "Ты полезный AI-ассистент. Отвечай кратко и по существу на русском языке."
            }
            await app.mongodb.user_access.insert_one(maria_user)
            logger.info("Default user created: @MariaPaperman")
            
        # Load all users into memory
        users = app.mongodb.user_access.find({})
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
    return user_id in user_access_list

async def get_user_role(user_id: int) -> str:
    """Get user role (admin/user) or None if not allowed"""
    if user_id in user_access_list:
        return user_access_list[user_id]["role"]
    return None

async def add_user_to_access_list(admin_id: int, username: str, user_id: int, role: str = "user") -> bool:
    """Add user to access list (only admin can do this)"""
    try:
        # Check if requester is admin
        if get_user_role(admin_id) != "admin":
            return False
            
        # Check if user already exists
        if user_id in user_access_list:
            return False
            
        user_data = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "created_at": datetime.utcnow(),
            "created_by": admin_id,
            "personal_prompt": "Ты полезный AI-ассистент. Отвечай кратко и по существу на русском языке."
        }
        
        await app.mongodb.user_access.insert_one(user_data)
        
        # Update memory
        user_access_list[user_id] = {
            "username": username,
            "role": role,
            "personal_prompt": user_data["personal_prompt"]
        }
        
        logger.info(f"User {username} (ID: {user_id}) added by admin {admin_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding user to access list: {str(e)}")
        return False

async def remove_user_from_access_list(admin_id: int, user_id: int) -> bool:
    """Remove user from access list (only admin can do this)"""
    try:
        # Check if requester is admin
        if get_user_role(admin_id) != "admin":
            return False
            
        # Don't allow removing admin
        if user_id in user_access_list and user_access_list[user_id]["role"] == "admin":
            return False
            
        await app.mongodb.user_access.delete_one({"user_id": user_id})
        
        # Update memory
        if user_id in user_access_list:
            del user_access_list[user_id]
            
        logger.info(f"User ID {user_id} removed by admin {admin_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing user from access list: {str(e)}")
        return False

async def update_user_personal_prompt(user_id: int, prompt: str) -> bool:
    """Update user's personal prompt"""
    try:
        await app.mongodb.user_access.update_one(
            {"user_id": user_id},
            {"$set": {"personal_prompt": prompt, "updated_at": datetime.utcnow()}}
        )
        
        # Update memory
        if user_id in user_access_list:
            user_access_list[user_id]["personal_prompt"] = prompt
            
        return True
        
    except Exception as e:
        logger.error(f"Error updating personal prompt: {str(e)}")
        return False

# Excel export functionality
async def export_data_to_excel(data_type: str, chat_id: int = None, topic_id: int = None, user_id: int = None) -> str:
    """Export data to Excel file and return file path"""
    try:
        import pandas as pd
        from datetime import datetime
        
        # Determine filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if topic_id:
            filename = f"/tmp/export_{data_type}_topic_{topic_id}_{timestamp}.xlsx"
        else:
            filename = f"/tmp/export_{data_type}_{timestamp}.xlsx"
        
        if data_type == "food_data":
            # Export food analysis data
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            cursor = app.mongodb.food_analysis.find(query).sort("timestamp", -1)
            data = await cursor.to_list(length=None)
            
            # Convert to DataFrame
            df_data = []
            for item in data:
                df_data.append({
                    "Дата": item.get("timestamp", "").strftime("%Y-%m-%d %H:%M:%S") if item.get("timestamp") else "",
                    "Пользователь": item.get("username", ""),
                    "Блюдо": item.get("dish_name", ""),
                    "Калории": item.get("calories", 0),
                    "Белки": item.get("proteins", 0),
                    "Жиры": item.get("fats", 0),
                    "Углеводы": item.get("carbs", 0),
                    "Описание": item.get("description", ""),
                    "Чат ID": item.get("chat_id", ""),
                    "User ID": item.get("user_id", "")
                })
            
            df = pd.DataFrame(df_data)
            
        elif data_type == "topic_data":
            # Export topic-specific data
            query = {"chat_id": chat_id}
            if topic_id:
                query["topic_id"] = topic_id
            
            cursor = app.mongodb.topic_data.find(query).sort("timestamp", -1)
            data = await cursor.to_list(length=None)
            
            df_data = []
            for item in data:
                df_data.append({
                    "Дата": item.get("timestamp", "").strftime("%Y-%m-%d %H:%M:%S") if item.get("timestamp") else "",
                    "Топик ID": item.get("topic_id", ""),
                    "Тип данных": item.get("data_type", ""),
                    "User ID": item.get("user_id", ""),
                    "Данные": str(item.get("data", {})),
                    "Чат ID": item.get("chat_id", "")
                })
            
            df = pd.DataFrame(df_data)
            
        elif data_type == "user_data":
            # Export user data
            cursor = app.mongodb.user_access.find({})
            users = await cursor.to_list(length=None)
            
            df_data = []
            for user in users:
                df_data.append({
                    "User ID": user.get("user_id", ""),
                    "Username": user.get("username", ""),
                    "Роль": user.get("role", ""),
                    "Дата создания": user.get("created_at", "").strftime("%Y-%m-%d %H:%M:%S") if user.get("created_at") else "",
                    "Создал": user.get("created_by", ""),
                    "Промпт": user.get("personal_prompt", "")
                })
            
            df = pd.DataFrame(df_data)
            
        else:
            return None
        
        # Save to Excel
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
            
            # Add summary sheet
            summary_data = {
                "Параметр": ["Тип экспорта", "Дата экспорта", "Количество записей", "Чат ID", "Топик ID"],
                "Значение": [data_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), len(df), chat_id or "Все", topic_id or "Все"]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        logger.info(f"Exported {len(df)} records to {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        return None

async def handle_admin_export(callback_query, data_type: str):
    """Handle admin export requests"""
    try:
        chat_id = callback_query.message.chat_id
        user_id = callback_query.from_user.id
        
        # Check admin access
        user_role = await get_user_role(user_id)
        if user_role != "admin":
            await bot.answer_callback_query(callback_query.id, "❌ Только администратор может экспортировать данные.")
            return
        
        # Send processing message
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"⏳ Подготавливаю экспорт данных ({data_type})...\n\nЭто может занять несколько секунд."
        )
        
        # Export data
        file_path = await export_data_to_excel(data_type)
        
        if file_path:
            # Send file
            with open(file_path, 'rb') as file:
                await bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=f"📊 Экспорт данных: {data_type}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            
            # Clean up temp file
            import os
            os.remove(file_path)
            
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="✅ Экспорт завершен! Файл отправлен в чат.",
                reply_markup=get_admin_export_keyboard()
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="❌ Ошибка при создании файла экспорта.",
                reply_markup=get_admin_export_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error handling admin export: {str(e)}")
        await bot.edit_message_text(
            chat_id=callback_query.message.chat_id,
            message_id=callback_query.message.message_id,
            text=f"❌ Ошибка экспорта: {str(e)}",
            reply_markup=get_admin_export_keyboard()
        )

async def handle_document_message(message):
    """Handle document messages with basic info"""
    chat_id = message.chat_id
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    is_group = message.chat.type in ['group', 'supergroup']
    
    # Check if this is a topic/thread in a group
    if is_group and hasattr(message, 'message_thread_id') and message.message_thread_id:
        # In topics, only process if bot is mentioned
        bot_username = "DMPlove_bot"  # Replace with your bot username
        
        # Check if bot is mentioned in the message or caption
        text_to_check = ""
        if message.caption:
            text_to_check = message.caption
        elif message.text:
            text_to_check = message.text
            
        if f"@{bot_username}" not in text_to_check:
            # Bot is not mentioned in topic, skip processing
            return
    
    try:
        document = message.document
        file_name = document.file_name or "document"
        file_size = document.file_size
        mime_type = document.mime_type or "unknown"
        
        # Send analyzing message
        analyzing_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"📄 Анализирую документ: {file_name}...",
            message_thread_id=getattr(message, 'message_thread_id', None)  # Reply in same topic
        )
        
        try:
            # Get file info
            file = await bot.get_file(document.file_id)
            if not file.file_path:
                raise Exception("Не удалось получить файл")
            
            # Construct correct file URL
            if file.file_path.startswith('https://'):
                file_url = file.file_path
            else:
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
            
            # Download file content
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url)
                file_content = response.content
            
            # Analyze document content
            analysis = await analyze_document(file_content, file_name, mime_type, user_id)
            
            # Delete analyzing message
            await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            
            # Send analysis result
            result_text = f"""📄 Анализ документа: {file_name}

📋 Тип: {mime_type}
📏 Размер: {file_size} байт
👤 От: {username}
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

🔍 Результат анализа:
{analysis}"""
            
            await bot.send_message(
                chat_id=chat_id,
                text=result_text,
                message_thread_id=getattr(message, 'message_thread_id', None)  # Reply in same topic
            )
            
        except Exception as e:
            logger.error(f"Document analysis error: {str(e)}")
            await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            
            error_msg = await bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка анализа документа: {str(e)}"
            )
            asyncio.create_task(delete_message_after_delay(chat_id, error_msg.message_id, 60))
            
    except Exception as e:
        logger.error(f"Document handling error: {str(e)}")

async def handle_video_message(message):
    """Handle video messages with analysis"""
    chat_id = message.chat_id
    username = message.from_user.username or message.from_user.first_name
    
    try:
        video = message.video
        duration = video.duration
        width = video.width
        height = video.height
        file_size = video.file_size
        
        # Send analyzing message
        analyzing_msg = await bot.send_message(
            chat_id=chat_id,
            text="🎥 Анализирую видео..."
        )
        
        # For now, provide video info analysis
        await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
        
        result_text = f"""🎥 Анализ видео

⏱️ Длительность: {duration} сек
📐 Разрешение: {width}x{height}
📏 Размер: {file_size} байт
👤 От: {username}
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

💡 Функция полного анализа видео с извлечением кадров и описанием содержимого будет доступна в следующем обновлении."""
        
        await bot.send_message(
            chat_id=chat_id,
            text=result_text
        )
        
    except Exception as e:
        logger.error(f"Video handling error: {str(e)}")

async def handle_voice_message(message):
    """Handle voice messages with transcription"""
    chat_id = message.chat_id
    username = message.from_user.username or message.from_user.first_name
    
    try:
        voice = message.voice
        duration = voice.duration
        file_size = voice.file_size
        
        # Send analyzing message
        analyzing_msg = await bot.send_message(
            chat_id=chat_id,
            text="🎤 Обрабатываю голосовое сообщение..."
        )
        
        try:
            # Get voice file
            file = await bot.get_file(voice.file_id)
            if not file.file_path:
                raise Exception("Не удалось получить аудиофайл")
            
            # Construct correct file URL
            if file.file_path.startswith('https://'):
                file_url = file.file_path
            else:
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
            
            # For now, provide voice info
            await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            
            result_text = f"""🎤 Голосовое сообщение

⏱️ Длительность: {duration} сек
📏 Размер: {file_size} байт
👤 От: {username}
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

🔄 Функция распознавания речи через OpenAI Whisper API будет добавлена в следующем обновлении."""
            
            await bot.send_message(
                chat_id=chat_id,
                text=result_text
            )
            
        except Exception as e:
            logger.error(f"Voice analysis error: {str(e)}")
            await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            
            error_msg = await bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка обработки голосового сообщения"
            )
            asyncio.create_task(delete_message_after_delay(chat_id, error_msg.message_id, 60))
            
    except Exception as e:
        logger.error(f"Voice handling error: {str(e)}")

async def handle_video_note_message(message):
    """Handle video note messages"""
    chat_id = message.chat_id
    username = message.from_user.username or message.from_user.first_name
    
    try:
        video_note = message.video_note
        duration = video_note.duration
        length = video_note.length
        file_size = video_note.file_size
        
        result_text = f"""🎥 Видео-сообщение (кружок)

⏱️ Длительность: {duration} сек
📐 Размер: {length}x{length}
📏 Размер файла: {file_size} байт
👤 От: {username}
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

💡 Получено видео-сообщение кружком!"""
        
        await bot.send_message(
            chat_id=chat_id,
            text=result_text
        )
        
    except Exception as e:
        logger.error(f"Video note handling error: {str(e)}")

async def handle_sticker_message(message):
    """Handle sticker messages"""
    # Don't spam with sticker responses in groups
    pass

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Family Telegram Bot Assistant")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Telegram Bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")
bot = Bot(token=TELEGRAM_TOKEN)

# Initialize OpenAI client with environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Create OpenAI client with enhanced reliability
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
logger.info(f"OpenAI API key loaded: {OPENAI_API_KEY[:20]}...")

# Initialize reliable OpenAI client
init_reliable_openai_client(OPENAI_API_KEY)
logger.info("Enhanced OpenAI reliability system initialized")

# Initialize debug mode (check environment variable)
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
init_debug_mode(DEBUG_MODE)
if DEBUG_MODE:
    logger.info("🐛 DEBUG MODE ENABLED - All interactions will be logged")
else:
    logger.info("✅ Debug mode disabled")

# MongoDB setup
@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    app.mongodb = app.mongodb_client.telegram_bot_db
    logger.info("Connected to MongoDB")
    
    # Initialize collections
    await app.mongodb.users.create_index("user_id", unique=True)
    await app.mongodb.food_analysis.create_index("user_id")
    await app.mongodb.health_data.create_index("user_id")
    await app.mongodb.movies.create_index("user_id")
    await app.mongodb.user_access.create_index("user_id", unique=True)
    await app.mongodb.topic_settings.create_index(["chat_id", "topic_id"], unique=True)
    await app.mongodb.topic_summaries.create_index(["chat_id", "topic_id"])
    await app.mongodb.topic_data.create_index(["chat_id", "topic_id", "data_type"])
    await app.mongodb.user_health_history.create_index(["user_id", "data_type", "timestamp"])
    
    # Initialize user access system
    await init_user_access()

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

# OpenAI Functions
async def analyze_food_image(image_url: str, user_id: int) -> Dict:
    """Analyze food image using OpenAI Vision API with direct image download"""
    try:
        # Get next unique number for this user
        food_count = await app.mongodb.food_analysis.count_documents({"user_id": user_id})
        unique_number = food_count + 1
        
        logger.info(f"Downloading image from Telegram: {image_url}")
        
        # Download image directly from Telegram
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content
            
        # Convert to base64
        import base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determine image format
        image_format = "jpeg"  # Default
        if image_bytes.startswith(b'\x89PNG'):
            image_format = "png"
        elif image_bytes.startswith(b'\xff\xd8'):
            image_format = "jpeg"
        elif image_bytes.startswith(b'GIF'):
            image_format = "gif"
            
        logger.info(f"Image downloaded: {len(image_bytes)} bytes, format: {image_format}")
        
        # Try gpt-4o first, fallback to gpt-4o-mini
        models_to_try = ["gpt-4o", "gpt-4o-mini"]
        
        for model_name in models_to_try:
            try:
                logger.info(f"Analyzing image with {model_name}")
                
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": """Внимательно проанализируйте изображение. Есть ли на нём ЕДА или НАПИТКИ? 
                                    Еда может быть: готовые блюда, сырые продукты, напитки, десерты, фрукты, овощи, выпечка, снеки и т.д.
                                    
                                    ВАЖНО: Если это еда, обязательно рассчитайте РЕАЛЬНЫЕ значения калорий, белков, жиров и углеводов на основе того, что видите на изображении. Оцените порции и дайте конкретные числа.
                                    
                                    Ответьте СТРОГО в JSON формате:
                                    {
                                        "is_food": true,
                                        "dish_name": "название блюда/продукта",
                                        "calories": реальное_число_калорий,
                                        "proteins": реальное_количество_белков_в_граммах,
                                        "fats": реальное_количество_жиров_в_граммах,
                                        "carbs": реальное_количество_углеводов_в_граммах,
                                        "description": "что видите"
                                    }
                                    
                                    Примеры:
                                    - Большой бутерброд с сыром: калории ~300, белки ~12, жиры ~15, углеводы ~30
                                    - Йогурт с ягодами: калории ~150, белки ~6, жиры ~3, углеводы ~20
                                    - Яблоко среднее: калории ~80, белки ~0.5, жиры ~0.3, углеводы ~20
                                    
                                    Если еды НЕТ: {"is_food": false, "dish_name": "", "calories": 0, "proteins": 0, "fats": 0, "carbs": 0, "description": "еда не найдена"}"""
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{image_format};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500
                )
                
                # Parse JSON response
                content = response.choices[0].message.content.strip()
                logger.info(f"OpenAI response with {model_name}: {content[:200]}...")
                
                # Clean JSON (remove markdown if present)
                if content.startswith("```json"):
                    content = content.replace("```json", "").replace("```", "").strip()
                
                analysis = json.loads(content)
                analysis["unique_number"] = unique_number
                logger.info(f"Successfully analyzed with {model_name}: is_food={analysis.get('is_food')}, dish={analysis.get('dish_name')}")
                return analysis
                
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing error with {model_name}: {json_err}")
                logger.error(f"Raw content: {content}")
                # Try next model
                continue
            except Exception as model_err:
                logger.error(f"Model {model_name} error: {str(model_err)}")
                # Try next model
                continue
        
        # If all models failed
        logger.error("All vision models failed, returning fallback")
        return {
            "is_food": False,
            "dish_name": "Ошибка анализа",
            "calories": 0,
            "proteins": 0,
            "fats": 0,
            "carbs": 0,
            "description": "Не удалось проанализировать изображение",
            "unique_number": unique_number
        }
            
    except Exception as e:
        logger.error(f"Food analysis error: {str(e)}")
        return {
            "is_food": False,
            "dish_name": "Системная ошибка",
            "calories": 0,
            "proteins": 0,
            "fats": 0,
            "carbs": 0,
            "description": f"Ошибка: {str(e)}",
            "unique_number": 1
        }

async def generate_fitness_advice(user_data: dict) -> str:
    """Generate fitness advice using OpenAI with nutrition data"""
    try:
        user_id = user_data.get('user_id')
        
        # Get recent nutrition data for personalized advice
        nutrition_summary = ""
        if user_id:
            # Get last 7 days of food data
            recent_stats = await get_food_stats(user_id, "week")
            daily_avg_calories = recent_stats['total_calories'] // 7 if recent_stats['total_meals'] > 0 else 0
            daily_avg_meals = recent_stats['total_meals'] // 7 if recent_stats['total_meals'] > 0 else 0
            
            if recent_stats['total_meals'] > 0:
                nutrition_summary = f"""
        
📊 Данные питания за неделю:
- Среднее потребление калорий в день: {daily_avg_calories} ккал
- Среднее количество приемов пищи: {daily_avg_meals}
- Общие белки за неделю: {recent_stats['total_proteins']} г
- Общие жиры за неделю: {recent_stats['total_fats']} г  
- Общие углеводы за неделю: {recent_stats['total_carbs']} г"""
            else:
                nutrition_summary = "\n\n📊 Данные о питании: пока нет записей (отправьте фото еды для анализа)"
        
        prompt = f"""
        Ты персональный фитнес-партнер и диетолог. Пользователь:
        - Возраст: {user_data.get('age', 'не указан')}
        - Рост: {user_data.get('height', 'не указан')} см
        - Вес: {user_data.get('weight', 'не указан')} кг
        - Цель: {user_data.get('goal', 'общее здоровье')}
        {nutrition_summary}
        
        На основе ВСЕХ этих данных дай персональные рекомендации по фитнесу и питанию. 
        Если есть данные о питании - анализируй их и дай конкретные советы по улучшению рациона.
        Будь мотивирующим и дружелюбным.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты персональный фитнес-тренер и диетолог. Анализируешь данные о питании и даешь персональные рекомендации."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=700
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Fitness advice error: {str(e)}")
        return f"❌ Ошибка генерации советов: {str(e)}"

# ChatGPT Function Calling definitions
MOVIE_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_movie_with_rating",
            "description": "Save a movie with user's rating and review to the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Movie or TV show title"
                    },
                    "rating": {
                        "type": "number",
                        "description": "User's rating from 1 to 10"
                    },
                    "review": {
                        "type": "string",
                        "description": "User's review or thoughts about the movie"
                    },
                    "genre": {
                        "type": "string",
                        "description": "Movie genre (action, comedy, drama, etc.)"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year of the movie"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["watched", "want_to_watch", "watching"],
                        "description": "User's watching status"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_recommendations",
            "description": "Get personalized movie recommendations based on user's watch history and preferences",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_genres": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Genres user is interested in"
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Minimum rating threshold for recommendations"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_user_movies",
            "description": "Search through user's movie collection",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (title, genre, or keyword)"
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Minimum rating filter"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

FOOD_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_food_statistics",
            "description": "Get user's food and nutrition statistics for a specific period",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "week", "month"],
                        "description": "Time period for statistics"
                    },
                    "target_user_id": {
                        "type": "integer",
                        "description": "User ID to get stats for (optional, defaults to current user)"
                    }
                },
                "required": ["period"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_food_database",
            "description": "Search through food database with filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for food items"
                    },
                    "period": {
                        "type": "string",
                        "enum": ["today", "yesterday", "week", "month"],
                        "description": "Time period filter"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

async def handle_function_call(function_name: str, arguments: dict, user_id: int, chat_id: int) -> str:
    """Handle ChatGPT function calls"""
    try:
        if function_name == "save_movie_with_rating":
            # Save movie with rating
            movie_data = {
                "title": arguments.get("title"),
                "rating": arguments.get("rating"),
                "review": arguments.get("review", ""),
                "genre": arguments.get("genre", ""),
                "year": arguments.get("year"),
                "status": arguments.get("status", "watched")
            }
            
            result_id = await save_movie(user_id, movie_data)
            
            rating_text = f" с оценкой {movie_data['rating']}/10" if movie_data['rating'] else ""
            review_text = f"\n💭 Отзыв: {movie_data['review']}" if movie_data['review'] else ""
            
            return f"✅ Фильм '{movie_data['title']}' добавлен в ваш список{rating_text}!{review_text}"
        
        elif function_name == "get_movie_recommendations":
            # Get personalized recommendations
            user_data = await get_movie_recommendations_data(user_id)
            
            if "message" in user_data:
                return user_data["message"]
            
            # Generate recommendations based on user preferences
            rec_prompt = f"""На основе предпочтений пользователя порекомендуй 5 фильмов:
            
Статистика пользователя:
- Всего фильмов: {user_data['total_movies']}
- Средняя оценка: {user_data['average_rating']}/10
- Любимые жанры: {', '.join(user_data['favorite_genres'])}
- Высоко оцененные: {', '.join(user_data['high_rated_movies'][:5])}
- Недавно смотрел: {', '.join(user_data['recent_movies'])}

Дай 5 конкретных рекомендаций с кратким описанием почему они подойдут."""

            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по кинематографу. Давай персональные рекомендации фильмов."},
                    {"role": "user", "content": rec_prompt}
                ],
                max_tokens=800
            )
            
            return f"🎬 **Персональные рекомендации:**\n\n{response.choices[0].message.content}"
        
        elif function_name == "search_user_movies":
            # Search user's movies
            query = arguments.get("query", "").lower()
            min_rating = arguments.get("min_rating", 0)
            
            user_movies = await get_user_movies(user_id, 100)
            
            # Filter movies
            filtered_movies = []
            for movie in user_movies:
                title_match = query in movie.get("title", "").lower()
                genre_match = query in movie.get("genre", "").lower()
                rating_match = movie.get("rating", 0) >= min_rating
                
                if (title_match or genre_match) and rating_match:
                    filtered_movies.append(movie)
            
            if not filtered_movies:
                return f"🔍 Не найдено фильмов по запросу '{query}'"
            
            result_text = f"🔍 **Найдено {len(filtered_movies)} фильмов по запросу '{query}':**\n\n"
            
            for i, movie in enumerate(filtered_movies[:10], 1):
                rating_text = f" ({movie['rating']}/10)" if movie.get('rating') else ""
                genre_text = f" • {movie['genre']}" if movie.get('genre') else ""
                result_text += f"{i}. {movie['title']}{rating_text}{genre_text}\n"
            
            return result_text
        
        elif function_name == "get_food_statistics":
            # Get food statistics
            period = arguments.get("period", "week")
            target_user_id = arguments.get("target_user_id", user_id)
            
            stats = await get_enhanced_food_stats(target_user_id, period)
            
            return f"""📊 **Статистика питания за {period}:**

🍽️ Приемов пищи: {stats['total_meals']}
🔥 Калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']} г
🥑 Жиры: {stats['total_fats']} г
🍞 Углеводы: {stats['total_carbs']} г

💡 Среднее в день: {stats['total_calories'] // 7 if period == 'week' else stats['total_calories']} ккал"""
        
        elif function_name == "search_food_database":
            # Search food database
            query = arguments.get("query")
            period = arguments.get("period")
            
            # Use existing search function
            return await handle_database_search_internal(chat_id, user_id, query, period)
        
        else:
            return f"❌ Неизвестная функция: {function_name}"
    
    except Exception as e:
        logger.error(f"Function call error: {str(e)}")
        return f"❌ Ошибка выполнения функции: {str(e)}"

async def handle_database_search_internal(chat_id: int, user_id: int, query: str, period: str = None) -> str:
    """Internal function for database search"""
    try:
        # Parse the query for date filters and search terms
        search_query = {}
        search_terms = []
        
        # Date filtering
        if period == "today" or "сегодня" in query.lower():
            today = datetime.utcnow().strftime("%Y-%m-%d")
            search_query["date"] = today
        elif period == "yesterday" or "вчера" in query.lower():
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            search_query["date"] = yesterday
        elif period == "week" or "неделя" in query.lower():
            week_ago = datetime.utcnow() - timedelta(days=7)
            search_query["timestamp"] = {"$gte": week_ago}
        elif period == "month" or "месяц" in query.lower():
            month_ago = datetime.utcnow() - timedelta(days=30)
            search_query["timestamp"] = {"$gte": month_ago}
        
        # Extract search terms (remove date keywords)
        clean_query = query.lower()
        date_keywords = ["сегодня", "вчера", "неделя", "месяц", "today", "yesterday", "week", "month"]
        for keyword in date_keywords:
            clean_query = clean_query.replace(keyword, "").strip()
        
        # Add text search if there are remaining terms
        if clean_query:
            search_query["dish_name"] = {"$regex": clean_query, "$options": "i"}
        
        # Add user filter
        search_query["user_id"] = user_id
        
        # Perform search
        cursor = app.mongodb.food_analysis.find(search_query).sort("timestamp", -1).limit(20)
        results = await cursor.to_list(20)
        
        if not results:
            return f"🔍 Не найдено записей по запросу '{query}'"
        
        # Calculate statistics
        total_calories = sum(item.get("calories", 0) for item in results)
        total_proteins = sum(item.get("proteins", 0) for item in results)
        total_fats = sum(item.get("fats", 0) for item in results)
        total_carbs = sum(item.get("carbs", 0) for item in results)
        
        # Format results
        result_text = f"🔍 **Найдено {len(results)} записей по запросу '{query}':**\n\n"
        
        for i, item in enumerate(results[:10], 1):
            date_str = item.get("date", "")
            time_str = item.get("time", "")[:5]  # HH:MM format
            
            result_text += f"{i}. **{item.get('dish_name', 'Неизвестно')}**\n"
            result_text += f"   📅 {date_str} {time_str} • 🔥 {item.get('calories', 0)} ккал\n"
            result_text += f"   🥩 {item.get('proteins', 0)}г • 🥑 {item.get('fats', 0)}г • 🍞 {item.get('carbs', 0)}г\n\n"
        
        if len(results) > 10:
            result_text += f"... и еще {len(results) - 10} записей\n\n"
        
        result_text += f"📊 **Общая статистика:**\n"
        result_text += f"🔥 Калории: {total_calories} ккал\n"
        result_text += f"🥩 Белки: {total_proteins} г\n"
        result_text += f"🥑 Жиры: {total_fats} г\n"
        result_text += f"🍞 Углеводы: {total_carbs} г"
        
        return result_text
        
    except Exception as e:
        logger.error(f"Database search error: {str(e)}")
        return f"❌ Ошибка поиска: {str(e)}"

async def generate_movie_recommendations(user_movies: List[str]) -> str:
    """Generate movie recommendations based on user's watched movies"""
    try:
        movies_list = ", ".join(user_movies[-10:])  # Last 10 movies
        
        prompt = f"""
        Пользователь посмотрел и оценил положительно эти фильмы/сериалы: {movies_list}
        
        Порекомендуй 5 похожих фильмов или сериалов с кратким описанием каждого.
        Учти жанры, стиль, и тематику просмотренных работ.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using available model
            messages=[
                {"role": "system", "content": "Ты эксперт по кинематографу и сериалам"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Movie recommendations error: {str(e)}")
        return f"❌ Ошибка генерации рекомендаций: {str(e)}"

async def enhanced_free_chat_ai(message: str, user_id: int, chat_id: int = None, topic_id: int = None) -> str:
    """Enhanced free chat with AI using reliable OpenAI client and UX improvements"""
    
    # Debug logging
    debug_logger = get_debug_logger()
    start_time = time.time()
    
    # Start UX tracking
    response_timer = ux_manager.start_response_timer(user_id)
    
    try:
        # Debug log input
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="ai_chat_request",
            input_data={"message": message, "chat_id": chat_id, "topic_id": topic_id}
        )
        
        # Start typing indicator
        await ux_manager.start_typing_indicator(bot, chat_id or user_id, user_id)
        
        # Show progress for long operations
        progress_msg_id = None
        if any(keyword in message.lower() for keyword in ['анализ', 'статистика', 'рекомендаци']):
            progress_msg_id = await ux_manager.show_progress_message(bot, chat_id or user_id, "ai_thinking")
        
        # Get user's preferred model
        user_data = await get_user_data(user_id)
        model = user_data.get("ai_model", "gpt-3.5-turbo")
        
        # Add user message to conversation history
        add_message_to_conversation(user_id, "user", message)
        
        # Enhanced system prompt with function calling capabilities
        enhanced_prompt = """Ты полезный AI-ассистент для семейного Telegram бота. У тебя есть доступ к базам данных пользователя через функции.

ДОСТУПНЫЕ ФУНКЦИИ:
🎬 ФИЛЬМЫ:
- save_movie_with_rating: сохранить фильм с оценкой когда пользователь говорит что посмотрел фильм
- get_movie_recommendations: дать рекомендации на основе истории просмотров
- search_user_movies: найти фильмы в коллекции пользователя

🍽️ ПИТАНИЕ:
- get_food_statistics: получить статистику питания за период
- search_food_database: найти записи о еде

КОГДА ИСПОЛЬЗОВАТЬ ФУНКЦИИ:
✅ "Я посмотрел фильм X, оценка 8/10" → save_movie_with_rating
✅ "Что мне посмотреть?" → get_movie_recommendations  
✅ "Какую статистику по еде за неделю?" → get_food_statistics
✅ "Найди мою еду за вчера" → search_food_database

Отвечай на русском языке, будь дружелюбным и полезным."""

        # Get personal prompt if exists
        if user_id in user_access_list:
            personal_prompt = user_access_list[user_id]["personal_prompt"]
            enhanced_prompt = f"{personal_prompt}\n\n{enhanced_prompt}"
        
        # Build conversation messages
        messages = [
            {"role": "system", "content": enhanced_prompt}
        ]
        
        # Add conversation history
        conversation_history = get_user_conversation(user_id)
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Determine which functions to include based on message content
        available_functions = []
        
        # Movie-related keywords
        movie_keywords = ["фильм", "сериал", "посмотрел", "посмотрела", "рекомендаци", "кино", "movie", "watched", "rating", "оценка"]
        if any(keyword in message.lower() for keyword in movie_keywords):
            available_functions.extend(MOVIE_FUNCTIONS)
        
        # Food-related keywords  
        food_keywords = ["еда", "статистика", "калории", "питание", "съел", "съела", "food", "nutrition", "calories"]
        if any(keyword in message.lower() for keyword in food_keywords):
            available_functions.extend(FOOD_FUNCTIONS)
        
        # If no specific keywords, include all functions
        if not available_functions:
            available_functions = MOVIE_FUNCTIONS + FOOD_FUNCTIONS
        
        # Prepare request for OpenAI
        openai_request_data = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "tools": available_functions if available_functions else None,
            "tool_choice": "auto" if available_functions else None
        }
        
        # Use reliable OpenAI client
        reliable_client = get_reliable_openai_client()
        
        openai_start_time = time.time()
        result = await reliable_client.safe_chat_completion(**openai_request_data)
        openai_response_time = time.time() - openai_start_time
        
        # Debug log OpenAI request
        debug_logger.log_openai_request(
            user_id=user_id,
            request_data=openai_request_data,
            response_data={"success": result["success"], "error_type": result.get("error_type")},
            error=result.get("error"),
            response_time=openai_response_time
        )
        
        # Handle result from reliable client
        if not result["success"]:
            # Track error for UX improvement
            ux_manager.track_user_error(user_id, result["error_type"] or "unknown")
            
            # Show helpful error message based on error type
            if result["error_type"] == "rate_limit":
                error_response = "🚫 Сервис временно перегружен. Попробуйте через несколько минут.\n\n💡 Совет: Попробуйте сформулировать вопрос короче."
            elif result["error_type"] == "timeout":
                error_response = "⏰ Запрос занял слишком много времени. Попробуйте упростить вопрос."
            elif result["error_type"] == "connection":
                error_response = "🔌 Проблемы с подключением к AI сервису. Повторите попытку."
            else:
                error_response = f"❌ {result['error']}"
                
            # Show help hint if user has many errors
            if ux_manager.should_show_help_hint(user_id, result["error_type"] or "unknown"):
                error_response += "\n\n💡 Подсказка: Попробуйте использовать более простые запросы или команды бота."
            
            # Debug log error response
            total_time = time.time() - start_time
            debug_logger.log_user_interaction(
                user_id=user_id,
                username=user_access_list.get(user_id, {}).get("username", "unknown"),
                interaction_type="ai_chat_response",
                input_data={"message": message},
                output_data={"response": error_response},
                response_time=total_time,
                error=result.get("error"),
                context={"error_type": result.get("error_type")}
            )
            
            return error_response
        
        response = result["response"]
        
        # Handle function calls
        if response.choices[0].message.tool_calls:
            # Process function calls
            function_results = []
            
            for tool_call in response.choices[0].message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                logger.info(f"Function call: {function_name} with args: {arguments}")
                
                # Debug log function call
                debug_logger.log_system_event(
                    "function_call",
                    {
                        "user_id": user_id,
                        "function_name": function_name,
                        "arguments": arguments
                    }
                )
                
                # Execute function
                result = await handle_function_call(function_name, arguments, user_id, chat_id or user_id)
                function_results.append(result)
            
            # If there are function results, return them
            if function_results:
                final_result = "\n\n".join(function_results)
                add_message_to_conversation(user_id, "assistant", final_result)
                
                # Debug log successful response
                total_time = time.time() - start_time
                debug_logger.log_user_interaction(
                    user_id=user_id,
                    username=user_access_list.get(user_id, {}).get("username", "unknown"),
                    interaction_type="ai_chat_response",
                    input_data={"message": message},
                    output_data={"response": final_result, "function_calls": len(function_results)},
                    response_time=total_time,
                    context={"used_functions": True}
                )
                
                return final_result
        
        # Regular response without function calls
        ai_response = response.choices[0].message.content
        
        # Add AI response to conversation history
        add_message_to_conversation(user_id, "assistant", ai_response)
        
        # Debug log successful response
        total_time = time.time() - start_time
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="ai_chat_response",
            input_data={"message": message},
            output_data={"response": ai_response},
            response_time=total_time,
            context={"used_functions": False}
        )
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Enhanced free chat error: {str(e)}")
        ux_manager.track_user_error(user_id, "unexpected")
        
        # Debug log exception
        total_time = time.time() - start_time
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="ai_chat_response",
            input_data={"message": message},
            output_data=None,
            response_time=total_time,
            error=str(e),
            context={"exception": True}
        )
        
        return f"❌ Произошла неожиданная ошибка. Попробуйте еще раз."
        
    finally:
        # Cleanup UX elements
        ux_manager.stop_typing_indicator(chat_id or user_id, user_id)
        if progress_msg_id:
            await ux_manager.delete_progress_message(bot, chat_id or user_id, progress_msg_id)
        
        # End response timer
        response_time = ux_manager.end_response_timer(user_id)
        logger.info(f"Response time for user {user_id}: {response_time:.2f}s")

async def free_chat_ai(message: str, user_id: int, chat_id: int = None, topic_id: int = None) -> str:
    """Free chat with AI using conversation context and function calling"""
    try:
        # Get user's preferred model
        user_data = await get_user_data(user_id)
        model = user_data.get("ai_model", "gpt-3.5-turbo")
        
        # Map model names to available models
        model_mapping = {
            "gpt-4": "gpt-3.5-turbo",
            "gpt-4-turbo-preview": "gpt-3.5-turbo", 
            "gpt-3.5-turbo": "gpt-3.5-turbo"
        }
        
        actual_model = model_mapping.get(model, "gpt-3.5-turbo")
        
        # Add user message to conversation history
        add_message_to_conversation(user_id, "user", message)
        
        # Enhanced system prompt with function calling capabilities
        enhanced_prompt = """Ты полезный AI-ассистент для семейного Telegram бота. У тебя есть доступ к базам данных пользователя через функции.

ДОСТУПНЫЕ ФУНКЦИИ:
🎬 ФИЛЬМЫ:
- save_movie_with_rating: сохранить фильм с оценкой когда пользователь говорит что посмотрел фильм
- get_movie_recommendations: дать рекомендации на основе истории просмотров
- search_user_movies: найти фильмы в коллекции пользователя

🍽️ ПИТАНИЕ:
- get_food_statistics: получить статистику питания за период
- search_food_database: найти записи о еде

КОГДА ИСПОЛЬЗОВАТЬ ФУНКЦИИ:
✅ "Я посмотрел фильм X, оценка 8/10" → save_movie_with_rating
✅ "Что мне посмотреть?" → get_movie_recommendations  
✅ "Какую статистику по еде за неделю?" → get_food_statistics
✅ "Найди мою еду за вчера" → search_food_database

Отвечай на русском языке, будь дружелюбным и полезным."""

        # Get personal prompt if exists
        if user_id in user_access_list:
            personal_prompt = user_access_list[user_id]["personal_prompt"]
            enhanced_prompt = f"{personal_prompt}\n\n{enhanced_prompt}"
        
        # Build conversation messages
        messages = [
            {"role": "system", "content": enhanced_prompt}
        ]
        
        # Add conversation history
        conversation_history = get_user_conversation(user_id)
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Determine which functions to include based on message content
        available_functions = []
        
        # Movie-related keywords
        movie_keywords = ["фильм", "сериал", "посмотрел", "посмотрела", "рекомендаци", "кино", "movie", "watched", "rating", "оценка"]
        if any(keyword in message.lower() for keyword in movie_keywords):
            available_functions.extend(MOVIE_FUNCTIONS)
        
        # Food-related keywords  
        food_keywords = ["еда", "статистика", "калории", "питание", "съел", "съела", "food", "nutrition", "calories"]
        if any(keyword in message.lower() for keyword in food_keywords):
            available_functions.extend(FOOD_FUNCTIONS)
        
        # If no specific keywords, include all functions
        if not available_functions:
            available_functions = MOVIE_FUNCTIONS + FOOD_FUNCTIONS
        
        # Make API call with function calling
        completion_params = {
            "model": actual_model,
            "messages": messages,
            "max_tokens": 500
        }
        
        # Add functions if available
        if available_functions:
            completion_params["tools"] = available_functions
            completion_params["tool_choice"] = "auto"
        
        response = openai_client.chat.completions.create(**completion_params)
        
        # Handle function calls
        if response.choices[0].message.tool_calls:
            # Process function calls
            function_results = []
            
            for tool_call in response.choices[0].message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                logger.info(f"Function call: {function_name} with args: {arguments}")
                
                # Execute function
                result = await handle_function_call(function_name, arguments, user_id, chat_id or user_id)
                function_results.append(result)
            
            # If there are function results, return them
            if function_results:
                final_result = "\n\n".join(function_results)
                add_message_to_conversation(user_id, "assistant", final_result)
                return final_result
        
        # Regular response without function calls
        ai_response = response.choices[0].message.content
        
        # Add AI response to conversation history
        add_message_to_conversation(user_id, "assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Free chat error: {str(e)}")
        return f"❌ Ошибка: {str(e)}"

# Inline Keyboards
def get_main_menu_keyboard():
    """Create main menu inline keyboard"""
    keyboard = [
        [InlineKeyboardButton("📸 Анализ еды", callback_data="analyze_food_info")],
        [InlineKeyboardButton("💪 Фитнес советы", callback_data="fitness_advice"), 
         InlineKeyboardButton("👤 Профиль", callback_data="health_profile")],
        [InlineKeyboardButton("🤖 AI Чат", callback_data="free_chat"), 
         InlineKeyboardButton("🎬 Фильмы", callback_data="movies")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats_main"), 
         InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("❌ Закрыть меню", callback_data="close_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quick_actions_keyboard():
    """Create quick actions keyboard for app-like experience"""
    keyboard = [
        [InlineKeyboardButton("📱 Быстрые действия", callback_data="quick_actions")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    """Create settings inline keyboard"""
    keyboard = [
        [InlineKeyboardButton("🤖 Модель ИИ", callback_data="ai_model"),
         InlineKeyboardButton("🎯 Фитнес цель", callback_data="fitness_goal")],
        [InlineKeyboardButton("➕ Новая команда", callback_data="create_command"),
         InlineKeyboardButton("📝 Мои команды", callback_data="my_commands")],
        [InlineKeyboardButton("🔧 Предпромпты", callback_data="prompts"),
         InlineKeyboardButton("📱 Команды бота", callback_data="bot_commands")],
        [InlineKeyboardButton("🍽️ Настройки еды", callback_data="food_settings"),
         InlineKeyboardButton("📊 Общие настройки", callback_data="general_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_food_settings_keyboard():
    """Create food analysis settings keyboard"""
    keyboard = [
        [InlineKeyboardButton("📍 Только в теме 'Еда  фото'", callback_data="topic_only_food")],
        [InlineKeyboardButton("🌐 Во всех темах группы", callback_data="topic_all")],
        [InlineKeyboardButton("🔔 Уведомления о находке", callback_data="toggle_notifications")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_prompts_keyboard():
    """Create prompts management keyboard"""
    keyboard = [
        [InlineKeyboardButton("📝 Фитнес промпт", callback_data="edit_fitness_prompt")],
        [InlineKeyboardButton("🤖 Общение промпт", callback_data="edit_chat_prompt")],
        [InlineKeyboardButton("🎬 Фильмы промпт", callback_data="edit_movies_prompt")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_model_keyboard():
    """Create AI model selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("GPT-3.5 Turbo (рекомендуется)", callback_data="model_gpt-3.5-turbo")],
        [InlineKeyboardButton("GPT-4o-mini (для изображений)", callback_data="model_gpt-4o-mini")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_health_profile_keyboard():
    """Create health profile keyboard"""
    keyboard = [
        [InlineKeyboardButton("📏 Рост", callback_data="set_height")],
        [InlineKeyboardButton("⚖️ Вес", callback_data="set_weight")],
        [InlineKeyboardButton("🎂 Возраст", callback_data="set_age")],
        [InlineKeyboardButton("🚶 Шаги в день", callback_data="set_steps")],
        [InlineKeyboardButton("🏃 Тренировки", callback_data="set_workout")],
        [InlineKeyboardButton("📊 История изменений", callback_data="view_health_history")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stats_keyboard():
    """Create statistics keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 Выбрать пользователя и период", callback_data="enhanced_stats_menu")],
        [InlineKeyboardButton("⚡ Быстрая статистика", callback_data="quick_stats_menu")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quick_stats_keyboard():
    """Create quick statistics keyboard for current user"""
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="quick_stats_today")],
        [InlineKeyboardButton("🕐 Вчера", callback_data="quick_stats_yesterday")],
        [InlineKeyboardButton("📊 Неделя", callback_data="quick_stats_week")],
        [InlineKeyboardButton("📈 Месяц", callback_data="quick_stats_month")],
        [InlineKeyboardButton("◀️ Назад", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_enhanced_stats_keyboard():
    """Create enhanced statistics keyboard with user and period selection"""
    keyboard = [
        [InlineKeyboardButton("👤 Выбрать пользователя", callback_data="select_stats_user")],
        [InlineKeyboardButton("📅 Выбрать период", callback_data="select_stats_period")],
        [InlineKeyboardButton("◀️ Назад", callback_data="stats_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stats_period_keyboard():
    """Create period selection keyboard for statistics"""
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="stats_period_today")],
        [InlineKeyboardButton("🕐 Вчера", callback_data="stats_period_yesterday")],
        [InlineKeyboardButton("📊 Неделя", callback_data="stats_period_week")],
        [InlineKeyboardButton("📈 Месяц", callback_data="stats_period_month")],
        [InlineKeyboardButton("◀️ Назад", callback_data="enhanced_stats_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stats_user_keyboard():
    """Create user selection keyboard for statistics"""
    keyboard = []
    
    # Add buttons for each allowed user
    for user_id, user_data in user_access_list.items():
        username = user_data["username"]
        role_emoji = "👑" if user_data["role"] == "admin" else "👤"
        keyboard.append([InlineKeyboardButton(f"{role_emoji} @{username}", callback_data=f"stats_user_{user_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="enhanced_stats_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_stop_keyboard():
    """Create stop dialog keyboard"""
    keyboard = [
        [InlineKeyboardButton("🛑 Остановить диалог", callback_data="stop_dialog")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_topic_settings_keyboard():
    """Create topic settings keyboard (for group admins)"""
    keyboard = [
        [InlineKeyboardButton("🔄 Переключить анализ еды", callback_data="toggle_food_analysis")],
        [InlineKeyboardButton("🤖 Переключить авто-анализ", callback_data="toggle_auto_analysis")],
        [InlineKeyboardButton("📊 Тип данных", callback_data="set_topic_data_type")],
        [InlineKeyboardButton("⏰ Время автоудаления", callback_data="set_auto_delete_delay")],
        [InlineKeyboardButton("💬 Настроить промпт", callback_data="set_topic_prompt")],
        [InlineKeyboardButton("🧹 Очистить контекст", callback_data="clear_topic_context")],
        [InlineKeyboardButton("📋 Статус топика", callback_data="topic_status")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_topic_data_type_keyboard():
    """Create data type selection keyboard for topics"""
    keyboard = [
        [InlineKeyboardButton("🍽️ Еда", callback_data="data_type_food")],
        [InlineKeyboardButton("🎬 Фильмы/Сериалы", callback_data="data_type_movies")],
        [InlineKeyboardButton("📚 Книги", callback_data="data_type_books")],
        [InlineKeyboardButton("📝 Общие данные", callback_data="data_type_general")],
        [InlineKeyboardButton("◀️ Назад", callback_data="topic_settings_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_auto_delete_delay_keyboard():
    """Create auto-delete delay selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("⚡ 30 секунд", callback_data="delay_30")],
        [InlineKeyboardButton("🕐 1 минута", callback_data="delay_60")],
        [InlineKeyboardButton("🕐 2 минуты", callback_data="delay_120")],
        [InlineKeyboardButton("🕐 5 минут", callback_data="delay_300")],
        [InlineKeyboardButton("🕐 10 минут", callback_data="delay_600")],
        [InlineKeyboardButton("♾️ Не удалять", callback_data="delay_0")],
        [InlineKeyboardButton("◀️ Назад", callback_data="topic_settings_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard():
    """Create main admin panel keyboard (only for admin in private chat)"""
    keyboard = [
        [InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton("🏢 Управление группами", callback_data="admin_groups")],
        [InlineKeyboardButton("📊 Экспорт данных", callback_data="admin_export")],
        [InlineKeyboardButton("⚙️ Системные настройки", callback_data="admin_system")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_users_keyboard():
    """Create admin users management keyboard"""
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_list_users")],
        [InlineKeyboardButton("➕ Добавить пользователя", callback_data="admin_add_user")],
        [InlineKeyboardButton("❌ Удалить пользователя", callback_data="admin_remove_user")],
        [InlineKeyboardButton("💬 Настройки промптов", callback_data="admin_user_prompts")],
        [InlineKeyboardButton("◀️ Админ панель", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_groups_keyboard():
    """Create admin groups management keyboard"""
    keyboard = [
        [InlineKeyboardButton("📋 Список групп", callback_data="admin_list_groups")],
        [InlineKeyboardButton("⚙️ Настройки групп", callback_data="admin_group_settings")],
        [InlineKeyboardButton("🚫 Заблокировать группу", callback_data="admin_block_group")],
        [InlineKeyboardButton("◀️ Админ панель", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_export_keyboard():
    """Create admin export management keyboard"""
    keyboard = [
        [InlineKeyboardButton("🍽️ Экспорт данных о еде", callback_data="export_food_data")],
        [InlineKeyboardButton("👤 Экспорт пользователей", callback_data="export_user_data")],
        [InlineKeyboardButton("📋 Экспорт по топикам", callback_data="export_topic_data")],
        [InlineKeyboardButton("🎬 Экспорт фильмов", callback_data="export_movies_data")],
        [InlineKeyboardButton("◀️ Админ панель", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_system_keyboard():
    """Create admin system settings keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔧 Настройки бота", callback_data="system_bot_settings")],
        [InlineKeyboardButton("📊 Системная статистика", callback_data="system_stats")],
        [InlineKeyboardButton("🔄 Перезапуск сервисов", callback_data="system_restart")],
        [InlineKeyboardButton("🗃️ Очистка логов", callback_data="system_clear_logs")],
        [InlineKeyboardButton("🌐 Настройки webhook", callback_data="system_webhook")],
        [InlineKeyboardButton("◀️ Админ панель", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_admin_groups_list_keyboard():
    """Create keyboard with list of groups where bot is present"""
    keyboard = []
    
    try:
        # Get unique group chats from topic settings
        groups = await app.mongodb.topic_settings.distinct("chat_id")
        
        for chat_id in groups[:10]:  # Limit to 10 groups
            try:
                # Try to get group info
                chat_info = await bot.get_chat(chat_id)
                group_name = chat_info.title or f"Group {chat_id}"
                keyboard.append([InlineKeyboardButton(f"🏢 {group_name}", callback_data=f"admin_group_{chat_id}")])
            except:
                # If can't get info, show ID only
                keyboard.append([InlineKeyboardButton(f"🏢 Group ID: {chat_id}", callback_data=f"admin_group_{chat_id}")])
                
    except Exception as e:
        logger.error(f"Error getting groups list: {str(e)}")
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_groups")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_groups_keyboard():
    """Create admin groups management keyboard"""
    keyboard = [
        [InlineKeyboardButton("📋 Список групп", callback_data="admin_list_groups")],
        [InlineKeyboardButton("⚙️ Настройки групп", callback_data="admin_group_settings")],
        [InlineKeyboardButton("🚫 Заблокировать группу", callback_data="admin_block_group")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_movies_keyboard():
    """Create movies keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить фильм/сериал", callback_data="add_movie")],
        [InlineKeyboardButton("🎬 Получить рекомендации", callback_data="get_recommendations")],
        [InlineKeyboardButton("📋 Мой список", callback_data="my_movies")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_fitness_goal_keyboard():
    """Create fitness goal keyboard"""
    keyboard = [
        [InlineKeyboardButton("🏃 Похудение", callback_data="goal_weight_loss")],
        [InlineKeyboardButton("💪 Набор массы", callback_data="goal_muscle_gain")],
        [InlineKeyboardButton("🔄 Поддержание формы", callback_data="goal_maintenance")],
        [InlineKeyboardButton("🏋️ Силовые тренировки", callback_data="goal_strength")],
        [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Database helper functions
async def save_user_info(user_id: int, user):
    """Save user information to database"""
    await app.mongodb.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_seen": datetime.utcnow()
            }
        },
        upsert=True
    )

async def save_user_setting(user_id: int, setting: str, value):
    """Save user setting"""
    await app.mongodb.users.update_one(
        {"user_id": user_id},
        {"$set": {f"settings.{setting}": value}},
        upsert=True
    )

async def get_user_data(user_id: int) -> dict:
    """Get user data from database"""
    user = await app.mongodb.users.find_one({"user_id": user_id})
    return user or {}

async def save_food_analysis(user_id: int, chat_id: int, username: str, analysis: dict, photo_file_id: str):
    """Save food analysis to database"""
    try:
        food_entry = {
            "id": str(uuid.uuid4()),
            "unique_number": analysis["unique_number"],
            "user_id": user_id,
            "chat_id": chat_id,
            "username": username,
            "dish_name": analysis["dish_name"],
            "calories": analysis["calories"],
            "proteins": analysis["proteins"],
            "fats": analysis["fats"],
            "carbs": analysis["carbs"],
            "description": analysis["description"],
            "photo_file_id": photo_file_id,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "timestamp": datetime.utcnow()
        }
        
        logger.info(f"Saving food entry to database: {food_entry['dish_name']} for user {user_id}")
        result = await app.mongodb.food_analysis.insert_one(food_entry)
        logger.info(f"Food entry saved successfully with ID: {result.inserted_id}")
        
    except Exception as e:
        logger.error(f"Error saving food analysis: {str(e)}")
        raise

async def save_movie(user_id: int, movie_data: dict):
    """Save movie with rating and metadata to user's list"""
    movie_entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": movie_data.get("title", ""),
        "year": movie_data.get("year"),
        "genre": movie_data.get("genre", ""),
        "rating": movie_data.get("rating"),  # User's personal rating 1-10
        "status": movie_data.get("status", "watched"),  # watched, want_to_watch, watching
        "review": movie_data.get("review", ""),
        "tmdb_id": movie_data.get("tmdb_id"),
        "poster_url": movie_data.get("poster_url", ""),
        "date_added": datetime.utcnow().strftime("%Y-%m-%d"),
        "timestamp": datetime.utcnow()
    }
    result = await app.mongodb.movies.insert_one(movie_entry)
    logger.info(f"Movie saved: {movie_data.get('title')} with rating {movie_data.get('rating')} for user {user_id}")
    return str(result.inserted_id)

async def get_user_movies(user_id: int, limit: int = 50) -> List[dict]:
    """Get user's detailed movie list with ratings"""
    movies = await app.mongodb.movies.find({"user_id": user_id}).sort("timestamp", -1).limit(limit).to_list(limit)
    return movies

async def get_movie_recommendations_data(user_id: int) -> dict:
    """Get user's movie data for generating recommendations"""
    user_movies = await get_user_movies(user_id, 100)
    
    if not user_movies:
        return {"message": "Добавьте фильмы в свой список для получения рекомендаций"}
    
    # Analyze user preferences
    genres = {}
    high_rated = []
    total_rating = 0
    rated_count = 0
    
    for movie in user_movies:
        # Count genres
        if movie.get("genre"):
            genre = movie["genre"]
            genres[genre] = genres.get(genre, 0) + 1
        
        # Track high-rated movies
        rating = movie.get("rating")
        if rating and rating >= 7:
            high_rated.append(movie["title"])
        
        if rating:
            total_rating += rating
            rated_count += 1
    
    avg_rating = round(total_rating / rated_count, 1) if rated_count > 0 else 0
    favorite_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        "total_movies": len(user_movies),
        "average_rating": avg_rating,
        "favorite_genres": [genre for genre, count in favorite_genres],
        "high_rated_movies": high_rated[:10],
        "recent_movies": [movie["title"] for movie in user_movies[:5]]
    }

async def save_health_data(user_id: int, data_type: str, value: str):
    """Save health data for user"""
    health_entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "data_type": data_type,
        "value": value,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "timestamp": datetime.utcnow()
    }
    await app.mongodb.health_data.insert_one(health_entry)
    
    # Also update current settings
    await save_user_setting(user_id, data_type, value)

# User state management for multi-step dialogs
user_states = {}

# Group topic settings for specific analysis
async def get_topic_settings(chat_id: int, topic_id: int = None) -> dict:
    """Get topic settings for a specific chat and topic"""
    try:
        key = f"{chat_id}_{topic_id}" if topic_id else str(chat_id)
        
        # Try to get from memory first
        if key in group_topic_settings:
            return group_topic_settings[key]
        
        # Try to get from database
        settings = await app.mongodb.topic_settings.find_one({"chat_id": chat_id, "topic_id": topic_id})
        if settings:
            group_topic_settings[key] = settings
            return settings
        
        # Default settings
        default_settings = {
            "chat_id": chat_id,
            "topic_id": topic_id,
            "food_analysis_enabled": True,  # By default, analyze food in all topics
            "food_only": False,  # If True, only analyze food, ignore other analysis
            "auto_analysis": True,  # Automatic analysis without @mention
            "auto_delete_delay": 300,  # Auto-delete messages after 5 minutes (300 seconds)
            "custom_prompt": "Ты полезный AI-ассистент для группового чата. Отвечай кратко и по существу на русском языке.",
            "data_type": "general",  # "food", "movies", "books", "general"
            "auto_extract_data": True,  # Automatically extract structured data
            "topic_name": None
        }
        
        group_topic_settings[key] = default_settings
        return default_settings
        
    except Exception as e:
        logger.error(f"Error getting topic settings: {str(e)}")
        return {"food_analysis_enabled": True, "food_only": False, "auto_analysis": True}

async def save_topic_settings(chat_id: int, topic_id: int, settings: dict):
    """Save topic settings to database and memory"""
    try:
        key = f"{chat_id}_{topic_id}" if topic_id else str(chat_id)
        
        # Update memory
        group_topic_settings[key] = settings
        
        # Update database
        await app.mongodb.topic_settings.update_one(
            {"chat_id": chat_id, "topic_id": topic_id},
            {"$set": settings},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Error saving topic settings: {str(e)}")

async def is_food_analysis_allowed_in_topic(chat_id: int, topic_id: int = None) -> bool:
    """Check if food analysis is allowed in this topic"""
    settings = await get_topic_settings(chat_id, topic_id)
    return settings.get("food_analysis_enabled", True)

async def get_auto_delete_delay(chat_id: int, topic_id: int = None) -> int:
    """Get auto-delete delay for messages in this topic (in seconds)"""
    settings = await get_topic_settings(chat_id, topic_id)
    return settings.get("auto_delete_delay", 300)  # Default 5 minutes
# User conversation context for continuous dialogs
user_conversations = {}

# Topic conversation context management
topic_conversations = {}

async def add_message_to_topic_conversation(chat_id: int, topic_id: int, role: str, content: str, user_id: int = None):
    """Add message to topic's conversation history"""
    try:
        key = f"{chat_id}_{topic_id}"
        if key not in topic_conversations:
            topic_conversations[key] = []
        
        message_data = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "user_id": user_id
        }
        
        topic_conversations[key].append(message_data)
        
        # Check if we need to summarize (50+ messages)
        if len(topic_conversations[key]) >= 50:
            await summarize_topic_conversation(chat_id, topic_id)
        
        logger.info(f"Added message to topic {topic_id} in chat {chat_id}. Total messages: {len(topic_conversations[key])}")
        
    except Exception as e:
        logger.error(f"Error adding message to topic conversation: {str(e)}")

async def get_topic_conversation(chat_id: int, topic_id: int) -> list:
    """Get topic's conversation history"""
    key = f"{chat_id}_{topic_id}"
    return topic_conversations.get(key, [])

async def clear_topic_conversation(chat_id: int, topic_id: int):
    """Clear topic's conversation history"""
    key = f"{chat_id}_{topic_id}"
    if key in topic_conversations:
        del topic_conversations[key]
    logger.info(f"Cleared conversation for topic {topic_id} in chat {chat_id}")

async def summarize_topic_conversation(chat_id: int, topic_id: int):
    """Summarize topic conversation when it reaches 50 messages"""
    try:
        key = f"{chat_id}_{topic_id}"
        if key not in topic_conversations or len(topic_conversations[key]) < 50:
            return
            
        messages = topic_conversations[key]
        
        # Get topic settings to use custom prompt
        topic_settings = await get_topic_settings(chat_id, topic_id)
        topic_prompt = topic_settings.get("custom_prompt", "Ты полезный AI-ассистент для группового чата.")
        
        # Build conversation text for summarization
        conversation_text = ""
        for msg in messages:
            if msg["role"] == "user":
                user_info = f"Пользователь {msg.get('user_id', 'unknown')}"
                conversation_text += f"{user_info}: {msg['content']}\n"
            elif msg["role"] == "assistant":
                conversation_text += f"Бот: {msg['content']}\n"
        
        # Create summary prompt
        summary_prompt = f"""
Контекст топика: {topic_prompt}

Проанализируй следующую беседу из группового чата и создай краткое резюме (не более 500 слов), которое:
1. Сохранит основные темы и выводы обсуждения
2. Укажет ключевые решения или договоренности
3. Отметит важную информацию для продолжения диалога
4. Учтет специфику топика

Беседа:
{conversation_text}

Создай резюме на русском языке, которое поможет продолжить обсуждение в том же контексте.
        """
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по суммаризации групповых бесед. Создаешь краткие, но информативные резюме для продолжения контекста."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=600
            )
            
            summary = response.choices[0].message.content
            
            # Replace conversation with summary
            topic_conversations[key] = [
                {
                    "role": "system",
                    "content": f"Резюме предыдущей беседы: {summary}",
                    "timestamp": datetime.utcnow(),
                    "user_id": None,
                    "is_summary": True
                }
            ]
            
            # Save summary to database for persistence
            await app.mongodb.topic_summaries.insert_one({
                "chat_id": chat_id,
                "topic_id": topic_id,
                "summary": summary,
                "created_at": datetime.utcnow(),
                "messages_count": len(messages)
            })
            
            logger.info(f"Created summary for topic {topic_id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error creating summary with OpenAI: {str(e)}")
            # Fallback: keep only last 10 messages
            topic_conversations[key] = messages[-10:]
            
    except Exception as e:
        logger.error(f"Error in summarize_topic_conversation: {str(e)}")

async def load_topic_conversation_from_db(chat_id: int, topic_id: int):
    """Load topic conversation history from database if exists"""
    try:
        # Get latest summary
        latest_summary = await app.mongodb.topic_summaries.find_one(
            {"chat_id": chat_id, "topic_id": topic_id},
            sort=[("created_at", -1)]
        )
        
        if latest_summary:
            key = f"{chat_id}_{topic_id}"
            topic_conversations[key] = [
                {
                    "role": "system",
                    "content": f"Резюме предыдущей беседы: {latest_summary['summary']}",
                    "timestamp": latest_summary["created_at"],
                    "user_id": None,
                    "is_summary": True
                }
            ]
            logger.info(f"Loaded conversation summary for topic {topic_id} in chat {chat_id}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error loading topic conversation from DB: {str(e)}")
        return False

async def handle_topic_message_with_context(message_text: str, user_id: int, chat_id: int, topic_id: int) -> str:
    """Handle message in topic with context awareness"""
    try:
        # Load conversation history if not in memory
        key = f"{chat_id}_{topic_id}"
        if key not in topic_conversations:
            await load_topic_conversation_from_db(chat_id, topic_id)
        
        # Add user message to context
        await add_message_to_topic_conversation(chat_id, topic_id, "user", message_text, user_id)
        
        # Get topic settings
        topic_settings = await get_topic_settings(chat_id, topic_id)
        system_prompt = topic_settings.get("custom_prompt", "Ты полезный AI-ассистент для группового чата. Отвечай кратко и по существу на русском языке.")
        
        # Build conversation for AI
        conversation_history = await get_topic_conversation(chat_id, topic_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in conversation_history:
            if msg.get("is_summary"):
                messages.append({"role": "system", "content": msg["content"]})
            else:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Get AI response
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content
        
        # Add AI response to context
        await add_message_to_topic_conversation(chat_id, topic_id, "assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error handling topic message with context: {str(e)}")
        return f"❌ Ошибка обработки сообщения в контексте топика: {str(e)}"

# Topic data management system
async def save_topic_data(chat_id: int, topic_id: int, data_type: str, data: dict, user_id: int):
    """Save data to topic-specific database"""
    try:
        entry = {
            "chat_id": chat_id,
            "topic_id": topic_id,
            "data_type": data_type,  # 'food', 'movies', 'books', 'general', etc.
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "data": data
        }
        
        result = await app.mongodb.topic_data.insert_one(entry)
        logger.info(f"Saved {data_type} data to topic {topic_id} in chat {chat_id}")
        return str(result.inserted_id)
        
    except Exception as e:
        logger.error(f"Error saving topic data: {str(e)}")
        return None

async def get_topic_data(chat_id: int, topic_id: int, data_type: str = None, limit: int = 50) -> list:
    """Get data from topic-specific database"""
    try:
        query = {"chat_id": chat_id, "topic_id": topic_id}
        if data_type:
            query["data_type"] = data_type
            
        cursor = app.mongodb.topic_data.find(query).sort("timestamp", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting topic data: {str(e)}")
        return []

async def extract_movie_data(message_text: str, chat_id: int, topic_id: int, user_id: int) -> bool:
    """Extract movie/series data from message"""
    try:
        extraction_prompt = f"""
Проанализируй сообщение и извлеки информацию о фильмах/сериалах.

Сообщение: "{message_text}"

Если есть фильмы/сериалы, верни JSON:
{{"has_content": true, "items": [{{"title": "название", "status": "liked/disliked/watched", "comment": "комментарий"}}]}}

Если нет: {{"has_content": false}}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Извлекай информацию о фильмах/сериалах. Отвечай только JSON."},
                {"role": "user", "content": extraction_prompt}
            ],
            max_tokens=300
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        if result.get("has_content", False):
            for item in result.get("items", []):
                await save_topic_data(chat_id, topic_id, "movies", item, user_id)
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error extracting movie data: {str(e)}")
        return False

def set_user_state(user_id: int, state: str):
    """Set user state for multi-step dialogs"""
    user_states[user_id] = state

def get_user_state(user_id: int) -> str:
    """Get user state"""
    return user_states.get(user_id, "")

def clear_user_state(user_id: int):
    """Clear user state"""
    if user_id in user_states:
        del user_states[user_id]

def add_message_to_conversation(user_id: int, role: str, content: str):
    """Add message to user's conversation history"""
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    
    user_conversations[user_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow()
    })
    
    # Keep only last 10 messages to avoid token limit
    if len(user_conversations[user_id]) > 10:
        user_conversations[user_id] = user_conversations[user_id][-10:]

def get_user_conversation(user_id: int) -> list:
    """Get user's conversation history"""
    return user_conversations.get(user_id, [])

def clear_user_conversation(user_id: int):
    """Clear user's conversation history"""
    if user_id in user_conversations:
        del user_conversations[user_id]

async def get_enhanced_food_stats(user_id: int, period: str, target_user_id: int = None) -> dict:
    """Get enhanced food statistics with detailed formatting"""
    try:
        # If no target user specified, use requester
        if target_user_id is None:
            target_user_id = user_id
            
        # Check if requester has access to view target user's stats
        requester_role = await get_user_role(user_id)
        if target_user_id != user_id and requester_role != "admin":
            return {"error": "Нет доступа к данным этого пользователя"}
            
        # Get target username
        target_username = "Неизвестно"
        if target_user_id in user_access_list:
            target_username = user_access_list[target_user_id]["username"]
            
        now = datetime.utcnow()
        
        if period == "yesterday":
            yesterday = now - timedelta(days=1)
            date_filter = {"date": yesterday.strftime("%Y-%m-%d")}
            period_name = "вчера"
        elif period == "week":
            week_ago = now - timedelta(days=7)
            date_filter = {"timestamp": {"$gte": week_ago}}
            period_name = "за неделю"
        elif period == "month":
            month_ago = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_filter = {"timestamp": {"$gte": month_ago}}
            period_name = "за месяц"
        else:
            # today
            date_filter = {"date": now.strftime("%Y-%m-%d")}
            period_name = "сегодня"
        
        # Get food data
        pipeline = [
            {"$match": {"user_id": target_user_id, **date_filter}},
            {"$group": {
                "_id": None,
                "total_meals": {"$sum": 1},
                "total_calories": {"$sum": "$calories"},
                "total_proteins": {"$sum": "$proteins"},
                "total_fats": {"$sum": "$fats"},
                "total_carbs": {"$sum": "$carbs"},
                "dishes": {"$push": {
                    "dish_name": "$dish_name",
                    "calories": "$calories",
                    "proteins": "$proteins", 
                    "fats": "$fats",
                    "carbs": "$carbs",
                    "timestamp": "$timestamp"
                }}
            }}
        ]
        
        result = await app.mongodb.food_analysis.aggregate(pipeline).to_list(1)
        
        if not result:
            return {
                "username": target_username,
                "period": period_name,
                "total_meals": 0,
                "total_calories": 0,
                "total_proteins": 0,
                "total_fats": 0,
                "total_carbs": 0,
                "dishes": [],
                "averages": {}
            }
            
        data = result[0]
        
        # Calculate averages
        days_count = 7 if period == "week" else (30 if period == "month" else 1)
        if period in ["week", "month"]:
            avg_calories = data["total_calories"] / days_count
            avg_proteins = data["total_proteins"] / days_count
            avg_fats = data["total_fats"] / days_count
            avg_carbs = data["total_carbs"] / days_count
            avg_meals = data["total_meals"] / days_count
        else:
            avg_calories = data["total_calories"] 
            avg_proteins = data["total_proteins"]
            avg_fats = data["total_fats"]
            avg_carbs = data["total_carbs"]
            avg_meals = data["total_meals"]
            
        return {
            "username": target_username,
            "period": period_name,
            "total_meals": data["total_meals"],
            "total_calories": data["total_calories"],
            "total_proteins": data["total_proteins"],
            "total_fats": data["total_fats"],
            "total_carbs": data["total_carbs"],
            "dishes": data["dishes"],
            "averages": {
                "avg_calories": avg_calories,
                "avg_proteins": avg_proteins, 
                "avg_fats": avg_fats,
                "avg_carbs": avg_carbs,
                "avg_meals": avg_meals,
                "days_count": days_count
            }
        }
        
    except Exception as e:
        logger.error(f"Enhanced food stats error: {str(e)}")
        return {"error": f"Ошибка получения статистики: {str(e)}"}

async def get_food_stats(user_id: int, period: str) -> dict:
    """Get food statistics for user"""
    result = await get_enhanced_food_stats(user_id, period)
    if "error" in result:
        return {"total_meals": 0, "total_calories": 0, "total_proteins": 0, "total_fats": 0, "total_carbs": 0}
    return {
        "total_meals": result["total_meals"],
        "total_calories": result["total_calories"],
        "total_proteins": result["total_proteins"],
        "total_fats": result["total_fats"],
        "total_carbs": result["total_carbs"]
    }

# Natural language processing for bot commands
async def process_natural_language_query(message_text: str, user_id: int, chat_id: int, topic_id: int = None) -> dict:
    """Process natural language queries and extract intent and parameters"""
    try:
        text_lower = message_text.lower()
        
        # Remove bot mention
        text_lower = text_lower.replace("@dmplove_bot", "").strip()
        
        # Extract mentioned users
        mentioned_users = []
        import re
        user_mentions = re.findall(r'@(\w+)', message_text)
        for mention in user_mentions:
            for uid, user_data in user_access_list.items():
                if user_data["username"].lower() == mention.lower():
                    mentioned_users.append({"user_id": uid, "username": user_data["username"]})
                    break
        
        # Determine intent and extract parameters
        intent = None
        parameters = {}
        
        # Statistics queries
        if any(word in text_lower for word in ["статистик", "статистика", "стат", "показ", "данные", "результат"]):
            intent = "statistics"
            
            # Extract period
            if any(word in text_lower for word in ["сегодня", "today"]):
                parameters["period"] = "today"
            elif any(word in text_lower for word in ["вчера", "yesterday"]):
                parameters["period"] = "yesterday"
            elif any(word in text_lower for word in ["неделя", "неделю", "week"]):
                parameters["period"] = "week"
            elif any(word in text_lower for word in ["месяц", "month"]):
                parameters["period"] = "month"
            else:
                parameters["period"] = "week"  # Default
                
            # Extract target user
            if mentioned_users:
                parameters["target_user"] = mentioned_users[0]
            else:
                parameters["target_user"] = {"user_id": user_id, "username": user_access_list.get(user_id, {}).get("username", "Неизвестно")}
                
        # Food analysis queries  
        elif any(word in text_lower for word in ["еда", "питание", "калории", "бжу", "блюд"]):
            if any(word in text_lower for word in ["найди", "поиск", "найти", "искать"]):
                intent = "food_search"
                # Extract search terms
                search_terms = []
                for word in text_lower.split():
                    if word not in ["найди", "поиск", "найти", "искать", "еду", "блюдо", "за", "в", "для"]:
                        search_terms.append(word)
                parameters["query"] = " ".join(search_terms)
            else:
                intent = "food_analysis_info"
                
        # Fitness advice queries
        elif any(word in text_lower for word in ["похуд", "фитнес", "тренировк", "здоровье", "вес", "цель"]):
            intent = "fitness_advice"
            if mentioned_users:
                parameters["target_user"] = mentioned_users[0]
            else:
                parameters["target_user"] = {"user_id": user_id, "username": user_access_list.get(user_id, {}).get("username", "Неизвестно")}
                
            # Extract goals from text
            parameters["context"] = message_text
            
        # General chat
        else:
            intent = "general_chat"
            parameters["message"] = text_lower
            
        return {
            "intent": intent,
            "parameters": parameters,
            "confidence": 0.8,  # Simple confidence score
            "original_text": message_text
        }
        
    except Exception as e:
        logger.error(f"Natural language processing error: {str(e)}")
        return {
            "intent": "unknown",
            "parameters": {},
            "confidence": 0.0,
            "error": str(e)
        }

async def handle_natural_language_query(query_result: dict, user_id: int, chat_id: int, topic_id: int = None):
    """Handle processed natural language query"""
    try:
        intent = query_result["intent"]
        params = query_result["parameters"]
        
        if intent == "statistics":
            # Handle statistics request
            target_user_id = params["target_user"]["user_id"]
            period = params["period"]
            
            stats = await get_enhanced_food_stats(user_id, period, target_user_id)
            
            if "error" in stats:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {stats['error']}",
                    message_thread_id=topic_id
                )
                return
                
            # Format response
            stats_text = f"""
📊 Статистика питания {stats['period']} для @{stats['username']}

📈 **Суммарные показатели:**
🍽️ Приемов пищи: {stats['total_meals']}
🔥 Калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']:.1f} г
🧈 Жиры: {stats['total_fats']:.1f} г  
🍞 Углеводы: {stats['total_carbs']:.1f} г

📊 **Средние значения в день:**
🔥 Калории: {stats['averages']['avg_calories']:.0f} ккал
🥩 Белки: {stats['averages']['avg_proteins']:.1f} г
🧈 Жиры: {stats['averages']['avg_fats']:.1f} г
🍞 Углеводы: {stats['averages']['avg_carbs']:.1f} г
🍽️ Приемов пищи: {stats['averages']['avg_meals']:.1f}
            """
            
            await bot.send_message(
                chat_id=chat_id,
                text=stats_text,
                parse_mode="Markdown",
                message_thread_id=topic_id
            )
            
        elif intent == "food_search":
            # Handle food search
            query = params.get("query", "")
            await handle_database_search(chat_id, user_id, query, topic_id)
            
        elif intent == "fitness_advice":
            # Handle fitness advice request
            target_user_id = params["target_user"]["user_id"]
            context = params.get("context", "")
            
            # Get user's health data and recent food stats
            health_data = await get_user_data(target_user_id)
            recent_stats = await get_enhanced_food_stats(user_id, "week", target_user_id)
            
            # Build fitness advice prompt
            fitness_prompt = f"""
Как фитнес-консультант, проанализируй данные пользователя @{params['target_user']['username']} и дай персональный совет.

Запрос пользователя: {context}

Данные пользователя:
- Рост: {health_data.get('height', 'не указан')} см
- Вес: {health_data.get('weight', 'не указан')} кг
- Возраст: {health_data.get('age', 'не указан')} лет

Питание за последнюю неделю:
- Средние калории в день: {recent_stats.get('averages', {}).get('avg_calories', 0):.0f} ккал
- Средние белки: {recent_stats.get('averages', {}).get('avg_proteins', 0):.1f} г
- Средние жиры: {recent_stats.get('averages', {}).get('avg_fats', 0):.1f} г
- Средние углеводы: {recent_stats.get('averages', {}).get('avg_carbs', 0):.1f} г

Дай персональные рекомендации на русском языке, учитывая цели и текущее питание.
            """
            
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Ты опытный фитнес-консультант и диетолог. Даешь персональные рекомендации по питанию и тренировкам."},
                        {"role": "user", "content": fitness_prompt}
                    ],
                    max_tokens=800
                )
                
                advice = response.choices[0].message.content
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🏋️‍♀️ **Персональный совет для @{params['target_user']['username']}:**\n\n{advice}",
                    parse_mode="Markdown",
                    message_thread_id=topic_id
                )
                
            except Exception as e:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка при получении фитнес-совета. Попробуйте позже.",
                    message_thread_id=topic_id
                )
                
        elif intent == "general_chat":
            # Handle general chat with enhanced reliability
            response = await enhanced_free_chat_ai(params["message"], user_id, chat_id, topic_id)
            await bot.send_message(
                chat_id=chat_id,
                text=response,
                message_thread_id=topic_id
            )
            
        else:
            # Unknown intent - ask for clarification
            clarification_text = """
🤔 Я не совсем понял ваш запрос. Возможно, вы имели в виду:

📊 **Статистика:** "дай статистику питания за неделю"
🔍 **Поиск еды:** "найди все блюда с курицей"  
🏋️ **Фитнес-совет:** "подходит ли мое питание для похудения"
💬 **Общение:** просто задайте любой вопрос

Попробуйте переформулировать запрос или используйте команды /help для просмотра всех возможностей.
            """
            
            await bot.send_message(
                chat_id=chat_id,
                text=clarification_text,
                parse_mode="Markdown",
                message_thread_id=topic_id
            )
            
    except Exception as e:
        logger.error(f"Natural language query handling error: {str(e)}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.",
            message_thread_id=topic_id
        )

# Enhanced user data with history tracking
async def save_user_health_data_with_history(user_id: int, data_type: str, value: any, unit: str = None):
    """Save user health data with timestamp for history tracking"""
    try:
        # Create history entry
        history_entry = {
            "user_id": user_id,
            "data_type": data_type,  # height, weight, age, steps, workout
            "value": value,
            "unit": unit,
            "timestamp": datetime.utcnow(),
            "date": datetime.utcnow().strftime("%Y-%m-%d")
        }
        
        # Save to history collection
        await app.mongodb.user_health_history.insert_one(history_entry)
        
        # Update current value in main health data
        await app.mongodb.health_data.update_one(
            {"user_id": user_id},
            {"$set": {
                data_type: value,
                f"{data_type}_unit": unit,
                f"{data_type}_updated": datetime.utcnow()
            }},
            upsert=True
        )
        
        # Also update user settings
        await save_user_setting(user_id, data_type, value)
        
        logger.info(f"Saved health data for user {user_id}: {data_type} = {value} {unit}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving user health data with history: {str(e)}")
        return False

async def get_user_health_history(user_id: int, data_type: str = None, days: int = 30) -> list:
    """Get user health data history"""
    try:
        # Build query
        query = {"user_id": user_id}
        if data_type:
            query["data_type"] = data_type
            
        # Get data from last N days
        start_date = datetime.utcnow() - timedelta(days=days)
        query["timestamp"] = {"$gte": start_date}
        
        # Get results sorted by timestamp
        cursor = app.mongodb.user_health_history.find(query).sort("timestamp", -1)
        results = await cursor.to_list(length=100)  # Limit to 100 entries
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting user health history: {str(e)}")
        return []

async def save_workout_data(user_id: int, workout_type: str, duration: int, frequency_per_week: int, notes: str = ""):
    """Save workout data with details"""
    try:
        workout_data = {
            "type": workout_type,
            "duration_minutes": duration,
            "frequency_per_week": frequency_per_week,
            "notes": notes
        }
        
        return await save_user_health_data_with_history(user_id, "workout", workout_data, "session")
        
    except Exception as e:
        logger.error(f"Error saving workout data: {str(e)}")
        return False

async def save_steps_data(user_id: int, daily_steps: int):
    """Save daily steps data"""
    try:
        return await save_user_health_data_with_history(user_id, "steps", daily_steps, "steps/day")
        
    except Exception as e:
        logger.error(f"Error saving steps data: {str(e)}")
        return False

# Message handlers
async def handle_message(message):
    """Handle incoming messages and commands"""
    chat_id = message.chat_id
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    is_group = message.chat.type in ['group', 'supergroup']
    
    # Check user access (only for private chats and mentions in groups)
    if not is_group:
        # Private chat - check if user is allowed
        if not await is_user_allowed(user_id):
            logger.info(f"Access denied for user {username} (ID: {user_id})")
            return  # Silently ignore
    else:
        # Group chat - check if bot is mentioned or it's a command
        bot_username = "DMPlove_bot"
        if message.text and not (message.text.startswith('/') or f"@{bot_username}" in message.text):
            # Not a command and bot not mentioned - check if this is from allowed user
            if not await is_user_allowed(user_id):
                return  # Silently ignore
    
    # Save user info to database
    await save_user_info(user_id, message.from_user)
    
    # Handle different types of content
    if message.photo:
        await handle_photo_message(message)
        return
    elif message.document:
        await handle_document_message(message)
        return
    elif message.video:
        await handle_video_message(message)
        return
    elif message.voice:
        await handle_voice_message(message)
        return
    elif message.video_note:
        await handle_video_note_message(message)
        return
    elif message.sticker:
        await handle_sticker_message(message)
        return
    
    # Check if message has text
    text = message.text
    if not text:
        return  # Skip messages without text
    
    # Handle multi-step dialogs based on user state (BEFORE group check)
    user_state = get_user_state(user_id)
    
    if user_state.startswith("setting_topic_prompt_"):
        # Handle topic prompt input
        parts = user_state.split("_")
        if len(parts) >= 5:
            target_chat_id = int(parts[3])
            target_topic_id = int(parts[4])
            
            # Save the new prompt
            current_settings = await get_topic_settings(target_chat_id, target_topic_id)
            current_settings["custom_prompt"] = text
            await save_topic_settings(target_chat_id, target_topic_id, current_settings)
            
            clear_user_state(user_id)
            
            # Enhanced confirmation message
            confirmation_text = f"""✅ **Промпт для топика успешно обновлен!**

📝 **Новый промпт:**
{text}

📍 **Применяется к:** Топик {target_topic_id}
⚙️ **Статус:** Активен
🔄 **Обновлен:** {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}

Теперь ИИ будет использовать этот промпт для всех сообщений в данном топике."""
            
            await bot.send_message(
                chat_id=chat_id,
                text=confirmation_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Настройки топика", callback_data="topic_settings_menu")]]) if is_group else None,
                message_thread_id=target_topic_id if is_group else None
            )
        return
    
    # In group chats, only respond to commands or mentions
    if is_group:
        # Check if bot is mentioned or it's a command
        bot_username = "DMPlove_bot"
        text_lower = text.lower()
        is_mentioned = f"@{bot_username.lower()}" in text_lower or f"@{bot_username}" in text
        is_command = text.startswith('/')
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.is_bot
        
        # Also check for direct mention by ID
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention" and entity.user and entity.user.username == bot_username:
                    is_mentioned = True
                    break
        
        logger.info(f"Group message check: mentioned={is_mentioned}, command={is_command}, reply_to_bot={is_reply_to_bot}, text='{text[:50]}...'")
        
        if not (is_mentioned or is_command or is_reply_to_bot):
            return  # Don't respond to regular group messages
            
        # If it's a mention, clean the text from @mentions for processing
        if is_mentioned and not is_command:
            # Remove @bot_username from text for better processing
            clean_text = text.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").strip()
            if clean_text:
                text = clean_text
    else:
        # In private chats, also handle @mentions by cleaning them
        bot_username = "DMPlove_bot"
        if f"@{bot_username}" in text or f"@{bot_username.lower()}" in text.lower():
            # Remove @bot_username from text in private chats too
            clean_text = text.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").strip()
            if clean_text:
                text = clean_text
    
    user_state = get_user_state(user_id)
    
    # Handle multi-step dialogs based on user state
    if user_state == "waiting_movie":
        # Simple movie entry - just title for now
        movie_data = {"title": text}
        await save_movie(user_id, movie_data)
        clear_user_state(user_id)
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ Фильм/сериал '{text}' добавлен в ваш список!\n\n💡 Совет: Вы можете добавлять фильмы с оценками через AI чат, например: 'Я посмотрел фильм Inception, оценка 9/10'",
            reply_markup=get_movies_keyboard() if not is_group else None
        )
        return
    elif user_state == "waiting_height":
        try:
            height = int(text)
            await save_user_health_data_with_history(user_id, "height", height, "cm")
            clear_user_state(user_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Рост сохранен: {height} см",
                reply_markup=get_health_profile_keyboard()
            )
        except ValueError:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Введите корректный рост в сантиметрах (например: 175)"
            )
        return
    elif user_state == "waiting_weight":
        try:
            weight = float(text)
            await save_user_health_data_with_history(user_id, "weight", weight, "kg")
            clear_user_state(user_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Вес сохранен: {weight} кг",
                reply_markup=get_health_profile_keyboard()
            )
        except ValueError:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Введите корректный вес в килограммах (например: 70.5)"
            )
        return
    elif user_state == "waiting_age":
        try:
            age = int(text)
            await save_user_health_data_with_history(user_id, "age", age, "years")
            clear_user_state(user_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Возраст сохранен: {age} лет",
                reply_markup=get_health_profile_keyboard()
            )
        except ValueError:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Введите корректный возраст в годах (например: 25)"
            )
        return
    elif user_state == "waiting_steps":
        try:
            steps = int(text)
            await save_steps_data(user_id, steps)
            clear_user_state(user_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Шаги сохранены: {steps} шагов в день",
                reply_markup=get_health_profile_keyboard()
            )
        except ValueError:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Введите корректное количество шагов (например: 8000)"
            )
        return
    elif user_state == "waiting_workout":
        # Parse workout input: "теннис 60 4 тренировки в зале"
        try:
            text = text.strip()
            parts = text.split(' ', 3)  # Разделяем максимум на 4 части
            
            if len(parts) >= 3:
                workout_type = parts[0]
                
                # Проверяем что длительность и частота - числа
                try:
                    duration = int(parts[1])
                    frequency = int(parts[2])
                except ValueError:
                    raise ValueError("Длительность и частота должны быть числами")
                
                notes = parts[3] if len(parts) > 3 else ""
                
                await save_workout_data(user_id, workout_type, duration, frequency, notes)
                clear_user_state(user_id)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Тренировка сохранена:\n🏃 {workout_type}\n⏱️ {duration} мин\n📅 {frequency} раз/неделю\n📝 {notes}",
                    reply_markup=get_health_profile_keyboard()
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ **Неверный формат ввода**\n\n📝 **Правильный формат:**\n`тип длительность частота комментарий`\n\n📋 **Примеры:**\n• `теннис 60 4 игра в зале`\n• `бег 30 5`\n• `фитнес 45 3 силовая тренировка`\n\n⏹️ Для отмены нажмите кнопку ниже:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏹️ Отмена", callback_data="health_profile")]])
                )
        except ValueError as ve:
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Ошибка:** {str(ve)}\n\n📝 **Правильный формат:**\n`тип длительность частота комментарий`\n\n📋 **Пример:** `теннис 60 4 игра в зале`\n\n⏹️ Для отмены нажмите кнопку ниже:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏹️ Отмена", callback_data="health_profile")]])
            )
        except Exception as e:
            logger.error(f"Workout parsing error: {str(e)}")
            await bot.send_message(
                chat_id=chat_id,
                text="❌ **Произошла ошибка при сохранении тренировки**\n\nПопробуйте еще раз или обратитесь к администратору.\n\n⏹️ Для отмены нажмите кнопку ниже:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏹️ Отмена", callback_data="health_profile")]])
            )
        return
    
    # Handle natural language commands (especially after @mention cleanup)
    text_lower = text.lower()
    if any(word in text_lower for word in ["статистик", "статистика", "stats"]):
        # Treat as /stats command - show keyboard in both private and group chats
        await bot.send_message(
            chat_id=chat_id,
            text="📊 Статистика питания:",
            reply_markup=get_stats_keyboard(),  # Always show keyboard
            message_thread_id=getattr(message, 'message_thread_id', None)
        )
        return
    elif any(word in text_lower for word in ["поиск", "найди", "search"]) and any(word in text_lower for word in ["еда", "еду", "блюдо", "питание"]):
        # Extract search query
        search_words = text_lower.split()
        search_query = " ".join([word for word in search_words if word not in ["поиск", "найди", "search", "@dmplove_bot"]])
        if search_query:
            await handle_database_search(chat_id, user_id, search_query, getattr(message, 'message_thread_id', None))
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="🔍 Использование: найди [запрос]\n\nПримеры:\n• найди йогурт\n• поиск сегодня\n• найди яблоко за неделю",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
        return
    
    # Handle commands
    if text.startswith('/start'):
        if is_group:
            welcome_text = """
🤖 Добро пожаловать в семейного бота-помощника!

В группе я автоматически:
📸 Анализирую ВСЕ фотографии еды
💾 Сохраняю данные с привязкой к отправителю  
📊 Веду статистику для каждого участника
🎨 Создаю изображения по запросу
📄 Анализирую документы и файлы

Команды для группы:
/help - помощь
/stats - статистика питания
/image [описание] - создать изображение
@DMPlove_bot [вопрос] - общение с AI

💡 Просто отправляйте фото еды или файлы - я всё обработаю!
            """
            await bot.send_message(chat_id=chat_id, text=welcome_text)
        else:
            welcome_text = """🤖 Ваш AI-помощник готов к работе!

Превратите Telegram в персональное AI-приложение:

📸 Анализирую фото еды и считаю калории
💪 Даю персональные фитнес советы  
👤 Веду профиль здоровья
🤖 Общаюсь через ChatGPT с поиском
🎬 Рекомендую фильмы и сериалы
📊 Показываю статистику питания
🎨 Создаю изображения по описанию
📄 Анализирую любые файлы

Используйте кнопки как мобильное приложение! 📱"""
            
            await bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=get_main_menu_keyboard()
            )
            
            # Send quick actions as second message
            await bot.send_message(
                chat_id=chat_id,
                text="⚡ Или используйте быстрые действия:",
                reply_markup=get_quick_actions_keyboard()
            )
    elif text.startswith('/help'):
        help_text = f"""
📋 Доступные команды:
/start - Главное меню
/help - Помощь
/menu - Показать меню (только в приватном чате)
/stats - Статистика питания
/image [описание] - Создать изображение
/search [запрос] - Поиск в базе данных питания
/topic_settings - Настройки топика (только для админов в группах)
/my_id - Показать ваш Telegram ID

{f'''👑 Административные команды:
/admin - Административная панель
/add_user [@username] [role] - Добавить пользователя
/add_user_id [ID] [username] [role] - Добавить по ID
/list_users - Список пользователей
/remove_user [ID] - Удалить пользователя
''' if await get_user_role(user_id) == 'admin' else ''}
🔥 Основные функции:
• Отправьте фото еды для автоматического анализа
• Отправьте любой файл для анализа
• Используйте кнопки для навигации (в приватном чате)
• Создавайте изображения командой /image
• Общайтесь с AI с поиском в интернете

💡 В группе: Отправьте фото/файлы или упомяните @DMPlove_bot
💡 В топиках: Используйте /topic_settings для настройки анализа еды
        """
        await bot.send_message(chat_id=chat_id, text=help_text)
    elif text.startswith('/menu'):
        if is_group:
            await bot.send_message(
                chat_id=chat_id,
                text="📱 Меню доступно только в приватном чате с ботом. Напишите мне в личные сообщения!"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="🏠 Главное меню:",
                reply_markup=get_main_menu_keyboard()
            )
    elif text.startswith('/stats'):
        await bot.send_message(
            chat_id=chat_id,
            text="📊 Статистика питания:",
            reply_markup=get_stats_keyboard(),  # Always show keyboard in both private and group chats
            message_thread_id=getattr(message, 'message_thread_id', None)
        )
    elif text.startswith('/search '):
        # Database search command
        query = text.replace('/search ', '').strip()
        if query:
            await handle_database_search(chat_id, user_id, query, getattr(message, 'message_thread_id', None))
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="🔍 Использование: /search [запрос]\n\nПримеры:\n• /search йогурт\n• /search сегодня\n• /search неделя\n• /search яблоко месяц",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    elif text.startswith('/topic_settings'):
        # Topic settings command (only for groups and admins)
        if is_group:
            topic_id = getattr(message, 'message_thread_id', None)
            if topic_id:
                # Check if user is admin
                try:
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="⚙️ Настройки топика:",
                            reply_markup=get_topic_settings_keyboard(),
                            message_thread_id=topic_id
                        )
                    else:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="❌ Только администраторы могут изменять настройки топика.",
                            message_thread_id=topic_id
                        )
                except Exception as e:
                    logger.error(f"Error checking admin status: {str(e)}")
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Ошибка при проверке прав доступа.",
                        message_thread_id=topic_id
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="📋 Эта команда работает только в топиках (темах)."
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="📋 Эта команда работает только в групповых чатах с топиками."
            )
    elif text.startswith('/add_user ') and not is_group:
        # Add user command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            parts = text.split(' ', 2)
            if len(parts) >= 2:
                username = parts[1].replace('@', '')
                role = parts[2] if len(parts) > 2 else "user"
                
                # For now, ask admin to provide user ID (in future can lookup by username)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"💡 Для добавления пользователя @{username} с ролью '{role}'\n\nМне нужен Telegram ID пользователя.\n\nПопросите пользователя написать мне что-либо в личные сообщения, и я покажу его ID, либо найдите ID другим способом.\n\nЗатем используйте: /add_user_id [ID] [username] [role]"
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="📝 Использование: /add_user [@username] [role]\n\nПример: /add_user @MariaPaperman user"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Только администратор может добавлять пользователей."
            )
    elif text.startswith('/add_user_id ') and not is_group:
        # Add user by ID command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            parts = text.split(' ')
            if len(parts) >= 3:
                try:
                    target_user_id = int(parts[1])
                    username = parts[2].replace('@', '')
                    role = parts[3] if len(parts) > 3 else "user"
                    
                    success = await add_user_to_access_list(user_id, username, target_user_id, role)
                    if success:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ Пользователь @{username} (ID: {target_user_id}) добавлен с ролью '{role}'"
                        )
                    else:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="❌ Ошибка при добавлении пользователя. Возможно, он уже существует."
                        )
                except ValueError:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Неверный формат ID пользователя."
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="📝 Использование: /add_user_id [ID] [username] [role]\n\nПример: /add_user_id 123456789 MariaPaperman user"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Только администратор может добавлять пользователей."
            )
    elif text.startswith('/list_users') and not is_group:
        # List users command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            if user_access_list:
                users_text = "👥 Список пользователей:\n\n"
                for uid, user_data in user_access_list.items():
                    role_emoji = "👑" if user_data["role"] == "admin" else "👤"
                    users_text += f"{role_emoji} @{user_data['username']} (ID: {uid}) - {user_data['role']}\n"
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=users_text
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="📝 Список пользователей пуст."
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Только администратор может просматривать список пользователей."
            )
    elif text.startswith('/remove_user ') and not is_group:
        # Remove user command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            try:
                target_user_id = int(text.split(' ')[1])
                success = await remove_user_from_access_list(user_id, target_user_id)
                if success:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ Пользователь ID {target_user_id} удален из списка доступа."
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Ошибка при удалении пользователя."
                    )
            except (ValueError, IndexError):
                await bot.send_message(
                    chat_id=chat_id,
                    text="📝 Использование: /remove_user [ID]\n\nПример: /remove_user 123456789"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Только администратор может удалять пользователей."
            )
    elif text.startswith('/set_user_prompt ') and not is_group:
        # Set user prompt command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            try:
                parts = text.split(' ', 2)
                if len(parts) < 3:
                    raise ValueError("Недостаточно параметров")
                
                target_user_id = int(parts[1])
                new_prompt = parts[2]
                
                # Check if target user exists
                if target_user_id not in user_access_list:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Пользователь ID {target_user_id} не найден в системе."
                    )
                    return
                
                # Update prompt
                success = await update_user_personal_prompt(target_user_id, new_prompt)
                if success:
                    username = user_access_list[target_user_id]["username"]
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"""✅ **Промпт обновлен для пользователя @{username}**

📝 **Новый промпт:**
{new_prompt}

🔄 **Обновлено:** {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}""",
                        parse_mode="Markdown"
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Ошибка при обновлении промпта."
                    )
            except (ValueError, IndexError):
                await bot.send_message(
                    chat_id=chat_id,
                    text="""📝 **Использование:** `/set_user_prompt ID новый_промпт`

**Пример:**
`/set_user_prompt 139373848 Ты эксперт по программированию. Отвечай подробно с примерами кода.`

💡 **Совет:** Новый промпт заменит текущий промпт пользователя полностью.""",
                    parse_mode="Markdown"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Только администратор может изменять промпты пользователей."
            )
    elif text.startswith('/my_id'):
        # Show user ID (helpful for admin to get IDs)
        await bot.send_message(
            chat_id=chat_id,
            text=f"🆔 Ваш Telegram ID: {user_id}\n👤 Username: @{username}"
        )
    elif text.startswith('/debug ') and user_role == "admin" and not is_group:
        # Debug mode control (admin only)
        parts = text.split(' ')
        if len(parts) < 2:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Использование: /debug [on|off|status|report|clear]"
            )
            return
        
        action = parts[1].lower()
        
        if action == "on":
            init_debug_mode(True)
            await bot.send_message(
                chat_id=chat_id,
                text="🐛 **Режим отладки включен**\n\n✅ Все взаимодействия записываются\n📁 Логи: /var/log/bot_debug.log\n🌐 Мониторинг: /debug",
                parse_mode="Markdown"
            )
        elif action == "off":
            init_debug_mode(False)
            await bot.send_message(
                chat_id=chat_id,
                text="✅ **Режим отладки выключен**\n\nЗапись взаимодействий остановлена.",
                parse_mode="Markdown"
            )
        elif action == "status":
            debug_logger = get_debug_logger()
            stats = debug_logger.get_debug_stats()
            
            if stats["debug_mode"]:
                status_text = f"""🐛 **Статус отладки: АКТИВЕН**

📊 **Статистика:**
• Всего взаимодействий: {stats['total_interactions']}
• Ошибки: {stats['error_count']} ({stats['error_rate']*100:.1f}%)
• Среднее время ответа: {stats['avg_response_time']:.2f}s

📁 **Файлы:**
• Debug лог: {stats['debug_file']}
• JSON данные: {stats['interactions_file']}

🌐 **Веб-мониторинг:** /debug"""
            else:
                status_text = "❌ **Режим отладки выключен**"
                
            await bot.send_message(
                chat_id=chat_id,
                text=status_text,
                parse_mode="Markdown"
            )
        elif action == "clear":
            if is_debug_mode():
                debug_logger = get_debug_logger()
                debug_logger.clear_debug_data()
                await bot.send_message(
                    chat_id=chat_id,
                    text="🗑️ **Данные отладки очищены**\n\nВсе логи и статистика удалены."
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Режим отладки не активен"
                )
        elif action == "report":
            if is_debug_mode():
                debug_logger = get_debug_logger()
                report = debug_logger.export_debug_report()
                
                # Создать краткий отчет для Telegram
                summary = report['summary']
                users_count = len(report['users_data'])
                
                report_text = f"""📊 **Отчет отладки**

👥 **Пользователи:** {users_count}
📈 **Взаимодействия:** {summary['total_interactions']}
❌ **Ошибки:** {summary['error_count']} ({summary['error_rate']*100:.1f}%)
⏱️ **Среднее время:** {summary['avg_response_time']:.2f}s

📋 **Типы взаимодействий:**"""
                
                for interaction_type, count in summary['interaction_types'].items():
                    report_text += f"\n• {interaction_type}: {count}"
                
                report_text += f"\n\n🌐 **Полный отчет:** /debug"
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=report_text,
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Режим отладки не активен"
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Неизвестное действие. Используйте: on, off, status, report, clear"
            )
    elif text.startswith('/admin') and not is_group:
        # Admin panel command (only for admin in private chat)
        user_role = await get_user_role(user_id)
        if user_role == "admin":
            await bot.send_message(
                chat_id=chat_id,
                text="👑 Административная панель:",
                reply_markup=get_admin_panel_keyboard()
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Доступ запрещен. Только администратор может использовать эту команду."
            )
    elif text.startswith('/topic_data'):
        # Show topic data (only in groups with topics)
        if is_group:
            topic_id = getattr(message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Get topic data
                    topic_data = await get_topic_data(chat_id, topic_id, limit=10)
                    topic_settings = await get_topic_settings(chat_id, topic_id)
                    data_type = topic_settings.get("data_type", "general")
                    
                    if topic_data:
                        data_text = f"📊 Последние данные топика ({data_type}):\n\n"
                        for i, entry in enumerate(topic_data[:5], 1):
                            timestamp = entry["timestamp"].strftime("%d.%m %H:%M")
                            user_data = entry.get("data", {})
                            
                            if data_type == "movies":
                                title = user_data.get("title", "Неизвестно")
                                status = user_data.get("status", "")
                                data_text += f"{i}. 🎬 {title} ({status}) - {timestamp}\n"
                            else:
                                comment = str(user_data).replace("{", "").replace("}", "")[:50]
                                data_text += f"{i}. 📝 {comment}... - {timestamp}\n"
                        
                        data_text += f"\n📈 Всего записей: {len(topic_data)}"
                    else:
                        data_text = "📊 В этом топике пока нет сохраненных данных."
                    
                    await bot.send_message(
                        chat_id=chat_id,
                        text=data_text,
                        message_thread_id=topic_id
                    )
                except Exception as e:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Ошибка получения данных топика: {str(e)}",
                        message_thread_id=topic_id
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="📋 Эта команда работает только в топиках (темах)."
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="📋 Эта команда работает только в групповых чатах с топиками."
            )
    else:
        # Free chat with AI (only if mentioned in groups)
        if not is_group:
            await handle_free_chat(message)
        else:
            # Groups - we already checked for mentions and cleaned text earlier
            # So if we're here, it means the message was properly mentioned and cleaned
            topic_id = getattr(message, 'message_thread_id', None)
            
            # Try natural language processing first
            query_result = await process_natural_language_query(text, user_id, chat_id, topic_id)
            
            if query_result["intent"] != "unknown" and query_result["confidence"] > 0.5:
                # Handle with natural language processor
                await handle_natural_language_query(query_result, user_id, chat_id, topic_id)
            else:
                # Use topic context if in a topic, otherwise fall back to regular chat
                if text.strip():  # Make sure we have some text after cleaning
                    if topic_id:
                        # Handle with topic context
                        response = await handle_topic_message_with_context(text, user_id, chat_id, topic_id)
                        
                        # Try to extract structured data
                        topic_settings = await get_topic_settings(chat_id, topic_id)
                        if topic_settings.get("auto_extract_data", True):
                            data_type = topic_settings.get("data_type", "general")
                            if data_type == "movies":
                                await extract_movie_data(text, chat_id, topic_id, user_id)
                        
                        await bot.send_message(
                            chat_id=chat_id,
                            text=response,
                            message_thread_id=topic_id
                        )
                    else:
                        # Regular free chat for group without topic
                        message.text = text
                        await handle_free_chat(message)
                else:
                    # If only mention without text, send help
                    await bot.send_message(
                        chat_id=chat_id,
                        text="👋 Привет! Напишите ваш вопрос после упоминания @DMPlove_bot",
                        message_thread_id=topic_id
                    )

async def handle_photo_message(message):
    """Handle photo messages for food analysis with topic-specific settings"""
    chat_id = message.chat_id
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    is_group = message.chat.type in ['group', 'supergroup']
    topic_id = getattr(message, 'message_thread_id', None)
    
    # Check topic-specific settings for groups
    if is_group and topic_id:
        # Check if food analysis is allowed in this topic
        analysis_allowed = await is_food_analysis_allowed_in_topic(chat_id, topic_id)
        if not analysis_allowed:
            # Topic has food analysis disabled, ignore this image
            logger.info(f"Food analysis disabled for topic {topic_id} in chat {chat_id}")
            return
            
        # Get topic settings for additional configurations
        topic_settings = await get_topic_settings(chat_id, topic_id)
        
        # If auto_analysis is disabled, require @mention
        if not topic_settings.get("auto_analysis", True):
            bot_username = "DMPlove_bot"  # Replace with your bot username
            
            # Check if bot is mentioned in the caption
            caption_text = message.caption or ""
            if f"@{bot_username}" not in caption_text:
                # Bot is not mentioned and auto analysis is disabled, skip
                logger.info(f"Auto analysis disabled for topic {topic_id}, bot not mentioned")
                return
    
    try:
        # Get the largest photo
        photo = message.photo[-1]
        
        # Send "analyzing" message
        analyzing_msg = await bot.send_message(
            chat_id=chat_id,
            text="🔍 Анализирую изображение на предмет еды...",
            message_thread_id=topic_id  # Reply in same topic
        )
        
        try:
            # Get file info
            file = await bot.get_file(photo.file_id)
            
            # Check if file_path is valid
            if not file.file_path:
                raise Exception("Не удалось получить файл изображения")
            
            # Construct correct file URL
            # file_path might already be a full URL, so check that first
            if file.file_path.startswith('https://'):
                file_url = file.file_path
            else:
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
            
            # Log for debugging
            logger.info(f"Analyzing image URL: {file_url}")
            
            # Analyze with OpenAI Vision
            analysis = await analyze_food_image(file_url, user_id)
            
            # Get auto-delete delay for this topic (only for groups)
            delete_delay = 0  # Default for private chats
            if is_group and topic_id:
                delete_delay = await get_auto_delete_delay(chat_id, topic_id)
            
            # Delete analyzing message
            await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            
            if analysis["is_food"]:
                # Save to database
                await save_food_analysis(user_id, chat_id, username, analysis, photo.file_id)
                
                # For private chats, no auto-delete and different formatting
                if not is_group:
                    # Send detailed result for private chat (no auto-delete)
                    result_text = f"""📊 Анализ еды #{analysis['unique_number']}

🍽️ Блюдо: {analysis['dish_name']}
🔥 Калории: {analysis['calories']} ккал
🥩 Белки: {analysis['proteins']} г
🧈 Жиры: {analysis['fats']} г
🍞 Углеводы: {analysis['carbs']} г
📅 Дата: {datetime.now().strftime('%d.%m.%Y')}
🕒 Время: {datetime.now().strftime('%H:%M')}

💾 Данные сохранены в базе питания."""
                    
                    await bot.send_message(
                        chat_id=chat_id,
                        text=result_text
                    )
                else:
                    # Group chat logic (existing code)
                    # Send "food found" notification that will be deleted
                    food_found_msg = await bot.send_message(
                        chat_id=chat_id,
                        text="✅ Еда найдена! Сохраняю данные о питании...",
                        message_thread_id=topic_id
                    )
                    
                    # Schedule deletion of notification after configured time
                    if delete_delay > 0:  # 0 means don't delete
                        asyncio.create_task(delete_message_after_delay(chat_id, food_found_msg.message_id, min(30, delete_delay)))  # Show notification max 30 seconds
                    
                    # Send detailed result
                    result_text = f"""📊 Анализ еды #{analysis['unique_number']}

🍽️ Блюдо: {analysis['dish_name']}
🔥 Калории: {analysis['calories']} ккал
🥩 Белки: {analysis['proteins']} г
🧈 Жиры: {analysis['fats']} г
🍞 Углеводы: {analysis['carbs']} г
👤 Кто съел: {username}
📅 Дата: {datetime.now().strftime('%d.%m.%Y')}
🕒 Время: {datetime.now().strftime('%H:%M')}

💾 Данные сохранены в базе питания."""
                    
                    result_msg = await bot.send_message(
                        chat_id=chat_id,
                        text=result_text,
                        message_thread_id=topic_id
                    )
                    
                    # Schedule deletion of detailed result after configured delay to keep chat clean
                    if delete_delay > 0:  # 0 means don't delete
                        asyncio.create_task(delete_message_after_delay(chat_id, result_msg.message_id, delete_delay))
            else:
                # No food found message
                if not is_group:
                    # Private chat - no auto-delete
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Еда не найдена на изображении"
                    )
                else:
                    # Group chat - with auto-delete
                    no_food_msg = await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Еда не найдена на изображении",
                        message_thread_id=topic_id
                    )
                    
                    # Schedule message deletion after configured time
                    if delete_delay > 0:  # 0 means don't delete
                        asyncio.create_task(delete_message_after_delay(chat_id, no_food_msg.message_id, min(60, delete_delay)))  # Max 1 minute for "not found"
        
        except Exception as api_error:
            logger.error(f"API error during photo analysis: {str(api_error)}")
            
            # Delete analyzing message if it exists
            try:
                await bot.delete_message(chat_id=chat_id, message_id=analyzing_msg.message_id)
            except:
                pass
            
            # Send error message
            error_msg = await bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка при анализе изображения. Попробуйте еще раз.",
                message_thread_id=topic_id
            )
            
            # Schedule error message deletion after 1 minute
            asyncio.create_task(delete_message_after_delay(chat_id, error_msg.message_id, 60))
        
    except Exception as e:
        logger.error(f"Photo analysis error: {str(e)}")
        
        # Send error message
        error_msg = await bot.send_message(
            chat_id=chat_id,
            text="❌ Ошибка анализа. Попробуйте отправить фото еще раз.",
            message_thread_id=getattr(message, 'message_thread_id', None)
        )
        
        # Schedule error message deletion after 1 minute
        asyncio.create_task(delete_message_after_delay(chat_id, error_msg.message_id, 60))

async def delete_message_after_delay(chat_id: int, message_id: int, delay_seconds: int):
    """Delete message after specified delay"""
    try:
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id} after {delay_seconds} seconds")
    except Exception as e:
        logger.error(f"Failed to delete message {message_id}: {str(e)}")

async def handle_image_generation(chat_id: int, description: str):
    """Handle image generation using OpenAI DALL-E"""
    try:
        generating_msg = await bot.send_message(
            chat_id=chat_id,
            text="🎨 Генерирую изображение..."
        )
        
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=description,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        
        # Delete generating message
        await bot.delete_message(chat_id=chat_id, message_id=generating_msg.message_id)
        
        # Send image
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=f"🎨 Изображение: {description}"
        )
        
    except Exception as e:
        logger.error(f"Image generation error: {str(e)}")
        try:
            await bot.delete_message(chat_id=chat_id, message_id=generating_msg.message_id)
        except:
            pass
        
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Ошибка генерации изображения: {str(e)}"
        )

async def analyze_document(file_content: bytes, file_name: str, mime_type: str, user_id: int) -> str:
    """Analyze document content using OpenAI"""
    try:
        # Check if this is an image file
        if mime_type.startswith('image/') or file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
            # This is an image, use Vision API
            import base64
            image_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Determine image format
            image_format = "jpeg"  # Default
            if file_content.startswith(b'\x89PNG'):
                image_format = "png"
            elif file_content.startswith(b'\xff\xd8'):
                image_format = "jpeg"
            elif file_content.startswith(b'GIF'):
                image_format = "gif"
            elif file_content.startswith(b'RIFF') and b'WEBP' in file_content[:20]:
                image_format = "webp"
            
            # Analyze image with Vision API
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Проанализируй это изображение и опиши что на нем изображено. Дай подробное описание на русском языке."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        # Try to extract text from document
        text_content = ""
        
        if mime_type == "text/plain" or file_name.endswith('.txt'):
            # Plain text file
            text_content = file_content.decode('utf-8', errors='ignore')
        elif mime_type == "application/json" or file_name.endswith('.json'):
            # JSON file
            text_content = file_content.decode('utf-8', errors='ignore')
        elif mime_type == "text/csv" or file_name.endswith('.csv'):
            # CSV file
            text_content = file_content.decode('utf-8', errors='ignore')
        elif mime_type == "text/markdown" or file_name.endswith('.md'):
            # Markdown file
            text_content = file_content.decode('utf-8', errors='ignore')
        else:
            # For other file types, try to extract as text
            try:
                text_content = file_content.decode('utf-8', errors='ignore')
                if not text_content.strip():
                    return f"❌ Не удалось извлечь текст из файла типа {mime_type}. Поддерживаются: TXT, JSON, CSV, MD, и изображения (PNG, JPG, GIF, WebP)"
            except:
                return f"❌ Не удалось обработать файл типа {mime_type}. Поддерживаются текстовые форматы и изображения."
        
        # Limit text length for API
        if len(text_content) > 8000:
            text_content = text_content[:8000] + "... (текст обрезан)"
        
        # Analyze with ChatGPT
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Ты аналитик документов. Проанализируй содержимое файла и дай краткое резюме на русском языке."
                },
                {
                    "role": "user", 
                    "content": f"Проанализируй этот документ '{file_name}':\n\n{text_content}"
                }
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Document analysis error: {str(e)}")
        return f"❌ Ошибка анализа: {str(e)}"

async def handle_database_search(chat_id: int, user_id: int, query: str, message_thread_id=None):
    """Handle database search for food data"""
    try:
        searching_msg = await bot.send_message(
            chat_id=chat_id,
            text="🔍 Ищу в базе данных питания...",
            message_thread_id=message_thread_id
        )
        
        # Parse search query for filters
        search_results = await search_food_database(user_id, query)
        
        if not search_results["results"]:
            await bot.delete_message(chat_id=chat_id, message_id=searching_msg.message_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"🔍 Поиск: \"{query}\"\n\n❌ Ничего не найдено в вашей базе данных питания.",
                message_thread_id=message_thread_id
            )
            return
        
        # Format results
        result_text = f"""🔍 Результаты поиска: "{query}"
        
📊 Найдено: {len(search_results["results"])} записей
📅 Период: {search_results["date_range"]}

📋 **Найденные блюда:**"""
        
        for i, item in enumerate(search_results["results"][:10], 1):  # Limit to 10 results
            date_str = item["timestamp"].strftime("%d.%m.%Y %H:%M") if isinstance(item["timestamp"], datetime) else item.get("date", "")
            result_text += f"""
{i}. **{item["dish_name"]}**
   📅 {date_str}
   🔥 {item["calories"]} ккал | 🥩 Б: {item["proteins"]}г | 🧈 Ж: {item["fats"]}г | 🍞 У: {item["carbs"]}г
   👤 {item.get("username", "Неизвестно")}"""
        
        if len(search_results["results"]) > 10:
            result_text += f"\n\n📝 ... и еще {len(search_results['results']) - 10} записей"
        
        # Add summary statistics
        total_calories = sum(item["calories"] for item in search_results["results"])
        total_proteins = sum(item["proteins"] for item in search_results["results"])
        total_fats = sum(item["fats"] for item in search_results["results"])
        total_carbs = sum(item["carbs"] for item in search_results["results"])
        
        result_text += f"""

📊 **Общая статистика найденного:**
🔥 Калории: {total_calories} ккал
🥩 Белки: {total_proteins:.1f}г
🧈 Жиры: {total_fats:.1f}г
🍞 Углеводы: {total_carbs:.1f}г"""
        
        await bot.delete_message(chat_id=chat_id, message_id=searching_msg.message_id)
        
        await bot.send_message(
            chat_id=chat_id,
            text=result_text,
            parse_mode="Markdown",
            message_thread_id=message_thread_id
        )
        
    except Exception as e:
        logger.error(f"Database search error: {str(e)}")
        try:
            await bot.delete_message(chat_id=chat_id, message_id=searching_msg.message_id)
        except:
            pass
        
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Ошибка поиска в базе данных: {str(e)}",
            message_thread_id=message_thread_id
        )

async def search_food_database(user_id: int, query: str) -> dict:
    """Search in food database with intelligent parsing"""
    try:
        # Parse query for different search types
        query_lower = query.lower()
        
        # Date filters
        date_filter = {}
        now = datetime.utcnow()
        
        if "сегодня" in query_lower or "today" in query_lower:
            date_filter = {"date": now.strftime("%Y-%m-%d")}
        elif "вчера" in query_lower or "yesterday" in query_lower:
            yesterday = now - timedelta(days=1)
            date_filter = {"date": yesterday.strftime("%Y-%m-%d")}
        elif "неделя" in query_lower or "week" in query_lower:
            week_ago = now - timedelta(days=7)
            date_filter = {"timestamp": {"$gte": week_ago}}
        elif "месяц" in query_lower or "month" in query_lower:
            month_ago = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_filter = {"timestamp": {"$gte": month_ago}}
        
        # Text search in dish names
        text_search = {}
        search_terms = [word for word in query_lower.split() 
                       if word not in ["сегодня", "вчера", "неделя", "месяц", "today", "yesterday", "week", "month", "поиск", "найди", "найти"]]
        
        if search_terms:
            # Create regex pattern for partial matching
            pattern = "|".join(search_terms)
            text_search = {"dish_name": {"$regex": pattern, "$options": "i"}}
        
        # Combine filters
        search_filter = {"user_id": user_id}
        if date_filter:
            search_filter.update(date_filter)
        if text_search:
            search_filter.update(text_search)
        
        # If no specific filters, search in last 30 days
        if not date_filter and not text_search:
            thirty_days_ago = now - timedelta(days=30)
            search_filter["timestamp"] = {"$gte": thirty_days_ago}
        
        # Execute search
        cursor = app.mongodb.food_analysis.find(search_filter).sort("timestamp", -1)
        results = await cursor.to_list(length=50)  # Limit to 50 results
        
        # Determine date range for results
        if results:
            dates = [r["timestamp"] for r in results if "timestamp" in r]
            if dates:
                min_date = min(dates).strftime("%d.%m.%Y")
                max_date = max(dates).strftime("%d.%m.%Y")
                if min_date == max_date:
                    date_range = min_date
                else:
                    date_range = f"{min_date} - {max_date}"
            else:
                date_range = "Различные даты"
        else:
            date_range = "Нет данных"
        
        return {
            "results": results,
            "date_range": date_range,
            "total_found": len(results)
        }
        
    except Exception as e:
        logger.error(f"Food database search error: {str(e)}")
        return {"results": [], "date_range": "", "total_found": 0}

async def handle_free_chat(message):
    """Handle free chat with AI"""
    chat_id = message.chat_id
    user_id = message.from_user.id
    
    try:
        # Show typing indicator
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        
        response = await enhanced_free_chat_ai(message.text, user_id, chat_id)
        
        await bot.send_message(
            chat_id=chat_id,
            text=response,
            reply_markup=get_stop_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Free chat error: {str(e)}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Ошибка: {str(e)}"
        )

async def handle_callback_query(callback_query):
    """Handle inline keyboard callbacks"""
    chat_id = callback_query.message.chat_id
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    # Debug logging
    debug_logger = get_debug_logger()
    start_time = time.time()
    
    try:
        # Debug log callback query
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="callback_query",
            input_data={"callback_data": data, "chat_id": chat_id}
        )
        
        # First check if user is allowed
        if not await is_user_allowed(user_id):
            await bot.answer_callback_query(callback_query.id, "❌ Нет доступа")
            
            # Debug log access denied
            debug_logger.log_callback_query(
                user_id=user_id,
                callback_data=data,
                success=False,
                error="Access denied",
                response_time=time.time() - start_time
            )
            return
        
        # Check if callback query is too old (more than 60 seconds)
        current_time = time.time()
        query_time = callback_query.message.date.timestamp() if callback_query.message else current_time
        
        if current_time - query_time > 30:  # Уменьшено до 30 секунд для быстрой обработки
            logger.warning(f"Callback query too old: {current_time - query_time}s")
            try:
                await bot.answer_callback_query(callback_query.id, "❌ Запрос устарел, попробуйте снова")
            except:
                pass
            
            # Debug log old query
            debug_logger.log_callback_query(
                user_id=user_id,
                callback_data=data,
                success=False,
                error="Query too old",
                response_time=time.time() - start_time
            )
            return
        
        # Answer callback query early to avoid timeout
        try:
            await bot.answer_callback_query(callback_query.id)
        except Exception as e:
            logger.warning(f"Failed to answer callback query: {str(e)}")
            # Continue processing even if we can't answer
        
        if data == "close_menu":
            # Delete the menu message
            await bot.delete_message(
                chat_id=chat_id,
                message_id=callback_query.message.message_id
            )
            return
        elif data == "main_menu":
            # Get user role to customize menu
            user_role = await get_user_role(user_id)
            
            if user_role == "admin":
                # Special admin menu
                admin_keyboard = [
                    [InlineKeyboardButton("📸 Анализ еды", callback_data="analyze_food_info")],
                    [InlineKeyboardButton("💪 Фитнес советы", callback_data="fitness_advice"), 
                     InlineKeyboardButton("👤 Профиль", callback_data="health_profile")],
                    [InlineKeyboardButton("🤖 AI Чат", callback_data="free_chat"), 
                     InlineKeyboardButton("🎬 Фильмы", callback_data="movies")],
                    [InlineKeyboardButton("📊 Статистика", callback_data="stats_main"), 
                     InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                    [InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")],
                    [InlineKeyboardButton("❌ Закрыть меню", callback_data="close_menu")]
                ]
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="🏠 Главное меню (Администратор):",
                    reply_markup=InlineKeyboardMarkup(admin_keyboard)
                )
            else:
                # Regular user menu
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="🏠 Главное меню:",
                    reply_markup=get_main_menu_keyboard()
                )
        elif data == "settings":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="⚙️ Настройки:",
                reply_markup=get_settings_keyboard()
            )
        elif data == "ai_model":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🤖 Выберите модель ИИ:",
                reply_markup=get_ai_model_keyboard()
            )
        elif data.startswith("model_"):
            model = data.replace("model_", "")
            await save_user_setting(user_id, "ai_model", model)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"✅ Модель изменена на {model}",
                reply_markup=get_settings_keyboard()
            )
        elif data == "fitness_advice":
            user_data = await get_user_data(user_id)
            user_data['user_id'] = user_id  # Add user_id for nutrition data lookup
            advice = await generate_fitness_advice(user_data)
            await bot.send_message(
                chat_id=chat_id,
                text=f"💪 Персональные рекомендации:\n\n{advice}",
                reply_markup=get_stop_keyboard()
            )
        elif data == "analyze_food_info":
            # Show food analysis information
            info_text = """📸 **Анализ еды - Информация**

🔍 **Как это работает:**
• Отправьте фото еды в чат
• ИИ автоматически распознает блюдо
• Получите данные о калориях и БЖУ
• Данные сохраняются в базу для статистики

💡 **Поддерживаемые форматы:**
• Фотографии блюд
• Готовые блюда и сырые продукты
• Напитки и десерты
• Фрукты и овощи

📊 **Данные которые вы получите:**
• Название блюда
• Калории (ккал)
• Белки (г)
• Жиры (г) 
• Углеводы (г)

🎯 **Совет:** Фотографируйте еду под хорошим освещением для лучшего распознавания!"""

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=info_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
            )
        elif data == "free_chat":
            # Start free chat with AI
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🤖 **AI Чат активирован!**\n\nТеперь просто напишите любое сообщение, и я отвечу с учетом контекста нашего разговора.\n\n💡 **Возможности:**\n• Общие вопросы и разговор\n• Генерация изображений (команда /image)\n• Анализ документов и файлов\n• Поиск информации\n\n🛑 Чтобы очистить контекст разговора, используйте кнопку \"Стоп\"",
                parse_mode="Markdown",
                reply_markup=get_stop_keyboard()
            )
        elif data == "movies":
            # Show movies menu
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎬 **Фильмы и сериалы**\n\nУправляйте своим списком фильмов и получайте персональные рекомендации на основе ваших предпочтений.",
                parse_mode="Markdown",
                reply_markup=get_movies_keyboard()
            )
        elif data == "health_profile":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="👤 Профиль здоровья:",
                reply_markup=get_health_profile_keyboard()
            )
        elif data == "set_height":
            # Set height
            set_user_state(user_id, "waiting_height")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📏 Введите ваш рост в сантиметрах:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="health_profile")]])
            )
        elif data == "set_weight":
            # Set weight
            set_user_state(user_id, "waiting_weight")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="⚖️ Введите ваш вес в килограммах:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="health_profile")]])
            )
        elif data == "set_age":
            # Set age
            set_user_state(user_id, "waiting_age")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎂 Введите ваш возраст в годах:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="health_profile")]])
            )
        elif data == "show_profile":
            user_data = await get_user_data(user_id)
            settings = user_data.get("settings", {})
            profile_text = f"""
👤 Ваш профиль здоровья:

📏 Рост: {settings.get('height', 'не указан')} см
⚖️ Вес: {settings.get('weight', 'не указан')} кг
🎂 Возраст: {settings.get('age', 'не указан')} лет
🎯 Цель: {settings.get('goal', 'не указана')}
🤖 Модель ИИ: {settings.get('ai_model', 'gpt-4')}
            """
            await bot.send_message(
                chat_id=chat_id,
                text=profile_text,
                reply_markup=get_health_profile_keyboard()
            )
        elif data == "stats":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📊 Статистика питания:",
                reply_markup=get_stats_keyboard()
            )
        elif data == "stats_main":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📊 Статистика питания:",
                reply_markup=get_stats_keyboard()
            )
        elif data == "enhanced_stats_menu":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📊 Расширенная статистика:\n\nВыберите пользователя и период для просмотра детальной статистики.",
                reply_markup=get_enhanced_stats_keyboard()
            )
        elif data == "quick_stats_menu":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="⚡ Быстрая статистика (ваши данные):",
                reply_markup=get_quick_stats_keyboard()
            )
        elif data == "select_stats_user":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="👤 Выберите пользователя для просмотра статистики:",
                reply_markup=get_stats_user_keyboard()
            )
        elif data == "select_stats_period":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📅 Выберите период для статистики:",
                reply_markup=get_stats_period_keyboard()
            )
        elif data.startswith("quick_stats_"):
            period = data.replace("quick_stats_", "")
            stats = await get_enhanced_food_stats(user_id, period)
            
            if "error" in stats:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {stats['error']}",
                    reply_markup=get_quick_stats_keyboard()
                )
                return
            
            # Format enhanced stats
            stats_text = f"""
📊 Статистика питания - {stats['period']}
👤 Пользователь: @{stats['username']}

📈 **Общие показатели:**
🍽️ Приемов пищи: {stats['total_meals']}
🔥 Калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']:.1f} г
🧈 Жиры: {stats['total_fats']:.1f} г  
🍞 Углеводы: {stats['total_carbs']:.1f} г

📊 **Средние значения в день:**
🔥 Калории: {stats['averages']['avg_calories']:.0f} ккал
🥩 Белки: {stats['averages']['avg_proteins']:.1f} г
🧈 Жиры: {stats['averages']['avg_fats']:.1f} г
🍞 Углеводы: {stats['averages']['avg_carbs']:.1f} г
🍽️ Приемов пищи: {stats['averages']['avg_meals']:.1f}
            """
            
            await bot.send_message(
                chat_id=chat_id,
                text=stats_text,
                parse_mode="Markdown",
                reply_markup=get_quick_stats_keyboard()
            )
        elif data.startswith("stats_user_"):
            # Handle user selection for enhanced stats
            selected_user_id = int(data.replace("stats_user_", ""))
            
            # Store selected user in callback data temporarily
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"👤 Выбран пользователь: @{user_access_list.get(selected_user_id, {}).get('username', 'Неизвестно')}\n\n📅 Теперь выберите период:",
                reply_markup=get_stats_period_keyboard()
            )
            
            # Store selected user ID in user state
            set_user_state(user_id, f"selected_user_{selected_user_id}")
            
        elif data.startswith("stats_period_"):
            # Handle period selection for enhanced stats
            period = data.replace("stats_period_", "")
            
            # Get selected user from state
            user_state = get_user_state(user_id)
            if user_state.startswith("selected_user_"):
                selected_user_id = int(user_state.replace("selected_user_", ""))
                clear_user_state(user_id)
                
                # Get enhanced stats
                stats = await get_enhanced_food_stats(user_id, period, selected_user_id)
                
                if "error" in stats:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"❌ {stats['error']}",
                        reply_markup=get_enhanced_stats_keyboard()
                    )
                    return
                
                # Format enhanced stats
                stats_text = f"""
📊 Статистика питания {stats['period']} для @{stats['username']}

📈 **Суммарные показатели:**
🍽️ Приемов пищи: {stats['total_meals']}
🔥 Калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']:.1f} г
🧈 Жиры: {stats['total_fats']:.1f} г  
🍞 Углеводы: {stats['total_carbs']:.1f} г

📊 **Средние значения в день:**
🔥 Калории: {stats['averages']['avg_calories']:.0f} ккал
🥩 Белки: {stats['averages']['avg_proteins']:.1f} г
🧈 Жиры: {stats['averages']['avg_fats']:.1f} г
🍞 Углеводы: {stats['averages']['avg_carbs']:.1f} г
🍽️ Приемов пищи: {stats['averages']['avg_meals']:.1f}
                """
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=stats_text,
                    parse_mode="Markdown",
                    reply_markup=get_enhanced_stats_keyboard()
                )
            else:
                # No user selected, default to requester
                stats = await get_enhanced_food_stats(user_id, period)
                
                if "error" in stats:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"❌ {stats['error']}",
                        reply_markup=get_stats_period_keyboard()
                    )
                    return
                
                # Format stats for current user
                stats_text = f"""
📊 Ваша статистика питания {stats['period']}

📈 **Суммарные показатели:**
🍽️ Приемов пищи: {stats['total_meals']}
🔥 Калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']:.1f} г
🧈 Жиры: {stats['total_fats']:.1f} г  
🍞 Углеводы: {stats['total_carbs']:.1f} г

📊 **Средние значения в день:**
🔥 Калории: {stats['averages']['avg_calories']:.0f} ккал
🥩 Белки: {stats['averages']['avg_proteins']:.1f} г
🧈 Жиры: {stats['averages']['avg_fats']:.1f} г
🍞 Углеводы: {stats['averages']['avg_carbs']:.1f} г
🍽️ Приемов пищи: {stats['averages']['avg_meals']:.1f}
                """
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=stats_text,
                    parse_mode="Markdown",
                    reply_markup=get_stats_period_keyboard()
                )
        elif data.startswith("stats_"):
            # Old stats format for backward compatibility
            period = data.replace("stats_", "")
            stats = await get_food_stats(user_id, period)
            
            period_names = {
                "today": "Сегодня",
                "week": "За неделю", 
                "month": "За месяц"
            }
            
            stats_text = f"""
📊 Статистика питания - {period_names[period]}:

🍽️ Количество приемов пищи: {stats['total_meals']}
🔥 Общие калории: {stats['total_calories']} ккал
🥩 Белки: {stats['total_proteins']} г
🧈 Жиры: {stats['total_fats']} г
🍞 Углеводы: {stats['total_carbs']} г
            """
            await bot.send_message(
                chat_id=chat_id,
                text=stats_text,
                reply_markup=get_stats_keyboard()
            )
        elif data == "analyze_food_info":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="""📸 Анализ еды

Просто отправьте фото любого блюда, и я:
• Определю название блюда
• Подсчитаю калории  
• Рассчитаю белки, жиры, углеводы
• Сохраню данные с вашим именем
• Покажу время и дату

Готов анализировать ваше следующее фото! 📷""",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
            )
        elif data == "my_stats":
            today_stats = await get_food_stats(user_id, "today")
            week_stats = await get_food_stats(user_id, "week")
            
            stats_text = f"""📊 Ваша статистика питания

🗓️ Сегодня:
🍽️ Приемов пищи: {today_stats['total_meals']}
🔥 Калории: {today_stats['total_calories']} ккал
🥩 Белки: {today_stats['total_proteins']} г
🧈 Жиры: {today_stats['total_fats']} г
🍞 Углеводы: {today_stats['total_carbs']} г

📅 За неделю:
🍽️ Приемов пищи: {week_stats['total_meals']}
🔥 Калории: {week_stats['total_calories']} ккал
            """
            
            await bot.send_message(
                chat_id=chat_id,
                text=stats_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Подробная статистика", callback_data="stats")],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
                ])
            )
        elif data == "quick_actions":
            await bot.send_message(
                chat_id=chat_id,
                text="⚡ Быстрые действия:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📸 Анализ фото", callback_data="analyze_food_info")],
                    [InlineKeyboardButton("💪 Фитнес совет", callback_data="fitness_advice")],
                    [InlineKeyboardButton("🎬 Что посмотреть?", callback_data="get_recommendations")],
                    [InlineKeyboardButton("🤖 Поговорить с AI", callback_data="free_chat")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
                ])
            )
        elif data == "refresh_menu":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="""🤖 Семейный бот-помощник

🔄 Меню обновлено!

Выберите действие:""",
                reply_markup=get_main_menu_keyboard()
            )
        elif data == "stop_dialog":
            clear_user_state(user_id)
            clear_user_conversation(user_id)  # Очищаем контекст диалога
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Диалог остановлен. Контекст разговора очищен.",
                reply_markup=get_main_menu_keyboard()
            )
        elif data == "toggle_food_analysis":
            # Toggle food analysis for current topic
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        current_settings = await get_topic_settings(chat_id, topic_id)
                        current_settings["food_analysis_enabled"] = not current_settings.get("food_analysis_enabled", True)
                        await save_topic_settings(chat_id, topic_id, current_settings)
                        
                        status = "включен" if current_settings["food_analysis_enabled"] else "выключен"
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text=f"✅ Анализ еды в этом топике {status}",
                            reply_markup=get_topic_settings_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error toggling food analysis: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при изменении настроек.")
        elif data == "toggle_auto_analysis":
            # Toggle auto analysis for current topic
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        current_settings = await get_topic_settings(chat_id, topic_id)
                        current_settings["auto_analysis"] = not current_settings.get("auto_analysis", True)
                        await save_topic_settings(chat_id, topic_id, current_settings)
                        
                        status = "включен" if current_settings["auto_analysis"] else "выключен (требуется @упоминание)"
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text=f"✅ Автоматический анализ {status}",
                            reply_markup=get_topic_settings_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error toggling auto analysis: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при изменении настроек.")
        elif data == "topic_status":
            # Show current topic status
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                current_settings = await get_topic_settings(chat_id, topic_id)
                
                food_status = "включен" if current_settings.get("food_analysis_enabled", True) else "выключен"
                auto_status = "включен" if current_settings.get("auto_analysis", True) else "выключен"
                
                # Get context info
                key = f"{chat_id}_{topic_id}"
                context_messages = len(topic_conversations.get(key, []))
                
                # Get data type info
                data_type = current_settings.get("data_type", "general")
                type_names = {
                    "food": "🍽️ Еда",
                    "movies": "🎬 Фильмы/Сериалы",
                    "books": "📚 Книги", 
                    "general": "📝 Общие данные"
                }
                
                status_text = f"""📊 Статус топика:

🍽️ Анализ еды: {food_status}
🤖 Автоматический анализ: {auto_status}
📊 Тип данных: {type_names.get(data_type, data_type)}
⏰ Автоудаление через: {current_settings.get('auto_delete_delay', 300) // 60} мин
💬 Сообщений в контексте: {context_messages}
📍 ID топика: {topic_id}

💭 **Промпт:** {current_settings.get('custom_prompt', 'Стандартный')[:100]}...

{current_settings.get('topic_name', 'Без названия')}"""
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=status_text,
                    reply_markup=get_topic_settings_keyboard()
                )
        elif data == "set_auto_delete_delay":
            # Show auto-delete delay options
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text="⏰ Выберите время автоудаления сообщений бота:",
                            reply_markup=get_auto_delete_delay_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error showing auto-delete options: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при показе настроек.")
        elif data.startswith("delay_"):
            # Set auto-delete delay
            delay_value = int(data.replace("delay_", ""))
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        current_settings = await get_topic_settings(chat_id, topic_id)
                        current_settings["auto_delete_delay"] = delay_value
                        await save_topic_settings(chat_id, topic_id, current_settings)
                        
                        if delay_value == 0:
                            status_text = "✅ Автоудаление сообщений отключено"
                        else:
                            minutes = delay_value // 60
                            seconds = delay_value % 60
                            if minutes > 0 and seconds > 0:
                                time_text = f"{minutes} мин {seconds} сек"
                            elif minutes > 0:
                                time_text = f"{minutes} мин"
                            else:
                                time_text = f"{seconds} сек"
                            status_text = f"✅ Автоудаление настроено на {time_text}"
                        
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text=status_text,
                            reply_markup=get_topic_settings_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error setting auto-delete delay: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при изменении настроек.")
        elif data == "topic_settings_menu":
            # Return to topic settings menu
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="⚙️ Настройки топика:",
                reply_markup=get_topic_settings_keyboard()
            )
        elif data == "set_topic_prompt":
            # Set custom prompt for topic
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text="""💬 Настройка промпта для топика

Отправьте новый промпт для этого топика. Это определит как AI будет вести себя в данной теме.

Примеры:
• "Ты эксперт по фильмам и сериалам. Помогаешь выбирать контент и обсуждаешь кино."
• "Ты фитнес-тренер. Даешь советы по тренировкам и правильному питанию."
• "Ты кулинарный помощник. Помогаешь с рецептами и советами по готовке."

Отправьте промпт одним сообщением в ответ на это.""",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="topic_settings_menu")]])
                        )
                        
                        # Set user state for prompt input
                        set_user_state(user_id, f"setting_topic_prompt_{chat_id}_{topic_id}")
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error setting topic prompt: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при настройке промпта.")
        elif data == "clear_topic_context":
            # Clear topic conversation context
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        await clear_topic_conversation(chat_id, topic_id)
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text="✅ Контекст топика очищен. Следующие сообщения начнут новый диалог.",
                            reply_markup=get_topic_settings_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут очищать контекст.")
                except Exception as e:
                    logger.error(f"Error clearing topic context: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при очистке контекста.")
        elif data == "set_topic_data_type":
            # Show data type selection
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text="📊 Выберите тип данных для этого топика:\n\n🍽️ Еда - анализ питания\n🎬 Фильмы/Сериалы - рекомендации\n📚 Книги - библиотека\n📝 Общие данные - произвольная структура",
                            reply_markup=get_topic_data_type_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error showing data type selection: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при показе типов данных.")
        elif data.startswith("data_type_"):
            # Set topic data type
            data_type = data.replace("data_type_", "")
            topic_id = getattr(callback_query.message, 'message_thread_id', None)
            if topic_id:
                try:
                    # Check admin status
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    if chat_member.status in ['administrator', 'creator']:
                        current_settings = await get_topic_settings(chat_id, topic_id)
                        current_settings["data_type"] = data_type
                        await save_topic_settings(chat_id, topic_id, current_settings)
                        
                        type_names = {
                            "food": "🍽️ Еда",
                            "movies": "🎬 Фильмы/Сериалы", 
                            "books": "📚 Книги",
                            "general": "📝 Общие данные"
                        }
                        
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=callback_query.message.message_id,
                            text=f"✅ Тип данных установлен: {type_names.get(data_type, data_type)}\n\nТеперь сообщения в этом топике будут автоматически анализироваться для извлечения структурированных данных.",
                            reply_markup=get_topic_settings_keyboard()
                        )
                    else:
                        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут изменять настройки.")
                except Exception as e:
                    logger.error(f"Error setting data type: {str(e)}")
                    await bot.answer_callback_query(callback_query.id, "❌ Ошибка при установке типа данных.")
        elif data == "movies":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎬 Фильмы и сериалы:",
                reply_markup=get_movies_keyboard()
            )
        elif data == "add_movie":
            set_user_state(user_id, "waiting_movie")
            await bot.send_message(
                chat_id=chat_id,
                text="🎬 Напишите название фильма или сериала, который вам понравился:",
                reply_markup=get_stop_keyboard()
            )
        elif data == "get_recommendations":
            user_movies = await get_user_movies(user_id)
            if len(user_movies) == 0:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Сначала добавьте фильмы/сериалы в свой список!",
                    reply_markup=get_movies_keyboard()
                )
            else:
                recommendations = await generate_movie_recommendations(user_movies)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🎬 Рекомендации на основе ваших предпочтений:\n\n{recommendations}",
                    reply_markup=get_movies_keyboard()
                )
        elif data == "my_movies":
            user_movies = await get_user_movies(user_id)
            if len(user_movies) == 0:
                movies_text = "📋 Ваш список фильмов и сериалов пуст.\nДобавьте что-нибудь!"
            else:
                movies_text = "📋 Ваши фильмы и сериалы:\n\n" + "\n".join([f"• {movie}" for movie in user_movies[:10]])
                if len(user_movies) > 10:
                    movies_text += f"\n\n... и еще {len(user_movies) - 10} фильмов"
            await bot.send_message(
                chat_id=chat_id,
                text=movies_text,
                reply_markup=get_movies_keyboard()
            )
        elif data == "change_height":
            set_user_state(user_id, "waiting_height")
            await bot.send_message(
                chat_id=chat_id,
                text="📏 Введите ваш рост в сантиметрах (например: 175):",
                reply_markup=get_stop_keyboard()
            )
        elif data == "change_weight":
            set_user_state(user_id, "waiting_weight")
            await bot.send_message(
                chat_id=chat_id,
                text="⚖️ Введите ваш вес в килограммах (например: 70):",
                reply_markup=get_stop_keyboard()
            )
        elif data == "change_age":
            set_user_state(user_id, "waiting_age")
            await bot.send_message(
                chat_id=chat_id,
                text="🎂 Введите ваш возраст (например: 25):",
                reply_markup=get_stop_keyboard()
            )
        elif data == "fitness_goal":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎯 Выберите вашу фитнес цель:",
                reply_markup=get_fitness_goal_keyboard()
            )
        elif data.startswith("goal_"):
            goal_name = data.replace("goal_", "").replace("_", " ")
            goal_names = {
                "weight loss": "Похудение",
                "muscle gain": "Набор мышечной массы",
                "maintenance": "Поддержание формы",
                "strength": "Силовые тренировки"
            }
            await save_user_setting(user_id, "goal", goal_names.get(goal_name, goal_name))
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"✅ Цель изменена на: {goal_names.get(goal_name, goal_name)}",
                reply_markup=get_settings_keyboard()
            )
        elif data == "free_chat":
            await bot.send_message(
                chat_id=chat_id,
                text="🤖 Режим свободного общения активирован!\n\nЗадавайте любые вопросы, и я отвечу через ChatGPT.",
                reply_markup=get_stop_keyboard()
            )
        elif data == "bot_commands":
            commands_text = """
🤖 Команды бота для @BotFather:

start - Главное меню
help - Помощь по использованию бота
menu - Показать главное меню
stats - Статистика питания
image - Создать изображение
search - Поиск в интернете

📱 Настройка в BotFather:
1. Найдите @BotFather в Telegram
2. Отправьте /setcommands
3. Выберите вашего бота
4. Скопируйте и вставьте команды выше
            """
            await bot.send_message(
                chat_id=chat_id,
                text=commands_text,
                reply_markup=get_settings_keyboard()
            )
        elif data == "create_command":
            set_user_state(user_id, "waiting_command_name")
            await bot.send_message(
                chat_id=chat_id,
                text="➕ Создание новой команды\n\nВведите название команды (без слэша):",
                reply_markup=get_stop_keyboard()
            )
        elif data == "my_commands":
            user_data = await get_user_data(user_id)
            custom_commands = user_data.get("custom_commands", {})
            
            if not custom_commands:
                commands_text = "📝 У вас пока нет пользовательских команд.\n\nИспользуйте 'Новая команда' для создания."
            else:
                commands_text = "📝 Ваши команды:\n\n"
                for cmd, data in custom_commands.items():
                    commands_text += f"/{cmd} - {data['description']}\n"
            
            await bot.send_message(
                chat_id=chat_id,
                text=commands_text,
                reply_markup=get_settings_keyboard()
            )
        elif data == "prompts":
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🔧 Управление предпромптами:",
                reply_markup=get_prompts_keyboard()
            )
        elif data == "edit_fitness_prompt":
            await bot.send_message(
                chat_id=chat_id,
                text="📝 Текущий фитнес промпт:\n\n'Ты персональный фитнес-тренер и диетолог'\n\nВведите новый промпт или нажмите 'Назад':",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="prompts")]])
            )
        elif data == "edit_chat_prompt":
            await bot.send_message(
                chat_id=chat_id,
                text="📝 Текущий промпт для общения:\n\n'Ты полезный AI-ассистент. Отвечай кратко и по существу на русском языке.'\n\nВведите новый промпт или нажмите 'Назад':",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="prompts")]])
            )
        elif data == "admin_panel":
            # Show admin panel
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="👑 Административная панель:",
                    reply_markup=get_admin_panel_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_add_user":
            # Add user interface  
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="""➕ **Добавить пользователя**

Для добавления пользователя используйте команды:

📝 **В приватном чате с ботом:**
• `/add_user @username role` - добавить по username
• `/add_user_id ID username role` - добавить по ID

**Роли:**
• `admin` - администратор (полный доступ)
• `user` - пользователь (обычный доступ)

**Пример:**
`/add_user @newuser user`""",
                    parse_mode="Markdown",
                    reply_markup=get_admin_users_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_remove_user":
            # Remove user interface
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="""❌ **Удалить пользователя**

Для удаления пользователя используйте команду:

📝 **В приватном чате с ботом:**
• `/remove_user ID` - удалить пользователя по ID

**Пример:**
`/remove_user 123456789`

⚠️ **Внимание:** Удаление необратимо!""",
                    parse_mode="Markdown",
                    reply_markup=get_admin_users_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_user_prompts":
            # User prompts management
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                if user_access_list:
                    prompts_text = "💬 **Настройки промптов пользователей:**\n\n"
                    for uid, user_data in user_access_list.items():
                        role_emoji = "👑" if user_data["role"] == "admin" else "👤"
                        prompt_preview = user_data["personal_prompt"][:60] + "..." if len(user_data["personal_prompt"]) > 60 else user_data["personal_prompt"]
                        prompts_text += f"{role_emoji} **@{user_data['username']}** (ID: {uid})\n"
                        prompts_text += f"📝 Промпт: {prompt_preview}\n\n"
                    
                    prompts_text += "🔧 Для изменения промпта используйте команду:\n"
                    prompts_text += "`/set_user_prompt ID новый_промпт`"
                    
                    # Add timestamp to avoid "message not modified" error
                    prompts_text += f"\n\n🕒 Обновлено: {datetime.utcnow().strftime('%H:%M:%S')}"
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=prompts_text,
                        parse_mode="Markdown",
                        reply_markup=get_admin_users_keyboard()
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="📝 Нет пользователей для настройки промптов.",
                        reply_markup=get_admin_users_keyboard()
                    )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_users":
            # Show admin users management
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="👥 Управление пользователями:",
                    reply_markup=get_admin_users_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_export":
            # Show admin export options
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="📊 Экспорт данных:\n\nВыберите тип данных для экспорта в Excel файл.",
                    reply_markup=get_admin_export_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "admin_system":
            # Show admin system settings
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="⚙️ **Системные настройки**\n\nНастройки работы бота и системы:",
                    parse_mode="Markdown",
                    reply_markup=get_admin_system_keyboard()
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data.startswith("export_"):
            # Handle export requests
            data_type = data.replace("export_", "")
            await handle_admin_export(callback_query, data_type)
        elif data == "admin_list_users":
            # Show list of users for admin
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                if user_access_list:
                    users_text = "👥 Список пользователей:\n\n"
                    for uid, user_data in user_access_list.items():
                        role_emoji = "👑" if user_data["role"] == "admin" else "👤"
                        users_text += f"{role_emoji} @{user_data['username']} (ID: {uid}) - {user_data['role']}\n"
                    
                    # Add timestamp to avoid "message not modified" error
                    users_text += f"\n🕒 Обновлено: {datetime.utcnow().strftime('%H:%M:%S')}"
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=users_text,
                        reply_markup=get_admin_users_keyboard()
                    )
                else:
                    # Add timestamp to avoid "message not modified" error
                    empty_text = f"📝 Список пользователей пуст.\n\n🕒 Обновлено: {datetime.utcnow().strftime('%H:%M:%S')}"
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=empty_text,
                        reply_markup=get_admin_users_keyboard()
                    )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "set_steps":
            # Set daily steps
            set_user_state(user_id, "waiting_steps")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🚶 Введите среднее количество шагов в день:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="health_profile")]])
            )
        elif data == "set_workout":
            # Set workout data
            set_user_state(user_id, "waiting_workout")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="""🏃 Введите информацию о тренировках в формате:
тип_тренировки длительность_мин частота_в_неделю [описание]

Примеры:
• теннис 60 4 игра в зале
• бег 30 3 утренние пробежки
• силовая 90 2""",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="health_profile")]])
            )
        elif data == "view_health_history":
            # Show health history
            try:
                history = await get_user_health_history(user_id, days=30)
                
                if history:
                    # Group by data type for better display
                    grouped = {}
                    for entry in history:
                        data_type = entry["data_type"]
                        if data_type not in grouped:
                            grouped[data_type] = []
                        grouped[data_type].append(entry)
                    
                    history_text = "📊 История изменений за 30 дней:\n\n"
                    
                    for data_type, entries in grouped.items():
                        if data_type in ["height", "weight", "age"]:
                            latest = entries[0]
                            history_text += f"📈 **{data_type.title()}:**\n"
                            history_text += f"   Текущее: {latest['value']} {latest['unit']}\n"
                            history_text += f"   Обновлено: {latest['timestamp'].strftime('%d.%m.%Y')}\n"
                            if len(entries) > 1:
                                change = latest['value'] - entries[-1]['value']
                                history_text += f"   Изменение: {change:+.1f} {latest['unit']}\n"
                        elif data_type == "steps":
                            avg_steps = sum(e['value'] for e in entries) / len(entries)
                            history_text += f"🚶 **Шаги:** среднее {avg_steps:.0f}/день ({len(entries)} записей)\n"
                        elif data_type == "workout":
                            history_text += f"🏃 **Тренировки:** {len(entries)} сессий\n"
                            
                        history_text += "\n"
                else:
                    history_text = "📊 История изменений пуста.\n\nНачните добавлять данные о здоровье!"
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=history_text,
                    parse_mode="Markdown",
                    reply_markup=get_health_profile_keyboard()
                )
                
            except Exception as e:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка получения истории: {str(e)}",
                    reply_markup=get_health_profile_keyboard()
                )
        elif data == "edit_movies_prompt":
            await bot.send_message(
                chat_id=chat_id,
                text="📝 Текущий промпт для фильмов:\n\n'Ты эксперт по кинематографу и сериалам'\n\nВведите новый промпт или нажмите 'Назад':",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="prompts")]])
            )
        elif data == "add_movie":
            # Add movie to user's list
            set_user_state(user_id, "waiting_movie")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎬 **Добавить фильм/сериал**\n\nВведите название фильма или сериала, который вы посмотрели:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="movies")]])
            )
        elif data == "get_recommendations":
            # Get movie recommendations
            try:
                user_movies = await get_user_movies(user_id)
                if user_movies:
                    recommendations = await generate_movie_recommendations(user_movies)
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"🎯 **Рекомендации для вас:**\n\n{recommendations}",
                        parse_mode="Markdown",
                        reply_markup=get_movies_keyboard()
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="📝 **Список фильмов пуст**\n\nДобавьте несколько фильмов в свой список, чтобы получить персональные рекомендации!",
                        parse_mode="Markdown",
                        reply_markup=get_movies_keyboard()
                    )
            except Exception as e:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка получения рекомендаций: {str(e)}",
                    reply_markup=get_movies_keyboard()
                )
        elif data == "my_movies":
            # Show user's movie list
            try:
                user_movies = await get_user_movies(user_id)
                if user_movies:
                    movies_text = "🎬 **Ваш список фильмов:**\n\n"
                    for i, movie in enumerate(user_movies[:20], 1):  # Show first 20
                        movies_text += f"{i}. {movie}\n"
                    
                    if len(user_movies) > 20:
                        movies_text += f"\n... и еще {len(user_movies) - 20} фильмов"
                    
                    movies_text += f"\n\n📊 **Всего фильмов:** {len(user_movies)}"
                else:
                    movies_text = "📝 **Список фильмов пуст**\n\nНачните добавлять фильмы, которые вы посмотрели!"
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=movies_text,
                    parse_mode="Markdown",
                    reply_markup=get_movies_keyboard()
                )
            except Exception as e:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка загрузки списка: {str(e)}",
                    reply_markup=get_movies_keyboard()
                )
        elif data == "prompts":
            # Show prompts management
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🔧 **Управление промптами**\n\nНастройте персональные промпты для разных функций бота:",
                parse_mode="Markdown",
                reply_markup=get_prompts_keyboard()
            )
        elif data == "fitness_goal":
            # Show fitness goals
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🎯 **Выберите вашу фитнес цель:**\n\nЭто поможет настроить персональные рекомендации:",
                parse_mode="Markdown",
                reply_markup=get_fitness_goal_keyboard()
            )
        elif data.startswith("goal_"):
            # Handle fitness goal selection
            goal_name = data.replace("goal_", "").replace("_", " ").title()
            await save_user_setting(user_id, "goal", goal_name)
            
            goal_messages = {
                "weight_loss": "🏃 Отличный выбор! Сосредоточимся на здоровом снижении веса.",
                "muscle_gain": "💪 Замечательно! Будем работать над набором мышечной массы.",
                "maintenance": "🔄 Прекрасно! Поможем поддержать текущую форму.",
                "strength": "🏋️ Супер! Сфокусируемся на силовых тренировках."
            }
            
            goal_key = data.replace("goal_", "")
            message = goal_messages.get(goal_key, "✅ Цель сохранена!")
            
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"✅ **Цель установлена: {goal_name}**\n\n{message}",
                parse_mode="Markdown",
                reply_markup=get_settings_keyboard()
            )
        elif data == "toggle_food_analysis":
            # Toggle food analysis in topic (only in groups)
            if callback_query.message.chat.type in ['group', 'supergroup']:
                topic_id = getattr(callback_query.message, 'message_thread_id', None)
                if topic_id:
                    settings = await get_topic_settings(chat_id, topic_id)
                    settings["food_analysis_enabled"] = not settings.get("food_analysis_enabled", True)
                    await save_topic_settings(chat_id, topic_id, settings)
                    
                    status = "включен" if settings["food_analysis_enabled"] else "выключен"
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"✅ Анализ еды в топике {status}",
                        reply_markup=get_topic_settings_keyboard()
                    )
                else:
                    await bot.answer_callback_query(callback_query.id, "❌ Работает только в топиках")
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Работает только в группах")
        elif data == "toggle_auto_analysis":
            # Toggle auto analysis in topic
            if callback_query.message.chat.type in ['group', 'supergroup']:
                topic_id = getattr(callback_query.message, 'message_thread_id', None)
                if topic_id:
                    settings = await get_topic_settings(chat_id, topic_id)
                    settings["auto_analysis"] = not settings.get("auto_analysis", True)
                    await save_topic_settings(chat_id, topic_id, settings)
                    
                    status = "включен" if settings["auto_analysis"] else "выключен (только при @упоминании)"
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"✅ Автоанализ {status}",
                        reply_markup=get_topic_settings_keyboard()
                    )
                else:
                    await bot.answer_callback_query(callback_query.id, "❌ Работает только в топиках")
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Работает только в группах")
        elif data == "quick_actions":
            # Show quick actions menu
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📱 **Быстрые действия**\n\nВыберите действие для быстрого выполнения:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📸 Анализ еды", callback_data="analyze_food_info")],
                    [InlineKeyboardButton("📊 Моя статистика", callback_data="quick_stats_menu")],
                    [InlineKeyboardButton("🤖 AI Чат", callback_data="free_chat")],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
                ])
            )
        elif data == "my_stats":
            # Redirect to quick stats menu
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📊 **Ваша статистика питания:**",
                parse_mode="Markdown",
                reply_markup=get_quick_stats_keyboard()
            )
        elif data == "refresh_menu":
            # Refresh main menu
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                admin_keyboard = [
                    [InlineKeyboardButton("📸 Анализ еды", callback_data="analyze_food_info")],
                    [InlineKeyboardButton("💪 Фитнес советы", callback_data="fitness_advice"), 
                     InlineKeyboardButton("👤 Профиль", callback_data="health_profile")],
                    [InlineKeyboardButton("🤖 AI Чат", callback_data="free_chat"), 
                     InlineKeyboardButton("🎬 Фильмы", callback_data="movies")],
                    [InlineKeyboardButton("📊 Статистика", callback_data="stats_main"), 
                     InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                    [InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")],
                    [InlineKeyboardButton("❌ Закрыть меню", callback_data="close_menu")]
                ]
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"🔄 **Меню обновлено** - {datetime.utcnow().strftime('%H:%M:%S')}\n\n🏠 Главное меню (Администратор):",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(admin_keyboard)
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"🔄 **Меню обновлено** - {datetime.utcnow().strftime('%H:%M:%S')}\n\n🏠 Главное меню:",
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard()
                )
        elif data == "food_settings":
            # Show food settings
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🍽️ **Настройки анализа еды**\n\nНастройте параметры автоматического анализа еды:",
                parse_mode="Markdown",
                reply_markup=get_food_settings_keyboard()
            )
        elif data == "general_settings":
            # Show general settings
            user_data = await get_user_data(user_id)
            settings = user_data.get("settings", {})
            
            settings_text = f"""📊 **Общие настройки**

🤖 **Модель ИИ:** {settings.get('ai_model', 'gpt-3.5-turbo')}
🎯 **Фитнес цель:** {settings.get('goal', 'не установлена')}
📏 **Рост:** {settings.get('height', 'не указан')} см
⚖️ **Вес:** {settings.get('weight', 'не указан')} кг
🎂 **Возраст:** {settings.get('age', 'не указан')} лет

💡 Используйте соответствующие разделы для изменения настроек."""

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=settings_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🤖 Изменить модель", callback_data="ai_model")],
                    [InlineKeyboardButton("🎯 Изменить цель", callback_data="fitness_goal")],
                    [InlineKeyboardButton("👤 Профиль здоровья", callback_data="health_profile")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
                ])
            )
        elif data == "bot_commands":
            # Show bot commands info
            commands_text = """📱 **Команды бота**

**Основные команды:**
• `/start` - Запуск бота и приветствие
• `/menu` - Главное меню (только в приватном чате)
• `/help` - Справка по командам

**Статистика и поиск:**
• `/stats` - Статистика питания
• `/search [запрос]` - Поиск в базе еды

**Изображения:**
• `/image [описание]` - Генерация изображения

**Группы и топики:**
• `/topic_settings` - Настройки топика (только админы)
• `/topic_data` - Данные топика

**Админские команды:**
• `/admin` - Админ панель
• `/add_user [@username] [role]` - Добавить пользователя
• `/remove_user [ID]` - Удалить пользователя
• `/set_user_prompt [ID] [промпт]` - Изменить промпт
• `/my_id` - Показать ваш ID

💡 **Совет:** В группах упоминайте @DMPlove_bot для активации бота"""

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=commands_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="settings")]])
            )
        elif data == "create_command":
            # Show info about creating custom commands
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="➕ **Создание команд**\n\n🚧 Функция находится в разработке.\n\nВ будущих версиях вы сможете создавать собственные команды с персональными промптами.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="settings")]])
            )
        elif data == "my_commands":
            # Show user's custom commands
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="📝 **Мои команды**\n\n📋 У вас пока нет персональных команд.\n\n💡 Используйте кнопку \"Новая команда\" для создания.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="settings")]])
            )
        elif data == "admin_groups":
            # Show admin groups management
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🏢 **Управление группами**\n\nНастройка групп и топиков, где работает бот:",
                parse_mode="Markdown",
                reply_markup=get_admin_groups_keyboard()
            )
        elif data == "admin_list_groups":
            # List all groups where bot is active
            try:
                # Get all topic data to find active groups
                cursor = app.mongodb.topics.find({})
                groups_data = {}
                
                async for topic in cursor:
                    chat_id_key = topic.get("chat_id")
                    if chat_id_key and chat_id_key not in groups_data:
                        groups_data[chat_id_key] = {
                            "topics": [],
                            "total_messages": 0
                        }
                    
                    if chat_id_key:
                        groups_data[chat_id_key]["topics"].append({
                            "topic_id": topic.get("topic_id"),
                            "messages_count": len(topic.get("conversation", []))
                        })
                        groups_data[chat_id_key]["total_messages"] += len(topic.get("conversation", []))
                
                if not groups_data:
                    groups_text = "📋 **Активные группы:** Нет данных\n\nБот еще не использовался в группах с топиками."
                else:
                    groups_text = f"📋 **Активные группы:** {len(groups_data)}\n\n"
                    
                    for i, (group_id, data) in enumerate(groups_data.items(), 1):
                        groups_text += f"{i}. **Группа ID:** {group_id}\n"
                        groups_text += f"   📝 Топиков: {len(data['topics'])}\n"
                        groups_text += f"   💬 Сообщений: {data['total_messages']}\n\n"
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=groups_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_groups")]])
                )
            except Exception as e:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка загрузки групп: {str(e)}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_groups")]])
                )
        elif data == "export_movies_data":
            # Export movies data
            try:
                # Get all movies from database
                cursor = app.mongodb.movies.find({})
                movies_data = []
                
                async for movie in cursor:
                    movies_data.append({
                        "user_id": movie.get("user_id"),
                        "title": movie.get("title"),
                        "rating": movie.get("rating"),
                        "genre": movie.get("genre"),
                        "year": movie.get("year"),
                        "status": movie.get("status"),
                        "review": movie.get("review"),
                        "date_added": movie.get("date_added")
                    })
                
                if not movies_data:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="📋 **Экспорт фильмов**\n\n❌ Нет данных для экспорта",
                        reply_markup=get_admin_export_keyboard()
                    )
                    return
                
                # Create Excel file
                import pandas as pd
                df = pd.DataFrame(movies_data)
                
                # Get usernames for user_ids
                for i, row in df.iterrows():
                    user_id = row['user_id']
                    username = user_access_list.get(user_id, {}).get("username", f"user_{user_id}")
                    df.at[i, 'username'] = username
                
                # Reorder columns
                column_order = ['username', 'user_id', 'title', 'rating', 'genre', 'year', 'status', 'review', 'date_added']
                df = df.reindex(columns=column_order)
                
                # Generate filename
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"movies_export_{timestamp}.xlsx"
                filepath = f"/tmp/{filename}"
                
                # Save to Excel
                df.to_excel(filepath, index=False, sheet_name='Movies')
                
                # Send file
                with open(filepath, 'rb') as file:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        filename=filename,
                        caption=f"📊 **Экспорт фильмов**\n\n📅 Дата: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}\n📽️ Всего фильмов: {len(movies_data)}"
                    )
                
                # Clean up
                os.remove(filepath)
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="✅ **Экспорт фильмов завершен**\n\nФайл отправлен выше.",
                    reply_markup=get_admin_export_keyboard()
                )
                
            except Exception as e:
                logger.error(f"Movies export error: {str(e)}")
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка экспорта фильмов: {str(e)}",
                    reply_markup=get_admin_export_keyboard()
                )
        elif data == "export_topic_data":
            # Export topic data
            try:
                # Get all topic data from database
                cursor = app.mongodb.topics.find({})
                topics_data = []
                
                async for topic in cursor:
                    # Get basic topic info
                    topic_info = {
                        "chat_id": topic.get("chat_id"),
                        "topic_id": topic.get("topic_id"),
                        "settings": topic.get("settings", {}),
                        "messages_count": len(topic.get("conversation", [])),
                        "last_activity": topic.get("last_activity"),
                        "created_date": topic.get("created_date")
                    }
                    
                    # Add conversation summary
                    conversation = topic.get("conversation", [])
                    if conversation:
                        topic_info["first_message_date"] = conversation[0].get("timestamp")
                        topic_info["last_message_date"] = conversation[-1].get("timestamp")
                        
                        # Count message types
                        user_messages = sum(1 for msg in conversation if msg.get("role") == "user")
                        ai_messages = sum(1 for msg in conversation if msg.get("role") == "assistant")
                        topic_info["user_messages"] = user_messages
                        topic_info["ai_messages"] = ai_messages
                    
                    topics_data.append(topic_info)
                
                if not topics_data:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="📋 **Экспорт топиков**\n\n❌ Нет данных для экспорта\n\nТопики появятся после использования бота в группах.",
                        reply_markup=get_admin_export_keyboard()
                    )
                    return
                
                # Create Excel file
                import pandas as pd
                df = pd.DataFrame(topics_data)
                
                # Format settings column
                df['settings_text'] = df['settings'].apply(lambda x: str(x) if x else "Стандартные")
                
                # Reorder columns
                column_order = ['chat_id', 'topic_id', 'messages_count', 'user_messages', 'ai_messages', 
                               'first_message_date', 'last_message_date', 'last_activity', 'created_date', 'settings_text']
                df = df.reindex(columns=[col for col in column_order if col in df.columns])
                
                # Generate filename
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"topics_export_{timestamp}.xlsx"
                filepath = f"/tmp/{filename}"
                
                # Save to Excel
                df.to_excel(filepath, index=False, sheet_name='Topics')
                
                # Send file
                with open(filepath, 'rb') as file:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        filename=filename,
                        caption=f"📊 **Экспорт топиков**\n\n📅 Дата: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}\n📝 Всего топиков: {len(topics_data)}\n💬 Всего сообщений: {sum(t['messages_count'] for t in topics_data)}"
                    )
                
                # Clean up
                os.remove(filepath)
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="✅ **Экспорт топиков завершен**\n\nФайл отправлен выше.",
                    reply_markup=get_admin_export_keyboard()
                )
                
            except Exception as e:
                logger.error(f"Topics export error: {str(e)}")
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ Ошибка экспорта топиков: {str(e)}",
                    reply_markup=get_admin_export_keyboard()
                )
        elif data == "set_topic_prompt":
            # Set custom prompt for topic
            if callback_query.message.chat.type in ['group', 'supergroup']:
                topic_id = getattr(callback_query.message, 'message_thread_id', None)
                if topic_id:
                    set_user_state(user_id, f"setting_topic_prompt_{chat_id}_{topic_id}")
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="💬 **Настройка промпта топика**\n\nВведите новый промпт для ИИ в этом топике:\n\n💡 Промпт определяет, как ИИ будет отвечать на сообщения в данном топике.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="topic_status")]])
                    )
                else:
                    await bot.answer_callback_query(callback_query.id, "❌ Работает только в топиках")
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Работает только в группах")
        elif data == "topic_status":
            # Show topic status and settings
            if callback_query.message.chat.type in ['group', 'supergroup']:
                topic_id = getattr(callback_query.message, 'message_thread_id', None)
                if topic_id:
                    settings = await get_topic_settings(chat_id, topic_id)
                    
                    food_status = "✅ Включен" if settings.get("food_analysis_enabled", True) else "❌ Выключен"
                    auto_status = "✅ Автоматически" if settings.get("auto_analysis", True) else "🔔 Только при @упоминании"
                    delete_delay = settings.get("auto_delete_delay", 300)
                    delete_status = f"⏰ {delete_delay} сек" if delete_delay > 0 else "♾️ Не удалять"
                    
                    prompt_preview = settings.get("custom_prompt", "Стандартный промпт")[:100] + "..." if len(settings.get("custom_prompt", "")) > 100 else settings.get("custom_prompt", "Стандартный промпт")
                    
                    status_text = f"""📋 **Статус топика {topic_id}**

🍽️ **Анализ еды:** {food_status}
🤖 **Режим анализа:** {auto_status}
🗑️ **Автоудаление:** {delete_status}

💬 **Промпт:**
{prompt_preview}

⚙️ Используйте кнопки ниже для изменения настроек."""

                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=status_text,
                        parse_mode="Markdown",
                        reply_markup=get_topic_settings_keyboard()
                    )
                else:
                    await bot.answer_callback_query(callback_query.id, "❌ Работает только в топиках")
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Работает только в группах")
        elif data == "clear_topic_context":
            # Clear topic conversation context
            if callback_query.message.chat.type in ['group', 'supergroup']:
                topic_id = getattr(callback_query.message, 'message_thread_id', None)
                if topic_id:
                    await clear_topic_conversation(chat_id, topic_id)
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text="✅ **Контекст топика очищен**\n\nИИ начнет новый диалог без учета предыдущих сообщений.",
                        parse_mode="Markdown",
                        reply_markup=get_topic_settings_keyboard()
                    )
                else:
                    await bot.answer_callback_query(callback_query.id, "❌ Работает только в топиках")
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Работает только в группах")
        
        # System settings handlers
        elif data == "system_bot_settings":
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="🔧 **Настройки бота**\n\nОсновные настройки работы бота:\n\n• Токен: ✅ Настроен\n• OpenAI API: ✅ Настроен\n• База данных: ✅ Подключена\n• Webhook: ✅ Активен",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_system")]])
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "system_stats":
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                # Get system statistics
                try:
                    # Count collections
                    users_count = await app.mongodb.users.count_documents({})
                    food_count = await app.mongodb.food_analysis.count_documents({})
                    movies_count = await app.mongodb.movies.count_documents({})
                    topics_count = await app.mongodb.topics.count_documents({})
                    
                    stats_text = f"""📊 **Системная статистика**
                    
👥 Пользователи: {users_count}
🍽️ Записи о еде: {food_count}
🎬 Фильмы: {movies_count}
📋 Топики: {topics_count}

🤖 Статус: Работает
💾 База данных: Подключена
🌐 Webhook: Активен"""
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=stats_text,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_system")]])
                    )
                except Exception as e:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"❌ Ошибка получения статистики: {str(e)}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_system")]])
                    )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        elif data == "system_webhook":
            user_role = await get_user_role(user_id)
            if user_role == "admin":
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text="🌐 **Настройки Webhook**\n\nТекущий webhook:\n`https://baseshinomontaz.store/webhook.php`\n\n✅ Постоянный домен установлен!\n\n📝 Proxy скрипт настроен для перенаправления на VPS.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_system")]])
                )
            else:
                await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен.")
        
        # Debug log successful callback query
        response_time = time.time() - start_time
        debug_logger.log_callback_query(
            user_id=user_id,
            callback_data=data,
            success=True,
            response_time=response_time
        )
        
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="callback_query_response",
            input_data={"callback_data": data},
            output_data={"success": True},
            response_time=response_time
        )
        
    except Exception as e:
        logger.error(f"Callback query error for user {user_id}, data '{data}': {str(e)}")
        logger.error(f"Callback query details: message_date={callback_query.message.date if callback_query.message else 'None'}, current_time={time.time()}")
        
        # Debug log error
        response_time = time.time() - start_time
        debug_logger.log_callback_query(
            user_id=user_id,
            callback_data=data,
            success=False,
            error=str(e),
            response_time=response_time
        )
        
        debug_logger.log_user_interaction(
            user_id=user_id,
            username=user_access_list.get(user_id, {}).get("username", "unknown"),
            interaction_type="callback_query_response",
            input_data={"callback_data": data},
            output_data=None,
            response_time=response_time,
            error=str(e)
        )
        
        # Try to answer callback query if not already answered
        try:
            await bot.answer_callback_query(callback_query.id, "❌ Ошибка обработки")
        except Exception as answer_error:
            logger.warning(f"Could not answer callback query: {str(answer_error)}")
            
        # Send error message only if it's not a "query too old" error
        if "Query is too old" not in str(e):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Ошибка: {str(e)}"
                )
            except Exception as send_error:
                logger.error(f"Could not send error message: {str(send_error)}")
        else:
            logger.info("Skipped sending 'query too old' error message to avoid spam")

# Webhook endpoint
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        update_data = await request.json()
        logger.info(f"Received webhook update: {update_data.get('update_id', 'unknown')}")
        
        update = Update.de_json(update_data, bot)

        if update.message:
            logger.info(f"Processing message from {update.message.from_user.username} in chat {update.message.chat.id}")
            await handle_message(update.message)
        elif update.callback_query:
            logger.info(f"Processing callback query: {update.callback_query.data}")
            await handle_callback_query(update.callback_query)
        else:
            logger.info(f"Unhandled update type in update: {update.update_id}")

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        logger.error(f"Update data: {update_data if 'update_data' in locals() else 'No data'}")
        # Return 200 OK even on error to prevent Telegram from retrying
        return {"status": "error", "message": str(e)}

# API endpoints
@app.get("/api/debug/status")
async def get_debug_status():
    """Получить статус системы отладки"""
    try:
        debug_logger = get_debug_logger()
        return {
            "debug_mode": is_debug_mode(),
            "stats": debug_logger.get_debug_stats(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "debug_mode": False}

@app.get("/api/debug/report")
async def get_debug_report():
    """Получить полный отчет отладки"""
    try:
        if not is_debug_mode():
            return {"error": "Debug mode is not enabled"}
        
        debug_logger = get_debug_logger()
        report = debug_logger.export_debug_report()
        
        return report
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/clear")
async def clear_debug_data():
    """Очистить данные отладки"""
    try:
        if not is_debug_mode():
            return {"error": "Debug mode is not enabled"}
        
        debug_logger = get_debug_logger()
        debug_logger.clear_debug_data()
        
        return {"success": True, "message": "Debug data cleared"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug")
async def debug_monitor():
    """Веб-интерфейс для мониторинга отладки"""
    from fastapi.responses import FileResponse
    return FileResponse('/app/debug_monitor.html')

@app.get("/api/debug/toggle/{mode}")
async def toggle_debug_mode(mode: str):
    """Включить/выключить режим отладки"""
    try:
        if mode not in ["on", "off"]:
            return {"error": "Mode must be 'on' or 'off'"}
        
        debug_mode = mode == "on"
        init_debug_mode(debug_mode)
        
        return {
            "success": True,
            "debug_mode": debug_mode,
            "message": f"Debug mode {'enabled' if debug_mode else 'disabled'}"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/system/status")
async def get_system_status():
    """Получить статус системы надежности и UX"""
    try:
        # Get OpenAI reliability status
        reliable_client = get_reliable_openai_client()
        openai_status = reliable_client.get_status()
        
        # Get UX manager stats
        ux_stats = ux_manager.get_system_stats()
        
        # Get database status
        try:
            # Simple DB ping
            await app.mongodb.command("ping")
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": db_status,
                "openai_reliability": openai_status,
                "user_experience": ux_stats
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/api/stats/{user_id}")
async def get_user_stats(user_id: int):
    """Get user statistics"""
    try:
        today_stats = await get_food_stats(user_id, "today")
        week_stats = await get_food_stats(user_id, "week")
        month_stats = await get_food_stats(user_id, "month")
        
        return {
            "today": today_stats,
            "week": week_stats,
            "month": month_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/set_webhook")
async def set_webhook():
    """Set webhook for Telegram bot"""
    try:
        # Use the permanent domain baseshinomontaz.store
        webhook_url = "https://baseshinomontaz.store/webhook.php"
        await bot.set_webhook(url=webhook_url)
        return {"status": "webhook set", "url": webhook_url}
    except Exception as e:
        logger.error(f"Webhook setup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)