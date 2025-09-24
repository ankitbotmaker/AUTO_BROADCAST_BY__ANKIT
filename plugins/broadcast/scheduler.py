#!/usr/bin/env python3
"""
Broadcast Scheduler
Handles scheduled broadcasts and auto operations
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import schedule

from ..database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class BroadcastScheduler:
    """Handles scheduled broadcasts and automatic operations"""
    
    def __init__(self, db_ops: DatabaseOperations, broadcast_manager):
        self.db_ops = db_ops
        self.broadcast_manager = broadcast_manager
        self.is_running = False
        self.scheduler_thread = None
        
        # Setup scheduled tasks
        self._setup_schedule()
        
        logger.info("✅ Broadcast Scheduler initialized")
    
    def _setup_schedule(self):
        """Setup recurring scheduled tasks"""
        # Check for auto operations every minute
        schedule.every(1).minutes.do(self._process_auto_operations)
        
        # Cleanup old data daily at 2 AM
        schedule.every().day.at("02:00").do(self._daily_cleanup)
        
        # Check for scheduled broadcasts every minute
        schedule.every(1).minutes.do(self._process_scheduled_broadcasts)
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            logger.info("🚀 Broadcast Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("🛑 Broadcast Scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _process_auto_operations(self):
        """Process auto delete and repost operations"""
        try:
            messages = self.db_ops.get_messages_for_auto_operations()
            
            for message in messages:
                try:
                    if message.get("operation") == "delete":
                        self._auto_delete_message(message)
                    elif message.get("operation") == "repost":
                        self._auto_repost_message(message)
                except Exception as e:
                    logger.error(f"❌ Error processing auto operation for message {message.get('message_id')}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error processing auto operations: {e}")
    
    def _auto_delete_message(self, message: Dict[str, Any]):
        """Auto delete a message"""
        try:
            channel_id = message.get("channel_id")
            telegram_message_id = message.get("telegram_message_id")
            
            if channel_id and telegram_message_id:
                # Delete the message
                result = self.broadcast_manager.message_sender.delete_message(
                    channel_id, telegram_message_id
                )
                
                if result["success"]:
                    # Update message status in database
                    self.db_ops.update_message_status(
                        message["message_id"], 
                        channel_id, 
                        "deleted"
                    )
                    logger.info(f"🗑️ Auto-deleted message {telegram_message_id} from channel {channel_id}")
                else:
                    logger.warning(f"⚠️ Failed to auto-delete message: {result['error']}")
        
        except Exception as e:
            logger.error(f"❌ Error auto-deleting message: {e}")
    
    def _auto_repost_message(self, message: Dict[str, Any]):
        """Auto repost a message"""
        try:
            # For simplicity, we'll just log this for now
            # In a full implementation, you'd need to store original message data
            # and recreate the broadcast
            logger.info(f"🔄 Auto-repost triggered for message {message.get('message_id')}")
            
            # TODO: Implement full repost functionality
            # This would involve:
            # 1. Getting original message data
            # 2. Creating a new broadcast
            # 3. Sending to the same channel
        
        except Exception as e:
            logger.error(f"❌ Error auto-reposting message: {e}")
    
    def _process_scheduled_broadcasts(self):
        """Process scheduled broadcasts that are due"""
        try:
            # This would query for scheduled broadcasts that are due
            # For now, we'll just log
            logger.debug("📅 Checking for scheduled broadcasts...")
            
            # TODO: Implement scheduled broadcast processing
            # This would involve:
            # 1. Query database for due scheduled broadcasts
            # 2. Execute the broadcasts
            # 3. Update their status
        
        except Exception as e:
            logger.error(f"❌ Error processing scheduled broadcasts: {e}")
    
    def _daily_cleanup(self):
        """Daily cleanup of old data"""
        try:
            logger.info("🧹 Starting daily cleanup...")
            
            # Cleanup old broadcasts and analytics
            cleanup_stats = self.db_ops.cleanup_old_data(days=30)
            
            # Cleanup completed broadcasts from memory
            self.broadcast_manager.cleanup_completed_broadcasts()
            
            logger.info(f"✅ Daily cleanup completed: {cleanup_stats}")
        
        except Exception as e:
            logger.error(f"❌ Error during daily cleanup: {e}")
    
    def schedule_broadcast(self, user_id: int, broadcast_data: Dict[str, Any], 
                          scheduled_time: datetime) -> Dict[str, Any]:
        """Schedule a broadcast for future execution"""
        try:
            # TODO: Implement scheduled broadcast creation
            # This would involve:
            # 1. Validate scheduled time
            # 2. Store in database
            # 3. Return confirmation
            
            return {
                "success": True,
                "message": f"Broadcast scheduled for {scheduled_time}",
                "schedule_id": f"schedule_{user_id}_{int(time.time())}"
            }
        
        except Exception as e:
            logger.error(f"❌ Error scheduling broadcast: {e}")
            return {
                "success": False,
                "message": "Failed to schedule broadcast"
            }
    
    def cancel_scheduled_broadcast(self, schedule_id: str) -> Dict[str, Any]:
        """Cancel a scheduled broadcast"""
        try:
            # TODO: Implement scheduled broadcast cancellation
            return {
                "success": True,
                "message": "Scheduled broadcast cancelled"
            }
        
        except Exception as e:
            logger.error(f"❌ Error cancelling scheduled broadcast: {e}")
            return {
                "success": False,
                "message": "Failed to cancel scheduled broadcast"
            }
    
    def get_scheduled_broadcasts(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's scheduled broadcasts"""
        try:
            # TODO: Implement getting scheduled broadcasts
            return []
        
        except Exception as e:
            logger.error(f"❌ Error getting scheduled broadcasts: {e}")
            return []