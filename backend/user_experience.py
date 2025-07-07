#!/usr/bin/env python3
"""
Система улучшения пользовательского опыта (UX)
Основана на анализе проблем реальных Telegram ботов с ChatGPT
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class UserExperienceManager:
    """Менеджер пользовательского опыта для 24/7 операций"""
    
    def __init__(self):
        # Typing indicators management
        self.typing_tasks = {}
        
        # Response time tracking
        self.response_times = {}
        self.slow_response_threshold = 5.0  # seconds
        
        # User session management
        self.user_sessions = {}
        self.session_timeout = 1800  # 30 minutes
        
        # Error tracking per user
        self.user_error_counts = {}
        self.error_reset_interval = 3600  # 1 hour
        
        # Queue management for busy periods
        self.request_queue = asyncio.Queue()
        self.max_queue_size = 100
        self.processing_requests = set()
        
    async def start_typing_indicator(self, bot, chat_id: int, user_id: int):
        """Запустить индикатор печати для длительных операций"""
        typing_key = f"{chat_id}_{user_id}"
        
        # Cancel existing typing task
        if typing_key in self.typing_tasks:
            self.typing_tasks[typing_key].cancel()
        
        async def keep_typing():
            try:
                while True:
                    await bot.send_chat_action(chat_id=chat_id, action="typing")
                    await asyncio.sleep(4)  # Telegram typing indicator lasts 5 seconds
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"Typing indicator error: {str(e)}")
        
        self.typing_tasks[typing_key] = asyncio.create_task(keep_typing())
    
    def stop_typing_indicator(self, chat_id: int, user_id: int):
        """Остановить индикатор печати"""
        typing_key = f"{chat_id}_{user_id}"
        
        if typing_key in self.typing_tasks:
            self.typing_tasks[typing_key].cancel()
            del self.typing_tasks[typing_key]
    
    def start_response_timer(self, user_id: int) -> float:
        """Начать отсчет времени ответа"""
        start_time = time.time()
        self.response_times[user_id] = start_time
        return start_time
    
    def end_response_timer(self, user_id: int) -> float:
        """Закончить отсчет и вернуть время ответа"""
        if user_id not in self.response_times:
            return 0.0
        
        end_time = time.time()
        response_time = end_time - self.response_times[user_id]
        del self.response_times[user_id]
        
        # Log slow responses
        if response_time > self.slow_response_threshold:
            logger.warning(f"Slow response for user {user_id}: {response_time:.2f}s")
        
        return response_time
    
    async def show_progress_message(self, bot, chat_id: int, operation: str) -> int:
        """Показать сообщение о прогрессе операции"""
        progress_messages = {
            "ai_thinking": "🤔 Обрабатываю ваш запрос...",
            "food_analysis": "📸 Анализирую изображение еды...",
            "movie_recommendations": "🎬 Подбираю персональные рекомендации...",
            "statistics": "📊 Собираю статистику...",
            "export": "📦 Подготавливаю экспорт данных...",
            "search": "🔍 Ищу в базе данных..."
        }
        
        message_text = progress_messages.get(operation, "⏳ Выполняю операцию...")
        
        try:
            message = await bot.send_message(chat_id=chat_id, text=message_text)
            return message.message_id
        except Exception as e:
            logger.warning(f"Could not send progress message: {str(e)}")
            return None
    
    async def update_progress_message(self, bot, chat_id: int, message_id: int, progress: str):
        """Обновить сообщение о прогрессе"""
        if not message_id:
            return
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=progress
            )
        except Exception as e:
            logger.warning(f"Could not update progress message: {str(e)}")
    
    async def delete_progress_message(self, bot, chat_id: int, message_id: int):
        """Удалить сообщение о прогрессе"""
        if not message_id:
            return
        
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.warning(f"Could not delete progress message: {str(e)}")
    
    def track_user_error(self, user_id: int, error_type: str):
        """Отследить ошибку пользователя"""
        current_time = time.time()
        
        if user_id not in self.user_error_counts:
            self.user_error_counts[user_id] = {}
        
        if error_type not in self.user_error_counts[user_id]:
            self.user_error_counts[user_id][error_type] = []
        
        # Add error timestamp
        self.user_error_counts[user_id][error_type].append(current_time)
        
        # Clean old errors
        cutoff_time = current_time - self.error_reset_interval
        self.user_error_counts[user_id][error_type] = [
            ts for ts in self.user_error_counts[user_id][error_type] 
            if ts > cutoff_time
        ]
    
    def get_user_error_count(self, user_id: int, error_type: str) -> int:
        """Получить количество ошибок пользователя за последний час"""
        if user_id not in self.user_error_counts:
            return 0
        
        if error_type not in self.user_error_counts[user_id]:
            return 0
        
        return len(self.user_error_counts[user_id][error_type])
    
    def should_show_help_hint(self, user_id: int, error_type: str) -> bool:
        """Определить, нужно ли показать подсказку пользователю"""
        error_count = self.get_user_error_count(user_id, error_type)
        
        # Show help after 3 errors of the same type
        return error_count >= 3
    
    async def add_to_queue(self, request_data: Dict[str, Any]) -> bool:
        """Добавить запрос в очередь обработки"""
        if self.request_queue.qsize() >= self.max_queue_size:
            logger.warning("Request queue is full")
            return False
        
        await self.request_queue.put(request_data)
        return True
    
    async def get_queue_position(self, user_id: int) -> Optional[int]:
        """Получить позицию в очереди"""
        # This is simplified - in real implementation you'd track user positions
        return self.request_queue.qsize() if self.request_queue.qsize() > 0 else None
    
    def get_user_session(self, user_id: int) -> Dict[str, Any]:
        """Получить сессию пользователя"""
        current_time = time.time()
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            
            # Check if session expired
            if current_time - session["last_activity"] > self.session_timeout:
                del self.user_sessions[user_id]
            else:
                # Update last activity
                session["last_activity"] = current_time
                return session
        
        # Create new session
        new_session = {
            "start_time": current_time,
            "last_activity": current_time,
            "request_count": 0,
            "context": {},
            "preferences": {}
        }
        
        self.user_sessions[user_id] = new_session
        return new_session
    
    def increment_user_requests(self, user_id: int):
        """Увеличить счетчик запросов пользователя"""
        session = self.get_user_session(user_id)
        session["request_count"] += 1
    
    def is_user_active(self, user_id: int) -> bool:
        """Проверить, активен ли пользователь"""
        return user_id in self.user_sessions
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        current_time = time.time()
        
        # Active sessions
        active_sessions = len(self.user_sessions)
        
        # Total requests in last hour
        total_requests = sum(
            session["request_count"] 
            for session in self.user_sessions.values()
            if current_time - session["start_time"] < 3600
        )
        
        # Queue stats
        queue_size = self.request_queue.qsize()
        processing_count = len(self.processing_requests)
        
        return {
            "active_sessions": active_sessions,
            "total_requests_last_hour": total_requests,
            "queue_size": queue_size,
            "processing_requests": processing_count,
            "typing_indicators": len(self.typing_tasks)
        }

class UserFeedbackCollector:
    """Система сбора обратной связи от пользователей"""
    
    def __init__(self):
        self.feedback_data = {}
        
    async def collect_response_rating(self, bot, user_id: int, chat_id: int, message_id: int):
        """Попросить пользователя оценить ответ"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        rating_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍", callback_data=f"rate_positive_{message_id}"),
                InlineKeyboardButton("👎", callback_data=f"rate_negative_{message_id}")
            ],
            [InlineKeyboardButton("🤷‍♂️ Пропустить", callback_data=f"rate_skip_{message_id}")]
        ])
        
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="💡 Помогите улучшить бота - оцените ответ:",
                reply_markup=rating_keyboard,
                reply_to_message_id=message_id
            )
        except Exception as e:
            logger.warning(f"Could not send rating request: {str(e)}")
    
    def record_feedback(self, user_id: int, message_id: int, rating: str, context: str = ""):
        """Записать обратную связь"""
        if user_id not in self.feedback_data:
            self.feedback_data[user_id] = []
        
        feedback_entry = {
            "timestamp": time.time(),
            "message_id": message_id,
            "rating": rating,
            "context": context
        }
        
        self.feedback_data[user_id].append(feedback_entry)
        logger.info(f"Recorded feedback: user={user_id}, rating={rating}")
    
    def get_user_satisfaction_score(self, user_id: int) -> float:
        """Получить индекс удовлетворенности пользователя"""
        if user_id not in self.feedback_data:
            return 0.5  # Neutral
        
        feedback_list = self.feedback_data[user_id]
        if not feedback_list:
            return 0.5
        
        # Calculate ratio of positive feedback
        positive_count = sum(1 for f in feedback_list if f["rating"] == "positive")
        total_count = sum(1 for f in feedback_list if f["rating"] in ["positive", "negative"])
        
        if total_count == 0:
            return 0.5
        
        return positive_count / total_count

# Глобальные экземпляры
ux_manager = UserExperienceManager()
feedback_collector = UserFeedbackCollector()