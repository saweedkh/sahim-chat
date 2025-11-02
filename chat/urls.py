# Django imports
from django.urls import path

# Local imports
from .views import (
    ChatCreateView,
    ChatListView,
    ChatRetrieveView,
    ChatUpdateView,
    ChatDeleteView,
    ChatMessagesListView,
    MessageListView,
    MessageRetrieveUpdateDestroyView,
    MessageFileDownloadView,
    WebSocketChatDocView,
    WebSocketUserChatsDocView,
)

urlpatterns = [
    path('chats/', ChatListView.as_view(), name='chat-list'),
    path('chats/create/', ChatCreateView.as_view(), name='chat-create'),
    path('chats/<int:pk>/', ChatRetrieveView.as_view(), name='chat-retrieve'),
    path('chats/<int:pk>/update/', ChatUpdateView.as_view(), name='chat-update'),
    path('chats/<int:pk>/delete/', ChatDeleteView.as_view(), name='chat-delete'),
    path('chats/<int:chat_id>/messages/', ChatMessagesListView.as_view(), name='chat-messages-list'),
    
    path('messages/', MessageListView.as_view(), name='message-list'),
    path('messages/<int:pk>/', MessageRetrieveUpdateDestroyView.as_view(), name='message-retrieve-update-destroy'),
    path('messages/<int:pk>/file/', MessageFileDownloadView.as_view(), name='message-file-download'),
    
    # WebSocket Documentation endpoints
    path('websocket/chat/doc/', WebSocketChatDocView.as_view(), name='websocket-chat-doc'),
    path('websocket/user/chats/doc/', WebSocketUserChatsDocView.as_view(), name='websocket-user-chats-doc'),
]