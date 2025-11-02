# Django imports
from django.utils.translation import gettext_lazy as _
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import base64
from django.conf import settings

# Local imports
from .models import Chat, Message

# Python imports
import json
import os
from logging import getLogger
from datetime import datetime

User = get_user_model()
logger = getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer for handling real-time chat messages.
    
    This consumer manages:
    - WebSocket connections for chat rooms
    - Sending and receiving messages
    - Broadcasting messages to connected users
    - Managing user presence in chat rooms
    """

    async def connect(self):
        """Called when a WebSocket connection is established."""
        # Get chat_id from URL route
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'
        user = self.scope['user']
        
        # Check if user is authenticated
        if user.is_anonymous:
            logger.warning(f"WebSocket connection rejected: User is anonymous for chat {self.chat_id}")
            await self.close(code=4001)  # 4001 = Unauthorized
            return
        
        logger.info(f"WebSocket connection attempt: User {user.id} trying to connect to chat {self.chat_id}")
        
        # Verify user is part of this chat
        chat = await self.get_chat(self.chat_id)
        if not chat:
            logger.warning(f"WebSocket connection rejected: Chat {self.chat_id} not found")
            await self.close(code=4004)  # 4004 = Not Found
            return
        
        if chat.user1_id != user.id and chat.user2_id != user.id:
            logger.warning(f"WebSocket connection rejected: User {user.id} is not part of chat {self.chat_id}")
            await self.close(code=4003)  # 4003 = Forbidden
            return
        
        try:
            # Join room group
            await self.channel_layer.group_add(
                self.chat_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            logger.info(f"WebSocket connected: User {user.id} connected to chat {self.chat_id}")
            
            # Send chat history (previous messages)
            await self.send_chat_history()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to chat',
                'chat_id': self.chat_id
            }))
        except Exception as e:
            logger.error(f"WebSocket connection error: {type(e).__name__}: {str(e)}", exc_info=True)
            await self.close(code=1011)  # 1011 = Internal Error
    
    @database_sync_to_async
    def get_chat(self, chat_id):
        """Get chat by ID."""
        try:
            return Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_chat_history(self, chat_id, limit=100):
        """Get chat message history."""
        try:
            messages = Message.objects.filter(chat_id=chat_id).select_related('sender').order_by('created_at')[:limit]
            return list(messages)
        except Exception as e:
            logger.error(f"Error getting chat history: {e}", exc_info=True)
            return []

    def _build_absolute_uri_sync(self, path):
        """
        Build absolute URI from scope (synchronous helper).
        WebSocket doesn't have request object, so we build URL manually.
        """
        # Get scheme from scope (websocket -> http, wss -> https)
        scope_scheme = self.scope.get('scheme', 'http')
        if scope_scheme in ('websocket', 'ws'):
            scheme = 'http'
        elif scope_scheme in ('wss', 'websocket+ssl'):
            scheme = 'https'
        else:
            scheme = scope_scheme
        
        # Get host from headers
        host = None
        headers = dict(self.scope.get('headers', []))
        if b'host' in headers:
            host = headers[b'host'].decode('utf-8')
        
        # Fallback to ALLOWED_HOSTS or default
        if not host:
            if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
                host = settings.ALLOWED_HOSTS[0]
            else:
                host = 'localhost:8000'
        
        # Build absolute URI manually
        # Ensure path starts with / if it doesn't
        if not path.startswith('/'):
            path = '/' + path
        
        # If path doesn't start with /media/, add MEDIA_URL
        media_url = settings.MEDIA_URL.rstrip('/')
        if media_url and not path.startswith(media_url):
            path = f"{media_url}{path}"
        
        # Build full URL
        base_url = f"{scheme}://{host}"
        # Remove trailing slash from base_url if exists
        base_url = base_url.rstrip('/')
        
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        return f"{base_url}{path}"
    
    async def build_absolute_uri(self, path):
        """Async wrapper for build_absolute_uri."""
        build_uri_func = sync_to_async(self._build_absolute_uri_sync)
        return await build_uri_func(path)

    async def disconnect(self, close_code):
        """Called when WebSocket connection is closed."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Called when a message is received from WebSocket.
        
        Expected message format:
        {
            "type": "chat_message",
            "content": "message text",
            "message_type": "text" | "image" | "file",
            "file_path": "optional file path"
        }
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing_indicator(data)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(data)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid message type'
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_chat_message(self, data):
        """Handle incoming chat message and broadcast it."""
        
        logger.info(f"handle_chat_message ---> {data}")

        user = self.scope['user']
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')
        file_path = data.get('file_path')
        
        file_data = data.get('file_data')
        file_name = data.get('file_name')
        
        if file_data and file_name:
            # Save base64 file to disk
            file_path = await self.save_base64_file(file_data, file_name, message_type)
            if not file_path:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to save file'
                }))
                return
        
        if not content and not file_path:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Message content or file is required'
            }))
            return
        
        # If file_path exists, read file and create ContentFile using sync_to_async
        file_field = None
        if file_path:
            read_file_func = sync_to_async(self._read_file_and_create_contentfile)
            file_field = await read_file_func(file_path)
            if not file_field:
                logger.warning(f"Could not create ContentFile from file_path: {file_path}")
        
        message = await self.save_message(
            chat_id=self.chat_id,
            sender=user,
            content=content,
            message_type=message_type,
            file_field=file_field
        )
        
        if message:
            # Format message data
            message_data = await self.format_message_data(message)
            
            # Broadcast message to room group
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to save message'
            }))

    async def format_message_data(self, message):
        """Format message data for WebSocket response."""
        current_user = self.scope['user']
        is_sent = message.sender.id == current_user.id
        
        file_url = None
        file_path_str = None
        file_name = None
        
        if message.file_path:
            file_path_str = message.file_path.name if hasattr(message.file_path, 'name') else str(message.file_path)
            # Use sync_to_async for os.path.basename
            basename_func = sync_to_async(os.path.basename)
            file_name = await basename_func(file_path_str)
            try:
                file_url = await self.build_absolute_uri(file_path_str)
                if not file_url:
                    media_url = settings.MEDIA_URL.rstrip('/')
                    if file_path_str.startswith(media_url):
                        file_url = file_path_str
                    elif file_path_str.startswith('/'):
                        file_url = f"{media_url}{file_path_str}"
                    else:
                        file_url = f"{media_url}/{file_path_str}"
            except Exception as e:
                logger.error(f"Error building absolute URI for file: {e}", exc_info=True)
                media_url = settings.MEDIA_URL.rstrip('/')
                if file_path_str.startswith('/'):
                    file_url = f"{media_url}{file_path_str}"
                else:
                    file_url = f"{media_url}/{file_path_str}"
        
        return {
            'id': message.id,
            'sender': {
                'id': message.sender.id,
                'phone_number': str(message.sender.phone_number),
                'full_name': message.sender.get_full_name(),
                'profile_picture': message.sender.profile_picture or None,
            },
            'content': message.content or '',
            'message_type': message.message_type,
            'file_path': file_path_str,
            'file_url': file_url,
            'file_name': file_name,
            'created_at': message.created_at.isoformat() if message.created_at else None,
            'read_by': message.read_by_id,
            'read_at': message.read_at.isoformat() if message.read_at else None,
            'is_sent': is_sent, 
        }
    
    async def send_chat_history(self):
        """Send chat history to the connected user."""
        try:
            messages = await self.get_chat_history(self.chat_id)
            current_user = self.scope['user']
            
            logger.info(f"Sending chat history: {len(messages)} messages to user {current_user.id}")
            
            for message in messages:
                message_data = await self.format_message_data(message)
                await self.send(text_data=json.dumps({
                    'type': 'chat_message',
                    **message_data
                }))
        except Exception as e:
            logger.error(f"Error sending chat history: {e}", exc_info=True)

    async def handle_typing_indicator(self, data):
        """Handle typing indicator and broadcast to other users."""
        user = self.scope['user']
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'typing_indicator',
                'user': {
                    'id': user.id,
                    'phone_number': str(user.phone_number),
                    'full_name': user.get_full_name(),
                },
                'is_typing': is_typing
            }
        )

    async def handle_read_receipt(self, data):
        """Handle read receipt and mark message as read."""
        user = self.scope['user']
        message_id = data.get('message_id')
        
        if message_id:
            await self.mark_message_as_read(message_id, user)
            
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'read_by': {
                        'id': user.id,
                        'phone_number': str(user.phone_number),
                        'full_name': user.get_full_name(),
                    }
                }
            )

    # Handler methods for group messages
    
    async def chat_message(self, event):
        """Called when a chat message is received from group."""
        message = event['message']
        sender_id = message.get('sender', {}).get('id') if isinstance(message.get('sender'), dict) else None
        current_user_id = self.scope['user'].id
        
        if sender_id != current_user_id:
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                **message
            }))

    async def typing_indicator(self, event):
        """Called when a typing indicator is received from group."""
        if event['user']['id'] != self.scope['user'].id:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user': event['user'],
                'is_typing': event['is_typing']
            }))

    async def read_receipt(self, event):
        """Called when a read receipt is received from group."""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'read_by': event['read_by']
        }))

    # Database operations
    
    def _save_base64_file_sync(self, file_data, file_name, message_type):
        """Save base64 file to disk and return file path (synchronous helper)."""
        try:
            from django.conf import settings
            
            # Decode base64
            try:
                file_content = base64.b64decode(file_data)
            except Exception as e:
                logger.error(f"Error decoding base64 file: {e}")
                return None
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            name, ext = os.path.splitext(file_name)
            unique_filename = f"{name}_{timestamp}{ext}"
            
            # Create file path
            upload_to = 'messages/'
            file_path = os.path.join(upload_to, unique_filename)
            
            # Create directory if it doesn't exist
            full_path = os.path.join(settings.MEDIA_ROOT, upload_to)
            os.makedirs(full_path, exist_ok=True)
            
            # Save file
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
            with open(full_file_path, 'wb') as f:
                f.write(file_content)
            
            # Return relative path for FileField
            return file_path
        except Exception as e:
            logger.error(f"Error saving base64 file: {e}", exc_info=True)
            return None
    
    async def save_base64_file(self, file_data, file_name, message_type):
        """Async wrapper for save_base64_file."""
        save_file_func = sync_to_async(self._save_base64_file_sync)
        return await save_file_func(file_data, file_name, message_type)
    
    def _read_file_and_create_contentfile(self, file_path):
        """Read file from disk and create ContentFile (synchronous helper)."""
        try:
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    filename = os.path.basename(file_path)
                    file_content = f.read()
                    file_field = ContentFile(file_content, name=filename)
                    logger.info(f"Creating ContentFile with filename: {filename}, original path: {file_path}, full_path: {full_path}")
                    return file_field
            else:
                logger.warning(f"File not found at path: {full_path}, file_path param: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error reading file: {e}", exc_info=True)
            return None
    
    @database_sync_to_async
    def save_message(self, chat_id, sender, content, message_type, file_field=None):
        """Save message to database."""
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
            
            if message.file_path:
                logger.info(f"Message saved with file_path: {message.file_path.name if hasattr(message.file_path, 'name') else message.file_path}")
            else:
                logger.warning(f"Message saved but file_path is empty. file_field was: {file_field}")
            
            return message
        except Chat.DoesNotExist:
            logger.error(f"Chat {chat_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {e}", exc_info=True)
            return None

    @database_sync_to_async
    def mark_message_as_read(self, message_id, user):
        """Mark a message as read."""
        try:
            message = Message.objects.get(id=message_id)
            
            # Verify user is part of this chat
            if message.chat.user1_id != user.id and message.chat.user2_id != user.id:
                return False
            
            # Only mark as read if user is not the sender
            if message.sender_id != user.id and not message.read_by:
                from django.utils import timezone
                message.read_by = user
                message.read_at = timezone.now()
                message.save()
                return True
            return False
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error marking message as read: {e}", exc_info=True)
            return False


class UserChatsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer for managing user's chat list notifications.
    
    This consumer handles:
    - New chat created notifications
    - Chat updated notifications
    - Chat deleted notifications
    """
    
    async def connect(self):
        """Called when a WebSocket connection is established."""
        user = self.scope['user']
        
        if user.is_anonymous:
            logger.warning(f"WebSocket connection rejected: User is anonymous for user chats")
            await self.close(code=4001) 
            return
        
        logger.info(f"WebSocket connection attempt: User {user.id} trying to connect to user chats")
        
        self.user_group_name = f'user_{user.id}_chats'
        
        try:
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            logger.info(f"WebSocket connected: User {user.id} connected to user chats")
            
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to user chats',
                'user_id': user.id
            }))
        except Exception as e:
            logger.error(f"WebSocket connection error: {type(e).__name__}: {str(e)}", exc_info=True)
            await self.close(code=1011) 

    async def disconnect(self, close_code):
        """Called when WebSocket connection is closed."""
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    async def chat_created(self, event):
        """Called when a new chat is created."""
        await self.send(text_data=json.dumps({
            'type': 'chat_created',
            'chat': event['chat']
        }))
    
    async def chat_updated(self, event):
        """Called when a chat is updated."""
        await self.send(text_data=json.dumps({
            'type': 'chat_updated',
            'chat': event['chat']
        }))
    
    async def chat_deleted(self, event):
        """Called when a chat is deleted."""
        await self.send(text_data=json.dumps({
            'type': 'chat_deleted',
            'chat_id': event['chat_id']
        }))

