"""
Link Handler Module
Handles Telegram link extraction and channel detection
"""

import re
import logging
from typing import List, Dict, Any, Optional
from telebot import TeleBot

logger = logging.getLogger(__name__)

class LinkHandler:
    """Handle Telegram link extraction and channel detection"""
    
    def __init__(self, bot: TeleBot):
        self.bot = bot
        self.link_patterns = [
            # Public channel patterns
            re.compile(r'https://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r'http://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r't\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r'@([a-zA-Z0-9_]+)', re.IGNORECASE),
            # Private channel patterns (t.me/+ format)
            re.compile(r'https://t\.me/\+([a-zA-Z0-9_-]+)', re.IGNORECASE),
            re.compile(r'http://t\.me/\+([a-zA-Z0-9_-]+)', re.IGNORECASE),
            re.compile(r't\.me/\+([a-zA-Z0-9_-]+)', re.IGNORECASE)
        ]
        
        logger.info("✅ Link Handler initialized with private channel support")
    
    def extract_telegram_links(self, text: str) -> List[str]:
        """Extract Telegram channel/group links from text"""
        try:
            if not text:
                return []
        
            links = set()
            
            for pattern in self.link_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    # Clean up the username
                    username = match.strip().lower()
                    if username and not username.startswith('_'):  # Skip invalid usernames
                        # For private channels, add + prefix
                        if '+' in pattern.pattern:
                            username = f"+{username}"
                        links.add(username)
            
            return list(links)
        
        except Exception as e:
            logger.error(f"❌ Error extracting links: {e}")
            return []
    
    def resolve_channel_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Resolve channel information from username"""
        try:
            # Handle private channels (t.me/+ format)
            if username.startswith('+'):
                # For private channels, use the invite link directly
                invite_link = f"https://t.me/{username}"
                try:
                    # Get chat info using invite link
                    chat = self.bot.get_chat(invite_link)
                    
                    return {
                        "channel_id": chat.id,
                        "channel_name": chat.title or chat.first_name or username,
                        "username": chat.username,
                        "type": chat.type,
                        "member_count": getattr(chat, 'member_count', None),
                        "description": getattr(chat, 'description', None),
                        "is_private": True,
                        "invite_link": invite_link
                    }
                except Exception as e:
                    logger.error(f"❌ Error resolving private channel {username}: {e}")
                    return None
            else:
                # Handle public channels
                # Add @ if not present
                if not username.startswith('@'):
                    username = f"@{username}"
                
                # Get chat info
                chat = self.bot.get_chat(username)
                
                return {
                    "channel_id": chat.id,
                    "channel_name": chat.title or chat.first_name or username,
                    "username": chat.username,
                    "type": chat.type,
                    "member_count": getattr(chat, 'member_count', None),
                    "description": getattr(chat, 'description', None),
                    "is_private": False
                }
            
        except Exception as e:
            logger.error(f"❌ Error resolving channel info for {username}: {e}")
            return None
    
    def check_bot_access(self, channel_id: int) -> bool:
        """Check if bot has admin access to channel"""
        try:
            # Get bot member status
            member = self.bot.get_chat_member(channel_id, self.bot.get_me().id)
            return member.status in ['administrator', 'creator']
        except Exception as e:
            logger.error(f"❌ Error checking bot access for channel {channel_id}: {e}")
            return False
    
    def auto_add_telegram_links(self, text: str, user_id: int, db_ops) -> List[Dict[str, Any]]:
        """Automatically add Telegram channels from text"""
        try:
            # Extract usernames from text
            usernames = self.extract_telegram_links(text)
            if not usernames:
                return []
            
            added_channels = []
            
            for username in usernames:
                try:
                    # Resolve channel info
                    channel_info = self.resolve_channel_info(username)
                    
                    if channel_info:
                        # Check if bot has access
                        if self.check_bot_access(channel_info["channel_id"]):
                            # Add to database
                            success = db_ops.add_channel(
                                channel_id=channel_info["channel_id"],
                                user_id=user_id,
                                channel_name=channel_info["channel_name"],
                                username=channel_info["username"]
                            )
                        
                            if success:
                                added_channels.append(channel_info)
                                logger.info(f"✅ Auto-added channel: {channel_info['channel_name']}")
                            else:
                                logger.warning(f"⚠️ Failed to add channel: {channel_info['channel_name']}")
                        else:
                            logger.warning(f"⚠️ Bot doesn't have admin access to: {channel_info['channel_name']}")
                    else:
                        logger.warning(f"⚠️ Could not resolve channel info for: {username}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing channel {username}: {e}")
                    continue
            
            return added_channels
            
        except Exception as e:
            logger.error(f"❌ Error in auto_add_telegram_links: {e}")
            return []
    
    def validate_channel_id(self, channel_id: str) -> bool:
        """Validate if channel ID is valid"""
        try:
            # Try to get chat info
            chat = self.bot.get_chat(channel_id)
            return chat is not None
        except Exception as e:
            logger.error(f"❌ Invalid channel ID {channel_id}: {e}")
            return False