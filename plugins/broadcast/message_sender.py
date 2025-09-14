#!/usr/bin/env python3
"""
Message Sender Plugin
Handles message sending to individual channels
"""

import logging
from typing import Optional, Dict, Any
from telebot import TeleBot, types

logger = logging.getLogger(__name__)

class MessageSender:
    """Enhanced message sender with error handling and retry logic"""
    
    def __init__(self, bot: TeleBot):
        self.bot = bot
    
    def send_message(self, channel_id: int, message, formatted_text: Optional[str] = None) -> Optional[types.Message]:
        """Send message to channel based on content type"""
        try:
            if message.content_type == "text":
                return self._send_text_message(channel_id, message, formatted_text)
            elif message.content_type == "photo":
                return self._send_photo_message(channel_id, message, formatted_text)
            elif message.content_type == "video":
                return self._send_video_message(channel_id, message, formatted_text)
            elif message.content_type == "document":
                return self._send_document_message(channel_id, message, formatted_text)
            else:
                return self._forward_message(channel_id, message)
                
        except Exception as e:
            logger.error(f"Error sending message to channel {channel_id}: {e}")
            return None
    
    def _send_text_message(self, channel_id: int, message, formatted_text: Optional[str] = None) -> Optional[types.Message]:
        """Send text message"""
        try:
            text_to_send = formatted_text or message.text or "📢 Broadcast Message"
            return self.bot.send_message(channel_id, text_to_send, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error sending text to {channel_id}: {e}")
            return None
    
    def _send_photo_message(self, channel_id: int, message, formatted_text: Optional[str] = None) -> Optional[types.Message]:
        """Send photo message"""
        try:
            caption = formatted_text or message.caption or "📢 Broadcast Message"
            
            # Try forwarding first
            try:
                return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception:
                # Fallback to sending photo
                return self.bot.send_photo(
                    channel_id, 
                    message.photo[-1].file_id, 
                    caption=caption, 
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error sending photo to {channel_id}: {e}")
            return None
    
    def _send_video_message(self, channel_id: int, message, formatted_text: Optional[str] = None) -> Optional[types.Message]:
        """Send video message"""
        try:
            caption = formatted_text or message.caption or "📢 Broadcast Message"
            
            # Try forwarding first
            try:
                return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception:
                # Fallback to sending video
                return self.bot.send_video(
                    channel_id, 
                    message.video.file_id, 
                    caption=caption, 
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error sending video to {channel_id}: {e}")
            return None
    
    def _send_document_message(self, channel_id: int, message, formatted_text: Optional[str] = None) -> Optional[types.Message]:
        """Send document message"""
        try:
            caption = formatted_text or message.caption or "📢 Broadcast Message"
            
            # Try forwarding first
            try:
                return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
            except Exception:
                # Fallback to sending document
                return self.bot.send_document(
                    channel_id, 
                    message.document.file_id, 
                    caption=caption, 
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error sending document to {channel_id}: {e}")
            return None
    
    def _forward_message(self, channel_id: int, message) -> Optional[types.Message]:
        """Forward message as fallback"""
        try:
            return self.bot.forward_message(channel_id, message.chat.id, message.message_id)
        except Exception as e:
            logger.error(f"Error forwarding message to {channel_id}: {e}")
            return None
