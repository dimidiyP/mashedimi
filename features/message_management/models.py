"""Models for message management functionality"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from core.utils import generate_uuid, get_current_timestamp

@dataclass
class TopicSettings:
    """Settings for topic-specific behavior"""
    id: str = field(default_factory=generate_uuid)
    chat_id: int = 0
    topic_id: Optional[int] = None  # None for regular groups
    topic_name: str = ""
    
    # Auto-deletion settings
    auto_delete_enabled: bool = False
    auto_delete_timeout: int = 300  # seconds (5 minutes default)
    delete_bot_messages: bool = True
    delete_user_messages: bool = False
    
    # Food analysis settings
    food_analysis_enabled: bool = True
    food_analysis_auto: bool = False  # False = only on @mention
    
    # AI assistant settings
    ai_assistant_enabled: bool = True
    ai_assistant_auto: bool = False  # False = only on @mention
    custom_prompt: Optional[str] = None
    
    # Notification settings
    notifications_enabled: bool = True
    
    # Access control
    admin_only_settings: bool = True
    allowed_users: List[int] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=get_current_timestamp)
    updated_at: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'topic_id': self.topic_id,
            'topic_name': self.topic_name,
            'auto_delete_enabled': self.auto_delete_enabled,
            'auto_delete_timeout': self.auto_delete_timeout,
            'delete_bot_messages': self.delete_bot_messages,
            'delete_user_messages': self.delete_user_messages,
            'food_analysis_enabled': self.food_analysis_enabled,
            'food_analysis_auto': self.food_analysis_auto,
            'ai_assistant_enabled': self.ai_assistant_enabled,
            'ai_assistant_auto': self.ai_assistant_auto,
            'custom_prompt': self.custom_prompt,
            'notifications_enabled': self.notifications_enabled,
            'admin_only_settings': self.admin_only_settings,
            'allowed_users': self.allowed_users,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopicSettings':
        return cls(
            id=data.get('id', generate_uuid()),
            chat_id=data.get('chat_id', 0),
            topic_id=data.get('topic_id'),
            topic_name=data.get('topic_name', ''),
            auto_delete_enabled=data.get('auto_delete_enabled', False),
            auto_delete_timeout=data.get('auto_delete_timeout', 300),
            delete_bot_messages=data.get('delete_bot_messages', True),
            delete_user_messages=data.get('delete_user_messages', False),
            food_analysis_enabled=data.get('food_analysis_enabled', True),
            food_analysis_auto=data.get('food_analysis_auto', False),
            ai_assistant_enabled=data.get('ai_assistant_enabled', True),
            ai_assistant_auto=data.get('ai_assistant_auto', False),
            custom_prompt=data.get('custom_prompt'),
            notifications_enabled=data.get('notifications_enabled', True),
            admin_only_settings=data.get('admin_only_settings', True),
            allowed_users=data.get('allowed_users', []),
            created_at=data.get('created_at', get_current_timestamp()),
            updated_at=data.get('updated_at', get_current_timestamp())
        )

@dataclass
class ScheduledMessage:
    """Scheduled message for auto-deletion"""
    id: str = field(default_factory=generate_uuid)
    chat_id: int = 0
    message_id: int = 0
    topic_id: Optional[int] = None
    user_id: int = 0
    message_type: str = "text"  # text, photo, document, etc.
    content_preview: str = ""  # First 100 chars of message
    scheduled_delete_at: datetime = field(default_factory=get_current_timestamp)
    created_at: datetime = field(default_factory=get_current_timestamp)
    deleted: bool = False
    deletion_attempted: bool = False
    deletion_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'topic_id': self.topic_id,
            'user_id': self.user_id,
            'message_type': self.message_type,
            'content_preview': self.content_preview,
            'scheduled_delete_at': self.scheduled_delete_at,
            'created_at': self.created_at,
            'deleted': self.deleted,
            'deletion_attempted': self.deletion_attempted,
            'deletion_error': self.deletion_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledMessage':
        return cls(
            id=data.get('id', generate_uuid()),
            chat_id=data.get('chat_id', 0),
            message_id=data.get('message_id', 0),
            topic_id=data.get('topic_id'),
            user_id=data.get('user_id', 0),
            message_type=data.get('message_type', 'text'),
            content_preview=data.get('content_preview', ''),
            scheduled_delete_at=data.get('scheduled_delete_at', get_current_timestamp()),
            created_at=data.get('created_at', get_current_timestamp()),
            deleted=data.get('deleted', False),
            deletion_attempted=data.get('deletion_attempted', False),
            deletion_error=data.get('deletion_error')
        )

@dataclass
class MessageTag:
    """Tag for message categorization"""
    id: str = field(default_factory=generate_uuid)
    name: str = ""
    description: str = ""
    color: str = "#007bff"  # Hex color code
    emoji: str = "🏷️"
    created_by: int = 0
    chat_id: int = 0
    topic_id: Optional[int] = None
    usage_count: int = 0
    created_at: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'emoji': self.emoji,
            'created_by': self.created_by,
            'chat_id': self.chat_id,
            'topic_id': self.topic_id,
            'usage_count': self.usage_count,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageTag':
        return cls(
            id=data.get('id', generate_uuid()),
            name=data.get('name', ''),
            description=data.get('description', ''),
            color=data.get('color', '#007bff'),
            emoji=data.get('emoji', '🏷️'),
            created_by=data.get('created_by', 0),
            chat_id=data.get('chat_id', 0),
            topic_id=data.get('topic_id'),
            usage_count=data.get('usage_count', 0),
            created_at=data.get('created_at', get_current_timestamp())
        )

@dataclass
class TaggedMessage:
    """Message with tags"""
    id: str = field(default_factory=generate_uuid)
    chat_id: int = 0
    message_id: int = 0
    topic_id: Optional[int] = None
    user_id: int = 0
    content: str = ""
    tags: List[str] = field(default_factory=list)  # Tag IDs
    tagged_by: int = 0
    tagged_at: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'topic_id': self.topic_id,
            'user_id': self.user_id,
            'content': self.content,
            'tags': self.tags,
            'tagged_by': self.tagged_by,
            'tagged_at': self.tagged_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaggedMessage':
        return cls(
            id=data.get('id', generate_uuid()),
            chat_id=data.get('chat_id', 0),
            message_id=data.get('message_id', 0),
            topic_id=data.get('topic_id'),
            user_id=data.get('user_id', 0),
            content=data.get('content', ''),
            tags=data.get('tags', []),
            tagged_by=data.get('tagged_by', 0),
            tagged_at=data.get('tagged_at', get_current_timestamp())
        )

@dataclass
class MessageFilter:
    """Filter for message processing"""
    id: str = field(default_factory=generate_uuid)
    name: str = ""
    description: str = ""
    chat_id: int = 0
    topic_id: Optional[int] = None
    
    # Filter criteria
    keywords: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    user_ids: List[int] = field(default_factory=list)
    excluded_user_ids: List[int] = field(default_factory=list)
    message_types: List[str] = field(default_factory=list)  # text, photo, document, etc.
    
    # Actions
    auto_delete: bool = False
    auto_tag: List[str] = field(default_factory=list)  # Tag IDs
    forward_to_chat: Optional[int] = None
    send_notification: bool = False
    
    # Settings
    enabled: bool = True
    priority: int = 5  # 1-10
    created_by: int = 0
    created_at: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'chat_id': self.chat_id,
            'topic_id': self.topic_id,
            'keywords': self.keywords,
            'excluded_keywords': self.excluded_keywords,
            'user_ids': self.user_ids,
            'excluded_user_ids': self.excluded_user_ids,
            'message_types': self.message_types,
            'auto_delete': self.auto_delete,
            'auto_tag': self.auto_tag,
            'forward_to_chat': self.forward_to_chat,
            'send_notification': self.send_notification,
            'enabled': self.enabled,
            'priority': self.priority,
            'created_by': self.created_by,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageFilter':
        return cls(
            id=data.get('id', generate_uuid()),
            name=data.get('name', ''),
            description=data.get('description', ''),
            chat_id=data.get('chat_id', 0),
            topic_id=data.get('topic_id'),
            keywords=data.get('keywords', []),
            excluded_keywords=data.get('excluded_keywords', []),
            user_ids=data.get('user_ids', []),
            excluded_user_ids=data.get('excluded_user_ids', []),
            message_types=data.get('message_types', []),
            auto_delete=data.get('auto_delete', False),
            auto_tag=data.get('auto_tag', []),
            forward_to_chat=data.get('forward_to_chat'),
            send_notification=data.get('send_notification', False),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 5),
            created_by=data.get('created_by', 0),
            created_at=data.get('created_at', get_current_timestamp())
        )