#!/usr/bin/env python3
"""
Broadcast Scheduler Plugin
Handles scheduled broadcasts and auto operations
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
import schedule

logger = logging.getLogger(__name__)

class BroadcastScheduler:
    """Enhanced scheduler for broadcast operations"""
    
    def __init__(self, bot, db_ops):
        self.bot = bot
        self.db_ops = db_ops
        self.scheduled_tasks = {}
        self.running = False
        self.scheduler_thread = None
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("📅 Broadcast scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("📅 Broadcast scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)
    
    def schedule_auto_repost(self, broadcast_id: str, channel_id: int, message_id: int, 
                           repost_time: int, callback: Callable):
        """Schedule auto repost for a message"""
        try:
            # Calculate repost time
            repost_datetime = datetime.now() + timedelta(minutes=repost_time)
            
            # Schedule the repost
            schedule.every().day.at(repost_datetime.strftime("%H:%M")).do(
                self._execute_auto_repost,
                broadcast_id, channel_id, message_id, callback
            )
            
            # Store task info
            task_id = f"repost_{broadcast_id}_{channel_id}_{message_id}"
            self.scheduled_tasks[task_id] = {
                "type": "repost",
                "broadcast_id": broadcast_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "scheduled_time": repost_datetime
            }
            
            logger.info(f"📅 Scheduled auto repost for {channel_id} in {repost_time} minutes")
            
        except Exception as e:
            logger.error(f"Error scheduling auto repost: {e}")
    
    def schedule_auto_delete(self, broadcast_id: str, channel_id: int, message_id: int, 
                           delete_time: int, callback: Callable):
        """Schedule auto delete for a message"""
        try:
            # Calculate delete time
            delete_datetime = datetime.now() + timedelta(minutes=delete_time)
            
            # Schedule the delete
            schedule.every().day.at(delete_datetime.strftime("%H:%M")).do(
                self._execute_auto_delete,
                broadcast_id, channel_id, message_id, callback
            )
            
            # Store task info
            task_id = f"delete_{broadcast_id}_{channel_id}_{message_id}"
            self.scheduled_tasks[task_id] = {
                "type": "delete",
                "broadcast_id": broadcast_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "scheduled_time": delete_datetime
            }
            
            logger.info(f"📅 Scheduled auto delete for {channel_id} in {delete_time} minutes")
            
        except Exception as e:
            logger.error(f"Error scheduling auto delete: {e}")
    
    def _execute_auto_repost(self, broadcast_id: str, channel_id: int, message_id: int, callback: Callable):
        """Execute auto repost"""
        try:
            logger.info(f"🔄 Executing auto repost for channel {channel_id}")
            callback(broadcast_id, channel_id, message_id, "repost")
            
            # Remove from scheduled tasks
            task_id = f"repost_{broadcast_id}_{channel_id}_{message_id}"
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]
                
        except Exception as e:
            logger.error(f"Error executing auto repost: {e}")
    
    def _execute_auto_delete(self, broadcast_id: str, channel_id: int, message_id: int, callback: Callable):
        """Execute auto delete"""
        try:
            logger.info(f"🗑️ Executing auto delete for channel {channel_id}")
            callback(broadcast_id, channel_id, message_id, "delete")
            
            # Remove from scheduled tasks
            task_id = f"delete_{broadcast_id}_{channel_id}_{message_id}"
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]
                
        except Exception as e:
            logger.error(f"Error executing auto delete: {e}")
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        try:
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]
                logger.info(f"📅 Cancelled task: {task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    def get_scheduled_tasks(self) -> Dict[str, Any]:
        """Get all scheduled tasks"""
        return self.scheduled_tasks.copy()
    
    def clear_all_tasks(self):
        """Clear all scheduled tasks"""
        try:
            schedule.clear()
            self.scheduled_tasks.clear()
            logger.info("📅 Cleared all scheduled tasks")
        except Exception as e:
            logger.error(f"Error clearing tasks: {e}")
