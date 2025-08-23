#!/usr/bin/env python3
"""
Advanced Telegram Broadcast Bot
Features: Auto Repost, Auto Delete, Scheduled Broadcasts, Analytics, Multi-Channel Management
Author: ANKIT
"""

import os
import time
import logging
import threading
import schedule
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

import telebot
from telebot import types
from pymongo import MongoClient
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configure advanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import config
try:
    from config import *
except ImportError:
    logger.error("Config file not found!")
    raise

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found!")

# MongoDB connection with advanced configuration
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["advanced_broadcast_bot"]
    
    # Collections
    channels_col = db["channels"]
    broadcast_messages_col = db["broadcast_messages"]
    users_col = db["users"]
    scheduled_broadcasts_col = db["scheduled_broadcasts"]
    analytics_col = db["analytics"]
    settings_col = db["settings"]
    
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    raise

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Convert ADMIN_IDS to list
if isinstance(ADMIN_IDS, str):
    ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS.split(",") if id.strip()]
else:
    ADMIN_IDS = []

# Thread pool for concurrent broadcasts
broadcast_executor = ThreadPoolExecutor(max_workers=5)  # Handle 5 concurrent broadcasts

class AdvancedBotState:
    def __init__(self):
        self.broadcast_state = {}
        self.active_reposts = {}
        self.scheduled_tasks = {}
        self.analytics_cache = {}
        self.user_sessions = {}
        self.active_broadcasts = {}  # Track active broadcasts

bot_state = AdvancedBotState()

class AdvancedBroadcastBot:
    def __init__(self):
        self.channels_col = channels_col
        self.broadcast_messages_col = broadcast_messages_col
        self.users_col = users_col
        self.scheduled_broadcasts_col = scheduled_broadcasts_col
        self.analytics_col = analytics_col
        self.settings_col = settings_col
        
        # Initialize analytics
        self.init_analytics()
        
        # Start background tasks
        self.start_background_tasks()

    def init_analytics(self):
        """Initialize analytics collection"""
        try:
            analytics_col.update_one(
                {"_id": "stats"},
                {
                    "$setOnInsert": {
                        "total_broadcasts": 0,
                        "total_messages_sent": 0,
                        "failed_broadcasts": 0,
                        "active_users": 0,
                        "premium_users": 0,
                        "total_channels": 0,
                        "created_at": datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Analytics init error: {e}")

    def start_background_tasks(self):
        """Start background tasks"""
        threading.Thread(target=self.check_scheduled_broadcasts, daemon=True).start()
        threading.Thread(target=self.check_expired_premium_users, daemon=True).start()

    def add_channel(self, channel_id: int, user_id: int) -> bool:
        """Add channel to user's collection"""
        try:
            # Check if channel already exists for this user
            existing = self.channels_col.find_one({
                "channel_id": channel_id,
                "user_id": user_id
            })
            
            if existing:
                return False
            
            # Get channel info
            chat_info = bot.get_chat(channel_id)
            
            channel_data = {
                "channel_id": channel_id,
                "user_id": user_id,
                "title": chat_info.title,
                "username": getattr(chat_info, 'username', None),
                "type": chat_info.type,
                "member_count": getattr(chat_info, 'member_count', 0),
                "added_at": datetime.now(),
                "settings": {
                    "broadcast_delay": BROADCAST_DELAY,
                    "auto_delete": False,
                    "auto_repost": False
                }
            }
            
            self.channels_col.insert_one(channel_data)
            self.update_analytics("total_channels", 1)
            return True
            
        except Exception as e:
            logger.error(f"Error adding channel {channel_id}: {e}")
            return False

    def get_all_channels(self, user_id: int) -> List[Dict]:
        """Get all channels for a user"""
        try:
            return list(self.channels_col.find({"user_id": user_id}))
        except Exception as e:
            logger.error(f"Error getting channels for user {user_id}: {e}")
            return []

    def save_broadcast_message(self, user_id: int, channel_id: int, message_id: int, broadcast_id: str):
        """Save broadcast message details"""
        try:
            self.broadcast_messages_col.insert_one({
                "user_id": user_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "broadcast_id": broadcast_id,
                "sent_at": datetime.now()
            })
        except Exception as e:
            logger.error(f"Error saving broadcast message: {e}")

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized (admin or premium)"""
        return self.is_admin(user_id) or self.is_premium(user_id)

    def is_premium(self, user_id: int) -> bool:
        """Check if user has premium access"""
        try:
            user = self.users_col.find_one({"user_id": user_id})
            if not user:
                return False
            
            if user.get("is_premium"):
                expiry = user.get("premium_expiry")
                if expiry and datetime.now() < expiry:
                    return True
                else:
                    # Premium expired, update status
                    self.users_col.update_one(
                        {"user_id": user_id},
                        {"$set": {"is_premium": False}}
                    )
            return False
        except Exception as e:
            logger.error(f"Error checking premium status: {e}")
            return False

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Add or update user"""
        try:
            self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "last_active": datetime.now()
                    },
                    "$setOnInsert": {
                        "joined_at": datetime.now(),
                        "is_premium": False,
                        "total_broadcasts": 0
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error adding user: {e}")

    def make_premium(self, user_id: int, days: int = 30) -> bool:
        """Make user premium (owner only)"""
        try:
            expiry = datetime.now() + timedelta(days=days)
            self.users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_premium": True,
                        "premium_expiry": expiry,
                        "premium_activated_at": datetime.now()
                    },
                    "$setOnInsert": {
                        "joined_at": datetime.now(),
                        "total_broadcasts": 0
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error making user premium: {e}")
            return False

    def remove_premium(self, user_id: int) -> bool:
        """Remove premium from user (owner only)"""
        try:
            self.users_col.update_one(
                {"user_id": user_id},
                {"$set": {"is_premium": False}}
            )
            return True
        except Exception as e:
            logger.error(f"Error removing premium: {e}")
            return False

    def update_analytics(self, metric: str, value: int = 1):
        """Update analytics"""
        try:
            self.analytics_col.update_one(
                {"_id": "stats"},
                {"$inc": {metric: value}}
            )
        except Exception as e:
            logger.error(f"Error updating analytics: {e}")

    def check_scheduled_broadcasts(self):
        """Check and execute scheduled broadcasts"""
        while True:
            try:
                now = datetime.now()
                scheduled = self.scheduled_broadcasts_col.find({
                    "scheduled_time": {"$lte": now},
                    "status": "pending"
                })
                
                for broadcast in scheduled:
                    try:
                        # Execute broadcast
                        self.execute_scheduled_broadcast(broadcast)
                        
                        # Update status
                        self.scheduled_broadcasts_col.update_one(
                            {"_id": broadcast["_id"]},
                            {"$set": {"status": "completed"}}
                        )
                    except Exception as e:
                        logger.error(f"Error executing scheduled broadcast: {e}")
                        self.scheduled_broadcasts_col.update_one(
                            {"_id": broadcast["_id"]},
                            {"$set": {"status": "failed"}}
                        )
                
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduled broadcast checker: {e}")
                time.sleep(60)

    def check_expired_premium_users(self):
        """Check and update expired premium users"""
        while True:
            try:
                now = datetime.now()
                expired_users = self.users_col.find({
                    "is_premium": True,
                    "premium_expiry": {"$lt": now}
                })
                
                for user in expired_users:
                    self.users_col.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"is_premium": False}}
                    )
                    logger.info(f"Premium expired for user {user['user_id']}")
                
                time.sleep(3600)  # Check every hour
            except Exception as e:
                logger.error(f"Error checking expired premium users: {e}")
                time.sleep(3600)

    def execute_scheduled_broadcast(self, broadcast_data):
        """Execute a scheduled broadcast"""
        try:
            # This would contain the logic to execute the broadcast
            # Implementation depends on how you store the message data
            pass
        except Exception as e:
            logger.error(f"Error executing scheduled broadcast: {e}")

# Initialize broadcast bot
broadcast_bot = AdvancedBroadcastBot()

def extract_telegram_links(text: str) -> List[str]:
    """Extract Telegram channel/group links from text"""
    patterns = [
        r'https?://t\.me/([a-zA-Z0-9_]+)',
        r'@([a-zA-Z0-9_]+)',
        r't\.me/([a-zA-Z0-9_]+)',
        r'https?://telegram\.me/([a-zA-Z0-9_]+)'
    ]
    
    links = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match not in links:
                links.append(match)
    
    return links

def resolve_telegram_link(link: str) -> Optional[int]:
    """Resolve Telegram link to channel ID"""
    try:
        # Try to get chat info directly
        if link.startswith('@'):
            chat_info = bot.get_chat(link)
            return chat_info.id
        elif link.startswith('https://t.me/') or link.startswith('t.me/'):
            username = link.split('/')[-1]
            chat_info = bot.get_chat(f"@{username}")
            return chat_info.id
        else:
            # Try as username
            chat_info = bot.get_chat(f"@{link}")
            return chat_info.id
    except Exception as e:
        logger.error(f"Error resolving link {link}: {e}")
        return None

