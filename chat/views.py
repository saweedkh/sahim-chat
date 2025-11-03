# Django imports
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import FileResponse
from django.conf import settings

# Local imports
from .models import Chat, Message
from .serializers import ChatSerializer, ChatListSerializer, MessageSerializer, ChatUserSerializer

# Third Party Packages
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import status, generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

# Python imports
import os
from logging import getLogger

logger = getLogger(__name__)
channel_layer = get_channel_layer()

class ChatCreateView(generics.CreateAPIView):
    """
    Create a new chat.
    
    POST /api/chats/ - Create a new chat
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSerializer
    
    def perform_create(self, serializer):
        """Create chat and send notification via WebSocket."""
        chat = serializer.save()
        chat_data = ChatListSerializer(chat, context={'request': self.request}).data
        
        try:
            async_to_sync(channel_layer.group_send)(
                f'user_{chat.user1.id}_chats',
                {
                    'type': 'chat_created',
                    'chat': chat_data
                }
            )
            
            async_to_sync(channel_layer.group_send)(
                f'user_{chat.user2.id}_chats',
                {
                    'type': 'chat_created',
                    'chat': chat_data
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")

@extend_schema(
    summary='List chats or users',
    description='''
    List all chats for the authenticated user, or list users that we have chatted with.
    
    Query parameters:
    - user: If set to 'true', returns list of users we have chatted with instead of chats
    - page: Page number for pagination
    - page_size: Number of items per page
    - ordering: Order by field (e.g., '-updated_at', 'created_at')
    ''',
    parameters=[
        OpenApiParameter(
            name='user',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='If set to "true", returns list of users we have chatted with instead of chats',
            required=False,
        ),
        OpenApiParameter(
            name='page',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Page number for pagination',
            required=False,
        ),
        OpenApiParameter(
            name='page_size',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Number of items per page',
            required=False,
        ),
        OpenApiParameter(
            name='ordering',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Order by field (e.g., "-updated_at", "created_at")',
            required=False,
        ),
    ],
    responses={
        200: OpenApiTypes.OBJECT,
    }
)
class ChatListView(generics.ListAPIView):
    """
    List all chats for the authenticated user.
    
    GET /api/chats/ - List chats of the user
    GET /api/chats/?user=true - List users that we have chatted with
    
    Query parameters:
    - user: If set to 'true', returns list of users we have chatted with instead of chats
    - page: Page number for pagination
    - page_size: Number of items per page
    - ordering: Order by field (e.g., '-updated_at', 'created_at')
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at', 'updated_at', 'last_message_time']
    ordering = ['-updated_at']
    search_fields = []
    
    def get_serializer_class(self):
        """Return appropriate serializer based on query parameter."""
        if self.request.query_params.get('user', '').lower():
            return ChatUserSerializer
        return ChatListSerializer
    
    def get_queryset(self):
        """Return chats or users based on query parameter."""
        current_user = self.request.user

        qs = Chat.objects.filter(
            Q(user1=current_user) | Q(user2=current_user)
        ).distinct()
        user_id = self.request.query_params.get('user', '').lower()
        if user_id:
            return qs.filter(
                Q(user1__id=user_id) | Q(user2__id=user_id)
            ).distinct()
        return qs

    def list(self, request, *args, **kwargs):
        """Override list to handle custom queryset format for users list."""
        queryset = self.get_queryset()
        if queryset:
            serializer = self.get_serializer(queryset, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({'error': 'No chats found'}, status=status.HTTP_404_NOT_FOUND)
    
class ChatDeleteView(generics.DestroyAPIView):
    """
    Delete a chat.
    
    DELETE /api/chats/{id}/ - Delete a chat
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSerializer
    
    def get_queryset(self):
        """Return chats for current user."""
        user = self.request.user
        return Chat.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).distinct()
    
    def perform_destroy(self, instance):
        """Delete chat and send notification via WebSocket."""
        chat_id = instance.id
        user1_id = instance.user1.id
        user2_id = instance.user2.id
        
        instance.delete()
        
        try:
            async_to_sync(channel_layer.group_send)(
                f'user_{user1_id}_chats',
                {
                    'type': 'chat_deleted',
                    'chat_id': chat_id
                }
            )
            
            async_to_sync(channel_layer.group_send)(
                f'user_{user2_id}_chats',
                {
                    'type': 'chat_deleted',
                    'chat_id': chat_id
                }
            )
        except Exception as e:
            # If Redis is not available, log the error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send WebSocket notification: {e}")

class ChatRetrieveView(generics.RetrieveAPIView):
    """
    Retrieve a chat.
    
    GET /api/chats/{id}/ - Retrieve a chat
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSerializer
    
    def get_queryset(self):
        """Return chats for current user."""
        user = self.request.user
        return Chat.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).distinct()
    
