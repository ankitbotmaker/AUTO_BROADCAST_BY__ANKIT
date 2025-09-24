#!/usr/bin/env python3
"""
Broadcast Manager
Handles broadcast operations with threading and queue management
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import uuid

from ..database.models import BroadcastModel, generate_broadcast_id
from ..database.operations import DatabaseOperations
from .message_sender import MessageSender
from config import MAX_CONCURRENT_BROADCASTS, BROADCAST_DELAY

logger = logging.getLogger(__name__)

class BroadcastManager:
    """Enhanced broadcast manager with threading and queue management"""
    
    def __init__(self, bot, db_ops: DatabaseOperations):
        self.bot = bot
        self.db_ops = db_ops
        self.message_sender = MessageSender(bot, db_ops)
        
        # Broadcast tracking
        self.active_broadcasts = {}
        self.broadcast_queues = {}
        self.broadcast_threads = {}
        
        # Thread pool for concurrent broadcasts
        self.executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BROADCASTS)
        
        # Shutdown flag
        self._shutdown = False
        
        logger.info("✅ Broadcast Manager initialized")
    
    def start_broadcast(self, user_id: int, message_data: Dict[str, Any], 
                       channels: List[Dict[str, Any]], settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start a new broadcast"""
        try:
            # Check if user already has an active broadcast
            if user_id in self.active_broadcasts:
                return {
                    "success": False,
                    "message": "❌ You already have an active broadcast running. Please wait for it to complete.",
                    "broadcast_id": None
                }
            
            # Validate inputs
            if not channels:
                return {
                    "success": False,
                    "message": "❌ No channels provided for broadcast.",
                    "broadcast_id": None
                }
            
            # Create broadcast record
            broadcast_id = generate_broadcast_id(user_id)
            channel_ids = [ch["channel_id"] for ch in channels]
            
            broadcast = BroadcastModel(
                broadcast_id=broadcast_id,
                user_id=user_id,
                message_type=message_data.get("type", "text"),
                message_content=message_data.get("text", ""),
                caption=message_data.get("caption"),
                file_id=message_data.get("file_id"),
                channels=channel_ids,
                auto_delete_time=settings.get("auto_delete_time") if settings else None,
                auto_repost_time=settings.get("auto_repost_time") if settings else None,
                settings=settings or {}
            )
            
            # Save to database
            if not self.db_ops.create_broadcast(broadcast):
                return {
                    "success": False,
                    "message": "❌ Failed to create broadcast record.",
                    "broadcast_id": None
                }
            
            # Start broadcast in background thread
            self.active_broadcasts[user_id] = {
                "broadcast_id": broadcast_id,
                "status": "starting",
                "total_channels": len(channels),
                "completed_channels": 0,
                "successful_sends": 0,
                "failed_sends": 0,
                "start_time": datetime.utcnow(),
                "thread": None
            }
            
            # Submit to thread pool
            future = self.executor.submit(
                self._execute_broadcast,
                user_id, broadcast_id, message_data, channels, settings
            )
            
            self.active_broadcasts[user_id]["thread"] = future
            
            return {
                "success": True,
                "message": f"🚀 Broadcast started! Sending to {len(channels)} channels...",
                "broadcast_id": broadcast_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error starting broadcast: {e}")
            return {
                "success": False,
                "message": "❌ An error occurred while starting the broadcast.",
                "broadcast_id": None
            }
    
    def _execute_broadcast(self, user_id: int, broadcast_id: str, 
                          message_data: Dict[str, Any], channels: List[Dict[str, Any]], 
                          settings: Dict[str, Any] = None):
        """Execute broadcast in background thread"""
        try:
            logger.info(f"🚀 Starting broadcast {broadcast_id} for user {user_id}")
            
            # Update status to running
            self.db_ops.update_broadcast_status(broadcast_id, "running")
            self.active_broadcasts[user_id]["status"] = "running"
            
            successful_sends = 0
            failed_sends = 0
            
            # Send to each channel
            for i, channel in enumerate(channels):
                if self._shutdown or user_id not in self.active_broadcasts:
                    logger.info(f"🛑 Broadcast {broadcast_id} stopped by user or shutdown")
                    break
                
                try:
                    # Send message to channel
                    result = self.message_sender.send_message(
                        channel_id=channel["channel_id"],
                        message_data=message_data,
                        user_id=user_id,
                        broadcast_id=broadcast_id,
                        settings=settings
                    )
                    
                    if result["success"]:
                        successful_sends += 1
                        logger.info(f"✅ Message sent to {channel['channel_name']}")
                    else:
                        failed_sends += 1
                        logger.warning(f"❌ Failed to send to {channel['channel_name']}: {result['error']}")
                    
                    # Update progress
                    self.active_broadcasts[user_id]["completed_channels"] = i + 1
                    self.active_broadcasts[user_id]["successful_sends"] = successful_sends
                    self.active_broadcasts[user_id]["failed_sends"] = failed_sends
                    
                    # Delay between sends
                    if i < len(channels) - 1:  # Don't delay after last message
                        time.sleep(BROADCAST_DELAY)
                        
                except Exception as e:
                    failed_sends += 1
                    logger.error(f"❌ Error sending to channel {channel.get('channel_name', 'Unknown')}: {e}")
            
            # Update final status
            if user_id in self.active_broadcasts:
                final_status = "completed" if successful_sends > 0 else "failed"
                
                self.db_ops.update_broadcast_status(
                    broadcast_id, 
                    final_status,
                    successful_sends=successful_sends,
                    failed_sends=failed_sends
                )
                
                # Send completion notification
                self._send_completion_notification(user_id, broadcast_id, successful_sends, failed_sends)
                
                # Clean up
                del self.active_broadcasts[user_id]
                
                logger.info(f"✅ Broadcast {broadcast_id} completed: {successful_sends} sent, {failed_sends} failed")
                
        except Exception as e:
            logger.error(f"❌ Error executing broadcast {broadcast_id}: {e}")
            if user_id in self.active_broadcasts:
                self.db_ops.update_broadcast_status(broadcast_id, "failed", error_details={"error": str(e)})
                del self.active_broadcasts[user_id]
    
    def stop_broadcast(self, user_id: int) -> Dict[str, Any]:
        """Stop active broadcast for user"""
        try:
            if user_id not in self.active_broadcasts:
                return {
                    "success": False,
                    "message": "❌ No active broadcast found to stop."
                }
            
            broadcast_info = self.active_broadcasts[user_id]
            broadcast_id = broadcast_info["broadcast_id"]
            
            # Cancel the thread
            if broadcast_info.get("thread"):
                broadcast_info["thread"].cancel()
            
            # Update database
            self.db_ops.update_broadcast_status(broadcast_id, "cancelled")
            
            # Clean up
            del self.active_broadcasts[user_id]
            
            return {
                "success": True,
                "message": f"🛑 Broadcast stopped. Sent to {broadcast_info['successful_sends']} channels."
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping broadcast: {e}")
            return {
                "success": False,
                "message": "❌ Error stopping broadcast."
            }
    
    def get_broadcast_status(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get current broadcast status for user"""
        try:
            if user_id in self.active_broadcasts:
                broadcast_info = self.active_broadcasts[user_id]
                
                # Calculate progress
                progress = 0
                if broadcast_info["total_channels"] > 0:
                    progress = (broadcast_info["completed_channels"] / broadcast_info["total_channels"]) * 100
                
                # Calculate elapsed time
                elapsed = datetime.utcnow() - broadcast_info["start_time"]
                
                return {
                    "broadcast_id": broadcast_info["broadcast_id"],
                    "status": broadcast_info["status"],
                    "total_channels": broadcast_info["total_channels"],
                    "completed_channels": broadcast_info["completed_channels"],
                    "successful_sends": broadcast_info["successful_sends"],
                    "failed_sends": broadcast_info["failed_sends"],
                    "progress_percentage": round(progress, 1),
                    "elapsed_time": str(elapsed).split(".")[0],  # Remove microseconds
                    "is_active": True
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting broadcast status: {e}")
            return None
    
    def _send_completion_notification(self, user_id: int, broadcast_id: str, 
                                    successful_sends: int, failed_sends: int):
        """Send broadcast completion notification to user"""
        try:
            total_channels = successful_sends + failed_sends
            success_rate = (successful_sends / total_channels * 100) if total_channels > 0 else 0
            
            status_emoji = "✅" if successful_sends > 0 else "❌"
            
            message = f"""
{status_emoji} <b>Broadcast Completed!</b>

<blockquote>
<b>📊 Results:</b>
• <b>Total Channels:</b> {total_channels}
• <b>✅ Successful:</b> {successful_sends}
• <b>❌ Failed:</b> {failed_sends}
• <b>📈 Success Rate:</b> {success_rate:.1f}%
</blockquote>

<b>🆔 Broadcast ID:</b> <code>{broadcast_id}</code>
            """.strip()
            
            self.bot.send_message(
                user_id,
                message,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"❌ Error sending completion notification: {e}")
    
    def cleanup_completed_broadcasts(self):
        """Clean up old completed broadcasts from memory"""
        try:
            current_time = datetime.utcnow()
            users_to_remove = []
            
            for user_id, broadcast_info in self.active_broadcasts.items():
                # Remove broadcasts older than 1 hour that are not running
                if broadcast_info["status"] != "running":
                    elapsed = current_time - broadcast_info["start_time"]
                    if elapsed > timedelta(hours=1):
                        users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                del self.active_broadcasts[user_id]
                logger.info(f"🧹 Cleaned up completed broadcast for user {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up broadcasts: {e}")
    
    def get_active_broadcasts_count(self) -> int:
        """Get count of active broadcasts"""
        return len([b for b in self.active_broadcasts.values() if b["status"] == "running"])
    
    def get_all_active_broadcasts(self) -> Dict[int, Dict[str, Any]]:
        """Get all active broadcasts (admin function)"""
        return self.active_broadcasts.copy()
    
    def shutdown(self):
        """Shutdown broadcast manager"""
        logger.info("🛑 Shutting down Broadcast Manager...")
        self._shutdown = True
        
        # Cancel all active broadcasts
        for user_id in list(self.active_broadcasts.keys()):
            self.stop_broadcast(user_id)
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("✅ Broadcast Manager shutdown complete")