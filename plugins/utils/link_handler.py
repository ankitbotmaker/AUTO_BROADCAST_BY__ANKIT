#!/usr/bin/env python3
"""
Link Handler
Handles Telegram link detection and channel resolution
"""

import logging
import re
from typing import Dict, List, Optional, Any
from ..database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class LinkHandler:
    """Enhanced link handler with automatic channel detection and resolution"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Telegram link patterns
        self.link_patterns = [
            re.compile(r'https?://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r'https?://telegram\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r't\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r'telegram\.me/([a-zA-Z0-9_]+)', re.IGNORECASE),
            re.compile(r'@([a-zA-Z0-9_]+)', re.IGNORECASE)
        ]
        
        logger.info("✅ Link Handler initialized")
    
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
                        links.add(username)
            
            return list(links)
        
        except Exception as e:
            logger.error(f"❌ Error extracting links: {e}")
            return []
    
    def resolve_channel_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Resolve channel information from username"""
        try:
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
                "description": getattr(chat, 'description', None)
            }
                
        except Exception as e:
            logger.warning(f"⚠️ Could not resolve channel {username}: {e}")
            return None
    
    def auto_add_telegram_links(self, user_id: int, text: str, 
                               db_ops: DatabaseOperations) -> List[Dict[str, Any]]:
        """Automatically detect and add Telegram channels from text"""
        try:
            if not text:
                return []
            
            # Extract links
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
                                logger.warning(f"⚠️ Failed to add channel to database: {username}")
                        else:
                            logger.warning(f"⚠️ Bot doesn't have access to channel: {username}")
                    else:
                        logger.warning(f"⚠️ Could not resolve channel: {username}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing channel {username}: {e}")
                    continue
            
            return added_channels
            
        except Exception as e:
            logger.error(f"❌ Error auto-adding links: {e}")
            return []
    
    def check_bot_access(self, channel_id: int) -> bool:
        """Check if bot has access to a channel"""
        try:
            # Try to get chat member (bot itself)
            bot_info = self.bot.get_me()
            member = self.bot.get_chat_member(channel_id, bot_info.id)
            
            # Check if bot is admin or member
            return member.status in ['administrator', 'member']
        
        except Exception as e:
            logger.warning(f"⚠️ Cannot access channel {channel_id}: {e}")
            return False
    
    def validate_telegram_link(self, link: str) -> Dict[str, Any]:
        """Validate a Telegram link and return info"""
        try:
            usernames = self.extract_telegram_links(link)
            
            if not usernames:
                return {
                    "valid": False,
                    "error": "No valid Telegram username found in the link"
                }
            
            username = usernames[0]  # Take the first one
            channel_info = self.resolve_channel_info(username)
            
            if channel_info:
                has_access = self.check_bot_access(channel_info["channel_id"])
                
                return {
                    "valid": True,
                    "channel_info": channel_info,
                    "bot_has_access": has_access,
                    "access_note": "✅ Bot has access" if has_access else "❌ Bot needs to be added as admin"
                }
            else:
                return {
                    "valid": False,
                    "error": "Channel not found or is private"
                }
        
        except Exception as e:
            logger.error(f"❌ Error validating link: {e}")
            return {
                "valid": False,
                "error": f"Error validating link: {str(e)}"
            }
    
    def get_channel_invite_link(self, channel_id: int) -> Optional[str]:
        """Get invite link for a channel"""
        try:
            # This would require admin rights
            invite_link = self.bot.export_chat_invite_link(channel_id)
            return invite_link
        except Exception as e:
            logger.warning(f"⚠️ Could not get invite link for {channel_id}: {e}")
            return None
    
    def format_channel_info(self, channel_info: Dict[str, Any]) -> str:
        """Format channel info for display"""
        try:
            name = channel_info.get("channel_name", "Unknown")
            username = channel_info.get("username", "")
            channel_type = channel_info.get("type", "channel")
            member_count = channel_info.get("member_count")
            
            formatted = f"<b>{name}</b>"
            
            if username:
                formatted += f" (@{username})"
            
            formatted += f"\n<b>Type:</b> {channel_type.title()}"
            
            if member_count:
                formatted += f"\n<b>Members:</b> {member_count:,}"
            
            return formatted
        
        except Exception as e:
            logger.error(f"❌ Error formatting channel info: {e}")
            return "Error formatting channel information"
    
    def bulk_validate_channels(self, channel_list: List[str]) -> Dict[str, Any]:
        """Validate multiple channels at once"""
        try:
            results = {
                "valid_channels": [],
                "invalid_channels": [],
                "total_processed": 0,
                "success_rate": 0
            }
            
            for channel_link in channel_list:
                result = self.validate_telegram_link(channel_link.strip())
                results["total_processed"] += 1
                
                if result["valid"]:
                    results["valid_channels"].append({
                        "link": channel_link,
                        "info": result["channel_info"],
                        "has_access": result["bot_has_access"]
                    })
                else:
                    results["invalid_channels"].append({
                        "link": channel_link,
                        "error": result["error"]
                    })
            
            if results["total_processed"] > 0:
                results["success_rate"] = (len(results["valid_channels"]) / results["total_processed"]) * 100
            
            return results
        
        except Exception as e:
            logger.error(f"❌ Error bulk validating channels: {e}")
            return {
                "valid_channels": [],
                "invalid_channels": [],
                "total_processed": 0,
                "success_rate": 0,
                "error": str(e)
            }