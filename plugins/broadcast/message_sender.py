#!/usr/bin/env python3
"""
Message Sender
Handles sending messages to channels with retry logic and error handling
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import telebot
from telebot.apihelper import ApiTelegramException

from ..database.models import generate_message_id
from ..database.operations import DatabaseOperations
from config import MAX_RETRIES, RETRY_DELAY, TIMEOUT_DURATION

logger = logging.getLogger(__name__)

class MessageSender:
    """Enhanced message sender with retry logic and comprehensive error handling"""
    
    def __init__(self, bot, db_ops: DatabaseOperations):
        self.bot = bot
        self.db_ops = db_ops
        
        # Message type handlers
        self.message_handlers = {
            "text": self._send_text_message,
            "photo": self._send_photo_message,
            "video": self._send_video_message,
            "document": self._send_document_message,
            "audio": self._send_audio_message,
            "voice": self._send_voice_message,
            "video_note": self._send_video_note_message,
            "sticker": self._send_sticker_message,
            "animation": self._send_animation_message
        }
        
        logger.info("✅ Message Sender initialized")
    
    def send_message(self, channel_id: int, message_data: Dict[str, Any], 
                    user_id: int, broadcast_id: str, settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send message to channel with retry logic"""
        message_type = message_data.get("type", "text")
        retry_count = 0
        last_error = None
        
        while retry_count < MAX_RETRIES:
            try:
                # Get the appropriate handler
                handler = self.message_handlers.get(message_type, self._send_text_message)
                
                # Send the message
                start_time = time.time()
                result = handler(channel_id, message_data, settings)
                response_time = time.time() - start_time
                
                if result["success"]:
                    # Log analytics
                    self.db_ops.add_analytics_entry(
                        user_id=user_id,
                        broadcast_id=broadcast_id,
                        channel_id=channel_id,
                        status="sent",
                        message_id=result.get("message_id"),
                        response_time=response_time
                    )
                    
                    # Track message for auto operations
                    if settings and (settings.get("auto_delete_time") or settings.get("auto_repost_time")):
                        self._track_message_for_auto_operations(
                            broadcast_id, user_id, channel_id, 
                            result.get("message_id"), settings
                        )
                    
                    return {
                        "success": True,
                        "message_id": result.get("message_id"),
                        "response_time": response_time,
                        "retry_count": retry_count
                    }
                else:
                    last_error = result.get("error", "Unknown error")
                    
            except ApiTelegramException as e:
                last_error = self._handle_telegram_error(e)
                if e.error_code in [403, 400]:  # Forbidden or Bad Request - don't retry
                    break
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"❌ Unexpected error sending to {channel_id}: {e}")
            
            retry_count += 1
            if retry_count < MAX_RETRIES:
                logger.warning(f"🔄 Retrying send to {channel_id} (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
        
        # Log failed attempt
        self.db_ops.add_analytics_entry(
            user_id=user_id,
            broadcast_id=broadcast_id,
            channel_id=channel_id,
            status="failed",
            error_message=last_error,
            retry_count=retry_count
        )
        
        return {
            "success": False,
            "error": last_error,
            "retry_count": retry_count
        }
    
    def _send_text_message(self, channel_id: int, message_data: Dict[str, Any], 
                          settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send text message"""
        try:
            text = message_data.get("text", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            disable_web_page_preview = message_data.get("disable_web_page_preview", False)
            
            message = self.bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_photo_message(self, channel_id: int, message_data: Dict[str, Any], 
                           settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send photo message"""
        try:
            photo = message_data.get("file_id") or message_data.get("photo")
            caption = message_data.get("caption", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            
            message = self.bot.send_photo(
                chat_id=channel_id,
                photo=photo,
                    caption=caption, 
                parse_mode=parse_mode,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_video_message(self, channel_id: int, message_data: Dict[str, Any], 
                           settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send video message"""
        try:
            video = message_data.get("file_id") or message_data.get("video")
            caption = message_data.get("caption", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            
            message = self.bot.send_video(
                chat_id=channel_id,
                video=video,
                    caption=caption, 
                parse_mode=parse_mode,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_document_message(self, channel_id: int, message_data: Dict[str, Any], 
                              settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send document message"""
        try:
            document = message_data.get("file_id") or message_data.get("document")
            caption = message_data.get("caption", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            
            message = self.bot.send_document(
                chat_id=channel_id,
                document=document,
                caption=caption,
                parse_mode=parse_mode,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_audio_message(self, channel_id: int, message_data: Dict[str, Any], 
                           settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send audio message"""
        try:
            audio = message_data.get("file_id") or message_data.get("audio")
            caption = message_data.get("caption", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            
            message = self.bot.send_audio(
                chat_id=channel_id,
                audio=audio,
                caption=caption,
                parse_mode=parse_mode,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_voice_message(self, channel_id: int, message_data: Dict[str, Any], 
                           settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send voice message"""
        try:
            voice = message_data.get("file_id") or message_data.get("voice")
            caption = message_data.get("caption", "")
            
            message = self.bot.send_voice(
                chat_id=channel_id,
                voice=voice,
                caption=caption,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_video_note_message(self, channel_id: int, message_data: Dict[str, Any], 
                                settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send video note message"""
        try:
            video_note = message_data.get("file_id") or message_data.get("video_note")
            
            message = self.bot.send_video_note(
                chat_id=channel_id,
                video_note=video_note,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_sticker_message(self, channel_id: int, message_data: Dict[str, Any], 
                             settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send sticker message"""
        try:
            sticker = message_data.get("file_id") or message_data.get("sticker")
            
            message = self.bot.send_sticker(
                chat_id=channel_id,
                sticker=sticker,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _send_animation_message(self, channel_id: int, message_data: Dict[str, Any], 
                               settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send animation/GIF message"""
        try:
            animation = message_data.get("file_id") or message_data.get("animation")
            caption = message_data.get("caption", "")
            parse_mode = message_data.get("parse_mode", "HTML")
            
            message = self.bot.send_animation(
                chat_id=channel_id,
                animation=animation,
                    caption=caption, 
                parse_mode=parse_mode,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _handle_telegram_error(self, error: ApiTelegramException) -> str:
        """Handle Telegram API errors with user-friendly messages"""
        error_code = error.error_code
        error_description = error.description.lower()
        
        if error_code == 403:
            if "bot was blocked" in error_description:
                return "Bot was blocked by the user"
            elif "not enough rights" in error_description:
                return "Bot doesn't have admin rights in the channel"
            elif "user not found" in error_description:
                return "Channel not found or bot not added"
            else:
                return "Access forbidden - check bot permissions"
        
        elif error_code == 400:
            if "chat not found" in error_description:
                return "Channel not found"
            elif "message is too long" in error_description:
                return "Message is too long"
            elif "bad request" in error_description:
                return "Invalid request format"
            else:
                return f"Bad request: {error.description}"
        
        elif error_code == 429:
            return "Rate limit exceeded - too many requests"
        
        elif error_code == 502:
            return "Telegram server error - temporary issue"
        
        else:
            return f"Telegram API error: {error.description}"
    
    def _track_message_for_auto_operations(self, broadcast_id: str, user_id: int, 
                                         channel_id: int, message_id: int, 
                                         settings: Dict[str, Any]):
        """Track message for auto delete/repost operations"""
        try:
            message_tracking_id = generate_message_id(broadcast_id, channel_id)
            
            auto_delete_time = settings.get("auto_delete_time")
            auto_repost_time = settings.get("auto_repost_time")
            
            # Add to database for tracking
            self.db_ops.add_broadcast_message(
                broadcast_id=broadcast_id,
                user_id=user_id,
                channel_id=channel_id,
                telegram_message_id=message_id,
                auto_delete_time=auto_delete_time,
                auto_repost_time=auto_repost_time
            )
            
            logger.info(f"📝 Message tracked for auto operations: {message_tracking_id}")
            
        except Exception as e:
            logger.error(f"❌ Error tracking message for auto operations: {e}")
    
    def delete_message(self, channel_id: int, message_id: int) -> Dict[str, Any]:
        """Delete a message from channel"""
        try:
            self.bot.delete_message(
                chat_id=channel_id,
                message_id=message_id,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message": "Message deleted successfully"
            }
            
        except ApiTelegramException as e:
            error_msg = self._handle_telegram_error(e)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def forward_message(self, from_channel_id: int, to_channel_id: int, 
                       message_id: int) -> Dict[str, Any]:
        """Forward a message between channels (for repost functionality)"""
        try:
            message = self.bot.forward_message(
                chat_id=to_channel_id,
                from_chat_id=from_channel_id,
                message_id=message_id,
                timeout=TIMEOUT_DURATION
            )
            
            return {
                "success": True,
                "message_id": message.message_id
            }
            
        except ApiTelegramException as e:
            error_msg = self._handle_telegram_error(e)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def get_channel_info(self, channel_id: int) -> Dict[str, Any]:
        """Get channel information"""
        try:
            chat = self.bot.get_chat(channel_id)
            
            return {
                "success": True,
                "channel_id": chat.id,
                "title": chat.title,
                "username": chat.username,
                "type": chat.type,
                "member_count": chat.member_count if hasattr(chat, 'member_count') else None
            }
            
        except ApiTelegramException as e:
            error_msg = self._handle_telegram_error(e)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }