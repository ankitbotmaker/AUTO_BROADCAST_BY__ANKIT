#!/usr/bin/env python3
"""
Message Formatter
Handles message formatting, HTML/Markdown conversion, and text processing
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import html

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Enhanced message formatter with comprehensive text processing"""
    
    def __init__(self):
        # HTML tags that are allowed in Telegram
        self.allowed_html_tags = [
            'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
            'code', 'pre', 'a', 'blockquote'
        ]
        
        # Markdown patterns
        self.markdown_patterns = {
            'bold': re.compile(r'\*\*(.*?)\*\*'),
            'italic': re.compile(r'\*(.*?)\*'),
            'underline': re.compile(r'__(.*?)__'),
            'strikethrough': re.compile(r'~~(.*?)~~'),
            'code': re.compile(r'`(.*?)`'),
            'pre': re.compile(r'```(.*?)```', re.DOTALL),
            'link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        }
        
        logger.info("✅ Message Formatter initialized")
    
    def format_welcome_message(self, user_name: str, channel_count: int, 
                              is_premium: bool = True) -> str:
        """Format welcome message"""
        try:
            premium_status = "🎉 FREE" if is_premium else "⭐ Premium"
            
            message = f"""
🚀 <b>Welcome to Advanced Broadcast Bot!</b>

<blockquote>
👤 <b>User:</b> {html.escape(user_name)}
📊 <b>Channels:</b> {channel_count}
💎 <b>Status:</b> {premium_status} (All Features Unlocked!)
</blockquote>

<b>🎯 Available Features:</b>
• 📢 Multi-Channel Broadcasting
• ⚡ Auto Repost & Delete
• 📊 Advanced Analytics
• 🔗 Auto Link Detection
• ⏰ Scheduled Broadcasts
• 🎨 Message Templates
• 📈 Real-time Analytics

<b>🚀 Quick Start:</b>
1. Add channels using /add
2. Send your message
3. Configure settings
4. Start broadcasting!

<b>💡 Tip:</b> Send a message with Telegram links to auto-add channels!
            """.strip()
            
            return message
        
        except Exception as e:
            logger.error(f"❌ Error formatting welcome message: {e}")
            return "Welcome to Advanced Broadcast Bot!"
    
    def format_analytics_summary(self, analytics: Dict[str, Any]) -> str:
        """Format analytics summary"""
        try:
            if not analytics:
                return "📊 <b>No analytics data available</b>"
            
            total_channels = analytics.get("total_channels", 0)
            total_broadcasts = analytics.get("total_broadcasts", 0)
            total_messages = analytics.get("total_messages", 0)
            successful_messages = analytics.get("successful_messages", 0)
            failed_messages = analytics.get("failed_messages", 0)
            success_rate = analytics.get("success_rate", 0)
            period_days = analytics.get("period_days", 30)
            
            message = f"""
📊 <b>Analytics Summary ({period_days} days)</b>

<blockquote>
📋 <b>Channels:</b> {total_channels}
📡 <b>Broadcasts:</b> {total_broadcasts}
📨 <b>Messages Sent:</b> {total_messages}
✅ <b>Successful:</b> {successful_messages}
❌ <b>Failed:</b> {failed_messages}
📈 <b>Success Rate:</b> {success_rate:.1f}%
</blockquote>

<b>📈 Performance:</b>
{'🟢 Excellent' if success_rate >= 95 else '🟡 Good' if success_rate >= 80 else '🔴 Needs Improvement'}
            """.strip()
            
            return message
        
        except Exception as e:
            logger.error(f"❌ Error formatting analytics: {e}")
            return "❌ Error loading analytics"
    
    def format_broadcast_status(self, status_data: Dict[str, Any]) -> str:
        """Format broadcast status message"""
        try:
            broadcast_id = status_data.get("broadcast_id", "Unknown")
            status = status_data.get("status", "unknown")
            total_channels = status_data.get("total_channels", 0)
            completed_channels = status_data.get("completed_channels", 0)
            successful_sends = status_data.get("successful_sends", 0)
            failed_sends = status_data.get("failed_sends", 0)
            progress = status_data.get("progress_percentage", 0)
            elapsed_time = status_data.get("elapsed_time", "00:00:00")
            
            status_emoji = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🛑"
            }.get(status, "❓")
            
            message = f"""
{status_emoji} <b>Broadcast Status</b>

<blockquote>
🆔 <b>ID:</b> <code>{broadcast_id}</code>
📊 <b>Status:</b> {status.title()}
📈 <b>Progress:</b> {progress:.1f}%
⏱ <b>Elapsed:</b> {elapsed_time}
</blockquote>

<b>📊 Details:</b>
• <b>Total Channels:</b> {total_channels}
• <b>Completed:</b> {completed_channels}/{total_channels}
• <b>✅ Successful:</b> {successful_sends}
• <b>❌ Failed:</b> {failed_sends}
            """.strip()
            
            return message
        
        except Exception as e:
            logger.error(f"❌ Error formatting broadcast status: {e}")
            return "❌ Error loading broadcast status"
    
    def format_channel_list(self, channels: List[Dict[str, Any]]) -> str:
        """Format channel list"""
        try:
            if not channels:
                return "📋 <b>No channels found</b>\n\n<blockquote>Use /add to add channels</blockquote>"
            
            message = f"📋 <b>Your Channels ({len(channels)})</b>\n\n"
            
            for i, channel in enumerate(channels[:10], 1):  # Limit to 10 for display
                name = html.escape(channel.get("channel_name", "Unknown"))
                username = channel.get("username", "")
                broadcasts = channel.get("total_broadcasts", 0)
                success_rate = channel.get("success_rate", 100)
                
                channel_info = f"<b>{i}.</b> {name}"
                if username:
                    channel_info += f" (@{username})"
                
                channel_info += f"\n   📊 {broadcasts} broadcasts • {success_rate:.1f}% success\n"
                message += channel_info
            
            if len(channels) > 10:
                message += f"\n<i>... and {len(channels) - 10} more channels</i>"
            
            return message
        
        except Exception as e:
            logger.error(f"❌ Error formatting channel list: {e}")
            return "❌ Error loading channels"
    
    def markdown_to_html(self, text: str) -> str:
        """Convert Markdown to HTML"""
        try:
            if not text:
                return text
            
            # Escape HTML first
            text = html.escape(text)
            
            # Convert markdown patterns to HTML
            text = self.markdown_patterns['bold'].sub(r'<b>\1</b>', text)
            text = self.markdown_patterns['italic'].sub(r'<i>\1</i>', text)
            text = self.markdown_patterns['underline'].sub(r'<u>\1</u>', text)
            text = self.markdown_patterns['strikethrough'].sub(r'<s>\1</s>', text)
            text = self.markdown_patterns['code'].sub(r'<code>\1</code>', text)
            text = self.markdown_patterns['pre'].sub(r'<pre>\1</pre>', text)
            text = self.markdown_patterns['link'].sub(r'<a href="\2">\1</a>', text)
            
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
                r'<u>(.*?)</u>': r'__\1__',
                r'<s>(.*?)</s>': r'~~\1~~',
                r'<strike>(.*?)</strike>': r'~~\1~~',
                r'<del>(.*?)</del>': r'~~\1~~',
                r'<code>(.*?)</code>': r'`\1`',
                r'<pre>(.*?)</pre>': r'```\1```',
                r'<a href="([^"]+)">(.*?)</a>': r'[\2](\1)',
                r'<blockquote>(.*?)</blockquote>': r'> \1'
            }
            
            for pattern, replacement in conversions.items():
                text = re.sub(pattern, replacement, text, flags=re.DOTALL)
            
            # Remove remaining HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error converting HTML to markdown: {e}")
            return text
    
    def sanitize_html(self, text: str) -> str:
        """Sanitize HTML to only allow Telegram-supported tags"""
        try:
            if not text:
                return text
            
            # Allow only specific HTML tags
            allowed_pattern = '|'.join(self.allowed_html_tags)
            
            # Remove disallowed tags
            text = re.sub(r'<(?!/?(?:' + allowed_pattern + r')\b)[^>]*>', '', text)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing HTML: {e}")
            return text
    
    def truncate_text(self, text: str, max_length: int = 4096, 
                     suffix: str = "...") -> str:
        """Truncate text to fit Telegram limits"""
        try:
            if not text or len(text) <= max_length:
                return text
            
            # Truncate and add suffix
            truncated = text[:max_length - len(suffix)] + suffix
            
            return truncated
        
        except Exception as e:
            logger.error(f"❌ Error truncating text: {e}")
            return text
    
    def format_error_message(self, error: str, context: str = "") -> str:
        """Format error message for user display"""
        try:
            message = f"❌ <b>Error</b>"
            
            if context:
                message += f" - {context}"
            
            message += f"\n\n<blockquote>{html.escape(error)}</blockquote>"
            
            return message
        
        except Exception as e:
            logger.error(f"❌ Error formatting error message: {e}")
            return f"❌ An error occurred: {error}"
    
    def format_success_message(self, message: str, details: str = "") -> str:
        """Format success message for user display"""
        try:
            formatted = f"✅ <b>{message}</b>"
            
            if details:
                formatted += f"\n\n<blockquote>{html.escape(details)}</blockquote>"
            
            return formatted
        
        except Exception as e:
            logger.error(f"❌ Error formatting success message: {e}")
            return f"✅ {message}"
    
    def extract_message_entities(self, message) -> Dict[str, Any]:
        """Extract message entities and content"""
        try:
            result = {
                "type": message.content_type,
                "text": None,
                "caption": None,
                "file_id": None,
                "entities": []
            }
            
            if message.content_type == "text":
                result["text"] = message.text
                if message.entities:
                    result["entities"] = [
                        {
                            "type": entity.type,
                            "offset": entity.offset,
                            "length": entity.length,
                            "url": getattr(entity, 'url', None)
                        }
                        for entity in message.entities
                    ]
            
            elif message.content_type == "photo":
                result["file_id"] = message.photo[-1].file_id  # Get largest photo
                result["caption"] = message.caption
                if message.caption_entities:
                    result["entities"] = [
                        {
                            "type": entity.type,
                            "offset": entity.offset,
                            "length": entity.length,
                            "url": getattr(entity, 'url', None)
                        }
                        for entity in message.caption_entities
                    ]
            
            # Add other content types as needed
            elif hasattr(message, message.content_type):
                media = getattr(message, message.content_type)
                if hasattr(media, 'file_id'):
                    result["file_id"] = media.file_id
                result["caption"] = message.caption
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Error extracting message entities: {e}")
            return {"type": "text", "text": "", "caption": None, "file_id": None, "entities": []}