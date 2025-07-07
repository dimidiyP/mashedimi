"""Utility functions for the bot"""

import logging
import base64
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import requests
from io import BytesIO
from PIL import Image
import json

logger = logging.getLogger(__name__)

def generate_uuid() -> str:
    """Generate a unique identifier"""
    return str(uuid.uuid4())

def get_current_timestamp() -> datetime:
    """Get current timestamp"""
    return datetime.now()

def format_timestamp(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format timestamp to string"""
    return dt.strftime(format_str)

def parse_timestamp(ts_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse timestamp from string"""
    return datetime.strptime(ts_str, format_str)

def get_date_range(period: str) -> tuple:
    """Get date range for a given period"""
    now = datetime.now()
    
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "month":
        start = now - timedelta(days=30)
        end = now
    else:
        start = now - timedelta(days=7)  # Default to week
        end = now
    
    return start, end

def create_keyboard(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
    """Create inline keyboard markup"""
    keyboard = []
    for row in buttons:
        keyboard_row = []
        for button in row:
            keyboard_row.append(
                InlineKeyboardButton(
                    text=button["text"],
                    callback_data=button["callback_data"]
                )
            )
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)

def download_image_as_base64(file_url: str) -> Optional[str]:
    """Download image from URL and convert to base64"""
    try:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        
        # Convert to base64
        image_data = base64.b64encode(response.content).decode('utf-8')
        return image_data
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None

def validate_image_size(image_data: bytes, max_size: int = 20 * 1024 * 1024) -> bool:
    """Validate image size"""
    return len(image_data) <= max_size

def resize_image_if_needed(image_data: bytes, max_size: int = 4 * 1024 * 1024) -> bytes:
    """Resize image if it's too large"""
    try:
        if len(image_data) <= max_size:
            return image_data
        
        # Open image
        image = Image.open(BytesIO(image_data))
        
        # Calculate new size
        reduction_factor = (max_size / len(image_data)) ** 0.5
        new_width = int(image.width * reduction_factor)
        new_height = int(image.height * reduction_factor)
        
        # Resize image
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = BytesIO()
        format_map = {
            'JPEG': 'JPEG',
            'PNG': 'PNG',
            'WEBP': 'WEBP'
        }
        
        format_to_use = format_map.get(image.format, 'JPEG')
        resized_image.save(output, format=format_to_use, quality=85)
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return image_data

def calculate_calories_from_macros(protein: float, carbs: float, fat: float) -> float:
    """Calculate calories from macronutrients"""
    return (protein * 4) + (carbs * 4) + (fat * 9)

def validate_nutrition_data(nutrition: Dict[str, Any]) -> bool:
    """Validate nutrition data"""
    required_fields = ['calories', 'protein', 'carbs', 'fat']
    
    for field in required_fields:
        if field not in nutrition:
            return False
        if not isinstance(nutrition[field], (int, float)):
            return False
        if nutrition[field] < 0:
            return False
    
    return True

def format_nutrition_text(nutrition: Dict[str, Any]) -> str:
    """Format nutrition data for display"""
    return (
        f"🔥 Калории: {nutrition.get('calories', 0):.0f} ккал\n"
        f"🥩 Белки: {nutrition.get('protein', 0):.1f} г\n"
        f"🍞 Углеводы: {nutrition.get('carbs', 0):.1f} г\n"
        f"🥑 Жиры: {nutrition.get('fat', 0):.1f} г"
    )

def sanitize_text(text: str) -> str:
    """Sanitize text for Telegram"""
    # Remove or replace problematic characters
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('&', '&amp;')
    return text

def extract_mentions(text: str) -> List[str]:
    """Extract mentions from text"""
    mentions = []
    words = text.split()
    
    for word in words:
        if word.startswith('@') and len(word) > 1:
            mentions.append(word[1:])  # Remove @ symbol
    
    return mentions

def remove_mentions(text: str, mentions: List[str]) -> str:
    """Remove mentions from text"""
    for mention in mentions:
        text = text.replace(f"@{mention}", "").strip()
    
    return text

def hash_text(text: str) -> str:
    """Create hash from text"""
    return hashlib.md5(text.encode()).hexdigest()

def chunk_text(text: str, max_length: int = 4096) -> List[str]:
    """Split text into chunks for Telegram"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def is_valid_rating(rating: Union[int, float, str]) -> bool:
    """Validate movie rating"""
    try:
        rating_float = float(rating)
        return 1 <= rating_float <= 10
    except (ValueError, TypeError):
        return False

def normalize_rating(rating: Union[int, float, str]) -> float:
    """Normalize rating to float"""
    try:
        rating_float = float(rating)
        return max(1.0, min(10.0, rating_float))
    except (ValueError, TypeError):
        return 5.0  # Default rating

def extract_food_keywords(text: str) -> List[str]:
    """Extract food-related keywords from text"""
    food_keywords = [
        'еда', 'пища', 'блюдо', 'завтрак', 'обед', 'ужин', 'перекус',
        'калории', 'белки', 'жиры', 'углеводы', 'питание', 'диета',
        'рецепт', 'готовка', 'приготовление', 'ингредиенты'
    ]
    
    text_lower = text.lower()
    found_keywords = []
    
    for keyword in food_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

def extract_movie_keywords(text: str) -> List[str]:
    """Extract movie-related keywords from text"""
    movie_keywords = [
        'фильм', 'кино', 'фильмы', 'сериал', 'сериалы', 'фильмец',
        'посмотрел', 'посмотрела', 'смотрел', 'смотрела', 'просмотр',
        'рекомендация', 'рекомендации', 'советую', 'посоветуй',
        'рейтинг', 'оценка', 'звезды', 'актер', 'актриса', 'режиссер'
    ]
    
    text_lower = text.lower()
    found_keywords = []
    
    for keyword in movie_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

def clean_json_string(json_str: str) -> str:
    """Clean JSON string from AI response"""
    # Remove common AI response wrappers
    json_str = json_str.strip()
    
    # Remove markdown code blocks
    if json_str.startswith('```json'):
        json_str = json_str[7:]
    if json_str.startswith('```'):
        json_str = json_str[3:]
    if json_str.endswith('```'):
        json_str = json_str[:-3]
    
    return json_str.strip()

def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON response from AI"""
    try:
        cleaned = clean_json_string(response)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing JSON response: {e}")
        return None