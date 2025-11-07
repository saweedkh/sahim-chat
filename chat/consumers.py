# Django imports
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

# Third party imports
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

# Local imports
from .models import Chat, Message
from .tasks import process_and_save_file_task

# Python imports
import os
import json
import base64
from urllib.parse import unquote
from datetime import datetime
from logging import getLogger 

# Constants
User = get_user_model()
logger = getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'
        user = self.scope['user']
        
        if user.is_anonymous:
            logger.warning(f"Anonymous user rejected for chat {self.chat_id}")
            await self.close(code=4001) 
            return
        
        chat = await self.get_chat(self.chat_id)
        if not chat:
            logger.warning(f"Chat {self.chat_id} not found")
            await self.close(code=4004) 
            return
        
        if not await self.is_user_in_chat(chat, user):
            logger.warning(f"User {user.id} not authorized for chat {self.chat_id}")
            await self.close(code=4003)
            return
        
        try:
            await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
            await self.accept()
            
            logger.info(f"User {user.id} connected to chat {self.chat_id}")
            
            # Mark all unread messages as read when chat is opened
            await self.mark_all_messages_as_read(user)
            
            await self.send_chat_history()
            await self.send_json({
                'type': 'connection_established',
                'message': 'Connected to chat',
                'chat_id': self.chat_id
            })
        except Exception as e:
            logger.error(f"Connection error: {e}", exc_info=True)
            await self.close(code=1011)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            handlers = {
                'chat_message': self.handle_chat_message,
                'typing': self.handle_typing_indicator,
                'read_receipt': self.handle_read_receipt,
            }
            
            handler = handlers.get(message_type)
            if handler:
                await handler(data)
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"Receive error: {e}", exc_info=True)
            await self.send_error(str(e))

    async def handle_chat_message(self, data):
        user = self.scope['user']
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')
        
        if message_type == 'text':
            await self.handle_text_message(user, content)
        elif message_type == 'file':
            await self.handle_file_message(user, data)

    async def handle_text_message(self, user, content):
        message = await self.save_message(
            chat_id=self.chat_id,
            sender=user,
            content=content,
            message_type='text'
        )
        
        if message:
            await self.broadcast_message(message)
            await self.mark_all_messages_as_read(user)

    async def handle_file_message(self, user, data):
        file_data = data.get('file_data')
        file_name = data.get('file_name')
        content = data.get('content', '')
        
        if not file_data or not file_name:
            await self.send_error('File data or name missing')
            return
        
        try:
            file_name = unquote(file_name)
            base, ext = os.path.splitext(file_name)
            ext = (ext or '').lower()
            
            if not ext:
                await self.send_json({
                    'type': 'upload_failed',
                    'reason': 'missing_extension'
                })
                return
            
            file_path = await self.save_uploaded_file(file_data, base, ext)
            
            result = process_and_save_file_task.delay(
                chat_id=self.chat_id,
                sender_id=user.id,
                file_path=file_path,
                content=content
            )
            
            await self.send_json({
                'type': 'file_upload_started',
                'task_id': result.id,
                'file_name': os.path.basename(file_path)
            })
            
        except Exception as e:
            logger.error(f"File upload error: {e}", exc_info=True)
            await self.send_json({
                'type': 'upload_failed',
                'reason': 'file_save_error'
            })

    async def save_uploaded_file(self, file_data, base_name, ext):
        payload = file_data.split(',', 1)[1] if isinstance(file_data, str) and ',' in file_data else file_data
        file_bytes = base64.b64decode(payload)
        
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'messages')
        os.makedirs(upload_dir, exist_ok=True)
        
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        candidate = f"{base_name}_{ts}{ext}"
        full_path = os.path.join(upload_dir, candidate)
        
        counter = 1
        while os.path.exists(full_path):
            candidate = f"{base_name}_{ts}_{counter}{ext}"
            full_path = os.path.join(upload_dir, candidate)
            counter += 1
        
        with open(full_path, 'wb') as f:
            f.write(file_bytes)
        
        return os.path.join('messages', candidate)

    async def broadcast_message(self, message):
        message_data = await self.format_message_data(message)
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

    async def format_message_data(self, message):
        current_user = self.scope['user']
        
        message_data = await self.get_message_fields(message)
        sender = await self.get_message_sender(message)
        sender_data = await self.get_user_data(sender)
        file_info = await self.get_file_info(message) if message_data.get('has_file') else {}
        
        return {
            'id': message_data['id'],
            'sender': sender_data,
            'content': message_data['content'],
            'message_type': message_data['message_type'],
            'celery_task_id': message_data['celery_task_id'],
            'created_at': message_data['created_at'],
            'read_by': message_data['read_by_id'],
            'read_at': message_data['read_at'],
            'is_sent': sender_data['id'] == current_user.id,
            'chat_id': message_data['chat_id'],
            **file_info
        }

    @sync_to_async
    def get_user_data(self, user):
        return {
            'id': user.id,
            'phone_number': str(user.phone_number),
            'full_name': user.get_full_name(),
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
        }

    @database_sync_to_async
    def get_message_sender(self, message):
        """Get message sender safely in async context"""
        return message.sender
    
    @database_sync_to_async
    def get_message_fields(self, message):
        """Get message fields safely in async context"""
        return {
            'id': message.id,
            'content': message.content or '',
            'message_type': message.message_type,
            'celery_task_id': message.celery_task_id,
            'created_at': message.created_at.isoformat() if message.created_at else None,
            'read_by_id': message.read_by_id,
            'read_at': message.read_at.isoformat() if message.read_at else None,
            'has_file': bool(message.file_path),
            'chat_id': message.chat.id,
        }
    
    @database_sync_to_async
    def get_file_info(self, message):
        """Get file info safely in async context"""
        if not message.file_path:
            return {}
        
        file_path_str = message.file_path.name if hasattr(message.file_path, 'name') else str(message.file_path)
        file_name = os.path.basename(file_path_str)
        file_url = self.build_file_url(file_path_str)
        
        return {
            'file_path': file_path_str,
            'file_name': file_name,
            'file_url': file_url,
        }

    def build_file_url(self, file_path):
        try:
            scheme = self.get_scheme()
            host = self.get_host()
            media_url = (settings.MEDIA_URL or '/media/').rstrip('/')
            path_part = file_path if file_path.startswith('/') else f"/{file_path}"
            
            if path_part.startswith(media_url):
                return f"{scheme}://{host}{path_part}"
            return f"{scheme}://{host}{media_url}{path_part}"
        except Exception:
            media_url = (settings.MEDIA_URL or '/media/').rstrip('/')
            return f"{media_url}/{file_path}" if not file_path.startswith('/') else f"{media_url}{file_path}"

    def get_scheme(self):
        scope_scheme = self.scope.get('scheme', 'http')
        if scope_scheme in ('websocket', 'ws'):
            return 'http'
        elif scope_scheme in ('wss', 'websocket+ssl'):
            return 'https'
        return scope_scheme

    def get_host(self):
        headers = dict(self.scope.get('headers', []))
        host = headers.get(b'host', b'').decode() if headers.get(b'host') else None
        
        if not host:
            if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
                return settings.ALLOWED_HOSTS[0]
            return 'localhost:8080'
        return host
    
    async def send_chat_history(self):
        try:
            messages = await self.get_chat_history(self.chat_id)
            
            for message in messages:
                message_data = await self.format_message_data(message)
                await self.send_json({
                    'type': 'chat_message',
                    **message_data
                })
        except Exception as e:
            logger.error(f"Error sending history: {e}", exc_info=True)

    async def handle_typing_indicator(self, data):
        user = self.scope['user']
        user_data = await self.get_user_data(user)
        
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'typing_indicator',
                'user': user_data,
                'is_typing': data.get('is_typing', False)
            }
        )

    async def handle_read_receipt(self, data):
        user = self.scope['user']
        await self.mark_all_messages_as_read(user)
        user_data = await self.get_user_data(user)
        
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'read_receipt',
                'read_by': user_data
            }
        )

    async def chat_message(self, event):
        await self.send_json({
            'type': 'chat_message',
            **event['message']
        })

    async def typing_indicator(self, event):
        if event['user']['id'] != self.scope['user'].id:
            await self.send_json({
                'type': 'typing_indicator',
                'user': event['user'],
                'is_typing': event['is_typing']
            })

    async def read_receipt(self, event):
        await self.send_json({
            'type': 'read_receipt',
            'read_by': event.get('read_by')
        })

    async def upload_failed(self, event):
        await self.send_json({
            'type': 'upload_failed',
            'message_id': event.get('message_id'),
            'reason': event.get('reason')
        })

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    async def send_error(self, message):
        await self.send_json({'type': 'error', 'message': message})

    @database_sync_to_async
    def get_chat(self, chat_id):
        try:
            return Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return None
    
    @database_sync_to_async
    def is_user_in_chat(self, chat, user):
        return chat.user1_id == user.id or chat.user2_id == user.id
    
    @database_sync_to_async
    def get_chat_history(self, chat_id, limit=100):
        try:
            return list(
                Message.objects.filter(chat_id=chat_id)
                .select_related('sender')
                .order_by('created_at')[:limit]
            )
        except Exception as e:
            logger.error(f"Error getting history: {e}", exc_info=True)
            return []

    @database_sync_to_async
    def save_message(self, chat_id, sender, content, message_type, file_field=None):
        try:
            chat = Chat.objects.get(id=chat_id)
            
            if chat.user1_id != sender.id and chat.user2_id != sender.id:
                return None
            
            message = Message.objects.create(
                chat=chat,
                sender=sender,
                content=content,
                message_type=message_type,
                file_path=file_field
            )
            message.refresh_from_db()
            message.sender = sender
            return message
            
        except Chat.DoesNotExist:
            logger.error(f"Chat {chat_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {e}", exc_info=True)
            return None

    @database_sync_to_async
    def mark_all_messages_as_read(self, user):
        """Mark all unread messages in the current chat as read"""
        try:
            chat = Chat.objects.get(id=self.chat_id)
            
            if chat.user1_id != user.id and chat.user2_id != user.id:
                return False
            
            updated = Message.objects.filter(
                chat_id=self.chat_id,
                read_by__isnull=True
            ).exclude(
                sender_id=user.id
            ).update(
                read_by=user,
                read_at=timezone.now()
            )
            
            if updated > 0:
                logger.info(f"Marked {updated} messages as read for user {user.id} in chat {self.chat_id}")
            
            return updated > 0
        except Chat.DoesNotExist:
            logger.error(f"Chat {self.chat_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error marking all messages as read: {e}", exc_info=True)
            return False
