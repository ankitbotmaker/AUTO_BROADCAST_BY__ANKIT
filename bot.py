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
from plugins.utils import LinkHandler, MessageFormatter, Validators, Helpers, setup_logger
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
                parse_mode="Markdown"
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
                parse_mode="Markdown"
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
                parse_mode="Markdown"
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
                    "❌ **No channels found!**\n\nPlease add channels first using /add command."
                )
                return
            
            broadcast_text = self._create_broadcast_message()
            markup = self._create_broadcast_keyboard()
            
            self.bot.send_message(
                user_id,
                broadcast_text,
                reply_markup=markup,
                parse_mode="Markdown"
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
                parse_mode="Markdown"
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
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in cleanup command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error loading cleanup interface.")
    
    def _handle_id_command(self, message):
        """Handle /id command"""
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            id_text = f"""
🆔 **ID Information**

**Your User ID:** `{user_id}`
**Chat ID:** `{chat_id}`

**How to get Channel ID:**
1. Add bot to your channel as admin
2. Send any message in the channel
3. Forward that message to this bot
4. Bot will show the channel ID
            """.strip()
            
            self.bot.send_message(
                user_id,
                id_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in id command: {e}")
            self.bot.send_message(message.chat.id, "❌ Error retrieving ID information.")
    
    def _handle_admin_command(self, message):
        """Handle /admin command"""
        try:
            user_id = message.from_user.id
            
            if user_id not in ADMIN_IDS:
                self.bot.send_message(
                    user_id,
                    "❌ **Access Denied!**\n\nYou don't have admin permissions."
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
            if data.startswith("add_channel_"):
                self._handle_add_channel_callback(call)
            elif data.startswith("remove_channel_"):
                self._handle_remove_channel_callback(call)
            elif data.startswith("broadcast_"):
                self._handle_broadcast_callback(call)
            elif data.startswith("premium_"):
                self._handle_premium_callback(call)
            elif data.startswith("admin_"):
                self._handle_admin_callback(call)
            else:
                self.bot.answer_callback_query(call.id, "❌ Unknown action")
                
        except Exception as e:
            logger.error(f"Error in callback query: {e}")
            self.bot.answer_callback_query(call.id, "❌ An error occurred")
    
    def _handle_message(self, message):
        """Handle regular messages"""
        try:
            user_id = message.chat.id
            
            # Check if user has channels
            channels = self.db_ops.get_user_channels(user_id)
            if not channels:
                self.bot.send_message(
                    user_id,
                    "❌ **No channels found!**\n\nPlease add channels first using /add command."
                )
                return
            
            # Auto-detect links and start broadcast flow
            if message.chat.type == 'private':
                self._start_broadcast_flow(user_id, message)
            
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            self.bot.send_message(message.chat.id, "❌ An error occurred processing your message.")
    
    def _start_broadcast_flow(self, user_id: int, message):
        """Start broadcast flow for a message"""
        try:
            # Auto-detect and add channels from links
            added_channels = self.link_handler.auto_add_telegram_links(
                user_id, message.text or message.caption or "", self.db_ops
            )
            
            # Get all user channels
            all_channels = self.db_ops.get_user_channels(user_id)
            
            # Create broadcast configuration UI
            broadcast_text = self._create_broadcast_config_message(message, added_channels, all_channels)
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
    
    # UI Creation Methods
    def _create_welcome_message(self, user_id: int) -> str:
        """Create welcome message"""
        user = self.db_ops.get_user(user_id)
        
        return f"""
🚀 **Welcome to Advanced Broadcast Bot!**

<b>👤 User:</b> {user.first_name if user else 'Unknown'}
<b>📊 Channels:</b> {len(self.db_ops.get_user_channels(user_id))}

<b>🎯 All Features FREE:</b>
• 📢 Multi-Channel Broadcasting
• ⚡ Auto Repost & Delete
• 📊 Advanced Analytics
• 🔗 Auto Link Detection
• ⏰ Scheduled Broadcasts
• 🎨 Message Templates
• 📈 Real-time Analytics

<b>🚀 Get Started:</b>
1. Add channels using /add
2. Send your message
3. Configure settings
4. Start broadcasting!

<b>💡 Tip:</b> Send a message with Telegram links to auto-add channels!
        """.strip()
    
    def _create_main_menu_keyboard(self, user_id: int) -> types.InlineKeyboardMarkup:
        """Create main menu keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_start"),
            types.InlineKeyboardButton("➕ Add Channels", callback_data="add_channels")
        )
        markup.add(
            types.InlineKeyboardButton("📋 My Channels", callback_data="my_channels"),
            types.InlineKeyboardButton("📊 Statistics", callback_data="show_stats")
        )
        markup.add(
            types.InlineKeyboardButton("🎨 Features", callback_data="features_info"),
            types.InlineKeyboardButton("🛠 Settings", callback_data="settings")
        )
        
        return markup
    
    def _create_broadcast_config_message(self, message, added_channels: List[Dict], all_channels: List[Dict]) -> str:
        """Create broadcast configuration message"""
        message_type = message.content_type
        message_text = message.text or message.caption or ""
        
        config_text = f"""
📢 **Broadcast Configuration**

<b>📝 Message Type:</b> {message_type.title()}
<b>📊 Total Channels:</b> {len(all_channels)}
<b>➕ Auto-Added:</b> {len(added_channels)}

<b>🔍 Message Preview:</b>
<blockquote>{message_text[:200]}{'...' if len(message_text) > 200 else ''}</blockquote>
        """.strip()
        
        if added_channels:
            channel_list = "\n".join([f"• {ch['channel_name']} (@{ch['username'] or 'private'})" for ch in added_channels])
            config_text += f"\n\n<b>✅ Auto-Added Channels:</b>\n{channel_list}"
        
        return config_text
    
    def _create_broadcast_config_keyboard(self) -> types.InlineKeyboardMarkup:
        """Create broadcast configuration keyboard"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🔄 Set Auto Repost", callback_data="set_repost_time"),
            types.InlineKeyboardButton("🗑 Set Auto Delete", callback_data="set_delete_time")
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
