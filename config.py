#!/usr/bin/env python3
"""
Advanced Telegram Broadcast Bot Configuration
Enhanced version with all settings and configurations
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# BOT CONFIGURATION
# =============================================================================

# Bot Token (Required)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

# Admin Configuration
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",") if os.getenv("ADMIN_IDS") else []
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip().isdigit()]

# Owner Configuration (for premium activation)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# MongoDB Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "telegram_broadcast_bot")

# Collection Names
USERS_COLLECTION = "users"
CHANNELS_COLLECTION = "channels"
BROADCASTS_COLLECTION = "broadcasts"
ANALYTICS_COLLECTION = "analytics"
SCHEDULED_BROADCASTS_COLLECTION = "scheduled_broadcasts"
BROADCAST_MESSAGES_COLLECTION = "broadcast_messages"
BOT_MESSAGES_COLLECTION = "bot_messages"

# =============================================================================
# TELEGRAM API CONFIGURATION
# =============================================================================

# Telegram API (Optional - for advanced features)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# =============================================================================
# BROADCAST CONFIGURATION
# =============================================================================

# Channel Limits (All Free)
MAX_CHANNELS = 1000  # Unlimited for everyone
MAX_BROADCAST_SIZE = 1000

# Broadcast Settings
BROADCAST_DELAY = 1  # Delay between broadcasts (seconds)
MAX_CONCURRENT_BROADCASTS = 5
BROADCAST_TIMEOUT = 30  # Timeout for individual broadcasts

# Auto Operations
AUTO_DELETE_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440, 2880, 4320, 10080]  # minutes
AUTO_REPOST_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440, 2880, 4320, 10080]  # minutes

# =============================================================================
# FREE FEATURES CONFIGURATION
# =============================================================================

# All features are now free for everyone
FREE_FEATURES = [
    "Unlimited Channels",
    "Advanced Analytics Dashboard",
    "Priority Support",
    "Scheduled Broadcasts",
    "Custom Auto Delete Times",
    "Bulk Operations",
    "Message Templates",
    "Export Analytics"
]

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Log Levels
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "bot.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Rate Limiting
RATE_LIMIT_PER_USER = 10  # Max requests per minute per user
RATE_LIMIT_PER_CHANNEL = 5  # Max broadcasts per minute per channel

# Security Settings
ENABLE_RATE_LIMITING = True
ENABLE_ANALYTICS = True
ENABLE_AUTO_CLEANUP = True

# =============================================================================
# UI CONFIGURATION
# =============================================================================

# Button Layout
BUTTONS_PER_ROW = 2
MAX_BUTTONS_PER_MESSAGE = 8

# Message Limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# =============================================================================
# DEPLOYMENT CONFIGURATION
# =============================================================================

# Heroku Configuration
PORT = int(os.getenv("PORT", 5000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

# Development Settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() == "true"

# =============================================================================
# FEATURE FLAGS
# =============================================================================

# Enable/Disable Features
ENABLE_SCHEDULED_BROADCASTS = True
ENABLE_AUTO_REPOST = True
ENABLE_AUTO_DELETE = True
ENABLE_ANALYTICS = True
ENABLE_BULK_OPERATIONS = True
ENABLE_LINK_DETECTION = True
ENABLE_MESSAGE_TEMPLATES = True  # Now free for everyone

# =============================================================================
# ERROR HANDLING CONFIGURATION
# =============================================================================

# Retry Settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEOUT_DURATION = 30  # seconds

# Error Messages
ERROR_MESSAGES = {
    "no_channels": "❌ **No channels found!**\n\nPlease add channels first using /add command.",
    "broadcast_running": "⚠️ **Broadcast Already Running!**\n\nPlease wait for the current broadcast to complete.",
    "permission_denied": "❌ **Permission Denied!**\n\nYou don't have permission to perform this action.",
    "feature_available": "✅ **Feature Available!**\n\nThis feature is now free for everyone!",
    "invalid_input": "❌ **Invalid Input!**\n\nPlease check your input and try again.",
    "rate_limited": "⏰ **Rate Limited!**\n\nPlease wait before making another request.",
    "channel_not_found": "❌ **Channel Not Found!**\n\nPlease check the channel ID or link.",
    "broadcast_failed": "❌ **Broadcast Failed!**\n\nPlease try again or contact support."
}

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_config():
    """Validate all configuration settings"""
    errors = []
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required")
    
    if not MONGO_URL:
        errors.append("MONGO_URL is required")
    
    if not ADMIN_IDS:
        errors.append("At least one ADMIN_ID is required")
    
    # OWNER_ID is optional now - all features are free
    # if OWNER_ID == 0:
    #     errors.append("OWNER_ID is required for premium system")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

# Validate configuration on import
if __name__ != "__main__":
    validate_config()
