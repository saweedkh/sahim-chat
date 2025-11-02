"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from chat.routing import websocket_urlpatterns
from chat.middleware import JWTAuthMiddlewareStack

# WebSocket application stack
websocket_application = JWTAuthMiddlewareStack(
    URLRouter(websocket_urlpatterns)
)

# Wrap with Origin validator only if not in DEBUG mode or if ALLOWED_HOSTS is configured
# In DEBUG mode, we may want to allow all origins for development
if not settings.DEBUG or '*' not in settings.ALLOWED_HOSTS:
    websocket_application = AllowedHostsOriginValidator(websocket_application)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": websocket_application,
})
