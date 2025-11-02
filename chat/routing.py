# Django imports
from django.urls import re_path

# Local imports
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/user/chats/$', consumers.UserChatsConsumer.as_asgi()),
]

