from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework.authtoken.models import Token


@database_sync_to_async
def get_user_from_token(token_key):
    try:
        token = Token.objects.select_related('user').get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    """Custom token auth middleware for Channels WebSocket connections."""

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token_keys = query_params.get('token', [])
        user = AnonymousUser()

        if token_keys:
            token_key = token_keys[0]
            user = await get_user_from_token(token_key)

        scope['user'] = user
        return await super().__call__(scope, receive, send)
