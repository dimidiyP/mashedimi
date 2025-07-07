"""Handlers for movie expert functionality"""

import logging
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.utils import create_keyboard, get_current_timestamp, is_valid_rating
from .services import MovieExpertService, MovieAIService
from .models import MovieEntry

logger = logging.getLogger(__name__)

class MovieExpertHandlers:
    """Handlers for movie expert functionality"""
    
    def __init__(self):
        self.movie_service = MovieExpertService()
        self.ai_service = MovieAIService()
    
    async def handle_movie_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show movie expert menu"""
        try:
            user_id = update.effective_user.id
            
            # Get user stats
            stats = await self.movie_service.get_user_stats(user_id)
            
            menu_text = "🎬 **КИНОЭКСПЕРТ**\n\n"
            
            if stats.total_movies > 0 or stats.total_series > 0:
                menu_text += f"📊 **ВАША СТАТИСТИКА:**\n"
                menu_text += f"🎥 Фильмов: {stats.total_movies}\n"
                menu_text += f"📺 Сериалов: {stats.total_series}\n"
                menu_text += f"⭐ Средняя оценка: {stats.average_rating}/10\n"
                menu_text += f"⏱️ Время просмотра: {stats.total_watch_time//60}ч {stats.total_watch_time%60}м\n"
                
                if stats.favorite_genres:
                    menu_text += f"🎭 Любимые жанры: {', '.join(stats.favorite_genres[:3])}\n"
                
                menu_text += f"📅 За этот месяц: {stats.movies_this_month}\n"
                menu_text += f"📆 За этот год: {stats.movies_this_year}\n"
                
                if stats.highest_rated_movie:
                    menu_text += f"🏆 Лучший: {stats.highest_rated_movie}\n"
            else:
                menu_text += "📝 Добавьте первый фильм для начала отслеживания!\n\n"
                menu_text += "💡 **Как добавить фильм:**\n"
                menu_text += "Напишите: 'Посмотрел [название] оценка 8/10'\n"
                menu_text += "Пример: 'Посмотрел Интерстеллар оценка 9/10'\n"
            
            # Menu buttons
            keyboard = [
                [
                    InlineKeyboardButton("➕ Добавить фильм", callback_data="movie_add"),
                    InlineKeyboardButton("🔍 Поиск", callback_data="movie_search")
                ],
                [
                    InlineKeyboardButton("💡 Рекомендации", callback_data="movie_recommendations"),
                    InlineKeyboardButton("📊 Статистика", callback_data="movie_stats")
                ],
                [
                    InlineKeyboardButton("📋 Мои фильмы", callback_data="movie_list"),
                    InlineKeyboardButton("⭐ Топ фильмы", callback_data="movie_top")
                ],
                [
                    InlineKeyboardButton("📤 Экспорт", callback_data="movie_export"),
                    InlineKeyboardButton("❌ Закрыть", callback_data="close_menu")
                ]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    menu_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    menu_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            logger.error(f"Error showing movie menu: {e}")
            await update.effective_message.reply_text("❌ Ошибка загрузки меню фильмов")
    
    async def handle_movie_recommendations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show movie recommendations"""
        try:
            query = update.callback_query
            await query.answer("🤖 Генерирую рекомендации...")
            
            user_id = update.effective_user.id
            
            # Get recommendations
            recommendations = await self.movie_service.get_recommendations(user_id, 5)
            
            if not recommendations:
                text = "🤷‍♂️ **НЕТ РЕКОМЕНДАЦИЙ**\n\n"
                text += "Добавьте больше фильмов для получения персональных рекомендаций!\n\n"
                text += "💡 Напишите: 'Посмотрел [название] оценка X/10'"
            else:
                text = "🎬 **ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ**\n\n"
                
                for i, rec in enumerate(recommendations, 1):
                    media_type = "📺 Сериал" if rec.is_series else "🎥 Фильм"
                    
                    text += f"**{i}. {rec.title}**"
                    if rec.year:
                        text += f" ({rec.year})"
                    text += f"\n{media_type}"
                    
                    if rec.genre:
                        text += f" | {', '.join(rec.genre[:2])}"
                    text += "\n"
                    
                    if rec.director:
                        text += f"🎭 Режиссер: {rec.director}\n"
                    
                    if rec.description:
                        text += f"📝 {rec.description}\n"
                    
                    text += f"💡 **Почему:** {rec.reason}\n"
                    text += f"🎯 Уверенность: {rec.confidence*100:.0f}%\n\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Новые рекомендации", callback_data="movie_recommendations"),
                    InlineKeyboardButton("◀️ Назад", callback_data="movie_menu")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing recommendations: {e}")
            await update.callback_query.answer("❌ Ошибка получения рекомендаций")
    
    async def handle_movie_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user's movie list"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            # Get user's movies
            movies = await self.movie_service.get_user_movies(user_id, 20)
            
            if not movies:
                text = "📭 **СПИСОК ПУСТ**\n\n"
                text += "Вы еще не добавили ни одного фильма.\n\n"
                text += "💡 Напишите: 'Посмотрел [название] оценка X/10'"
            else:
                text = f"📋 **МОИ ФИЛЬМЫ** (последние {len(movies)})\n\n"
                
                for movie in movies:
                    media_type = "📺" if movie.is_series else "🎥"
                    date_str = movie.watch_date.strftime("%d.%m.%Y")
                    
                    text += f"{media_type} **{movie.title}**"
                    if movie.year:
                        text += f" ({movie.year})"
                    text += f" - ⭐{movie.rating}/10\n"
                    
                    if movie.genre:
                        text += f"🎭 {', '.join(movie.genre[:2])}\n"
                    
                    text += f"📅 {date_str}"
                    
                    if movie.review:
                        review_short = movie.review[:50] + "..." if len(movie.review) > 50 else movie.review
                        text += f"\n💭 {review_short}"
                    
                    text += "\n\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔍 Поиск", callback_data="movie_search"),
                    InlineKeyboardButton("📤 Экспорт", callback_data="movie_export")
                ],
                [
                    InlineKeyboardButton("◀️ Назад", callback_data="movie_menu")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing movie list: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки списка фильмов")
    
    async def handle_movie_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show detailed movie statistics"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            # Get detailed stats
            stats = await self.movie_service.get_user_stats(user_id)
            
            text = "📊 **ПОДРОБНАЯ СТАТИСТИКА**\n\n"
            
            if stats.total_movies == 0 and stats.total_series == 0:
                text += "📭 Нет данных для статистики\n\n"
                text += "Добавьте фильмы для просмотра статистики!"
            else:
                # General stats
                text += f"🎥 **Фильмы:** {stats.total_movies}\n"
                text += f"📺 **Сериалы:** {stats.total_series}\n"
                text += f"🎬 **Всего:** {stats.total_movies + stats.total_series}\n\n"
                
                # Time and ratings
                total_hours = stats.total_watch_time // 60
                total_minutes = stats.total_watch_time % 60
                text += f"⏱️ **Время просмотра:** {total_hours}ч {total_minutes}м\n"
                text += f"⭐ **Средняя оценка:** {stats.average_rating}/10\n\n"
                
                # Period stats
                text += f"📅 **За этот месяц:** {stats.movies_this_month}\n"
                text += f"📆 **За этот год:** {stats.movies_this_year}\n\n"
                
                # Favorites
                if stats.favorite_genres:
                    text += f"🎭 **Любимые жанры:**\n"
                    for genre in stats.favorite_genres[:5]:
                        text += f"• {genre}\n"
                    text += "\n"
                
                # Best/worst
                if stats.highest_rated_movie:
                    text += f"🏆 **Лучший:** {stats.highest_rated_movie}\n"
                if stats.lowest_rated_movie:
                    text += f"👎 **Худший:** {stats.lowest_rated_movie}\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("📈 Тренды", callback_data="movie_trends"),
                    InlineKeyboardButton("🏆 Топ-10", callback_data="movie_top")
                ],
                [
                    InlineKeyboardButton("◀️ Назад", callback_data="movie_menu")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing movie stats: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки статистики")
    
    async def handle_movie_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle movie-related text messages"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            # Process with AI service
            response = await self.ai_service.process_movie_message(user_id, message_text)
            
            # Add action buttons if movie was saved
            if "сохранен" in response:
                keyboard = [
                    [
                        InlineKeyboardButton("🎬 Меню фильмов", callback_data="movie_menu"),
                        InlineKeyboardButton("💡 Рекомендации", callback_data="movie_recommendations")
                    ]
                ]
                
                await update.message.reply_text(
                    response,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(response, parse_mode="Markdown")
        
        except Exception as e:
            logger.error(f"Error handling movie message: {e}")
            await update.message.reply_text("❌ Ошибка обработки сообщения о фильмах")
    
    async def handle_movie_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle movie search"""
        try:
            query = update.callback_query
            
            # For now, show instruction
            text = "🔍 **ПОИСК ФИЛЬМОВ**\n\n"
            text += "Напишите название фильма, жанр, режиссера или ключевые слова для поиска в вашей коллекции.\n\n"
            text += "Примеры:\n"
            text += "• 'Интерстеллар'\n"
            text += "• 'Нолан'\n"
            text += "• 'фантастика'\n"
            text += "• 'космос'"
            
            keyboard = [
                [InlineKeyboardButton("◀️ Назад", callback_data="movie_menu")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error handling movie search: {e}")
            await update.callback_query.answer("❌ Ошибка поиска")
    
    async def handle_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Handle actual search query"""
        try:
            user_id = update.effective_user.id
            
            # Search in user's movies
            movies = await self.movie_service.search_user_movies(user_id, query)
            
            if not movies:
                text = f"🔍 **ПОИСК: '{query}'**\n\n"
                text += "❌ Ничего не найдено в вашей коллекции"
            else:
                text = f"🔍 **ПОИСК: '{query}'**\n\n"
                text += f"Найдено {len(movies)} результат(ов):\n\n"
                
                for movie in movies[:10]:  # Limit to 10 results
                    media_type = "📺" if movie.is_series else "🎥"
                    text += f"{media_type} **{movie.title}**"
                    if movie.year:
                        text += f" ({movie.year})"
                    text += f" - ⭐{movie.rating}/10\n"
                    
                    if movie.genre:
                        text += f"🎭 {', '.join(movie.genre[:2])}\n"
                    
                    if movie.review and query.lower() in movie.review.lower():
                        text += f"💭 ...{movie.review[:100]}...\n"
                    
                    text += "\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("🎬 Меню", callback_data="movie_menu"),
                    InlineKeyboardButton("🔍 Новый поиск", callback_data="movie_search")
                ]
            ]
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error handling search query: {e}")
            await update.message.reply_text("❌ Ошибка поиска")
    
    async def handle_close_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Close menu"""
        try:
            await update.callback_query.delete_message()
        except Exception as e:
            logger.error(f"Error closing menu: {e}")
            await update.callback_query.answer("❌ Не удалось закрыть меню")