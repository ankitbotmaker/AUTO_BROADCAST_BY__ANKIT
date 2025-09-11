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
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    client.admin.command('ping')
    db = client["advanced_broadcast_bot"]
    
    # Collections
    channels_col = db["channels"]
    broadcast_messages_col = db["broadcast_messages"]
    users_col = db["users"]
    scheduled_broadcasts_col = db["scheduled_broadcasts"]
    analytics_col = db["analytics"]
    settings_col = db["settings"]
    bot_messages_col = db["bot_messages"]
    
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    # Create a simple in-memory fallback
    logger.warning("Using fallback mode - some features may be limited")
    db = None
    channels_col = None
    broadcast_messages_col = None
    users_col = None
    scheduled_broadcasts_col = None
    analytics_col = None
    settings_col = None
    bot_messages_col = None

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

def html_escape(text: Optional[str]) -> str:
    """Escape text for safe HTML parse_mode rendering."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def send_html(chat_id: int, text: str, reply_markup: Optional[types.InlineKeyboardMarkup] = None):
    return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")

def send_html_photo(chat_id: int, photo: str, caption: str, reply_markup: Optional[types.InlineKeyboardMarkup] = None):
    return bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup, parse_mode="HTML")

def render_markdown_to_html(text: Optional[str]) -> str:
    """Lightweight conversion from simple Markdown to safe HTML (bold, code, blockquote)."""
    if not text:
        return ""

    original_text = str(text)

    # Collect placeholders to protect segments during escaping
    placeholders: Dict[str, str] = {}
    placeholder_index = 0

    def make_placeholder(kind: str, content: str) -> str:
        nonlocal placeholder_index
        key = f"__{kind.upper()}_{placeholder_index}__"
        placeholder_index += 1
        placeholders[key] = content
        return key

    # Inline code `...`
    def repl_code(m):
        return make_placeholder("CODE", m.group(1))

    code_pattern = re.compile(r"`([^`]+)`", re.DOTALL)
    stage = code_pattern.sub(repl_code, original_text)

    # Bold **...**
    def repl_bold(m):
        return make_placeholder("BOLD", m.group(1))

    bold_pattern = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
    stage = bold_pattern.sub(repl_bold, stage)

    # Line-level blockquotes starting with >
    lines = stage.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(">"):
            quote_content = line.strip()[1:].lstrip()
            lines[i] = make_placeholder("QUOTE", quote_content)
    stage = "\n".join(lines)

    # Escape everything else
    stage = html_escape(stage)

    # Restore placeholders as HTML tags (escape their inner text)
    for key, val in placeholders.items():
        safe_inner = html_escape(val)
        if key.startswith("__CODE_"):
            replacement = f"<code>{safe_inner}</code>"
        elif key.startswith("__BOLD_"):
            replacement = f"<b>{safe_inner}</b>"
        elif key.startswith("__QUOTE_"):
            replacement = f"<blockquote>{safe_inner}</blockquote>"
        else:
            replacement = safe_inner
        stage = stage.replace(key, replacement)

    return stage

# Monkey-patch TeleBot sending methods to auto-convert Markdown -> HTML for UI consistency
_orig_send_message = bot.send_message
_orig_edit_message_text = bot.edit_message_text
_orig_send_photo = bot.send_photo
_orig_send_video = bot.send_video
_orig_send_document = bot.send_document

def _patched_send_message(chat_id, text, *args, **kwargs):
    pm = kwargs.get("parse_mode")
    if pm == "Markdown":
        kwargs["parse_mode"] = "HTML"
        text = render_markdown_to_html(text)
    
    # Send the message
    result = _orig_send_message(chat_id, text, *args, **kwargs)
    
    # Track bot messages for later deletion (only for private chats)
    try:
        if hasattr(result, 'message_id') and result.message_id and str(chat_id).startswith('-') == False:
            track_bot_message(chat_id, result.message_id)
    except Exception as e:
        logger.warning(f"Failed to track bot message: {e}")
    
    return result

def _patched_edit_message_text(text, chat_id=None, message_id=None, *args, **kwargs):
    pm = kwargs.get("parse_mode")
    if pm == "Markdown":
        kwargs["parse_mode"] = "HTML"
        text = render_markdown_to_html(text)
    return _orig_edit_message_text(text, chat_id, message_id, *args, **kwargs)

def _patched_send_photo(chat_id, photo, *args, **kwargs):
    pm = kwargs.get("parse_mode")
    caption = kwargs.get("caption")
    if pm == "Markdown" and caption is not None:
        kwargs["parse_mode"] = "HTML"
        kwargs["caption"] = render_markdown_to_html(caption)
    return _orig_send_photo(chat_id, photo, *args, **kwargs)

def _patched_send_video(chat_id, video, *args, **kwargs):
    pm = kwargs.get("parse_mode")
    caption = kwargs.get("caption")
    if pm == "Markdown" and caption is not None:
        kwargs["parse_mode"] = "HTML"
        kwargs["caption"] = render_markdown_to_html(caption)
    return _orig_send_video(chat_id, video, *args, **kwargs)

def _patched_send_document(chat_id, document, *args, **kwargs):
    pm = kwargs.get("parse_mode")
    caption = kwargs.get("caption")
    if pm == "Markdown" and caption is not None:
        kwargs["parse_mode"] = "HTML"
        kwargs["caption"] = render_markdown_to_html(caption)
    return _orig_send_document(chat_id, document, *args, **kwargs)

bot.send_message = _patched_send_message
bot.edit_message_text = _patched_edit_message_text
bot.send_photo = _patched_send_photo
bot.send_video = _patched_send_video
bot.send_document = _patched_send_document

class AdvancedBroadcastBot:
    def __init__(self):
        self.db = db  # Add the main database reference
        self.channels_col = channels_col
        self.broadcast_messages_col = broadcast_messages_col
        self.users_col = users_col
        self.scheduled_broadcasts_col = scheduled_broadcasts_col
        self.analytics_col = analytics_col
        self.settings_col = settings_col
        
        # Initialize analytics only if MongoDB is available
        if self.analytics_col is not None:
            self.init_analytics()
        
        # Start background tasks only if MongoDB is available
        if self.scheduled_broadcasts_col is not None:
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
        logger.info("Starting background tasks...")
        threading.Thread(target=self.check_scheduled_broadcasts, daemon=True).start()
        logger.info("Background tasks started successfully")

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

    def save_broadcast_message(self, user_id: int, channel_id: int, message_id: int, broadcast_id: str, message_type: str = "broadcast"):
        """Save broadcast message details"""
        try:
            if self.broadcast_messages_col is not None:
                self.broadcast_messages_col.insert_one({
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "broadcast_id": broadcast_id,
                    "message_type": message_type,
                    "status": "active",
                    "created_at": datetime.now(),
                    "sent_at": datetime.now()
                })
            else:
                logger.warning("MongoDB not available - broadcast message not saved")
        except Exception as e:
            logger.error(f"Error saving broadcast message: {e}")

    def get_user_analytics(self, user_id: int) -> Dict:
        """Get user analytics and statistics"""
        try:
            # Get user data
            user_data = self.users_col.find_one({"user_id": user_id})
            
            # Get channel count
            channel_count = self.channels_col.count_documents({"user_id": user_id})
            
            # Get broadcast count
            broadcast_count = self.broadcast_messages_col.count_documents({"user_id": user_id})
            
            return {
                "total_channels": channel_count,
                "total_broadcasts": broadcast_count,
                "subscription_type": "Free"
            }
        except Exception as e:
            logger.error(f"Error getting user analytics for {user_id}: {e}")
            return {
                "total_channels": 0,
                "total_broadcasts": 0,
                "subscription_type": "Free"
            }

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    def is_authorized(self, user_id: int) -> bool:
        """Authorization disabled: all users are authorized."""
        return True

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
                        "total_broadcasts": 0
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error adding user: {e}")

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
        """Check and execute scheduled broadcasts and auto-deletes with enhanced monitoring"""
        logger.info("Starting scheduled tasks checker...")
        while True:
            try:
                now = datetime.now()
                
                # Check scheduled broadcasts
                scheduled = self.scheduled_broadcasts_col.find({
                    "scheduled_time": {"$lte": now},
                    "status": "pending",
                    "type": {"$ne": "auto_delete"}
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
                
                # Check auto-deletes with enhanced processing
                auto_deletes = list(self.scheduled_broadcasts_col.find({
                    "delete_at": {"$lte": now},
                    "status": "pending",
                    "type": "auto_delete"
                }))
                
                if auto_deletes:
                    logger.info(f"Processing {len(auto_deletes)} auto delete tasks...")
                    
                    for delete_task in auto_deletes:
                        try:
                            # Update attempt count
                            self.scheduled_broadcasts_col.update_one(
                                {"_id": delete_task["_id"]},
                                {"$inc": {"attempts": 1}, "$set": {"last_attempt": now}}
                            )
                            
                            success = execute_auto_delete(delete_task["channel_id"], delete_task["message_id"])
                            
                            if success:
                                status = "completed"
                                logger.info(f"Auto delete completed for message {delete_task['message_id']}")
                            else:
                                # Check if we should retry
                                attempts = delete_task.get("attempts", 0) + 1
                                if attempts < 3:  # Max 3 attempts
                                    status = "pending"
                                    logger.warning(f"Auto delete failed, will retry (attempt {attempts}/3)")
                                else:
                                    status = "failed"
                                    logger.error(f"Auto delete failed after {attempts} attempts")
                            
                            # Update status
                            self.scheduled_broadcasts_col.update_one(
                                {"_id": delete_task["_id"]},
                                {"$set": {"status": status}}
                            )
                        except Exception as e:
                            logger.error(f"Error executing auto delete: {e}")
                            self.scheduled_broadcasts_col.update_one(
                                {"_id": delete_task["_id"]},
                                {"$set": {"status": "failed", "error": str(e)}}
                            )
                
                # Clean up old completed/failed auto delete tasks (older than 7 days)
                cleanup_date = now - timedelta(days=7)
                cleanup_result = self.scheduled_broadcasts_col.delete_many({
                    "type": "auto_delete",
                    "created_at": {"$lt": cleanup_date},
                    "status": {"$in": ["completed", "failed", "already_deleted"]}
                })
                if cleanup_result.deleted_count > 0:
                    logger.info(f"Cleaned up {cleanup_result.deleted_count} old auto delete tasks")
                
                time.sleep(15)  # Check every 15 seconds for better responsiveness
            except Exception as e:
                logger.error(f"Error in scheduled tasks checker: {e}")
                time.sleep(30)


    def execute_scheduled_broadcast(self, broadcast_data):
        """Execute a scheduled broadcast"""
        try:
            # This would contain the logic to execute the broadcast
            # Implementation depends on how you store the message data
            pass
        except Exception as e:
            logger.error(f"Error executing scheduled broadcast: {e}")

    def get_broadcast_messages(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get broadcast messages for a user"""
        try:
            if self.broadcast_messages_col is not None:
                return list(self.broadcast_messages_col.find(
                    {"user_id": user_id}
                ).sort("sent_at", -1).limit(limit))
            else:
                logger.warning("MongoDB not available - returning empty broadcast messages list")
                return []
        except Exception as e:
            logger.error(f"Error getting broadcast messages for user {user_id}: {e}")
            return []

# Initialize broadcast bot
broadcast_bot = AdvancedBroadcastBot()