def send_message_to_channel(channel_data: Dict, message, broadcast_id: str, delete_time: Optional[int] = None) -> Dict:
    """Send message to a single channel (for concurrent processing)"""
    result = {
        "channel_id": channel_data["channel_id"],
        "success": False,
        "error": None,
        "message_id": None
    }
    
    try:
        channel_id = channel_data["channel_id"]
        sent = None
        
        # Add delay based on channel settings
        delay = channel_data.get("settings", {}).get("broadcast_delay", BROADCAST_DELAY)
        if delay > 0:
            time.sleep(delay)
        
        # Get formatted text if available
        formatted_text = None
        if hasattr(message, 'chat') and message.chat.id in bot_state.broadcast_state:
            state = bot_state.broadcast_state.get(message.chat.id, {})
            formatted_text = state.get("formatted_text")
        
        # Send based on content type
        if message.content_type == "text":
            text_to_send = formatted_text if formatted_text else message.text
            sent = bot.send_message(channel_id, text_to_send, parse_mode="Markdown")
        elif message.content_type == "photo":
            caption = formatted_text if formatted_text else (message.caption or "")
            try:
                sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception as e:
                sent = bot.send_photo(channel_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
        elif message.content_type == "video":
            caption = formatted_text if formatted_text else (message.caption or "")
            try:
                sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception as e:
                sent = bot.send_video(channel_id, message.video.file_id, caption=caption, parse_mode="Markdown")
        elif message.content_type == "document":
            caption = formatted_text if formatted_text else (message.caption or "")
            try:
                sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception as e:
                sent = bot.send_document(channel_id, message.document.file_id, caption=caption, parse_mode="Markdown")
        else:
            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)

        if sent:
            result["success"] = True
            result["message_id"] = sent.message_id
            
            # Save broadcast message
            broadcast_bot.save_broadcast_message(message.chat.id, channel_id, sent.message_id, broadcast_id)
            
            # Schedule auto delete if enabled
            if delete_time:
                threading.Thread(
                    target=advanced_auto_delete, 
                    args=(channel_id, sent.message_id, delete_time)
                ).start()
                
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error sending to channel {channel_data['channel_id']}: {e}")
    
    return result

def finish_advanced_broadcast(chat_id: int):
    """Advanced broadcast function with concurrent processing"""
    try:
        state = bot_state.broadcast_state.get(chat_id)
        if not state:
            return

        message = state["message"]
        repost_time = state.get("repost_time")
        delete_time = state.get("delete_time")
        broadcast_type = state.get("broadcast_type", "immediate")

        broadcast_id = f"broadcast_{chat_id}_{int(time.time())}"
        channels = broadcast_bot.get_all_channels(chat_id)
        
        if not channels:
            bot.send_message(chat_id, "❌ No channels found! Please add channels first.")
            return
            
        # Check if user already has an active broadcast
        if chat_id in bot_state.active_broadcasts:
            bot.send_message(chat_id, "⚠️ **Broadcast Already Running!**\n\nPlease wait for the current broadcast to complete.")
            return
        
        # Mark broadcast as active
        bot_state.active_broadcasts[chat_id] = {
            "started_at": datetime.now(),
            "total_channels": len(channels),
            "completed": 0,
            "failed": 0
        }

        # Send initial status
        status_msg = bot.send_message(
            chat_id,
            f"📡 **Broadcasting to {len(channels)} channels...**\n\n⏳ Please wait...",
            parse_mode="Markdown"
        )

        # Process broadcasts concurrently
        futures = []
        for channel in channels:
            future = broadcast_executor.submit(
                send_message_to_channel, 
                channel, 
                message, 
                broadcast_id, 
                delete_time
            )
            futures.append(future)

        # Collect results
        sent_count = 0
        failed_count = 0
        failed_channels = []
        
        for i, future in enumerate(as_completed(futures)):
            try:
                result = future.result()
                if result["success"]:
                    sent_count += 1
                else:
                    failed_count += 1
                    failed_channels.append(str(result["channel_id"]))
                
                # Update progress every 5 channels
                if (i + 1) % 5 == 0:
                    try:
                        bot.edit_message_text(
                            f"📡 **Broadcasting Progress**\n\n"
                            f"✅ Sent: {sent_count}\n"
                            f"❌ Failed: {failed_count}\n"
                            f"📊 Progress: {i + 1}/{len(channels)}",
                            chat_id, status_msg.message_id,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to update progress message: {e}")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing broadcast result: {e}")

        # Update analytics
        broadcast_bot.update_analytics("total_broadcasts")
        broadcast_bot.update_analytics("total_messages_sent", sent_count)
        if failed_count > 0:
            broadcast_bot.update_analytics("failed_broadcasts", failed_count)

        # Update user stats
        broadcast_bot.users_col.update_one(
            {"user_id": chat_id},
            {
                "$inc": {"total_broadcasts": 1},
                "$set": {"last_active": datetime.now()}
            }
        )

        # Final result message
        result_text = f"""
✅ **Broadcast Completed!**

📊 **Results:**
• ✅ Sent: `{sent_count}`
• ❌ Failed: `{failed_count}`
• 📢 Total Channels: `{len(channels)}`
• 🕐 Broadcast Time: `{datetime.now().strftime('%H:%M:%S')}`

⚙️ **Settings:**
• 🔄 Auto Repost: {'✅' if repost_time else '❌'} {f'({repost_time} min)' if repost_time else ''}
• 🗑 Auto Delete: {'✅' if delete_time else '❌'} {f'({delete_time} min)' if delete_time else ''}
• 📋 Broadcast ID: `{broadcast_id}`
        """
        
        if failed_channels:
            failed_list = ', '.join(failed_channels[:5])
            if len(failed_channels) > 5:
                failed_list += f" and {len(failed_channels) - 5} more"
            result_text += f"\n❌ **Failed Channels:**\n`{failed_list}`"

        try:
            bot.edit_message_text(result_text, chat_id, status_msg.message_id, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, result_text, parse_mode="Markdown")

        # Start auto repost if enabled
        if repost_time:
            bot.send_message(
                chat_id,
                f"🔄 **Auto Repost Started!**\n\n"
                f"⏱ **Interval:** `{repost_time} minutes`\n"
                f"🗑 **Auto Delete:** {'✅' if delete_time else '❌'}\n"
                f"🔢 **Channels:** `{sent_count}`\n\n"
                f"Use **⏹ Stop Repost** button to cancel.",
                parse_mode="Markdown"
            )
            
            stop_flag = {"stop": False}
            bot_state.active_reposts[chat_id] = stop_flag
            threading.Thread(
                target=advanced_auto_repost, 
                args=(chat_id, message, repost_time, delete_time, stop_flag)
            ).start()

        # Clear broadcast state and active broadcast
        bot_state.broadcast_state.pop(chat_id, None)
        bot_state.active_broadcasts.pop(chat_id, None)

    except Exception as e:
        logger.error(f"❌ Error in finish_broadcast: {e}")
        bot.send_message(chat_id, "❌ An error occurred during broadcast")
        # Clear active broadcast on error
        bot_state.active_broadcasts.pop(chat_id, None)

