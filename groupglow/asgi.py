"""
ASGI config for groupglow project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'groupglow.settings')

# Get the default ASGI app first
application = get_asgi_application()

# Try to add Channels if available
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from django.urls import re_path
    from quiz_app.consumers_v2 import QuizConsumer
    from quiz_app.middleware import TokenAuthMiddleware

    websocket_urlpatterns = [
        re_path(r'ws/quiz/(?P<room_code>\w+)/$', QuizConsumer.as_asgi()),
    ]

    application = ProtocolTypeRouter({
        'http': application,
        'websocket': TokenAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        ),
    })
except ImportError:
    # Fallback if Channels not available
    pass
