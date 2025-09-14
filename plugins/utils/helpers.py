#!/usr/bin/env python3
"""
Helpers Utility
General helper functions and utilities
"""

import time
import random
import string
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class Helpers:
    """Enhanced helper functions and utilities"""
    
    @staticmethod
    def generate_broadcast_id(user_id: int) -> str:
        """Generate unique broadcast ID"""
        timestamp = int(time.time())
        return f"broadcast_{user_id}_{timestamp}"
    
    @staticmethod
    def generate_random_string(length: int = 8) -> str:
        """Generate random string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def get_current_timestamp() -> int:
        """Get current timestamp"""
        return int(time.time())
    
    @staticmethod
    def format_timestamp(timestamp: int) -> str:
        """Format timestamp to readable date"""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def get_time_until(target_time: datetime) -> str:
        """Get time until target datetime"""
        now = datetime.now()
        if target_time <= now:
            return "Expired"
        
        delta = target_time - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @staticmethod
    def calculate_success_rate(successful: int, total: int) -> float:
        """Calculate success rate percentage"""
        if total == 0:
            return 0.0
        return round((successful / total) * 100, 2)
    
    @staticmethod
    def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split list into chunks"""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    @staticmethod
    def remove_duplicates(lst: List[Any]) -> List[Any]:
        """Remove duplicates while preserving order"""
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    
    @staticmethod
    def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get value from dictionary"""
        try:
            return dictionary.get(key, default)
        except (AttributeError, TypeError):
            return default
    
    @staticmethod
    def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Helpers.deep_merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def retry_on_exception(func, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
        """Retry function on exception"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
    
    @staticmethod
    def async_retry_on_exception(func, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
        """Async retry function on exception"""
        async def wrapper():
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    logger.warning(f"Async attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
        return wrapper()
    
    @staticmethod
    def run_concurrent_tasks(tasks: List[callable], max_workers: int = 5) -> List[Any]:
        """Run tasks concurrently with ThreadPoolExecutor"""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(task): task for task in tasks}
            
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                    results.append(None)
        
        return results
    
    @staticmethod
    def create_progress_tracker(total: int) -> Dict[str, Any]:
        """Create progress tracker for long operations"""
        return {
            "total": total,
            "completed": 0,
            "failed": 0,
            "start_time": time.time(),
            "last_update": time.time()
        }
    
    @staticmethod
    def update_progress(tracker: Dict[str, Any], completed: int = 1, failed: int = 0) -> Dict[str, Any]:
        """Update progress tracker"""
        tracker["completed"] += completed
        tracker["failed"] += failed
        tracker["last_update"] = time.time()
        
        # Calculate progress percentage
        total_processed = tracker["completed"] + tracker["failed"]
        if tracker["total"] > 0:
            tracker["percentage"] = (total_processed / tracker["total"]) * 100
        else:
            tracker["percentage"] = 0
        
        # Calculate estimated time remaining
        if tracker["completed"] > 0:
            elapsed_time = time.time() - tracker["start_time"]
            rate = tracker["completed"] / elapsed_time
            remaining = tracker["total"] - total_processed
            tracker["eta_seconds"] = remaining / rate if rate > 0 else 0
        else:
            tracker["eta_seconds"] = 0
        
        return tracker
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m"
    
    @staticmethod
    def is_valid_timezone(timezone: str) -> bool:
        """Check if timezone string is valid"""
        try:
            from datetime import timezone
            import pytz
            pytz.timezone(timezone)
            return True
        except:
            return False
    
    @staticmethod
    def get_timezone_offset(timezone: str) -> int:
        """Get timezone offset in minutes"""
        try:
            import pytz
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            offset = now.utcoffset()
            return int(offset.total_seconds() / 60)
        except:
            return 0
    
    @staticmethod
    def create_loading_indicator(current: int, total: int) -> str:
        """Create loading indicator"""
        if total == 0:
            return "⏳"
        
        percentage = (current / total) * 100
        
        if percentage < 25:
            return "⏳"
        elif percentage < 50:
            return "🔄"
        elif percentage < 75:
            return "⚡"
        elif percentage < 100:
            return "🚀"
        else:
            return "✅"
    
    @staticmethod
    def create_status_emoji(status: str) -> str:
        """Create status emoji"""
        status_emojis = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫",
            "paused": "⏸️",
            "queued": "📋"
        }
        return status_emojis.get(status.lower(), "❓")
    
    @staticmethod
    def create_priority_emoji(priority: str) -> str:
        """Create priority emoji"""
        priority_emojis = {
            "low": "🟢",
            "normal": "🟡",
            "high": "🟠",
            "urgent": "🔴"
        }
        return priority_emojis.get(priority.lower(), "🟡")
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:255-len(ext)-1] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def create_checksum(data: str) -> str:
        """Create simple checksum for data"""
        import hashlib
        return hashlib.md5(data.encode()).hexdigest()[:8]
    
    @staticmethod
    def validate_checksum(data: str, checksum: str) -> bool:
        """Validate checksum"""
        return Helpers.create_checksum(data) == checksum
    
    @staticmethod
    def create_short_url(url: str) -> str:
        """Create short URL (placeholder for URL shortener service)"""
        # This would integrate with a URL shortener service
        # For now, just return a truncated version
        if len(url) > 50:
            return url[:47] + "..."
        return url
    
    @staticmethod
    def parse_time_string(time_str: str) -> Optional[int]:
        """Parse time string to minutes"""
        if not time_str or not isinstance(time_str, str):
            return None
        
        time_str = time_str.lower().strip()
        
        # Handle different formats
        if time_str.endswith('m') or time_str.endswith('min'):
            try:
                return int(time_str.rstrip('min'))
            except ValueError:
                return None
        elif time_str.endswith('h') or time_str.endswith('hour'):
            try:
                return int(time_str.rstrip('hour')) * 60
            except ValueError:
                return None
        elif time_str.endswith('d') or time_str.endswith('day'):
            try:
                return int(time_str.rstrip('day')) * 1440
            except ValueError:
                return None
        else:
            # Try to parse as plain number (assume minutes)
            try:
                return int(time_str)
            except ValueError:
                return None
