#!/usr/bin/env python3
"""
Advanced Telegram Broadcast Bot - Enhanced Version
Features: Auto Repost, Auto Delete, Scheduled Broadcasts, Analytics, Multi-Channel Management
Author: ANKIT
Version: 3.0 - Enhanced with Plugin Architecture
"""

import os
import sys
import time
import logging
import threading
import schedule
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add plugins directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))

import telebot
from telebot import types
from pymongo import MongoClient
from dotenv import load_dotenv
import requests

# Import configuration
from config import *

# Import plugins
from plugins.database import DatabaseConnection, DatabaseOperations
from plugins.utils import LinkHandler, MessageFormatter, Validators, Helpers, setup_logger, ChannelDetector
from plugins.broadcast import BroadcastManager

# Configure logging
logger = setup_logger("MainBot", LOG_LEVEL, LOG_FILE)

class AdvancedBroadcastBot:
    """Enhanced Telegram Broadcast Bot with Plugin Architecture"""
    
    def __init__(self):
        self.bot = None
        self.db_connection = None
        self.db_ops = None
        self.broadcast_manager = None
        self.link_handler = None
        self.message_formatter = None
        self.validators = Validators()
        self.helpers = Helpers()
        
        # Bot state management
        self.broadcast_states = {}
        self.active_broadcasts = {}
        self.scheduled_tasks = {}
        self.user_messages = {}  # Store user messages temporarily for broadcasting
        self.user_preferences = {}  # Store user preferences temporarily
        
        # Initialize components
        self._initialize_database()
        self._initialize_bot()
        self._initialize_plugins()
        self._setup_handlers()
        
    def _initialize_database(self):
        """Initialize database connection and operations"""
        try:
            self.db_connection = DatabaseConnection()
            if self.db_connection.connect():
                self.db_ops = DatabaseOperations()
                logger.info("✅ Database initialized successfully")
            else:
                logger.error("❌ Database initialization failed")
                raise Exception("Database connection failed")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            raise
    
    def _initialize_bot(self):
        """Initialize Telegram bot"""
        try:
            self.bot = telebot.TeleBot(BOT_TOKEN)
            logger.info("✅ Bot initialized successfully")
        except Exception as e:
            logger.error(f"❌ Bot initialization error: {e}")
            raise
    
    def _initialize_plugins(self):
        """Initialize all plugins"""
        try:
            # Initialize broadcast manager
            self.broadcast_manager = BroadcastManager(self.bot, self.db_ops)
            
            # Initialize utilities
            self.link_handler = LinkHandler(self.bot)
            self.message_formatter = MessageFormatter()
            self.channel_detector = ChannelDetector(self.bot)
            
            logger.info("✅ All plugins initialized successfully")
        except Exception as e:
            logger.error(f"❌ Plugin initialization error: {e}")
            raise
    
    def _setup_handlers(self):
        """Setup all message and callback handlers"""
        try:
            # Command handlers
            @self.bot.message_handler(commands=["start", "help"])
            def start_command(message):
                self._handle_start_command(message)
            
            @self.bot.message_handler(commands=["stats", "analytics"])
            def stats_command(message):
                self._handle_stats_command(message)
            
            @self.bot.message_handler(commands=["premium"])
            def premium_command(message):
                self._handle_premium_command(message)
            
            @self.bot.message_handler(commands=["add"])
            def add_command(message):
                self._handle_add_command(message)
            
            @self.bot.message_handler(commands=["channels"])
            def channels_command(message):
                self._handle_channels_command(message)
            
            @self.bot.message_handler(commands=["broadcast"])
            def broadcast_command(message):
                self._handle_broadcast_command(message)
            
            @self.bot.message_handler(commands=["stop"])
            def stop_command(message):
                self._handle_stop_command(message)
            
            @self.bot.message_handler(commands=["cleanup", "clear"])
            def cleanup_command(message):
                self._handle_cleanup_command(message)
            
            @self.bot.message_handler(commands=["id"])
            def id_command(message):
                self._handle_id_command(message)
            
            # Admin commands
            @self.bot.message_handler(commands=["admin"])
            def admin_command(message):
                self._handle_admin_command(message)
            
            # Callback query handler
            @self.bot.callback_query_handler(func=lambda call: True)
            def callback_handler(call):
                self._handle_callback_query(call)
            
            # Forward message handler (for getting channel IDs)
            @self.bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note', 'sticker', 'animation'], func=lambda message: message.forward_from_chat is not None)
            def forward_handler(message):
                self._handle_forward_message(message)
            
            # Main message handler
            @self.bot.message_handler(func=lambda message: True)
            def message_handler(message):
                self._handle_message(message)
            
            logger.info("✅ All handlers setup successfully")
        except Exception as e:
            logger.error(f"❌ Handler setup error: {e}")
            raise
    
    def _handle_start_command(self, message):
        """Handle /start command"""
        try:
            user_id = message.from_user.id
            
            # Add user to database
            self.db_ops.add_user(
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            # Create welcome message
            welcome_text = self._create_welcome_message(user_id)
            markup = self._create_main_menu_keyboard(user_id)
            
            self.bot.send_message(
                user_id,
                welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            self.bot.send_message(message.chat.id, "❌ An error occurred. Please try again.")
    
    def _handle_stats_command(self, message):
        """Handle /stats command"""
        try:
            user_id = message.from_user.id
            analytics = self.db_ops.get_user_analytics(user_id)
            
            stats_text = self.message_formatter.format_analytics_summary(analytics)
            markup = self._create_stats_keyboard()
            
            self.bot.send_message(
                user_id,
                stats_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error retrieving statistics.")
    
    def _handle_premium_command(self, message):
        """Handle /premium command - All features are now free!"""
        try:
            user_id = message.from_user.id
            
            free_text = self._create_free_features_message()
            markup = self._create_free_features_keyboard()
            
            self.bot.send_message(
                user_id,
                free_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in premium command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading features information.")
    
    def _handle_add_command(self, message):
        """Handle /add command"""
        try:
            user_id = message.from_user.id
            
            add_text = self._create_add_channels_message()
            markup = self._create_add_channels_keyboard()
            
            self.bot.send_message(
                user_id,
                add_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Error in add command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading add channels interface.")
    
    def _handle_channels_command(self, message):
        """Handle /channels command"""
        try:
            user_id = message.from_user.id
            channels = self.db_ops.get_user_channels(user_id)
            
            channels_text = self._create_channels_list_message(channels)
            markup = self._create_channels_keyboard()
            
            self.bot.send_message(
                user_id,
                channels_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in channels command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading channels.")
    
    def _handle_broadcast_command(self, message):
        """Handle /broadcast command"""
        try:
            user_id = message.from_user.id
            channels = self.db_ops.get_user_channels(user_id)
            
            if not channels:
                self.bot.send_message(
                    user_id,
                    "❌ <b>No channels found!</b>\n\n<blockquote>Please add channels first using /add command.</blockquote>",
                    parse_mode="HTML"
                )
                return
    
            broadcast_text = self._create_broadcast_message()
            markup = self._create_broadcast_keyboard()
            
            self.bot.send_message(
                user_id,
                broadcast_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in broadcast command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading broadcast interface.")
    
    def _handle_stop_command(self, message):
        """Handle /stop command"""
        try:
            user_id = message.from_user.id
            result = self.broadcast_manager.stop_broadcast(user_id)
            
            self.bot.send_message(
                user_id,
                result["message"],
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error stopping broadcast.")
    
    def _handle_cleanup_command(self, message):
        """Handle /cleanup command"""
        try:
            user_id = message.from_user.id
            
            cleanup_text = self._create_cleanup_message()
            markup = self._create_cleanup_keyboard()
            
            self.bot.send_message(
                user_id,
                cleanup_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in cleanup command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading cleanup interface.")
    
    def _handle_id_command(self, message):
        """Handle /id command - works in both private and channels"""
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            message_id = message.message_id
            
            # Check if it's a private chat or channel/group
            if message.chat.type == 'private':
                # Private chat - show user and chat ID
                id_text = f"""
🆔 <b>ID Information</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
👤 <b>Your User ID:</b> <code>{user_id}</code>
💬 <b>Chat ID:</b> <code>{chat_id}</code>
📨 <b>Message ID:</b> <code>{message_id}</code>
</blockquote>

📋 <b>How to get Channel ID:</b>
<code>1. Add bot to your channel as admin</code>
<code>2. Send /id command in the channel</code>
<code>3. Bot will reply with channel ID</code>
<code>4. Use that ID to add channel!</code>

💡 <b>Pro Tip:</b> You can also forward any channel message to bot to get ID!
            """.strip()
            
                self.bot.send_message(chat_id, id_text, parse_mode="HTML")
            
            else:
                # Channel or group - show comprehensive info
                chat_info = self.bot.get_chat(chat_id)
                
                # Get channel/group details
                chat_title = getattr(chat_info, 'title', 'Unknown')
                chat_username = getattr(chat_info, 'username', None)
                chat_type = getattr(chat_info, 'type', 'unknown')
                member_count = getattr(chat_info, 'member_count', 'Unknown')
                
                id_text = f"""
🆔 <b>Channel/Group ID Information</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

📋 <b>Chat Details:</b>
• <b>Name:</b> {chat_title}
• <b>ID:</b> <code>{chat_id}</code>
• <b>Type:</b> {chat_type.title()}
• <b>Username:</b> @{chat_username or 'Private'}
• <b>Members:</b> {member_count}

👤 <b>Your Info:</b>
• <b>User ID:</b> <code>{user_id}</code>
• <b>Message ID:</b> <code>{message_id}</code>

🚀 <b>To add this channel to broadcast bot:</b>
<code>1. Copy the Chat ID above</code>
<code>2. Go to @ANKITBBBOT in private</code>
<code>3. Send the Chat ID to bot</code>
<code>4. Bot will automatically add this channel!</code>

💡 <b>Quick Add:</b> Send <code>{chat_id}</code> to @ANKITBBBOT
                """.strip()
                
                # Send reply in the channel/group
                self.bot.reply_to(message, id_text, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in id command: {e}")
            try:
                self.bot.send_message(message.chat.id, "❌ Error retrieving ID information.")
            except:
                # If we can't send to the chat, try replying to the message
                self.bot.reply_to(message, "❌ Error retrieving ID information.")
    
    def _handle_admin_command(self, message):
        """Handle /admin command"""
        try:
            user_id = message.from_user.id
            
            if user_id not in ADMIN_IDS:
                self.bot.send_message(
                    user_id, 
                    "❌ <b>Access Denied!</b>\n\n<blockquote>You don't have admin permissions.</blockquote>",
                    parse_mode="HTML"
                )
                return
            
            admin_text = self._create_admin_message()
            markup = self._create_admin_keyboard()

            self.bot.send_message(
                user_id,
                admin_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in admin command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading admin panel.")
    
    def _handle_callback_query(self, call):
        """Handle callback queries"""
        try:
            user_id = call.from_user.id
            data = call.data
            
            # Handle different callback types
            if data.startswith("add_channel_") or data in ["add_channels", "add_by_link", "bulk_add", "auto_detect_channels", "add_by_id"]:
                self._handle_add_channel_callback(call)
            elif data.startswith("remove_channel_"):
                self._handle_remove_channel_callback(call)
            elif data.startswith("broadcast_") or data in ["broadcast_start", "broadcast_status", "stop_broadcast"]:
                self._handle_broadcast_callback(call)
            elif data in ["set_repost_time", "set_delete_time", "send_now", "advanced_settings", "cancel_broadcast", "broadcast_config_back"] or data.startswith("repost_") or data.startswith("delete_"):
                self._handle_broadcast_config_callback(call)
            elif data.startswith("premium_") or data in ["features_info"]:
                self._handle_premium_callback(call)
            elif data.startswith("admin_") or data in ["admin_analytics", "admin_emergency_stop", "admin_panel", "admin_users", "admin_controls", "admin_logs", "admin_restart", "admin_detailed_stats", "admin_export_data"]:
                self._handle_admin_callback(call)
            elif data in ["main_menu"]:
                self._handle_main_menu_callback(call)
            elif data in ["my_channels", "show_stats", "settings"]:
                self._handle_navigation_callback(call)
            else:
                self.bot.answer_callback_query(call.id, "❌ Unknown action")
        except Exception as e:
            logger.error(f"Error in callback query: {e}")
            self.bot.answer_callback_query(call.id, "❌ An error occurred")
    
    def _handle_message(self, message):
        """Handle regular messages"""
        try:
            user_id = message.chat.id
            message_text = message.text or message.caption or ""
            
            # Check if user is in a custom time input state
            if user_id in self.broadcast_states:
                state = self.broadcast_states[user_id]
                if state.get("waiting_for") in ["custom_repost_time", "custom_delete_time"]:
                    logger.info(f"DEBUG: Processing custom time input from user {user_id}: '{message_text}'")
                    self._handle_custom_time_input(user_id, message_text, state)
                    return
            
            # Check for channel ID in message (format: -1001234567890)
            if message_text and message_text.strip().startswith('-') and message_text.strip().replace('-', '').isdigit():
                self._handle_channel_id_message(user_id, message_text.strip())
                return
            
            # Check if user has channels
            channels = self.db_ops.get_user_channels(user_id)
            if not channels:
                self.bot.send_message(
                    user_id,
                    "❌ <b>No channels found!</b>\n\n<blockquote>Please add channels first using /add command.</blockquote>",
                    parse_mode="HTML"
                )
                return
            
            # Auto-detect links and start broadcast flow
            if message.chat.type == 'private':
                self._start_broadcast_flow(user_id, message)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            self.bot.send_message(message.chat.id, "❌ An error occurred processing your message.")
    
    def _handle_forward_message(self, message):
        """Handle forwarded messages to extract channel IDs"""
        try:
            user_id = message.from_user.id
            forward_from_chat = message.forward_from_chat
            
            if forward_from_chat:
                channel_id = forward_from_chat.id
                channel_title = getattr(forward_from_chat, 'title', 'Unknown Channel')
                channel_username = getattr(forward_from_chat, 'username', None)
                channel_type = getattr(forward_from_chat, 'type', 'unknown')
                
                forward_info_text = f"""
🔍 <b>Forwarded Message Detected!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

📋 <b>Source Channel/Group:</b>
• <b>Name:</b> {channel_title}
• <b>ID:</b> <code>{channel_id}</code>
• <b>Type:</b> {channel_type.title()}
• <b>Username:</b> @{channel_username or 'Private'}

🚀 <b>Want to add this channel to your broadcast list?</b>

<blockquote>
💡 <b>Method 1 - Auto Add:</b>
Send this ID to me: <code>{channel_id}</code>
Bot will automatically add if you're admin!

💡 <b>Method 2 - Manual Add:</b>
1. Make sure bot is admin in this channel
2. Use /add command for step-by-step guide
</blockquote>

⚠️ <b>Note:</b> Bot must be admin in channel to add it for broadcasting.
                """.strip()
                
                self.bot.send_message(user_id, forward_info_text, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error handling forward message: {e}")
    
    def _start_broadcast_flow(self, user_id: int, message):
        """Start broadcast flow for a message"""
        try:
            # Store the message for broadcasting
            self.user_messages[user_id] = message
            
            # Auto-detect and add channels from links
            added_channels = self.link_handler.auto_add_telegram_links(
                user_id, message.text or message.caption or "", self.db_ops
            )
            
            # Get all user channels
            all_channels = self.db_ops.get_user_channels(user_id)
            
            # Create broadcast configuration UI
            broadcast_text = self._create_broadcast_config_message(message, added_channels, all_channels, user_id)
            markup = self._create_broadcast_config_keyboard()
            
            self.bot.send_message(
                user_id,
                broadcast_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error starting broadcast flow: {e}")
            self.bot.send_message(user_id, "❌ Error processing your message for broadcast.")
    
    def _handle_channel_id_message(self, user_id: int, channel_id_str: str):
        """Handle channel ID message and try to add channel"""
        try:
            # Validate channel ID
            channel_id = self.channel_detector.validate_channel_id(channel_id_str)
            
            if not channel_id:
                self.bot.send_message(
                    user_id,
                    f"❌ <b>Invalid Channel ID!</b>\n\n<blockquote>Received: <code>{channel_id_str}</code>\nPlease check the format and try again.</blockquote>",
                    parse_mode="HTML"
                )
                return
            
            # Try to add channel automatically
            result = self.channel_detector.auto_add_channel_if_admin(user_id, channel_id, self.db_ops)
            
            if result["success"]:
                # Success message
                channel_info = result["channel_info"]
                bot_status = result["bot_status"]
                
                success_text = f"""
✅ <b>Channel Added Successfully!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

📋 <b>Channel Details:</b>
• <b>Name:</b> {channel_info["title"]}
• <b>ID:</b> <code>{channel_info["channel_id"]}</code>
• <b>Type:</b> {channel_info["type"].title()}
• <b>Username:</b> @{channel_info["username"] or "Private"}

🤖 <b>Bot Status:</b>
• <b>Role:</b> {bot_status["status"].title()}
• <b>Can Post:</b> {'✅' if bot_status.get("can_post_messages") else '❌'}
• <b>Can Edit:</b> {'✅' if bot_status.get("can_edit_messages") else '❌'}
• <b>Can Delete:</b> {'✅' if bot_status.get("can_delete_messages") else '❌'}

🚀 <b>Ready to broadcast!</b> Send your message to start.
                """.strip()
                
                self.bot.send_message(user_id, success_text, parse_mode="HTML")
            else:
                # Error message
                error_text = f"""
❌ <b>Failed to Add Channel!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

🆔 <b>Channel ID:</b> <code>{channel_id_str}</code>
⚠️ <b>Error:</b> {result["error"]}

🔧 <b>Possible Solutions:</b>
• Make sure bot is admin in the channel
• Check if channel ID is correct
• Ensure channel is accessible
• Try adding bot manually to channel first

💡 <b>Need Help?</b>
Use /add command for step-by-step guide.
                """.strip()
                
                self.bot.send_message(user_id, error_text, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error handling channel ID message: {e}")
            self.bot.send_message(
                user_id,
                f"❌ <b>Error Processing Channel ID!</b>\n\n<blockquote>Received: <code>{channel_id_str}</code>\nPlease try again or contact support.</blockquote>",
                parse_mode="HTML"
            )
    
    # UI Creation Methods
    def _create_welcome_message(self, user_id: int) -> str:
        """Create welcome message"""
        user = self.db_ops.get_user(user_id)
        channels = self.db_ops.get_user_channels(user_id)
        
        user_name = "Unknown"
        if user and user.first_name:
            user_name = user.first_name
        elif user and user.username:
            user_name = f"@{user.username}"
        
        return f"""
🔥 <b>Welcome to Advanced Broadcast Bot!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

👋 <b>Hello {user_name}!</b>
📊 <b>Your Channels:</b> {len(channels)} connected

<blockquote>
🎉 <b>ALL FEATURES ARE FREE!</b>
No premium required - everything unlocked!
</blockquote>

🚀 <b>What You Can Do:</b>
┣ 📢 <b>Multi-Channel Broadcasting</b> - Send to unlimited channels
┣ ⚡ <b>Auto Repost & Delete</b> - Smart automation
┣ 📊 <b>Advanced Analytics</b> - Detailed insights  
┣ 🔗 <b>Auto Link Detection</b> - Smart channel adding
┣ ⏰ <b>Scheduled Posts</b> - Future broadcasting
┣ 🎨 <b>Rich Media Support</b> - Photos, videos, docs
┗ 📈 <b>Real-time Tracking</b> - Live progress

<b>🎯 Quick Start Guide:</b>
<code>1. Click "➕ Add Channels" below</code>
<code>2. Send your channel links</code>
<code>3. Create your message</code>
<code>4. Hit "📢 Broadcast" and go!</code>

💡 <b>Pro Tip:</b> Just send me a message with channel links - I'll auto-detect and add them!
        """.strip()
    
    def _create_main_menu_keyboard(self, user_id: int) -> types.InlineKeyboardMarkup:
        """Create main menu keyboard with attractive design"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Get user channel count for dynamic display
        channels = self.db_ops.get_user_channels(user_id)
        channel_count = len(channels)
        
        # First row - Main actions
        markup.add(
            types.InlineKeyboardButton("🚀 Start Broadcasting", callback_data="broadcast_start"),
            types.InlineKeyboardButton(f"➕ Add Channels ({channel_count})", callback_data="add_channels")
        )
        
        # Second row - Management
        markup.add(
            types.InlineKeyboardButton("📋 My Channels", callback_data="my_channels"),
            types.InlineKeyboardButton("📊 Analytics", callback_data="show_stats")
        )
        
        # Third row - Settings & Features
        markup.add(
            types.InlineKeyboardButton("🎨 Free Features", callback_data="features_info"),
            types.InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        )
        
        # Admin button if user is admin
        if user_id in ADMIN_IDS:
            markup.add(
                types.InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin_panel")
        )
        
        return markup
    
    def _create_broadcast_config_message(self, message, added_channels: List[Dict], all_channels: List[Dict], user_id: int = None) -> str:
        """Create broadcast configuration message"""
        message_type = message.content_type
        message_text = message.text or message.caption or ""
        
        # Get current user preferences
        repost_setting = "Not Set"
        delete_setting = "Not Set"
        
        if user_id and user_id in self.user_preferences:
            prefs = self.user_preferences[user_id]
            if "auto_repost_time" in prefs:
                repost_setting = prefs["auto_repost_time"]["display"]
            if "auto_delete_time" in prefs:
                delete_setting = prefs["auto_delete_time"]["display"]
        
        config_text = f"""
<b>📢 Broadcast Configuration</b>

<blockquote>
<b>📝 Message Type:</b> {message_type.title()}
<b>📊 Total Channels:</b> {len(all_channels)}
<b>➕ Auto-Added:</b> {len(added_channels)}
</blockquote>

<b>⚙️ Current Settings</b>
<blockquote>
<b>🔄 Auto Repost:</b> {repost_setting}
<b>🗑️ Auto Delete:</b> {delete_setting}
</blockquote>

<b>🔍 Message Preview</b>
<blockquote>{(message_text[:200] + '...') if len(message_text) > 200 else message_text}</blockquote>
        """.strip()
        
        if added_channels:
            channel_list = "\n".join([f"• <b>{ch['channel_name']}</b> (@{ch['username'] or 'private'})" for ch in added_channels])
            config_text += f"\n\n<b>✅ Auto-Added Channels</b>\n<blockquote>{channel_list}</blockquote>"
        
        return config_text
    
    def _create_broadcast_config_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create broadcast configuration keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
            types.InlineKeyboardButton("🗑️ Set Auto Delete", callback_data="set_delete_time")
        )
        markup.add(
            types.InlineKeyboardButton("📤 Send Now", callback_data="send_now"),
            types.InlineKeyboardButton("⚙️ Advanced", callback_data="advanced_settings")
        )
        markup.add(
            types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
        )
        
        return markup
    
    def _create_free_features_message(self) -> str:
        """Create free features message"""
        return """
🎉 **All Features Are Now FREE!**

<b>🚀 What You Get:</b>
• 📢 **Unlimited Broadcasting** - Send to unlimited channels
• ⚡ **Auto Repost & Delete** - Automated message management
• 📊 **Advanced Analytics** - Detailed performance tracking
• 🔗 **Auto Link Detection** - Automatically add channels from links
• ⏰ **Scheduled Broadcasts** - Schedule future messages
• 🎨 **Message Templates** - Pre-built message formats
• 📈 **Real-time Monitoring** - Live broadcast progress
• 🛠 **Bulk Operations** - Mass channel management
• 📱 **Multi-media Support** - Photos, videos, documents
• ⚙️ **Custom Settings** - Flexible configuration options

<b>💡 No Premium Required!</b>
All features are completely free for everyone. No hidden costs, no limitations!

<b>🚀 Ready to Start?</b>
Use the main menu to begin broadcasting!
        """.strip()
    
    def _create_free_features_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create free features keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("🚀 Start Broadcasting", callback_data="broadcast_start"),
            types.InlineKeyboardButton("➕ Add Channels", callback_data="add_channels"),
            types.InlineKeyboardButton("📊 View Analytics", callback_data="show_stats"),
            types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_stats_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create statistics keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats"),
            types.InlineKeyboardButton("📈 Export Data", callback_data="export_stats")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_add_channels_message(self) -> str:
        """Create add channels message"""
        return """
🔗 <b>Add Channels to Your Network</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🚀 <b>Choose Your Method:</b>
┣ 🔗 <b>Add by Link</b> - Paste individual channel links
┣ 📋 <b>Bulk Add</b> - Add multiple channels at once  
┗ 🤖 <b>Auto-Detect</b> - Send message with links
</blockquote>

📌 <b>Supported Link Formats:</b>
<code>• https://t.me/channelname</code>
<code>• @channelname</code>
<code>• t.me/channelname</code>
<code>• https://telegram.me/channelname</code>

⚠️ <b>Important Requirements:</b>
┣ 🤖 Bot must be admin in the channel
┣ 📢 Channel must be public or bot invited
┗ ✅ Valid Telegram channel link

💡 <b>Pro Tip:</b> You can add up to 1000 channels for FREE!
        """.strip()
    
    def _create_add_channels_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create add channels keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🔗 Add by Link", callback_data="add_by_link"),
            types.InlineKeyboardButton("📋 Bulk Add", callback_data="bulk_add")
        )
        markup.add(
            types.InlineKeyboardButton("🤖 Auto Detect", callback_data="auto_detect_channels"),
            types.InlineKeyboardButton("🆔 Add by ID", callback_data="add_by_id")
        )
        markup.add(
            types.InlineKeyboardButton("🔍 Validate Channels", callback_data="validate_channels"),
            types.InlineKeyboardButton("📊 Channel Stats", callback_data="channel_stats")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_channels_list_message(self, channels: List[Dict[str, Any]]) -> str:
        """Create channels list message"""
        if not channels:
            return """
📋 <b>Your Channels</b>

<blockquote>
No channels found. Use /add to add channels first.
</blockquote>

<b>🚀 Get Started:</b>
1. Click "➕ Add Channels" below
2. Paste your channel links
3. Start broadcasting!
            """.strip()
        
        message = f"📋 <b>Your Channels ({len(channels)})</b>\n\n"
        
        for i, channel in enumerate(channels[:10], 1):
            name = channel.get("channel_name", "Unknown")
            username = channel.get("username", "")
            broadcasts = channel.get("total_broadcasts", 0)
            success_rate = channel.get("success_rate", 100)
            
            channel_info = f"<b>{i}.</b> {name}"
            if username:
                channel_info += f" (@{username})"
            
            channel_info += f"\n   📊 {broadcasts} broadcasts • {success_rate:.1f}% success\n"
            message += channel_info
        
        if len(channels) > 10:
            message += f"\n<i>... and {len(channels) - 10} more channels</i>"
        
        return message
    
    def _create_channels_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create channels keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("➕ Add More", callback_data="add_channels"),
            types.InlineKeyboardButton("🗑️ Remove Channel", callback_data="remove_channel")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh List", callback_data="refresh_channels"),
            types.InlineKeyboardButton("📊 Channel Stats", callback_data="channel_stats")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_broadcast_message(self) -> str:
        """Create broadcast message"""
        return """
🚀 <b>Broadcast Control Center</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Ready to Broadcast!</b>
Send your message and I'll handle everything automatically!
</blockquote>

🔥 <b>Powerful Features Available:</b>
┣ 📱 <b>Rich Media Support</b> - Text, photos, videos, documents
┣ 🔗 <b>Smart Link Detection</b> - Auto-add channels from your message
┣ ⚡ <b>Auto Operations</b> - Repost & delete with timers
┣ 📊 <b>Live Progress</b> - Real-time tracking & analytics
┣ ⏰ <b>Schedule Posts</b> - Future broadcasting
┗ 🎨 <b>Custom Templates</b> - Pre-built message formats

<b>📋 Simple 3-Step Process:</b>
<code>1. 📝 Send your message (any media type)</code>
<code>2. ⚙️ Configure auto settings (optional)</code>
<code>3. 🚀 Hit "Send Now" and watch magic happen!</code>

💡 <b>Smart Tip:</b> Include channel links in your message - I'll detect and add them automatically!
        """.strip()
    
    def _create_broadcast_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create broadcast keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📊 Broadcast Status", callback_data="broadcast_status"),
            types.InlineKeyboardButton("🛑 Stop Broadcast", callback_data="stop_broadcast")
        )
        markup.add(
            types.InlineKeyboardButton("⏰ Schedule Broadcast", callback_data="schedule_broadcast"),
            types.InlineKeyboardButton("📋 Broadcast History", callback_data="broadcast_history")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_cleanup_message(self) -> str:
        """Create cleanup message"""
        return """
🧹 <b>Auto Cleanup System</b>

<blockquote>
Manage automatic message deletion and cleanup operations.
</blockquote>

<b>🎯 Available Options:</b>
• 🗑️ Delete Old Messages
• 🧹 Clean Database
• 📊 Cleanup Statistics
• ⚙️ Configure Auto-Delete

<b>⚠️ Warning:</b>
Cleanup operations cannot be undone. Please be careful!
        """.strip()
    
    def _create_cleanup_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create cleanup keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🗑️ Delete Old Messages", callback_data="delete_old_messages"),
            types.InlineKeyboardButton("🧹 Clean Database", callback_data="clean_database")
        )
        markup.add(
            types.InlineKeyboardButton("📊 Cleanup Stats", callback_data="cleanup_stats"),
            types.InlineKeyboardButton("⚙️ Auto-Delete Settings", callback_data="autodelete_settings")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _create_admin_message(self) -> str:
        """Create admin message"""
        try:
            # Get system stats
            stats = self.broadcast_manager.get_all_active_broadcasts()
            active_broadcasts = len(stats)
            
            return f"""
👨‍💼 <b>Admin Panel</b>

<blockquote>
<b>System Status:</b>
• 🔄 Active Broadcasts: {active_broadcasts}
• 📊 Database: Connected
• 🤖 Bot: Online
</blockquote>

<b>🛠️ Admin Functions:</b>
• 📊 System Analytics
• 👥 User Management
• 🔧 System Controls
• 📋 View Logs
            """.strip()
        except Exception as e:
            logger.error(f"Error creating admin message: {e}")
            return "👨‍💼 <b>Admin Panel</b>\n\nSystem status loading..."
    
    def _create_admin_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create admin keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📊 System Analytics", callback_data="admin_analytics"),
            types.InlineKeyboardButton("👥 User Management", callback_data="admin_users")
        )
        markup.add(
            types.InlineKeyboardButton("🔧 System Controls", callback_data="admin_controls"),
            types.InlineKeyboardButton("📋 View Logs", callback_data="admin_logs")
        )
        markup.add(
            types.InlineKeyboardButton("🛑 Emergency Stop", callback_data="admin_emergency_stop"),
            types.InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart")
        )
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
        )
        
        return markup
    
    def _handle_add_channel_callback(self, call):
        """Handle add channel callback"""
        try:
            user_id = call.from_user.id
            data = call.data
            
            if data == "add_channels":
                # Show add channels interface
                add_text = self._create_add_channels_message()
                markup = self._create_add_channels_keyboard()
                
                self.bot.edit_message_text(
                    add_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "➕ Add Channels")
            
            elif data == "add_by_link":
                # Prompt user to send channel links
                self.bot.answer_callback_query(call.id, "📨 Send me channel links!")
                
                instruction_text = """
📋 <b>Add Channels by Link</b>

<blockquote>
Send me your channel links in any of these formats:
• https://t.me/channelname
• @channelname
• t.me/channelname

You can send multiple links at once!
</blockquote>

<b>💡 Requirements:</b>
• Bot must be admin in the channel
• Channel must be public or you must invite bot

<b>🚀 Ready? Send your links!</b>
                """.strip()
                
                self.bot.send_message(user_id, instruction_text, parse_mode="HTML")
            
            elif data == "bulk_add":
                # Bulk add interface
                self.bot.answer_callback_query(call.id, "📋 Bulk Add Mode!")
                
                bulk_text = """
📋 <b>Bulk Add Channels</b>

<blockquote>
Send me multiple channel links separated by new lines:

@channel1
https://t.me/channel2
@channel3
t.me/channel4
</blockquote>

<b>💡 Tips:</b>
• One link per line
• Up to 50 channels at once
• Bot will validate each channel

<b>🚀 Send your channel list!</b>
                """.strip()
                
                self.bot.send_message(user_id, bulk_text, parse_mode="HTML")
            
            elif data == "auto_detect_channels":
                # Auto detect user's admin channels
                self.bot.answer_callback_query(call.id, "🤖 Auto Detection Guide!")
                
                auto_detect_text = """
🤖 <b>Auto Detect Your Admin Channels</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Coming Soon!</b>
This feature will automatically detect channels where you're admin and add bot directly!
</blockquote>

🔧 <b>For Now - Manual Method:</b>
<code>1. Go to your channel</code>
<code>2. Add @ANKITBBBOT as admin</code>
<code>3. Copy channel ID using /id command</code>
<code>4. Use "🆔 Add by ID" button below</code>

💡 <b>Channel ID Format:</b>
• Usually starts with -100
• Example: -1001234567890

🚀 <b>Future Update:</b>
Will scan all your chats and auto-add where you're admin!
                """.strip()
                
                self.bot.send_message(user_id, auto_detect_text, parse_mode="HTML")
            
            elif data == "add_by_id":
                # Add channel by ID
                self.bot.answer_callback_query(call.id, "🆔 Send Channel ID!")
                
                id_instruction_text = """
🆔 <b>Add Channel by ID</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Perfect for Private Channels!</b>
Add channels directly using their unique ID.
</blockquote>

📋 <b>How to Get Channel ID:</b>
<code>1. Go to your channel</code>
<code>2. Add @ANKITBBBOT as admin</code>
<code>3. Send any message in channel</code>
<code>4. Forward that message to this bot</code>
<code>5. Bot will show the channel ID</code>

💡 <b>Alternative Method:</b>
• Send /id command in your channel
• Copy the ID shown

🆔 <b>ID Format Examples:</b>
• <code>-1001234567890</code>
• <code>-100</code> prefix for supergroups
• <code>-</code> prefix for regular groups

🚀 <b>Ready? Send your channel ID now!</b>
                """.strip()
                
                self.bot.send_message(user_id, id_instruction_text, parse_mode="HTML")
            
            else:
                self.bot.answer_callback_query(call.id, "Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error handling add channel callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _handle_remove_channel_callback(self, call):
        """Handle remove channel callback"""
        try:
            self.bot.answer_callback_query(call.id, "Feature coming soon!")
        except Exception as e:
            logger.error(f"Error handling remove channel callback: {e}")
    
    def _handle_broadcast_callback(self, call):
        """Handle broadcast callback"""
        try:
            user_id = call.from_user.id
            
            if call.data == "broadcast_start":
                # Show broadcast interface
                channels = self.db_ops.get_user_channels(user_id)
                if not channels:
                    self.bot.edit_message_text(
                        "❌ No channels found! Please add channels first.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    return
                
                broadcast_text = self._create_broadcast_message()
                markup = self._create_broadcast_keyboard()
                
                self.bot.edit_message_text(
                    broadcast_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            
            elif call.data == "broadcast_status":
                # Show broadcast status
                status = self.broadcast_manager.get_broadcast_status(user_id)
                if status:
                    status_text = self.message_formatter.format_broadcast_status(status)
                    self.bot.answer_callback_query(call.id, "Status updated!")
                    self.bot.send_message(user_id, status_text, parse_mode="HTML")
                else:
                    self.bot.answer_callback_query(call.id, "No active broadcast found")
            
            elif call.data == "stop_broadcast":
                # Stop broadcast and cleanup messages
                self.bot.answer_callback_query(call.id, "🛑 Stopping broadcast and cleaning up...")
                
                # Step 1: Stop ongoing broadcast
                result = self.broadcast_manager.stop_broadcast(user_id)
                
                # Step 2: Stop all auto actions
                stopped_tasks = self._stop_user_auto_actions(user_id)
                
                # Step 3: Cleanup messages from channels
                deleted_count = self._stop_broadcast_and_cleanup(user_id)
                
                # Send confirmation message
                cleanup_text = f"""
🛑 <b>Broadcast Stopped & Cleaned Up!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
✅ <b>Broadcast Status:</b> {result.get('message', 'Stopped')}
🔄 <b>Auto Tasks Stopped:</b> {stopped_tasks}
🧹 <b>Messages Deleted:</b> {deleted_count}
</blockquote>

<b>📋 What was cleaned:</b>
┣ 🛑 Ongoing broadcast stopped
┣ ⏰ Auto repost/delete cancelled  
┗ 🗑️ Recent messages deleted from channels

<i>All channels are now clean and ready for new broadcasts!</i>
                """.strip()
                
                self.bot.send_message(user_id, cleanup_text, parse_mode="HTML")
            
            elif call.data == "schedule_broadcast":
                # Schedule broadcast feature
                schedule_text = """
⏰ <b>Schedule Broadcast</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🚀 <b>Coming Soon!</b>
Schedule your broadcasts for future delivery!
</blockquote>

<b>🎯 Planned Features:</b>
┣ 📅 <b>Date & Time Picker</b>
┣ 🔄 <b>Recurring Schedules</b> 
┣ ⏰ <b>Timezone Support</b>
┣ 📝 <b>Draft Management</b>
┗ 🔔 <b>Schedule Reminders</b>

💡 <b>For now:</b> Use the instant broadcast feature!
                """.strip()
                
                self.bot.edit_message_text(
                    schedule_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 Back to Broadcast", callback_data="broadcast_start")
                    ),
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📅 Schedule feature coming soon!")
            
            elif call.data == "broadcast_history":
                # Broadcast history
                broadcasts = self.db_ops.get_user_broadcasts(user_id)
                
                if not broadcasts:
                    history_text = """
📋 <b>Broadcast History</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📭 <b>No broadcasts found!</b>
You haven't sent any broadcasts yet.
</blockquote>

🚀 <b>Start your first broadcast:</b>
<code>1. Send me your message</code>
<code>2. I'll handle the rest!</code>

💡 <b>Tip:</b> All your broadcast history will appear here!
                    """.strip()
                else:
                    history_text = f"""
📋 <b>Broadcast History</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📊 <b>Total Broadcasts:</b> {len(broadcasts)}
</blockquote>

<b>🕐 Recent Broadcasts:</b>
                    """.strip()
                    
                    for i, broadcast in enumerate(broadcasts[:5]):  # Show last 5
                        status_emoji = "✅" if broadcast.get('status') == 'completed' else "⏳"
                        date = broadcast.get('created_date', 'Unknown')
                        history_text += f"\n{status_emoji} <b>#{i+1}</b> - {date}"
                
                self.bot.edit_message_text(
                    history_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 Back to Broadcast", callback_data="broadcast_start")
                    ),
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📊 History loaded!")
            
            else:
                self.bot.answer_callback_query(call.id, "Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error handling broadcast callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _handle_broadcast_config_callback(self, call):
        """Handle broadcast configuration callbacks"""
        try:
            user_id = call.from_user.id
            data = call.data
            
            if data == "set_repost_time":
                # Set auto repost time
                repost_text = """
⏰ <b>Auto Repost Settings</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🔄 <b>Auto Repost Feature</b>
Automatically repost your message after a set time interval!
</blockquote>

<b>🕐 Available Time Options:</b>
┣ ⚡ <b>5 Minutes</b> - Quick repost
┣ 🕐 <b>30 Minutes</b> - Half hour interval
┣ 🕐 <b>1 Hour</b> - Hourly repost
┣ 🕐 <b>3 Hours</b> - Every 3 hours
┣ 🕐 <b>6 Hours</b> - Every 6 hours
┣ 🕐 <b>12 Hours</b> - Twice daily
┗ 🕐 <b>24 Hours</b> - Daily repost

💡 <b>Pro Tip:</b> Choose interval based on your audience activity!
                """.strip()
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("⚡ 5 Min", callback_data="repost_5min"),
                    types.InlineKeyboardButton("🕐 30 Min", callback_data="repost_30min")
                )
                markup.add(
                    types.InlineKeyboardButton("🕐 1 Hour", callback_data="repost_1hour"),
                    types.InlineKeyboardButton("🕐 3 Hours", callback_data="repost_3hour")
                )
                markup.add(
                    types.InlineKeyboardButton("🕐 6 Hours", callback_data="repost_6hour"),
                    types.InlineKeyboardButton("🕐 12 Hours", callback_data="repost_12hour")
                )
                markup.add(
                    types.InlineKeyboardButton("🕐 24 Hours", callback_data="repost_24hour"),
                    types.InlineKeyboardButton("❌ Disable", callback_data="repost_disable")
                )
                markup.add(
                    types.InlineKeyboardButton("⏰ Custom Time", callback_data="repost_custom"),
                    types.InlineKeyboardButton("🔙 Back", callback_data="broadcast_config_back")
                )
                
                self.bot.edit_message_text(
                    repost_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "⏰ Set auto repost time!")
            
            elif data == "set_delete_time":
                # Set auto delete time
                delete_text = """
🗑️ <b>Auto Delete Settings</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🛡️ <b>Auto Delete Feature</b>
Automatically delete your message after broadcast completion!
</blockquote>

<b>⏱️ Available Delete Options:</b>
┣ ⚡ <b>Instant</b> - Delete immediately after send
┣ 🕐 <b>2 Minutes</b> - Very quick cleanup
┣ 🕐 <b>3 Minutes</b> - Short-term content
┣ 🕐 <b>10 Minutes</b> - Medium cleanup
┣ 🕐 <b>20 Minutes</b> - Extended visibility
┣ 🕐 <b>1 Hour</b> - Standard cleanup
┗ ♾️ <b>Never</b> - Keep messages forever

💡 <b>Tip:</b> Keep delete time shorter than repost time for clean channels!
⚠️ <b>Warning:</b> Deleted messages cannot be recovered!
                """.strip()
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("⚡ Instant", callback_data="delete_instant"),
                    types.InlineKeyboardButton("🕐 2 Min", callback_data="delete_2min")
                )
                markup.add(
                    types.InlineKeyboardButton("🕐 3 Min", callback_data="delete_3min"),
                    types.InlineKeyboardButton("🕐 10 Min", callback_data="delete_10min")
                )
                markup.add(
                    types.InlineKeyboardButton("🕐 20 Min", callback_data="delete_20min"),
                    types.InlineKeyboardButton("🕐 1 Hour", callback_data="delete_1hour")
                )
                markup.add(
                    types.InlineKeyboardButton("♾️ Never", callback_data="delete_never"),
                    types.InlineKeyboardButton("⏰ Custom Time", callback_data="delete_custom")
                )
                markup.add(
                    types.InlineKeyboardButton("🔙 Back", callback_data="broadcast_config_back")
                )
                
                self.bot.edit_message_text(
                    delete_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "🗑️ Set auto delete time!")
            
            elif data == "send_now":
                # Send broadcast now
                self.bot.answer_callback_query(call.id, "🚀 Starting broadcast...")
                
                # Get user's stored message
                if user_id not in self.user_messages:
                    self.bot.edit_message_text(
                        "❌ No message found! Please send a message first to broadcast.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    return
                
                message_to_broadcast = self.user_messages[user_id]
                channels = self.db_ops.get_user_channels(user_id)
                
                if not channels:
                    self.bot.edit_message_text(
                        "❌ No channels found! Please add channels first.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    return
                
                # Start the actual broadcast process
                threading.Thread(
                    target=self._execute_broadcast,
                    args=(user_id, message_to_broadcast, channels, call.message.chat.id, call.message.message_id),
                    daemon=True
                ).start()
                
                # Show broadcasting status
                # Get user preferences for display
                repost_setting = "Disabled"
                delete_setting = "Disabled"
                
                if user_id in self.user_preferences:
                    prefs = self.user_preferences[user_id]
                    if "auto_repost_time" in prefs:
                        repost_setting = prefs["auto_repost_time"]["display"]
                    if "auto_delete_time" in prefs:
                        delete_setting = prefs["auto_delete_time"]["display"]
                
                broadcast_status_text = f"""
🚀 <b>Broadcasting Started!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📊 <b>Progress:</b> 0/{len(channels)} channels
⏱️ <b>Status:</b> Starting...
</blockquote>

<b>📱 Target Channels:</b> {len(channels)}
<b>⚡ Mode:</b> Instant Broadcast
<b>🔄 Auto Repost:</b> {repost_setting}
<b>🗑️ Auto Delete:</b> {delete_setting}

💡 <b>Tip:</b> Broadcasting in progress, please wait...
                """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("📊 Live Status", callback_data="broadcast_status"),
                    types.InlineKeyboardButton("🛑 Stop", callback_data="stop_broadcast")
                )
                markup.add(
                    types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
                )
                
                self.bot.edit_message_text(
                    broadcast_status_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                
            elif data == "advanced_settings":
                # Advanced settings
                advanced_text = """
⚙️ <b>Advanced Broadcast Settings</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎛️ <b>Professional Controls</b>
Fine-tune your broadcast behavior!
</blockquote>

<b>🔧 Available Settings:</b>
┣ 📊 <b>Channel Selection</b> - Choose specific channels
┣ ⏱️ <b>Send Delay</b> - Add delay between channels
┣ 🔀 <b>Random Order</b> - Randomize channel sequence
┣ 📝 <b>Custom Caption</b> - Override message caption
┣ 🔗 <b>Link Preview</b> - Enable/disable previews
┣ 📌 <b>Pin Messages</b> - Auto-pin after send
┗ 📊 <b>Error Handling</b> - Retry failed sends

💡 <b>Coming Soon:</b> More advanced features!
                """.strip()
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📊 Select Channels", callback_data="select_channels"),
                    types.InlineKeyboardButton("⏱️ Send Delay", callback_data="send_delay")
                )
                markup.add(
                    types.InlineKeyboardButton("🔀 Random Order", callback_data="random_order"),
                    types.InlineKeyboardButton("📝 Custom Caption", callback_data="custom_caption")
                )
                markup.add(
                    types.InlineKeyboardButton("🔙 Back", callback_data="broadcast_config_back")
                )
                self.bot.edit_message_text(
                    advanced_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "⚙️ Advanced settings!")
            
            elif data == "cancel_broadcast":
                # Cancel broadcast
                welcome_text = self._create_welcome_message(user_id)
                markup = self._create_main_menu_keyboard(user_id)
                
                self.bot.edit_message_text(
                    welcome_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "❌ Broadcast cancelled!")
            
            elif data == "broadcast_config_back":
                # Go back to broadcast config
                config_text = """
📢 <b>Broadcast Configuration</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📝 <b>Message Ready!</b>
Configure your broadcast settings below.
</blockquote>

<b>⚙️ Available Options:</b>
┣ 🔄 <b>Auto Repost</b> - Set repost intervals
┣ 🗑️ <b>Auto Delete</b> - Set deletion timers  
┣ 📤 <b>Send Now</b> - Start immediate broadcast
┗ ⚙️ <b>Advanced</b> - Professional controls

💡 <b>Tip:</b> Configure settings before sending!
                """.strip()
                
                markup = self._create_broadcast_config_keyboard()
                
                self.bot.edit_message_text(
                    config_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "🔙 Back to configuration!")
            
            # Handle repost time selections
            elif data.startswith("repost_"):
                time_option = data.replace("repost_", "")
                time_map = {
                    "5min": "5 Minutes",
                    "30min": "30 Minutes", 
                    "1hour": "1 Hour",
                    "3hour": "3 Hours",
                    "6hour": "6 Hours",
                    "12hour": "12 Hours",
                    "24hour": "24 Hours",
                    "disable": "Disabled"
                }
                
                selected_time = time_map.get(time_option, "Unknown")
                
                # Store the preset time setting
                if user_id not in self.user_preferences:
                    self.user_preferences[user_id] = {}
                
                self.user_preferences[user_id]["auto_repost_time"] = {
                    'display': selected_time,
                    'minutes': self._preset_to_minutes(time_option)
                }
                
                success_text = f"""
✅ <b>Auto Repost Configured!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🔄 <b>Repost Interval:</b> {selected_time}
</blockquote>

<b>📋 What This Means:</b>
┣ 📤 <b>First Send:</b> Immediate broadcast
┣ 🔄 <b>Auto Repost:</b> Every {selected_time.lower()}
┣ ♾️ <b>Duration:</b> Until manually stopped
┗ 📊 <b>Tracking:</b> Full analytics included

🚀 <b>Ready to proceed?</b> Configure more settings or send now!
                """.strip()
                
                markup = self._create_broadcast_config_keyboard()
                
                self.bot.edit_message_text(
                    success_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, f"🔄 Auto repost set to {selected_time}!")
            
            # Handle delete time selections  
            elif data.startswith("delete_"):
                time_option = data.replace("delete_", "")
                time_map = {
                    "instant": "Instant",
                    "2min": "2 Minutes",
                    "3min": "3 Minutes",
                    "10min": "10 Minutes",
                    "20min": "20 Minutes",
                    "1hour": "1 Hour",
                    "never": "Never"
                }
                
                selected_time = time_map.get(time_option, "Unknown")
                
                # Store the preset delete time setting
                if user_id not in self.user_preferences:
                    self.user_preferences[user_id] = {}
                
                self.user_preferences[user_id]["auto_delete_time"] = {
                    'display': selected_time,
                    'minutes': self._preset_delete_to_minutes(time_option)
                }
                
                success_text = f"""
✅ <b>Auto Delete Configured!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🗑️ <b>Delete Timer:</b> {selected_time}
</blockquote>

<b>📋 What This Means:</b>
┣ 📤 <b>Send Messages:</b> Normal broadcast
┣ ⏱️ <b>Wait Period:</b> {selected_time.lower()}
┣ 🗑️ <b>Auto Delete:</b> Remove from all channels
┗ 🛡️ <b>Cleanup:</b> No traces left behind

⚠️ <b>Warning:</b> Deleted messages cannot be recovered!
                """.strip()
                
                markup = self._create_broadcast_config_keyboard()
                
                self.bot.edit_message_text(
                    success_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, f"🗑️ Auto delete set to {selected_time}!")
            
            # Handle custom repost time
            elif data == "repost_custom":
                logger.info(f"DEBUG: User {user_id} clicked repost_custom button")
                custom_text = """
⏰ <b>Custom Auto Repost Time</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Set Your Custom Interval!</b>
Enter the time in minutes, hours, or days.
</blockquote>

<b>📝 Format Examples:</b>
┣ <b>Minutes:</b> <code>15m</code> or <code>15 minutes</code>
┣ <b>Hours:</b> <code>2h</code> or <code>2 hours</code>
┣ <b>Days:</b> <code>1d</code> or <code>1 day</code>
┣ <b>Mixed:</b> <code>1h 30m</code> or <code>2d 12h</code>

<b>⚡ Quick Examples:</b>
• <code>45m</code> - Repost every 45 minutes
• <code>2h 15m</code> - Repost every 2 hours 15 minutes
• <code>1d</code> - Repost daily

💡 <b>Just send me your custom time!</b>
                """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🔙 Back to Options", callback_data="set_repost_time")
                )
                
                self.bot.edit_message_text(
                    custom_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "⏰ Send custom repost time!")
                
                # Set user state for custom input
                self.broadcast_states[user_id] = {
                    "waiting_for": "custom_repost_time",
                    "message_id": call.message.message_id,
                    "chat_id": call.message.chat.id
                }
            
            # Handle custom delete time
            elif data == "delete_custom":
                logger.info(f"DEBUG: User {user_id} clicked delete_custom button")
                custom_text = """
⏰ <b>Custom Auto Delete Time</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Set Your Custom Delete Timer!</b>
Enter when to delete messages after broadcast.
</blockquote>

<b>📝 Format Examples:</b>
┣ <b>Minutes:</b> <code>10m</code> or <code>10 minutes</code>
┣ <b>Hours:</b> <code>3h</code> or <code>3 hours</code>
┣ <b>Days:</b> <code>2d</code> or <code>2 days</code>
┣ <b>Mixed:</b> <code>1h 45m</code> or <code>1d 6h</code>

<b>⚡ Quick Examples:</b>
• <code>20m</code> - Delete after 20 minutes
• <code>1h 30m</code> - Delete after 1.5 hours
• <code>3d</code> - Delete after 3 days

⚠️ <b>Warning:</b> Deleted messages cannot be recovered!

💡 <b>Just send me your custom time!</b>
                """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🔙 Back to Options", callback_data="set_delete_time")
                )
                
                self.bot.edit_message_text(
                    custom_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "⏰ Send custom delete time!")
                
                # Set user state for custom input
                self.broadcast_states[user_id] = {
                    "waiting_for": "custom_delete_time",
                    "message_id": call.message.message_id,
                    "chat_id": call.message.chat.id
                }
            
            else:
                self.bot.answer_callback_query(call.id, "Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error handling broadcast config callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _execute_broadcast(self, user_id: int, message, channels: List[Dict], status_chat_id: int, status_message_id: int):
        """Execute the actual broadcasting to channels"""
        try:
            total_channels = len(channels)
            successful_sends = 0
            failed_sends = 0
            
            for i, channel in enumerate(channels):
                try:
                    channel_id = channel.get('channel_id')
                    channel_name = channel.get('channel_name', 'Unknown')
                    
                    # Update progress
                    progress_text = f"""
🚀 <b>Broadcasting in Progress...</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📊 <b>Progress:</b> {i+1}/{total_channels} channels
⏱️ <b>Status:</b> Sending to {channel_name}...
</blockquote>

<b>📱 Target Channels:</b> {total_channels}
<b>✅ Successful:</b> {successful_sends}
<b>❌ Failed:</b> {failed_sends}
<b>📺 Current:</b> {channel_name}

💡 <b>Please wait...</b> Broadcasting in progress!
                    """.strip()
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton("🛑 Stop", callback_data="stop_broadcast")
                    )
                    
                    try:
                        self.bot.edit_message_text(
                            progress_text,
                            status_chat_id,
                            status_message_id,
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except:
                        pass  # Ignore edit failures
                    
                    # Send the message to the channel
                    self._send_message_to_channel(message, channel_id)
                    successful_sends += 1
                    
                    # Small delay between sends
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error sending to channel {channel_id}: {e}")
                    failed_sends += 1
                    continue
            
            # Show final results
            final_text = f"""
✅ <b>Broadcast Completed!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🎯 <b>Final Results</b>
</blockquote>

<b>📊 Statistics:</b>
┣ 📱 <b>Total Channels:</b> {total_channels}
┣ ✅ <b>Successful:</b> {successful_sends}
┣ ❌ <b>Failed:</b> {failed_sends}
┗ 📈 <b>Success Rate:</b> {int((successful_sends/total_channels)*100) if total_channels > 0 else 0}%

🎉 <b>Broadcast completed successfully!</b>

💡 <b>Tip:</b> Check analytics for detailed insights!
            """.strip()
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("📊 View Analytics", callback_data="show_stats"),
                types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
            )
            
            try:
                self.bot.edit_message_text(
                    final_text,
                    status_chat_id,
                    status_message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except:
                pass
            
            # Schedule auto repost and auto delete if configured
            self._schedule_auto_actions(user_id, message, channels, successful_sends)
                
            # Clean up stored message
            if user_id in self.user_messages:
                del self.user_messages[user_id]
                
        except Exception as e:
            logger.error(f"Error in broadcast execution: {e}")
            # Show error message
            error_text = f"""
❌ <b>Broadcast Error!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
⚠️ <b>Broadcast Failed</b>
An error occurred during broadcasting.
</blockquote>

<b>📊 Partial Results:</b>
┣ ✅ <b>Successful:</b> {successful_sends}
┣ ❌ <b>Failed:</b> {failed_sends}
┗ 📱 <b>Total:</b> {total_channels}

🔧 <b>Please try again or contact support.</b>
            """.strip()
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔄 Retry", callback_data="send_now"),
                types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
            )
            
            try:
                self.bot.edit_message_text(
                    error_text,
                    status_chat_id,
                    status_message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except:
                pass
    
    def _send_message_to_channel(self, message, channel_id: int):
        """Send a specific message to a channel"""
        try:
            if message.content_type == 'text':
                self.bot.send_message(
                    channel_id,
                    message.text,
                    parse_mode="HTML" if message.entities else None
                )
            elif message.content_type == 'photo':
                self.bot.send_photo(
                    channel_id,
                    message.photo[-1].file_id,
                    caption=message.caption,
                    parse_mode="HTML" if message.caption_entities else None
                )
            elif message.content_type == 'video':
                self.bot.send_video(
                    channel_id,
                    message.video.file_id,
                    caption=message.caption,
                    parse_mode="HTML" if message.caption_entities else None
                )
            elif message.content_type == 'document':
                self.bot.send_document(
                    channel_id,
                    message.document.file_id,
                    caption=message.caption,
                    parse_mode="HTML" if message.caption_entities else None
                )
            elif message.content_type == 'audio':
                self.bot.send_audio(
                    channel_id,
                    message.audio.file_id,
                    caption=message.caption,
                    parse_mode="HTML" if message.caption_entities else None
                )
            elif message.content_type == 'voice':
                self.bot.send_voice(
                    channel_id,
                    message.voice.file_id,
                    caption=message.caption,
                    parse_mode="HTML" if message.caption_entities else None
                )
            elif message.content_type == 'video_note':
                self.bot.send_video_note(
                    channel_id,
                    message.video_note.file_id
                )
            elif message.content_type == 'sticker':
                self.bot.send_sticker(
                    channel_id,
                    message.sticker.file_id
                )
            else:
                # Fallback for other message types
                self.bot.send_message(
                    channel_id,
                    f"📎 Unsupported message type: {message.content_type}"
                )
                
        except Exception as e:
            logger.error(f"Error sending message to channel {channel_id}: {e}")
            raise e
    
    def _schedule_auto_actions(self, user_id: int, message, channels: List[Dict], successful_count: int):
        """Schedule auto repost and auto delete actions"""
        try:
            if user_id not in self.user_preferences:
                return
                
            prefs = self.user_preferences[user_id]
            
            # Schedule auto delete if configured
            if "auto_delete_time" in prefs:
                delete_config = prefs["auto_delete_time"]
                delete_minutes = delete_config.get("minutes", 0)
                
                if delete_minutes > 0:  # Don't schedule for instant or never (-1)
                    # Store broadcast info for deletion
                    broadcast_id = f"{user_id}_{int(time.time())}"
                    self.scheduled_tasks[f"delete_{broadcast_id}"] = {
                        'type': 'delete',
                        'user_id': user_id,
                        'channels': channels,
                        'message': message,
                        'scheduled_time': datetime.now() + timedelta(minutes=delete_minutes),
                        'successful_count': successful_count
                    }
                    
                    # Start delete timer in background
                    threading.Timer(
                        delete_minutes * 60,
                        self._execute_auto_delete,
                        args=[broadcast_id]
                    ).start()
                    
                    logger.info(f"🗑️ Auto delete scheduled for {delete_minutes} minutes for user {user_id}")
                
                elif delete_minutes == 0:  # Instant delete
                    threading.Timer(5, self._execute_instant_delete, args=[channels, message]).start()
            
            # Schedule auto repost if configured
            if "auto_repost_time" in prefs:
                repost_config = prefs["auto_repost_time"]
                repost_minutes = repost_config.get("minutes", 0)
                
                if repost_minutes > 0:  # Don't schedule for disabled (0)
                    # Store broadcast info for reposting
                    broadcast_id = f"{user_id}_{int(time.time())}_repost"
                    self.scheduled_tasks[f"repost_{broadcast_id}"] = {
                        'type': 'repost',
                        'user_id': user_id,
                        'channels': channels,
                        'message': message,
                        'interval_minutes': repost_minutes,
                        'next_repost': datetime.now() + timedelta(minutes=repost_minutes)
                    }
                    
                    # Start repost timer in background
                    threading.Timer(
                        repost_minutes * 60,
                        self._execute_auto_repost,
                        args=[broadcast_id]
                    ).start()
                    
                    logger.info(f"🔄 Auto repost scheduled every {repost_minutes} minutes for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error scheduling auto actions: {e}")
    
    def _execute_auto_delete(self, broadcast_id: str):
        """Execute auto delete for a broadcast"""
        try:
            task_key = f"delete_{broadcast_id}"
            if task_key not in self.scheduled_tasks:
                return
                
            task = self.scheduled_tasks[task_key]
            channels = task['channels']
            message = task['message']
            user_id = task['user_id']
            
            deleted_count = 0
            for channel in channels:
                try:
                    channel_id = channel.get('channel_id')
                    if not channel_id:
                        continue
                    
                    # Delete recent messages from this channel
                    messages_deleted = self._delete_channel_messages(channel_id)
                    deleted_count += messages_deleted
                    
                    logger.info(f"🗑️ Auto deleted {messages_deleted} messages from channel {channel_id}")
                    
                except Exception as e:
                    logger.error(f"Error auto-deleting from channel {channel_id}: {e}")
            
            # Clean up scheduled task
            del self.scheduled_tasks[task_key]
            
            # Notify user about deletion
            try:
                delete_text = f"""
🗑️ <b>Auto Delete Completed!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
✅ <b>Messages Deleted:</b> {deleted_count}
📋 <b>Channels Cleaned:</b> {len(channels)}
</blockquote>

<b>🧹 What was cleaned:</b>
┣ 🗑️ Recent messages deleted
┣ ⏰ Auto delete task completed
┗ ✨ Channels ready for new content

<i>All channels are now clean and ready!</i>
                """.strip()
                
                self.bot.send_message(user_id, delete_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error sending delete notification: {e}")
                
            logger.info(f"✅ Auto delete completed for broadcast {broadcast_id} - {deleted_count} messages deleted")
            
        except Exception as e:
            logger.error(f"Error in auto delete execution: {e}")
    
    def _execute_instant_delete(self, channels: List[Dict], message):
        """Execute instant delete after broadcast"""
        try:
            deleted_count = 0
            for channel in channels:
                try:
                    channel_id = channel.get('channel_id')
                    if not channel_id:
                        continue
                    
                    # Delete recent messages from this channel
                    messages_deleted = self._delete_channel_messages(channel_id)
                    deleted_count += messages_deleted
                    
                    logger.info(f"🗑️ Instant deleted {messages_deleted} messages from channel {channel_id}")
                    
                except Exception as e:
                    logger.error(f"Error instant deleting from channel {channel_id}: {e}")
                    
            logger.info(f"✅ Instant delete completed for {deleted_count} messages across {len(channels)} channels")
            
        except Exception as e:
            logger.error(f"Error in instant delete execution: {e}")
    
    def _execute_auto_repost(self, broadcast_id: str):
        """Execute auto repost for a broadcast"""
        try:
            task_key = f"repost_{broadcast_id}"
            if task_key not in self.scheduled_tasks:
                return
                
            task = self.scheduled_tasks[task_key]
            channels = task['channels']
            message = task['message']
            user_id = task['user_id']
            interval_minutes = task['interval_minutes']
            
            # Execute repost
            reposted_count = 0
            for channel in channels:
                try:
                    channel_id = channel.get('channel_id')
                    self._send_message_to_channel(message, channel_id)
                    reposted_count += 1
                    time.sleep(1)  # Small delay between sends
                except Exception as e:
                    logger.error(f"Error auto-reposting to channel {channel_id}: {e}")
            
            # Schedule next repost
            task['next_repost'] = datetime.now() + timedelta(minutes=interval_minutes)
            threading.Timer(
                interval_minutes * 60,
                self._execute_auto_repost,
                args=[broadcast_id]
            ).start()
            
            # Notify user about repost
            try:
                self.bot.send_message(
                    user_id,
                    f"🔄 <b>Auto Repost Completed</b>\n\n"
                    f"<blockquote>Reposted to {reposted_count} channels successfully!</blockquote>\n"
                    f"<b>Next repost:</b> {interval_minutes} minutes",
                    parse_mode="HTML"
                )
            except:
                pass
                
            logger.info(f"✅ Auto repost completed for broadcast {broadcast_id}, next in {interval_minutes} minutes")
            
        except Exception as e:
            logger.error(f"Error in auto repost execution: {e}")
    
    def _stop_user_auto_actions(self, user_id: int):
        """Stop all auto actions for a user"""
        try:
            tasks_to_remove = []
            for task_key, task in self.scheduled_tasks.items():
                if task.get('user_id') == user_id:
                    tasks_to_remove.append(task_key)
            
            for task_key in tasks_to_remove:
                del self.scheduled_tasks[task_key]
                logger.info(f"🛑 Stopped auto task: {task_key}")
                
            if tasks_to_remove:
                return len(tasks_to_remove)
            return 0
                
        except Exception as e:
            logger.error(f"Error stopping auto actions: {e}")
            return 0
    
    def _stop_broadcast_and_cleanup(self, user_id):
        """Stop ongoing broadcast and cleanup all messages"""
        try:
            # Step 1: Stop ongoing broadcast
            if hasattr(self, 'broadcast_manager'):
                self.broadcast_manager.stop_broadcast(user_id)
            
            # Step 2: Get all channels for user
            channels = self.db_ops.get_user_channels(user_id)
            if not channels:
                return 0
            
            # Step 3: Delete all messages from all channels
            deleted_count = 0
            for channel in channels:
                channel_id = channel.get('channel_id')
                if not channel_id:
                    continue
                
                try:
                    # Get recent messages from this channel
                    messages_deleted = self._delete_channel_messages(channel_id)
                    deleted_count += messages_deleted
                    
                except Exception as e:
                    logger.error(f"❌ Error deleting messages from channel {channel_id}: {e}")
            
            logger.info(f"🧹 Cleaned up {deleted_count} messages for user {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Error in stop broadcast and cleanup: {e}")
            return 0
    
    def _delete_channel_messages(self, channel_id):
        """Delete recent messages from a channel"""
        try:
            deleted_count = 0
            
            # Get recent messages (last 50 messages)
            try:
                # Try to get recent messages using get_chat_history
                messages = self.bot.get_chat_history(channel_id, limit=50)
                
                for message in messages:
                    try:
                        self.bot.delete_message(channel_id, message.message_id)
                        deleted_count += 1
                        time.sleep(0.1)  # Small delay to avoid rate limits
                    except Exception as e:
                        # Message might be too old or already deleted
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Error getting chat history for channel {channel_id}: {e}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Error deleting messages from channel {channel_id}: {e}")
            return 0
    
    def _handle_custom_time_input(self, user_id: int, time_text: str, state: Dict):
        """Handle custom time input from user"""
        try:
            # Parse the custom time
            parsed_time = self._parse_custom_time(time_text)
            
            if parsed_time is None:
                # Invalid format
                error_text = """
❌ <b>Invalid Time Format!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
⚠️ <b>Format Error</b>
Please use valid time format.
</blockquote>

<b>📝 Valid Examples:</b>
┣ <code>15m</code> - 15 minutes
┣ <code>2h</code> - 2 hours  
┣ <code>1d</code> - 1 day
┣ <code>1h 30m</code> - 1 hour 30 minutes
┣ <code>2d 6h</code> - 2 days 6 hours

💡 <b>Try again with correct format!</b>
                """.strip()
                
                self.bot.send_message(user_id, error_text, parse_mode="HTML")
                return
            
            # Determine if it's repost or delete
            is_repost = state["waiting_for"] == "custom_repost_time"
            feature_name = "Auto Repost" if is_repost else "Auto Delete"
            emoji = "🔄" if is_repost else "🗑️"
            
            # Show confirmation
            success_text = f"""
✅ <b>Custom {feature_name} Set!</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
{emoji} <b>Custom Time:</b> {parsed_time['display']}
</blockquote>

<b>📋 Configuration:</b>
┣ ⏱️ <b>Interval:</b> {parsed_time['display']}
┣ 📊 <b>Total Minutes:</b> {parsed_time['minutes']}
┣ 🎯 <b>Feature:</b> {feature_name}
┗ ✅ <b>Status:</b> Configured

🚀 <b>Perfect!</b> Your custom timing is set!

💡 <b>Ready to configure more settings or start broadcast!</b>
            """.strip()
            
            markup = self._create_broadcast_config_keyboard()
            
            try:
                self.bot.edit_message_text(
                    success_text,
                    state["chat_id"],
                    state["message_id"],
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except:
                # If edit fails, send new message
                self.bot.send_message(
                    user_id,
                    success_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            
            # Clear the state
            del self.broadcast_states[user_id]
            
            # Store the custom time setting
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = {}
            
            preference_key = "auto_repost_time" if is_repost else "auto_delete_time"
            self.user_preferences[user_id][preference_key] = {
                'display': parsed_time['display'],
                'minutes': parsed_time['minutes']
            }
            
            logger.info(f"User {user_id} set custom {feature_name.lower()} time: {parsed_time['display']} ({parsed_time['minutes']} minutes)")
            
        except Exception as e:
            logger.error(f"Error handling custom time input: {e}")
            self.bot.send_message(user_id, "❌ An error occurred processing your custom time.")
            
            # Clear the state on error
            if user_id in self.broadcast_states:
                del self.broadcast_states[user_id]
    
    def _parse_custom_time(self, time_text: str) -> Optional[Dict]:
        """Parse custom time string and return minutes and display format"""
        try:
            import re
            
            time_text = time_text.lower().strip()
            total_minutes = 0
            parts = []
            
            # Patterns for different time units
            patterns = {
                'days': r'(\d+)\s*(?:d|day|days)',
                'hours': r'(\d+)\s*(?:h|hour|hours)',
                'minutes': r'(\d+)\s*(?:m|min|minute|minutes)'
            }
            
            # Extract days
            days_match = re.search(patterns['days'], time_text)
            if days_match:
                days = int(days_match.group(1))
                total_minutes += days * 24 * 60
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            
            # Extract hours
            hours_match = re.search(patterns['hours'], time_text)
            if hours_match:
                hours = int(hours_match.group(1))
                total_minutes += hours * 60
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            
            # Extract minutes
            minutes_match = re.search(patterns['minutes'], time_text)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                total_minutes += minutes
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            
            # Validate
            if total_minutes == 0:
                return None
            
            # Create display string
            display = " ".join(parts)
            
            return {
                'minutes': total_minutes,
                'display': display
            }
            
        except Exception as e:
            logger.error(f"Error parsing custom time: {e}")
            return None
    
    def _preset_to_minutes(self, time_option: str) -> int:
        """Convert preset time option to minutes"""
        time_minutes_map = {
            "5min": 5,
            "30min": 30,
            "1hour": 60,
            "3hour": 180,
            "6hour": 360,
            "12hour": 720,
            "24hour": 1440,
            "disable": 0
        }
        return time_minutes_map.get(time_option, 0)
    
    def _preset_delete_to_minutes(self, time_option: str) -> int:
        """Convert preset delete time option to minutes"""
        delete_minutes_map = {
            "instant": 0,
            "2min": 2,
            "3min": 3,
            "10min": 10,
            "20min": 20,
            "1hour": 60,
            "never": -1  # Special value for never delete
        }
        return delete_minutes_map.get(time_option, 0)
    
    def _handle_premium_callback(self, call):
        """Handle premium callback"""
        try:
            if call.data == "features_info":
                free_text = self._create_free_features_message()
                markup = self._create_free_features_keyboard()
                
                self.bot.edit_message_text(
                    free_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            else:
                self.bot.answer_callback_query(call.id, "All features are free!")
                
        except Exception as e:
            logger.error(f"Error handling premium callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _handle_admin_callback(self, call):
        """Handle admin callback"""
        try:
            user_id = call.from_user.id
            
            if user_id not in ADMIN_IDS:
                self.bot.answer_callback_query(call.id, "Access denied!")
                return
            
            if call.data == "admin_panel":
                # Show admin panel
                admin_text = self._create_admin_message()
                markup = self._create_admin_keyboard()
                
                self.bot.edit_message_text(
                    admin_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "👨‍💼 Admin Panel")
            
            elif call.data == "admin_analytics":
                # Show system analytics
                from plugins.broadcast.analytics import BroadcastAnalytics
                analytics = BroadcastAnalytics(self.db_ops)
                system_stats = analytics.get_system_analytics()
                
                stats_text = f"""
📊 <b>System Analytics</b>

<blockquote>
• 👥 Total Users: {system_stats.get('total_users', 0)}
• 📋 Total Channels: {system_stats.get('total_channels', 0)}
• 📡 Total Broadcasts: {system_stats.get('total_broadcasts', 0)}
• 📊 Analytics Entries: {system_stats.get('total_analytics_entries', 0)}
</blockquote>

<b>Last Updated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
                """.strip()
                
                self.bot.send_message(user_id, stats_text, parse_mode="HTML")
                self.bot.answer_callback_query(call.id, "Analytics loaded!")
            
            elif call.data == "admin_emergency_stop":
                # Emergency stop all broadcasts
                stopped_count = 0
                for uid in list(self.broadcast_manager.active_broadcasts.keys()):
                    result = self.broadcast_manager.stop_broadcast(uid)
                    if result["success"]:
                        stopped_count += 1
                
                self.bot.answer_callback_query(call.id, f"Stopped {stopped_count} broadcasts")
            
            elif call.data == "admin_users":
                # User management
                users = self.db_ops.get_all_users()
                total_users = len(users)
                active_users = len([u for u in users if u.get('is_active', True)])
                
                users_text = f"""
👥 <b>User Management</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📊 <b>User Statistics</b>
</blockquote>

<b>📈 User Metrics:</b>
┣ 👥 <b>Total Users:</b> {total_users}
┣ ✅ <b>Active Users:</b> {active_users}
┣ ❌ <b>Inactive Users:</b> {total_users - active_users}
┗ 📊 <b>Activity Rate:</b> {int((active_users/total_users)*100) if total_users > 0 else 0}%

<b>🕐 Recent Users (Last 5):</b>
                """.strip()
                
                for i, user in enumerate(users[-5:], 1):
                    username = user.get('username', 'N/A')
                    first_name = user.get('first_name', 'Unknown')
                    user_id_display = user.get('user_id', 'N/A')
                    users_text += f"\n{i}. <b>{first_name}</b> (@{username}) - ID: <code>{user_id_display}</code>"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_detailed_stats"),
                    types.InlineKeyboardButton("📥 Export Data", callback_data="admin_export_data")
                )
                markup.add(
                    types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")
                )
                
                self.bot.edit_message_text(
                    users_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "👥 User management loaded!")
            
            elif call.data == "admin_controls":
                # System controls
                import psutil
                import platform
                
                # Get system info
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                controls_text = f"""
🔧 <b>System Controls</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
🖥️ <b>System Status</b>
</blockquote>

<b>📊 System Metrics:</b>
┣ 🖥️ <b>OS:</b> {platform.system()} {platform.release()}
┣ ⚡ <b>CPU Usage:</b> {cpu_percent}%
┣ 🧠 <b>RAM Usage:</b> {memory.percent}%
┣ 💾 <b>Disk Usage:</b> {disk.percent}%
┣ 🔄 <b>Bot Status:</b> Online
┗ 📊 <b>Active Broadcasts:</b> {len(self.broadcast_manager.active_broadcasts)}

<b>🛠️ Available Controls:</b>
┣ 🔄 <b>Restart Bot</b> - Restart bot process
┣ 🛑 <b>Emergency Stop</b> - Stop all broadcasts
┣ 📋 <b>View Logs</b> - Check system logs
┗ 🧹 <b>Cleanup</b> - Clean temporary data
                """.strip()
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart"),
                    types.InlineKeyboardButton("📋 View Logs", callback_data="admin_logs")
                )
                markup.add(
                    types.InlineKeyboardButton("🧹 Cleanup Data", callback_data="admin_cleanup"),
                    types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
                )
                
                self.bot.edit_message_text(
                    controls_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "🔧 System controls loaded!")
            
            elif call.data == "admin_logs":
                # View logs
                try:
                    with open('bot.log', 'r', encoding='utf-8') as log_file:
                        logs = log_file.readlines()
                        recent_logs = logs[-20:]  # Last 20 lines
                        
                    logs_text = f"""
📋 <b>System Logs</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📄 <b>Recent Log Entries (Last 20)</b>
</blockquote>

<code>
{''.join(recent_logs[-10:])}
</code>

<b>📊 Log Statistics:</b>
┣ 📄 <b>Total Lines:</b> {len(logs)}
┣ 🕐 <b>Last Updated:</b> {datetime.now().strftime('%H:%M:%S')}
┗ 📋 <b>Showing:</b> Last 10 entries

💡 <b>Tip:</b> Check logs regularly for issues!
                    """.strip()
                    
                except Exception as e:
                    logs_text = f"""
📋 <b>System Logs</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
❌ <b>Error Loading Logs</b>
</blockquote>

<b>🔧 Error Details:</b>
{str(e)}

💡 <b>Tip:</b> Log file might not exist or be accessible.
                    """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_logs"),
                    types.InlineKeyboardButton("🔙 Back", callback_data="admin_controls")
                )
                
                self.bot.edit_message_text(
                    logs_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📋 Logs loaded!")
            
            elif call.data == "admin_restart":
                # Restart bot
                restart_text = """
🔄 <b>Bot Restart Initiated</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
⚠️ <b>System Restart</b>
Bot is restarting... Please wait.
</blockquote>

<b>🔄 Restart Process:</b>
┣ 🛑 <b>Step 1:</b> Stopping current processes
┣ 💾 <b>Step 2:</b> Saving state data
┣ 🔄 <b>Step 3:</b> Restarting bot process
┗ ✅ <b>Step 4:</b> Resuming operations

💡 <b>The bot will be back online in a few seconds!</b>
                """.strip()
                
                self.bot.edit_message_text(
                    restart_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "🔄 Restarting bot...")
                
                # Restart the bot process
                import sys
                import os
                logger.info("🔄 Admin initiated bot restart")
                os.execv(sys.executable, ['python'] + sys.argv)
            
            elif call.data == "admin_detailed_stats":
                # Detailed statistics
                db_stats = self.db_ops.get_database_stats()
                
                detailed_text = f"""
📊 <b>Detailed System Statistics</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
📈 <b>Comprehensive Analytics</b>
</blockquote>

<b>👥 User Statistics:</b>
┣ 📊 <b>Total Users:</b> {db_stats.get('total_users', 0)}
┣ 🆕 <b>New Today:</b> {db_stats.get('new_users_today', 0)}
┣ 🔄 <b>Active Users:</b> {db_stats.get('active_users', 0)}
┗ 📈 <b>Growth Rate:</b> {db_stats.get('growth_rate', 0)}%

<b>📺 Channel Statistics:</b>
┣ 📊 <b>Total Channels:</b> {db_stats.get('total_channels', 0)}
┣ ✅ <b>Active Channels:</b> {db_stats.get('active_channels', 0)}
┣ 🔗 <b>Connected Channels:</b> {db_stats.get('connected_channels', 0)}
┗ 📈 <b>Channel Growth:</b> {db_stats.get('channel_growth', 0)}%

<b>📡 Broadcast Statistics:</b>
┣ 📊 <b>Total Broadcasts:</b> {db_stats.get('total_broadcasts', 0)}
┣ ✅ <b>Successful:</b> {db_stats.get('successful_broadcasts', 0)}
┣ ❌ <b>Failed:</b> {db_stats.get('failed_broadcasts', 0)}
┗ 📈 <b>Success Rate:</b> {db_stats.get('success_rate', 0)}%

<b>📊 Database Statistics:</b>
┣ 📄 <b>Analytics Entries:</b> {db_stats.get('analytics_entries', 0)}
┣ 💾 <b>DB Size:</b> {db_stats.get('db_size', 'Unknown')}
┗ 🕐 <b>Last Updated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_detailed_stats"),
                    types.InlineKeyboardButton("🔙 Back", callback_data="admin_users")
                )
                
                self.bot.edit_message_text(
                    detailed_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📊 Detailed stats loaded!")
            
            elif call.data == "admin_export_data":
                # Export data
                self.bot.answer_callback_query(call.id, "📥 Preparing export...")
                
                try:
                    # Generate export data
                    export_data = {
                        "users": self.db_ops.get_all_users(),
                        "channels": [],
                        "broadcasts": [],
                        "analytics": [],
                        "exported_at": datetime.now().isoformat()
                    }
                    
                    # Get channels for all users
                    for user in export_data["users"]:
                        user_channels = self.db_ops.get_user_channels(user.get('user_id'))
                        export_data["channels"].extend(user_channels)
                    
                    # Create JSON file
                    import json
                    export_filename = f"bbbot_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    
                    with open(export_filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                    
                    # Send file
                    with open(export_filename, 'rb') as f:
                        self.bot.send_document(
                            call.message.chat.id,
                            f,
                            caption=f"""
📥 <b>Data Export Complete</b>

<b>📊 Export Summary:</b>
• 👥 Users: {len(export_data['users'])}
• 📺 Channels: {len(export_data['channels'])}
• 🕐 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💾 <b>File contains all bot data in JSON format.</b>
                            """.strip(),
                            parse_mode="HTML"
                        )
                    
                    # Clean up file
                    os.remove(export_filename)
                    
                except Exception as e:
                    error_text = f"""
❌ <b>Export Failed</b>
<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>

<blockquote>
⚠️ <b>Export Error</b>
</blockquote>

<b>🔧 Error Details:</b>
{str(e)}

💡 <b>Try again or contact support.</b>
                    """.strip()
                    
                    self.bot.send_message(call.message.chat.id, error_text, parse_mode="HTML")
            
            else:
                self.bot.answer_callback_query(call.id, "Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error handling admin callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _handle_main_menu_callback(self, call):
        """Handle main menu callback"""
        try:
            user_id = call.from_user.id
            
            welcome_text = self._create_welcome_message(user_id)
            markup = self._create_main_menu_keyboard(user_id)
            
            self.bot.edit_message_text(
                welcome_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
            self.bot.answer_callback_query(call.id, "🏠 Main Menu")
        except Exception as e:
            logger.error(f"❌ Error handling main menu callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def _handle_navigation_callback(self, call):
        """Handle navigation callbacks for channels, stats, settings"""
        try:
            user_id = call.from_user.id
            data = call.data
            
            if data == "my_channels":
                channels = self.db_ops.get_user_channels(user_id)
                channels_text = self._create_channels_list_message(channels)
                markup = self._create_channels_keyboard()
                
                self.bot.edit_message_text(
                    channels_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📋 Your Channels")
            
            elif data == "show_stats":
                analytics = self.db_ops.get_user_analytics(user_id)
                stats_text = self.message_formatter.format_analytics_summary(analytics)
                markup = self._create_stats_keyboard()
                
                self.bot.edit_message_text(
                    stats_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "📊 Analytics")
            
            elif data == "settings":
                settings_text = """
⚙️ <b>Bot Settings</b>

<blockquote>
All features are FREE and enabled by default!
</blockquote>

<b>🎯 Available Features:</b>
• 📢 Multi-Channel Broadcasting ✅
• ⚡ Auto Repost & Delete ✅  
• 📊 Advanced Analytics ✅
• 🔗 Auto Link Detection ✅
• ⏰ Scheduled Broadcasts ✅
• 🎨 Message Templates ✅

<b>💡 No configuration needed!</b>
All features are automatically available.
                """.strip()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu"))
                
                self.bot.edit_message_text(
                    settings_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(call.id, "⚙️ Settings")
            
            else:
                self.bot.answer_callback_query(call.id, "Feature coming soon!")
                
        except Exception as e:
            logger.error(f"❌ Error handling navigation callback: {e}")
            self.bot.answer_callback_query(call.id, "An error occurred")
    
    def start_polling(self):
        """Start bot polling"""
        try:
            logger.info("🚀 Starting Advanced Broadcast Bot...")
            self.bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ Bot polling error: {e}")
            raise
    
    def stop(self):
        """Stop bot gracefully"""
        try:
            logger.info("🛑 Stopping bot...")
            self.broadcast_manager.shutdown()
            self.db_connection.disconnect()
            logger.info("✅ Bot stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")

def main():
    """Main function"""
    try:
        # Validate configuration
        validate_config()
        
        # Create and start bot
        bot = AdvancedBroadcastBot()
        bot.start_polling()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
