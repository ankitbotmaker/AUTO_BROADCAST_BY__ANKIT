#!/usr/bin/env python3
"""
Message Formatter Utility
Handles message formatting, HTML/Markdown conversion, and text processing
"""

import re
import logging
from typing import Optional, Dict, Any, List
from telebot import types

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Enhanced message formatting and text processing"""
    
    def __init__(self):
        self.html_escape_chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        }
    
    def html_escape(self, text: Optional[str]) -> str:
        """Escape HTML special characters"""
        if text is None:
            return ""
        return ''.join(self.html_escape_chars.get(c, c) for c in str(text))
    
    def render_markdown_to_html(self, text: Optional[str]) -> str:
        """Convert Markdown to safe HTML"""
        if not text:
            return ""
        
        def make_placeholder(kind: str, content: str) -> str:
            return f"__PLACEHOLDER_{kind}_{len(placeholders)}__"
        
        placeholders = []
        
        # Handle code blocks first
        def repl_code(m):
            content = m.group(1)
            placeholder = make_placeholder("code", content)
            placeholders.append(('code', content, placeholder))
            return placeholder
        
        text = re.sub(r'```([^`]+)```', repl_code, text)
        
        # Handle bold text
        def repl_bold(m):
            content = m.group(1)
            placeholder = make_placeholder("bold", content)
            placeholders.append(('bold', content, placeholder))
            return placeholder
        
        text = re.sub(r'\*\*([^*]+)\*\*', repl_bold, text)
        
        # Handle inline code
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # Handle line breaks
        text = text.replace('\n', '<br>')
        
        # Replace placeholders
        for kind, content, placeholder in placeholders:
            if kind == 'code':
                text = text.replace(placeholder, f'<pre><code>{self.html_escape(content)}</code></pre>')
            elif kind == 'bold':
                text = text.replace(placeholder, f'<b>{self.html_escape(content)}</b>')
        
        return text
    
    def format_broadcast_message(self, message_text: str, message_type: str = "text") -> str:
        """Format message for broadcasting"""
        if not message_text:
            return "📢 Broadcast Message"
        
        # Add broadcast indicator if not present
        if not message_text.startswith(("📢", "🔔", "📡")):
            message_text = f"📢 {message_text}"
        
        return message_text
    
    def create_progress_bar(self, current: int, total: int, width: int = 20) -> str:
        """Create a progress bar"""
        if total == 0:
            return "█" * width
        
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        percentage = int((current / total) * 100)
        
        return f"{bar} {percentage}%"
    
    def create_loading_animation(self, step: int) -> str:
        """Create loading animation"""
        animations = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        return animations[step % len(animations)]
    
    def format_channel_list(self, channels: List[Dict[str, Any]]) -> str:
        """Format channel list for display"""
        if not channels:
            return "No channels found"
        
        formatted_channels = []
        for i, channel in enumerate(channels, 1):
            name = channel.get('channel_name', f'Channel {i}')
            username = channel.get('username', 'private')
            formatted_channels.append(f"{i}. **{name}** (@{username})")
        
        return "\n".join(formatted_channels)
    
    def format_analytics_summary(self, analytics: Dict[str, Any]) -> str:
        """Format analytics data for display"""
        total_broadcasts = analytics.get('total_broadcasts', 0)
        successful = analytics.get('successful_broadcasts', 0)
        failed = analytics.get('failed_broadcasts', 0)
        success_rate = (successful / total_broadcasts * 100) if total_broadcasts > 0 else 0
        
        return f"""
📊 **Analytics Summary**
• **Total Broadcasts:** {total_broadcasts}
• **Successful:** {successful}
• **Failed:** {failed}
• **Success Rate:** {success_rate:.1f}%
• **Total Channels:** {analytics.get('total_channels', 0)}
• **Messages Sent:** {analytics.get('total_messages_sent', 0)}
        """.strip()
    
    def format_premium_plans(self, plans: Dict[str, Dict[str, Any]]) -> str:
        """Format premium plans for display"""
        formatted_plans = []
        for plan_id, plan_data in plans.items():
            name = plan_data['name']
            price = plan_data['price']
            duration = plan_data['duration_days']
            formatted_plans.append(f"• **{name}** - ₹{price} ({duration} days)")
        
        return "\n".join(formatted_plans)
    
    def truncate_text(self, text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text
    
    def extract_mentions(self, text: str) -> List[str]:
        """Extract @mentions from text"""
        if not text:
            return []
        
        mentions = re.findall(r'@[a-zA-Z0-9_]+', text)
        return list(set(mentions))  # Remove duplicates
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Extract #hashtags from text"""
        if not text:
            return []
        
        hashtags = re.findall(r'#[a-zA-Z0-9_]+', text)
        return list(set(hashtags))  # Remove duplicates
    
    def format_broadcast_status(self, status: str) -> str:
        """Format broadcast status with emoji"""
        status_emojis = {
            'pending': '⏳',
            'running': '🔄',
            'completed': '✅',
            'failed': '❌',
            'cancelled': '🚫'
        }
        
        emoji = status_emojis.get(status, '❓')
        return f"{emoji} {status.title()}"
    
    def create_inline_keyboard(self, buttons: List[List[Dict[str, str]]]) -> types.InlineKeyboardMarkup:
        """Create inline keyboard from button configuration"""
        markup = types.InlineKeyboardMarkup()
        
        for row in buttons:
            keyboard_row = []
            for button in row:
                keyboard_row.append(
                    types.InlineKeyboardButton(
                        text=button['text'],
                        callback_data=button['callback_data']
                    )
                )
            markup.add(*keyboard_row)
        
        return markup
    
    def format_time_duration(self, minutes: int) -> str:
        """Format time duration in human readable format"""
        if minutes < 60:
            return f"{minutes} minutes"
        elif minutes < 1440:  # Less than 24 hours
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                return f"{hours}h {remaining_minutes}m"
        else:  # 24 hours or more
            days = minutes // 1440
            remaining_hours = (minutes % 1440) // 60
            if remaining_hours == 0:
                return f"{days} day{'s' if days > 1 else ''}"
            else:
                return f"{days}d {remaining_hours}h"
    
    def validate_message_length(self, text: str, max_length: int = 4096) -> bool:
        """Validate message length"""
        return len(text) <= max_length if text else True
