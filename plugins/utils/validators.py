#!/usr/bin/env python3
"""
Validators Utility
Input validation and data validation functions
"""

import re
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Validators:
    """Enhanced validation functions for all inputs"""
    
    @staticmethod
    def is_valid_user_id(user_id: Union[int, str]) -> bool:
        """Validate Telegram user ID"""
        try:
            user_id = int(user_id)
            return user_id > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_channel_id(channel_id: Union[int, str]) -> bool:
        """Validate Telegram channel ID"""
        try:
            channel_id = int(channel_id)
            # Channel IDs are negative for groups/channels
            return channel_id < 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_username(username: str) -> bool:
        """Validate Telegram username"""
        if not username or not isinstance(username, str):
            return False
        
        # Username should start with @ and contain only alphanumeric characters and underscores
        pattern = r'^@[a-zA-Z0-9_]{5,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def is_valid_telegram_link(link: str) -> bool:
        """Validate Telegram link format"""
        if not link or not isinstance(link, str):
            return False
        
        patterns = [
            r'^https?://t\.me/[a-zA-Z0-9_]+$',
            r'^@[a-zA-Z0-9_]+$',
            r'^t\.me/[a-zA-Z0-9_]+$',
            r'^https?://telegram\.me/[a-zA-Z0-9_]+$'
        ]
        
        return any(re.match(pattern, link.strip()) for pattern in patterns)
    
    @staticmethod
    def is_valid_time_input(time_input: Union[int, str]) -> bool:
        """Validate time input for auto operations"""
        try:
            time_value = int(time_input)
            # Valid range: 1 minute to 30 days (43200 minutes)
            return 1 <= time_value <= 43200
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_premium_plan(plan: str) -> bool:
        """Validate premium plan"""
        valid_plans = ["1_month", "3_months", "6_months", "1_year"]
        return plan in valid_plans
    
    @staticmethod
    def is_valid_message_type(message_type: str) -> bool:
        """Validate message type"""
        valid_types = ["text", "photo", "video", "document", "audio", "voice", "sticker", "animation"]
        return message_type in valid_types
    
    @staticmethod
    def is_valid_broadcast_status(status: str) -> bool:
        """Validate broadcast status"""
        valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
        return status in valid_statuses
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_phone_number(phone: str) -> bool:
        """Validate phone number format"""
        if not phone or not isinstance(phone, str):
            return False
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Check if it's a valid length (7-15 digits)
        return 7 <= len(digits_only) <= 15
    
    @staticmethod
    def is_valid_date_string(date_string: str, format_string: str = "%Y-%m-%d") -> bool:
        """Validate date string format"""
        try:
            datetime.strptime(date_string, format_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_duration(duration: Union[int, str]) -> bool:
        """Validate duration in minutes"""
        try:
            duration = int(duration)
            # Valid range: 1 minute to 1 year (525600 minutes)
            return 1 <= duration <= 525600
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_channel_name(name: str) -> bool:
        """Validate channel name"""
        if not name or not isinstance(name, str):
            return False
        
        # Channel name should be 1-255 characters
        return 1 <= len(name.strip()) <= 255
    
    @staticmethod
    def is_valid_broadcast_id(broadcast_id: str) -> bool:
        """Validate broadcast ID format"""
        if not broadcast_id or not isinstance(broadcast_id, str):
            return False
        
        # Broadcast ID should follow pattern: broadcast_userid_timestamp
        pattern = r'^broadcast_\d+_\d+$'
        return bool(re.match(pattern, broadcast_id))
    
    @staticmethod
    def is_valid_analytics_metric(metric: str) -> bool:
        """Validate analytics metric name"""
        if not metric or not isinstance(metric, str):
            return False
        
        # Metric should contain only alphanumeric characters and underscores
        pattern = r'^[a-zA-Z0-9_]+$'
        return bool(re.match(pattern, metric))
    
    @staticmethod
    def is_valid_message_text(text: str, max_length: int = 4096) -> bool:
        """Validate message text length and content"""
        if not text or not isinstance(text, str):
            return False
        
        # Check length
        if len(text) > max_length:
            return False
        
        # Check for valid characters (basic validation)
        # Allow most Unicode characters except control characters
        for char in text:
            if ord(char) < 32 and char not in '\n\r\t':
                return False
        
        return True
    
    @staticmethod
    def is_valid_callback_data(callback_data: str) -> bool:
        """Validate callback data length"""
        if not callback_data or not isinstance(callback_data, str):
            return False
        
        # Telegram callback data limit is 64 bytes
        return len(callback_data.encode('utf-8')) <= 64
    
    @staticmethod
    def is_valid_file_id(file_id: str) -> bool:
        """Validate Telegram file ID format"""
        if not file_id or not isinstance(file_id, str):
            return False
        
        # File ID should be a non-empty string
        return len(file_id.strip()) > 0
    
    @staticmethod
    def is_valid_boolean(value: Any) -> bool:
        """Validate boolean value"""
        return isinstance(value, bool)
    
    @staticmethod
    def is_valid_integer(value: Any, min_value: int = None, max_value: int = None) -> bool:
        """Validate integer value with optional range"""
        try:
            int_value = int(value)
            if min_value is not None and int_value < min_value:
                return False
            if max_value is not None and int_value > max_value:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_float(value: Any, min_value: float = None, max_value: float = None) -> bool:
        """Validate float value with optional range"""
        try:
            float_value = float(value)
            if min_value is not None and float_value < min_value:
                return False
            if max_value is not None and float_value > max_value:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_list(value: Any, min_length: int = None, max_length: int = None) -> bool:
        """Validate list with optional length constraints"""
        if not isinstance(value, list):
            return False
        
        if min_length is not None and len(value) < min_length:
            return False
        
        if max_length is not None and len(value) > max_length:
            return False
        
        return True
    
    @staticmethod
    def is_valid_dict(value: Any, required_keys: List[str] = None) -> bool:
        """Validate dictionary with optional required keys"""
        if not isinstance(value, dict):
            return False
        
        if required_keys:
            for key in required_keys:
                if key not in value:
                    return False
        
        return True
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text or not isinstance(text, str):
            return ""
        
        # Remove control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Trim whitespace
        sanitized = sanitized.strip()
        
        return sanitized
    
    @staticmethod
    def validate_broadcast_data(data: Dict[str, Any]) -> List[str]:
        """Validate broadcast data and return list of errors"""
        errors = []
        
        if not Validators.is_valid_user_id(data.get('user_id')):
            errors.append("Invalid user ID")
        
        if not Validators.is_valid_message_type(data.get('message_type')):
            errors.append("Invalid message type")
        
        if not Validators.is_valid_list(data.get('channels'), min_length=1):
            errors.append("At least one channel is required")
        
        if data.get('repost_time') and not Validators.is_valid_time_input(data['repost_time']):
            errors.append("Invalid repost time")
        
        if data.get('delete_time') and not Validators.is_valid_time_input(data['delete_time']):
            errors.append("Invalid delete time")
        
        return errors
