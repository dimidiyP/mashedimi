"""Handlers for food and health functionality"""

import logging
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.utils import (
    download_image_as_base64, format_nutrition_text, 
    create_keyboard, get_current_timestamp
)
from .services import FoodAnalysisService, HealthProfileService, HealthAIService
from .models import WorkoutSession, StepsData

logger = logging.getLogger(__name__)

class FoodHealthHandlers:
    """Handlers for food and health functionality"""
    
    def __init__(self):
        self.food_service = FoodAnalysisService()
        self.health_service = HealthProfileService()
        self.ai_service = HealthAIService()
    
    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages for food analysis"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            message_id = update.message.message_id
            
            # Get photo with highest resolution
            photo = update.message.photo[-1]
            
            # Get file URL
            file = await context.bot.get_file(photo.file_id)
            file_url = file.file_path
            
            # Download and convert to base64
            status_message = await update.message.reply_text(
                "🔍 Анализирую изображение еды...",
                reply_to_message_id=message_id
            )
            
            image_base64 = download_image_as_base64(file_url)
            if not image_base64:
                await status_message.edit_text("❌ Не удалось загрузить изображение")
                return
            
            # Analyze food
            analysis = await self.food_service.analyze_food_image(
                image_base64, user_id, chat_id, message_id
            )
            
            if not analysis or not analysis.food_items:
                await status_message.edit_text(
                    "🤷‍♂️ На изображении не обнаружено еды или не удалось проанализировать"
                )
                return
            
            # Format response
            response_text = "🍽️ **АНАЛИЗ ЕДЫ**\n\n"
            
            for i, food_item in enumerate(analysis.food_items, 1):
                response_text += f"**{i}. {food_item.name}**\n"
                if food_item.description:
                    response_text += f"_{food_item.description}_\n"
                response_text += f"📏 Порция: {food_item.portion_size}г\n"
                
                if food_item.nutrition:
                    response_text += f"🔥 {food_item.nutrition.calories:.0f} ккал\n"
                    response_text += f"🥩 Белки: {food_item.nutrition.protein:.1f}г\n"
                    response_text += f"🍞 Углеводы: {food_item.nutrition.carbs:.1f}г\n"
                    response_text += f"🥑 Жиры: {food_item.nutrition.fat:.1f}г\n"
                
                response_text += f"📊 Уверенность: {food_item.confidence*100:.0f}%\n\n"
            
            # Total nutrition
            if analysis.total_nutrition:
                response_text += "**📊 ИТОГО:**\n"
                response_text += format_nutrition_text(analysis.total_nutrition.to_dict())
            
            # Create action buttons
            keyboard = [
                [
                    InlineKeyboardButton("📈 Статистика", callback_data=f"food_stats_{user_id}"),
                    InlineKeyboardButton("🎯 Цели", callback_data=f"health_goals_{user_id}")
                ],
                [
                    InlineKeyboardButton("💡 Совет", callback_data=f"health_advice_{user_id}"),
                    InlineKeyboardButton("🔍 Поиск", callback_data=f"food_search_{user_id}")
                ]
            ]
            
            await status_message.edit_text(
                response_text, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error handling photo message: {e}")
            await update.message.reply_text("❌ Произошла ошибка при анализе изображения")
    
    async def handle_health_profile_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show health profile menu"""
        try:
            user_id = update.effective_user.id
            profile = await self.health_service.get_or_create_profile(user_id)
            
            # Format profile info
            profile_text = "👤 **ПРОФИЛЬ ЗДОРОВЬЯ**\n\n"
            
            if profile.age:
                profile_text += f"🎂 Возраст: {profile.age} лет\n"
            if profile.gender:
                profile_text += f"👫 Пол: {profile.gender}\n"
            if profile.height:
                profile_text += f"📏 Рост: {profile.height} см\n"
            if profile.weight:
                profile_text += f"⚖️ Вес: {profile.weight} кг\n"
            
            profile_text += f"🏃‍♂️ Активность: {profile.activity_level}\n"
            profile_text += f"🎯 Цель: {profile.fitness_goal}\n"
            
            if profile.dietary_restrictions:
                profile_text += f"🚫 Ограничения: {', '.join(profile.dietary_restrictions)}\n"
            if profile.allergies:
                profile_text += f"⚠️ Аллергии: {', '.join(profile.allergies)}\n"
            
            # Calculate BMI if possible
            if profile.height and profile.weight:
                bmi = profile.weight / ((profile.height / 100) ** 2)
                profile_text += f"📊 ИМТ: {bmi:.1f}\n"
            
            # Daily goals
            daily_goals = await self.health_service.get_daily_goals(user_id)
            if daily_goals:
                profile_text += f"\n🎯 **ДНЕВНЫЕ ЦЕЛИ:**\n"
                profile_text += f"🔥 Калории: {daily_goals.get('calories', 0):.0f} ккал\n"
                profile_text += f"🥩 Белки: {daily_goals.get('protein', 0):.0f}г\n"
                profile_text += f"🍞 Углеводы: {daily_goals.get('carbs', 0):.0f}г\n"
                profile_text += f"🥑 Жиры: {daily_goals.get('fat', 0):.0f}г\n"
            
            # Menu buttons
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Рост", callback_data="health_edit_height"),
                    InlineKeyboardButton("⚖️ Вес", callback_data="health_edit_weight"),
                    InlineKeyboardButton("🎂 Возраст", callback_data="health_edit_age")
                ],
                [
                    InlineKeyboardButton("👫 Пол", callback_data="health_edit_gender"),
                    InlineKeyboardButton("🏃‍♂️ Активность", callback_data="health_edit_activity"),
                    InlineKeyboardButton("🎯 Цель", callback_data="health_edit_goal")
                ],
                [
                    InlineKeyboardButton("💪 Тренировка", callback_data="health_add_workout"),
                    InlineKeyboardButton("👣 Шаги", callback_data="health_add_steps")
                ],
                [
                    InlineKeyboardButton("📊 Статистика", callback_data="health_stats"),
                    InlineKeyboardButton("💡 Совет", callback_data="health_advice_general")
                ],
                [
                    InlineKeyboardButton("❌ Закрыть", callback_data="close_menu")
                ]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    profile_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    profile_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            logger.error(f"Error showing health profile menu: {e}")
            await update.effective_message.reply_text("❌ Ошибка загрузки профиля")
    
    async def handle_food_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show food statistics"""
        try:
            query = update.callback_query
            user_id = int(query.data.split("_")[-1])
            
            # Period selection buttons
            if query.data == f"food_stats_{user_id}":
                keyboard = [
                    [
                        InlineKeyboardButton("Сегодня", callback_data=f"food_stats_period_{user_id}_today"),
                        InlineKeyboardButton("Неделя", callback_data=f"food_stats_period_{user_id}_week")
                    ],
                    [
                        InlineKeyboardButton("Месяц", callback_data=f"food_stats_period_{user_id}_month"),
                        InlineKeyboardButton("◀️ Назад", callback_data="health_profile_menu")
                    ]
                ]
                
                await query.edit_message_text(
                    "📊 **СТАТИСТИКА ПИТАНИЯ**\n\nВыберите период:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                return
            
            # Show statistics for period
            period = query.data.split("_")[-1]
            stats = await self.food_service.get_user_food_statistics(user_id, period)
            
            period_names = {
                "today": "Сегодня",
                "week": "За неделю", 
                "month": "За месяц"
            }
            
            stats_text = f"📊 **СТАТИСТИКА: {period_names.get(period, period)}**\n\n"
            
            if stats.get("meal_count", 0) > 0:
                stats_text += f"🍽️ Приемов пищи: {stats['meal_count']}\n"
                stats_text += f"🔥 Калории: {stats['total_calories']:.0f} ккал\n"
                stats_text += f"🥩 Белки: {stats['total_protein']:.1f} г\n"
                stats_text += f"🍞 Углеводы: {stats['total_carbs']:.1f} г\n"
                stats_text += f"🥑 Жиры: {stats['total_fat']:.1f} г\n"
                stats_text += f"📈 Среднее за прием: {stats['avg_calories_per_meal']:.0f} ккал"
            else:
                stats_text += "📭 Нет данных за выбранный период\n\nОтправьте фото еды для начала отслеживания!"
            
            keyboard = [
                [
                    InlineKeyboardButton("◀️ Назад", callback_data=f"food_stats_{user_id}"),
                    InlineKeyboardButton("💡 Совет", callback_data="health_advice_nutrition")
                ]
            ]
            
            await query.edit_message_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing food statistics: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки статистики")
    
    async def handle_health_advice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get AI health advice"""
        try:
            query = update.callback_query
            await query.answer("🤖 Генерирую персональный совет...")
            
            user_id = update.effective_user.id
            
            # Determine advice type
            advice_type = "general"
            if "_nutrition" in query.data:
                advice_type = "nutrition"
            elif "_fitness" in query.data:
                advice_type = "fitness"
            elif "_goals" in query.data:
                advice_type = "goals"
            
            # Get AI recommendation
            recommendation = await self.ai_service.get_personalized_recommendation(
                user_id, advice_type
            )
            
            advice_text = f"🤖 **ПЕРСОНАЛЬНЫЙ СОВЕТ**\n\n{recommendation}"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Другой совет", callback_data=f"health_advice_{advice_type}"),
                    InlineKeyboardButton("📊 Профиль", callback_data="health_profile_menu")
                ]
            ]
            
            await query.edit_message_text(
                advice_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error getting health advice: {e}")
            await update.callback_query.answer("❌ Ошибка получения совета")
    
    async def handle_workout_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle workout input"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            # Parse workout input (format: "activity duration intensity notes")
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте:\n"
                    "`[активность] [длительность в минутах] [интенсивность 1-10] [заметки]`\n\n"
                    "Пример: `бег 30 7 утренняя пробежка`",
                    parse_mode="Markdown"
                )
                return
            
            activity_type = parts[0]
            duration = float(parts[1])
            intensity = int(parts[2]) if len(parts) > 2 else 5
            notes = " ".join(parts[3:]) if len(parts) > 3 else ""
            
            # Estimate calories burned (rough calculation)
            calories_burned = duration * intensity * 0.8  # Simple formula
            
            # Create workout session
            workout = WorkoutSession(
                user_id=user_id,
                activity_type=activity_type,
                duration=duration,
                calories_burned=calories_burned,
                intensity=intensity,
                notes=notes
            )
            
            # Save workout
            success = await self.health_service.save_workout(workout)
            
            if success:
                response = f"✅ **ТРЕНИРОВКА СОХРАНЕНА**\n\n"
                response += f"🏃‍♂️ Активность: {activity_type}\n"
                response += f"⏱️ Длительность: {duration:.0f} мин\n"
                response += f"🔥 Сожжено калорий: {calories_burned:.0f}\n"
                response += f"💪 Интенсивность: {intensity}/10\n"
                if notes:
                    response += f"📝 Заметки: {notes}\n"
                
                keyboard = [
                    [
                        InlineKeyboardButton("📊 Статистика", callback_data="health_stats"),
                        InlineKeyboardButton("👤 Профиль", callback_data="health_profile_menu")
                    ]
                ]
                
                await update.message.reply_text(
                    response,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Ошибка сохранения тренировки")
        
        except Exception as e:
            logger.error(f"Error handling workout input: {e}")
            await update.message.reply_text("❌ Ошибка обработки тренировки")
    
    async def handle_steps_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle steps input"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            # Parse steps
            try:
                steps = int(text)
                if steps < 0 or steps > 100000:
                    raise ValueError("Invalid steps range")
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат. Введите количество шагов (число от 0 до 100000)"
                )
                return
            
            # Estimate distance and calories
            distance = steps * 0.0008  # km (rough average step length)
            calories_burned = steps * 0.04  # rough calories per step
            
            # Create steps data
            steps_data = StepsData(
                user_id=user_id,
                steps=steps,
                distance=distance,
                calories_burned=calories_burned
            )
            
            # Save steps
            success = await self.health_service.save_steps(steps_data)
            
            if success:
                response = f"✅ **ШАГИ СОХРАНЕНЫ**\n\n"
                response += f"👣 Шаги: {steps:,}\n"
                response += f"📏 Расстояние: {distance:.1f} км\n"
                response += f"🔥 Сожжено калорий: {calories_burned:.0f}\n"
                
                keyboard = [
                    [
                        InlineKeyboardButton("📊 Статистика", callback_data="health_stats"),
                        InlineKeyboardButton("👤 Профиль", callback_data="health_profile_menu")
                    ]
                ]
                
                await update.message.reply_text(
                    response,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Ошибка сохранения данных о шагах")
        
        except Exception as e:
            logger.error(f"Error handling steps input: {e}")
            await update.message.reply_text("❌ Ошибка обработки данных о шагах")
    
    async def handle_close_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Close menu"""
        try:
            await update.callback_query.delete_message()
        except Exception as e:
            logger.error(f"Error closing menu: {e}")
            await update.callback_query.answer("❌ Не удалось закрыть меню")