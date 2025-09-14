#!/usr/bin/env python3
"""
Broadcast Manager
Main broadcast management and orchestration
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from telebot import TeleBot, types

from ..database.operations import DatabaseOperations
from ..utils.helpers import Helpers
from ..utils.logger import broadcast_logger, performance_logger
from ..utils.validators import Validators
from config import MAX_CONCURRENT_BROADCASTS, BROADCAST_DELAY, BROADCAST_TIMEOUT

logger = logging.getLogger(__name__)

class BroadcastManager:
    """Enhanced broadcast management with concurrent processing and error handling"""
    
    def __init__(self, bot: TeleBot, db_ops: DatabaseOperations):
        self.bot = bot
        self.db_ops = db_ops
        self.active_broadcasts = {}
        self.broadcast_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BROADCASTS)
        
    def start_broadcast(self, user_id: int, message, channels: List[Dict[str, Any]], 
                       repost_time: Optional[int] = None, delete_time: Optional[int] = None,
                       broadcast_type: str = "immediate") -> Dict[str, Any]:
        """Start a new broadcast"""
        try:
            # Check if user already has active broadcast
            if user_id in self.active_broadcasts:
                return {
                    "success": False,
                    "error": "Broadcast already running",
                    "message": "⚠️ **Broadcast Already Running!**\n\nPlease wait for the current broadcast to complete."
                }
            
            # Generate broadcast ID
            broadcast_id = Helpers.generate_broadcast_id(user_id)
            
            # Create broadcast record
            broadcast_data = {
                "broadcast_id": broadcast_id,
                "user_id": user_id,
                "message_type": message.content_type,
                "message_text": message.text,
                "message_caption": message.caption,
                "channels": [ch["channel_id"] for ch in channels],
                "total_channels": len(channels),
                "repost_time": repost_time,
                "delete_time": delete_time,
                "broadcast_type": broadcast_type,
                "status": "running",
                "started_at": datetime.now()
            }
            
            # Save to database
            from ..database.models import BroadcastModel
            broadcast = BroadcastModel(**broadcast_data)
            self.db_ops.create_broadcast(broadcast)
            
            # Mark as active
            self.active_broadcasts[user_id] = {
                "broadcast_id": broadcast_id,
                "started_at": datetime.now(),
                "total_channels": len(channels),
                "completed": 0,
                "failed": 0,
                "channels": channels
            }
            
            # Start broadcast process
            self._execute_broadcast(user_id, broadcast_id, message, channels, repost_time, delete_time)
            
            broadcast_logger.log_broadcast_start(user_id, broadcast_id, len(channels))
            
            return {
                "success": True,
                "broadcast_id": broadcast_id,
                "message": f"🚀 **Broadcast Started!**\n\n**Channels:** {len(channels)}\n**Status:** Processing..."
            }
            
        except Exception as e:
            logger.error(f"Error starting broadcast for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "❌ **Broadcast Failed!**\n\nPlease try again or contact support."
            }
    
    def _execute_broadcast(self, user_id: int, broadcast_id: str, message, 
                          channels: List[Dict[str, Any]], repost_time: Optional[int] = None,
                          delete_time: Optional[int] = None):
        """Execute broadcast with concurrent processing"""
        try:
            performance_logger.start_timer(f"broadcast_{broadcast_id}")
            
            # Create progress tracker
            progress_tracker = Helpers.create_progress_tracker(len(channels))
            
            # Submit tasks to thread pool
            futures = []
            for channel in channels:
                future = self.broadcast_executor.submit(
                    self._send_to_channel,
                    channel, message, broadcast_id, delete_time
                )
                futures.append(future)
            
            # Process results as they complete
            successful = 0
            failed = 0
            
            for future in as_completed(futures, timeout=BROADCAST_TIMEOUT):
                try:
                    result = future.result()
                    if result.get("success", False):
                        successful += 1
                        # Save message tracking
                        self._save_message_tracking(user_id, result, broadcast_id)
                    else:
                        failed += 1
                        logger.warning(f"Failed to send to channel {result.get('channel_id')}: {result.get('error')}")
                    
                    # Update progress
                    progress_tracker = Helpers.update_progress(progress_tracker, 1 if result.get("success") else 0, 0 if result.get("success") else 1)
                    
                    # Log progress
                    broadcast_logger.log_broadcast_progress(
                        broadcast_id, progress_tracker["completed"], 
                        progress_tracker["total"], progress_tracker["failed"]
                    )
                    
                    # Add delay between sends
                    if BROADCAST_DELAY > 0:
                        time.sleep(BROADCAST_DELAY)
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing broadcast result: {e}")
            
            # Update final status
            self._update_broadcast_status(broadcast_id, "completed", 
                                        successful_channels=successful, 
                                        failed_channels=failed)
            
            # Calculate duration
            duration = time.time() - progress_tracker["start_time"]
            performance_logger.end_timer(f"broadcast_{broadcast_id}")
            
            # Log completion
            broadcast_logger.log_broadcast_complete(broadcast_id, successful, failed, duration)
            
            # Schedule auto operations if configured
            if repost_time or delete_time:
                self._schedule_auto_operations(broadcast_id, repost_time, delete_time)
            
            # Clean up active broadcast
            if user_id in self.active_broadcasts:
                del self.active_broadcasts[user_id]
                
        except Exception as e:
            logger.error(f"Error executing broadcast {broadcast_id}: {e}")
            self._update_broadcast_status(broadcast_id, "failed", error=str(e))
            if user_id in self.active_broadcasts:
                del self.active_broadcasts[user_id]
    
    def _send_to_channel(self, channel: Dict[str, Any], message, broadcast_id: str, 
                        delete_time: Optional[int] = None) -> Dict[str, Any]:
        """Send message to a single channel"""
        result = {
            "channel_id": channel["channel_id"],
            "success": False,
            "error": None,
            "message_id": None
        }
        
        try:
            # Get formatted text from broadcast state if available
            formatted_text = None
            # This would be retrieved from broadcast state in real implementation
            
            # Send based on content type
            sent_message = self._send_message_by_type(
                channel["channel_id"], message, formatted_text
            )
            
            if sent_message:
                result["success"] = True
                result["message_id"] = sent_message.message_id
                
                # Schedule auto delete if configured
                if delete_time:
                    self._schedule_auto_delete(
                        channel["channel_id"], 
                        sent_message.message_id, 
                        delete_time
                    )
            else:
                result["error"] = "Failed to send message"
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error sending to channel {channel['channel_id']}: {e}")
        
        return result
    
    def _send_message_by_type(self, channel_id: int, message, formatted_text: Optional[str] = None):
        """Send message based on content type"""
        try:
            if message.content_type == "text":
                text_to_send = formatted_text or message.text or "📢 Broadcast Message"
                return self.bot.send_message(channel_id, text_to_send, parse_mode="Markdown")
                
            elif message.content_type == "photo":
                caption = formatted_text or message.caption or "📢 Broadcast Message"
                try:
                    return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
                except Exception:
                    return self.bot.send_photo(
                        channel_id, message.photo[-1].file_id, 
                        caption=caption, parse_mode="Markdown"
                    )
                    
            elif message.content_type == "video":
                caption = formatted_text or message.caption or "📢 Broadcast Message"
                try:
                    return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
                except Exception:
                    return self.bot.send_video(
                        channel_id, message.video.file_id, 
                        caption=caption, parse_mode="Markdown"
                    )
                    
            elif message.content_type == "document":
                caption = formatted_text or message.caption or "📢 Broadcast Message"
                try:
                    return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
                except Exception:
                    return self.bot.send_document(
                        channel_id, message.document.file_id, 
                        caption=caption, parse_mode="Markdown"
                    )
                    
            else:
                # Default to forwarding
                return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
                
        except Exception as e:
            logger.error(f"Error sending {message.content_type} to channel {channel_id}: {e}")
            return None
    
    def _save_message_tracking(self, user_id: int, result: Dict[str, Any], broadcast_id: str):
        """Save message tracking for auto operations"""
        try:
            from ..database.models import BroadcastMessageModel
            message = BroadcastMessageModel(
                user_id=user_id,
                channel_id=result["channel_id"],
                message_id=result["message_id"],
                broadcast_id=broadcast_id,
                message_type="broadcast"
            )
            self.db_ops.save_broadcast_message(message)
        except Exception as e:
            logger.error(f"Error saving message tracking: {e}")
    
    def _schedule_auto_operations(self, broadcast_id: str, repost_time: Optional[int], 
                                 delete_time: Optional[int]):
        """Schedule auto repost and delete operations"""
        try:
            # This would integrate with a scheduler service
            # For now, just log the scheduling
            if repost_time:
                logger.info(f"Scheduled auto repost for broadcast {broadcast_id} in {repost_time} minutes")
            if delete_time:
                logger.info(f"Scheduled auto delete for broadcast {broadcast_id} in {delete_time} minutes")
        except Exception as e:
            logger.error(f"Error scheduling auto operations: {e}")
    
    def _schedule_auto_delete(self, channel_id: int, message_id: int, delete_time: int):
        """Schedule auto delete for a message"""
        try:
            # This would integrate with a scheduler service
            logger.info(f"Scheduled auto delete for message {message_id} in channel {channel_id} after {delete_time} minutes")
        except Exception as e:
            logger.error(f"Error scheduling auto delete: {e}")
    
    def _update_broadcast_status(self, broadcast_id: str, status: str, **kwargs):
        """Update broadcast status in database"""
        try:
            self.db_ops.update_broadcast_status(broadcast_id, status, **kwargs)
        except Exception as e:
            logger.error(f"Error updating broadcast status: {e}")
    
    def stop_broadcast(self, user_id: int) -> Dict[str, Any]:
        """Stop active broadcast for user"""
        try:
            if user_id not in self.active_broadcasts:
                return {
                    "success": False,
                    "message": "❌ **No Active Broadcast!**\n\nNo broadcast is currently running."
                }
            
            broadcast_info = self.active_broadcasts[user_id]
            broadcast_id = broadcast_info["broadcast_id"]
            
            # Update status to cancelled
            self._update_broadcast_status(broadcast_id, "cancelled")
            
            # Remove from active broadcasts
            del self.active_broadcasts[user_id]
            
            logger.info(f"Broadcast {broadcast_id} stopped for user {user_id}")
            
            return {
                "success": True,
                "message": "🛑 **Broadcast Stopped!**\n\nBroadcast has been successfully stopped."
            }
            
        except Exception as e:
            logger.error(f"Error stopping broadcast for user {user_id}: {e}")
            return {
                "success": False,
                "message": "❌ **Error Stopping Broadcast!**\n\nPlease try again or contact support."
            }
    
    def get_broadcast_status(self, user_id: int) -> Dict[str, Any]:
        """Get current broadcast status for user"""
        if user_id not in self.active_broadcasts:
            return {
                "active": False,
                "message": "No active broadcast"
            }
        
        broadcast_info = self.active_broadcasts[user_id]
        return {
            "active": True,
            "broadcast_id": broadcast_info["broadcast_id"],
            "started_at": broadcast_info["started_at"],
            "total_channels": broadcast_info["total_channels"],
            "completed": broadcast_info["completed"],
            "failed": broadcast_info["failed"],
            "progress": (broadcast_info["completed"] / broadcast_info["total_channels"] * 100) if broadcast_info["total_channels"] > 0 else 0
        }
    
    def get_active_broadcasts(self) -> List[Dict[str, Any]]:
        """Get all active broadcasts"""
        return list(self.active_broadcasts.values())
    
    def cleanup_completed_broadcasts(self):
        """Clean up completed broadcasts"""
        try:
            current_time = datetime.now()
            to_remove = []
            
            for user_id, broadcast_info in self.active_broadcasts.items():
                # Remove broadcasts older than 1 hour
                if (current_time - broadcast_info["started_at"]).total_seconds() > 3600:
                    to_remove.append(user_id)
            
            for user_id in to_remove:
                del self.active_broadcasts[user_id]
                logger.info(f"Cleaned up old broadcast for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up broadcasts: {e}")
    
    def shutdown(self):
        """Shutdown broadcast manager"""
        try:
            # Cancel all active broadcasts
            for user_id in list(self.active_broadcasts.keys()):
                self.stop_broadcast(user_id)
            
            # Shutdown thread pool
            self.broadcast_executor.shutdown(wait=True)
            
            logger.info("Broadcast manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during broadcast manager shutdown: {e}")
