#!/usr/bin/env python3
"""
Broadcast Analytics Plugin
Handles analytics and performance tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from ..database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class BroadcastAnalytics:
    """Enhanced analytics tracking for broadcast operations"""
    
    def __init__(self, db_ops: DatabaseOperations):
        self.db_ops = db_ops
    
    def track_broadcast_start(self, user_id: int, broadcast_id: str, channel_count: int):
        """Track broadcast start"""
        try:
            self.db_ops.update_analytics(user_id, "total_broadcasts", 1)
            logger.info(f"📊 Tracked broadcast start: User {user_id}, Channels {channel_count}")
        except Exception as e:
            logger.error(f"Error tracking broadcast start: {e}")
    
    def track_broadcast_completion(self, user_id: int, successful: int, failed: int):
        """Track broadcast completion"""
        try:
            if successful > 0:
                self.db_ops.update_analytics(user_id, "successful_broadcasts", successful)
            if failed > 0:
                self.db_ops.update_analytics(user_id, "failed_broadcasts", failed)
            
            total = successful + failed
            if total > 0:
                success_rate = (successful / total) * 100
                logger.info(f"📊 Tracked broadcast completion: Success {successful}, Failed {failed}, Rate {success_rate:.1f}%")
        except Exception as e:
            logger.error(f"Error tracking broadcast completion: {e}")
    
    def track_message_sent(self, user_id: int, channel_id: int):
        """Track individual message sent"""
        try:
            self.db_ops.update_analytics(user_id, "total_messages_sent", 1)
        except Exception as e:
            logger.error(f"Error tracking message sent: {e}")
    
    def track_auto_operation(self, user_id: int, operation_type: str):
        """Track auto operations (repost/delete)"""
        try:
            if operation_type == "repost":
                self.db_ops.update_analytics(user_id, "total_auto_reposts", 1)
            elif operation_type == "delete":
                self.db_ops.update_analytics(user_id, "total_auto_deletes", 1)
        except Exception as e:
            logger.error(f"Error tracking auto operation: {e}")
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user analytics"""
        try:
            analytics = self.db_ops.get_user_analytics(user_id, days)
            
            # Calculate additional metrics
            total_broadcasts = analytics.get("total_broadcasts", 0)
            successful = analytics.get("successful_broadcasts", 0)
            failed = analytics.get("failed_broadcasts", 0)
            
            success_rate = (successful / total_broadcasts * 100) if total_broadcasts > 0 else 0
            
            return {
                **analytics,
                "success_rate": round(success_rate, 2),
                "total_channels": analytics.get("total_channels", 0),
                "messages_sent": analytics.get("total_messages_sent", 0),
                "auto_reposts": analytics.get("total_auto_reposts", 0),
                "auto_deletes": analytics.get("total_auto_deletes", 0)
            }
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get system-wide analytics"""
        try:
            # This would aggregate analytics from all users
            # Implementation depends on specific requirements
            return {
                "total_users": 0,
                "total_broadcasts": 0,
                "total_channels": 0,
                "success_rate": 0.0
            }
        except Exception as e:
            logger.error(f"Error getting system analytics: {e}")
            return {}
    
    def generate_analytics_report(self, user_id: int, days: int = 30) -> str:
        """Generate formatted analytics report"""
        try:
            analytics = self.get_user_analytics(user_id, days)
            
            report = f"""
📊 **Analytics Report ({days} days)**

**📈 Broadcast Statistics:**
• Total Broadcasts: {analytics.get('total_broadcasts', 0)}
• Successful: {analytics.get('successful_broadcasts', 0)}
• Failed: {analytics.get('failed_broadcasts', 0)}
• Success Rate: {analytics.get('success_rate', 0):.1f}%

**📢 Channel Statistics:**
• Total Channels: {analytics.get('total_channels', 0)}
• Messages Sent: {analytics.get('messages_sent', 0)}

**⚡ Auto Operations:**
• Auto Reposts: {analytics.get('auto_reposts', 0)}
• Auto Deletes: {analytics.get('auto_deletes', 0)}
            """.strip()
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            return "❌ Error generating analytics report"
