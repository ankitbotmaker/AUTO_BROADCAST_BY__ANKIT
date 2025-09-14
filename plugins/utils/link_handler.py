#!/usr/bin/env python3
"""
Link Handler Utility
Handles Telegram link detection, resolution, and channel extraction
"""

import re
import logging
from typing import List, Optional, Dict, Any
from telebot import TeleBot

logger = logging.getLogger(__name__)

class LinkHandler:
    """Enhanced link detection and resolution handler"""
    
    def __init__(self, bot: TeleBot):
        self.bot = bot
        self.link_patterns = [
            r'(https?://t\.me/[a-zA-Z0-9_]+)',
            r'(@[a-zA-Z0-9_]+)',
            r'(t\.me/[a-zA-Z0-9_]+)',
            r'(https?://telegram\.me/[a-zA-Z0-9_]+)'
        ]
    
    def extract_telegram_links(self, text: str) -> List[str]:
        """Extract all Telegram links from text"""
        if not text or not isinstance(text, str):
            return []
        
        links = []
        for pattern in self.link_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match not in links:
                    links.append(match)
        
        logger.info(f"Extracted {len(links)} links from text: {links}")
        return links
    
    def resolve_telegram_link(self, link: str) -> Optional[int]:
        """Resolve Telegram link to channel ID"""
        try:
            # Clean the link first
            link = link.strip()
            
            # Try to get chat info directly
            if link.startswith('@'):
                chat_info = self.bot.get_chat(link)
                return chat_info.id
                
            elif link.startswith('https://t.me/') or link.startswith('t.me/'):
                # Extract username preserving underscores
                username = link.split('/')[-1]
                # Remove any query parameters
                username = username.split('?')[0]
                # Ensure username is properly formatted
                if not username.startswith('@'):
                    username = f"@{username}"
                chat_info = self.bot.get_chat(username)
                return chat_info.id
                
            elif link.startswith('https://telegram.me/'):
                # Extract username preserving underscores
                username = link.split('/')[-1]
                # Remove any query parameters
                username = username.split('?')[0]
                # Ensure username is properly formatted
                if not username.startswith('@'):
                    username = f"@{username}"
                chat_info = self.bot.get_chat(username)
                return chat_info.id
                
            else:
                # Try as username (add @ if not present)
                if not link.startswith('@'):
                    link = f"@{link}"
                chat_info = self.bot.get_chat(link)
                return chat_info.id
                
        except Exception as e:
            logger.error(f"Error resolving link {link}: {e}")
            return None
    
    def auto_add_telegram_links(self, user_id: int, text: str, db_ops) -> List[Dict[str, Any]]:
        """Automatically add Telegram links as channels"""
        added_channels = []
        links = self.extract_telegram_links(text)
        
        logger.info(f"Found {len(links)} links in text: {links}")
        
        for link in links:
            try:
                logger.info(f"Processing link: {link}")
                channel_id = self.resolve_telegram_link(link)
                
                if channel_id:
                    logger.info(f"Resolved link {link} to channel ID: {channel_id}")
                    
                    # Check if channel already exists
                    existing = db_ops.get_channel(channel_id, user_id)
                    
                    if not existing:
                        # Get channel info
                        chat_info = self.bot.get_chat(channel_id)
                        channel_name = chat_info.title or chat_info.username or f"Channel {channel_id}"
                        
                        # Add channel to database
                        success = db_ops.add_channel(
                            channel_id=channel_id,
                            user_id=user_id,
                            channel_name=channel_name,
                            username=chat_info.username
                        )
                        
                        if success:
                            added_channels.append({
                                "channel_id": channel_id,
                                "channel_name": channel_name,
                                "username": chat_info.username
                            })
                            logger.info(f"Successfully added channel {channel_name} ({channel_id}) for user {user_id}")
                        else:
                            logger.error(f"Failed to add channel {channel_id} to database")
                    else:
                        logger.info(f"Channel {channel_id} already exists for user {user_id}")
                else:
                    logger.warning(f"Could not resolve link {link} to channel ID")
                    
            except Exception as e:
                logger.error(f"Error auto-adding channel {link}: {e}")
        
        logger.info(f"Auto-added {len(added_channels)} channels for user {user_id}")
        return added_channels
    
    def validate_channel_access(self, channel_id: int) -> bool:
        """Validate if bot has access to channel"""
        try:
            chat_info = self.bot.get_chat(channel_id)
            # Check if bot is admin or has send message permission
            bot_member = self.bot.get_chat_member(channel_id, self.bot.get_me().id)
            return bot_member.status in ['administrator', 'creator']
        except Exception as e:
            logger.error(f"Error validating channel access for {channel_id}: {e}")
            return False
    
    def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed channel information"""
        try:
            chat_info = self.bot.get_chat(channel_id)
            return {
                "id": chat_info.id,
                "title": chat_info.title,
                "username": chat_info.username,
                "type": chat_info.type,
                "description": getattr(chat_info, 'description', None),
                "member_count": getattr(chat_info, 'member_count', None)
            }
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_id}: {e}")
            return None
    
    def is_valid_telegram_link(self, text: str) -> bool:
        """Check if text contains valid Telegram links"""
        links = self.extract_telegram_links(text)
        return len(links) > 0
    
    def clean_links_from_text(self, text: str) -> str:
        """Remove Telegram links from text while preserving other content"""
        if not text:
            return text
        
        cleaned_text = text
        for pattern in self.link_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text)
        
        # Clean up extra whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text
    
    def format_links_display(self, links: List[str]) -> str:
        """Format links for display in messages"""
        if not links:
            return ""
        
        formatted_links = []
        for i, link in enumerate(links, 1):
            formatted_links.append(f"{i}. `{link}`")
        
        return "\n".join(formatted_links)