class ChatUpdateView(generics.UpdateAPIView):
    """
    Update a chat.
    
    PUT /api/chats/{id}/ - Update a chat
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSerializer
    
    def get_queryset(self):
        """Return chats for current user."""
        user = self.request.user
        return Chat.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).distinct()
    
    def perform_update(self, serializer):
        """Update chat and send notification via WebSocket."""
        chat = serializer.save()
        
        chat_data = ChatListSerializer(chat, context={'request': self.request}).data
        
        # Send notification via WebSocket (only if Redis is available)
        try:
            async_to_sync(channel_layer.group_send)(
                f'user_{chat.user1.id}_chats',
                {
                    'type': 'chat_updated',
                    'chat': chat_data
                }
            )
            
            async_to_sync(channel_layer.group_send)(
                f'user_{chat.user2.id}_chats',
                {
                    'type': 'chat_updated',
                    'chat': chat_data
                }
            )
        except Exception as e:
            # If Redis is not available, log the error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send WebSocket notification: {e}")

class ChatMessagesListView(generics.ListAPIView):
    """
    Get messages for a specific chat.
    
    GET /api/chats/{chat_id}/messages/ - List messages of a chat (برای pagination و تاریخچه)
    
    Note: برای ارسال و دریافت پیام‌های real-time از WebSocket استفاده کنید: ws://domain/ws/chat/{chat_id}/
    Query parameters:
    - page: Page number for pagination
    - page_size: Number of messages per page
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return messages for the specific chat."""
        chat_id = self.kwargs['chat_id']
        chat = get_object_or_404(Chat, id=chat_id)
        
        # Verify user is part of this chat
        if chat.user1 != self.request.user and chat.user2 != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(_('شما به این چت دسترسی ندارید.'))
        
        return chat.messages.all().select_related('sender', 'chat', 'read_by')


class MessageListView(generics.ListAPIView):
    """
    List all messages for chats where user is a participant.
    
    GET /api/messages/ - لیست پیام‌ها (برای pagination و تاریخچه)
    
    Note: برای ارسال پیام جدید از WebSocket استفاده کنید: ws://domain/ws/chat/{chat_id}/
    Query parameters:
    - chat_id: Filter messages by chat ID
    - page: Page number for pagination
    - page_size: Number of messages per page
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return messages for chats where user is a participant."""
        user = self.request.user
        chat_id = self.request.query_params.get('chat_id')
        
        queryset = Message.objects.filter(
            Q(chat__user1=user) | Q(chat__user2=user)
        ).select_related('sender', 'chat', 'read_by')
        
        if chat_id:
            queryset = queryset.filter(chat_id=chat_id)
        
        return queryset


class MessageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a message instance.
    
    API Endpoints:
      -  GET /api/messages/{id}/ - Details of a message
      -  PUT /api/messages/{id}/ - Update message
      -  PATCH /api/messages/{id}/ - Partial update message
      -  DELETE /api/messages/{id}/ - Delete message
    
    Note: For marking a message as read, use WebSocket: ws://localhost:8080/ws/chat/{chat_id}/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        """Return messages for chats where user is a participant."""
        user = self.request.user
        return Message.objects.filter(
            Q(chat__user1=user) | Q(chat__user2=user)
        ).select_related('sender', 'chat', 'read_by')

class MessageFileDownloadView(APIView):
    """
    Download file from a message.
    
    GET /api/messages/{id}/file/ - دانلود فایل پیام
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Download file from message."""        
        message = get_object_or_404(
            Message.objects.filter(
                Q(chat__user1=request.user) | Q(chat__user2=request.user)
            ),
            id=pk
        )
        
        if not message.file_path:
            return Response(
                {'error': 'این پیام فایلی ندارد'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        file_path = message.file_path.path if hasattr(message.file_path, 'path') else os.path.join(settings.MEDIA_ROOT, str(message.file_path))
        
        if not os.path.exists(file_path):
            return Response(
                {'error': 'فایل پیدا نشد'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        filename = os.path.basename(file_path)
        file = open(file_path, 'rb')
        response = FileResponse(file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

# WebSocket Documentation Views
@extend_schema(
    tags=['WebSocket'],
    summary='WebSocket Chat Documentation',
    description='''
    Documentation for WebSocket chat endpoint.
    
    **Endpoint**: `ws://localhost:8000/ws/chat/{chat_id}/`
    
    **Authentication**:
    - Query Parameter: `?token=<jwt_token>`
    - Header: `Authorization: Bearer <jwt_token>`
    
    **Connection Flow**:
    1. Connect to WebSocket URL
    2. Server validates JWT token
    3. Server joins user to chat group
    4. Server sends connection confirmation
    
    **Client → Server Message Types**:
    
    1. **chat_message** - Send a new message
       ```json
       {
         "type": "chat_message",
         "content": "message text",
         "message_type": "text" | "image" | "file",
         "file_path": "optional file path"
       }
       ```
    
    2. **typing** - Send typing indicator
       ```json
       {
         "type": "typing",
         "is_typing": true | false
       }
       ```
    
    3. **read_receipt** - Mark message as read
       ```json
       {
         "type": "read_receipt",
         "message_id": 1
       }
       ```
    
    **Server → Client Message Types**:
    
    1. **connection_established** - Connection confirmation
    2. **chat_message** - New message broadcast
    3. **typing_indicator** - User typing status
    4. **read_receipt** - Message read status
    ''',
    responses={200: OpenApiTypes.OBJECT}
)
class WebSocketChatDocView(APIView):
    """WebSocket Chat Documentation API."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return WebSocket chat documentation."""
        return Response({
            'endpoint': 'ws://localhost:8000/ws/chat/{chat_id}/',
            'description': 'WebSocket endpoint for real-time chat messaging',
            'authentication': {
                'query_parameter': '?token=<jwt_token>',
                'header': 'Authorization: Bearer <jwt_token>'
            },
            'client_to_server': {
                'chat_message': {
                    'type': 'chat_message',
                    'content': 'string (required)',
                    'message_type': 'text | image | file (default: text)',
                    'file_path': 'string (optional)'
                },
                'typing': {
                    'type': 'typing',
                    'is_typing': 'boolean (required)'
                },
                'read_receipt': {
                    'type': 'read_receipt',
                    'message_id': 'integer (required)'
                }
            },
            'server_to_client': {
                'connection_established': {
                    'type': 'connection_established',
                    'message': 'string',
                    'chat_id': 'integer'
                },
                'chat_message': {
                    'type': 'chat_message',
                    'id': 'integer',
                    'sender': 'object',
                    'content': 'string',
                    'message_type': 'string',
                    'created_at': 'datetime'
                },
                'typing_indicator': {
                    'type': 'typing_indicator',
                    'user': 'object',
                    'is_typing': 'boolean'
                },
                'read_receipt': {
                    'type': 'read_receipt',
                    'message_id': 'integer',
                    'read_by': 'object'
                }
            }
        })

