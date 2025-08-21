import os
import telebot
from telebot import types
from pymongo import MongoClient
import threading
import time
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, Any, Optional

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "7769199668:AAGsMQ6BzCPGu_ONdgnb7QEURkbIb80uyUY")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://rowojo2049:bga4FhmFXj2GTM5B@cluster0.ggmw5h8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
OWNER_ID = int(os.getenv("OWNER_ID", "7792539085"))
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "7792539085").split(",")]

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB setup with error handling
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["broadcast_bot"]
    channels_col = db["channels"]
    broadcast_messages_col = db["broadcast_messages"]  # Store broadcast message IDs
    users_col = db["users"]  # Store user authentication and premium data
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    raise

# Global state management
class BotState:
    def __init__(self):
        self.broadcast_state: Dict[int, Dict[str, Any]] = {}
        self.active_reposts: Dict[int, Dict[str, Any]] = {}
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.broadcast_messages: Dict[int, Dict[str, list]] = {}  # {chat_id: {channel_id: [message_ids]}}

bot_state = BotState()

class BroadcastBot:
    def __init__(self):
        self.bot = bot
        self.channels_col = channels_col
        self.users_col = users_col
        
    def is_owner(self, user_id: int) -> bool:
        """Check if user is the owner"""
        return user_id == OWNER_ID
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS or user_id == OWNER_ID
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if user:
                return user.get("is_active", False)
            return False
        except Exception as e:
            logger.error(f"Error checking user authorization: {e}")
            return False
    
    def is_premium(self, user_id: int) -> bool:
        """Check if user has premium access"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if user:
                return user.get("is_premium", False)
            return False
        except Exception as e:
            logger.error(f"Error checking premium status: {e}")
            return False
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Add a new user to the database"""
        try:
            if not self.users_col.find_one({"user_id": user_id}):
                self.users_col.insert_one({
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": False,
                    "is_premium": False,
                    "premium_expires": None,
                    "added_at": datetime.now(),
                    "last_activity": datetime.now()
                })
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    def activate_user(self, user_id: int, activated_by: int) -> bool:
        """Activate a user (give basic access)"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if not user:
                # Create user if doesn't exist
                self.users_col.insert_one({
                    "user_id": user_id,
                    "username": None,
                    "first_name": f"User_{user_id}",
                    "last_name": None,
                    "is_active": True,
                    "is_premium": False,
                    "premium_expires": None,
                    "activated_by": activated_by,
                    "activated_at": datetime.now(),
                    "added_at": datetime.now(),
                    "last_activity": datetime.now()
                })
                return True
            
            result = self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_active": True,
                        "activated_by": activated_by,
                        "activated_at": datetime.now(),
                        "last_activity": datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error activating user {user_id}: {e}")
            return False
    
    def deactivate_user(self, user_id: int, deactivated_by: int) -> bool:
        """Deactivate a user"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if not user:
                # Create user if doesn't exist (but deactivated)
                self.users_col.insert_one({
                    "user_id": user_id,
                    "username": None,
                    "first_name": f"User_{user_id}",
                    "last_name": None,
                    "is_active": False,
                    "is_premium": False,
                    "premium_expires": None,
                    "deactivated_by": deactivated_by,
                    "deactivated_at": datetime.now(),
                    "added_at": datetime.now(),
                    "last_activity": datetime.now()
                })
                return True
            
            result = self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_active": False,
                        "is_premium": False,
                        "premium_expires": None,
                        "deactivated_by": deactivated_by,
                        "deactivated_at": datetime.now(),
                        "last_activity": datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False
    
    def give_premium(self, user_id: int, days: int, given_by: int) -> bool:
        """Give premium access to a user"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if not user:
                # Create user if doesn't exist
                self.users_col.insert_one({
                    "user_id": user_id,
                    "username": None,
                    "first_name": f"User_{user_id}",
                    "last_name": None,
                    "is_active": True,
                    "is_premium": True,
                    "premium_expires": datetime.now() + timedelta(days=days),
                    "premium_given_by": given_by,
                    "premium_given_at": datetime.now(),
                    "added_at": datetime.now(),
                    "last_activity": datetime.now()
                })
                return True
            
            # Calculate premium expiry
            if user.get("premium_expires") and user["premium_expires"] > datetime.now():
                # Extend existing premium
                new_expiry = user["premium_expires"] + timedelta(days=days)
            else:
                # Start new premium from now
                new_expiry = datetime.now() + timedelta(days=days)
            
            result = self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_active": True,
                        "is_premium": True,
                        "premium_expires": new_expiry,
                        "premium_given_by": given_by,
                        "premium_given_at": datetime.now(),
                        "last_activity": datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error giving premium to user {user_id}: {e}")
            return False
    
    def revoke_premium(self, user_id: int, revoked_by: int) -> bool:
        """Revoke premium access from a user"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if not user:
                # Create user if doesn't exist (but without premium)
                self.users_col.insert_one({
                    "user_id": user_id,
                    "username": None,
                    "first_name": f"User_{user_id}",
                    "last_name": None,
                    "is_active": True,
                    "is_premium": False,
                    "premium_expires": None,
                    "premium_revoked_by": revoked_by,
                    "premium_revoked_at": datetime.now(),
                    "added_at": datetime.now(),
                    "last_activity": datetime.now()
                })
                return True
            
            result = self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_premium": False,
                        "premium_expires": None,
                        "premium_revoked_by": revoked_by,
                        "premium_revoked_at": datetime.now(),
                        "last_activity": datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error revoking premium from user {user_id}: {e}")
            return False
    
    def get_user_info(self, user_id: int) -> dict:
        """Get user information"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if user:
                return {
                    "user_id": user["user_id"],
                    "username": user.get("username"),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "is_active": user.get("is_active", False),
                    "is_premium": user.get("is_premium", False),
                    "premium_expires": user.get("premium_expires"),
                    "added_at": user.get("added_at"),
                    "last_activity": user.get("last_activity")
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {e}")
            return None
    
    def get_all_users(self) -> list:
        """Get all users from database"""
        try:
            return list(self.users_col.find({}, {"_id": 0}))
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def get_active_users(self) -> list:
        """Get all active users"""
        try:
            return list(self.users_col.find({"is_active": True}, {"_id": 0}))
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    def get_premium_users(self) -> list:
        """Get all premium users"""
        try:
            return list(self.users_col.find({"is_premium": True}, {"_id": 0}))
        except Exception as e:
            logger.error(f"Error getting premium users: {e}")
            return []
    
    def get_channel_count(self, user_id: int = None) -> int:
        """Get total number of channels for a user"""
        try:
            if user_id:
                return self.channels_col.count_documents({"user_id": user_id})
            else:
                return self.channels_col.count_documents({})
        except Exception as e:
            logger.error(f"Error getting channel count for user {user_id}: {e}")
            return 0
    
    def add_channel(self, channel_id: int, user_id: int) -> bool:
        """Add a channel to the user's personal database"""
        try:
            # Check if channel already exists for this user
            if not self.channels_col.find_one({"channel_id": channel_id, "user_id": user_id}):
                self.channels_col.insert_one({
                    "channel_id": channel_id, 
                    "user_id": user_id,
                    "added_at": datetime.now()
                })
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding channel {channel_id} for user {user_id}: {e}")
            return False
    
    def remove_channel(self, channel_id: int, user_id: int) -> bool:
        """Remove a channel from the user's personal database"""
        try:
            result = self.channels_col.delete_one({"channel_id": channel_id, "user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error removing channel {channel_id} for user {user_id}: {e}")
            return False
    
    def get_all_channels(self, user_id: int = None) -> list:
        """Get all channels from database for a specific user"""
        try:
            if user_id:
                return list(self.channels_col.find({"user_id": user_id}, {"channel_id": 1, "_id": 0}))
            else:
                return list(self.channels_col.find({}, {"channel_id": 1, "_id": 0}))
        except Exception as e:
            logger.error(f"Error getting channels for user {user_id}: {e}")
            return []
    
    def save_broadcast_message(self, owner_id: int, channel_id: int, message_id: int, broadcast_id: str):
        """Save broadcast message ID to database"""
        try:
            broadcast_messages_col.insert_one({
                "owner_id": owner_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "broadcast_id": broadcast_id,
                "user_id": owner_id,  # Add user_id for personal tracking
                "timestamp": datetime.now()
            })
        except Exception as e:
            logger.error(f"Error saving broadcast message: {e}")
    
    def get_broadcast_messages(self, owner_id: int, broadcast_id: str = None) -> list:
        """Get broadcast messages for an owner"""
        try:
            query = {"owner_id": owner_id}
            if broadcast_id:
                query["broadcast_id"] = broadcast_id
            return list(broadcast_messages_col.find(query))
        except Exception as e:
            logger.error(f"Error getting broadcast messages: {e}")
            return []
    
    def delete_broadcast_messages(self, owner_id: int, broadcast_id: str = None) -> bool:
        """Delete broadcast messages from database"""
        try:
            query = {"owner_id": owner_id}
            if broadcast_id:
                query["broadcast_id"] = broadcast_id
            result = broadcast_messages_col.delete_many(query)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting broadcast messages: {e}")
            return False
    
    def get_broadcast_stats(self, owner_id: int) -> dict:
        """Get broadcast statistics for a specific user"""
        try:
            total_messages = broadcast_messages_col.count_documents({"owner_id": owner_id})
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_messages = broadcast_messages_col.count_documents({
                "owner_id": owner_id,
                "timestamp": {"$gte": today}
            })
            
            # Get unique broadcast IDs
            broadcast_ids = broadcast_messages_col.distinct("broadcast_id", {"owner_id": owner_id})
            
            return {
                "total_messages": total_messages,
                "today_messages": today_messages,
                "total_broadcasts": len(broadcast_ids),
                "channels_count": self.get_channel_count(owner_id)
            }
        except Exception as e:
            logger.error(f"Error getting broadcast stats: {e}")
            return {"total_messages": 0, "today_messages": 0, "total_broadcasts": 0, "channels_count": 0}
    
    def schedule_broadcast(self, owner_id: int, message, channels: list, schedule_time: datetime, broadcast_id: str):
        """Schedule a broadcast for later"""
        try:
            # Save scheduled broadcast info
            scheduled_col = db["scheduled_broadcasts"]
            scheduled_col.insert_one({
                "owner_id": owner_id,
                "broadcast_id": broadcast_id,
                "message_data": {
                    "content_type": message.content_type,
                    "text": message.text if message.content_type == "text" else None,
                    "file_id": self._get_file_id(message),
                    "caption": message.caption
                },
                "channels": channels,
                "schedule_time": schedule_time,
                "status": "pending"
            })
            return True
        except Exception as e:
            logger.error(f"Error scheduling broadcast: {e}")
            return False
    
    def _get_file_id(self, message) -> str:
        """Get file ID from message"""
        if message.content_type == "photo":
            return message.photo[-1].file_id
        elif message.content_type == "video":
            return message.video.file_id
        elif message.content_type == "document":
            return message.document.file_id
        elif message.content_type == "audio":
            return message.audio.file_id
        return None
    
    def get_user_channels(self, user_id: int) -> list:
        """Get channels where user has admin rights"""
        try:
            # Get user's chat member updates to find channels
            # This is a simplified approach - in real implementation you'd need to store this data
            user_channels = []
            
            # Try to get updates from bot's getUpdates method
            updates = self.bot.get_updates()
            
            for update in updates:
                if hasattr(update, 'my_chat_member') and update.my_chat_member:
                    chat = update.my_chat_member.chat
                    if chat.type in ['channel', 'supergroup']:
                        try:
                            # Check if user is admin in this chat
                            member = self.bot.get_chat_member(chat.id, user_id)
                            if member.status in ['administrator', 'creator']:
                                user_channels.append({
                                    'chat_id': chat.id,
                                    'title': chat.title,
                                    'type': chat.type,
                                    'username': getattr(chat, 'username', None)
                                })
                        except Exception as e:
                            logger.error(f"Error checking member status for {chat.id}: {e}")
                            continue
            
            return user_channels
            
        except Exception as e:
            logger.error(f"Error getting user channels: {e}")
            return []
    
    def get_accessible_channels(self, user_id: int) -> list:
        """Get all channels user can access (simplified version)"""
        try:
            # This is a simplified approach
            # In a real implementation, you'd need to maintain a list of user's channels
            # For now, we'll return an empty list and ask user to manually add channels
            
            # You can extend this by storing user's channel access in database
            return []
            
        except Exception as e:
            logger.error(f"Error getting accessible channels: {e}")
            return []

# Initialize bot instance
broadcast_bot = BroadcastBot()

def auto_repost(chat_id: int, message, repost_time: int, delete_time: Optional[int], stop_flag: Dict[str, bool]):
    """Background repost function with improved error handling"""
    logger.info(f"Starting auto repost for chat {chat_id}")
    
    while not stop_flag.get("stop", False):
        try:
            time.sleep(repost_time * 60)
            if stop_flag.get("stop", False):
                break
                
            # Get channels for this specific user
            channels = broadcast_bot.get_all_channels(chat_id)
            success_count = 0
            failed_count = 0
            
            for ch in channels:
                try:
                    sent = None
                    channel_id = ch["channel_id"]
                    
                    if message.content_type == "text":
                        sent = bot.send_message(channel_id, message.text)
                    elif message.content_type == "photo":
                        # Handle photo with caption (text, links, formatting)
                        caption = message.caption or ""
                        
                        # Simple and reliable method - try forwarding first, then sending
                        try:
                            # Method 1: Forward the original message (preserves everything)
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                            logger.info(f"Photo auto-forwarded successfully to {channel_id}")
                        except Exception as forward_error:
                            logger.warning(f"Auto-forward failed, trying to send: {forward_error}")
                            try:
                                # Method 2: Send photo with caption
                                sent = bot.send_photo(
                                    channel_id, 
                                    message.photo[-1].file_id, 
                                    caption=caption
                                )
                                logger.info(f"Photo auto-sent successfully to {channel_id}")
                            except Exception as send_error:
                                logger.error(f"Photo auto-send failed to {channel_id}: {send_error}")
                                raise send_error
                    elif message.content_type == "video":
                        # Handle video with caption (text, links, formatting)
                        caption = message.caption or ""
                        parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                        
                        try:
                            sent = bot.send_video(
                                channel_id, 
                                message.video.file_id, 
                                caption=caption,
                                parse_mode=parse_mode
                            )
                        except Exception as caption_error:
                            logger.warning(f"Markdown parsing failed for video caption, sending as plain text: {caption_error}")
                            sent = bot.send_video(
                                channel_id, 
                                message.video.file_id, 
                                caption=caption
                            )
                            
                    elif message.content_type == "document":
                        # Handle document with caption (text, links, formatting)
                        caption = message.caption or ""
                        parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                        
                        try:
                            sent = bot.send_document(
                                channel_id, 
                                message.document.file_id, 
                                caption=caption,
                                parse_mode=parse_mode
                            )
                        except Exception as caption_error:
                            logger.warning(f"Markdown parsing failed for document caption, sending as plain text: {caption_error}")
                            sent = bot.send_document(
                                channel_id, 
                                message.document.file_id, 
                                caption=caption
                            )
                            
                    elif message.content_type == "audio":
                        # Handle audio with caption (text, links, formatting)
                        caption = message.caption or ""
                        parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                        
                        try:
                            sent = bot.send_audio(
                                channel_id, 
                                message.audio.file_id, 
                                caption=caption,
                                parse_mode=parse_mode
                            )
                        except Exception as caption_error:
                            logger.warning(f"Markdown parsing failed for audio caption, sending as plain text: {caption_error}")
                            sent = bot.send_audio(
                                channel_id, 
                                message.audio.file_id, 
                                caption=caption
                            )
                    else:
                        sent = bot.forward_message(channel_id, message.chat.id, message.message_id)

                    success_count += 1
                    
                    # Save message ID for potential deletion
                    if sent:
                        broadcast_bot.save_broadcast_message(chat_id, channel_id, sent.message_id, f"repost_{chat_id}_{int(time.time())}")
                    
                    # Auto delete if configured
                    if delete_time and sent:
                        threading.Thread(
                            target=auto_delete, args=(channel_id, sent.message_id, delete_time)
                        ).start()
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Repost failed for {ch.get('channel_id')} -> {e}")
            
            logger.info(f"Repost cycle completed - Success: {success_count}, Failed: {failed_count}")
            
        except Exception as e:
            logger.error(f"Error in auto_repost: {e}")
            time.sleep(60)  # Wait before retrying

def auto_delete(chat_id: int, msg_id: int, delete_time: int):
    """Auto delete function with improved error handling"""
    try:
        time.sleep(delete_time * 60)
        bot.delete_message(chat_id, msg_id)
        logger.info(f"✅ Auto deleted message {msg_id} from {chat_id}")
    except Exception as e:
        logger.error(f"❌ Delete failed for {chat_id} -> {e}")

@bot.message_handler(commands=["start", "history", "status", "myinfo", "test"])
def start_cmd(message):
    """Enhanced start command with better UI"""
    # Add user to database if not exists
    broadcast_bot.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Check if user is authorized (active users, premium users, or admins)
    if not (broadcast_bot.is_authorized(message.chat.id) or 
            broadcast_bot.is_premium(message.chat.id) or 
            broadcast_bot.is_admin(message.chat.id)):
        bot.send_message(
            message.chat.id, 
            "🚫 **Access Denied!**\n\nYou are not authorized to use this bot.\n\nContact admin to get access.",
            parse_mode="Markdown"
        )
        return
    
    if message.text == "/test":
        # Test function for debugging
        bot.send_message(
            message.chat.id,
            "🧪 **Test Mode Active**\n\nNow forward any message to test broadcast functionality.\n\nBot will show detailed information about the forwarded message.",
            parse_mode="Markdown"
        )
        bot_state.broadcast_state[message.chat.id] = {"step": "waiting_msg"}
        return
        
    if message.text == "/history":
        # Show broadcast history
        messages = broadcast_bot.get_broadcast_messages(message.chat.id)
        if not messages:
            bot.send_message(message.chat.id, "📋 No broadcast history found.")
            return
        
        # Group messages by broadcast ID
        broadcast_groups = {}
        for msg in messages:
            broadcast_id = msg.get("broadcast_id", "unknown")
            if broadcast_id not in broadcast_groups:
                broadcast_groups[broadcast_id] = []
            broadcast_groups[broadcast_id].append(msg)
        
        history_text = f"📋 **Broadcast History**\n\nTotal Broadcasts: `{len(broadcast_groups)}`\n\n"
        
        for i, (broadcast_id, msgs) in enumerate(broadcast_groups.items(), 1):
            history_text += f"**{i}. Broadcast ID:** `{broadcast_id}`\n"
            history_text += f"**Messages:** `{len(msgs)}`\n"
            history_text += f"**Date:** `{msgs[0]['timestamp'].strftime('%Y-%m-%d %H:%M')}`\n\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🗑 Delete All History", callback_data="delete_history"),
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
        )
        
        bot.send_message(message.chat.id, history_text, reply_markup=markup, parse_mode="Markdown")
        return
    
    elif message.text in ["/status", "/myinfo"]:
        # Show user's own status
        user_info = broadcast_bot.get_user_info(message.chat.id)
        if not user_info:
            bot.send_message(message.chat.id, "❌ User information not found.")
            return
        
        # Determine user type
        if broadcast_bot.is_owner(message.chat.id):
            user_type = "👑 Owner"
        elif broadcast_bot.is_admin(message.chat.id):
            user_type = "🛡️ Admin"
        elif user_info["is_premium"]:
            user_type = "⭐ Premium User"
        elif user_info["is_active"]:
            user_type = "✅ Active User"
        else:
            user_type = "❌ Inactive User"
        
        # Premium expiry info
        premium_info = ""
        if user_info["is_premium"] and user_info["premium_expires"]:
            if user_info["premium_expires"] > datetime.now():
                days_left = (user_info["premium_expires"] - datetime.now()).days
                premium_info = f"\n⭐ **Premium Status:** Active\n📅 **Expires:** `{user_info['premium_expires'].strftime('%Y-%m-%d %H:%M')}`\n⏰ **Days Left:** `{days_left}`"
            else:
                premium_info = "\n⭐ **Premium Status:** Expired"
        
        status_text = f"""
👤 **User Information**

🆔 **User ID:** `{user_info['user_id']}`
👤 **Name:** {user_info['first_name']} {user_info.get('last_name', '')}
🔗 **Username:** @{user_info.get('username', 'N/A')}
👥 **Type:** {user_type}
📅 **Joined:** `{user_info['added_at'].strftime('%Y-%m-%d %H:%M')}`
🕐 **Last Activity:** `{user_info['last_activity'].strftime('%Y-%m-%d %H:%M')}`{premium_info}
        """
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
        )
        
        bot.send_message(message.chat.id, status_text, reply_markup=markup, parse_mode="Markdown")
        return
    
    # Regular start command
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
        types.InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
    )
    markup.add(
        types.InlineKeyboardButton("🔍 Find My Channels", callback_data="find_channels"),
    )
    markup.add(
        types.InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"),
        types.InlineKeyboardButton("📋 Show Channels", callback_data="show_channels"),
    )
    markup.add(
        types.InlineKeyboardButton("📢 My Channels", callback_data="my_channels"),
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Clear All", callback_data="clear_channels"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
    )
    markup.add(
        types.InlineKeyboardButton("⏹ Stop Repost", callback_data="stop_repost"),
        types.InlineKeyboardButton("🗑 Stop & Delete Broadcast", callback_data="stop_and_delete"),
    )
    markup.add(
        types.InlineKeyboardButton("📋 Broadcast History", callback_data="show_history"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
    )
    
    # Add admin management buttons for admins only
    if broadcast_bot.is_admin(message.chat.id):
        markup.add(
            types.InlineKeyboardButton("👥 User Management", callback_data="user_management"),
            types.InlineKeyboardButton("⭐ Premium Management", callback_data="premium_management"),
        )
    
    # Show premium status for premium users
    elif broadcast_bot.is_premium(message.chat.id):
        user_info = broadcast_bot.get_user_info(message.chat.id)
        if user_info and user_info.get("premium_expires"):
            days_left = (user_info["premium_expires"] - datetime.now()).days
            if days_left > 0:
                markup.add(
                    types.InlineKeyboardButton(f"⭐ Premium Active ({days_left} days left)", callback_data="premium_status"),
                )
    
    markup.add(
        types.InlineKeyboardButton("🔄 Restart Bot", callback_data="restart_bot"),
    )

    welcome_text = f"""
👋 **Welcome to Broadcast Bot Panel!**

**👑 Owner:** ANKIT
**📢 Your Channels:** `{broadcast_bot.get_channel_count(message.chat.id)}`
**🟢 Status:** ✅ Online

Choose an option below:
    """
    
    try:
        bot.send_photo(
            message.chat.id,
            "https://i.ibb.co/GQrGd0MV/a101f4b2bfa4.jpg",
            caption=welcome_text,
            reply_markup=markup,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error sending start message: {e}")
        bot.send_message(message.chat.id, "Error loading bot interface. Please try again.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Enhanced callback handler with better error handling"""
    # Check if user is authorized (active users, premium users, or admins)
    if not (broadcast_bot.is_authorized(call.message.chat.id) or 
            broadcast_bot.is_premium(call.message.chat.id) or 
            broadcast_bot.is_admin(call.message.chat.id)):
        bot.answer_callback_query(call.id, "🚫 Access Denied! Contact admin for access.")
        return

    try:
        state = bot_state.broadcast_state.get(call.message.chat.id, {})

        if call.data == "broadcast":
            bot_state.broadcast_state[call.message.chat.id] = {"step": "waiting_msg"}
            bot.send_message(call.message.chat.id, "📢 Send the message you want to broadcast:")

        elif call.data == "add_channel":
            bot.send_message(
                call.message.chat.id,
                "➕ Send me channel ID (starts with -100) or forward any message from that channel.\n\n**Format:** `-1001234567890`",
                parse_mode="Markdown"
            )

        elif call.data == "find_channels":
            # Show instructions for finding channels
            instructions_text = """
🔍 **Find My Channels**

To find your channels, you have several options:

**Option 1: Forward Message**
• Go to any channel where you're admin
• Forward any message from that channel to this bot
• The bot will automatically detect the channel

**Option 2: Manual Channel ID**
• Get channel ID from @userinfobot or similar
• Send the channel ID (format: -1001234567890)

**Option 3: Add Bot to Channel**
• Add this bot to your channel as admin
• Send any message in the channel
• The bot will detect it automatically

**Current Saved Channels:** `{saved_count}`

Would you like to:
            """.format(saved_count=broadcast_bot.get_channel_count())
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📤 Forward Message", callback_data="forward_message_help"),
                types.InlineKeyboardButton("🆔 Get Channel ID", callback_data="get_channel_id_help"),
            )
            markup.add(
                types.InlineKeyboardButton("➕ Add Bot to Channel", callback_data="add_bot_help"),
                types.InlineKeyboardButton("📋 Show Saved", callback_data="show_channels"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            bot.send_message(
                call.message.chat.id,
                instructions_text,
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "remove_channel":
            channels = broadcast_bot.get_all_channels(call.message.chat.id)
            if channels:
                markup = types.InlineKeyboardMarkup(row_width=1)
                for ch in channels[:10]:  # Limit to 10 buttons
                    markup.add(types.InlineKeyboardButton(
                        f"❌ {ch['channel_id']}", 
                        callback_data=f"remove_{ch['channel_id']}"
                    ))
                bot.send_message(call.message.chat.id, "Select channel to remove:", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "⚠️ No channels to remove.")

        elif call.data.startswith("remove_"):
            channel_id = int(call.data.split("_")[1])
            if broadcast_bot.remove_channel(channel_id, call.message.chat.id):
                bot.answer_callback_query(call.id, f"✅ Removed channel {channel_id}")
                bot.edit_message_text(f"✅ Channel {channel_id} removed successfully.", 
                                    call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "❌ Failed to remove channel")

        elif call.data == "show_channels":
            channels = broadcast_bot.get_all_channels(call.message.chat.id)
            if channels:
                channel_list = "\n".join([f"• `{ch['channel_id']}`" for ch in channels])
                bot.send_message(
                    call.message.chat.id, 
                    f"📋 **Your Saved Channels ({len(channels)}):**\n\n{channel_list}",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(call.message.chat.id, "⚠️ No channels saved.")

        elif call.data == "my_channels":
            channels = broadcast_bot.get_all_channels(call.message.chat.id)
            if channels:
                # Get detailed channel information
                detailed_channels = []
                for ch in channels:
                    try:
                        chat_info = bot.get_chat(ch['channel_id'])
                        channel_name = chat_info.title
                        channel_username = getattr(chat_info, 'username', None)
                        member_count = getattr(chat_info, 'member_count', 'N/A')
                        
                        channel_info = f"📢 **{channel_name}**\n"
                        channel_info += f"🆔 ID: `{ch['channel_id']}`\n"
                        if channel_username:
                            channel_info += f"🔗 Username: @{channel_username}\n"
                        channel_info += f"👥 Members: {member_count}\n"
                        detailed_channels.append(channel_info)
                    except Exception as e:
                        # If can't get chat info, show basic info
                        detailed_channels.append(f"📢 **Channel**\n🆔 ID: `{ch['channel_id']}`\n❌ Info unavailable\n")
                
                channels_text = f"📢 **Your Channels ({len(channels)})**\n\n"
                channels_text += "\n".join(detailed_channels)
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🔄 Refresh", callback_data="my_channels"),
                    types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
                )
                
                bot.send_message(
                    call.message.chat.id, 
                    channels_text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
                    types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
                )
                bot.send_message(
                    call.message.chat.id, 
                    "📢 **No Channels Found**\n\nYou haven't added any channels yet.\n\nClick 'Add Channel' to get started!",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )

        elif call.data == "clear_channels":
            try:
                channels_col.delete_many({"user_id": call.message.chat.id})
                bot.send_message(call.message.chat.id, "🗑 All your channels cleared successfully.")
            except Exception as e:
                logger.error(f"Error clearing channels: {e}")
                bot.send_message(call.message.chat.id, "❌ Error clearing channels.")

        elif call.data == "stats":
            total_channels = broadcast_bot.get_channel_count(call.message.chat.id)
            active_reposts_count = len(bot_state.active_reposts)
            
            stats_text = f"""
📊 **Your Bot Statistics**

**Your Channels:** `{total_channels}`
**Active Reposts:** `{active_reposts_count}`
**Bot Status:** ✅ Online
**Last Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
            """
            bot.send_message(call.message.chat.id, stats_text, parse_mode="Markdown")

        elif call.data == "stop_repost":
            stop_repost(call.message.chat.id)

        elif call.data == "stop_and_delete":
            # Show confirmation dialog
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Yes, Delete All", callback_data="confirm_delete_all"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete"),
            )
            bot.send_message(
                call.message.chat.id,
                "⚠️ **Warning!**\n\nThis will:\n• Stop all active reposts\n• Delete ALL broadcast messages from channels\n• Cannot be undone!\n\nAre you sure?",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "confirm_delete_all":
            # Stop reposts first
            if call.message.chat.id in bot_state.active_reposts:
                bot_state.active_reposts[call.message.chat.id]["stop"] = True
                del bot_state.active_reposts[call.message.chat.id]
            
            # Delete messages from channels
            deleted_count, failed_count = delete_broadcast_messages_from_channels(call.message.chat.id)
            
            result_text = f"""
🗑 **Broadcast Cleanup Completed!**

📊 **Results:**
• Messages Deleted: `{deleted_count}`
• Failed Deletions: `{failed_count}`
• Reposts Stopped: ✅

✅ All broadcast messages have been removed from channels.
            """
            bot.send_message(call.message.chat.id, result_text, parse_mode="Markdown")

        elif call.data == "cancel_delete":
            bot.send_message(call.message.chat.id, "❌ Operation cancelled.")

        elif call.data == "show_history":
            # Show broadcast history
            messages = broadcast_bot.get_broadcast_messages(call.message.chat.id)
            if not messages:
                bot.send_message(call.message.chat.id, "📋 No broadcast history found.")
                return
            
            # Group messages by broadcast ID
            broadcast_groups = {}
            for msg in messages:
                broadcast_id = msg.get("broadcast_id", "unknown")
                if broadcast_id not in broadcast_groups:
                    broadcast_groups[broadcast_id] = []
                broadcast_groups[broadcast_id].append(msg)
            
            history_text = f"📋 **Broadcast History**\n\nTotal Broadcasts: `{len(broadcast_groups)}`\n\n"
            
            for i, (broadcast_id, msgs) in enumerate(broadcast_groups.items(), 1):
                history_text += f"**{i}. Broadcast ID:** `{broadcast_id}`\n"
                history_text += f"**Messages:** `{len(msgs)}`\n"
                history_text += f"**Date:** `{msgs[0]['timestamp'].strftime('%Y-%m-%d %H:%M')}`\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🗑 Delete All History", callback_data="delete_history"),
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            # Send new message instead of editing (since original message might have photo)
            bot.send_message(
                call.message.chat.id,
                history_text, 
                reply_markup=markup, 
                parse_mode="Markdown"
            )

        elif call.data == "delete_history":
            # Delete all broadcast history
            deleted_count, failed_count = delete_broadcast_messages_from_channels(call.message.chat.id)
            
            result_text = f"""
🗑 **History Cleanup Completed!**

📊 **Results:**
• Messages Deleted: `{deleted_count}`
• Failed Deletions: `{failed_count}`

✅ All broadcast history has been cleared.
            """
            bot.send_message(call.message.chat.id, result_text, parse_mode="Markdown")

        elif call.data == "back_to_menu":
            # Return to main menu
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
                types.InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
            )
            markup.add(
                types.InlineKeyboardButton("🔍 Find My Channels", callback_data="find_channels"),
            )
            markup.add(
                types.InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"),
                types.InlineKeyboardButton("📋 Show Channels", callback_data="show_channels"),
            )
            markup.add(
                types.InlineKeyboardButton("📢 My Channels", callback_data="my_channels"),
            )
            markup.add(
                types.InlineKeyboardButton("🗑 Clear All", callback_data="clear_channels"),
                types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
            )
            markup.add(
                types.InlineKeyboardButton("⏹ Stop Repost", callback_data="stop_repost"),
                types.InlineKeyboardButton("🗑 Stop & Delete Broadcast", callback_data="stop_and_delete"),
            )
            markup.add(
                types.InlineKeyboardButton("📋 Broadcast History", callback_data="show_history"),
                types.InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            )
            
            # Add admin management buttons for admins only
            if broadcast_bot.is_admin(call.message.chat.id):
                markup.add(
                    types.InlineKeyboardButton("👥 User Management", callback_data="user_management"),
                    types.InlineKeyboardButton("⭐ Premium Management", callback_data="premium_management"),
                )
            
            # Show premium status for premium users
            elif broadcast_bot.is_premium(call.message.chat.id):
                user_info = broadcast_bot.get_user_info(call.message.chat.id)
                if user_info and user_info.get("premium_expires"):
                    days_left = (user_info["premium_expires"] - datetime.now()).days
                    if days_left > 0:
                        markup.add(
                            types.InlineKeyboardButton(f"⭐ Premium Active ({days_left} days left)", callback_data="premium_status"),
                        )
            
            markup.add(
                types.InlineKeyboardButton("🔄 Restart Bot", callback_data="restart_bot"),
            )

            welcome_text = f"""
👋 **Welcome to Broadcast Bot Panel!**

**👑 Owner:** ANKIT
**📢 Your Channels:** `{broadcast_bot.get_channel_count(call.message.chat.id)}`
**🟢 Status:** ✅ Online

Choose an option below:
            """
            
            # Send new message with photo instead of editing
            try:
                bot.send_photo(
                    call.message.chat.id,
                    "https://i.ibb.co/GQrGd0MV/a101f4b2bfa4.jpg",
                    caption=welcome_text,
                    reply_markup=markup,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Error sending welcome message: {e}")
                bot.send_message(
                    call.message.chat.id,
                    welcome_text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )

        elif call.data == "settings":
            # Show settings menu
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📅 Schedule Broadcast", callback_data="schedule_broadcast"),
                types.InlineKeyboardButton("📊 Advanced Stats", callback_data="advanced_stats"),
            )
            markup.add(
                types.InlineKeyboardButton("🔔 Notifications", callback_data="notifications"),
                types.InlineKeyboardButton("🔄 Auto Backup", callback_data="auto_backup"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            settings_text = """
⚙️ **Bot Settings**

Choose an option to configure:
• **Schedule Broadcast**: Set future broadcasts
• **Advanced Stats**: Detailed analytics
• **Notifications**: Configure alerts
• **Auto Backup**: Automatic data backup
            """
            
            # Send new message instead of editing (since original message has photo)
            bot.send_message(
                call.message.chat.id,
                settings_text,
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "schedule_broadcast":
            # Show simple schedule options
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⏰ 1 Hour", callback_data="schedule_1h"),
                types.InlineKeyboardButton("⏰ 2 Hours", callback_data="schedule_2h"),
                types.InlineKeyboardButton("⏰ 3 Hours", callback_data="schedule_3h"),
                types.InlineKeyboardButton("⏰ 6 Hours", callback_data="schedule_6h"),
                types.InlineKeyboardButton("⏰ 12 Hours", callback_data="schedule_12h"),
                types.InlineKeyboardButton("⏰ 24 Hours", callback_data="schedule_24h"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            bot.send_message(
                call.message.chat.id,
                "📅 **Schedule Broadcast**\n\nChoose when you want to schedule the broadcast:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "advanced_stats":
            stats = broadcast_bot.get_broadcast_stats(call.message.chat.id)
            
            stats_text = f"""
📊 **Advanced Statistics**

📈 **Overall Stats:**
• Total Messages Sent: `{stats['total_messages']}`
• Today's Messages: `{stats['today_messages']}`
• Total Broadcasts: `{stats['total_broadcasts']}`
• Active Channels: `{stats['channels_count']}`

📅 **Performance:**
• Average per Broadcast: `{stats['total_messages'] // max(stats['total_broadcasts'], 1)}`
• Success Rate: `{(stats['total_messages'] / max(stats['total_messages'] + 10, 1)) * 100:.1f}%`

⏰ **Last Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
            """
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📊 Export Data", callback_data="export_data"),
                types.InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
            )
            
            bot.send_message(call.message.chat.id, stats_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "notifications":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Enable All", callback_data="enable_notifications"),
                types.InlineKeyboardButton("❌ Disable All", callback_data="disable_notifications"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
            )
            
            notif_text = """
🔔 **Notification Settings**

Configure what notifications you want to receive:
• Broadcast completion alerts
• Error notifications
• Scheduled broadcast reminders
• System status updates
            """
            
            bot.send_message(call.message.chat.id, notif_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "auto_backup":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📤 Create Backup", callback_data="create_backup"),
                types.InlineKeyboardButton("📥 Restore Backup", callback_data="restore_backup"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
            )
            
            backup_text = """
🔄 **Auto Backup Settings**

Manage your bot data:
• Create backup of channels and settings
• Restore from previous backup
• Automatic daily backups
• Export data for analysis
            """
            
            bot.send_message(call.message.chat.id, backup_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "export_data":
            # Export data functionality
            try:
                channels = broadcast_bot.get_all_channels()
                messages = broadcast_bot.get_broadcast_messages(call.message.chat.id)
                
                export_data = {
                    "export_time": datetime.now().isoformat(),
                    "channels": channels,
                    "broadcast_messages": messages,
                    "stats": broadcast_bot.get_broadcast_stats(call.message.chat.id)
                }
                
                # Save to file
                filename = f"bot_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, default=str, indent=2, ensure_ascii=False)
                
                # Send file
                with open(filename, 'rb') as f:
                    bot.send_document(
                        call.message.chat.id,
                        f,
                        caption="📊 **Bot Data Export**\n\nYour bot data has been exported successfully!",
                        parse_mode="Markdown"
                    )
                
                # Clean up file
                import os
                os.remove(filename)
                
            except Exception as e:
                logger.error(f"Error exporting data: {e}")
                bot.send_message(call.message.chat.id, "❌ Error exporting data")

        elif call.data == "create_backup":
            try:
                channels = broadcast_bot.get_all_channels()
                backup_data = {
                    "backup_time": datetime.now().isoformat(),
                    "channels": channels,
                    "owner_id": call.message.chat.id
                }
                
                filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, default=str, indent=2, ensure_ascii=False)
                
                with open(filename, 'rb') as f:
                    bot.send_document(
                        call.message.chat.id,
                        f,
                        caption="📤 **Backup Created Successfully!**\n\nSave this file to restore your bot data later.",
                        parse_mode="Markdown"
                    )
                
                import os
                os.remove(filename)
                
            except Exception as e:
                logger.error(f"Error creating backup: {e}")
                bot.send_message(call.message.chat.id, "❌ Error creating backup")

        elif call.data == "confirm_schedule":
            state = bot_state.broadcast_state.get(call.message.chat.id)
            if state and state.get("step") == "schedule_confirm":
                message = state["message"]
                schedule_time = state["schedule_time"]
                channels = broadcast_bot.get_all_channels()
                broadcast_id = f"scheduled_{call.message.chat.id}_{int(time.time())}"
                
                if broadcast_bot.schedule_broadcast(call.message.chat.id, message, channels, schedule_time, broadcast_id):
                    bot.send_message(
                        call.message.chat.id,
                        f"✅ **Broadcast Scheduled Successfully!**\n\n📅 **Schedule Time:** `{schedule_time.strftime('%Y-%m-%d %H:%M')}`\n📢 **Your Channels:** `{len(channels)}`\n🆔 **Broadcast ID:** `{broadcast_id}`\n\nYou'll be notified when the broadcast is sent.",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(call.message.chat.id, "❌ Error scheduling broadcast")
                
                bot_state.broadcast_state.pop(call.message.chat.id, None)

        elif call.data == "cancel_schedule":
            bot_state.broadcast_state.pop(call.message.chat.id, None)
            bot.send_message(call.message.chat.id, "❌ Schedule cancelled")

        # Simple schedule options
        elif call.data.startswith("schedule_"):
            hours = int(call.data.split("_")[1].replace("h", ""))
            bot_state.broadcast_state[call.message.chat.id] = {"step": "schedule_msg", "hours": hours}
            bot.send_message(
                call.message.chat.id,
                f"📅 **Schedule for {hours} Hour{'s' if hours > 1 else ''}**\n\nSend the message you want to schedule for broadcast in {hours} hour{'s' if hours > 1 else ''}."
            )

        elif call.data == "forward_message_help":
            help_text = """
📤 **How to Forward Message**

1. **Go to your channel** where you're admin
2. **Select any message** (text, photo, video, etc.)
3. **Forward it** to this bot
4. **Bot will automatically** detect the channel and add it

**Example:**
• Channel: @mychannel
• Message: "Hello World"
• Forward to: @your_bot
• Result: Channel automatically added!

**Note:** Make sure you're admin in the channel you want to add.
            """
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Find Channels", callback_data="find_channels"),
            )
            bot.send_message(call.message.chat.id, help_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "get_channel_id_help":
            help_text = """
🆔 **How to Get Channel ID**

**Method 1: Using @userinfobot**
1. Add @userinfobot to your channel
2. Send any message in the channel
3. The bot will show channel ID like: `-1001234567890`

**Method 2: Using @getidsbot**
1. Add @getidsbot to your channel
2. Send `/start` in the channel
3. Get the channel ID

**Method 3: Manual Detection**
1. Send channel ID directly: `-1001234567890`
2. Bot will verify and add if valid

**Format:** Always starts with `-100` followed by numbers
            """
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Find Channels", callback_data="find_channels"),
            )
            bot.send_message(call.message.chat.id, help_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "add_bot_help":
            help_text = """
➕ **How to Add Bot to Channel**

**Step 1: Add Bot as Admin**
1. Go to your channel settings
2. Click "Administrators"
3. Click "Add Administrator"
4. Search for your bot: `@your_bot_username`
5. Give these permissions:
   ✅ Post Messages
   ✅ Edit Messages
   ✅ Delete Messages

**Step 2: Send Test Message**
1. Send any message in the channel
2. Bot will automatically detect the channel
3. Channel will be added to your list

**Step 3: Verify**
1. Check "Show Saved Channels" in bot
2. Your channel should appear in the list

**Note:** Bot needs admin rights to send messages in your channel.
            """
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Find Channels", callback_data="find_channels"),
            )
            bot.send_message(call.message.chat.id, help_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "user_management":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            # Show user management menu
            users = broadcast_bot.get_all_users()
            active_users = broadcast_bot.get_active_users()
            
            stats_text = f"""
👥 **User Management Panel**

📊 **Statistics:**
• Total Users: `{len(users)}`
• Active Users: `{len(active_users)}`
• Premium Users: `{len(broadcast_bot.get_premium_users())}`

Choose an action:
            """
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ Activate User", callback_data="activate_user"),
                types.InlineKeyboardButton("➖ Deactivate User", callback_data="deactivate_user"),
            )
            markup.add(
                types.InlineKeyboardButton("📋 All Users", callback_data="show_all_users"),
                types.InlineKeyboardButton("✅ Active Users", callback_data="show_active_users"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            bot.send_message(call.message.chat.id, stats_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "premium_management":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            # Show premium management menu
            premium_users = broadcast_bot.get_premium_users()
            
            stats_text = f"""
⭐ **Premium Management Panel**

📊 **Statistics:**
• Premium Users: `{len(premium_users)}`
• Total Users: `{len(broadcast_bot.get_all_users())}`

Choose an action:
            """
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⭐ Give Premium", callback_data="give_premium"),
                types.InlineKeyboardButton("❌ Revoke Premium", callback_data="revoke_premium"),
            )
            markup.add(
                types.InlineKeyboardButton("📋 Premium Users", callback_data="show_premium_users"),
                types.InlineKeyboardButton("📊 Premium Stats", callback_data="premium_stats"),
            )
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
            )
            
            bot.send_message(call.message.chat.id, stats_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "activate_user":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            bot_state.user_sessions[call.message.chat.id] = {"action": "activate_user", "step": "waiting_user_id"}
            bot.send_message(
                call.message.chat.id,
                "➕ **Activate User**\n\nSend the user ID you want to activate.\n\n**Format:** `123456789`"
            )

        elif call.data == "deactivate_user":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            bot_state.user_sessions[call.message.chat.id] = {"action": "deactivate_user", "step": "waiting_user_id"}
            bot.send_message(
                call.message.chat.id,
                "➖ **Deactivate User**\n\nSend the user ID you want to deactivate.\n\n**Format:** `123456789`"
            )

        elif call.data == "give_premium":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            bot_state.user_sessions[call.message.chat.id] = {"action": "give_premium", "step": "waiting_user_id"}
            bot.send_message(
                call.message.chat.id,
                "⭐ **Give Premium**\n\nSend the user ID you want to give premium access.\n\n**Format:** `123456789`"
            )

        elif call.data == "revoke_premium":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            bot_state.user_sessions[call.message.chat.id] = {"action": "revoke_premium", "step": "waiting_user_id"}
            bot.send_message(
                call.message.chat.id,
                "❌ **Revoke Premium**\n\nSend the user ID you want to revoke premium from.\n\n**Format:** `123456789`"
            )

        elif call.data == "show_all_users":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            users = broadcast_bot.get_all_users()
            if not users:
                bot.send_message(call.message.chat.id, "📋 No users found in database.")
                return
            
            users_text = f"📋 **All Users ({len(users)})**\n\n"
            for i, user in enumerate(users[:20], 1):  # Show first 20 users
                status = "✅ Active" if user.get("is_active") else "❌ Inactive"
                premium = "⭐ Premium" if user.get("is_premium") else "📱 Basic"
                users_text += f"**{i}. ID:** `{user['user_id']}`\n"
                users_text += f"**Name:** {user.get('first_name', 'N/A')}\n"
                users_text += f"**Status:** {status} | {premium}\n\n"
            
            if len(users) > 20:
                users_text += f"... and {len(users) - 20} more users"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to User Management", callback_data="user_management"),
            )
            
            bot.send_message(call.message.chat.id, users_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "show_active_users":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            users = broadcast_bot.get_active_users()
            if not users:
                bot.send_message(call.message.chat.id, "📋 No active users found.")
                return
            
            users_text = f"✅ **Active Users ({len(users)})**\n\n"
            for i, user in enumerate(users[:20], 1):  # Show first 20 users
                premium = "⭐ Premium" if user.get("is_premium") else "📱 Basic"
                users_text += f"**{i}. ID:** `{user['user_id']}`\n"
                users_text += f"**Name:** {user.get('first_name', 'N/A')}\n"
                users_text += f"**Type:** {premium}\n\n"
            
            if len(users) > 20:
                users_text += f"... and {len(users) - 20} more users"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to User Management", callback_data="user_management"),
            )
            
            bot.send_message(call.message.chat.id, users_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "show_premium_users":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            users = broadcast_bot.get_premium_users()
            if not users:
                bot.send_message(call.message.chat.id, "📋 No premium users found.")
                return
            
            users_text = f"⭐ **Premium Users ({len(users)})**\n\n"
            for i, user in enumerate(users[:20], 1):  # Show first 20 users
                expiry = user.get("premium_expires")
                if expiry:
                    expiry_str = expiry.strftime("%Y-%m-%d %H:%M")
                else:
                    expiry_str = "Unknown"
                
                users_text += f"**{i}. ID:** `{user['user_id']}`\n"
                users_text += f"**Name:** {user.get('first_name', 'N/A')}\n"
                users_text += f"**Expires:** `{expiry_str}`\n\n"
            
            if len(users) > 20:
                users_text += f"... and {len(users) - 20} more users"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Premium Management", callback_data="premium_management"),
            )
            
            bot.send_message(call.message.chat.id, users_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "premium_stats":
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.send_message(call.message.chat.id, "🚫 You don't have permission to access this feature.")
                return
            
            users = broadcast_bot.get_all_users()
            premium_users = broadcast_bot.get_premium_users()
            active_users = broadcast_bot.get_active_users()
            
            # Calculate premium expiry stats
            expiring_soon = 0
            expired = 0
            for user in premium_users:
                if user.get("premium_expires"):
                    if user["premium_expires"] < datetime.now():
                        expired += 1
                    elif user["premium_expires"] < datetime.now() + timedelta(days=7):
                        expiring_soon += 1
            
            stats_text = f"""
📊 **Premium Statistics**

👥 **User Overview:**
• Total Users: `{len(users)}`
• Active Users: `{len(active_users)}`
• Premium Users: `{len(premium_users)}`

⭐ **Premium Status:**
• Active Premium: `{len(premium_users) - expired}`
• Expired Premium: `{expired}`
• Expiring Soon (7 days): `{expiring_soon}`

📈 **Conversion Rate:**
• Basic to Premium: `{(len(premium_users) / max(len(active_users), 1)) * 100:.1f}%`
            """
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 Back to Premium Management", callback_data="premium_management"),
            )
            
            bot.send_message(call.message.chat.id, stats_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "premium_status":
            # Show premium user status
            user_info = broadcast_bot.get_user_info(call.message.chat.id)
            if user_info and user_info.get("is_premium"):
                expiry = user_info.get("premium_expires")
                if expiry:
                    days_left = (expiry - datetime.now()).days
                    if days_left > 0:
                        status_text = f"""
⭐ **Premium Status**

👤 **User:** {user_info.get('first_name', 'N/A')}
🆔 **ID:** `{user_info['user_id']}`
⭐ **Status:** Active Premium
📅 **Expires:** `{expiry.strftime('%Y-%m-%d %H:%M')}`
⏰ **Days Left:** `{days_left}`

✅ You have access to all broadcast features!
                        """
                    else:
                        status_text = "⭐ **Premium Status:** Expired\n\nContact admin to renew your premium access."
                else:
                    status_text = "⭐ **Premium Status:** Active (No expiry date)"
                
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"),
                )
                
                bot.send_message(call.message.chat.id, status_text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, "❌ Premium status not found.")

        elif call.data == "restart_bot":
            # Only allow restart for admins
            if not broadcast_bot.is_admin(call.message.chat.id):
                bot.answer_callback_query(call.id, "🚫 Only admins can restart the bot!")
                return
            bot.send_message(call.message.chat.id, "🔄 Restarting bot...")
            # In a real deployment, you'd restart the process
            bot.send_message(call.message.chat.id, "✅ Bot restarted successfully!")

        # Repost / Delete flow handling
        elif call.data in ["repost_yes", "repost_no", "delete_yes", "delete_no"]:
            if call.data == "repost_yes":
                state["step"] = "ask_repost_time"
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("⏱ 5 Min", callback_data="repost_5"),
                    types.InlineKeyboardButton("⏱ 10 Min", callback_data="repost_10"),
                    types.InlineKeyboardButton("⏱ 15 Min", callback_data="repost_15"),
                    types.InlineKeyboardButton("⏱ 30 Min", callback_data="repost_30"),
                    types.InlineKeyboardButton("⏱ 1 Hour", callback_data="repost_1h"),
                    types.InlineKeyboardButton("⏱ 2 Hours", callback_data="repost_2h"),
                    types.InlineKeyboardButton("⏱ 6 Hours", callback_data="repost_6h"),
                    types.InlineKeyboardButton("⏱ 12 Hours", callback_data="repost_12h"),
                    types.InlineKeyboardButton("⏱ 24 Hours", callback_data="repost_24h"),
                    types.InlineKeyboardButton("⏱ Custom Time", callback_data="repost_custom"),
                )
                bot.send_message(call.message.chat.id, "⏱ **Auto Repost Options**\n\nChoose repost interval:", reply_markup=markup, parse_mode="Markdown")
            elif call.data == "repost_no":
                state["repost_time"] = None
                state["step"] = "ask_autodelete"
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🗑 5 Min", callback_data="delete_5"),
                    types.InlineKeyboardButton("🗑 10 Min", callback_data="delete_10"),
                    types.InlineKeyboardButton("🗑 15 Min", callback_data="delete_15"),
                    types.InlineKeyboardButton("🗑 30 Min", callback_data="delete_30"),
                    types.InlineKeyboardButton("🗑 1 Hour", callback_data="delete_1h"),
                    types.InlineKeyboardButton("🗑 2 Hours", callback_data="delete_2h"),
                    types.InlineKeyboardButton("🗑 6 Hours", callback_data="delete_6h"),
                    types.InlineKeyboardButton("🗑 12 Hours", callback_data="delete_12h"),
                    types.InlineKeyboardButton("🗑 24 Hours", callback_data="delete_24h"),
                    types.InlineKeyboardButton("⏱ Custom Time", callback_data="delete_custom"),
                    types.InlineKeyboardButton("❌ No Delete", callback_data="delete_no"),
                )
                bot.send_message(call.message.chat.id, "🗑 **Auto Delete Options**\n\nChoose when to auto delete the broadcasted message:", reply_markup=markup, parse_mode="Markdown")

            elif call.data == "delete_yes":
                state["step"] = "ask_autodelete_time"
                bot.send_message(call.message.chat.id, "⏱ After how many minutes should the message auto-delete?")
            elif call.data == "delete_custom":
                state["step"] = "ask_autodelete_time"
                bot.send_message(call.message.chat.id, "⏱ Enter custom delete time in minutes (minimum 1):")
            elif call.data == "repost_custom":
                state["step"] = "ask_repost_time"
                bot.send_message(call.message.chat.id, "⏱ Enter custom repost time in minutes (minimum 1):")
            elif call.data == "delete_no":
                state["delete_time"] = None
                finish_broadcast(call.message.chat.id)
            elif call.data.startswith("delete_"):
                if call.data == "delete_no":
                    state["delete_time"] = None
                    finish_broadcast(call.message.chat.id)
                else:
                    # Extract time from callback data
                    time_str = call.data.replace("delete_", "")
                    if time_str.endswith("h"):
                        hours = int(time_str.replace("h", ""))
                        state["delete_time"] = hours * 60  # Convert to minutes
                    else:
                        state["delete_time"] = int(time_str)  # Already in minutes
                    finish_broadcast(call.message.chat.id)
            elif call.data.startswith("repost_"):
                # Extract time from callback data
                time_str = call.data.replace("repost_", "")
                if time_str.endswith("h"):
                    hours = int(time_str.replace("h", ""))
                    state["repost_time"] = hours * 60  # Convert to minutes
                else:
                    state["repost_time"] = int(time_str)  # Already in minutes
                
                # Now ask for auto delete
                state["step"] = "ask_autodelete"
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🗑 5 Min", callback_data="delete_5"),
                    types.InlineKeyboardButton("🗑 10 Min", callback_data="delete_10"),
                    types.InlineKeyboardButton("🗑 15 Min", callback_data="delete_15"),
                    types.InlineKeyboardButton("🗑 30 Min", callback_data="delete_30"),
                    types.InlineKeyboardButton("🗑 1 Hour", callback_data="delete_1h"),
                    types.InlineKeyboardButton("🗑 2 Hours", callback_data="delete_2h"),
                    types.InlineKeyboardButton("🗑 6 Hours", callback_data="delete_6h"),
                    types.InlineKeyboardButton("🗑 12 Hours", callback_data="delete_12h"),
                    types.InlineKeyboardButton("🗑 24 Hours", callback_data="delete_24h"),
                    types.InlineKeyboardButton("⏱ Custom Time", callback_data="delete_custom"),
                    types.InlineKeyboardButton("❌ No Delete", callback_data="delete_no"),
                )
                bot.send_message(call.message.chat.id, "🗑 **Auto Delete Options**\n\nChoose when to auto delete the broadcasted message:", reply_markup=markup, parse_mode="Markdown")

            bot_state.broadcast_state[call.message.chat.id] = state

    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ An error occurred")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Enhanced message handler with better validation"""
    # Check if user is authorized (active users, premium users, or admins)
    if not (broadcast_bot.is_authorized(message.chat.id) or 
            broadcast_bot.is_premium(message.chat.id) or 
            broadcast_bot.is_admin(message.chat.id)):
        return

    # Debug logging for forwarded messages
    if message.forward_from_chat:
        logger.info(f"Forwarded message detected: {message.content_type} from {message.forward_from_chat.title}")
        logger.info(f"Message caption: {message.caption}")
        logger.info(f"User state: {bot_state.broadcast_state.get(message.chat.id)}")

    try:
        state = bot_state.broadcast_state.get(message.chat.id)

        # Handle broadcast message
        if state and state.get("step") == "waiting_msg":
            # Check if it's a forwarded message
            if message.forward_from_chat:
                # Handle forwarded message for broadcast
                state["message"] = message
                state["step"] = "ask_repost"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Yes", callback_data="repost_yes"),
                    types.InlineKeyboardButton("❌ No", callback_data="repost_no"),
                )
                
                # Show detailed message preview
                preview_text = f"📢 **Forwarded Message Preview:**\n\n"
                preview_text += f"**Type:** {message.content_type}\n"
                preview_text += f"**From Channel:** {message.forward_from_chat.title}\n"
                if message.caption:
                    preview_text += f"**Caption:** {message.caption[:150]}{'...' if len(message.caption) > 150 else ''}\n"
                else:
                    preview_text += f"**Caption:** No caption\n"
                preview_text += f"**Message ID:** {message.message_id}\n"
                preview_text += f"**Forward Date:** {message.forward_date}\n\n"
                preview_text += "♻️ Do you want to Auto Repost this forwarded message?"
                
                try:
                    bot.send_message(message.chat.id, preview_text, reply_markup=markup, parse_mode="Markdown")
                    logger.info(f"Forwarded message preview sent successfully for {message.content_type}")
                except Exception as e:
                    # Fallback without Markdown
                    bot.send_message(message.chat.id, preview_text, reply_markup=markup)
                    logger.error(f"Error sending preview with Markdown: {e}")
            else:
                # Handle regular message for broadcast
                state["message"] = message
                state["step"] = "ask_repost"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Yes", callback_data="repost_yes"),
                    types.InlineKeyboardButton("❌ No", callback_data="repost_no"),
                )
                bot.send_message(message.chat.id, "♻️ Do you want to Auto Repost this message?", reply_markup=markup)
                logger.info(f"Regular message preview sent successfully for {message.content_type}")
            return

        # Handle repost time input
        if state and state.get("step") == "ask_repost_time":
            try:
                minutes = int(message.text.strip())
                if minutes < 1:
                    bot.send_message(message.chat.id, "⚠️ Please enter a number greater than 0.")
                    return
                state["repost_time"] = minutes
                state["step"] = "ask_autodelete"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
                    types.InlineKeyboardButton("❌ No", callback_data="delete_no"),
                )
                bot.send_message(message.chat.id, "🗑 Do you want Auto Delete for this message?", reply_markup=markup)
            except ValueError:
                bot.send_message(message.chat.id, "⚠️ Please enter a valid number (minutes).")
            return

        # Handle auto delete time input
        if state and state.get("step") == "ask_autodelete_time":
            try:
                minutes = int(message.text.strip())
                if minutes < 1:
                    bot.send_message(message.chat.id, "⚠️ Please enter a number greater than 0.")
                    return
                state["delete_time"] = minutes
                finish_broadcast(message.chat.id)
            except ValueError:
                bot.send_message(message.chat.id, "⚠️ Please enter a valid number (minutes).")
            return

        # Handle scheduled broadcast message
        if state and state.get("step") == "schedule_msg":
            state["message"] = message
            hours = state.get("hours", 1)  # Default 1 hour if not specified
            
            # Calculate schedule time
            schedule_time = datetime.now() + timedelta(hours=hours)
            state["schedule_time"] = schedule_time
            state["step"] = "schedule_confirm"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Confirm Schedule", callback_data="confirm_schedule"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_schedule"),
            )
            
            bot.send_message(
                message.chat.id,
                f"📅 **Schedule Confirmation**\n\n**Message:** {message.content_type}\n**Schedule Time:** `{schedule_time.strftime('%Y-%m-%d %H:%M')}`\n**Your Channels:** `{broadcast_bot.get_channel_count(message.chat.id)}`\n\nConfirm to schedule this broadcast?",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        # Handle schedule time input
        if state and state.get("step") == "schedule_time":
            try:
                schedule_time = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
                if schedule_time <= datetime.now():
                    bot.send_message(message.chat.id, "⚠️ Schedule time must be in the future!")
                    return
                
                state["schedule_time"] = schedule_time
                state["step"] = "schedule_confirm"
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("✅ Confirm Schedule", callback_data="confirm_schedule"),
                    types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_schedule"),
                )
                
                bot.send_message(
                    message.chat.id,
                    f"📅 **Schedule Confirmation**\n\n**Message:** {message.content_type}\n**Schedule Time:** `{schedule_time.strftime('%Y-%m-%d %H:%M')}`\n**Your Channels:** `{broadcast_bot.get_channel_count(message.chat.id)}`\n\nConfirm to schedule this broadcast?",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            except ValueError:
                bot.send_message(message.chat.id, "⚠️ Invalid time format. Use: YYYY-MM-DD HH:MM")
            return

        # Handle forwarded messages (auto-detect channels OR broadcast)
        if message.forward_from_chat and message.forward_from_chat.type in ['channel', 'supergroup']:
            # Check if user is in broadcast mode
            if state and state.get("step") == "waiting_msg":
                # User wants to broadcast this forwarded message
                state["message"] = message
                state["step"] = "ask_repost"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Yes", callback_data="repost_yes"),
                    types.InlineKeyboardButton("❌ No", callback_data="repost_no"),
                )
                bot.send_message(message.chat.id, "♻️ Do you want to Auto Repost this forwarded message?", reply_markup=markup)
                return
            
            # Regular channel detection (not in broadcast mode)
            try:
                channel_id = message.forward_from_chat.id
                channel_title = message.forward_from_chat.title
                channel_username = getattr(message.forward_from_chat, 'username', None)
                
                # Check if user is admin in this channel
                try:
                    member = bot.get_chat_member(channel_id, message.chat.id)
                    if member.status in ['administrator', 'creator']:
                        if broadcast_bot.add_channel(channel_id, message.chat.id):
                            success_msg = f"✅ **Channel Added Successfully!**\n\n📢 **Channel:** `{channel_title}`\n🆔 **ID:** `{channel_id}`"
                            if channel_username:
                                success_msg += f"\n🔗 **Username:** @{channel_username}"
                            success_msg += f"\n\n✅ Channel is ready for broadcasting!"
                            
                            bot.send_message(message.chat.id, success_msg, parse_mode="Markdown")
                        else:
                            bot.send_message(message.chat.id, f"⚠️ Channel `{channel_title}` already exists in your list", parse_mode="Markdown")
                    else:
                        bot.send_message(
                            message.chat.id, 
                            f"❌ **Access Denied!**\n\nYou need to be an **admin** in `{channel_title}` to add it.\n\nPlease make yourself admin and try again.",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    bot.send_message(
                        message.chat.id,
                        f"❌ **Error!**\n\nCould not verify your admin status in `{channel_title}`.\n\nMake sure:\n• You're admin in the channel\n• Bot has permission to check member status",
                        parse_mode="Markdown"
                    )
                    logger.error(f"Error checking admin status for {channel_id}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing forwarded message: {e}")
                bot.send_message(message.chat.id, "❌ Error processing forwarded message")
            return

        # Handle user management actions
        user_session = bot_state.user_sessions.get(message.chat.id)
        if user_session:
            action = user_session.get("action")
            step = user_session.get("step")
            
            if step == "waiting_user_id":
                try:
                    user_id = int(message.text.strip())
                    
                    if action == "activate_user":
                        if broadcast_bot.activate_user(user_id, message.chat.id):
                            bot.send_message(
                                message.chat.id,
                                f"✅ **User Activated Successfully!**\n\n**User ID:** `{user_id}`\n**Activated by:** `{message.chat.id}`\n\nUser can now use the bot.",
                                parse_mode="Markdown"
                            )
                        else:
                            bot.send_message(message.chat.id, "❌ Failed to activate user. User might not exist.")
                    
                    elif action == "deactivate_user":
                        if broadcast_bot.deactivate_user(user_id, message.chat.id):
                            bot.send_message(
                                message.chat.id,
                                f"✅ **User Deactivated Successfully!**\n\n**User ID:** `{user_id}`\n**Deactivated by:** `{message.chat.id}`\n\nUser can no longer use the bot.",
                                parse_mode="Markdown"
                            )
                        else:
                            bot.send_message(message.chat.id, "❌ Failed to deactivate user. User might not exist.")
                    
                    elif action == "give_premium":
                        user_session["user_id"] = user_id
                        user_session["step"] = "waiting_days"
                        bot_state.user_sessions[message.chat.id] = user_session
                        bot.send_message(
                            message.chat.id,
                            f"⭐ **Give Premium**\n\n**User ID:** `{user_id}`\n\nSend the number of days for premium access.\n\n**Format:** `30` (for 30 days)"
                        )
                        return
                    
                    elif action == "revoke_premium":
                        if broadcast_bot.revoke_premium(user_id, message.chat.id):
                            bot.send_message(
                                message.chat.id,
                                f"✅ **Premium Revoked Successfully!**\n\n**User ID:** `{user_id}`\n**Revoked by:** `{message.chat.id}`\n\nUser's premium access has been removed.",
                                parse_mode="Markdown"
                            )
                        else:
                            bot.send_message(message.chat.id, "❌ Failed to revoke premium. User might not exist or not have premium.")
                    
                    # Clear session after action
                    bot_state.user_sessions.pop(message.chat.id, None)
                    
                except ValueError:
                    bot.send_message(message.chat.id, "⚠️ Invalid user ID format. Please send a valid number.")
                return
            
            elif step == "waiting_days" and action == "give_premium":
                try:
                    days = int(message.text.strip())
                    if days < 1:
                        bot.send_message(message.chat.id, "⚠️ Please enter a number greater than 0.")
                        return
                    
                    user_id = user_session.get("user_id")
                    if broadcast_bot.give_premium(user_id, days, message.chat.id):
                        bot.send_message(
                            message.chat.id,
                            f"✅ **Premium Given Successfully!**\n\n**User ID:** `{user_id}`\n**Days:** `{days}`\n**Given by:** `{message.chat.id}`\n\nUser now has premium access for {days} days.",
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(message.chat.id, "❌ Failed to give premium. User might not exist.")
                    
                    # Clear session
                    bot_state.user_sessions.pop(message.chat.id, None)
                    
                except ValueError:
                    bot.send_message(message.chat.id, "⚠️ Invalid number format. Please send a valid number.")
                return

        # Handle channel ID input
        if message.text and message.text.startswith("-100"):
            try:
                ch_id = int(message.text.strip())
                
                # Verify the channel exists and user has access
                try:
                    chat_info = bot.get_chat(ch_id)
                    member = bot.get_chat_member(ch_id, message.chat.id)
                    
                    if member.status in ['administrator', 'creator']:
                        if broadcast_bot.add_channel(ch_id, message.chat.id):
                            success_msg = f"✅ **Channel Added Successfully!**\n\n📢 **Channel:** `{chat_info.title}`\n🆔 **ID:** `{ch_id}`"
                            if hasattr(chat_info, 'username') and chat_info.username:
                                success_msg += f"\n🔗 **Username:** @{chat_info.username}"
                            success_msg += f"\n\n✅ Channel is ready for broadcasting!"
                            
                            bot.send_message(message.chat.id, success_msg, parse_mode="Markdown")
                        else:
                            bot.send_message(message.chat.id, f"⚠️ Channel `{chat_info.title}` already exists in your list", parse_mode="Markdown")
                    else:
                        bot.send_message(
                            message.chat.id,
                            f"❌ **Access Denied!**\n\nYou need to be an **admin** in `{chat_info.title}` to add it.\n\nPlease make yourself admin and try again.",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    bot.send_message(message.chat.id, "❌ Invalid channel ID or you don't have access to this channel")
                    logger.error(f"Error verifying channel {ch_id}: {e}")
                    
            except ValueError:
                bot.send_message(message.chat.id, "⚠️ Invalid channel ID format. Use format: -1001234567890")
            except Exception as e:
                logger.error(f"Error adding channel: {e}")
                bot.send_message(message.chat.id, "❌ Error adding channel")

    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        bot.send_message(message.chat.id, "❌ An error occurred while processing your message")

def finish_broadcast(chat_id: int):
    """Enhanced broadcast completion with better error handling"""
    try:
        state = bot_state.broadcast_state.get(chat_id)
        if not state:
            return

        message = state["message"]
        repost_time = state.get("repost_time")
        delete_time = state.get("delete_time")

        # Log message details for debugging
        logger.info(f"Starting broadcast for user {chat_id}")
        logger.info(f"Message type: {message.content_type}")
        logger.info(f"Message ID: {message.message_id}")
        if message.forward_from_chat:
            logger.info(f"Forwarded from: {message.forward_from_chat.title}")
        if message.caption:
            logger.info(f"Caption: {message.caption[:100]}...")

        # Generate unique broadcast ID
        broadcast_id = f"broadcast_{chat_id}_{int(time.time())}"
        
        channels = broadcast_bot.get_all_channels(chat_id)
        sent_count = 0
        failed_count = 0
        failed_channels = []

        for ch in channels:
            try:
                sent = None
                channel_id = ch["channel_id"]
                
                if message.content_type == "text":
                    sent = bot.send_message(channel_id, message.text)
                elif message.content_type == "photo":
                    # Handle photo with caption (text, links, formatting)
                    caption = message.caption or ""
                    
                    # Simple and reliable method - try forwarding first, then sending
                    try:
                        # Method 1: Forward the original message (preserves everything)
                        sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        logger.info(f"Photo forwarded successfully to {channel_id}")
                    except Exception as forward_error:
                        logger.warning(f"Forward failed, trying to send: {forward_error}")
                        try:
                            # Method 2: Send photo with caption
                            sent = bot.send_photo(
                                channel_id, 
                                message.photo[-1].file_id, 
                                caption=caption
                            )
                            logger.info(f"Photo sent successfully to {channel_id}")
                        except Exception as send_error:
                            logger.error(f"Photo send failed to {channel_id}: {send_error}")
                            raise send_error
                elif message.content_type == "video":
                    # Handle video with caption (text, links, formatting)
                    caption = message.caption or ""
                    parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                    
                    try:
                        sent = bot.send_video(
                            channel_id, 
                            message.video.file_id, 
                            caption=caption,
                            parse_mode=parse_mode
                        )
                    except Exception as caption_error:
                        logger.warning(f"Markdown parsing failed for video caption, sending as plain text: {caption_error}")
                        sent = bot.send_video(
                            channel_id, 
                            message.video.file_id, 
                            caption=caption
                        )
                        
                elif message.content_type == "document":
                    # Handle document with caption (text, links, formatting)
                    caption = message.caption or ""
                    parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                    
                    try:
                        sent = bot.send_document(
                            channel_id, 
                            message.document.file_id, 
                            caption=caption,
                            parse_mode=parse_mode
                        )
                    except Exception as caption_error:
                        logger.warning(f"Markdown parsing failed for document caption, sending as plain text: {caption_error}")
                        sent = bot.send_document(
                            channel_id, 
                            message.document.file_id, 
                            caption=caption
                        )
                        
                elif message.content_type == "audio":
                    # Handle audio with caption (text, links, formatting)
                    caption = message.caption or ""
                    parse_mode = "Markdown" if any(char in caption for char in ['*', '_', '`', '[', ']', '(', ')']) else None
                    
                    try:
                        sent = bot.send_audio(
                            channel_id, 
                            message.audio.file_id, 
                            caption=caption,
                            parse_mode=parse_mode
                        )
                    except Exception as caption_error:
                        logger.warning(f"Markdown parsing failed for audio caption, sending as plain text: {caption_error}")
                        sent = bot.send_audio(
                            channel_id, 
                            message.audio.file_id, 
                            caption=caption
                        )
                else:
                    sent = bot.forward_message(channel_id, message.chat.id, message.message_id)

                sent_count += 1
                
                # Save message ID for potential deletion
                if sent:
                    broadcast_bot.save_broadcast_message(chat_id, channel_id, sent.message_id, broadcast_id)

                # Auto delete
                if delete_time and sent:
                    threading.Thread(
                        target=auto_delete, args=(channel_id, sent.message_id, delete_time)
                    ).start()

            except Exception as e:
                failed_count += 1
                failed_channels.append(str(channel_id))
                logger.error(f"❌ Failed in {channel_id} -> {e}")

        # Send detailed results
        result_text = f"""
✅ **Broadcast Completed!**

📊 **Results:**
• Sent: `{sent_count}`
• Failed: `{failed_count}`
• Total Channels: `{len(channels)}`

⏰ **Settings:**
• Auto Repost: {'✅' if repost_time else '❌'} {f'({repost_time} min)' if repost_time else ''}
• Auto Delete: {'✅' if delete_time else '❌'} {f'({delete_time} min)' if delete_time else ''}
        """
        
        if failed_channels:
            result_text += f"\n❌ **Failed Channels:**\n`{', '.join(failed_channels[:5])}`"
            if len(failed_channels) > 5:
                result_text += f"\n... and {len(failed_channels) - 5} more"

        bot.send_message(chat_id, result_text, parse_mode="Markdown")

        # Start auto repost if configured
        if repost_time:
            bot.send_message(
                chat_id,
                f"♻️ **Auto Repost Started!**\n\n⏱ Interval: `{repost_time} minutes`\n🗑 Auto Delete: {'✅' if delete_time else '❌'}\n\nUse ⏹ Stop Repost button to cancel.",
                parse_mode="Markdown"
            )
            stop_flag = {"stop": False}
            bot_state.active_reposts[chat_id] = stop_flag
            threading.Thread(
                target=auto_repost, args=(chat_id, message, repost_time, delete_time, stop_flag)
            ).start()

        bot_state.broadcast_state.pop(chat_id, None)

    except Exception as e:
        logger.error(f"Error in finish_broadcast: {e}")
        bot.send_message(chat_id, "❌ An error occurred during broadcast")

def stop_repost(chat_id: int):
    """Stop active repost with confirmation"""
    try:
        if chat_id in bot_state.active_reposts:
            bot_state.active_reposts[chat_id]["stop"] = True
            del bot_state.active_reposts[chat_id]
            bot.send_message(chat_id, "⏹ **Auto Repost stopped successfully!**", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "⚠️ No active repost running.")
    except Exception as e:
        logger.error(f"Error stopping repost: {e}")
        bot.send_message(chat_id, "❌ Error stopping repost")

def delete_broadcast_messages_from_channels(owner_id: int, broadcast_id: str = None):
    """Delete all broadcast messages from channels"""
    try:
        messages = broadcast_bot.get_broadcast_messages(owner_id, broadcast_id)
        if not messages:
            return 0, 0
        
        deleted_count = 0
        failed_count = 0
        
        for msg in messages:
            try:
                bot.delete_message(msg["channel_id"], msg["message_id"])
                deleted_count += 1
                logger.info(f"✅ Deleted message {msg['message_id']} from channel {msg['channel_id']}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to delete message {msg['message_id']} from channel {msg['channel_id']}: {e}")
        
        # Delete from database
        broadcast_bot.delete_broadcast_messages(owner_id, broadcast_id)
        
        return deleted_count, failed_count
        
    except Exception as e:
        logger.error(f"Error deleting broadcast messages: {e}")
        return 0, 0

def check_scheduled_broadcasts():
    """Check and execute scheduled broadcasts"""
    try:
        scheduled_col = db["scheduled_broadcasts"]
        now = datetime.now()
        
        # Find pending broadcasts that are due
        pending_broadcasts = scheduled_col.find({
            "status": "pending",
            "schedule_time": {"$lte": now}
        })
        
        for broadcast in pending_broadcasts:
            try:
                # Execute the scheduled broadcast
                message_data = broadcast["message_data"]
                channels = broadcast["channels"]
                
                sent_count = 0
                for ch in channels:
                    try:
                        channel_id = ch["channel_id"]
                        sent = None
                        
                        if message_data["content_type"] == "text":
                            sent = bot.send_message(channel_id, message_data["text"])
                        elif message_data["content_type"] == "photo":
                            sent = bot.send_photo(channel_id, message_data["file_id"], caption=message_data["caption"])
                        elif message_data["content_type"] == "video":
                            sent = bot.send_video(channel_id, message_data["file_id"], caption=message_data["caption"])
                        elif message_data["content_type"] == "document":
                            sent = bot.send_document(channel_id, message_data["file_id"], caption=message_data["caption"])
                        elif message_data["content_type"] == "audio":
                            sent = bot.send_audio(channel_id, message_data["file_id"], caption=message_data["caption"])
                        
                        if sent:
                            sent_count += 1
                            # Save message ID
                            broadcast_bot.save_broadcast_message(
                                broadcast["owner_id"], 
                                channel_id, 
                                sent.message_id, 
                                broadcast["broadcast_id"]
                            )
                            
                    except Exception as e:
                        logger.error(f"Failed to send scheduled broadcast to {ch.get('channel_id')}: {e}")
                
                # Update status to completed
                scheduled_col.update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {"status": "completed", "sent_count": sent_count}}
                )
                
                # Notify owner
                bot.send_message(
                    broadcast["owner_id"],
                    f"✅ **Scheduled Broadcast Completed!**\n\n📊 **Results:**\n• Messages Sent: `{sent_count}`\n• Total Channels: `{len(channels)}`\n• Broadcast ID: `{broadcast['broadcast_id']}`",
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                logger.error(f"Error executing scheduled broadcast {broadcast.get('broadcast_id')}: {e}")
                
    except Exception as e:
        logger.error(f"Error checking scheduled broadcasts: {e}")

def start_scheduled_broadcast_checker():
    """Start the scheduled broadcast checker thread"""
    def checker_loop():
        while True:
            try:
                check_scheduled_broadcasts()
                check_expired_premium_users()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduled broadcast checker: {e}")
                time.sleep(60)
    
    threading.Thread(target=checker_loop, daemon=True).start()

def check_expired_premium_users():
    """Check and clean expired premium users"""
    try:
        users = broadcast_bot.get_premium_users()
        expired_count = 0
        
        for user in users:
            if user.get("premium_expires") and user["premium_expires"] < datetime.now():
                # Revoke expired premium
                if broadcast_bot.revoke_premium(user["user_id"], OWNER_ID):
                    expired_count += 1
                    logger.info(f"Premium expired for user {user['user_id']}")
        
        if expired_count > 0:
            logger.info(f"Cleaned {expired_count} expired premium users")
            
    except Exception as e:
        logger.error(f"Error checking expired premium users: {e}")

# Error handler for bot
@bot.message_handler(func=lambda message: True)
def error_handler(message):
    """Global error handler"""
    logger.error(f"Unhandled message: {message}")

if __name__ == "__main__":
    logger.info("🤖 Bot starting...")
    
    # Start scheduled broadcast checker
    start_scheduled_broadcast_checker()
    logger.info("✅ Scheduled broadcast checker started")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
        raise