def extract_telegram_links(text: str) -> List[str]:
    """Extract Telegram channel/group links from text"""
    patterns = [
        r'(https?://t\.me/[a-zA-Z0-9_]+)',
        r'(@[a-zA-Z0-9_]+)',
        r'(t\.me/[a-zA-Z0-9_]+)',
        r'(https?://telegram\.me/[a-zA-Z0-9_]+)'
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
            # Extract username preserving underscores
            username = link.split('/')[-1]
            # Ensure username is properly formatted
            if not username.startswith('@'):
                username = f"@{username}"
            chat_info = bot.get_chat(username)
            return chat_info.id
        elif link.startswith('https://telegram.me/'):
            # Extract username preserving underscores
            username = link.split('/')[-1]
            # Ensure username is properly formatted
            if not username.startswith('@'):
                username = f"@{username}"
            chat_info = bot.get_chat(username)
            return chat_info.id
        else:
            # Try as username (add @ if not present)
            if not link.startswith('@'):
                link = f"@{link}"
            chat_info = bot.get_chat(link)
            return chat_info.id
    except Exception as e:
        logger.error(f"Error resolving link {link}: {e}")
        return None

def auto_add_telegram_links(user_id: int, text: str) -> List[Dict]:
    """Automatically add Telegram links as channels"""
    added_channels = []
    links = extract_telegram_links(text)
    
    for link in links:
        try:
            channel_id = resolve_telegram_link(link)
            if channel_id:
                # Check if channel already exists
                existing = broadcast_bot.channels_col.find_one({
                    "user_id": user_id,
                    "channel_id": channel_id
                })
                
                if not existing:
                    # Get channel info
                    chat_info = bot.get_chat(channel_id)
                    channel_name = chat_info.title or chat_info.username or f"Channel {channel_id}"
                    
                    # Add channel to database
                    broadcast_bot.add_channel(
                        channel_id=channel_id,
                        user_id=user_id
                    )
                    
                    added_channels.append({
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "username": chat_info.username
                    })
                    
                    logger.info(f"Auto-added channel {channel_name} ({channel_id}) for user {user_id}")
                else:
                    logger.info(f"Channel {channel_id} already exists for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error auto-adding channel {link}: {e}")
    
    return added_channels

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
                logger.info(f"Scheduling auto delete for message {sent.message_id} in channel {channel_id} after {delete_time} minutes")
                schedule_auto_delete(channel_id, sent.message_id, delete_time)
                
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

        # Send initial status with loading animation
        loading_text = f"""
<b>📡 BROADCAST INITIALIZATION</b>

<blockquote><b>🚀 Starting Broadcast Process</b>
• <b>Channels:</b> {len(channels)}
• <b>Status:</b> {create_loading_animation(0)}
• <b>Progress:</b> {create_progress_bar(0, len(channels))}</blockquote>

<b>⚡ Processing channels...</b>
        """
        status_msg = send_loading_message(chat_id, loading_text)

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
                
                # Update progress every 5 channels with animation
                if (i + 1) % 5 == 0:
                    try:
                        progress_text = f"""
<b>📡 BROADCAST IN PROGRESS</b>

<blockquote><b>🚀 Broadcasting Status</b>
• <b>Sent:</b> {sent_count} ✅
• <b>Failed:</b> {failed_count} ❌
• <b>Status:</b> {create_loading_animation((i + 1) // 5)}
• <b>Progress:</b> {create_progress_bar(i + 1, len(channels))}</blockquote>

<b>⚡ Processing: {i + 1}/{len(channels)} channels</b>
                        """
                        send_loading_message(chat_id, progress_text, status_msg.message_id)
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

        # Final result message with enhanced UI
        result_text = f"""
<b>🎉 BROADCAST COMPLETED!</b>

<blockquote><b>📊 BROADCAST RESULTS</b>
• <b>Sent:</b> {sent_count} ✅
• <b>Failed:</b> {failed_count} ❌
• <b>Total Channels:</b> {len(channels)}
• <b>Success Rate:</b> {int((sent_count / len(channels)) * 100) if len(channels) > 0 else 0}%
• <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}</blockquote>

<b>⚙️ BROADCAST SETTINGS</b>
<blockquote>• <b>Auto Repost:</b> {'✅' if repost_time else '❌'} {f'({repost_time} min)' if repost_time else ''}
• <b>Auto Delete:</b> {'✅' if delete_time else '❌'} {f'({delete_time} min)' if delete_time else ''}
• <b>Broadcast ID:</b> <code>{broadcast_id}</code></blockquote>

<b>🚀 {create_loading_animation(4)}</b>
        """
        
        if failed_channels:
            failed_list = ', '.join(failed_channels[:5])
            if len(failed_channels) > 5:
                failed_list += f" and {len(failed_channels) - 5} more"
            result_text += f"\n❌ **Failed Channels:**\n`{failed_list}`"

        try:
            bot.edit_message_text(result_text, chat_id, status_msg.message_id, parse_mode="Markdown")
            # Auto-delete the result message after 10 seconds
            threading.Timer(10, lambda: delete_message_safe(chat_id, status_msg.message_id)).start()
        except:
            sent_msg = bot.send_message(chat_id, result_text, parse_mode="Markdown")
            # Auto-delete the result message after 10 seconds
            if sent_msg:
                threading.Timer(10, lambda: delete_message_safe(chat_id, sent_msg.message_id)).start()

        # Start auto repost if enabled
        if repost_time:
            repost_text = f"""
<b>🔄 AUTO REPOST ACTIVATED!</b>

<blockquote><b>⚙️ REPOST CONFIGURATION</b>
• <b>Interval:</b> {repost_time} minutes
• <b>Auto Delete:</b> {'✅' if delete_time else '❌'}
• <b>Channels:</b> {sent_count}
• <b>Status:</b> {create_loading_animation(1)}</blockquote>

<b>💡 Use ⏹ Stop Repost button to cancel</b>
            """
            repost_msg = bot.send_message(chat_id, repost_text, parse_mode="HTML")
            # Auto-delete repost message after 15 seconds
            if repost_msg:
                threading.Timer(15, lambda: delete_message_safe(chat_id, repost_msg.message_id)).start()
            
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
        logger.error(f"Error in finish_broadcast: {e}")
        bot.send_message(chat_id, "❌ An error occurred during broadcast")
        # Clear active broadcast on error
        bot_state.active_broadcasts.pop(chat_id, None)



def create_loading_animation(step: int = 0) -> str:
    """Create animated loading interface"""
    animations = [
        "⏳ Loading...",
        "🔄 Processing...",
        "⚡ Working...",
        "🚀 Almost done...",
        "✅ Complete!"
    ]
    
    dots = "●" * (step % 4) + "○" * (4 - (step % 4))
    return f"{animations[step % len(animations)]} {dots}"

def create_progress_bar(current: int, total: int, width: int = 10) -> str:
    """Create a visual progress bar"""
    if total == 0:
        return "━" * width
    
    filled = int((current / total) * width)
    empty = width - filled
    
    bar = "█" * filled + "░" * empty
    percentage = int((current / total) * 100)
    
    return f"`{bar}` {percentage}%"

def send_loading_message(chat_id: int, text: str, message_id: int = None) -> int:
    """Send or update a loading message with animation"""
    try:
        if message_id:
            # Update existing message
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML")
            return message_id
        else:
            # Send new message
            sent = bot.send_message(chat_id, text, parse_mode="HTML")
            return sent.message_id
    except Exception as e:
        logger.error(f"Error sending loading message: {e}")
        return None

def show_typing_indicator(chat_id: int, duration: int = 3):
    """Show typing indicator for specified duration"""
    try:
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(duration)
    except Exception as e:
        logger.error(f"Error showing typing indicator: {e}")

def create_channel_addition_ui(channel_count: int, success_count: int, failed_count: int) -> str:
    """Create UI for channel addition process"""
    return f"""
<b>📋 CHANNEL ADDITION PROGRESS</b>

<blockquote><b>📊 ADDITION STATUS</b>
• <b>Total:</b> {channel_count}
• <b>Added:</b> {success_count} ✅
• <b>Failed:</b> {failed_count} ❌
• <b>Progress:</b> {create_progress_bar(success_count + failed_count, channel_count)}
• <b>Status:</b> {create_loading_animation((success_count + failed_count) // 5)}</blockquote>

<b>⚡ Processing channels...</b>
    """

def send_and_delete(message, text, parse_mode="Markdown", reply_markup=None, delete_after=5):
    """Send message and auto-delete after specified seconds"""
    try:
        sent_msg = bot.send_message(
            message.chat.id,
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        
        # Auto-delete after specified time
        if delete_after > 0:
            threading.Timer(delete_after, lambda: delete_message_safe(message.chat.id, sent_msg.message_id)).start()
        
        return sent_msg
    except Exception as e:
        logger.error(f"Error in send_and_delete: {e}")
        return None

def delete_message_safe(chat_id: int, message_id: int):
    """Safely delete message with error handling"""
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Error deleting message {message_id} from {chat_id}: {e}")

def schedule_auto_delete(chat_id: int, msg_id: int, delete_time: int):
    """Schedule auto delete with enhanced monitoring and immediate execution for short times"""
    try:
        delete_at = datetime.now() + timedelta(minutes=delete_time)
        
        # Store in MongoDB for persistence across bot restarts
        auto_delete_data = {
            "channel_id": chat_id,
            "message_id": msg_id,
            "delete_at": delete_at,
            "created_at": datetime.now(),
            "status": "pending",
            "delete_time_minutes": delete_time,
            "attempts": 0,
            "last_attempt": None,
            "error_count": 0
        }
        
        # Use scheduled_broadcasts collection for simplicity
        if broadcast_bot.scheduled_broadcasts_col is not None:
            broadcast_bot.scheduled_broadcasts_col.insert_one({
                **auto_delete_data,
                "type": "auto_delete"
            })
        else:
            logger.warning("MongoDB not available - auto delete will not persist across restarts")
        
        logger.info(f"Auto delete scheduled: {msg_id} from {chat_id} at {delete_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # For very short times (5 minutes or less), also set immediate timer
        if delete_time <= 5:
            threading.Timer(delete_time * 60, lambda: execute_auto_delete(chat_id, msg_id)).start()
            logger.info(f"Immediate timer set for {delete_time} minute auto delete")
        
    except Exception as e:
        logger.error(f"Error scheduling auto delete: {e}")

def execute_auto_delete(chat_id: int, msg_id: int):
    """Execute auto delete with enhanced retry logic and better error handling"""
    max_retries = 5
    retry_delays = [1, 2, 3, 5, 8]  # Progressive delays
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Auto delete attempt {attempt + 1}/{max_retries} for message {msg_id} from {chat_id}")
            
            result = bot.delete_message(chat_id, msg_id)
            if result:
                logger.info(f"Auto deleted message {msg_id} from {chat_id}")
                broadcast_bot.update_analytics("auto_deletes")
                
                # Update message status
                if broadcast_bot.broadcast_messages_col is not None:
                    broadcast_bot.broadcast_messages_col.update_one(
                        {"channel_id": chat_id, "message_id": msg_id},
                        {"$set": {"status": "deleted", "deleted_at": datetime.now(), "delete_attempts": attempt + 1}}
                    )
                return True
            else:
                logger.warning(f"Delete returned False for message {msg_id} from {chat_id}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle different error types
            if "message to delete not found" in error_msg or "message not found" in error_msg:
                logger.info(f"Message {msg_id} from {chat_id} already deleted or not found")
                # Update message status as already deleted
                broadcast_bot.broadcast_messages_col.update_one(
                    {"channel_id": chat_id, "message_id": msg_id},
                    {"$set": {"status": "already_deleted", "deleted_at": datetime.now(), "delete_attempts": attempt + 1}}
                )
                return True  # Consider this a success since the goal is achieved
                
            elif "chat not found" in error_msg or "channel not found" in error_msg:
                logger.warning(f"Channel {chat_id} not found for message {msg_id}")
                broadcast_bot.broadcast_messages_col.update_one(
                    {"channel_id": chat_id, "message_id": msg_id},
                    {"$set": {"status": "channel_not_found", "deleted_at": datetime.now(), "delete_attempts": attempt + 1}}
                )
                return False  # Don't retry for channel not found
                
            elif "not enough rights" in error_msg or "forbidden" in error_msg:
                logger.warning(f"No permission to delete message {msg_id} from {chat_id}")
                broadcast_bot.broadcast_messages_col.update_one(
                    {"channel_id": chat_id, "message_id": msg_id},
                    {"$set": {"status": "no_permission", "deleted_at": datetime.now(), "delete_attempts": attempt + 1}}
                )
                return False  # Don't retry for permission issues
                
            elif "flood" in error_msg or "too many requests" in error_msg:
                logger.warning(f"Rate limited for message {msg_id} from {chat_id}, waiting longer...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt] * 2)  # Double delay for rate limits
                    continue
                    
            elif attempt < max_retries - 1:
                logger.warning(f"Delete attempt {attempt + 1} failed: {e}")
                time.sleep(retry_delays[attempt])
            else:
                logger.error(f"Auto delete failed for {chat_id}: {e}")
                if broadcast_bot.broadcast_messages_col is not None:
                    broadcast_bot.broadcast_messages_col.update_one(
                        {"channel_id": chat_id, "message_id": msg_id},
                        {"$set": {"status": "delete_failed", "deleted_at": datetime.now(), "delete_attempts": attempt + 1, "error": str(e)}}
                    )
                
    return False

def advanced_auto_repost(chat_id: int, message, repost_time: int, delete_time: Optional[int], stop_flag: Dict[str, bool]):
    """Advanced auto repost with enhanced features"""
    logger.info(f"Starting auto repost for user {chat_id}")
    repost_count = 0
    
    while not stop_flag.get("stop", False):
        try:
            logger.info(f"Auto repost cycle {repost_count + 1} starting...")
            time.sleep(repost_time * 60)
            if stop_flag.get("stop", False):
                logger.info(f"Auto repost stopped for user {chat_id}")
                break
                
            channels = broadcast_bot.get_all_channels(chat_id)
            logger.info(f"Got {len(channels)} channels for repost")
            success_count = 0
            failed_count = 0
            
            for ch in channels:
                try:
                    if stop_flag.get("stop", False):
                        break
                        
                    sent = None
                    channel_id = ch["channel_id"]
                    logger.info(f"Reposting to channel {channel_id}")
                    
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
                        logger.info(f"Sending text to {channel_id}")
                        sent = bot.send_message(channel_id, text_to_send, parse_mode="Markdown")
                    elif message.content_type == "photo":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"Sending photo to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"Forward failed for {channel_id}, trying send_photo: {e}")
                            sent = bot.send_photo(channel_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
                    elif message.content_type == "video":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"Sending video to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"Forward failed for {channel_id}, trying send_video: {e}")
                            sent = bot.send_video(channel_id, message.video.file_id, caption=caption, parse_mode="Markdown")
                    elif message.content_type == "document":
                        caption = formatted_text if formatted_text else (message.caption or "")
                        logger.info(f"Sending document to {channel_id}")
                        try:
                            sent = bot.forward_message(channel_id, message.chat.id, message.message_id)
                        except Exception as e:
                            logger.warning(f"Forward failed for {channel_id}, trying send_document: {e}")
                            sent = bot.send_document(channel_id, message.document.file_id, caption=caption, parse_mode="Markdown")
                    else:
                        logger.info(f"Forwarding message to {channel_id}")
                        sent = bot.forward_message(channel_id, message.chat.id, message.message_id)

                    if sent:
                        success_count += 1
                        logger.info(f"Successfully reposted to {channel_id}")
                        
                        # Delete the previous message if it exists
                        try:
                            # Get the last message for this channel from this user
                            if broadcast_bot.broadcast_messages_col is not None:
                                last_msg = broadcast_bot.broadcast_messages_col.find_one(
                                    {"user_id": chat_id, "channel_id": channel_id, "status": {"$ne": "deleted"}},
                                    sort=[("created_at", -1)]
                                )
                                if last_msg and last_msg["message_id"] != sent.message_id:
                                    logger.info(f"Deleting previous message {last_msg['message_id']} from {channel_id}")
                                    try:
                                        bot.delete_message(channel_id, last_msg["message_id"])
                                        # Update status in database
                                        broadcast_bot.broadcast_messages_col.update_one(
                                            {"_id": last_msg["_id"]},
                                            {"$set": {"status": "deleted", "deleted_at": datetime.now()}}
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to delete previous message: {e}")
                        except Exception as e:
                            logger.warning(f"Error handling previous message: {e}")
                        
                        broadcast_bot.save_broadcast_message(
                            chat_id, channel_id, sent.message_id, 
                            f"auto_repost_{chat_id}_{int(time.time())}", "auto_repost"
                        )
                        
                        # Schedule auto delete if enabled
                        if delete_time:
                            logger.info(f"Scheduling auto delete for {channel_id} in {delete_time} minutes")
                            schedule_auto_delete(channel_id, sent.message_id, delete_time)
                    else:
                        failed_count += 1
                        logger.error(f"Failed to repost to {channel_id} - sent is None")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Repost failed for {ch.get('channel_id')}: {e}")
                    logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            
            repost_count += 1
            broadcast_bot.update_analytics("auto_reposts")
            
            logger.info(f"Repost cycle {repost_count} completed - Success: {success_count}, Failed: {failed_count}")
            
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
                    logger.error(f"Failed to send repost update: {e}")
            
        except Exception as e:
            logger.error(f"Error in auto_repost: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            time.sleep(60)

@bot.message_handler(commands=["start", "help", "stats", "analytics", "premium", "cleanup", "clear", "id", "test", "cid", "profile", "cleanbot", "channelid"])
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
    
    if message.text.startswith("/test"):
        # Test if bot is working
        bot.send_message(
            message.chat.id, 
            "🧪 <b>Bot Test Successful!</b> ✅\n\n"
            "<blockquote>"
            "🎯 <b>Bot Status:</b> Online\n"
            "📡 <b>Connection:</b> Active\n"
            "⚡ <b>Response Time:</b> Instant\n\n"
            "✅ All systems are working correctly!"
            "</blockquote>"
        )
        logger.info(f"Test command executed successfully by user {message.chat.id}")
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
• Status: 🔶 Free
        """
        bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")
        return

    if message.text.startswith("/profile"):
        # Show user profile (HTML formatting)
        analytics = broadcast_bot.get_user_analytics(message.chat.id)
        user_id = message.from_user.id
        first_name = html_escape(message.from_user.first_name or "-")
        last_name = html_escape(message.from_user.last_name or "")
        username = html_escape(f"@{message.from_user.username}") if message.from_user.username else "—"
        full_name = (first_name + (" " + last_name if last_name else "")).strip()
        plan = html_escape(analytics.get('subscription_type', 'Free').title())
        status = "🔶 Free"
        member_since = html_escape(str(analytics.get('member_since', 'Unknown')))
        last_active = html_escape(str(analytics.get('last_active', 'Now')))
        total_channels = html_escape(str(analytics.get('total_channels', 0)))
        total_broadcasts = html_escape(str(analytics.get('total_broadcasts', 0)))

        profile_html = (
            f"<b>👤 User Profile</b>\n\n"
            f"<blockquote>⚡ Manage broadcasts, channels and analytics from one place.</blockquote>\n"
            f"<b>Name:</b> {full_name}\n"
            f"<b>Username:</b> {username}\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n\n"
            f"<b>💎 Subscription</b>\n"
            f"<b>Plan:</b> {plan}\n"
            f"<b>Status:</b> {status}\n\n"
            f"<b>📊 Usage</b>\n"
            f"<b>Channels:</b> {total_channels}\n"
            f"<b>Broadcasts:</b> {total_broadcasts}\n\n"
            f"<b>🕒 Activity</b>\n"
            f"<b>Member Since:</b> {member_since}\n"
            f"<b>Last Active:</b> {last_active}\n\n"
            f"<a href=\"tg://user?id={user_id}\">Open Telegram Profile</a>"
        )

        send_html(message.chat.id, profile_html)
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

**Current Status:** 🆓 Free

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
            username = message.chat.username or "None"
            
            # Check if bot is admin in this channel
            try:
                bot_user = bot.get_me()
                chat_member = bot.get_chat_member(chat_id, bot_user.id)
                admin_status = "✅ Admin" if chat_member.status in ['administrator', 'creator'] else "❌ Not Admin"
            except Exception as e:
                admin_status = "❓ Unknown"
            
            id_text = f"""
🆔 **Channel/Group Information**

**📢 Channel Details:**
• **Channel ID:** `{chat_id}`
• **Channel Name:** {chat_title}
• **Chat Type:** {chat_type.title()}
• **Username:** @{username}
• **Bot Status:** {admin_status}

**💡 Usage:**
• Use this ID to add channel to bot
• Copy this ID for bulk channel addition
• Share with admin for channel management

**🔧 Quick Actions:**
• Add bot as admin if not already
• Use `/cid` to see all admin channels
• Send channel links in broadcast messages
            """
        
        try:
            bot.send_message(message.chat.id, id_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error sending /id response: {e}")
            # If bot can't send message in channel, try to send to user's private chat
            if chat_type != "private":
                try:
                    user_id = message.from_user.id
                    fallback_text = f"""
🆔 **Channel Information**

**📢 Channel Details:**
• **Channel ID:** `{chat_id}`
• **Channel Name:** {message.chat.title or "Unknown"}
• **Chat Type:** {chat_type.title()}
• **Username:** @{message.chat.username or "None"}

**⚠️ Note:** Bot cannot respond in this channel.
**💡 Solution:** Add bot as admin or use in private chat.

**🔧 Quick Actions:**
• Add bot as admin to enable commands
• Use this ID to add channel to bot
• Copy this ID for bulk channel addition
                    """
                    bot.send_message(user_id, fallback_text, parse_mode="Markdown")
                except Exception as e2:
                    logger.error(f"Failed to send fallback message: {e2}")
        return
    
    if message.text.startswith("/channelid"):
        # Simple channel ID command that works in any channel
        chat_id = message.chat.id
        chat_type = message.chat.type
        
        if chat_type == "private":
            bot.send_message(chat_id, "❌ **This command only works in channels/groups!**\n\nUse `/id` for your user information.", parse_mode="Markdown")
        else:
            channel_info = f"""
🆔 **Channel ID**

**📢 Channel Details:**
• **Channel ID:** `{chat_id}`
• **Channel Name:** {message.chat.title or "Unknown"}
• **Chat Type:** {chat_type.title()}
• **Username:** @{message.chat.username or "None"}

**💡 Usage:**
• Copy this ID to add channel to bot
• Use for bulk channel addition
• Share with admin for management
            """
            try:
                bot.send_message(chat_id, channel_info, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error sending /channelid response: {e}")
                # Try to send to user's private chat
                try:
                    user_id = message.from_user.id
                    fallback_text = f"""
🆔 **Channel ID**

**📢 Channel Details:**
• **Channel ID:** `{chat_id}`
• **Channel Name:** {message.chat.title or "Unknown"}
• **Chat Type:** {chat_type.title()}
• **Username:** @{message.chat.username or "None"}

**⚠️ Note:** Bot cannot respond in this channel.
**💡 Solution:** Add bot as admin to enable commands.

**🔧 Quick Actions:**
• Add bot as admin to enable commands
• Use this ID to add channel to bot
                    """
                    bot.send_message(user_id, fallback_text, parse_mode="Markdown")
                except Exception as e2:
                    logger.error(f"Failed to send fallback message: {e2}")
        return
    
    if message.text.startswith("/cid"):
        # Show channel IDs where bot is admin
        try:
            # Get bot info first
            bot_user = bot.get_me()
            logger.info(f"Bot user: {bot_user.username} (ID: {bot_user.id})")
            
            # Get all channels where bot is admin
            admin_channels = []
            
            # Check channels from user's database first
            user_channels = broadcast_bot.get_all_channels(message.chat.id)
            for ch in user_channels:
                try:
                    chat_member = bot.get_chat_member(ch["channel_id"], bot_user.id)
                    if chat_member.status in ['administrator', 'creator']:
                        admin_channels.append({
                            "channel_id": ch["channel_id"],
                            "channel_name": ch.get("channel_name", "Unknown"),
                            "username": ch.get("username", "private")
                        })
                except Exception as e:
                    logger.warning(f"Could not check admin status for {ch['channel_id']}: {e}")
            
            # Also check some common channel patterns or let user know how to add more
            if admin_channels:
                # Show channel IDs where bot is admin
                channel_ids = [str(ch["channel_id"]) for ch in admin_channels]
                
                # Chunk the output to avoid "message is too long" errors
                chunk_size = 15
                for i in range(0, len(channel_ids), chunk_size):
                    chunk = channel_ids[i:i + chunk_size]
                    chunk_text = "\n".join(chunk)
                    
                    # Show channel names too for better identification
                    chunk_channels = admin_channels[i:i + chunk_size]
                    channel_info = "\n".join([f"• {ch['channel_name']} (@{ch['username'] or 'private'}) - `{ch['channel_id']}`" for ch in chunk_channels])
                    
                    bot.send_message(
                        message.chat.id, 
                        f"📋 **Admin Channels (Part {i//chunk_size + 1}):**\n\n{channel_info}",
                        parse_mode="Markdown"
                    )
            else:
                bot.send_message(
                    message.chat.id, 
                    "❌ **No admin channels found!**\n\n"
                    "**To add channels:**\n"
                    "1. Add bot as admin to your channels\n"
                    "2. Use `/id` in the channel to get channel ID\n"
                    "3. Use 'Add Channel' button to add them\n"
                    "4. Or send channel links in broadcast message\n\n"
                    "**Note:** Bot must be admin in channels to broadcast there.",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error in /cid command: {e}")
            bot.send_message(message.chat.id, f"❌ **Error:** {str(e)}")
        return
    
    if message.text.startswith("/cleanbot"):
        # Manual cleanup of bot messages
        deleted_count = delete_bot_messages(message.chat.id)
        bot.send_message(
            message.chat.id, 
            f"🤖 **Bot Messages Cleaned!**\n\n✅ **Deleted:** `{deleted_count}` bot messages\n\n💡 Use this command to clean up bot messages manually.",
            parse_mode="Markdown"
        )
        return
    
    if message.text.startswith("/cleanup") or message.text.startswith("/clear"):
            
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
    
    # If user is using /start or /help without specific command, show main menu
    if message.text.startswith("/start") or message.text.startswith("/help"):
        # No gating here anymore
        pass

    # Main menu (for premium/admin users) - SIMPLIFIED
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 BROADCAST", callback_data="broadcast"),
        types.InlineKeyboardButton("➕ ADD CHANNEL", callback_data="add_channel"),
        )
    markup.add(
        types.InlineKeyboardButton("📋 BULK ADD CHANNELS", callback_data="bulk_add_channels"),
        types.InlineKeyboardButton("🛑 STOP ALL", callback_data="stop_all_broadcasts"),
    )
    

    user_analytics = broadcast_bot.get_user_analytics(message.chat.id)
    _first = message.from_user.first_name or "-"
    _last = message.from_user.last_name or ""
    _full_name = (_first + (" " + _last if _last else "")).strip()
    _username = f"@{message.from_user.username}" if message.from_user.username else "—"
    _uid = message.from_user.id

    name_html = html_escape(_full_name)
    username_html = html_escape(_username)
    plan_html = html_escape(str(user_analytics.get('subscription_type', 'FREE')).upper())

    welcome_caption_html = (
        f"<b>🎉 ADVANCED BROADCAST BOT 🚀</b>\n\n"
        f"<blockquote><b>👋 WELCOME, {html_escape(_first).upper()}!</b>\n\n"
        f"<b>⚡ YOUR CONTROL CENTER</b>\n"
        f"Manage broadcasts, channels & analytics with ease\n\n"
        f"<b>👤 PROFILE INFORMATION</b>\n"
        f"• <b>Name:</b> {name_html}\n"
        f"• <b>Username:</b> {username_html}\n"
        f"• <b>User ID:</b> <code>{_uid}</code></blockquote>\n\n"
        f"<b>📊 YOUR DASHBOARD</b>\n"
        f"<blockquote>• <b>Channels:</b> {user_analytics.get('total_channels', 0)}\n"
        f"• <b>Broadcasts:</b> {user_analytics.get('total_broadcasts', 0)}\n"
        f"• <b>Plan:</b> {plan_html}\n"
        f"• <b>Status:</b> ✅ ONLINE</blockquote>\n\n"
        f"<b>🔥 ADVANCED FEATURES</b>\n"
        f"<blockquote>• <b>Auto Repost & Delete</b> — Smart message management\n"
        f"• <b>Scheduled Broadcasts</b> — Time-based messaging\n"
        f"• <b>Real-time Analytics</b> — Live performance tracking\n"
        f"• <b>Bulk Operations</b> — Mass channel management\n"
        f"• <b>Instant Stop All</b> — Emergency controls</blockquote>\n\n"
        f"<b>💡 QUICK COMMANDS</b>\n"
        f"<blockquote>• <b>/id</b> — Get channel IDs\n"
        f"• <b>/cid</b> — List admin channel IDs\n"
        f"• <b>/profile</b> — Your profile details\n"
        f"• <b>/stats</b> — Your statistics\n"
        f"• <b>/test</b> — Bot functionality test</blockquote>\n\n"
        f"<b>🚀 CHOOSE AN OPTION BELOW</b>"
    )

    try:
        bot.send_photo(
            message.chat.id,
            "https://i.ibb.co/GQrGd0MV/a101f4b2bfa4.jpg",
            caption=welcome_caption_html,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error sending start message: {e}")
        send_html(message.chat.id, welcome_caption_html, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Advanced callback handler"""
    logger.info(f"Callback received: {call.data} from user {call.message.chat.id}")
    
    # Premium gating removed

    try:
        user_id = call.message.chat.id
        state = bot_state.broadcast_state.get(user_id, {})
        
        logger.info(f"Processing callback: {call.data} for user {user_id}")
        
        # Answer callback query immediately to prevent timeout
        try:
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.warning(f"Failed to answer callback query: {e}")

        if call.data == "test_button":
            logger.info("Test button pressed!")
            
            # Show typing indicator
            show_typing_indicator(user_id, 2)
            
            test_result = f"""
<b>🧪 BOT FUNCTIONALITY TEST</b>

<blockquote><b>✅ ALL SYSTEMS OPERATIONAL</b>
• <b>Database:</b> Connected ✅
• <b>Broadcast:</b> Ready ✅
• <b>Auto-Delete:</b> Active ✅
• <b>Auto-Repost:</b> Active ✅
• <b>Status:</b> {create_loading_animation(4)}</blockquote>

<b>🚀 Bot is working perfectly!</b>
            """
            bot.send_message(user_id, test_result, parse_mode="HTML")
            return

        elif call.data == "broadcast":
            logger.info(f"Broadcast button pressed by user {user_id}")
            bot_state.broadcast_state[user_id] = {"step": "waiting_msg"}
            
            # Show typing indicator
            show_typing_indicator(user_id, 2)
            
            broadcast_prompt = f"""
<b>📢 BROADCAST MESSAGE REQUEST</b>

<blockquote><b>🚀 Ready to Broadcast!</b>
• <b>Status:</b> {create_loading_animation(0)}
• <b>Action:</b> Send your message now
• <b>Features:</b> Auto-repost & delete available</blockquote>

<b>💡 Send your message to start broadcasting</b>
            """
            sent_msg = bot.send_message(user_id, broadcast_prompt, parse_mode="HTML")
            # Auto-delete broadcast prompt after 30 seconds
            if sent_msg:
                threading.Timer(30, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()

        elif call.data == "stop_and_delete":
            logger.info(f"Stop and Delete button pressed by user {user_id}")
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
            
        elif call.data == "instant_stop_all":
            logger.info(f"Instant Stop All button pressed by user {user_id}")
            
            # Send instant status
            status_msg = bot.send_message(
                user_id,
                f"🛑 **Instant Stop All Activated!**\n\n"
                f"⏹ Stopping all reposts...\n"
                f"🗑 Preparing to delete messages...\n"
                f"⚡ Processing at maximum speed...",
                parse_mode="Markdown"
            )
            
            # Stop all active reposts
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
            
            # Get all broadcast messages from database
            broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 10000)
            
            # Update status
            bot.edit_message_text(
                f"🛑 **Instant Stop All - IN PROGRESS**\n\n"
                f"⏹ **Reposts Stopped:** ✅\n"
                f"🗑 **Messages Found:** `{len(broadcast_messages)}`\n"
                f"⚡ **Deleting messages...**\n"
                f"⏳ Please wait...",
                user_id, status_msg.message_id, parse_mode="Markdown"
            )
            
            # Enhanced deletion with better error handling and accurate reporting
            deleted_count = 0
            failed_count = 0
            already_deleted_count = 0
            no_permission_count = 0
            failed_channels = []
            
            # Process messages in batches for better performance
            batch_size = 50
            for i in range(0, len(broadcast_messages), batch_size):
                batch = broadcast_messages[i:i + batch_size]
                
                for msg in batch:
                    try:
                        channel_id = msg.get('channel_id')
                        message_id = msg.get('message_id')
                        
                        if channel_id and message_id:
                            result = bot.delete_message(channel_id, message_id)
                            if result:
                                deleted_count += 1
                            else:
                                failed_count += 1
                                failed_channels.append(str(channel_id))
                        else:
                            failed_count += 1
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "message to delete not found" in error_msg or "message not found" in error_msg:
                            already_deleted_count += 1
                        elif "not enough rights" in error_msg or "forbidden" in error_msg or "unauthorized" in error_msg:
                            no_permission_count += 1
                            failed_channels.append(str(msg.get('channel_id', 'unknown')))
                        else:
                            failed_count += 1
                            failed_channels.append(str(msg.get('channel_id', 'unknown')))
                        logger.error(f"Failed to delete message {msg.get('message_id')} from {msg.get('channel_id')}: {e}")
                
                # Update progress every batch
                if i + batch_size < len(broadcast_messages):
                    progress = min(100, int((i + batch_size) / len(broadcast_messages) * 100))
                    bot.edit_message_text(
                        f"🛑 **Instant Stop All - IN PROGRESS**\n\n"
                        f"⏹ **Reposts Stopped:** ✅\n"
                        f"🗑 **Progress:** `{progress}%`\n"
                        f"✅ **Deleted:** `{deleted_count}`\n"
                        f"🗑 **Already Deleted:** `{already_deleted_count}`\n"
                        f"🚫 **No Permission:** `{no_permission_count}`\n"
                        f"❌ **Failed:** `{failed_count}`\n"
                        f"⚡ **Processing...**",
                        user_id, status_msg.message_id, parse_mode="Markdown"
                    )
            
            # Clear broadcast history from database
            broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
            
            # Clear any active broadcasts
            if user_id in bot_state.active_broadcasts:
                del bot_state.active_broadcasts[user_id]
            
            # Clear broadcast state
            if user_id in bot_state.broadcast_state:
                del bot_state.broadcast_state[user_id]
            
            # Delete bot messages from user's chat (clean up bot's own messages)
            bot_messages_deleted = delete_bot_messages(user_id)
            
            # Final result with detailed information
            result_text = f"""
🛑 **Instant Stop All - COMPLETED!**

⚡ **Ultra-Fast Results:**
• ✅ **Channel Messages Deleted:** `{deleted_count}`
• 🗑 **Already Deleted:** `{already_deleted_count}`
• 🚫 **No Permission:** `{no_permission_count}`
• ❌ **Failed:** `{failed_count}`
• 🤖 **Bot Messages Deleted:** `{bot_messages_deleted}`
• ⏹ **Reposts Stopped:** ✅
• 📋 **History Cleared:** ✅
• ⚡ **Speed:** Instant

🎯 **All broadcasts stopped and chat cleaned up!**
            """
            
            if no_permission_count > 0:
                failed_list = ', '.join(set(failed_channels[:10]))
                if len(set(failed_channels)) > 10:
                    failed_list += f" and {len(set(failed_channels)) - 10} more"
                result_text += f"\n\n🚫 **Channels with Permission Issues:**\n`{failed_list}`"
            
            bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
            # Auto-delete instant stop result after 8 seconds
            threading.Timer(8, lambda: delete_message_safe(user_id, status_msg.message_id)).start()

        elif call.data == "send_now":
            # Send broadcast immediately without any auto features
            state["repost_time"] = None
            state["delete_time"] = None
            finish_advanced_broadcast(user_id)
            
        elif call.data == "repost_yes":
            # Update state and highlight repost time selection
            state["step"] = "repost_selected"
            bot_state.broadcast_state[user_id] = state
            
            # Update the message to highlight repost time selection
            try:
                message_text = "📢 **Broadcast Configuration**\n\n"
                
                # Add channel info if available
                if state.get("message"):
                    original_text = state["message"].text or state["message"].caption or ""
                    added_channels = []
                    if original_text:
                        try:
                            added_channels = auto_add_telegram_links(user_id, original_text)
                        except Exception as e:
                            logger.warning(f"auto_add_telegram_links failed: {e}")
                    
                    if added_channels:
                        channel_list = "\n".join([f"• **{ch['channel_name']}** (@{ch['username'] or 'private'})" for ch in added_channels])
                        message_text += f"✅ **Auto-added {len(added_channels)} channels:**\n{channel_list}\n\n"
                        original_links = extract_telegram_links(original_text)
                        if original_links:
                            links_text = "\n".join([f"🔗 `{link}`" for link in original_links])
                            message_text += f"🔍 **Detected Links:**\n{links_text}\n\n"
                    
                    if original_text:
                        preview_text = original_text[:100] + "..." if len(original_text) > 100 else original_text
                        message_text += f"📝 **Broadcast Text:**\n`{preview_text}`\n\n"

                message_text += "⚙️ **Configure your broadcast:**\n\n"
                message_text += "🔄 **Auto Repost:** ✅ **ENABLED** - Select time below:\n"

                # Create markup with repost times highlighted
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # 🔄 AUTO REPOST SECTION (highlighted)
                markup.add(types.InlineKeyboardButton("🔄 **AUTO REPOST**", callback_data="repost_yes"))
                markup.row(
                    types.InlineKeyboardButton("⏱ 5m", callback_data="repost_5"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2")
                )
                markup.row(
                    types.InlineKeyboardButton("🕕 6h", callback_data="repost_360"),
                    types.InlineKeyboardButton("🌙 12h", callback_data="repost_720"),
                    types.InlineKeyboardButton("📅 1d", callback_data="repost_1440"),
                    types.InlineKeyboardButton("📆 2d", callback_data="repost_2880")
                )
                markup.row(
                    types.InlineKeyboardButton("🎯 Custom Repost Time", callback_data="repost_custom")
                )
                
                # Separator
                markup.add(types.InlineKeyboardButton("━━━━━━━━━━━━━━━━", callback_data="separator"))
                
                # 🗑 AUTO DELETE SECTION (normal)
                markup.add(types.InlineKeyboardButton("🗑 **AUTO DELETE**", callback_data="delete_yes"))
                markup.row(
                    types.InlineKeyboardButton("⚡ 3m", callback_data="delete_3"),
                    types.InlineKeyboardButton("🔟 2m", callback_data="delete_2"),
                    types.InlineKeyboardButton("🕒 2m", callback_data="delete_2"),
                    types.InlineKeyboardButton("⏰ 2m", callback_data="delete_2")
                )
                markup.row(
                    types.InlineKeyboardButton("🕕 6h", callback_data="delete_360"),
                    types.InlineKeyboardButton("🌙 12h", callback_data="delete_720"),
                    types.InlineKeyboardButton("📅 1d", callback_data="delete_1440"),
                    types.InlineKeyboardButton("📆 2d", callback_data="delete_2880")
                )
                markup.row(
                    types.InlineKeyboardButton("🎯 Custom Delete Time", callback_data="delete_custom")
                )
                
                # Skip options
                markup.row(
                    types.InlineKeyboardButton("❌ No Repost", callback_data="repost_no"),
                    types.InlineKeyboardButton("❌ No Delete", callback_data="delete_no")
                )
                
                # Send now option
                markup.add(types.InlineKeyboardButton("🚀 Send Now (No Auto)", callback_data="send_now"))
                
                bot.edit_message_text(
                    message_text, 
                    user_id, 
                    call.message.message_id, 
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to update message for repost_yes: {e}")
            
        elif call.data == "repost_no":
            state["repost_time"] = None
            state["step"] = "repost_disabled"
            bot_state.broadcast_state[user_id] = state

        elif call.data == "delete_yes":
            # Update state and highlight delete time selection
            state["step"] = "delete_selected"
            bot_state.broadcast_state[user_id] = state
            
            # Update the message to highlight delete time selection
            try:
                message_text = "📢 **Broadcast Configuration**\n\n"
                
                # Add channel info if available
                if state.get("message"):
                    original_text = state["message"].text or state["message"].caption or ""
                    added_channels = []
                    if original_text:
                        try:
                            added_channels = auto_add_telegram_links(user_id, original_text)
                        except Exception as e:
                            logger.warning(f"auto_add_telegram_links failed: {e}")
                    
                    if added_channels:
                        channel_list = "\n".join([f"• **{ch['channel_name']}** (@{ch['username'] or 'private'})" for ch in added_channels])
                        message_text += f"✅ **Auto-added {len(added_channels)} channels:**\n{channel_list}\n\n"
                        original_links = extract_telegram_links(original_text)
                        if original_links:
                            links_text = "\n".join([f"🔗 `{link}`" for link in original_links])
                            message_text += f"🔍 **Detected Links:**\n{links_text}\n\n"
                    
                    if original_text:
                        preview_text = original_text[:100] + "..." if len(original_text) > 100 else original_text
                        message_text += f"📝 **Broadcast Text:**\n`{preview_text}`\n\n"

                message_text += "⚙️ **Configure your broadcast:**\n\n"
                message_text += "🗑 **Auto Delete:** ✅ **ENABLED** - Select time below:\n"

                # Create markup with delete times highlighted
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # 🔄 AUTO REPOST SECTION (normal)
                markup.add(types.InlineKeyboardButton("🔄 **AUTO REPOST**", callback_data="repost_yes"))
                markup.row(
                    types.InlineKeyboardButton("⏱ 5m", callback_data="repost_5"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"),
                    types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2")
                )
                markup.row(
                    types.InlineKeyboardButton("🕕 6h", callback_data="repost_360"),
                    types.InlineKeyboardButton("🌙 12h", callback_data="repost_720"),
                    types.InlineKeyboardButton("📅 1d", callback_data="repost_1440"),
                    types.InlineKeyboardButton("📆 2d", callback_data="repost_2880")
                )
                markup.row(
                    types.InlineKeyboardButton("🎯 Custom Repost Time", callback_data="repost_custom")
                )
                
                # Separator
                markup.add(types.InlineKeyboardButton("━━━━━━━━━━━━━━━━", callback_data="separator"))
                
                # 🗑 AUTO DELETE SECTION (highlighted)
                markup.add(types.InlineKeyboardButton("🗑 **AUTO DELETE**", callback_data="delete_yes"))
                markup.row(
                    types.InlineKeyboardButton("⚡ 3m", callback_data="delete_3"),
                    types.InlineKeyboardButton("🔟 2m", callback_data="delete_2"),
                    types.InlineKeyboardButton("🕒 2m", callback_data="delete_2"),
                    types.InlineKeyboardButton("⏰ 2m", callback_data="delete_2")
                )
                markup.row(
                    types.InlineKeyboardButton("🕕 6h", callback_data="delete_360"),
                    types.InlineKeyboardButton("🌙 12h", callback_data="delete_720"),
                    types.InlineKeyboardButton("📅 1d", callback_data="delete_1440"),
                    types.InlineKeyboardButton("📆 2d", callback_data="delete_2880")
                )
                markup.row(
                    types.InlineKeyboardButton("🎯 Custom Delete Time", callback_data="delete_custom")
                )
                
                # Skip options
                markup.row(
                    types.InlineKeyboardButton("❌ No Repost", callback_data="repost_no"),
                    types.InlineKeyboardButton("❌ No Delete", callback_data="delete_no")
                )
                
                # Send now option
                markup.add(types.InlineKeyboardButton("🚀 Send Now (No Auto)", callback_data="send_now"))
                
                bot.edit_message_text(
                    message_text, 
                    user_id, 
                    call.message.message_id, 
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to update message for delete_yes: {e}")
            
        elif call.data == "delete_no":
            state["delete_time"] = None
            state["step"] = "delete_disabled"
            bot_state.broadcast_state[user_id] = state

        elif call.data == "set_repost_time":
            # Show auto repost time selection
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("⏱ 5m", callback_data="repost_5"))
            markup.add(types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"))
            markup.add(types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"))
            markup.add(types.InlineKeyboardButton("⏱ 2m", callback_data="repost_2"))
            markup.add(types.InlineKeyboardButton("🕕 6h", callback_data="repost_360"))
            markup.add(types.InlineKeyboardButton("🌙 12h", callback_data="repost_720"))
            markup.add(types.InlineKeyboardButton("📅 1d", callback_data="repost_1440"))
            markup.add(types.InlineKeyboardButton("📆 2d", callback_data="repost_2880"))
            markup.add(types.InlineKeyboardButton("🎯 Custom Time", callback_data="repost_custom"))
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config"))
            
            repost_text = f"""
<b>🔄 AUTO REPOST TIME SELECTION</b>

<blockquote><b>⏰ Choose Repost Interval</b>
Your message will be automatically reposted at the selected interval</blockquote>

<b>💡 Select a time option:</b>
            """
            bot.edit_message_text(repost_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data == "set_delete_time":
            # Show auto delete time selection
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("⚡ 3m", callback_data="delete_3"))
            markup.add(types.InlineKeyboardButton("🔟 2m", callback_data="delete_2"))
            markup.add(types.InlineKeyboardButton("🕒 2m", callback_data="delete_2"))
            markup.add(types.InlineKeyboardButton("⏰ 2m", callback_data="delete_2"))
            markup.add(types.InlineKeyboardButton("🕕 6h", callback_data="delete_360"))
            markup.add(types.InlineKeyboardButton("🌙 12h", callback_data="delete_720"))
            markup.add(types.InlineKeyboardButton("📅 1d", callback_data="delete_1440"))
            markup.add(types.InlineKeyboardButton("📆 2d", callback_data="delete_2880"))
            markup.add(types.InlineKeyboardButton("🎯 Custom Time", callback_data="delete_custom"))
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config"))
            
            delete_text = f"""
<b>🗑 AUTO DELETE TIME SELECTION</b>

<blockquote><b>⏰ Choose Delete Time</b>
Your message will be automatically deleted after the selected time</blockquote>

<b>💡 Select a time option:</b>
            """
            bot.edit_message_text(delete_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data == "send_now":
            # Send broadcast immediately without auto features
            state["repost_time"] = None
            state["delete_time"] = None
            bot_state.broadcast_state[user_id] = state
            finish_advanced_broadcast(user_id)

        elif call.data == "advanced_settings":
            # Show advanced settings
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔄 Set Repost", callback_data="set_repost_time"),
                types.InlineKeyboardButton("🗑 Set Delete", callback_data="set_delete_time")
            )
            markup.add(
                types.InlineKeyboardButton("📤 Send Now", callback_data="send_now"),
                types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config")
            )
            
            advanced_text = f"""
<b>⚙️ ADVANCED BROADCAST SETTINGS</b>

<blockquote><b>🔧 Configure Auto Features</b>
• <b>Auto Repost:</b> {'✅ Set' if state.get('repost_time') else '❌ Not Set'}
• <b>Auto Delete:</b> {'✅ Set' if state.get('delete_time') else '❌ Not Set'}</blockquote>

<b>💡 Choose an option:</b>
            """
            bot.edit_message_text(advanced_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data == "back_to_config":
            # Return to main configuration
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
                types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time")
            )
            markup.add(
                types.InlineKeyboardButton("📤 Send Now (No Auto)", callback_data="send_now"),
                types.InlineKeyboardButton("⚙️ Advanced Settings", callback_data="advanced_settings")
            )
            
            config_text = f"""
<b>📢 BROADCAST CONFIGURATION</b>

<blockquote><b>⚙️ CONFIGURE YOUR BROADCAST</b>
Set up auto-repost and auto-delete settings for your message</blockquote>

<b>💡 Choose an option:</b>
            """
            bot.edit_message_text(config_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data.startswith("repost_"):
            time_value = int(call.data.replace("repost_", ""))
            state["repost_time"] = time_value
            state["step"] = "repost_time_selected"
            bot_state.broadcast_state[user_id] = state
            bot.answer_callback_query(call.id, f"✅ Auto repost set to {time_value} minutes!")
            
            # Check if both settings are configured
            if state.get("repost_time") and state.get("delete_time"):
                # Both are set, show final confirmation
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🚀 Start Broadcast", callback_data="start_broadcast"),
                    types.InlineKeyboardButton("⚙️ Change Settings", callback_data="advanced_settings")
                )
                
                final_text = f"""
<b>🎯 BROADCAST READY!</b>

<blockquote><b>✅ CONFIGURATION COMPLETE</b>
• <b>Auto Repost:</b> {state.get('repost_time')} minutes
• <b>Auto Delete:</b> {state.get('delete_time')} minutes</blockquote>

<b>🚀 Ready to broadcast!</b>
                """
                bot.edit_message_text(final_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
            else:
                # Show current status
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time"),
                    types.InlineKeyboardButton("📤 Send Now", callback_data="send_now")
                )
                markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config"))
                
                status_text = f"""
<b>🔄 AUTO REPOST SET!</b>

<blockquote><b>✅ REPOST CONFIGURED</b>
• <b>Auto Repost:</b> {time_value} minutes
• <b>Auto Delete:</b> {'✅ Set' if state.get('delete_time') else '❌ Not Set'}</blockquote>

<b>💡 Next step:</b>
                """
                bot.edit_message_text(status_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data.startswith("delete_"):
            if call.data == "delete_custom":
                # Handle custom delete time
                state["step"] = "ask_delete_custom_time"
                bot_state.broadcast_state[user_id] = state
                custom_text = f"""
<b>🎯 CUSTOM AUTO DELETE TIME</b>

<blockquote><b>⏰ Enter Delete Time</b>
Enter the time in minutes (1-43200)</blockquote>

<b>💡 Examples:</b>
• 15 = 15 minutes
• 120 = 2 hours  
• 1440 = 1 day
• 10080 = 1 week
                """
                sent_msg = bot.send_message(user_id, custom_text, parse_mode="HTML")
                # Auto-delete the prompt after 60 seconds
                if sent_msg:
                    threading.Timer(60, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()
            elif call.data != "delete_custom":
                try:
                    time_value = int(call.data.replace("delete_", ""))
                    state["delete_time"] = time_value
                    state["step"] = "delete_time_selected"
                    bot_state.broadcast_state[user_id] = state
                except ValueError:
                    logger.error(f"Invalid delete time value: {call.data}")
                
                # Check if both settings are configured
                if state.get("repost_time") and state.get("delete_time"):
                    # Both are set, show final confirmation
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🚀 Start Broadcast", callback_data="start_broadcast"),
                        types.InlineKeyboardButton("⚙️ Change Settings", callback_data="advanced_settings")
                    )
                    
                    final_text = f"""
<b>🎯 BROADCAST READY!</b>

<blockquote><b>✅ CONFIGURATION COMPLETE</b>
• <b>Auto Repost:</b> {state.get('repost_time')} minutes
• <b>Auto Delete:</b> {state.get('delete_time')} minutes</blockquote>

<b>🚀 Ready to broadcast!</b>
                    """
                    bot.edit_message_text(final_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
                else:
                    # Show current status
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
                        types.InlineKeyboardButton("📤 Send Now", callback_data="send_now")
                    )
                    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config"))
                    
                    status_text = f"""
<b>🗑 AUTO DELETE SET!</b>

<blockquote><b>✅ DELETE CONFIGURED</b>
• <b>Auto Repost:</b> {'✅ Set' if state.get('repost_time') else '❌ Not Set'}
• <b>Auto Delete:</b> {time_value} minutes</blockquote>

<b>💡 Next step:</b>
                    """
                    bot.edit_message_text(status_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data == "start_broadcast":
            # Start the broadcast with configured settings
            finish_advanced_broadcast(user_id)

        elif call.data.startswith("repost_"):
            if call.data == "repost_custom":
                # Handle custom repost time
                state["step"] = "ask_repost_custom_time"
                bot_state.broadcast_state[user_id] = state
                custom_text = f"""
<b>🎯 CUSTOM AUTO REPOST TIME</b>

<blockquote><b>⏰ Enter Repost Time</b>
Enter the time in minutes (1-43200)</blockquote>

<b>💡 Examples:</b>
• 15 = 15 minutes
• 120 = 2 hours
• 1440 = 1 day
• 10080 = 1 week
                """
                sent_msg = bot.send_message(user_id, custom_text, parse_mode="HTML")
                # Auto-delete the prompt after 60 seconds
                if sent_msg:
                    threading.Timer(60, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()
            elif call.data != "repost_custom":
                try:
                    time_value = int(call.data.replace("repost_", ""))
                    state["repost_time"] = time_value
                    state["step"] = "repost_time_selected"
                    bot_state.broadcast_state[user_id] = state
                except ValueError:
                    logger.error(f"Invalid repost time value: {call.data}")
                
                # Check if both settings are configured
                if state.get("repost_time") and state.get("delete_time"):
                    # Both are set, show final confirmation
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🚀 Start Broadcast", callback_data="start_broadcast"),
                        types.InlineKeyboardButton("⚙️ Change Settings", callback_data="advanced_settings")
                    )
                    
                    final_text = f"""
<b>🎯 BROADCAST READY!</b>

<blockquote><b>✅ CONFIGURATION COMPLETE</b>
• <b>Auto Repost:</b> {state.get('repost_time')} minutes
• <b>Auto Delete:</b> {state.get('delete_time')} minutes</blockquote>

<b>🚀 Ready to broadcast!</b>
                    """
                    bot.edit_message_text(final_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
                else:
                    # Show current status
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time"),
                        types.InlineKeyboardButton("📤 Send Now", callback_data="send_now")
                    )
                    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_config"))
                    
                    status_text = f"""
<b>🔄 AUTO REPOST SET!</b>

<blockquote><b>✅ REPOST CONFIGURED</b>
• <b>Auto Repost:</b> {time_value} minutes
• <b>Auto Delete:</b> {'✅ Set' if state.get('delete_time') else '❌ Not Set'}</blockquote>

<b>💡 Next step:</b>
                    """
                    bot.edit_message_text(status_text, user_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif call.data == "separator":
            # Separator button - do nothing
            pass
        elif call.data == "stop_repost":
            # Stop repost for this user
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
                bot.send_message(
                    user_id, 
                    "⏹ **Auto Repost Stopped!**\n\n✅ All repost cycles have been terminated.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(user_id, "⚠️ No active auto reposts found.")
            

            
        elif call.data == "confirm_delete_all":
            # Send status message
            status_msg = bot.send_message(
                user_id,
                f"🧹 **Broadcast Cleanup Started!**\n\n"
                f"⏹ Stopping all reposts...\n"
                f"🗑 Preparing to delete messages...\n"
                f"⚡ Processing...",
                parse_mode="Markdown"
            )
            
            # Stop all reposts
            if user_id in bot_state.active_reposts:
                bot_state.active_reposts[user_id]["stop"] = True
                del bot_state.active_reposts[user_id]
            
            # Delete all broadcast messages with better error handling
            deleted_count = 0
            failed_count = 0
            already_deleted_count = 0
            no_permission_count = 0
            failed_channels = []
            
            try:
                # Get all broadcast messages for this user
                broadcast_messages = broadcast_bot.get_broadcast_messages(user_id, 10000)
                
                # Update status
                bot.edit_message_text(
                    f"🧹 **Broadcast Cleanup - IN PROGRESS**\n\n"
                    f"⏹ **Reposts Stopped:** ✅\n"
                    f"🗑 **Messages Found:** `{len(broadcast_messages)}`\n"
                    f"⚡ **Deleting messages...**\n"
                    f"⏳ Please wait...",
                    user_id, status_msg.message_id, parse_mode="Markdown"
                )
                
                # Process messages in batches
                batch_size = 50
                for i in range(0, len(broadcast_messages), batch_size):
                    batch = broadcast_messages[i:i + batch_size]
                    
                    for msg in batch:
                        try:
                            channel_id = msg.get('channel_id')
                            message_id = msg.get('message_id')
                            
                            if channel_id and message_id:
                                result = bot.delete_message(channel_id, message_id)
                                if result:
                                    deleted_count += 1
                                else:
                                    failed_count += 1
                                    failed_channels.append(str(channel_id))
                            else:
                                failed_count += 1
                        except Exception as e:
                            error_msg = str(e).lower()
                            if "message to delete not found" in error_msg or "message not found" in error_msg:
                                already_deleted_count += 1
                            elif "not enough rights" in error_msg or "forbidden" in error_msg or "unauthorized" in error_msg:
                                no_permission_count += 1
                                failed_channels.append(str(msg.get('channel_id', 'unknown')))
                            else:
                                failed_count += 1
                                failed_channels.append(str(msg.get('channel_id', 'unknown')))
                            logger.error(f"Failed to delete message {msg.get('message_id')} from {msg.get('channel_id')}: {e}")
                    
                    # Update progress every batch
                    if i + batch_size < len(broadcast_messages):
                        progress = min(100, int((i + batch_size) / len(broadcast_messages) * 100))
                        bot.edit_message_text(
                            f"🧹 **Broadcast Cleanup - IN PROGRESS**\n\n"
                            f"⏹ **Reposts Stopped:** ✅\n"
                            f"🗑 **Progress:** `{progress}%`\n"
                            f"✅ **Deleted:** `{deleted_count}`\n"
                            f"🗑 **Already Deleted:** `{already_deleted_count}`\n"
                            f"🚫 **No Permission:** `{no_permission_count}`\n"
                            f"❌ **Failed:** `{failed_count}`\n"
                            f"⚡ **Processing...**",
                            user_id, status_msg.message_id, parse_mode="Markdown"
                        )
                
                # Clear broadcast history from database
                broadcast_bot.broadcast_messages_col.delete_many({"user_id": user_id})
                
                # Clear any active broadcasts
                if user_id in bot_state.active_broadcasts:
                    del bot_state.active_broadcasts[user_id]
                
                # Clear broadcast state
                if user_id in bot_state.broadcast_state:
                    del bot_state.broadcast_state[user_id]
                
                # Delete bot messages from user's chat (clean up bot's own messages)
                bot_messages_deleted = delete_bot_messages(user_id)
                
                result_text = f"""
🗑 **Broadcast Cleanup Completed!**

📊 **Results:**
• ✅ **Channel Messages Deleted:** `{deleted_count}`
• 🗑 **Already Deleted:** `{already_deleted_count}`
• 🚫 **No Permission:** `{no_permission_count}`
• ❌ **Failed:** `{failed_count}`
• 🤖 **Bot Messages Deleted:** `{bot_messages_deleted}`
• 🔄 **Reposts Stopped:** ✅
• 📋 **History Cleared:** ✅

✅ **All broadcast messages and bot messages cleaned up!**
                """
                
                if no_permission_count > 0:
                    failed_list = ', '.join(set(failed_channels[:10]))
                    if len(set(failed_channels)) > 10:
                        failed_list += f" and {len(set(failed_channels)) - 10} more"
                    result_text += f"\n\n🚫 **Channels with Permission Issues:**\n`{failed_list}`"
                
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                # Auto-delete cleanup result after 8 seconds
                threading.Timer(8, lambda: delete_message_safe(user_id, status_msg.message_id)).start()
                
            except Exception as e:
                logger.error(f"Error in confirm_delete_all: {e}")
                bot.edit_message_text("❌ **Error during cleanup process**", user_id, status_msg.message_id, parse_mode="Markdown")
                
        elif call.data == "cancel_delete":
            bot.send_message(user_id, "❌ Operation cancelled.")

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
            bot.send_message(
                user_id, 
                "➕ **Add Single Channel**\n\n"
                "**Send one of the following:**\n\n"
                "1️⃣ **Channel ID:** `-1001234567890`\n"
                "2️⃣ **Channel Link:** `https://t.me/channelname`\n"
                "3️⃣ **Channel Username:** `@channelname`\n\n"
                "**💡 How to get Channel ID:**\n"
                "• Use `/id` command in the channel\n"
                "• Forward a message from the channel to me\n"
                "• Or send the channel link/username",
                parse_mode="Markdown"
            )

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
• Status: 🔶 Free
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
            bot.send_message(user_id, "✅ Premium mode is disabled. All features are free now.")

        elif call.data == "contact_admin":
            bot.send_message(user_id, "ℹ️ Contact owner not required. Bot is free to use.")


        elif call.data == "cleanup_all_messages":
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
• ✅ **Messages Deleted:** `{deleted_count}`
• ❌ **Failed Deletions:** `{failed_count}`
• 📋 **History Cleared:** ✅

✅ **All broadcast messages have been removed from channels.**
                """
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Error in cleanup_all_messages: {e}")
                bot.send_message(user_id, "❌ Error during message cleanup process")

        elif call.data == "cleanup_stop_reposts":
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
• ✅ **Messages Deleted:** `{deleted_count}`
• ❌ **Failed Deletions:** `{failed_count}`
• ⏹ **Reposts Stopped:** ✅
• 📋 **History Cleared:** ✅

✅ **Complete cleanup completed successfully!**
                """
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Error in cleanup_everything: {e}")
                bot.send_message(user_id, "❌ Error during complete cleanup process")

        elif call.data == "cleanup_cancel":
            bot.send_message(user_id, "❌ Cleanup operation cancelled.")

        elif call.data == "bulk_add_channels":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_bulk_add"))
            
            sent_msg = bot.send_message(
                user_id,
                "📋 **Bulk Add Channels**\n\n"
                "Send channel IDs in this format:\n"
                "```\n"
                "-1001234567890\n"
                "-1001234567891\n"
                "-1001234567892\n"
                "```\n\n"
                "**OR** send Telegram links:\n"
                "```\n"
                "https://t.me/channel1\n"
                "@channel2\n"
                "t.me/channel3\n"
                "```\n\n"
                "**💡 One per line or comma separated**",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
            bot_state.broadcast_state[user_id] = {"step": "bulk_add_waiting"}
            
            # Auto-delete instruction after 2 minutes
            if sent_msg:
                threading.Timer(120, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()

        elif call.data == "cancel_bulk_add":
            if user_id in bot_state.broadcast_state:
                del bot_state.broadcast_state[user_id]
            bot.send_message(user_id, "❌ Bulk add operation cancelled.")

        elif call.data == "stop_all_broadcasts":
            # Stop all broadcasts and delete all messages for this user
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Yes, Stop & Delete All", callback_data="confirm_stop_all"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_stop_all"),
            )
            
            bot.send_message(
                user_id,
                "🛑 **STOP ALL BROADCASTS**\n\n"
                "**This will:**\n"
                "• ⏹ Stop all running auto-reposts\n"
                "• 🗑 Delete ALL broadcast messages from channels\n"
                "• 🧹 Clear all scheduled tasks\n"
                "• ❌ **Cannot be undone!**\n\n"
                "**Are you sure?**",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        elif call.data == "confirm_stop_all":
            try:
                # Stop all reposts for this user
                if user_id in bot_state.active_reposts:
                    bot_state.active_reposts[user_id]["stop"] = True
                    
                # Stop active broadcasts
                if user_id in bot_state.active_broadcasts:
                    del bot_state.active_broadcasts[user_id]
                
                # Get all broadcast messages for this user and delete them
                if broadcast_bot.broadcast_messages_col is not None:
                    broadcast_messages = list(broadcast_bot.broadcast_messages_col.find({"user_id": user_id}))
                else:
                    broadcast_messages = []
                
                status_msg = bot.send_message(
                    user_id,
                    f"🛑 **Stopping all broadcasts...**\n\n"
                    f"📊 Found {len(broadcast_messages)} messages to delete\n"
                    f"⏳ Processing...",
                    parse_mode="Markdown"
                )
                
                deleted_count = 0
                already_deleted_count = 0
                no_permission_count = 0
                failed_count = 0
                failed_channels = []
                
                for msg_doc in broadcast_messages:
                    try:
                        result = bot.delete_message(msg_doc["channel_id"], msg_doc["message_id"])
                        if result:
                            deleted_count += 1
                        else:
                            already_deleted_count += 1
                        
                        # Remove from database regardless of deletion result
                        if broadcast_bot.broadcast_messages_col is not None:
                            broadcast_bot.broadcast_messages_col.delete_one({"_id": msg_doc["_id"]})
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        # Classify the error
                        if "message to delete not found" in error_msg or "message not found" in error_msg:
                            already_deleted_count += 1
                            # Still remove from database since message doesn't exist
                            if broadcast_bot.broadcast_messages_col is not None:
                                broadcast_bot.broadcast_messages_col.delete_one({"_id": msg_doc["_id"]})
                        elif "forbidden" in error_msg or "not enough rights" in error_msg or "no permission" in error_msg:
                            no_permission_count += 1
                            failed_channels.append(str(msg_doc["channel_id"]))
                        else:
                            failed_count += 1
                            failed_channels.append(str(msg_doc["channel_id"]))
                            logger.warning(f"Failed to delete message {msg_doc['message_id']} from {msg_doc['channel_id']}: {e}")
                
                # Clear scheduled tasks for this user
                if broadcast_bot.scheduled_broadcasts_col is not None:
                    broadcast_bot.scheduled_broadcasts_col.delete_many({"user_id": user_id})
                
                # Update status
                result_text = f"""
🛑 **All Broadcasts Stopped!** ✅

**📊 Results:**
• ✅ **Deleted:** {deleted_count} messages
• 🗑 **Already Deleted:** {already_deleted_count} messages
• 🚫 **No Permission:** {no_permission_count} messages
• ❌ **Failed:** {failed_count} messages
• 🧹 **Cleared:** All scheduled tasks
• ⏹ **Stopped:** All active reposts

**🎯 All operations completed!**
                """
                
                if no_permission_count > 0 or failed_count > 0:
                    failed_list = ', '.join(set(failed_channels[:10]))
                    if len(set(failed_channels)) > 10:
                        failed_list += f" and {len(set(failed_channels)) - 10} more"
                    result_text += f"\n\n🚫 **Channels with Issues:**\n`{failed_list}`"
                
                bot.edit_message_text(result_text, user_id, status_msg.message_id, parse_mode="Markdown")
                
                # Auto-delete result after 30 seconds
                threading.Timer(30, lambda: delete_message_safe(user_id, status_msg.message_id)).start()
                
            except Exception as e:
                logger.error(f"Error in stop_all_broadcasts: {e}")
                bot.send_message(user_id, "❌ Error stopping broadcasts. Please try again.")

        elif call.data == "cancel_stop_all":
            bot.send_message(user_id, "❌ Stop operation cancelled.")

        elif call.data == "cleanup_menu":
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

def create_broadcast_config_ui(user_id: int, message, added_channels: list = None) -> tuple:
    """Create clean broadcast configuration UI"""
    original_text = message.text or message.caption or ""
    
    # Create message text
    message_text = "📢 **Broadcast Configuration**\n\n"
    
    if added_channels:
        channel_list = "\n".join([f"• **{ch['channel_name']}** (@{ch['username'] or 'private'})" for ch in added_channels])
        message_text += f"✅ **Auto-added {len(added_channels)} channels:**\n{channel_list}\n\n"
        
        original_links = extract_telegram_links(original_text)
        if original_links:
            links_text = "\n".join([f"🔗 `{link}`" for link in original_links])
            message_text += f"🔍 **Detected Links:**\n{links_text}\n\n"

    if original_text:
        preview_text = original_text[:100] + "..." if len(original_text) > 100 else original_text
        message_text += f"📝 **Broadcast Text:**\n`{preview_text}`\n\n"

    message_text += "⚙️ **Configure your broadcast:**\n\n"

    # Create clean markup
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Main options
    markup.add(
        types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
        types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time")
    )
    markup.add(
        types.InlineKeyboardButton("📤 Send Now (No Auto)", callback_data="send_now"),
        types.InlineKeyboardButton("⚙️ Advanced Settings", callback_data="advanced_settings")
    )
    
    return message_text, markup

def start_broadcast_flow_from_message(user_id: int, message):
    """Start broadcast flow directly from an incoming message with clean UI."""
    logger.info(f"Starting broadcast flow for user {user_id}, content_type: {message.content_type}")
    
    state = bot_state.broadcast_state.get(user_id, {})
    state["message"] = message
    state["step"] = "configuring"

    original_text = message.text or message.caption or ""
    logger.info(f"Original text: {original_text[:50]}...")

    # Auto-add channels
    added_channels = []
    if original_text:
        try:
            added_channels = auto_add_telegram_links(user_id, original_text)
            logger.info(f"Auto-added {len(added_channels)} channels")
        except Exception as e:
            logger.warning(f"auto_add_telegram_links failed: {e}")

    state["formatted_text"] = original_text
    state["format_type"] = "plain"
    bot_state.broadcast_state[user_id] = state

    # Create clean UI
    message_text, markup = create_broadcast_config_ui(user_id, message, added_channels)

    try:
        sent_msg = bot.send_message(user_id, message_text, reply_markup=markup, parse_mode="Markdown")
        if sent_msg:
            threading.Timer(120, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()
        logger.info(f"Broadcast flow message sent successfully to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send broadcast flow message to user {user_id}: {e}")
        try:
            bot.send_message(user_id, "📢 Send your broadcast message:")
        except Exception as e2:
            logger.error(f"Fallback message also failed: {e2}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Advanced message handler with improved broadcast flow"""
    user_id = message.chat.id
    
    try:
        state = bot_state.broadcast_state.get(user_id)

        # Handle custom time input
        if state and state.get("step") in ["ask_repost_custom_time", "ask_delete_custom_time"]:
            try:
                time_input = message.text.strip()
                if time_input.isdigit():
                    time_value = int(time_input)
                    if 1 <= time_value <= 43200:  # 1 minute to 30 days
                        if state["step"] == "ask_repost_custom_time":
                            state["repost_time"] = time_value
                            state["step"] = "repost_time_selected"
                            bot.send_message(user_id, f"✅ **Auto Repost set to {time_value} minutes!**", parse_mode="Markdown")
                        else:  # ask_delete_custom_time
                            state["delete_time"] = time_value
                            state["step"] = "delete_time_selected"
                            bot.send_message(user_id, f"✅ **Auto Delete set to {time_value} minutes!**", parse_mode="Markdown")
                        
                        bot_state.broadcast_state[user_id] = state
                        
                        # Delete the user's input message
                        try:
                            bot.delete_message(user_id, message.message_id)
                        except:
                            pass
                        
                        # Show next step or final confirmation
                        if state.get("repost_time") and state.get("delete_time"):
                            # Both are set, show final confirmation
                            markup = types.InlineKeyboardMarkup(row_width=2)
                            markup.add(
                                types.InlineKeyboardButton("🚀 Start Broadcast", callback_data="start_broadcast"),
                                types.InlineKeyboardButton("⚙️ Change Settings", callback_data="advanced_settings")
                            )
                            
                            final_text = f"""
<b>🎯 BROADCAST READY!</b>

<blockquote><b>✅ CONFIGURATION COMPLETE</b>
• <b>Auto Repost:</b> {state.get('repost_time')} minutes
• <b>Auto Delete:</b> {state.get('delete_time')} minutes</blockquote>

<b>🚀 Ready to broadcast!</b>
                            """
                            bot.send_message(user_id, final_text, reply_markup=markup, parse_mode="HTML")
                        else:
                            # Show current status
                            markup = types.InlineKeyboardMarkup(row_width=2)
                            if not state.get("repost_time"):
                                markup.add(types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"))
                            if not state.get("delete_time"):
                                markup.add(types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time"))
                            markup.add(types.InlineKeyboardButton("📤 Send Now", callback_data="send_now"))
                            
                            status_text = f"""
<b>⚙️ BROADCAST CONFIGURATION</b>

<blockquote><b>✅ CURRENT SETTINGS</b>
• <b>Auto Repost:</b> {'✅ Set' if state.get('repost_time') else '❌ Not Set'}
• <b>Auto Delete:</b> {'✅ Set' if state.get('delete_time') else '❌ Not Set'}</blockquote>

<b>💡 Next step:</b>
                            """
                            bot.send_message(user_id, status_text, reply_markup=markup, parse_mode="HTML")
                        
                        return
                    else:
                        bot.send_message(user_id, "❌ **Invalid time!** Please enter a number between 1 and 43200 minutes.", parse_mode="Markdown")
                else:
                    bot.send_message(user_id, "❌ **Invalid input!** Please enter a number (in minutes).", parse_mode="Markdown")
                
                # Delete the user's input message
                try:
                    bot.delete_message(user_id, message.message_id)
                except:
                    pass
                return
            except Exception as e:
                logger.error(f"Error handling custom time input: {e}")
                bot.send_message(user_id, "❌ **Error processing input!** Please try again.", parse_mode="Markdown")
                return

        # Auto-start broadcast flow if user sends text/media with caption in private chat
        if not state and message.chat.type == 'private' and (getattr(message, 'text', None) or getattr(message, 'caption', None) or message.content_type in ["photo", "video", "document"]):
            logger.info(f"Auto-starting broadcast flow for user {user_id}, content_type: {message.content_type}")
            start_broadcast_flow_from_message(user_id, message)
            return

        # Handle broadcast state
        if state and state.get("step") == "waiting_msg":
            state["message"] = message
            state["step"] = "ask_repost"
            
            # Store original text as formatted text
            original_text = message.text or message.caption or ""
            
            # Auto-add Telegram links as channels but PRESERVE original text
            added_channels = []
            if original_text:
                added_channels = auto_add_telegram_links(user_id, original_text)
            
            # Store ORIGINAL text for broadcasting (don't remove links!)
            state["formatted_text"] = original_text
            state["format_type"] = "plain"
            
            # Create enhanced broadcast configuration UI
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Main configuration buttons
            markup.add(
                types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
                types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time")
            )
            markup.add(
                types.InlineKeyboardButton("📤 Send Now (No Auto)", callback_data="send_now"),
                types.InlineKeyboardButton("⚙️ Advanced Settings", callback_data="advanced_settings")
            )
            
            # Prepare message with auto-added channels info
            repost_message = (
                f"<b>📢 BROADCAST CONFIGURATION</b>\n\n"
                f"<blockquote><b>⚙️ CONFIGURE YOUR BROADCAST</b>\n"
                f"Set up auto-repost and auto-delete settings for your message</blockquote>"
            )
            
            if added_channels:
                channel_list = "\n".join([f"• <b>{ch['channel_name']}</b> (@{ch['username'] or 'private'})" for ch in added_channels])
                repost_message += f"\n\n<b>✅ AUTO-ADDED {len(added_channels)} CHANNELS</b>\n<blockquote>{channel_list}</blockquote>"
                
                # Show original links that were detected
                original_links = extract_telegram_links(original_text)
                if original_links:
                    links_text = "\n".join([f"🔗 <code>{link}</code>" for link in original_links])
                    repost_message += f"\n\n<b>🔍 DETECTED LINKS</b>\n<blockquote>{links_text}</blockquote>"
                
                # Show what text will be broadcasted
                if original_text:
                    preview_text = original_text[:100] + "..." if len(original_text) > 100 else original_text
                    repost_message += f"\n\n<b>📝 BROADCAST TEXT</b>\n<blockquote><code>{preview_text}</code></blockquote>"
            
            sent_msg = bot.send_message(
                user_id, 
                repost_message,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            # Auto-delete repost question after 60 seconds
            if sent_msg:
                threading.Timer(60, lambda: delete_message_safe(user_id, sent_msg.message_id)).start()
            return

        if state and state.get("step") == "add_single_channel":
            # Handle single channel addition
            message_text = message.text or ""
            
            try:
                added_channel = None
                error_message = ""
                
                if message_text.startswith('-100') or message_text.startswith('-'):
                    # Direct channel ID
                    try:
                        channel_id = int(message_text)
                        channel_info = bot.get_chat(channel_id)
                        if channel_info:
                            added_channel = {
                                "channel_id": channel_id,
                                "channel_name": channel_info.title,
                                "username": getattr(channel_info, 'username', None)
                            }
                        else:
                            error_message = "❌ Channel not found!"
                    except ValueError:
                        error_message = "❌ Invalid channel ID format!"
                    except Exception as e:
                        error_message = f"❌ Error: {str(e)}"
                        
                elif message_text.startswith('@'):
                    # Channel username
                    try:
                        username = message_text[1:]  # Remove @
                        channel_info = bot.get_chat(f"@{username}")
                        added_channel = {
                            "channel_id": channel_info.id,
                            "channel_name": channel_info.title,
                            "username": username
                        }
                    except Exception as e:
                        error_message = f"❌ Channel not found: {str(e)}"
                        
                elif 't.me/' in message_text:
                    # Channel link
                    try:
                        resolved = resolve_telegram_link(message_text)
                        if resolved:
                            added_channel = resolved
                        else:
                            error_message = "❌ Invalid channel link!"
                    except Exception as e:
                        error_message = f"❌ Error resolving link: {str(e)}"
                        
                else:
                    error_message = "❌ Invalid format! Send channel ID, username, or link."
                
                if added_channel:
                    # Check if bot is admin
                    try:
                        bot_user = bot.get_me()
                        chat_member = bot.get_chat_member(added_channel["channel_id"], bot_user.id)
                        if chat_member.status not in ['administrator', 'creator']:
                            error_message = "❌ Bot is not admin in this channel! Add bot as admin first."
                            added_channel = None
                    except Exception as e:
                        error_message = f"❌ Cannot check admin status: {str(e)}"
                        added_channel = None
                
                if added_channel:
                    # Add to database
                    broadcast_bot.add_channel(user_id, added_channel["channel_id"], added_channel["channel_name"], added_channel.get("username"))
                    
                    result_message = f"✅ **Channel Added Successfully!**\n\n"
                    result_message += f"**📢 Channel:** {added_channel['channel_name']}\n"
                    result_message += f"**🆔 ID:** `{added_channel['channel_id']}`\n"
                    result_message += f"**👤 Username:** @{added_channel['username'] or 'private'}\n\n"
                    result_message += "🎉 **Channel is ready for broadcasting!**"
                    
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("➕ Add Another", callback_data="add_single_channel"),
                        types.InlineKeyboardButton("📢 Start Broadcast", callback_data="broadcast"),
                    )
                    
                    bot.send_message(user_id, result_message, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.send_message(user_id, f"❌ **Failed to add channel!**\n\n{error_message}")
                
                # Clear the state
                bot_state.broadcast_state[user_id] = {}
                
            except Exception as e:
                logger.error(f"Error in add_single_channel: {e}")
                bot.send_message(user_id, f"❌ **Error occurred:** {str(e)}")
                bot_state.broadcast_state[user_id] = {}
            return

        if state and state.get("step") == "bulk_add_waiting":
            # Handle bulk channel addition
            message_text = message.text or ""
            
            # Parse channel IDs and links
            lines = message_text.replace(',', '\n').split('\n')
            lines = [line.strip() for line in lines if line.strip()]
         
            added_channels = []
            failed_channels = []
            
            for line in lines:
                try:
                    if line.startswith('-100') or line.startswith('-'):
                        # Direct channel ID
                        channel_id = int(line)
                        channel_info = bot.get_chat(channel_id)
                        if channel_info:
                            added_channels.append({
                                "channel_id": channel_id,
                                "channel_name": channel_info.title,
                                "username": getattr(channel_info, 'username', None)
                            })
                        else:
                            # Try to resolve as link
                            resolved = resolve_telegram_link(line)
                            if resolved:
                                added_channels.append(resolved)
                            else:
                                failed_channels.append(line)
                except Exception as e:
                    logger.warning(f"Failed to add channel {line}: {e}")
                    failed_channels.append(line)
            
            # Add channels to database
            for ch in added_channels:
                broadcast_bot.add_channel(user_id, ch["channel_id"], ch["channel_name"], ch.get("username"))
            
            # Send result
            result_message = f"✅ **Bulk Channel Addition Complete!**\n\n"
            if added_channels:
                channel_list = "\n".join([f"• **{ch['channel_name']}** (@{ch['username'] or 'private'})" for ch in added_channels])
                result_message += f"✅ **Added {len(added_channels)} channels:**\n{channel_list}\n\n"
            
            if failed_channels:
                failed_list = "\n".join([f"• `{ch}`" for ch in failed_channels])
                result_message += f"❌ **Failed to add {len(failed_channels)} channels:**\n{failed_list}\n\n"
            
            result_message += "🔄 **Continue with broadcast setup:**"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔄 Continue Setup", callback_data="continue_setup"),
                types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast"),
            )
            
            bot.send_message(user_id, result_message, reply_markup=markup, parse_mode="Markdown")
            state["step"] = "setup_complete"
            return

        # If no state and in private chat, start broadcast flow
        if message.chat.type == 'private' and not state:
            logger.info(f"Starting broadcast flow for user {user_id} in private chat")
            start_broadcast_flow_from_message(user_id, message)
            return

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        try:
            bot.send_message(user_id, "❌ **Error occurred!**\n\nPlease try again or contact support.")
        except:
            pass

def track_bot_message(user_id: int, message_id: int):
    """Track bot messages for later deletion"""
    try:
        if bot_messages_col is not None:
            bot_messages_col.insert_one({
                "user_id": user_id,
                "message_id": message_id,
                "timestamp": datetime.now()
            })
    except Exception as e:
        logger.warning(f"Failed to track bot message: {e}")

def delete_bot_messages(user_id: int):
    """Delete all tracked bot messages for a user"""
    deleted_count = 0
    try:
        # Get all tracked bot messages for this user
        if bot_messages_col is not None:
            bot_messages = list(bot_messages_col.find({"user_id": user_id}))
        else:
            bot_messages = []
        
        for msg in bot_messages:
            try:
                if bot.delete_message(user_id, msg["message_id"]):
                    deleted_count += 1
            except Exception as e:
                # Ignore errors for bot message deletion
                pass
        
        # Clear tracked messages from database
        if bot_messages_col is not None:
            bot_messages_col.delete_many({"user_id": user_id})

    except Exception as e:
        logger.warning(f"Failed to delete bot messages: {e}")
    
    return deleted_count

if __name__ == "__main__":
    logger.info("Advanced Broadcast Bot starting...")
    
    try:
        # Start background tasks only if MongoDB is available
        if broadcast_bot.scheduled_broadcasts_col is not None:
            logger.info("Starting background tasks...")
            
            # Start scheduled broadcasts checker
            import threading
            scheduled_thread = threading.Thread(target=broadcast_bot.check_scheduled_broadcasts, daemon=True)
            scheduled_thread.start()
            logger.info("Scheduled broadcasts checker started")
            
            
            # Update analytics on startup
            try:
                broadcast_bot.update_analytics("active_users", 0)
                logger.info("Analytics updated successfully")
            except Exception as e:
                logger.error(f"Error updating analytics: {e}")
        else:
            logger.warning("MongoDB not available - running in limited mode")
        
        # Remove any existing webhook (optional)
        try:
            bot.remove_webhook()
            logger.info("Webhook removed successfully")
        except Exception as e:
            logger.warning(f"Failed to remove webhook (continuing anyway): {e}")
        
        # Start bot polling with retry mechanism
        logger.info("Starting bot polling...")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=60)
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Bot polling error (attempt {retry_count}/{max_retries}): {e}")
                
                if "409" in str(e) or "Conflict" in str(e):
                    logger.warning("409 Conflict detected - another bot instance may be running")
                    if retry_count < max_retries:
                        logger.info(f"Waiting 10 seconds before retry {retry_count + 1}...")
                        time.sleep(10)
                    else:
                        logger.error("Max retries reached. Please check if another bot instance is running.")
                        break
                else:
                    logger.error(f"Unexpected error: {e}")
                    break
        
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        logger.error(f"Error details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