@extend_schema(
    tags=['WebSocket'],
    summary='WebSocket User Chats Documentation',
    description='''
    Documentation for WebSocket user chats notification endpoint.
    
    **Endpoint**: `ws://localhost:8000/ws/user/chats/`
    
    **Authentication**:
    - Query Parameter: `?token=<jwt_token>`
    - Header: `Authorization: Bearer <jwt_token>`
    
    **Connection Flow**:
    1. Connect to WebSocket URL
    2. Server validates JWT token
    3. Server joins user to their personal notification group
    4. Server sends connection confirmation
    
    **Server → Client Notification Types**:
    
    1. **chat_created** - New chat created
       ```json
       {
         "type": "chat_created",
         "chat": { ... }
       }
       ```
    
    2. **chat_updated** - Chat updated
       ```json
       {
         "type": "chat_updated",
         "chat": { ... }
       }
       ```
    
    3. **chat_deleted** - Chat deleted
       ```json
       {
         "type": "chat_deleted",
         "chat_id": 1
       }
       ```
    ''',
    responses={200: OpenApiTypes.OBJECT}
)
class WebSocketUserChatsDocView(APIView):
    """WebSocket User Chats Documentation API."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return WebSocket user chats documentation."""
        return Response({
            'endpoint': 'ws://localhost:8000/ws/user/chats/',
            'description': 'WebSocket endpoint for receiving real-time chat notifications',
            'authentication': {
                'query_parameter': '?token=<jwt_token>',
                'header': 'Authorization: Bearer <jwt_token>'
            },
            'server_to_client': {
                'connection_established': {
                    'type': 'connection_established',
                    'message': 'string',
                    'user_id': 'integer'
                },
                'chat_created': {
                    'type': 'chat_created',
                    'chat': 'object'
                },
                'chat_updated': {
                    'type': 'chat_updated',
                    'chat': 'object'
                },
                'chat_deleted': {
                    'type': 'chat_deleted',
                    'chat_id': 'integer'
                }
            }
        })
