"""
Message Formatter Module
Handles message formatting for display
"""

import html
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Format messages for display"""
    
    def __init__(self):
        logger.info("✅ Message Formatter initialized")
    
    def format_broadcast_message(self, message: str, channels: List[Dict[str, Any]]) -> str:
        """Format broadcast message with channel info"""
        try:
            channel_count = len(channels)
            channel_names = [ch.get("channel_name", "Unknown") for ch in channels[:5]]
            
            if channel_count > 5:
                channel_names.append(f"... and {channel_count - 5} more")
            
            header = f"📢 <b>Broadcast Message</b>\n<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>\n\n"
            channel_info = f"📋 <b>Target Channels:</b> {channel_count}\n"
            channel_list = f"┣ {', '.join(channel_names)}\n\n" if channel_names else ""
            message_content = f"<blockquote>{html.escape(message)}</blockquote>"
            
            return header + channel_info + channel_list + message_content
            
        except Exception as e:
            logger.error(f"❌ Error formatting broadcast message: {e}")
            return f"📢 <b>Broadcast Message</b>\n\n<blockquote>{html.escape(message)}</blockquote>"
    
    def format_channel_list(self, channels: List[Dict[str, Any]]) -> str:
        """Format channel list"""
        try:
            if not channels:
                return "📋 <b>No channels found</b>\n\n<blockquote>Use /add to add channels</blockquote>"
            
            message = f"📋 <b>Your Channels ({len(channels)})</b>\n\n"
            
            for i, channel in enumerate(channels[:10], 1):  # Limit to 10 for display
                name = html.escape(channel.get("channel_name", "Unknown"))
                username = channel.get("username", "")
                status = "✅" if channel.get("is_active", True) else "❌"
                
                if username:
                    message += f"┣ {i}. {status} <b>{name}</b> (@{username})\n"
                else:
                    message += f"┣ {i}. {status} <b>{name}</b>\n"
            
            if len(channels) > 10:
                message += f"┗ ... and {len(channels) - 10} more channels\n"
            
            message += f"\n<i>Total: {len(channels)} channels</i>"
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting channel list: {e}")
            return "❌ Error loading channels"
    
    def format_analytics_summary(self, analytics: Dict[str, Any]) -> str:
        """Format analytics summary"""
        try:
            if not analytics:
                return "📊 <b>No Analytics Data</b>\n\n<blockquote>Start broadcasting to see analytics!</blockquote>"
            
            total_broadcasts = analytics.get("total_broadcasts", 0)
            total_messages = analytics.get("total_messages", 0)
            success_rate = analytics.get("success_rate", 0)
            last_broadcast = analytics.get("last_broadcast")
            
            message = f"📊 <b>Analytics Summary</b>\n<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>\n\n"
            message += f"📢 <b>Total Broadcasts:</b> {total_broadcasts}\n"
            message += f"📨 <b>Messages Sent:</b> {total_messages}\n"
            message += f"✅ <b>Success Rate:</b> {success_rate:.1f}%\n"
            
            if last_broadcast:
                last_time = datetime.fromisoformat(last_broadcast).strftime("%Y-%m-%d %H:%M")
                message += f"🕒 <b>Last Broadcast:</b> {last_time}\n"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting analytics: {e}")
            return "❌ Error loading analytics"
    
    def format_broadcast_status(self, status: Dict[str, Any]) -> str:
        """Format broadcast status"""
        try:
            if not status:
                return "❌ <b>No Active Broadcast</b>"
            
            broadcast_id = status.get("broadcast_id", "Unknown")
            progress = status.get("progress", 0)
            total = status.get("total", 0)
            completed = status.get("completed", 0)
            failed = status.get("failed", 0)
            
            message = f"📊 <b>Broadcast Status</b>\n<i>━━━━━━━━━━━━━━━━━━━━━━━━━━━</i>\n\n"
            message += f"🆔 <b>ID:</b> {broadcast_id}\n"
            message += f"📈 <b>Progress:</b> {progress:.1f}%\n"
            message += f"✅ <b>Completed:</b> {completed}\n"
            message += f"❌ <b>Failed:</b> {failed}\n"
            message += f"📊 <b>Total:</b> {total}\n"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting broadcast status: {e}")
            return "❌ Error loading broadcast status"
    
    def markdown_to_html(self, text: str) -> str:
        """Convert Markdown to HTML"""
        try:
            if not text:
                return text
            
            # Convert markdown to HTML
            conversions = {
                r'\*\*(.*?)\*\*': r'<b>\1</b>',
                r'\*(.*?)\*': r'<i>\1</i>',
                r'`(.*?)`': r'<code>\1</code>',
                r'```(.*?)```': r'<pre>\1</pre>',
                r'\[([^\]]+)\]\(([^)]+)\)': r'<a href="\2">\1</a>'
            }
            
            for pattern, replacement in conversions.items():
                text = re.sub(pattern, replacement, text, flags=re.DOTALL)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error converting markdown to HTML: {e}")
            return text
    
    def html_to_markdown(self, text: str) -> str:
        """Convert HTML to Markdown"""
        try:
            if not text:
                return text
            
            # Convert HTML tags to markdown
            conversions = {
                r'<b>(.*?)</b>': r'**\1**',
                r'<strong>(.*?)</strong>': r'**\1**',
                r'<i>(.*?)</i>': r'*\1*',
                r'<em>(.*?)</em>': r'*\1*',
                r'<code>(.*?)</code>': r'`\1`',
                r'<pre>(.*?)</pre>': r'```\1```',
                r'<a href="([^"]+)">([^<]+)</a>': r'[\2](\1)'
            }
            
            for pattern, replacement in conversions.items():
                text = re.sub(pattern, replacement, text, flags=re.DOTALL)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error converting HTML to markdown: {e}")
            return text
    
    def sanitize_html(self, text: str) -> str:
        """Sanitize HTML content"""
        try:
            if not text:
                return text
            
            # Remove potentially dangerous tags
            dangerous_tags = ['script', 'iframe', 'object', 'embed', 'link', 'meta']
            for tag in dangerous_tags:
                text = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(f'<{tag}[^>]*/?>', '', text, flags=re.IGNORECASE)
            
            # Escape remaining HTML
            text = html.escape(text)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing HTML: {e}")
            return text