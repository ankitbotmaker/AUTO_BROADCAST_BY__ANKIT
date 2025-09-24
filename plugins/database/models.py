#!/usr/bin/env python3
"""
Database Models
Data models for MongoDB collections
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class BroadcastStatus(Enum):
    """Broadcast status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageType(Enum):
    """Message type enumeration"""
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"
    ANIMATION = "animation"

@dataclass
class UserModel:
    """User data model"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_premium: bool = True  # All users are premium now
    is_admin: bool = False
    join_date: datetime = None
    last_active: datetime = None
    total_broadcasts: int = 0
    total_channels: int = 0
    total_messages_sent: int = 0
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.join_date is None:
            self.join_date = datetime.utcnow()
        if self.last_active is None:
            self.last_active = datetime.utcnow()
        if self.settings is None:
            self.settings = {
                'auto_delete_enabled': False,
                'auto_repost_enabled': False,
                'default_delete_time': 60,
                'default_repost_time': 60,
                'notifications_enabled': True,
                'analytics_enabled': True
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.user_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """Create from dictionary"""
        if '_id' in data:
            data['user_id'] = data.pop('_id')
        return cls(**data)

@dataclass
class ChannelModel:
    """Channel data model"""
    channel_id: int
    user_id: int
    channel_name: str
    username: Optional[str] = None
    channel_type: str = "channel"  # channel, group, supergroup
    is_active: bool = True
    added_date: datetime = None
    last_broadcast: datetime = None
    total_broadcasts: int = 0
    success_rate: float = 100.0
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.added_date is None:
            self.added_date = datetime.utcnow()
        if self.settings is None:
            self.settings = {
                'auto_delete_enabled': False,
                'auto_repost_enabled': False,
                'delete_time': 60,
                'repost_time': 60,
                'priority': 1
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = f"{self.user_id}_{self.channel_id}"
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChannelModel':
        """Create from dictionary"""
        if '_id' in data:
            data.pop('_id')
        return cls(**data)

@dataclass
class BroadcastModel:
    """Broadcast data model"""
    broadcast_id: str
    user_id: int
    message_type: str
    message_content: str
    caption: Optional[str] = None
    file_id: Optional[str] = None
    channels: List[int] = None
    status: str = BroadcastStatus.PENDING.value
    created_date: datetime = None
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    total_channels: int = 0
    successful_sends: int = 0
    failed_sends: int = 0
    auto_delete_time: Optional[int] = None
    auto_repost_time: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    error_details: Dict[str, Any] = None
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.utcnow()
        if self.channels is None:
            self.channels = []
        if self.error_details is None:
            self.error_details = {}
        if self.settings is None:
            self.settings = {
                'delete_original': False,
                'send_notifications': True,
                'retry_failed': True,
                'max_retries': 3
            }
        self.total_channels = len(self.channels)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.broadcast_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastModel':
        """Create from dictionary"""
        if '_id' in data:
            data['broadcast_id'] = data.pop('_id')
        return cls(**data)
    
    def get_success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_channels == 0:
            return 0.0
        return (self.successful_sends / self.total_channels) * 100

@dataclass
class AnalyticsModel:
    """Analytics data model"""
    analytics_id: str
    user_id: int
    broadcast_id: str
    channel_id: int
    message_id: Optional[int] = None
    status: str = "sent"  # sent, failed, deleted, reposted
    timestamp: datetime = None
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.analytics_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalyticsModel':
        """Create from dictionary"""
        if '_id' in data:
            data['analytics_id'] = data.pop('_id')
        return cls(**data)

@dataclass
class ScheduledBroadcastModel:
    """Scheduled broadcast data model"""
    schedule_id: str
    user_id: int
    broadcast_data: Dict[str, Any]
    scheduled_time: datetime
    status: str = "scheduled"  # scheduled, sent, cancelled, failed
    created_date: datetime = None
    executed_date: Optional[datetime] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.schedule_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledBroadcastModel':
        """Create from dictionary"""
        if '_id' in data:
            data['schedule_id'] = data.pop('_id')
        return cls(**data)

@dataclass
class BroadcastMessageModel:
    """Individual broadcast message tracking"""
    message_id: str
    broadcast_id: str
    user_id: int
    channel_id: int
    telegram_message_id: Optional[int] = None
    status: str = "pending"  # pending, sent, failed, deleted
    sent_date: Optional[datetime] = None
    delete_date: Optional[datetime] = None
    auto_delete_time: Optional[int] = None
    auto_repost_time: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.message_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastMessageModel':
        """Create from dictionary"""
        if '_id' in data:
            data['message_id'] = data.pop('_id')
        return cls(**data)

@dataclass
class BotMessageModel:
    """Bot message tracking for auto-delete"""
    bot_message_id: str
    user_id: int
    chat_id: int
    telegram_message_id: int
    message_type: str = "notification"
    sent_date: datetime = None
    auto_delete_time: Optional[int] = None
    delete_date: Optional[datetime] = None
    is_deleted: bool = False
    
    def __post_init__(self):
        if self.sent_date is None:
            self.sent_date = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB"""
        data = asdict(self)
        data['_id'] = self.bot_message_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotMessageModel':
        """Create from dictionary"""
        if '_id' in data:
            data['bot_message_id'] = data.pop('_id')
        return cls(**data)

# Helper functions for model operations
def generate_broadcast_id(user_id: int) -> str:
    """Generate unique broadcast ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"broadcast_{user_id}_{timestamp}"

def generate_analytics_id(user_id: int, broadcast_id: str, channel_id: int) -> str:
    """Generate unique analytics ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"analytics_{user_id}_{broadcast_id}_{channel_id}_{timestamp}"

def generate_schedule_id(user_id: int) -> str:
    """Generate unique schedule ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"schedule_{user_id}_{timestamp}"

def generate_message_id(broadcast_id: str, channel_id: int) -> str:
    """Generate unique message ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"msg_{broadcast_id}_{channel_id}_{timestamp}"

def generate_bot_message_id(user_id: int, chat_id: int) -> str:
    """Generate unique bot message ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"bot_msg_{user_id}_{chat_id}_{timestamp}"