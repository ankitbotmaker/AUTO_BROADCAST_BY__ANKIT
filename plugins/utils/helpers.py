"""
Helper Functions Module
Contains utility and helper functions
"""

import re
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import asyncio
import concurrent.futures

logger = logging.getLogger(__name__)

class Helpers:
    """Helper functions for the bot"""
    
    def __init__(self):
        logger.info("✅ Helpers initialized")
    
    def format_timestamp(self, timestamp: Union[datetime, float, int]) -> str:
        """Format timestamp to human readable string"""
        try:
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            
            return timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            logger.error(f"❌ Error formatting timestamp: {e}")
            return "Unknown"
    
    def parse_time_string(self, time_str: str) -> Optional[int]:
        """Parse time string to minutes"""
        try:
            if not time_str or not isinstance(time_str, str):
                return None
            
            time_str = time_str.strip().lower()
            
            # Patterns for different time formats
            patterns = {
                'minutes': ['m', 'min', 'minute', 'minutes'],
                'hours': ['h', 'hr', 'hour', 'hours'],
                'days': ['d', 'day', 'days']
            }
            
            total_minutes = 0
            
            # Extract numbers and units
            for pattern in patterns['minutes']:
                matches = re.findall(rf'(\d+)\s*{pattern}', time_str)
                for match in matches:
                    total_minutes += int(match)
            
            for pattern in patterns['hours']:
                matches = re.findall(rf'(\d+)\s*{pattern}', time_str)
                for match in matches:
                    total_minutes += int(match) * 60
            
            for pattern in patterns['days']:
                matches = re.findall(rf'(\d+)\s*{pattern}', time_str)
                for match in matches:
                    total_minutes += int(match) * 1440
            
            return total_minutes if total_minutes > 0 else None
            
        except Exception as e:
            logger.error(f"❌ Error parsing time string: {e}")
            return None
    
    def format_duration(self, minutes: int) -> str:
        """Format minutes to human readable duration"""
        try:
            if minutes < 60:
                return f"{minutes}m"
            elif minutes < 1440:  # Less than a day
                hours = minutes // 60
                mins = minutes % 60
                if mins == 0:
                    return f"{hours}h"
                else:
                    return f"{hours}h {mins}m"
            else:  # Days
                days = minutes // 1440
                hours = (minutes % 1440) // 60
                if hours == 0:
                    return f"{days}d"
                else:
                    return f"{days}d {hours}h"
            
        except Exception as e:
            logger.error(f"❌ Error formatting duration: {e}")
            return f"{minutes}m"
    
    def calculate_eta(self, start_time: datetime, completed: int, total: int) -> str:
        """Calculate estimated time of arrival"""
        try:
            if completed == 0 or total == 0:
                return "Unknown"
            
            elapsed = datetime.now() - start_time
            rate = completed / elapsed.total_seconds()
            remaining = total - completed
            
            if rate == 0:
                return "Unknown"
            
            eta_seconds = remaining / rate
            eta = start_time + timedelta(seconds=eta_seconds)
            
            return eta.strftime("%H:%M:%S")
            
        except Exception as e:
            logger.error(f"❌ Error calculating ETA: {e}")
            return "Unknown"
    
    def get_safe_filename(self, filename: str) -> str:
        """Get safe filename by removing invalid characters"""
        try:
            # Remove invalid characters
            safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
            # Remove multiple underscores
            safe_chars = re.sub(r'_+', '_', safe_chars)
            # Remove leading/trailing underscores
            safe_chars = safe_chars.strip('_')
            
            return safe_chars if safe_chars else "file"
            
        except Exception as e:
            logger.error(f"❌ Error creating safe filename: {e}")
            return "file"
    
    def retry_on_exception(self, func, max_retries: int = 3, delay: float = 1.0):
        """Retry function on exception"""
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    
    def async_retry_on_exception(self, func, max_retries: int = 3, delay: float = 1.0):
        """Async retry function on exception"""
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    
    def run_concurrent_tasks(self, tasks: List[callable], max_workers: int = 5) -> List[Any]:
        """Run tasks concurrently"""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(task) for task in tasks]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
                return results
        except Exception as e:
            logger.error(f"❌ Error running concurrent tasks: {e}")
            return []
    
    def create_progress_tracker(self, total: int) -> Dict[str, Any]:
        """Create progress tracker"""
        return {
            "total": total,
            "completed": 0,
            "failed": 0,
            "start_time": datetime.now(),
            "last_update": datetime.now()
        }
    
    def update_progress(self, tracker: Dict[str, Any], completed: int = 1, failed: int = 0):
        """Update progress tracker"""
        try:
            tracker["completed"] += completed
            tracker["failed"] += failed
            tracker["last_update"] = datetime.now()
            
            # Calculate progress percentage
            total = tracker["total"]
            if total > 0:
                tracker["progress"] = (tracker["completed"] + tracker["failed"]) / total * 100
            else:
                tracker["progress"] = 0
                
        except Exception as e:
            logger.error(f"❌ Error updating progress: {e}")
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        try:
            if size_bytes == 0:
                return "0 B"
            
            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            while size_bytes >= 1024 and i < len(size_names) - 1:
                size_bytes /= 1024.0
                i += 1
            
            return f"{size_bytes:.1f} {size_names[i]}"
            
        except Exception as e:
            logger.error(f"❌ Error formatting file size: {e}")
            return "Unknown"
    
    def is_valid_timezone(self, timezone: str) -> bool:
        """Check if timezone is valid"""
        try:
            import pytz
            pytz.timezone(timezone)
            return True
        except Exception:
            return False
    
    def get_timezone_offset(self, timezone: str) -> str:
        """Get timezone offset"""
        try:
            import pytz
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            offset = now.strftime('%z')
            return f"UTC{offset[:3]}:{offset[3:]}"
        except Exception as e:
            logger.error(f"❌ Error getting timezone offset: {e}")
            return "UTC+00:00"
    
    def create_loading_indicator(self, current: int, total: int, width: int = 20) -> str:
        """Create loading indicator"""
        try:
            if total == 0:
                return "[" + " " * width + "] 0%"
            
            progress = current / total
            filled = int(width * progress)
            bar = "█" * filled + "░" * (width - filled)
            percentage = int(progress * 100)
            
            return f"[{bar}] {percentage}%"
            
        except Exception as e:
            logger.error(f"❌ Error creating loading indicator: {e}")
            return "[░░░░░░░░░░░░░░░░░░░░] 0%"
    
    def create_status_emoji(self, status: str) -> str:
        """Create status emoji"""
        status_emojis = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "loading": "⏳",
            "pending": "⏸️",
            "running": "🔄",
            "stopped": "🛑"
        }
        return status_emojis.get(status.lower(), "❓")
    
    def create_priority_emoji(self, priority: int) -> str:
        """Create priority emoji"""
        if priority >= 3:
            return "🔴"
        elif priority >= 2:
            return "🟡"
        else:
            return "🟢"
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        try:
            # Remove or replace invalid characters
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                filename = filename.replace(char, '_')
            
            # Remove multiple underscores
            filename = re.sub(r'_+', '_', filename)
            
            # Remove leading/trailing underscores and dots
            filename = filename.strip('_.')
            
            return filename if filename else "file"
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing filename: {e}")
            return "file"
    
    def create_checksum(self, data: str) -> str:
        """Create checksum for data"""
        try:
            return hashlib.md5(data.encode()).hexdigest()
        except Exception as e:
            logger.error(f"❌ Error creating checksum: {e}")
            return ""
    
    def validate_checksum(self, data: str, checksum: str) -> bool:
        """Validate checksum"""
        try:
            return self.create_checksum(data) == checksum
        except Exception as e:
            logger.error(f"❌ Error validating checksum: {e}")
            return False
    
    def create_short_url(self, url: str) -> str:
        """Create short URL (placeholder)"""
        try:
            # This is a placeholder - in real implementation, you'd use a URL shortener service
            return url
        except Exception as e:
            logger.error(f"❌ Error creating short URL: {e}")
            return url