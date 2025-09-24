#!/usr/bin/env python3
"""
Channel Detector
Automatically detect user's admin channels and add bot
"""

import logging
from typing import Dict, List, Optional, Any
from ..database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class ChannelDetector:
    """Automatically detect and add user's admin channels"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("✅ Channel Detector initialized")
    
    def detect_user_admin_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Detect channels where user is admin/owner"""
        try:
            admin_channels = []
            
            # Get user's chat list (requires API credentials)
            # This is a simplified version - in real implementation you'd use Pyrogram/Telethon
            
            # For now, we'll provide instructions to user
            return []
            
        except Exception as e:
            logger.error(f"❌ Error detecting admin channels: {e}")
            return []
    
    def check_bot_admin_status(self, channel_id: int) -> Dict[str, Any]:
        """Check if bot is admin in channel"""
        try:
            bot_info = self.bot.get_me()
            member = self.bot.get_chat_member(channel_id, bot_info.id)
            
            return {
                "is_admin": member.status in ['administrator', 'creator'],
                "status": member.status,
                "can_post_messages": getattr(member, 'can_post_messages', False),
                "can_edit_messages": getattr(member, 'can_edit_messages', False),
                "can_delete_messages": getattr(member, 'can_delete_messages', False)
            }
        except Exception as e:
            logger.warning(f"⚠️ Cannot check bot status in {channel_id}: {e}")
            return {
                "is_admin": False,
                "status": "not_member",
                "error": str(e)
            }
    
    def get_channel_info_by_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get channel information by ID"""
        try:
            chat = self.bot.get_chat(channel_id)
            
            return {
                "channel_id": chat.id,
                "title": chat.title,
                "username": chat.username,
                "type": chat.type,
                "member_count": getattr(chat, 'member_count', None),
                "description": getattr(chat, 'description', None)
            }
        except Exception as e:
            logger.warning(f"⚠️ Cannot get channel info for {channel_id}: {e}")
            return None
    
    def auto_add_channel_if_admin(self, user_id: int, channel_id: int, 
                                 db_ops: DatabaseOperations) -> Dict[str, Any]:
        """Automatically add channel if bot is admin"""
        try:
            # Check if bot is admin
            bot_status = self.check_bot_admin_status(channel_id)
            
            if not bot_status["is_admin"]:
                return {
                    "success": False,
                    "error": "Bot is not admin in this channel",
                    "bot_status": bot_status
                }
            
            # Get channel info
            channel_info = self.get_channel_info_by_id(channel_id)
            
            if not channel_info:
                return {
                    "success": False,
                    "error": "Could not get channel information"
                }
            
            # Add to database
            success = db_ops.add_channel(
                channel_id=channel_id,
                user_id=user_id,
                channel_name=channel_info["title"],
                username=channel_info["username"]
            )
            
            if success:
                return {
                    "success": True,
                    "channel_info": channel_info,
                    "bot_status": bot_status,
                    "message": f"✅ Added {channel_info['title']} successfully!"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to add channel to database"
                }
                
        except Exception as e:
            logger.error(f"❌ Error auto-adding channel: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def bulk_add_channels_by_ids(self, user_id: int, channel_ids: List[int], 
                                db_ops: DatabaseOperations) -> Dict[str, Any]:
        """Bulk add multiple channels by IDs"""
        try:
            results = {
                "total_channels": len(channel_ids),
                "successful_adds": 0,
                "failed_adds": 0,
                "added_channels": [],
                "failed_channels": [],
                "errors": []
            }
            
            for channel_id in channel_ids:
                try:
                    result = self.auto_add_channel_if_admin(user_id, channel_id, db_ops)
                    
                    if result["success"]:
                        results["successful_adds"] += 1
                        results["added_channels"].append({
                            "channel_id": channel_id,
                            "channel_info": result["channel_info"]
                        })
                    else:
                        results["failed_adds"] += 1
                        results["failed_channels"].append({
                            "channel_id": channel_id,
                            "error": result["error"]
                        })
                        
                except Exception as e:
                    results["failed_adds"] += 1
                    results["errors"].append(f"Channel {channel_id}: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in bulk add: {e}")
            return {
                "total_channels": len(channel_ids),
                "successful_adds": 0,
                "failed_adds": len(channel_ids),
                "added_channels": [],
                "failed_channels": [],
                "errors": [str(e)]
            }
    
    def validate_channel_id(self, channel_id_str: str) -> Optional[int]:
        """Validate and convert channel ID string to integer"""
        try:
            # Remove any prefixes and clean the ID
            cleaned_id = channel_id_str.strip().replace("-100", "").replace("-", "")
            
            # Convert to integer
            channel_id = int(cleaned_id)
            
            # Telegram channel IDs are typically negative and large
            if channel_id > 0:
                channel_id = -1000000000000 - channel_id
            
            return channel_id
            
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Invalid channel ID format: {channel_id_str}")
            return None
    
    def get_channel_invite_link(self, channel_id: int) -> Optional[str]:
        """Get invite link for a channel (if bot has permission)"""
        try:
            invite_link = self.bot.export_chat_invite_link(channel_id)
            return invite_link
        except Exception as e:
            logger.warning(f"⚠️ Could not get invite link for {channel_id}: {e}")
            return None
