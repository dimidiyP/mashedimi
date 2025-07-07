"""Services for message management functionality"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError

from config.settings import settings
from config.database import db_manager
from config.constants import (
    COLLECTION_TOPIC_SETTINGS, AUTO_DELETE_TIMEOUT_DEFAULT,
    AUTO_DELETE_TIMEOUT_MIN, AUTO_DELETE_TIMEOUT_MAX
)
from core.utils import get_current_timestamp
from .models import (
    TopicSettings, ScheduledMessage, MessageTag, 
    TaggedMessage, MessageFilter
)

logger = logging.getLogger(__name__)

class MessageManagementService:
    """Service for message management functionality"""
    
    def __init__(self):
        self.scheduled_deletions = {}  # In-memory store for scheduled deletions
        self.deletion_tasks = {}  # Store asyncio tasks
    
    async def get_topic_settings(self, chat_id: int, topic_id: Optional[int] = None) -> TopicSettings:
        """Get or create topic settings"""
        try:
            collection = db_manager.get_collection(COLLECTION_TOPIC_SETTINGS)
            
            # Find existing settings
            query = {"chat_id": chat_id}
            if topic_id is not None:
                query["topic_id"] = topic_id
            
            existing = collection.find_one(query)
            
            if existing:
                return TopicSettings.from_dict(existing)
            else:
                # Create new settings
                settings = TopicSettings(
                    chat_id=chat_id,
                    topic_id=topic_id,
                    topic_name=f"Topic {topic_id}" if topic_id else "General Chat"
                )
                
                collection.insert_one(settings.to_dict())
                logger.info(f"Created new topic settings for chat {chat_id}, topic {topic_id}")
                return settings
                
        except Exception as e:
            logger.error(f"Error getting topic settings: {e}")
            # Return default settings
            return TopicSettings(chat_id=chat_id, topic_id=topic_id)
    
    async def update_topic_settings(self, chat_id: int, topic_id: Optional[int], 
                                  updates: Dict[str, Any]) -> bool:
        """Update topic settings"""
        try:
            collection = db_manager.get_collection(COLLECTION_TOPIC_SETTINGS)
            
            # Add updated timestamp
            updates["updated_at"] = get_current_timestamp()
            
            query = {"chat_id": chat_id}
            if topic_id is not None:
                query["topic_id"] = topic_id
            
            result = collection.update_one(
                query,
                {"$set": updates},
                upsert=True
            )
            
            logger.info(f"Updated topic settings for chat {chat_id}, topic {topic_id}")
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            logger.error(f"Error updating topic settings: {e}")
            return False
    
    async def should_auto_delete(self, chat_id: int, topic_id: Optional[int], 
                               message_type: str, user_id: int) -> bool:
        """Check if message should be auto-deleted"""
        try:
            settings = await self.get_topic_settings(chat_id, topic_id)
            
            if not settings.auto_delete_enabled:
                return False
            
            # Check message type
            if message_type == "bot" and not settings.delete_bot_messages:
                return False
            
            if message_type == "user" and not settings.delete_user_messages:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking auto-delete: {e}")
            return False
    
    async def schedule_message_deletion(self, chat_id: int, message_id: int, 
                                      topic_id: Optional[int] = None, 
                                      user_id: int = 0, message_type: str = "bot",
                                      content_preview: str = "") -> bool:
        """Schedule a message for deletion"""
        try:
            settings = await self.get_topic_settings(chat_id, topic_id)
            
            if not await self.should_auto_delete(chat_id, topic_id, message_type, user_id):
                return False
            
            # Calculate deletion time
            delete_at = get_current_timestamp() + timedelta(seconds=settings.auto_delete_timeout)
            
            # Create scheduled message
            scheduled_msg = ScheduledMessage(
                chat_id=chat_id,
                message_id=message_id,
                topic_id=topic_id,
                user_id=user_id,
                message_type=message_type,
                content_preview=content_preview[:100],
                scheduled_delete_at=delete_at
            )
            
            # Save to database
            collection = db_manager.get_collection("scheduled_messages")
            collection.insert_one(scheduled_msg.to_dict())
            
            # Schedule the deletion task
            task_key = f"{chat_id}_{message_id}"
            task = asyncio.create_task(
                self._delayed_delete_message(chat_id, message_id, settings.auto_delete_timeout)
            )
            self.deletion_tasks[task_key] = task
            
            logger.info(f"Scheduled deletion for message {message_id} in {settings.auto_delete_timeout}s")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling message deletion: {e}")
            return False
    
    async def cancel_message_deletion(self, chat_id: int, message_id: int) -> bool:
        """Cancel scheduled message deletion"""
        try:
            task_key = f"{chat_id}_{message_id}"
            
            # Cancel the asyncio task
            if task_key in self.deletion_tasks:
                task = self.deletion_tasks[task_key]
                if not task.done():
                    task.cancel()
                del self.deletion_tasks[task_key]
            
            # Update database
            collection = db_manager.get_collection("scheduled_messages")
            collection.update_one(
                {"chat_id": chat_id, "message_id": message_id},
                {"$set": {"deleted": True, "deletion_error": "Cancelled by user"}}
            )
            
            logger.info(f"Cancelled deletion for message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling message deletion: {e}")
            return False
    
    async def _delayed_delete_message(self, chat_id: int, message_id: int, delay: int) -> None:
        """Delete message after delay"""
        try:
            # Wait for the specified delay
            await asyncio.sleep(delay)
            
            # Get bot instance
            from core.bot import bot_core
            bot = bot_core.get_bot()
            
            if bot:
                # Try to delete the message
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                
                # Update database
                collection = db_manager.get_collection("scheduled_messages")
                collection.update_one(
                    {"chat_id": chat_id, "message_id": message_id},
                    {"$set": {"deleted": True, "deletion_attempted": True}}
                )
                
                logger.info(f"Successfully deleted message {message_id}")
            
        except TelegramError as e:
            logger.warning(f"Failed to delete message {message_id}: {e}")
            
            # Update database with error
            collection = db_manager.get_collection("scheduled_messages")
            collection.update_one(
                {"chat_id": chat_id, "message_id": message_id},
                {
                    "$set": {
                        "deletion_attempted": True,
                        "deletion_error": str(e)
                    }
                }
            )
            
        except asyncio.CancelledError:
            logger.info(f"Deletion cancelled for message {message_id}")
            
        except Exception as e:
            logger.error(f"Error in delayed delete: {e}")
    
    async def create_message_tag(self, chat_id: int, topic_id: Optional[int], 
                               name: str, description: str = "", 
                               emoji: str = "🏷️", color: str = "#007bff",
                               created_by: int = 0) -> Optional[MessageTag]:
        """Create a new message tag"""
        try:
            # Check if tag already exists
            collection = db_manager.get_collection("message_tags")
            existing = collection.find_one({
                "chat_id": chat_id,
                "topic_id": topic_id,
                "name": name
            })
            
            if existing:
                return MessageTag.from_dict(existing)
            
            # Create new tag
            tag = MessageTag(
                name=name,
                description=description,
                emoji=emoji,
                color=color,
                created_by=created_by,
                chat_id=chat_id,
                topic_id=topic_id
            )
            
            collection.insert_one(tag.to_dict())
            logger.info(f"Created tag '{name}' for chat {chat_id}")
            return tag
            
        except Exception as e:
            logger.error(f"Error creating message tag: {e}")
            return None
    
    async def tag_message(self, chat_id: int, message_id: int, topic_id: Optional[int],
                         user_id: int, content: str, tag_names: List[str],
                         tagged_by: int) -> bool:
        """Tag a message"""
        try:
            # Get tag IDs
            tag_collection = db_manager.get_collection("message_tags")
            tag_ids = []
            
            for tag_name in tag_names:
                tag = tag_collection.find_one({
                    "chat_id": chat_id,
                    "topic_id": topic_id,
                    "name": tag_name
                })
                
                if tag:
                    tag_ids.append(tag["id"])
                    # Increment usage count
                    tag_collection.update_one(
                        {"id": tag["id"]},
                        {"$inc": {"usage_count": 1}}
                    )
            
            if not tag_ids:
                return False
            
            # Create tagged message
            tagged_message = TaggedMessage(
                chat_id=chat_id,
                message_id=message_id,
                topic_id=topic_id,
                user_id=user_id,
                content=content[:1000],  # Limit content length
                tags=tag_ids,
                tagged_by=tagged_by
            )
            
            # Save to database
            collection = db_manager.get_collection("tagged_messages")
            collection.insert_one(tagged_message.to_dict())
            
            logger.info(f"Tagged message {message_id} with {len(tag_ids)} tags")
            return True
            
        except Exception as e:
            logger.error(f"Error tagging message: {e}")
            return False
    
    async def search_tagged_messages(self, chat_id: int, topic_id: Optional[int],
                                   tag_names: List[str] = None, 
                                   query: str = None) -> List[TaggedMessage]:
        """Search tagged messages"""
        try:
            collection = db_manager.get_collection("tagged_messages")
            
            # Build search query
            search_query = {"chat_id": chat_id}
            if topic_id is not None:
                search_query["topic_id"] = topic_id
            
            if tag_names:
                # Get tag IDs
                tag_collection = db_manager.get_collection("message_tags")
                tag_ids = []
                
                for tag_name in tag_names:
                    tag = tag_collection.find_one({
                        "chat_id": chat_id,
                        "topic_id": topic_id,
                        "name": tag_name
                    })
                    if tag:
                        tag_ids.append(tag["id"])
                
                if tag_ids:
                    search_query["tags"] = {"$in": tag_ids}
            
            if query:
                search_query["content"] = {"$regex": query, "$options": "i"}
            
            # Execute search
            results = collection.find(search_query).sort("tagged_at", -1).limit(50)
            
            tagged_messages = []
            for result in results:
                tagged_messages.append(TaggedMessage.from_dict(result))
            
            return tagged_messages
            
        except Exception as e:
            logger.error(f"Error searching tagged messages: {e}")
            return []
    
    async def get_chat_tags(self, chat_id: int, topic_id: Optional[int] = None) -> List[MessageTag]:
        """Get all tags for a chat/topic"""
        try:
            collection = db_manager.get_collection("message_tags")
            
            query = {"chat_id": chat_id}
            if topic_id is not None:
                query["topic_id"] = topic_id
            
            tags_data = collection.find(query).sort("usage_count", -1)
            
            tags = []
            for tag_data in tags_data:
                tags.append(MessageTag.from_dict(tag_data))
            
            return tags
            
        except Exception as e:
            logger.error(f"Error getting chat tags: {e}")
            return []
    
    async def process_message_with_bot_mention(self, chat_id: int, message_id: int,
                                             topic_id: Optional[int], text: str,
                                             user_id: int) -> Dict[str, Any]:
        """Process message that mentions the bot"""
        try:
            settings = await self.get_topic_settings(chat_id, topic_id)
            
            # Clean text by removing bot mentions
            clean_text = text
            for mention in ["@DMPlove_bot", "@dmplove_bot"]:
                clean_text = clean_text.replace(mention, "").strip()
            
            result = {
                "processed": True,
                "clean_text": clean_text,
                "should_respond": False,
                "response_type": None
            }
            
            # Check if it's a command or request
            text_lower = clean_text.lower()
            
            # Food analysis keywords
            food_keywords = ["еда", "калории", "анализ", "питание", "блюдо"]
            if any(keyword in text_lower for keyword in food_keywords):
                result["should_respond"] = True
                result["response_type"] = "food_analysis"
            
            # Movie keywords
            movie_keywords = ["фильм", "кино", "рекомендации", "посмотрел", "сериал"]
            if any(keyword in text_lower for keyword in movie_keywords):
                result["should_respond"] = True
                result["response_type"] = "movie_expert"
            
            # Health keywords
            health_keywords = ["здоровье", "профиль", "тренировка", "шаги"]
            if any(keyword in text_lower for keyword in health_keywords):
                result["should_respond"] = True
                result["response_type"] = "health_profile"
            
            # Tag keywords
            tag_keywords = ["тег", "метка", "поиск"]
            if any(keyword in text_lower for keyword in tag_keywords):
                result["should_respond"] = True
                result["response_type"] = "message_tags"
            
            # If no specific keywords, use general AI
            if not result["should_respond"]:
                result["should_respond"] = True
                result["response_type"] = "general_ai"
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing message with bot mention: {e}")
            return {"processed": False, "error": str(e)}

class AutoModerationService:
    """Service for automatic message moderation"""
    
    def __init__(self):
        self.message_service = MessageManagementService()
    
    async def check_message_filters(self, chat_id: int, topic_id: Optional[int],
                                  message_text: str, user_id: int, 
                                  message_type: str) -> Dict[str, Any]:
        """Check if message matches any filters"""
        try:
            collection = db_manager.get_collection("message_filters")
            
            # Get active filters for this chat/topic
            query = {
                "chat_id": chat_id,
                "enabled": True
            }
            if topic_id is not None:
                query["topic_id"] = topic_id
            
            filters = collection.find(query).sort("priority", -1)
            
            actions = {
                "auto_delete": False,
                "auto_tag": [],
                "forward_to_chat": None,
                "send_notification": False,
                "matched_filters": []
            }
            
            for filter_data in filters:
                filter_obj = MessageFilter.from_dict(filter_data)
                
                if await self._message_matches_filter(filter_obj, message_text, user_id, message_type):
                    actions["matched_filters"].append(filter_obj.name)
                    
                    # Apply actions
                    if filter_obj.auto_delete:
                        actions["auto_delete"] = True
                    
                    if filter_obj.auto_tag:
                        actions["auto_tag"].extend(filter_obj.auto_tag)
                    
                    if filter_obj.forward_to_chat:
                        actions["forward_to_chat"] = filter_obj.forward_to_chat
                    
                    if filter_obj.send_notification:
                        actions["send_notification"] = True
            
            return actions
            
        except Exception as e:
            logger.error(f"Error checking message filters: {e}")
            return {"error": str(e)}
    
    async def _message_matches_filter(self, filter_obj: MessageFilter, 
                                    message_text: str, user_id: int, 
                                    message_type: str) -> bool:
        """Check if message matches a specific filter"""
        try:
            text_lower = message_text.lower()
            
            # Check message type
            if filter_obj.message_types and message_type not in filter_obj.message_types:
                return False
            
            # Check user ID
            if filter_obj.user_ids and user_id not in filter_obj.user_ids:
                return False
            
            # Check excluded users
            if filter_obj.excluded_user_ids and user_id in filter_obj.excluded_user_ids:
                return False
            
            # Check keywords
            if filter_obj.keywords:
                has_keyword = any(
                    keyword.lower() in text_lower 
                    for keyword in filter_obj.keywords
                )
                if not has_keyword:
                    return False
            
            # Check excluded keywords
            if filter_obj.excluded_keywords:
                has_excluded = any(
                    keyword.lower() in text_lower 
                    for keyword in filter_obj.excluded_keywords
                )
                if has_excluded:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching filter: {e}")
            return False