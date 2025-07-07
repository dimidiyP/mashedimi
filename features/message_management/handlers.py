"""Handlers for message management functionality"""

import logging
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.utils import create_keyboard, get_current_timestamp
from .services import MessageManagementService, AutoModerationService
from .models import TopicSettings

logger = logging.getLogger(__name__)

class MessageManagementHandlers:
    """Handlers for message management functionality"""
    
    def __init__(self):
        self.message_service = MessageManagementService()
        self.moderation_service = AutoModerationService()
    
    async def handle_topic_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show topic settings menu"""
        try:
            chat_id = update.effective_chat.id
            topic_id = getattr(update.effective_message, 'message_thread_id', None)
            user_id = update.effective_user.id
            
            # Check if user is admin (simplified check)
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            is_admin = chat_member.status in ['administrator', 'creator']
            
            if not is_admin:
                await update.effective_message.reply_text(
                    "❌ Только администраторы могут изменять настройки топика"
                )
                return
            
            # Get current settings
            settings = await self.message_service.get_topic_settings(chat_id, topic_id)
            
            # Format settings info
            topic_name = settings.topic_name or (f"Topic {topic_id}" if topic_id else "General Chat")
            menu_text = f"⚙️ **НАСТРОЙКИ ТОПИКА**\n`{topic_name}`\n\n"
            
            # Auto-deletion settings
            menu_text += "🗑️ **АВТОУДАЛЕНИЕ:**\n"
            status = "✅ Включено" if settings.auto_delete_enabled else "❌ Выключено"
            menu_text += f"Статус: {status}\n"
            
            if settings.auto_delete_enabled:
                menu_text += f"⏱️ Задержка: {settings.auto_delete_timeout} сек\n"
                menu_text += f"🤖 Сообщения бота: {'✅' if settings.delete_bot_messages else '❌'}\n"
                menu_text += f"👥 Сообщения пользователей: {'✅' if settings.delete_user_messages else '❌'}\n"
            
            menu_text += "\n🤖 **AI АНАЛИЗ:**\n"
            food_status = "✅ Включен" if settings.food_analysis_enabled else "❌ Выключен"
            menu_text += f"Анализ еды: {food_status}\n"
            
            if settings.food_analysis_enabled:
                auto_mode = "Автоматически" if settings.food_analysis_auto else "Только при @упоминании"
                menu_text += f"Режим: {auto_mode}\n"
            
            ai_status = "✅ Включен" if settings.ai_assistant_enabled else "❌ Выключен"
            menu_text += f"AI ассистент: {ai_status}\n"
            
            if settings.ai_assistant_enabled:
                ai_auto_mode = "Автоматически" if settings.ai_assistant_auto else "Только при @упоминании"
                menu_text += f"Режим: {ai_auto_mode}\n"
            
            if settings.custom_prompt:
                menu_text += f"📝 Кастомный промпт: установлен\n"
            
            # Create menu buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🗑️ Автоудаление", 
                        callback_data=f"topic_auto_delete_{chat_id}_{topic_id or 0}"
                    ),
                    InlineKeyboardButton(
                        "🤖 AI настройки", 
                        callback_data=f"topic_ai_settings_{chat_id}_{topic_id or 0}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏷️ Теги", 
                        callback_data=f"topic_tags_{chat_id}_{topic_id or 0}"
                    ),
                    InlineKeyboardButton(
                        "🛡️ Модерация", 
                        callback_data=f"topic_moderation_{chat_id}_{topic_id or 0}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📊 Статистика", 
                        callback_data=f"topic_stats_{chat_id}_{topic_id or 0}"
                    ),
                    InlineKeyboardButton(
                        "📤 Экспорт", 
                        callback_data=f"topic_export_{chat_id}_{topic_id or 0}"
                    )
                ],
                [
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
            logger.error(f"Error showing topic settings menu: {e}")
            await update.effective_message.reply_text("❌ Ошибка загрузки настроек топика")
    
    async def handle_auto_delete_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle auto-delete settings"""
        try:
            query = update.callback_query
            data_parts = query.data.split("_")
            chat_id = int(data_parts[-2])
            topic_id = int(data_parts[-1]) if data_parts[-1] != "0" else None
            
            # Get current settings
            settings = await self.message_service.get_topic_settings(chat_id, topic_id)
            
            menu_text = "🗑️ **НАСТРОЙКИ АВТОУДАЛЕНИЯ**\n\n"
            
            if settings.auto_delete_enabled:
                menu_text += "✅ Автоудаление включено\n"
                menu_text += f"⏱️ Задержка: {settings.auto_delete_timeout} секунд\n"
                menu_text += f"🤖 Удалять сообщения бота: {'✅' if settings.delete_bot_messages else '❌'}\n"
                menu_text += f"👥 Удалять сообщения пользователей: {'✅' if settings.delete_user_messages else '❌'}\n"
            else:
                menu_text += "❌ Автоудаление выключено\n"
            
            menu_text += "\n⚙️ Выберите действие:"
            
            # Create buttons
            keyboard = []
            
            if settings.auto_delete_enabled:
                keyboard.append([
                    InlineKeyboardButton("❌ Выключить", callback_data=f"toggle_auto_delete_{chat_id}_{topic_id or 0}"),
                    InlineKeyboardButton("⏱️ Изменить время", callback_data=f"set_delete_timeout_{chat_id}_{topic_id or 0}")
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        f"🤖 Боты: {'✅' if settings.delete_bot_messages else '❌'}", 
                        callback_data=f"toggle_delete_bots_{chat_id}_{topic_id or 0}"
                    ),
                    InlineKeyboardButton(
                        f"👥 Юзеры: {'✅' if settings.delete_user_messages else '❌'}", 
                        callback_data=f"toggle_delete_users_{chat_id}_{topic_id or 0}"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("✅ Включить", callback_data=f"toggle_auto_delete_{chat_id}_{topic_id or 0}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("◀️ Назад", callback_data="topic_settings_menu")
            ])
            
            await query.edit_message_text(
                menu_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing auto-delete settings: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки настроек автоудаления")
    
    async def handle_toggle_auto_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Toggle auto-delete setting"""
        try:
            query = update.callback_query
            data_parts = query.data.split("_")
            chat_id = int(data_parts[-2])
            topic_id = int(data_parts[-1]) if data_parts[-1] != "0" else None
            
            # Get current settings
            settings = await self.message_service.get_topic_settings(chat_id, topic_id)
            
            # Toggle setting
            new_enabled = not settings.auto_delete_enabled
            
            success = await self.message_service.update_topic_settings(
                chat_id, topic_id, {"auto_delete_enabled": new_enabled}
            )
            
            if success:
                status = "включено" if new_enabled else "выключено"
                await query.answer(f"✅ Автоудаление {status}")
                
                # Refresh the menu
                await self.handle_auto_delete_settings(update, context)
            else:
                await query.answer("❌ Ошибка изменения настройки")
        
        except Exception as e:
            logger.error(f"Error toggling auto-delete: {e}")
            await update.callback_query.answer("❌ Ошибка изменения настройки")
    
    async def handle_ai_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle AI settings"""
        try:
            query = update.callback_query
            data_parts = query.data.split("_")
            chat_id = int(data_parts[-2])
            topic_id = int(data_parts[-1]) if data_parts[-1] != "0" else None
            
            # Get current settings
            settings = await self.message_service.get_topic_settings(chat_id, topic_id)
            
            menu_text = "🤖 **НАСТРОЙКИ AI**\n\n"
            
            # Food analysis settings
            menu_text += "🍽️ **АНАЛИЗ ЕДЫ:**\n"
            food_status = "✅ Включен" if settings.food_analysis_enabled else "❌ Выключен"
            menu_text += f"Статус: {food_status}\n"
            
            if settings.food_analysis_enabled:
                food_mode = "Автоматически" if settings.food_analysis_auto else "При @упоминании"
                menu_text += f"Режим: {food_mode}\n"
            
            # AI assistant settings
            menu_text += "\n🧠 **AI АССИСТЕНТ:**\n"
            ai_status = "✅ Включен" if settings.ai_assistant_enabled else "❌ Выключен"
            menu_text += f"Статус: {ai_status}\n"
            
            if settings.ai_assistant_enabled:
                ai_mode = "Автоматически" if settings.ai_assistant_auto else "При @упоминании"
                menu_text += f"Режим: {ai_mode}\n"
            
            if settings.custom_prompt:
                menu_text += f"📝 Кастомный промпт: установлен\n"
            else:
                menu_text += f"📝 Кастомный промпт: не установлен\n"
            
            # Create buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"🍽️ Еда: {'✅' if settings.food_analysis_enabled else '❌'}", 
                        callback_data=f"toggle_food_analysis_{chat_id}_{topic_id or 0}"
                    ),
                    InlineKeyboardButton(
                        f"🧠 AI: {'✅' if settings.ai_assistant_enabled else '❌'}", 
                        callback_data=f"toggle_ai_assistant_{chat_id}_{topic_id or 0}"
                    )
                ]
            ]
            
            if settings.food_analysis_enabled:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🍽️ Режим: {'Авто' if settings.food_analysis_auto else '@'}", 
                        callback_data=f"toggle_food_auto_{chat_id}_{topic_id or 0}"
                    )
                ])
            
            if settings.ai_assistant_enabled:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🧠 Режим: {'Авто' if settings.ai_assistant_auto else '@'}", 
                        callback_data=f"toggle_ai_auto_{chat_id}_{topic_id or 0}"
                    )
                ])
            
            keyboard.extend([
                [
                    InlineKeyboardButton("📝 Кастомный промпт", callback_data=f"set_custom_prompt_{chat_id}_{topic_id or 0}")
                ],
                [
                    InlineKeyboardButton("◀️ Назад", callback_data="topic_settings_menu")
                ]
            ])
            
            await query.edit_message_text(
                menu_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing AI settings: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки AI настроек")
    
    async def handle_message_tags_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle message tags menu"""
        try:
            query = update.callback_query
            data_parts = query.data.split("_")
            chat_id = int(data_parts[-2])
            topic_id = int(data_parts[-1]) if data_parts[-1] != "0" else None
            
            # Get existing tags
            tags = await self.message_service.get_chat_tags(chat_id, topic_id)
            
            menu_text = "🏷️ **ТЕГИ СООБЩЕНИЙ**\n\n"
            
            if tags:
                menu_text += f"📊 Всего тегов: {len(tags)}\n\n"
                
                for tag in tags[:10]:  # Show first 10 tags
                    menu_text += f"{tag.emoji} **{tag.name}**"
                    if tag.description:
                        menu_text += f" - {tag.description}"
                    menu_text += f" (использований: {tag.usage_count})\n"
                
                if len(tags) > 10:
                    menu_text += f"\n...и еще {len(tags) - 10} тегов"
            else:
                menu_text += "📭 Теги не созданы\n\n"
                menu_text += "💡 Создайте теги для категоризации сообщений"
            
            # Create buttons
            keyboard = [
                [
                    InlineKeyboardButton("➕ Создать тег", callback_data=f"create_tag_{chat_id}_{topic_id or 0}"),
                    InlineKeyboardButton("🔍 Поиск по тегам", callback_data=f"search_tags_{chat_id}_{topic_id or 0}")
                ],
                [
                    InlineKeyboardButton("📊 Статистика тегов", callback_data=f"tag_stats_{chat_id}_{topic_id or 0}"),
                    InlineKeyboardButton("🗑️ Управление", callback_data=f"manage_tags_{chat_id}_{topic_id or 0}")
                ],
                [
                    InlineKeyboardButton("◀️ Назад", callback_data="topic_settings_menu")
                ]
            ]
            
            await query.edit_message_text(
                menu_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        except Exception as e:
            logger.error(f"Error showing tags menu: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки меню тегов")
    
    async def handle_message_with_bot_mention(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handle message that mentions the bot"""
        try:
            chat_id = update.effective_chat.id
            message_id = update.message.message_id
            topic_id = getattr(update.message, 'message_thread_id', None)
            text = update.message.text
            user_id = update.effective_user.id
            
            # Process the message
            result = await self.message_service.process_message_with_bot_mention(
                chat_id, message_id, topic_id, text, user_id
            )
            
            if result.get("processed"):
                # Schedule auto-deletion if needed
                await self.message_service.schedule_message_deletion(
                    chat_id, message_id, topic_id, user_id, "user", text[:100]
                )
                
                return result.get("response_type", "general_ai")
            
            return "general_ai"
            
        except Exception as e:
            logger.error(f"Error handling message with bot mention: {e}")
            return "general_ai"
    
    async def handle_automatic_message_processing(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle automatic message processing (filters, etc.)"""
        try:
            chat_id = update.effective_chat.id
            message_id = update.message.message_id
            topic_id = getattr(update.message, 'message_thread_id', None)
            text = update.message.text or ""
            user_id = update.effective_user.id
            
            # Check message filters
            filter_actions = await self.moderation_service.check_message_filters(
                chat_id, topic_id, text, user_id, "user"
            )
            
            # Apply filter actions
            if filter_actions.get("auto_delete"):
                try:
                    await context.bot.delete_message(chat_id, message_id)
                    logger.info(f"Auto-deleted message {message_id} due to filter match")
                except Exception as e:
                    logger.error(f"Failed to auto-delete message: {e}")
            
            # Auto-tag if needed
            if filter_actions.get("auto_tag"):
                await self.message_service.tag_message(
                    chat_id, message_id, topic_id, user_id, text,
                    filter_actions["auto_tag"], 0  # 0 = system tagged
                )
            
            # Forward if needed
            if filter_actions.get("forward_to_chat"):
                try:
                    await context.bot.forward_message(
                        filter_actions["forward_to_chat"], chat_id, message_id
                    )
                except Exception as e:
                    logger.error(f"Failed to forward message: {e}")
            
            # Schedule regular auto-deletion
            await self.message_service.schedule_message_deletion(
                chat_id, message_id, topic_id, user_id, "user", text[:100]
            )
            
        except Exception as e:
            logger.error(f"Error in automatic message processing: {e}")
    
    async def handle_bot_message_posted(self, chat_id: int, message_id: int, 
                                      topic_id: Optional[int] = None, 
                                      content: str = "") -> None:
        """Handle when bot posts a message (for auto-deletion)"""
        try:
            # Schedule auto-deletion for bot message
            await self.message_service.schedule_message_deletion(
                chat_id, message_id, topic_id, 0, "bot", content[:100]
            )
        except Exception as e:
            logger.error(f"Error handling bot message posted: {e}")
    
    async def handle_close_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Close menu"""
        try:
            await update.callback_query.delete_message()
        except Exception as e:
            logger.error(f"Error closing menu: {e}")
            await update.callback_query.answer("❌ Не удалось закрыть меню")