#!/usr/bin/env python3
"""
Database Operations
Handles all database CRUD operations and business logic
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo import ASCENDING, DESCENDING

from .connection import db_connection
from .models import (
    UserModel, ChannelModel, BroadcastModel, AnalyticsModel,
    ScheduledBroadcastModel, BroadcastMessageModel, BotMessageModel,
    generate_broadcast_id, generate_analytics_id, generate_schedule_id,
    generate_message_id, generate_bot_message_id
)
from config import (
    USERS_COLLECTION, CHANNELS_COLLECTION, BROADCASTS_COLLECTION,
    ANALYTICS_COLLECTION, SCHEDULED_BROADCASTS_COLLECTION, 
    BROADCAST_MESSAGES_COLLECTION, BOT_MESSAGES_COLLECTION
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """Enhanced database operations with comprehensive CRUD functionality"""
    
    def __init__(self):
        self.db_connection = db_connection
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create database indexes for performance"""
        try:
            # Users collection indexes
            users_collection = self.db_connection.get_collection(USERS_COLLECTION)
            if users_collection is not None:
                users_collection.create_index("user_id", unique=True)
                users_collection.create_index("username")
                users_collection.create_index("join_date")
            
            # Channels collection indexes
            channels_collection = self.db_connection.get_collection(CHANNELS_COLLECTION)
            if channels_collection is not None:
                channels_collection.create_index([("user_id", ASCENDING), ("channel_id", ASCENDING)])
                channels_collection.create_index("user_id")
                channels_collection.create_index("channel_id")
                channels_collection.create_index("added_date")
            
            # Broadcasts collection indexes
            broadcasts_collection = self.db_connection.get_collection(BROADCASTS_COLLECTION)
            if broadcasts_collection is not None:
                broadcasts_collection.create_index("broadcast_id", unique=True)
                broadcasts_collection.create_index("user_id")
                broadcasts_collection.create_index("status")
                broadcasts_collection.create_index("created_date")
            
            # Analytics collection indexes
            analytics_collection = self.db_connection.get_collection(ANALYTICS_COLLECTION)
            if analytics_collection is not None:
                analytics_collection.create_index("user_id")
                analytics_collection.create_index("broadcast_id")
                analytics_collection.create_index("timestamp")
            
            logger.info("✅ Database indexes created successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not create indexes: {e}")
    
    # =============================================================================
    # USER OPERATIONS
    # =============================================================================
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None, is_admin: bool = False) -> UserModel:
        """Add or update user"""
        try:
            collection = self.db_connection.get_collection(USERS_COLLECTION)
            if collection is None:
                return None
            
            existing_user = collection.find_one({"_id": user_id})
            
            if existing_user:
                # Update existing user
                update_data = {
                    "last_active": datetime.utcnow(),
                "username": username,
                "first_name": first_name,
                    "last_name": last_name
                }
                collection.update_one({"_id": user_id}, {"$set": update_data})
                user_data = {**existing_user, **update_data}
                user_data['user_id'] = user_data.pop('_id')
                return UserModel.from_dict(user_data)
            else:
                # Create new user
                user = UserModel(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=is_admin
                )
                collection.insert_one(user.to_dict())
                logger.info(f"✅ New user added: {user_id}")
                return user
        except Exception as e:
            logger.error(f"❌ Error adding user: {e}")
            return None
    
    def get_user(self, user_id: int) -> Optional[UserModel]:
        """Get user by ID"""
        try:
            collection = self.db_connection.get_collection(USERS_COLLECTION)
            if collection is None:
                return None
            
            user_data = collection.find_one({"_id": user_id})
            if user_data:
                user_data['user_id'] = user_data.pop('_id')
                return UserModel.from_dict(user_data)
            return None
        except Exception as e:
            logger.error(f"❌ Error getting user: {e}")
            return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from database"""
        try:
            collection = self.db_connection.get_collection(USERS_COLLECTION)
            if collection is None:
                return []
            
            users = list(collection.find({}))
            # Convert MongoDB _id to user_id for consistency
            for user in users:
                if '_id' in user:
                    user['user_id'] = user['_id']
                    del user['_id']
            
            return users
        except Exception as e:
            logger.error(f"❌ Error getting all users: {e}")
            return []
    
    def get_user_channels(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all channels for a user"""
        try:
            collection = self.db_connection.get_collection(CHANNELS_COLLECTION)
            if collection is None:
                return []
    
            query = {"user_id": user_id}
            if active_only:
                query["is_active"] = True
            
            channels = []
            for channel_data in collection.find(query).sort("added_date", DESCENDING):
                channels.append({
                    "channel_id": channel_data["channel_id"],
                    "channel_name": channel_data["channel_name"],
                    "username": channel_data.get("username"),
                    "channel_type": channel_data.get("channel_type", "channel"),
                    "added_date": channel_data.get("added_date"),
                    "total_broadcasts": channel_data.get("total_broadcasts", 0),
                    "success_rate": channel_data.get("success_rate", 100.0)
                })
            return channels
        except Exception as e:
            logger.error(f"❌ Error getting user channels: {e}")
            return []
    
    def add_channel(self, channel_id: int, user_id: int, channel_name: str, username: str = None) -> bool:
        """Add channel for user"""
        try:
            collection = self.db_connection.get_collection(CHANNELS_COLLECTION)
            if collection is None:
                return False
            
            channel_data = {
                "channel_id": channel_id,
                "user_id": user_id,
                "channel_name": channel_name,
                "username": username,
                "added_at": datetime.now(),
                "is_active": True,
                "total_broadcasts": 0,
                "success_rate": 100.0
            }
            
            result = collection.update_one(
                {"channel_id": channel_id, "user_id": user_id},
                {"$set": channel_data},
                upsert=True
            )
            
            logger.info(f"Channel {channel_id} added for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding channel {channel_id} for user {user_id}: {e}")
            return False
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get user analytics summary"""
        try:
            # Return basic analytics structure for now
            return {
                "user_id": user_id,
                "period_days": days,
                "total_channels": len(self.get_user_channels(user_id)),
                "total_broadcasts": 0,
                "total_messages": 0,
                "successful_messages": 0,
                "failed_messages": 0,
                "success_rate": 100.0,
                "recent_broadcasts": [],
                "daily_stats": []
            }
        except Exception as e:
            logger.error(f"❌ Error getting user analytics: {e}")
            return {
                "user_id": 0,
                "period_days": 0,
                "total_channels": 0,
                "total_broadcasts": 0,
                "total_messages": 0,
                "successful_messages": 0,
                "failed_messages": 0,
                "success_rate": 0.0,
                "recent_broadcasts": [],
                "daily_stats": []
            }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for admin panel"""
        try:
            stats = {}
            
            # Get collection counts
            collections = [
                USERS_COLLECTION, CHANNELS_COLLECTION, BROADCASTS_COLLECTION,
                ANALYTICS_COLLECTION, SCHEDULED_BROADCASTS_COLLECTION,
                BROADCAST_MESSAGES_COLLECTION
            ]
            
            for collection_name in collections:
                collection = self.db_connection.get_collection(collection_name)
                if collection is not None:
                    stats[collection_name] = collection.count_documents({})
                else:
                    stats[collection_name] = 0
            
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {collection: 0 for collection in collections}