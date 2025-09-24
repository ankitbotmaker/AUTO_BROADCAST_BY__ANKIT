#!/usr/bin/env python3
"""
Broadcast Analytics
Handles analytics collection and reporting
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ..database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

class BroadcastAnalytics:
    """Handles broadcast analytics and reporting"""
    
    def __init__(self, db_ops: DatabaseOperations):
        self.db_ops = db_ops
        logger.info("✅ Broadcast Analytics initialized")
    
    def record_broadcast_start(self, user_id: int, broadcast_id: str, 
                              channel_count: int) -> bool:
        """Record broadcast start"""
        try:
            return self.db_ops.update_analytics(
                user_id, 
                "broadcasts_started", 
                1
            )
        except Exception as e:
            logger.error(f"❌ Error recording broadcast start: {e}")
            return False
    
    def record_broadcast_completion(self, user_id: int, broadcast_id: str, 
                                   successful_sends: int, failed_sends: int) -> bool:
        """Record broadcast completion"""
        try:
            # Record completion
            self.db_ops.update_analytics(user_id, "broadcasts_completed", 1)
            
            # Record message stats
            self.db_ops.update_analytics(user_id, "messages_sent", successful_sends)
            self.db_ops.update_analytics(user_id, "messages_failed", failed_sends)
            
            return True
        except Exception as e:
            logger.error(f"❌ Error recording broadcast completion: {e}")
            return False
    
    def get_user_analytics_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user analytics"""
        try:
            analytics = self.db_ops.get_user_analytics(user_id, days)
            
            # Add calculated metrics
            if analytics:
                total_messages = analytics.get("total_messages_sent", 0) + analytics.get("messages_failed", 0)
                success_rate = 0
                if total_messages > 0:
                    success_rate = (analytics.get("total_messages_sent", 0) / total_messages) * 100
                
                analytics["success_rate"] = round(success_rate, 2)
                analytics["total_messages"] = total_messages
            
            return analytics
        except Exception as e:
            logger.error(f"❌ Error getting user analytics: {e}")
            return {}
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get system-wide analytics (admin function)"""
        try:
            stats = self.db_ops.get_database_stats()
            
            return {
                "total_users": stats.get("users", 0),
                "total_channels": stats.get("channels", 0),
                "total_broadcasts": stats.get("broadcasts", 0),
                "total_analytics_entries": stats.get("analytics", 0),
                "last_updated": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting system analytics: {e}")
            return {}
    
    def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by activity"""
        try:
            # This would need a more complex query
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"❌ Error getting top users: {e}")
            return []
    
    def export_analytics(self, user_id: int, format: str = "json") -> Optional[str]:
        """Export user analytics"""
        try:
            analytics = self.get_user_analytics_summary(user_id)
            
            if format == "json":
                import json
                return json.dumps(analytics, indent=2, default=str)
            
            # Could add CSV, Excel formats here
            return None
        except Exception as e:
            logger.error(f"❌ Error exporting analytics: {e}")
            return None