def apply_message_formatting(user_id: int, format_type: str):
    """Apply formatting to message and show preview"""
    try:
        state = bot_state.broadcast_state.get(user_id)
        if not state or "message" not in state:
            bot.send_message(user_id, "❌ No message found to format!")
            return
            
        message = state["message"]
        original_text = message.text or message.caption or ""
        
        # Apply formatting based on type
        if format_type == "format_plain":
            formatted_text = original_text
            format_name = "Plain Text"
        elif format_type == "format_bold":
            formatted_text = f"**{original_text}**"
            format_name = "Bold Text"
        elif format_type == "format_italic":
            formatted_text = f"*{original_text}*"
            format_name = "Italic Text"
        elif format_type == "format_links":
            # Add some example links
            formatted_text = f"{original_text}\n\n🔗 **Useful Links:**\n• [Telegram](https://t.me/)\n• [Support](https://t.me/)\n• [Channel](https://t.me/)"
            format_name = "With Links"
        elif format_type == "format_code":
            formatted_text = f"```\n{original_text}\n```"
            format_name = "Code Format"
        elif format_type == "format_quote":
            formatted_text = f"> {original_text}\n\n— *Quote*"
            format_name = "Quote Style"
        elif format_type == "format_sticky":
            formatted_text = f"📌 **IMPORTANT**\n\n{original_text}\n\n📌 *Pinned Message*"
            format_name = "Sticky Note"
        elif format_type == "format_highlight":
            formatted_text = f"⚡ **HIGHLIGHT** ⚡\n\n{original_text}\n\n🎯 *Highlighted Content*"
            format_name = "Highlight"
        else:
            formatted_text = original_text
            format_name = "Default"
        
        # Store formatted text
        state["formatted_text"] = formatted_text
        state["format_type"] = format_type
        
        # Show preview
        preview_text = f"""
🎨 **Formatting Applied: {format_name}**

📝 **Preview:**
{formatted_text[:200]}{'...' if len(formatted_text) > 200 else ''}

✅ **Ready to broadcast!**
        """
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Confirm & Continue", callback_data="format_confirm"),
            types.InlineKeyboardButton("🔄 Try Different Format", callback_data="format_retry"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="format_cancel")
        )
        
        bot.send_message(
            user_id,
            preview_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error applying formatting: {e}")
        bot.send_message(user_id, f"❌ Error applying formatting: {e}")

def advanced_auto_delete(chat_id: int, msg_id: int, delete_time: int):
    """Advanced auto delete with retry and logging"""
    try:
        logger.info(f"⏰ Auto delete scheduled: {msg_id} from {chat_id} in {delete_time} minutes")
        time.sleep(delete_time * 60)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = bot.delete_message(chat_id, msg_id)
                if result:
                    logger.info(f"✅ Auto deleted message {msg_id} from {chat_id}")
                    broadcast_bot.update_analytics("auto_deletes")
                    
                    # Update message status
                    broadcast_bot.broadcast_messages_col.update_one(
                        {"channel_id": chat_id, "message_id": msg_id},
                        {"$set": {"status": "deleted", "deleted_at": datetime.now()}}
                    )
                    break
                else:
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Wait before retry
                        continue
                    else:
                        logger.warning(f"⚠️ Failed to delete message {msg_id} from {chat_id} after {max_retries} attempts")
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Delete attempt {attempt + 1} failed: {e}")
                    time.sleep(5)
                else:
                    logger.error(f"❌ Auto delete failed for {chat_id} after {max_retries} attempts: {e}")
                    
    except Exception as e:
        logger.error(f"❌ Auto delete function error: {e}")

def advanced_auto_repost(chat_id: int, message, repost_time: int, delete_time: Optional[int], stop_flag: Dict[str, bool]):
    """Advanced auto repost with enhanced features"""
    logger.info(f"🔄 Starting auto repost for user {chat_id}")
    repost_count = 0
    
    while not stop_flag.get("stop", False):
        try:
            logger.info(f"🔄 Auto repost cycle {repost_count + 1} starting...")
            time.sleep(repost_time * 60)
            if stop_flag.get("stop", False):
                logger.info(f"🔄 Auto repost stopped for user {chat_id}")
                break
                
            channels = broadcast_bot.get_all_channels(chat_id)
            logger.info(f"🔄 Got {len(channels)} channels for repost")
            success_count = 0
            failed_count = 0
            
            for ch in channels:
                try:
                    if stop_flag.get("stop", False):
                        break
                        
                    sent = None
                    channel_id = ch["channel_id"]
                    logger.info(f"🔄 Reposting to channel {channel_id}")
                    
                    # Add delay between channels
                    delay = ch.get("settings", {}).get("broadcast_delay", BROADCAST_DELAY)
                    time.sleep(delay)
                    
                    # Get formatted text if available
                    formatted_text = None
                    if hasattr(message, 'chat') and message.chat.id in bot_state.broadcast_state:
                        state = bot_state.broadcast_state.get(message.chat.id, {})
                        formatted_text = state.get("formatted_text")
                    
                    # Send message based on type
                    if message.content_type == "text":
                        text_to_send = formatted_text if formatted_text else message.text
                        logger.info(f"🔄 Sending text to {channel_id}")
                        sent = bot.send_message(channel_id, text_to_send, parse_mode="Markdown")
                    elif message.content_type == "photo":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"🔄 Sending photo to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"🔄 Forward failed for {channel_id}, trying send_photo: {e}")
                            sent = bot.send_photo(channel_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
                    elif message.content_type == "video":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"🔄 Sending video to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"🔄 Forward failed for {channel_id}, trying send_video: {e}")
                            sent = bot.send_video(channel_id, message.video.file_id, caption=caption, parse_mode="Markdown")
                    elif message.content_type == "document":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"🔄 Sending document to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"🔄 Forward failed for {channel_id}, trying send_document: {e}")
                            sent = bot.send_document(channel_id, message.document.file_id, caption=caption, parse_mode="Markdown")
                    else:
                        logger.info(f"🔄 Forwarding message to {channel_id}")
                        sent = bot.forward_message(channel_id, message.chat.id, message.message_id)

                    if sent:
                        success_count += 1
                        logger.info(f"🔄 ✅ Successfully reposted to {channel_id}")
                        broadcast_bot.save_broadcast_message(
                            chat_id, channel_id, sent.message_id, 
                            f"auto_repost_{chat_id}_{int(time.time())}", "auto_repost"
                        )
                        
                        # Schedule auto delete if enabled
                        if delete_time:
                            logger.info(f"🔄 Scheduling auto delete for {channel_id} in {delete_time} minutes")
                            threading.Thread(
                                target=advanced_auto_delete, 
                                args=(channel_id, sent.message_id, delete_time)
                            ).start()
                    else:
                        failed_count += 1
                        logger.error(f"🔄 ❌ Failed to repost to {channel_id} - sent is None")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"🔄 ❌ Repost failed for {ch.get('channel_id')}: {e}")
                    logger.error(f"🔄 Exception details: {type(e).__name__}: {str(e)}")
            
            repost_count += 1
            broadcast_bot.update_analytics("auto_reposts")
            
            logger.info(f"🔄 Repost cycle {repost_count} completed - Success: {success_count}, Failed: {failed_count}")
            
            # Notify user every 10 reposts
            if repost_count % 10 == 0:
                try:
                    bot.send_message(
                        chat_id,
                        f"🔄 **Auto Repost Update**\n\n"
                        f"**Cycle:** {repost_count}\n"
                        f"**Last Success:** {success_count}\n"
                        f"**Last Failed:** {failed_count}\n"
                        f"**Interval:** {repost_time} minutes",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"🔄 Failed to send repost update: {e}")
            
        except Exception as e:
            logger.error(f"🔄 ❌ Error in auto_repost: {e}")
            logger.error(f"🔄 Exception details: {type(e).__name__}: {str(e)}")
            time.sleep(60)

@bot.message_handler(commands=["start", "help", "stats", "analytics", "premium", "cleanup", "clear", "id"])
def start_cmd(message):
    """Enhanced start command with analytics"""
    user_id = message.from_user.id
    
    # Add user to database
    broadcast_bot.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Check if user is premium or admin
    if not (broadcast_bot.is_premium(user_id) or broadcast_bot.is_admin(user_id)):
        premium_text = f"""
🔒 **Premium Required!** ⚡

🚫 **Access Denied** - This bot is only for Premium users.

💎 **Premium Features:**
• 📢 **Unlimited Broadcasts**
• ⚡ **Auto Repost & Delete**
• 📋 **Bulk Channel Management**
• 📊 **Advanced Analytics**
• 🎯 **Priority Support**
• ⏱ **Custom Auto Delete Times**
• 🔢 **100+ Channels Support**
• 🧹 **Auto Cleanup System**
• 🛑 **Instant Stop All**

💰 **Premium Plans:**
• **1 Month:** ₹299
• **3 Months:** ₹799
• **6 Months:** ₹1499
• **1 Year:** ₹2499

👑 **Owner Only Activation:**
• Only the bot owner can activate premium
• Contact owner directly for activation
• No self-activation allowed

📞 **Contact Owner:** @{OWNER_ID}

🔑 **Your User ID:** `{user_id}`

⚠️ **Important:** Send your ID to owner for premium activation!
        """
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💎 Get Premium", callback_data="get_premium"),
            types.InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin"),
        )
        
        try:
            bot.send_photo(
                message.chat.id,
                "https://i.ibb.co/GQrGd0MV/a101f4b2bfa4.jpg",
                caption=premium_text,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error sending premium message: {e}")
            bot.send_message(message.chat.id, premium_text, reply_markup=markup, parse_mode="Markdown")
        
        return
    
    if message.text.startswith("/stats"):
        # Show user statistics
        analytics = broadcast_bot.get_user_analytics(message.chat.id)
        stats_text = f"""
📊 **Your Statistics**

**👤 Profile:**
• User ID: `{message.chat.id}`
• Member Since: `{analytics.get('member_since', 'Unknown')}`
• Last Active: `{analytics.get('last_active', 'Now')}`

**📈 Usage Stats:**
• Total Channels: `{analytics.get('total_channels', 0)}`
• Total Broadcasts: `{analytics.get('total_broadcasts', 0)}`
• Recent Broadcasts: `{analytics.get('recent_broadcasts', 0)} (7 days)`

**💎 Subscription:**
• Type: `{analytics.get('subscription_type', 'Free').title()}`
• Status: {'🟢 Active' if broadcast_bot.is_premium(message.chat.id) else '🔶 Free'}
        """
        bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")
        return
    
    if message.text.startswith("/analytics") and broadcast_bot.is_admin(message.chat.id):
        # Show admin analytics
        today = datetime.now().strftime('%Y-%m-%d')
        analytics = broadcast_bot.analytics_col.find_one({"date": today})
        
        if analytics:
            admin_stats = f"""
🔧 **Admin Analytics - {today}**

**📊 Today's Stats:**
• Total Broadcasts: `{analytics.get('total_broadcasts', 0)}`
• Messages Sent: `{analytics.get('total_messages_sent', 0)}`
• Active Users: `{broadcast_bot.users_col.count_documents({'last_active': {'$gte': datetime.now() - timedelta(days=1)}})}`
• New Channels: `{analytics.get('new_channels_added', 0)}`
• Auto Reposts: `{analytics.get('auto_reposts', 0)}`
• Auto Deletes: `{analytics.get('auto_deletes', 0)}`
• Failed Broadcasts: `{analytics.get('failed_broadcasts', 0)}`

**📈 Overall Stats:**
• Total Users: `{broadcast_bot.users_col.count_documents({})}`
• Total Channels: `{broadcast_bot.channels_col.count_documents({})}`
• Premium Users: `{broadcast_bot.users_col.count_documents({'is_premium': True})}`
            """
            bot.send_message(message.chat.id, admin_stats, parse_mode="Markdown")
        return
    
    if message.text.startswith("/premium"):
        premium_text = f"""
💎 **Premium Features**

**🆓 Free Plan:**
• {MAX_CHANNELS_PER_USER} channels maximum
• Basic broadcast features
• Standard support

**💎 Premium Plan:**
• {MAX_CHANNELS_PER_USER * 2} channels maximum
• Advanced analytics
• Priority support
• Scheduled broadcasts
• Custom auto-repost intervals
• Bulk channel management

**Current Status:** {'💎 Premium' if broadcast_bot.is_premium(message.chat.id) else '🆓 Free'}

Contact admin to upgrade to Premium!
        """
        bot.send_message(message.chat.id, premium_text, parse_mode="Markdown")
        return

    if message.text.startswith("/id"):
        chat_id = message.chat.id
        chat_type = message.chat.type
        
        if chat_type == "private":
            id_text = f"""
🆔 **Your Information**

**👤 User Details:**
• **User ID:** `{chat_id}`
• **Username:** @{message.from_user.username or "None"}
• **First Name:** {message.from_user.first_name or "None"}
• **Last Name:** {message.from_user.last_name or "None"}
• **Chat Type:** Private Chat

**💡 Usage:**
• Share this ID with owner for premium activation
• Use this ID for bot configuration
            """
        else:
            chat_title = message.chat.title or "Unknown"
            id_text = f"""
🆔 **Channel/Group Information**

**📢 Channel Details:**
• **Channel ID:** `{chat_id}`
• **Channel Name:** {chat_title}
• **Chat Type:** {chat_type.title()}
• **Username:** @{message.chat.username or "None"}

**💡 Usage:**
• Use this ID to add channel to bot
• Copy this ID for bulk channel addition
• Share with admin for channel management
            """
        
        bot.send_message(message.chat.id, id_text, parse_mode="Markdown")
        return

    if message.text.startswith("/cleanup") or message.text.startswith("/clear"):
        if not (broadcast_bot.is_premium(message.chat.id) or broadcast_bot.is_admin(message.chat.id)):
            bot.send_message(message.chat.id, "🔒 **Premium Required!**\n\nThis feature is only for premium users.")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🗑 Delete All Messages", callback_data="cleanup_all_messages"),
            types.InlineKeyboardButton("⏹ Stop All Reposts", callback_data="cleanup_stop_reposts"),
            types.InlineKeyboardButton("🗑 Delete & Stop All", callback_data="cleanup_everything"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="cleanup_cancel"),
        )
        
        cleanup_text = f"""
🧹 **Auto Cleanup System**

**🔧 Available Actions:**
• 🗑 **Delete All Messages** - Remove all broadcast messages from channels
• ⏹ **Stop All Reposts** - Stop all active auto reposts
• 🗑 **Delete & Stop All** - Complete cleanup (messages + reposts)

**⚠️ Warning:** These actions cannot be undone!

Choose an option:
        """
        bot.send_message(message.chat.id, cleanup_text, reply_markup=markup, parse_mode="Markdown")
        return

    # Main menu
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
        types.InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
        types.InlineKeyboardButton("📋 My Channels", callback_data="my_channels"),
        types.InlineKeyboardButton("🔍 Find Channels", callback_data="find_channels"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Analytics", callback_data="user_analytics"),
        types.InlineKeyboardButton("📅 Schedule", callback_data="schedule_broadcast"),
        types.InlineKeyboardButton("📜 History", callback_data="show_history"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="user_settings"),
    )
    markup.add(
        types.InlineKeyboardButton("⏹ Stop Repost", callback_data="stop_repost"),
        types.InlineKeyboardButton("🗑 Stop & Delete", callback_data="stop_and_delete"),
        types.InlineKeyboardButton("🛑 Instant Stop All", callback_data="instant_stop_all"),
        types.InlineKeyboardButton("🧹 Auto Cleanup", callback_data="cleanup_menu"),
    )
    
    if broadcast_bot.is_admin(message.chat.id):
        markup.add(
            types.InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel"),
        )

    user_analytics = broadcast_bot.get_user_analytics(message.chat.id)
    welcome_text = f"""
🎉 **Advanced Broadcast Bot** 🚀

**👋 Welcome, {message.from_user.first_name}!**

**📊 Your Dashboard:**
• 📢 **Channels:** `{user_analytics.get('total_channels', 0)}`
• 📈 **Broadcasts:** `{user_analytics.get('total_broadcasts', 0)}`
• 💎 **Plan:** `{user_analytics.get('subscription_type', 'Free').title()}`
• 🟢 **Status:** ✅ Online

**🔥 Advanced Features:**
• ⚡ **Auto Repost & Delete**
• ⏰ **Scheduled Broadcasts**  
• 📊 **Real-time Analytics**
• 🎨 **Multi-media Support**
• 📋 **Bulk Operations**
• 🛑 **Instant Stop All**

**💡 Pro Tips:**
• Use `/id` to get channel IDs quickly!
• Use "🛑 Instant Stop All" for emergency stops
• Use "🧹 Auto Cleanup" for complete cleanup

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
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Advanced callback handler"""
    if not (broadcast_bot.is_authorized(call.message.chat.id) or 
            broadcast_bot.is_premium(call.message.chat.id) or 
            broadcast_bot.is_admin(call.message.chat.id)):
        bot.answer_callback_query(call.id, "🚫 Access Denied!")
        return

    try:
        user_id = call.message.chat.id
        state = bot_state.broadcast_state.get(user_id, {})

        if call.data == "broadcast":
            bot_state.broadcast_state[user_id] = {"step": "waiting_msg"}
            bot.send_message(user_id, "📢 Send your broadcast message:")

        elif call.data == "repost_yes":
            state["step"] = "ask_repost_time"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⏱ 5m", callback_data="repost_5"),
                types.InlineKeyboardButton("⏱ 10m", callback_data="repost_10"),
                types.InlineKeyboardButton("⏱ 30m", callback_data="repost_30"),
                types.InlineKeyboardButton("⏱ 1h", callback_data="repost_60"),
            )
            bot.send_message(user_id, "⏱ Choose repost interval:", reply_markup=markup)
            
        elif call.data == "repost_no":
            state["repost_time"] = None
            state["step"] = "ask_autodelete"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
                types.InlineKeyboardButton("❌ No", callback_data="delete_no"),
            )
            bot.send_message(user_id, "🗑 Enable Auto Delete?", reply_markup=markup)
            
        elif call.data == "delete_yes":
            state["step"] = "ask_autodelete_time"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🗑 5m", callback_data="delete_5"),
                types.InlineKeyboardButton("🗑 10m", callback_data="delete_10"),
                types.InlineKeyboardButton("🗑 15m", callback_data="delete_15"),
                types.InlineKeyboardButton("🗑 30m", callback_data="delete_30"),
                types.InlineKeyboardButton("🗑 1h", callback_data="delete_60"),
                types.InlineKeyboardButton("🗑 2h", callback_data="delete_120"),
                types.InlineKeyboardButton("🗑 6h", callback_data="delete_360"),
                types.InlineKeyboardButton("🗑 12h", callback_data="delete_720"),
                types.InlineKeyboardButton("🗑 24h", callback_data="delete_1440"),
                types.InlineKeyboardButton("⏱ Custom Time", callback_data="delete_custom"),
            )
            bot.send_message(user_id, "🗑 Choose delete time:", reply_markup=markup)
            
        elif call.data == "delete_no":
            state["delete_time"] = None
            finish_advanced_broadcast(user_id)

        elif call.data.startswith("repost_"):
            time_value = int(call.data.replace("repost_", ""))
            state["repost_time"] = time_value
            state["step"] = "ask_autodelete"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Yes", callback_data="delete_yes"),
                types.InlineKeyboardButton("❌ No", callback_data="delete_no"),
            )
            bot.send_message(user_id, "🗑 Enable Auto Delete?", reply_markup=markup)

        elif call.data.startswith("delete_"):
            if call.data == "delete_custom":
                state["step"] = "ask_autodelete_time"
                bot.send_message(
                    user_id, 
                    "⏱ **Custom Delete Time**\n\n"
                    "Enter delete time in minutes:\n\n"
                    "📝 **Examples:**\n"
                    "• `10` = 10 minutes\n"
                    "• `60` = 1 hour\n"
                    "• `1440` = 24 hours\n\n"
                    "⚠️ **Minimum:** 1 minute"
                )
            else:
                time_value = int(call.data.replace("delete_", ""))
                state["delete_time"] = time_value
                finish_advanced_broadcast(user_id)

        elif call.data == "stop_repost":
            stop_repost(user_id)
            
        # Formatting handlers
        elif call.data.startswith("format_"):
            if call.data == "format_skip":
                # Skip formatting and go to repost question
                state["step"] = "ask_repost"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Enable Auto Repost", callback_data="repost_yes"),
                    types.InlineKeyboardButton("❌ Broadcast Once", callback_data="repost_no"),
                )
                bot.send_message(user_id, "🔄 Enable Auto Repost?", reply_markup=markup)
            else:
                # Apply formatting
                apply_message_formatting(user_id, call.data)
                
        elif call.data == "format_confirm":
            # Confirm formatting and continue to repost
            state["step"] = "ask_repost"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Enable Auto Repost", callback_data="repost_yes"),
                types.InlineKeyboardButton("❌ Broadcast Once", callback_data="repost_no"),
            )
            bot.send_message(user_id, "🔄 Enable Auto Repost?", reply_markup=markup)
            
        elif call.data == "format_retry":
            # Show formatting options again
            state["step"] = "ask_formatting"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📝 Plain Text", callback_data="format_plain"),
                types.InlineKeyboardButton("🎨 Bold Text", callback_data="format_bold"),
                types.InlineKeyboardButton("📋 Italic Text", callback_data="format_italic"),
                types.InlineKeyboardButton("🔗 With Links", callback_data="format_links"),
                types.InlineKeyboardButton("📊 Code Format", callback_data="format_code"),
                types.InlineKeyboardButton("💬 Quote Style", callback_data="format_quote"),
                types.InlineKeyboardButton("📌 Sticky Note", callback_data="format_sticky"),
                types.InlineKeyboardButton("🎯 Highlight", callback_data="format_highlight"),
                types.InlineKeyboardButton("🚀 Skip Formatting", callback_data="format_skip")
            )
            
            bot.send_message(
                user_id, 
                "🎨 **Choose Message Formatting:**\n\n"
                "Select how you want your message to appear:\n\n"
                "• 📝 **Plain Text** - Simple text\n"
                "• 🎨 **Bold Text** - **Bold formatting**\n"
                "• 📋 **Italic Text** - *Italic formatting*\n"
                "• 🔗 **With Links** - Clickable links\n"
                "• 📊 **Code Format** - `Code blocks`\n"
                "• 💬 **Quote Style** - > Quoted text\n"
                "• 📌 **Sticky Note** - 📌 Pinned style\n"
                "• 🎯 **Highlight** - ⚡ Highlighted\n"
                "• 🚀 **Skip Formatting** - Continue without changes",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
        elif call.data == "format_cancel":
            # Cancel formatting and clear state
            bot_state.broadcast_state.pop(user_id, None)
            bot.send_message(user_id, "❌ Formatting cancelled. Send /start to try again.")
            
        elif call.data == "stop_and_delete":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Yes, Delete All", callback_data="confirm_delete_all"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete"),
            )
            bot.send_message(
                user_id,
                "⚠️ **Warning!**\n\n"
                "This will:\n"
                "• Stop all active reposts\n"
                "• Delete ALL broadcast messages from channels\n"
                "• Cannot be undone!\n\n"
                "Are you sure?",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
        elif call.data == "confirm_delete_all":
            # Stop all reposts
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
            
            # Delete all broadcast messages
            deleted_count = 0
            failed_count = 0
            
            try:
                # Get all broadcast messages for this user
                broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 1000)
                
                for msg in broadcast_messages:
                    try:
                        result = bot.delete_message(msg['channel_id'], msg['message_id'])
                        if result:
                            deleted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Failed to delete message {msg['message_id']} from {msg['channel_id']}: {e}")
                
                # Clear broadcast history from database
                broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
                
                result_text = f"""
🗑 **Broadcast Cleanup Completed!**

📊 **Results:**
• ✅ Messages Deleted: `{deleted_count}`
• ❌ Failed Deletions: `{failed_count}`
• 🔄 Reposts Stopped: ✅
• 📋 History Cleared: ✅

✅ All broadcast messages have been removed from channels.
                """
                bot.send_message(user_id, result_text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Error in confirm_delete_all: {e}")
                bot.send_message(user_id, "❌ Error during cleanup process")
                
        elif call.data == "cancel_delete":
            bot.send_message(user_id, "❌ Operation cancelled.")

        elif call.data == "instant_stop_all":
            # Instant stop all reposts and delete all messages
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
            
            # Get all broadcast messages
            broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 1000)
            
            # Send instant status
            status_msg = bot.send_message(
                user_id,
                f"🛑 **Instant Stop All Activated!**\n\n"
                f"⏹ Stopping all reposts...\n"
                f"🗑 Deleting {len(broadcast_messages)} messages...\n"
                f"⚡ Processing at maximum speed...",
                parse_mode="Markdown"
            )
            
            # Fast deletion without progress updates
            deleted_count = 0
            failed_count = 0
            
            for msg in broadcast_messages:
                try:
                    result = bot.delete_message(msg['channel_id'], msg['message_id'])
                    if result:
                        deleted_count += 1
                    else:
                        failed_count += 1
                except:
                    failed_count += 1
            
            # Clear broadcast history
            broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
            
            # Final result
            result_text = f"""
🛑 **Instant Stop All - COMPLETED!**

⚡ **Ultra-Fast Results:**
• ✅ **Messages Deleted:** `{deleted_count}`
• ❌ **Failed:** `{failed_count}`
• ⏹ **Reposts Stopped:** ✅
• 📋 **History Cleared:** ✅
• ⚡ **Speed:** Instant

🎯 **All broadcasts stopped and deleted instantly!**
            """
            bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")

        elif call.data == "add_channel":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ Single Channel", callback_data="add_single_channel"),
                types.InlineKeyboardButton("📋 Bulk Add Channels", callback_data="add_bulk_channels"),
            )
            bot.send_message(
                user_id, 
                "➕ **Add Channels**\n\nChoose how you want to add channels:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "add_single_channel":
            bot_state.broadcast_state[user_id] = {"step": "add_single_channel"}
            bot.send_message(user_id, "➕ Send channel ID (e.g., -1001234567890):")

        elif call.data == "add_bulk_channels":
            bot_state.broadcast_state[user_id] = {"step": "bulk_add_channels"}
            bot.send_message(
                user_id,
                "📋 **Bulk Add Channels**\n\n"
                "Send channel IDs in this format:\n\n"
                "```\n"
                "-1002334441744\n"
                "-1002070181214\n"
                "-1002203225057\n"
                "-1002431437495\n"
                "```\n\n"
                "**Or:**\n\n"
                "```\n"
                "-1002334441744, -1002070181214, -1002203225057\n"
                "```\n\n"
                "⚠️ **Maximum:** 100 channels at once",
                parse_mode="Markdown"
            )

        elif call.data == "my_channels":
            channels = broadcast_bot.get_all_channels(user_id)
            if channels:
                channels_text = "📋 **Your Channels:**\n\n"
                for i, ch in enumerate(channels, 1):
                    try:
                        chat_info = bot.get_chat(ch["channel_id"])
                        channels_text += f"{i}. **{chat_info.title}**\n   `{ch['channel_id']}`\n\n"
                    except:
                        channels_text += f"{i}. **Unknown Channel**\n   `{ch['channel_id']}`\n\n"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🗑 Remove Channel", callback_data="remove_channel"))
                bot.send_message(user_id, channels_text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(user_id, "❌ No channels found! Add channels first.")

        elif call.data == "find_channels":
            bot.send_message(user_id, "🔍 **Find Channels**\n\nForward a message from any channel to get its ID.")

        elif call.data == "user_analytics":
            analytics = broadcast_bot.get_user_analytics(user_id)
            stats_text = f"""
📊 **Your Analytics**

**👤 Profile:**
• User ID: `{user_id}`
• Member Since: `{analytics.get('member_since', 'Unknown')}`
• Last Active: `{analytics.get('last_active', 'Now')}`

**📈 Usage Stats:**
• Total Channels: `{analytics.get('total_channels', 0)}`
• Total Broadcasts: `{analytics.get('total_broadcasts', 0)}`
• Recent Broadcasts: `{analytics.get('recent_broadcasts', 0)} (7 days)`

**💎 Subscription:**
• Type: `{analytics.get('subscription_type', 'Free').title()}`
• Status: {'🟢 Active' if broadcast_bot.is_premium(user_id) else '🔶 Free'}
            """
            bot.send_message(user_id, stats_text, parse_mode="Markdown")

        elif call.data == "schedule_broadcast":
            bot.send_message(user_id, "📅 **Scheduled Broadcast**\n\nThis feature is coming soon!")

        elif call.data == "show_history":
            messages = broadcast_bot.get_broadcast_messages(user_id, 10)
            if messages:
                history_text = "📜 **Recent Broadcast History:**\n\n"
                for i, msg in enumerate(messages[:5], 1):
                    history_text += f"{i}. **{msg['message_type'].title()}**\n   Channel: `{msg['channel_id']}`\n   Time: `{msg['timestamp'].strftime('%H:%M:%S')}`\n\n"
                bot.send_message(user_id, history_text, parse_mode="Markdown")
            else:
                bot.send_message(user_id, "❌ No broadcast history found!")

        elif call.data == "user_settings":
            settings_text = f"""
⚙️ **User Settings**

**🔧 Current Settings:**
• Max Channels: `{MAX_CHANNELS_PER_USER}`
• Broadcast Delay: `{BROADCAST_DELAY}s`
• Auto Delete Options: Available
• Auto Repost Options: Available

**💎 Premium Features:**
• Double Channel Limit
• Advanced Analytics
• Priority Support
            """
            bot.send_message(user_id, settings_text, parse_mode="Markdown")

        elif call.data == "admin_panel" and broadcast_bot.is_admin(user_id):
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📊 System Analytics", callback_data="admin_analytics"),
                types.InlineKeyboardButton("👥 User Management", callback_data="admin_users"),
                types.InlineKeyboardButton("🔧 System Settings", callback_data="admin_settings"),
                types.InlineKeyboardButton("📋 Broadcast Logs", callback_data="admin_logs"),
                types.InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart"),
                types.InlineKeyboardButton("❌ Close Panel", callback_data="admin_close"),
            )
            bot.send_message(
                user_id,
                "🔧 **Admin Panel**\n\nSelect an option:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "admin_analytics" and broadcast_bot.is_admin(user_id):
            today = datetime.now().strftime('%Y-%m-%d')
            analytics = broadcast_bot.analytics_col.find_one({"date": today})
            
            if analytics:
                admin_stats = f"""
🔧 **System Analytics - {today}**

**📊 Today's Stats:**
• Total Broadcasts: `{analytics.get('total_broadcasts', 0)}`
• Messages Sent: `{analytics.get('total_messages_sent', 0)}`
• Active Users: `{broadcast_bot.users_col.count_documents({'last_active': {'$gte': datetime.now() - timedelta(days=1)}})}`
• New Channels: `{analytics.get('new_channels_added', 0)}`
• Auto Reposts: `{analytics.get('auto_reposts', 0)}`
• Auto Deletes: `{analytics.get('auto_deletes', 0)}`
• Failed Broadcasts: `{analytics.get('failed_broadcasts', 0)}`

**📈 Overall Stats:**
• Total Users: `{broadcast_bot.users_col.count_documents({})}`
• Total Channels: `{broadcast_bot.channels_col.count_documents({})}`
• Premium Users: `{broadcast_bot.users_col.count_documents({'is_premium': True})}`
                """
                bot.send_message(user_id, admin_stats, parse_mode="Markdown")
            else:
                bot.send_message(user_id, "❌ No analytics data found!")

        elif call.data == "admin_users" and broadcast_bot.is_admin(user_id):
            total_users = broadcast_bot.users_col.count_documents({})
            active_users = broadcast_bot.users_col.count_documents({'last_active': {'$gte': datetime.now() - timedelta(days=1)}})
            premium_users = broadcast_bot.users_col.count_documents({'is_premium': True})
            expired_premium = len(broadcast_bot.get_expired_premium_users())
            
            users_text = f"""
👥 **User Management**

**📊 User Statistics:**
• Total Users: `{total_users}`
• Active Users (24h): `{active_users}`
• Premium Users: `{premium_users}`
• Expired Premium: `{expired_premium}`
• Free Users: `{total_users - premium_users}`

**🔧 Owner Actions:**
• Make users premium (Owner Only)
• Remove premium access (Owner Only)
• View premium statistics
            """
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            if str(user_id) == OWNER_ID:
                markup.add(
                    types.InlineKeyboardButton("💎 Make Premium", callback_data="admin_make_premium"),
                    types.InlineKeyboardButton("🗑 Remove Premium", callback_data="admin_remove_premium"),
                )
            markup.add(
                types.InlineKeyboardButton("📊 Premium Stats", callback_data="admin_premium_stats"),
            )
            bot.send_message(user_id, users_text, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "admin_settings" and broadcast_bot.is_admin(user_id):
            settings_text = f"""
🔧 **System Settings**

**⚙️ Current Configuration:**
• BOT_TOKEN: ✅ Configured
• MONGO_URL: ✅ Connected
• MAX_CHANNELS_PER_USER: `{MAX_CHANNELS_PER_USER}`
• BROADCAST_DELAY: `{BROADCAST_DELAY}s`
• AUTO_DELETE_OPTIONS: Available
• AUTO_REPOST_OPTIONS: Available

**🔧 System Status:**
• Bot: ✅ Online
• Database: ✅ Connected
• Analytics: ✅ Active
            """
            bot.send_message(user_id, settings_text, parse_mode="Markdown")

        elif call.data == "admin_logs" and broadcast_bot.is_admin(user_id):
            bot.send_message(user_id, "📋 **Broadcast Logs**\n\nCheck bot.log file for detailed logs.")

        elif call.data == "admin_restart" and broadcast_bot.is_admin(user_id):
            bot.send_message(user_id, "🔄 **Restarting Bot...**\n\nBot will restart in 3 seconds.")
            time.sleep(3)
            os._exit(0)

        elif call.data == "admin_close" and broadcast_bot.is_admin(user_id):
            bot.send_message(user_id, "❌ **Admin Panel Closed**")

        elif call.data == "remove_channel":
            channels = broadcast_bot.get_all_channels(user_id)
            if channels:
                markup = types.InlineKeyboardMarkup(row_width=1)
                for ch in channels[:10]:  # Limit to 10 channels
                    try:
                        chat_info = bot.get_chat(ch["channel_id"])
                        markup.add(types.InlineKeyboardButton(
                            f"🗑 {chat_info.title}", 
                            callback_data=f"remove_{ch['channel_id']}"
                        ))
                    except:
                        markup.add(types.InlineKeyboardButton(
                            f"🗑 Unknown Channel", 
                            callback_data=f"remove_{ch['channel_id']}"
                        ))
                bot.send_message(user_id, "🗑 **Select channel to remove:**", reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(user_id, "❌ No channels to remove!")

        elif call.data.startswith("remove_") and broadcast_bot.is_admin(user_id):
            channel_id = int(call.data.replace("remove_", ""))
            if broadcast_bot.remove_channel(channel_id, user_id):
                bot.send_message(user_id, f"✅ Channel `{channel_id}` removed successfully!", parse_mode="Markdown")
            else:
                bot.send_message(user_id, f"❌ Failed to remove channel `{channel_id}`", parse_mode="Markdown")

        elif call.data == "get_premium":
            premium_text = f"""
💎 **Premium Subscription**

🔑 **Your User ID:** `{user_id}`

💰 **Premium Plans:**
• **1 Month:** ₹299
• **3 Months:** ₹799  
• **6 Months:** ₹1499
• **1 Year:** ₹2499

💳 **Payment Methods:**
• UPI: owner@example
• Paytm: 9876543210
• PhonePe: 9876543210

👑 **Owner Only Activation:**
• Only bot owner can activate premium
• Contact owner directly: @{OWNER_ID}
• No admin activation allowed

⚠️ **After Payment:**
1. Send payment screenshot to owner
2. Share your User ID: `{user_id}`
3. Owner will activate premium within 5 minutes

🔒 **Security:** Premium activation is owner-controlled only!
            """
            bot.send_message(user_id, premium_text, parse_mode="Markdown")

        elif call.data == "contact_admin":
            contact_text = f"""
📞 **Contact Owner**

🔑 **Your User ID:** `{user_id}`

👑 **Owner Contact:** @{OWNER_ID}

💬 **Message Template:**
```
Hi Owner,
I want to get premium access for your bot.
My User ID: {user_id}
Please help me with payment details and activation.
```

⏰ **Response Time:** Within 5 minutes

🔒 **Note:** Only owner can activate premium access!
            """
            bot.send_message(user_id, contact_text, parse_mode="Markdown")

        elif call.data == "admin_make_premium" and broadcast_bot.is_admin(user_id):
            if str(user_id) != OWNER_ID:
                bot.send_message(
                    user_id,
                    "🔒 **Owner Only Feature!**\n\nOnly the bot owner can activate premium users.",
                    parse_mode="Markdown"
                )
                return
                
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("1 Month", callback_data="premium_30"),
                types.InlineKeyboardButton("3 Months", callback_data="premium_90"),
                types.InlineKeyboardButton("6 Months", callback_data="premium_180"),
                types.InlineKeyboardButton("1 Year", callback_data="premium_365"),
            )
            bot.send_message(
                user_id,
                "💎 **Owner Premium Activation**\n\nSend user ID to make premium:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data.startswith("premium_") and broadcast_bot.is_admin(user_id):
            if str(user_id) != OWNER_ID:
                bot.send_message(
                    user_id,
                    "🔒 **Owner Only Feature!**\n\nOnly the bot owner can activate premium users.",
                    parse_mode="Markdown"
                )
                return
                
            days = int(call.data.replace("premium_", ""))
            bot_state.broadcast_state[user_id] = {"step": "waiting_user_id", "premium_days": days}
            bot.send_message(
                user_id,
                f"💎 **Owner Premium Activation**\n\nSend the user ID to make premium for {days} days:",
                parse_mode="Markdown"
            )

        elif call.data == "admin_remove_premium" and broadcast_bot.is_admin(user_id):
            if str(user_id) != OWNER_ID:
                bot.send_message(
                    user_id,
                    "🔒 **Owner Only Feature!**\n\nOnly the bot owner can remove premium access.",
                    parse_mode="Markdown"
                )
                return
            bot_state.broadcast_state[user_id] = {"step": "waiting_user_id_remove"}
            bot.send_message(user_id, "🗑 **Remove Premium**\n\nSend the user ID to remove premium:")

        elif call.data == "admin_premium_stats" and broadcast_bot.is_admin(user_id):
            premium_users = broadcast_bot.get_premium_users()
            expired_users = broadcast_bot.get_expired_premium_users()
            
            stats_text = f"""
📊 **Premium Statistics**

**💎 Active Premium Users:** `{len(premium_users)}`
**⏰ Expired Premium Users:** `{len(expired_users)}`

**📈 Revenue Estimation:**
• 1 Month Plans: ₹{len(premium_users) * 299}
• 3 Month Plans: ₹{len(premium_users) * 799}
• 6 Month Plans: ₹{len(premium_users) * 1499}
• 1 Year Plans: ₹{len(premium_users) * 2499}

**🔧 Quick Actions:**
• Make users premium
• Remove premium access
• View detailed analytics
            """
            bot.send_message(user_id, stats_text, parse_mode="Markdown")

        elif call.data == "cleanup_all_messages":
            if not (broadcast_bot.is_premium(user_id) or broadcast_bot.is_admin(user_id)):
                bot.answer_callback_query(call.id, "🔒 Premium Required!")
                return
                
            # Delete all broadcast messages
            deleted_count = 0
            failed_count = 0
            
            try:
                # Get all broadcast messages for this user
                broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 1000)
                
                status_msg = bot.send_message(
                    user_id,
                    f"🗑 **Deleting {len(broadcast_messages)} messages...**\n\n⏳ Please wait...",
                    parse_mode="Markdown"
                )
                
                for i, msg in enumerate(broadcast_messages):
                    try:
                        result = bot.delete_message(msg['channel_id'], msg['message_id'])
                        if result:
                            deleted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Failed to delete message {msg['message_id']} from {msg['channel_id']}: {e}")
                    
                    # Update progress every 10 messages
                    if (i + 1) % 10 == 0:
                        try:
                            bot.edit_message_text(
                                f"🗑 **Deleting Messages Progress**\n\n"
                                f"✅ Deleted: {deleted_count}\n"
                                f"❌ Failed: {failed_count}\n"
                                f"📊 Progress: {i + 1}/{len(broadcast_messages)}",
                                user_id, status_msg.message_id,
                                parse_mode="Markdown"
                            )
                        except:
                            pass
                
                # Clear broadcast history from database
                broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
                
                result_text = f"""
🗑 **Message Cleanup Completed!**

📊 **Results:**
• ✅ Messages Deleted: `{deleted_count}`
• ❌ Failed Deletions: `{failed_count}`
• 📋 History Cleared: ✅

✅ All broadcast messages have been removed from channels.
                """
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Error in cleanup_all_messages: {e}")
                bot.send_message(user_id, "❌ Error during message cleanup process")

        elif call.data == "cleanup_stop_reposts":
            if not (broadcast_bot.is_premium(user_id) or broadcast_bot.is_admin(user_id)):
                bot.answer_callback_query(call.id, "🔒 Premium Required!")
                return
                
            # Stop all reposts
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
                
                bot.send_message(
                    user_id, 
                    "⏹ **All Auto Reposts Stopped!**\n\n✅ All repost cycles have been terminated.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(user_id, "⚠️ No active auto reposts found.")

        elif call.data == "cleanup_everything":
            if not (broadcast_bot.is_premium(user_id) or broadcast_bot.is_admin(user_id)):
                bot.answer_callback_query(call.id, "🔒 Premium Required!")
                return
                
            # Stop all reposts
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
            
            # Delete all broadcast messages
            deleted_count = 0
            failed_count = 0
            
            try:
                # Get all broadcast messages for this user
                broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 1000)
                
                status_msg = bot.send_message(
                    user_id,
                    f"🧹 **Complete Cleanup in Progress...**\n\n"
                    f"🗑 Deleting {len(broadcast_messages)} messages\n"
                    f"⏹ Stopping all reposts\n\n"
                    f"⏳ Please wait...",
                    parse_mode="Markdown"
                )
                
                for i, msg in enumerate(broadcast_messages):
                    try:
                        result = bot.delete_message(msg['channel_id'], msg['message_id'])
                        if result:
                            deleted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Failed to delete message {msg['message_id']} from {msg['channel_id']}: {e}")
                    
                    # Update progress every 10 messages
                    if (i + 1) % 10 == 0:
                        try:
                            bot.edit_message_text(
                                f"🧹 **Complete Cleanup Progress**\n\n"
                                f"🗑 Messages Deleted: {deleted_count}\n"
                                f"❌ Failed: {failed_count}\n"
                                f"⏹ Reposts Stopped: ✅\n"
                                f"📊 Progress: {i + 1}/{len(broadcast_messages)}",
                                user_id, status_msg.message_id,
                                parse_mode="Markdown"
                            )
                        except:
                            pass
                
                # Clear broadcast history from database
                broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
                
                result_text = f"""
🧹 **Complete Cleanup Finished!**

📊 **Results:**
• ✅ Messages Deleted: `{deleted_count}`
• ❌ Failed Deletions: `{failed_count}`
• ⏹ Reposts Stopped: ✅
• 📋 History Cleared: ✅

✅ Complete cleanup completed successfully!
                """
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Error in cleanup_everything: {e}")
                bot.send_message(user_id, "❌ Error during complete cleanup process")

        elif call.data == "cleanup_cancel":
            bot.send_message(user_id, "❌ Cleanup operation cancelled.")

        elif call.data == "cleanup_menu":
            if not (broadcast_bot.is_premium(user_id) or broadcast_bot.is_admin(user_id)):
                bot.answer_callback_query(call.id, "🔒 Premium Required!")
                return
                
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🗑 Delete All Messages", callback_data="cleanup_all_messages"),
                types.InlineKeyboardButton("⏹ Stop All Reposts", callback_data="cleanup_stop_reposts"),
                types.InlineKeyboardButton("🗑 Delete & Stop All", callback_data="cleanup_everything"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cleanup_cancel"),
            )
            
            cleanup_text = f"""
🧹 **Auto Cleanup System** ⚡

**🔧 Available Actions:**
• 🗑 **Delete All Messages** - Remove all broadcast messages from channels
• ⏹ **Stop All Reposts** - Stop all active auto reposts
• 🗑 **Delete & Stop All** - Complete cleanup (messages + reposts)

**⚠️ Warning:** These actions cannot be undone!

**💡 Choose an option:**
            """
            bot.send_message(user_id, cleanup_text, reply_markup=markup, parse_mode="Markdown")

        if state:
            bot_state.broadcast_state[user_id] = state

    except Exception as e:
        logger.error(f"Callback error: {e}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Advanced message handler"""
    user_id = message.chat.id
    
    if not (broadcast_bot.is_authorized(user_id) or 
            broadcast_bot.is_premium(user_id) or 
            broadcast_bot.is_admin(user_id)):
        bot.send_message(user_id, "🚫 Access Denied! Contact admin.")
        return

    try:
        state = bot_state.broadcast_state.get(user_id)

        if state and state.get("step") == "waiting_msg":
            state["message"] = message
            state["step"] = "ask_formatting"
            
            # Show formatting options
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📝 Plain Text", callback_data="format_plain"),
                types.InlineKeyboardButton("🎨 Bold Text", callback_data="format_bold"),
                types.InlineKeyboardButton("📋 Italic Text", callback_data="format_italic"),
                types.InlineKeyboardButton("🔗 With Links", callback_data="format_links"),
                types.InlineKeyboardButton("📊 Code Format", callback_data="format_code"),
                types.InlineKeyboardButton("💬 Quote Style", callback_data="format_quote"),
                types.InlineKeyboardButton("📌 Sticky Note", callback_data="format_sticky"),
                types.InlineKeyboardButton("🎯 Highlight", callback_data="format_highlight"),
                types.InlineKeyboardButton("🚀 Skip Formatting", callback_data="format_skip")
            )
            
            bot.send_message(
                user_id, 
                "🎨 **Choose Message Formatting:**\n\n"
                "Select how you want your message to appear:\n\n"
                "• 📝 **Plain Text** - Simple text\n"
                "• 🎨 **Bold Text** - **Bold formatting**\n"
                "• 📋 **Italic Text** - *Italic formatting*\n"
                "• 🔗 **With Links** - Clickable links\n"
                "• 📊 **Code Format** - `Code blocks`\n"
                "• 💬 **Quote Style** - > Quoted text\n"
                "• 📌 **Sticky Note** - 📌 Pinned style\n"
                "• 🎯 **Highlight** - ⚡ Highlighted\n"
                "• 🚀 **Skip Formatting** - Continue without changes",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        # Handle custom auto delete time input
        if state and state.get("step") == "ask_autodelete_time":
            try:
                minutes = int(message.text.strip())
                if minutes < 1:
                    bot.send_message(user_id, "⚠️ **Invalid Time**\n\nPlease enter a number greater than 0.")
                    return
                if minutes > 43200:  # 30 days
                    bot.send_message(user_id, "⚠️ **Time Too Long**\n\nMaximum delete time is 30 days (43200 minutes).")
                    return
                    
                state["delete_time"] = minutes
                
                time_display = f"{minutes} minutes" if minutes < 60 else f"{minutes//60} hours {minutes%60} minutes" if minutes % 60 else f"{minutes//60} hours"
                bot.send_message(
                    user_id,
                    f"✅ **Auto delete set to {time_display}**\n\n⏳ Starting broadcast...",
                    parse_mode="Markdown"
                )
                finish_advanced_broadcast(user_id)
            except ValueError:
                bot.send_message(user_id, "⚠️ **Invalid Input**\n\nPlease enter a valid number (minutes).")
            return

        # Handle admin premium management
        if state and state.get("step") == "waiting_user_id" and broadcast_bot.is_admin(user_id):
            try:
                target_user_id = int(message.text.strip())
                premium_days = state.get("premium_days", 30)
                
                if broadcast_bot.make_premium(target_user_id, premium_days):
                    bot.send_message(
                        user_id,
                        f"✅ **Owner Premium Activation Successful!**\n\n"
                        f"**User ID:** `{target_user_id}`\n"
                        f"**Duration:** {premium_days} days\n"
                        f"**Status:** Active\n"
                        f"**👑 Activated By:** Owner",
                        parse_mode="Markdown"
                    )
                    
                    # Notify the user
                    try:
                        bot.send_message(
                            target_user_id,
                            f"🎉 **Premium Activated by Owner!**\n\n"
                            f"✅ Your premium access has been activated!\n"
                            f"⏰ **Duration:** {premium_days} days\n"
                            f"🔓 **Access:** Full bot features unlocked\n"
                            f"👑 **Activated By:** Bot Owner\n\n"
                            f"Use /start to access the bot!",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                else:
                    bot.send_message(user_id, f"❌ Failed to activate premium for user `{target_user_id}`", parse_mode="Markdown")
                
                bot_state.broadcast_state.pop(user_id, None)
            except ValueError:
                bot.send_message(user_id, "⚠️ Invalid user ID. Please enter a valid number.")
            return

        elif state and state.get("step") == "waiting_user_id_remove" and broadcast_bot.is_admin(user_id):
            try:
                target_user_id = int(message.text.strip())
                
                if broadcast_bot.remove_premium(target_user_id):
                    bot.send_message(
                        user_id,
                        f"✅ **Owner Premium Removal Successful!**\n\n"
                        f"**User ID:** `{target_user_id}`\n"
                        f"**Status:** Premium access revoked\n"
                        f"**👑 Removed By:** Owner",
                        parse_mode="Markdown"
                    )
                    
                    # Notify the user
                    try:
                        bot.send_message(
                            target_user_id,
                            f"⚠️ **Premium Removed by Owner**\n\n"
                            f"❌ Your premium access has been removed.\n"
                            f"🔒 **Access:** Bot features locked\n"
                            f"👑 **Removed By:** Bot Owner\n\n"
                            f"Contact owner to renew premium!",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                else:
                    bot.send_message(user_id, f"❌ Failed to remove premium from user `{target_user_id}`", parse_mode="Markdown")
                
                bot_state.broadcast_state.pop(user_id, None)
            except ValueError:
                bot.send_message(user_id, "⚠️ Invalid user ID. Please enter a valid number.")
            return

        # Handle channel ID input and Telegram links
        if message.text:
            state = bot_state.broadcast_state.get(user_id, {})
            
            # Check if user is in bulk add mode
            if state.get("step") == "bulk_add_channels":
                # Handle bulk channel addition
                try:
                    # Parse channel IDs and links from different formats
                    channel_text = message.text.strip()
                    channel_ids = []
                    
                    # Extract Telegram links first
                    telegram_links = extract_telegram_links(channel_text)
                    for link in telegram_links:
                        channel_id = resolve_telegram_link(link)
                        if channel_id:
                            channel_ids.append(str(channel_id))
                    
                    # Split by newlines, commas, or spaces for direct IDs
                    if '\n' in channel_text:
                        # Format: -1001234567890\n-1001234567891
                        direct_ids = [line.strip() for line in channel_text.split('\n') if line.strip().startswith('-100')]
                        channel_ids.extend(direct_ids)
                    elif ',' in channel_text:
                        # Format: -1001234567890, -1001234567891
                        direct_ids = [ch.strip() for ch in channel_text.split(',') if ch.strip().startswith('-100')]
                        channel_ids.extend(direct_ids)
                    elif channel_text.startswith('-100'):
                        # Single channel ID
                        channel_ids.append(channel_text)
                    
                    # Remove duplicates
                    channel_ids = list(set(channel_ids))
                    
                    # Limit to 100 channels
                    if len(channel_ids) > 100:
                        bot.send_message(user_id, "⚠️ **Too Many Channels**\n\nMaximum 100 channels allowed at once.")
                        return
                    
                    # Process channels
                    success_count = 0
                    failed_count = 0
                    already_exists = 0
                    failed_channels = []
                    
                    status_msg = bot.send_message(
                        user_id,
                        f"📋 **Adding {len(channel_ids)} channels...**\n\n⏳ Please wait...",
                        parse_mode="Markdown"
                    )
                    
                    for i, ch_id_str in enumerate(channel_ids):
                        try:
                            ch_id = int(ch_id_str)
                            chat_info = bot.get_chat(ch_id)
                            
                            if broadcast_bot.add_channel(ch_id, user_id):
                                success_count += 1
                            else:
                                already_exists += 1
                                
                        except Exception as e:
                            failed_count += 1
                            failed_channels.append(ch_id_str)
                        
                        # Update progress every 10 channels
                        if (i + 1) % 10 == 0:
                            try:
                                bot.edit_message_text(
                                    f"📋 **Adding Channels Progress**\n\n"
                                    f"✅ Added: {success_count}\n"
                                    f"⚠️ Already Exists: {already_exists}\n"
                                    f"❌ Failed: {failed_count}\n"
                                    f"📊 Progress: {i + 1}/{len(channel_ids)}",
                                    user_id, status_msg.message_id,
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                    
                    # Final result
                    result_text = f"""
✅ **Bulk Channel Addition Completed!**

📊 **Results:**
• ✅ Successfully Added: `{success_count}`
• ⚠️ Already Exists: `{already_exists}`
• ❌ Failed: `{failed_count}`
• 📋 Total Processed: `{len(channel_ids)}`

🕐 **Time:** `{datetime.now().strftime('%H:%M:%S')}`
                    """
                    
                    if failed_channels:
                        failed_list = ', '.join(failed_channels[:5])
                        if len(failed_channels) > 5:
                            failed_list += f" and {len(failed_channels) - 5} more"
                        result_text += f"\n❌ **Failed Channels:**\n`{failed_list}`"
                    
                    try:
                        bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                    except:
                        bot.send_message(user_id, result_text, parse_mode="Markdown")
                    
                    # Clear bulk add state
                    bot_state.broadcast_state.pop(user_id, None)
                    
                except Exception as e:
                    bot.send_message(user_id, f"❌ **Bulk Add Error:** {e}")
                    bot_state.broadcast_state.pop(user_id, None)
                
            else:
                # Handle single channel addition (ID or link)
                try:
                    # Check if it's a Telegram link
                    telegram_links = extract_telegram_links(message.text)
                    if telegram_links:
                        # Handle as link
                        link = telegram_links[0]
                        channel_id = resolve_telegram_link(link)
                        if channel_id:
                            chat_info = bot.get_chat(channel_id)
                            if broadcast_bot.add_channel(channel_id, user_id):
                                bot.send_message(user_id, f"✅ Channel **{chat_info.title}** added from link!", parse_mode="Markdown")
                            else:
                                bot.send_message(user_id, f"⚠️ Channel already exists!")
                        else:
                            bot.send_message(user_id, f"❌ Could not resolve link: {link}")
                    elif message.text.startswith('-100'):
                        # Handle as direct channel ID
                        ch_id = int(message.text.strip())
                        chat_info = bot.get_chat(ch_id)
                        
                        if broadcast_bot.add_channel(ch_id, user_id):
                            bot.send_message(user_id, f"✅ Channel **{chat_info.title}** added!", parse_mode="Markdown")
                        else:
                            bot.send_message(user_id, f"⚠️ Channel already exists!")
                    else:
                        bot.send_message(user_id, f"❌ Invalid format! Use channel ID (-100...) or Telegram link")
                except Exception as e:
                    bot.send_message(user_id, f"❌ Error: {e}")

    except Exception as e:
        logger.error(f"Message handler error: {e}")

if __name__ == "__main__":
    logger.info("🚀 Advanced Broadcast Bot starting...")
    
    # Update analytics on startup
    broadcast_bot.update_analytics("active_users", 0)
    
    # Check if running on Heroku
    port = int(os.environ.get('PORT', 5000))
    
    try:
        if os.environ.get('PORT'):
            # Heroku deployment - use webhook
            logger.info("🌐 Starting on Heroku with webhook...")
            
            # Get app name from environment or use default
            app_name = os.environ.get('HEROKU_APP_NAME', 'your-app-name')
            webhook_url = f"https://{app_name}.herokuapp.com/webhook"
            
            try:
                bot.remove_webhook()
                bot.set_webhook(url=webhook_url)
                logger.info(f"✅ Webhook set to: {webhook_url}")
            except Exception as e:
                logger.error(f"❌ Failed to set webhook: {e}")
            
            # Start Flask server for webhook
            from flask import Flask, request
            
            app = Flask(__name__)
            
            @app.route('/webhook', methods=['POST'])
            def webhook():
                try:
                    update = types.Update.de_json(request.stream.read().decode('utf-8'))
                    bot.process_new_updates([update])
                    return 'ok', 200
                except Exception as e:
                    logger.error(f"Webhook error: {e}")
                    return 'error', 500
            
            @app.route('/')
            def home():
                return '🚀 Advanced Broadcast Bot is running!'
            
            app.run(host='0.0.0.0', port=port)
            
        else:
            # Local development - use polling
            logger.info("🏠 Starting locally with polling...")
            bot.infinity_polling(none_stop=True, timeout=60)
            
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        # Auto-restart logic could be added here
