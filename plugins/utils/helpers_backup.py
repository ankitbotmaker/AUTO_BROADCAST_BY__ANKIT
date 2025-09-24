#!/usr/bin/env python3
"""
Helpers
Utility helper functions for common operations
"""

import logging
import time
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json

logger = logging.getLogger(__name__)

class Helpers:
    """Collection of utility helper functions"""
    
    def __init__(self):
        logger.info("✅ Helpers initialized")
    
    def generate_unique_id(self, prefix: str = "", length: int = 8) -> str:
        """Generate a unique ID"""
        try:
            timestamp = str(int(time.time()))
            random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
            
            if prefix:
                return f"{prefix}_{timestamp}_{random_chars}"
            else:
                return f"{timestamp}_{random_chars}"
        
        except Exception as e:
            logger.error(f"❌ Error generating unique ID: {e}")
            return f"id_{int(time.time())}"
    
    def generate_hash(self, text: str, algorithm: str = "md5") -> str:
        """Generate hash for text"""
        try:
            if algorithm == "md5":
                return hashlib.md5(text.encode()).hexdigest()
            elif algorithm == "sha256":
                return hashlib.sha256(text.encode()).hexdigest()
            elif algorithm == "sha1":
                return hashlib.sha1(text.encode()).hexdigest()
            else:
                return hashlib.md5(text.encode()).hexdigest()
        
        except Exception as e:
            logger.error(f"❌ Error generating hash: {e}")
            return ""
    
    def format_timestamp(self, timestamp: Union[datetime, int, float], 
                        format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format timestamp to string"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
        else:
                return str(timestamp)
            
            return dt.strftime(format_str)
        
        except Exception as e:
            logger.error(f"❌ Error formatting timestamp: {e}")
            return str(timestamp)
    
    def parse_time_string(self, time_str: str) -> Optional[int]:
        """Parse time string to minutes (e.g., '1h 30m', '45m', '2d')"""
        try:
            time_str = time_str.lower().strip()
            total_minutes = 0
            
            # Time unit patterns
            patterns = {
                'days': ['d', 'day', 'days'],
                'hours': ['h', 'hour', 'hours'],
                'minutes': ['m', 'min', 'minute', 'minutes']
            }
            
            # Extract numbers and units
            import re
            matches = re.findall(r'(\d+)\s*([a-z]+)', time_str)
            
            for value, unit in matches:
                value = int(value)
                
                if unit in patterns['days']:
                    total_minutes += value * 24 * 60
                elif unit in patterns['hours']:
                    total_minutes += value * 60
                elif unit in patterns['minutes']:
                    total_minutes += value
            
            return total_minutes if total_minutes > 0 else None
            
            except Exception as e:
            logger.error(f"❌ Error parsing time string: {e}")
            return None
    
    def format_duration(self, minutes: int) -> str:
        """Format minutes to human readable duration"""
        try:
            if minutes < 60:
                return f"{minutes}m"
            elif minutes < 1440:  # Less than 24 hours
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
            
            elapsed = datetime.utcnow() - start_time
            rate = completed / elapsed.total_seconds()  # items per second
            remaining = total - completed
            
            if rate == 0:
                return "Unknown"
            
            eta_seconds = remaining / rate
            eta_time = datetime.utcnow() + timedelta(seconds=eta_seconds)
            
            return eta_time.strftime("%H:%M:%S")
        
        except Exception as e:
            logger.error(f"❌ Error calculating ETA: {e}")
            return "Unknown"
    
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
    
    def safe_json_loads(self, json_str: str, default: Any = None) -> Any:
        """Safely load JSON with fallback"""
        try:
            return json.loads(json_str) if json_str else default
        except Exception as e:
            logger.warning(f"⚠️ Error parsing JSON: {e}")
            return default
    
    def safe_json_dumps(self, obj: Any, default: str = "{}") -> str:
        """Safely dump JSON with fallback"""
        try:
            return json.dumps(obj, default=str, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"⚠️ Error dumping JSON: {e}")
            return default
    
    def chunk_list(self, lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split list into chunks"""
        try:
            return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
        except Exception as e:
            logger.error(f"❌ Error chunking list: {e}")
            return [lst] if lst else []
    
    def deduplicate_list(self, lst: List[Any], key_func: callable = None) -> List[Any]:
        """Remove duplicates from list"""
        try:
            if key_func:
                seen = set()
                result = []
                for item in lst:
                    key = key_func(item)
                    if key not in seen:
                        seen.add(key)
                        result.append(item)
                return result
            else:
                return list(dict.fromkeys(lst))  # Preserves order
        
        except Exception as e:
            logger.error(f"❌ Error deduplicating list: {e}")
            return lst
    
    def retry_operation(self, func: callable, max_retries: int = 3, 
                       delay: float = 1.0, *args, **kwargs) -> Any:
        """Retry an operation with exponential backoff"""
        try:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            
        except Exception as e:
            logger.error(f"❌ All retry attempts failed: {e}")
            raise e
    
    def get_safe_filename(self, filename: str, max_length: int = 255) -> str:
        """Get safe filename by removing invalid characters"""
        try:
            # Remove invalid characters
            invalid_chars = '<>:"/\\|?*'
            safe_name = ''.join(c for c in filename if c not in invalid_chars)
            
            # Replace spaces with underscores
            safe_name = safe_name.replace(' ', '_')
            
            # Limit length
            if len(safe_name) > max_length:
                name, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
                max_name_length = max_length - len(ext) - 1 if ext else max_length
                safe_name = name[:max_name_length] + ('.' + ext if ext else '')
            
            return safe_name or "file"
        
        except Exception as e:
            logger.error(f"❌ Error creating safe filename: {e}")
            return "file"
    
    def calculate_percentage(self, part: Union[int, float], 
                           total: Union[int, float], precision: int = 1) -> float:
        """Calculate percentage with safe division"""
        try:
            if total == 0:
                return 0.0
            return round((part / total) * 100, precision)
        except Exception as e:
            logger.error(f"❌ Error calculating percentage: {e}")
            return 0.0
    
    def merge_dicts(self, *dicts: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple dictionaries"""
        try:
            result = {}
            for d in dicts:
                if isinstance(d, dict):
                    result.update(d)
            return result
        except Exception as e:
            logger.error(f"❌ Error merging dictionaries: {e}")
            return {}
    
    def get_nested_value(self, data: Dict[str, Any], key_path: str, 
                        default: Any = None, separator: str = ".") -> Any:
        """Get nested value from dictionary using dot notation"""
        try:
            keys = key_path.split(separator)
            value = data
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
        except Exception as e:
            logger.error(f"❌ Error getting nested value: {e}")
            return default
    
    def set_nested_value(self, data: Dict[str, Any], key_path: str, 
                        value: Any, separator: str = ".") -> bool:
        """Set nested value in dictionary using dot notation"""
        try:
            keys = key_path.split(separator)
            current = data
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            return True
        except Exception as e:
            logger.error(f"❌ Error setting nested value: {e}")
            return False
    
    def is_url(self, text: str) -> bool:
        """Check if text is a URL"""
        try:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            return url_pattern.match(text) is not None
        except Exception as e:
            logger.error(f"❌ Error checking URL: {e}")
            return False