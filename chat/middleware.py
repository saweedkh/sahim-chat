# Django imports
from typing import Any
from logging import getLogger
from django.contrib.auth.models import AnonymousUser
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.db import close_old_connections

# Third party imports
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings
from urllib.parse import parse_qs
from django.contrib.auth import get_user_model

User = get_user_model()
logger = getLogger(__name__)


@database_sync_to_async
def get_user(validated_token):
    """
    Get user from validated token.
    """
    try:
        user_id = validated_token['user_id']
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Custom JWT authentication middleware for WebSocket connections.
    
    This middleware:
    - Validates JWT tokens from query parameters or headers
    - Authenticates users for WebSocket connections
    - Adds user to scope for use in consumers
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """
        Authenticate WebSocket connection using JWT token.
        
        Token can be provided in:
        - Query parameter: ?token=<jwt_token>
        - Header: Authorization: Bearer <jwt_token>
        """
        close_old_connections()
        
        token = None
        
        query_string = parse_qs(scope['query_string'].decode())
        if 'token' in query_string:
            token = query_string['token'][0]
        
        if not token:
            headers = dict(scope['headers'])
            if b'authorization' in headers:
                auth_header = headers[b'authorization'].decode()
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
        
        if token:
            try:
                UntypedToken(token)
                decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user = await get_user(decoded_data)
                scope['user'] = user
                if user.is_anonymous:
                    logger.warning(f"JWT Authentication: User not found in database for token")
            except (InvalidToken, TokenError) as e:
                logger.warning(f"JWT Authentication failed: {type(e).__name__}: {str(e)}")
                scope['user'] = AnonymousUser()
            except Exception as e:
                logger.error(f"JWT Authentication error: {type(e).__name__}: {str(e)}", exc_info=True)
                scope['user'] = AnonymousUser()
        else:
            logger.debug("WebSocket: No JWT token provided in query string or headers")
            scope['user'] = AnonymousUser()
        
        return await self.app(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Stack JWT auth middleware on top of AuthMiddlewareStack.
    """
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))

