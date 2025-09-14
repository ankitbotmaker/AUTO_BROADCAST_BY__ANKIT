#!/usr/bin/env python3
"""
Logger Utility
Enhanced logging configuration and utilities
"""

import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from config import LOG_LEVEL, LOG_FILE, LOG_FORMAT

def setup_logger(name: str = None, level: str = None, log_file: str = None) -> logging.Logger:
    """Setup enhanced logger with file and console handlers"""
    
    # Create logger
    logger = logging.getLogger(name or __name__)
    
    # Set level
    log_level = getattr(logging, (level or LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file or LOG_FILE:
        file_handler = logging.FileHandler(log_file or LOG_FILE, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

class LoggerMixin:
    """Mixin class to add logging capabilities to any class"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = setup_logger(self.__class__.__name__)
    
    def log_info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def log_error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, extra=kwargs)
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def log_debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)

class BroadcastLogger:
    """Specialized logger for broadcast operations"""
    
    def __init__(self):
        self.logger = setup_logger("BroadcastLogger")
    
    def log_broadcast_start(self, user_id: int, broadcast_id: str, channel_count: int):
        """Log broadcast start"""
        self.logger.info(f"🚀 Broadcast started - User: {user_id}, ID: {broadcast_id}, Channels: {channel_count}")
    
    def log_broadcast_progress(self, broadcast_id: str, completed: int, total: int, failed: int = 0):
        """Log broadcast progress"""
        percentage = (completed / total * 100) if total > 0 else 0
        self.logger.info(f"📊 Broadcast progress - ID: {broadcast_id}, {completed}/{total} ({percentage:.1f}%), Failed: {failed}")
    
    def log_broadcast_complete(self, broadcast_id: str, successful: int, failed: int, duration: float):
        """Log broadcast completion"""
        success_rate = (successful / (successful + failed) * 100) if (successful + failed) > 0 else 0
        self.logger.info(f"✅ Broadcast completed - ID: {broadcast_id}, Success: {successful}, Failed: {failed}, Rate: {success_rate:.1f}%, Duration: {duration:.2f}s")
    
    def log_broadcast_error(self, broadcast_id: str, error: str, channel_id: int = None):
        """Log broadcast error"""
        channel_info = f", Channel: {channel_id}" if channel_id else ""
        self.logger.error(f"❌ Broadcast error - ID: {broadcast_id}{channel_info}, Error: {error}")
    
    def log_channel_added(self, user_id: int, channel_id: int, channel_name: str):
        """Log channel addition"""
        self.logger.info(f"➕ Channel added - User: {user_id}, Channel: {channel_id} ({channel_name})")
    
    def log_channel_removed(self, user_id: int, channel_id: int):
        """Log channel removal"""
        self.logger.info(f"➖ Channel removed - User: {user_id}, Channel: {channel_id}")
    
    def log_premium_activated(self, user_id: int, plan: str, expiry: datetime):
        """Log premium activation"""
        self.logger.info(f"💎 Premium activated - User: {user_id}, Plan: {plan}, Expiry: {expiry}")
    
    def log_premium_expired(self, user_id: int):
        """Log premium expiry"""
        self.logger.info(f"⏰ Premium expired - User: {user_id}")

class PerformanceLogger:
    """Logger for performance monitoring"""
    
    def __init__(self):
        self.logger = setup_logger("PerformanceLogger")
        self.start_times = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.start_times[operation] = datetime.now()
        self.logger.debug(f"⏱️ Started timing: {operation}")
    
    def end_timer(self, operation: str):
        """End timing an operation"""
        if operation in self.start_times:
            duration = (datetime.now() - self.start_times[operation]).total_seconds()
            self.logger.info(f"⏱️ Operation completed: {operation} in {duration:.2f}s")
            del self.start_times[operation]
        else:
            self.logger.warning(f"⏱️ No start time found for operation: {operation}")
    
    def log_memory_usage(self, operation: str, memory_mb: float):
        """Log memory usage"""
        self.logger.info(f"💾 Memory usage for {operation}: {memory_mb:.2f} MB")
    
    def log_database_query(self, collection: str, operation: str, duration: float, result_count: int = None):
        """Log database query performance"""
        result_info = f", Results: {result_count}" if result_count is not None else ""
        self.logger.debug(f"🗄️ DB Query - Collection: {collection}, Operation: {operation}, Duration: {duration:.3f}s{result_info}")

class SecurityLogger:
    """Logger for security events"""
    
    def __init__(self):
        self.logger = setup_logger("SecurityLogger")
    
    def log_unauthorized_access(self, user_id: int, action: str, ip: str = None):
        """Log unauthorized access attempt"""
        ip_info = f", IP: {ip}" if ip else ""
        self.logger.warning(f"🚨 Unauthorized access - User: {user_id}, Action: {action}{ip_info}")
    
    def log_rate_limit_exceeded(self, user_id: int, action: str, limit: int):
        """Log rate limit exceeded"""
        self.logger.warning(f"⏰ Rate limit exceeded - User: {user_id}, Action: {action}, Limit: {limit}")
    
    def log_suspicious_activity(self, user_id: int, activity: str, details: str = None):
        """Log suspicious activity"""
        details_info = f", Details: {details}" if details else ""
        self.logger.warning(f"🔍 Suspicious activity - User: {user_id}, Activity: {activity}{details_info}")
    
    def log_admin_action(self, admin_id: int, action: str, target_user: int = None):
        """Log admin action"""
        target_info = f", Target: {target_user}" if target_user else ""
        self.logger.info(f"👨‍💼 Admin action - Admin: {admin_id}, Action: {action}{target_info}")

# Global logger instances
broadcast_logger = BroadcastLogger()
performance_logger = PerformanceLogger()
security_logger = SecurityLogger()

def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    return setup_logger(name)

def log_function_call(func_name: str, **kwargs):
    """Log function call with parameters"""
    logger = get_logger("FunctionLogger")
    params = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.debug(f"🔧 Function call: {func_name}({params})")

def log_exception(exception: Exception, context: str = None):
    """Log exception with context"""
    logger = get_logger("ExceptionLogger")
    context_info = f" in {context}" if context else ""
    logger.error(f"💥 Exception{context_info}: {type(exception).__name__}: {str(exception)}", exc_info=True)
