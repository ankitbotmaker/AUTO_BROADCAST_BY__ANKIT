#!/usr/bin/env python3
"""
Database Models
Defines data models and schemas for all collections
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Premium system removed - all features are now free

class BroadcastStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageType(Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    VOICE = "voice"
    STICKER = "sticker"
    ANIMATION = "animation"

@dataclass
class UserModel:
    """User data model"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    total_broadcasts: int = 0
    total_channels: int = 0
    created_at: datetime = None
    last_active: datetime = None
    is_blocked: bool = False
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_active is None:
            self.last_active = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        # Convert datetime objects to ISO format
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """Create from dictionary"""
        # Convert ISO format back to datetime
        for key in ['created_at', 'last_active', 'premium_expiry']:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

@dataclass
class ChannelModel:
    """Channel data model"""
    channel_id: int
    user_id: int
    channel_name: str
    username: Optional[str] = None
    is_active: bool = True
    added_at: datetime = None
    last_used: datetime = None
    total_broadcasts: int = 0
    success_rate: float = 0.0
    
    def __post_init__(self):
        if self.added_at is None:
            self.added_at = datetime.now()
        if self.last_used is None:
            self.last_used = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChannelModel':
        """Create from dictionary"""
        for key in ['added_at', 'last_used']:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

@dataclass
class BroadcastModel:
    """Broadcast data model"""
    broadcast_id: str
    user_id: int
    message_type: str
    message_text: Optional[str] = None
    message_caption: Optional[str] = None
    channels: List[int] = None
    status: str = BroadcastStatus.PENDING.value
    total_channels: int = 0
    successful_channels: int = 0
    failed_channels: int = 0
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    repost_time: Optional[int] = None
    delete_time: Optional[int] = None
    is_scheduled: bool = False
    scheduled_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = []
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastModel':
        """Create from dictionary"""
        for key in ['created_at', 'started_at', 'completed_at', 'scheduled_at']:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

@dataclass
class AnalyticsModel:
    """Analytics data model"""
    user_id: int
    date: str  # YYYY-MM-DD format
    total_broadcasts: int = 0
    total_channels: int = 0
    successful_broadcasts: int = 0
    failed_broadcasts: int = 0
    total_messages_sent: int = 0
    total_auto_reposts: int = 0
    total_auto_deletes: int = 0
    average_success_rate: float = 0.0
    peak_activity_hour: int = 0
    most_used_channel: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalyticsModel':
        """Create from dictionary"""
        return cls(**data)

@dataclass
class BroadcastMessageModel:
    """Broadcast message tracking model"""
    user_id: int
    channel_id: int
    message_id: int
    broadcast_id: str
    message_type: str
    sent_at: datetime = None
    deleted_at: Optional[datetime] = None
    reposted_at: Optional[datetime] = None
    is_deleted: bool = False
    is_reposted: bool = False
    
    def __post_init__(self):
        if self.sent_at is None:
            self.sent_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastMessageModel':
        """Create from dictionary"""
        for key in ['sent_at', 'deleted_at', 'reposted_at']:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)
