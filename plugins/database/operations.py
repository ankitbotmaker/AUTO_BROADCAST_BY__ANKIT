#!/usr/bin/env python3
"""
Database Operations
Handles all database CRUD operations and queries
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .connection import db_connection
from .models import UserModel, ChannelModel, BroadcastModel, AnalyticsModel, BroadcastMessageModel
from config import (
    USERS_COLLECTION, CHANNELS_COLLECTION, BROADCASTS_COLLECTION,
    ANALYTICS_COLLECTION, SCHEDULED_BROADCASTS_COLLECTION, 
    BROADCAST_MESSAGES_COLLECTION, BOT_MESSAGES_COLLECTION
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """Enhanced database operations with error handling and optimization"""
    
    def __init__(self):
        self.db = db_connection
    
    # =============================================================================
    # USER OPERATIONS
    # =============================================================================
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Add or update user"""
        try:
            collection = self.db.get_collection(USERS_COLLECTION)
            if not collection:
                return False
            
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_active": datetime.now(),
                "created_at": datetime.now()
            }
            
            result = collection.update_one(
                {"user_id": user_id},
                {"$set": user_data, "$setOnInsert": {"premium_status": "free", "total_broadcasts": 0, "total_channels": 0}},
                upsert=True
            )
            
            logger.info(f"User {user_id} added/updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[UserModel]:
        """Get user by ID"""
        try:
            collection = self.db.get_collection(USERS_COLLECTION)
            if not collection:
                return None
            
            user_data = collection.find_one({"user_id": user_id})
            if user_data:
                return UserModel.from_dict(user_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    # Premium system removed - all features are now free
    
    def get_all_users(self) -> List[UserModel]:
        """Get all users"""
        try:
            collection = self.db.get_collection(USERS_COLLECTION)
            if not collection:
                return []
            
            users = []
            for user_data in collection.find():
                users.append(UserModel.from_dict(user_data))
            return users
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    # =============================================================================
    # CHANNEL OPERATIONS
    # =============================================================================
    
    def add_channel(self, channel_id: int, user_id: int, channel_name: str, username: str = None) -> bool:
        """Add channel for user"""
        try:
            collection = self.db.get_collection(CHANNELS_COLLECTION)
            if not collection:
                return False
            
            channel_data = {
                "channel_id": channel_id,
                "user_id": user_id,
                "channel_name": channel_name,
                "username": username,
                "added_at": datetime.now(),
                "is_active": True
            }
            
            result = collection.update_one(
                {"channel_id": channel_id, "user_id": user_id},
                {"$set": channel_data, "$setOnInsert": {"total_broadcasts": 0, "success_rate": 0.0}},
                upsert=True
            )
            
            logger.info(f"Channel {channel_id} added for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding channel {channel_id} for user {user_id}: {e}")
            return False
    
    def get_user_channels(self, user_id: int) -> List[ChannelModel]:
        """Get all channels for user"""
        try:
            collection = self.db.get_collection(CHANNELS_COLLECTION)
            if not collection:
                return []
            
            channels = []
            for channel_data in collection.find({"user_id": user_id, "is_active": True}):
                channels.append(ChannelModel.from_dict(channel_data))
            return channels
            
        except Exception as e:
            logger.error(f"Error getting channels for user {user_id}: {e}")
            return []
    
    def remove_channel(self, channel_id: int, user_id: int) -> bool:
        """Remove channel from user"""
        try:
            collection = self.db.get_collection(CHANNELS_COLLECTION)
            if not collection:
                return False
            
            result = collection.update_one(
                {"channel_id": channel_id, "user_id": user_id},
                {"$set": {"is_active": False}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error removing channel {channel_id} for user {user_id}: {e}")
            return False
    
    def get_channel(self, channel_id: int, user_id: int) -> Optional[ChannelModel]:
        """Get specific channel"""
        try:
            collection = self.db.get_collection(CHANNELS_COLLECTION)
            if not collection:
                return None
            
            channel_data = collection.find_one({"channel_id": channel_id, "user_id": user_id})
            if channel_data:
                return ChannelModel.from_dict(channel_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting channel {channel_id}: {e}")
            return None
    
    # =============================================================================
    # BROADCAST OPERATIONS
    # =============================================================================
    
    def create_broadcast(self, broadcast: BroadcastModel) -> bool:
        """Create new broadcast"""
        try:
            collection = self.db.get_collection(BROADCASTS_COLLECTION)
            if not collection:
                return False
            
            result = collection.insert_one(broadcast.to_dict())
            logger.info(f"Broadcast {broadcast.broadcast_id} created successfully")
            return result.inserted_id is not None
            
        except Exception as e:
            logger.error(f"Error creating broadcast {broadcast.broadcast_id}: {e}")
            return False
    
    def update_broadcast_status(self, broadcast_id: str, status: str, **kwargs) -> bool:
        """Update broadcast status"""
        try:
            collection = self.db.get_collection(BROADCASTS_COLLECTION)
            if not collection:
                return False
            
            update_data = {"status": status}
            if status == "running":
                update_data["started_at"] = datetime.now()
            elif status in ["completed", "failed", "cancelled"]:
                update_data["completed_at"] = datetime.now()
            
            update_data.update(kwargs)
            
            result = collection.update_one(
                {"broadcast_id": broadcast_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating broadcast {broadcast_id}: {e}")
            return False
    
    def get_user_broadcasts(self, user_id: int, limit: int = 50) -> List[BroadcastModel]:
        """Get user broadcasts"""
        try:
            collection = self.db.get_collection(BROADCASTS_COLLECTION)
            if not collection:
                return []
            
            broadcasts = []
            for broadcast_data in collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit):
                broadcasts.append(BroadcastModel.from_dict(broadcast_data))
            return broadcasts
            
        except Exception as e:
            logger.error(f"Error getting broadcasts for user {user_id}: {e}")
            return []
    
    def get_active_broadcasts(self) -> List[BroadcastModel]:
        """Get all active broadcasts"""
        try:
            collection = self.db.get_collection(BROADCASTS_COLLECTION)
            if not collection:
                return []
            
            broadcasts = []
            for broadcast_data in collection.find({"status": "running"}):
                broadcasts.append(BroadcastModel.from_dict(broadcast_data))
            return broadcasts
            
        except Exception as e:
            logger.error(f"Error getting active broadcasts: {e}")
            return []
    
    # =============================================================================
    # ANALYTICS OPERATIONS
    # =============================================================================
    
    def update_analytics(self, user_id: int, metric: str, value: int = 1) -> bool:
        """Update user analytics"""
        try:
            collection = self.db.get_collection(ANALYTICS_COLLECTION)
            if not collection:
                return False
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            result = collection.update_one(
                {"user_id": user_id, "date": today},
                {"$inc": {metric: value}},
                upsert=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating analytics for user {user_id}: {e}")
            return False
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get user analytics for specified days"""
        try:
            collection = self.db.get_collection(ANALYTICS_COLLECTION)
            if not collection:
                return {}
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            pipeline = [
                {"$match": {"user_id": user_id, "date": {"$gte": start_date.strftime("%Y-%m-%d")}}},
                {"$group": {
                    "_id": None,
                    "total_broadcasts": {"$sum": "$total_broadcasts"},
                    "total_channels": {"$max": "$total_channels"},
                    "successful_broadcasts": {"$sum": "$successful_broadcasts"},
                    "failed_broadcasts": {"$sum": "$failed_broadcasts"},
                    "total_messages_sent": {"$sum": "$total_messages_sent"}
                }}
            ]
            
            result = list(collection.aggregate(pipeline))
            if result:
                return result[0]
            return {}
            
        except Exception as e:
            logger.error(f"Error getting analytics for user {user_id}: {e}")
            return {}
    
    # =============================================================================
    # MESSAGE TRACKING OPERATIONS
    # =============================================================================
    
    def save_broadcast_message(self, message: BroadcastMessageModel) -> bool:
        """Save broadcast message for tracking"""
        try:
            collection = self.db.get_collection(BROADCAST_MESSAGES_COLLECTION)
            if not collection:
                return False
            
            result = collection.insert_one(message.to_dict())
            return result.inserted_id is not None
            
        except Exception as e:
            logger.error(f"Error saving broadcast message: {e}")
            return False
    
    def get_broadcast_messages(self, user_id: int, broadcast_id: str = None) -> List[BroadcastMessageModel]:
        """Get broadcast messages"""
        try:
            collection = self.db.get_collection(BROADCAST_MESSAGES_COLLECTION)
            if not collection:
                return []
            
            query = {"user_id": user_id}
            if broadcast_id:
                query["broadcast_id"] = broadcast_id
            
            messages = []
            for message_data in collection.find(query):
                messages.append(BroadcastMessageModel.from_dict(message_data))
            return messages
            
        except Exception as e:
            logger.error(f"Error getting broadcast messages: {e}")
            return []
    
    def update_message_status(self, message_id: int, channel_id: int, status: str, **kwargs) -> bool:
        """Update message status (deleted, reposted, etc.)"""
        try:
            collection = self.db.get_collection(BROADCAST_MESSAGES_COLLECTION)
            if not collection:
                return False
            
            update_data = {}
            if status == "deleted":
                update_data["is_deleted"] = True
                update_data["deleted_at"] = datetime.now()
            elif status == "reposted":
                update_data["is_reposted"] = True
                update_data["reposted_at"] = datetime.now()
            
            update_data.update(kwargs)
            
            result = collection.update_one(
                {"message_id": message_id, "channel_id": channel_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating message status: {e}")
            return False
