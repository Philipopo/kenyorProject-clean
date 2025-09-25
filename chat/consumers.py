import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print('[ChatConsumer] WebSocket connection attempt')
        self.user = None
        self.group_name = None
        await self.accept()
        print('[ChatConsumer] WebSocket accepted')

    async def receive(self, text_data):
        print('[ChatConsumer] Received:', text_data)
        data = json.loads(text_data)
        if 'token' in data and self.user is None:
            try:
                token = UntypedToken(data['token'])
                self.user = await database_sync_to_async(User.objects.get)(id=token['user_id'])
                self.group_name = f"user_{self.user.id}"
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                print(f'[ChatConsumer] User {self.user.email} authenticated, added to group {self.group_name}')
                await self.send(text_data=json.dumps({'type': 'connected', 'message': 'WebSocket connected'}))
                return
            except (InvalidToken, TokenError, User.DoesNotExist) as e:
                print(f'[ChatConsumer] Authentication error: {str(e)}')
                await self.close()
                return
        elif self.user is None:
            print('[ChatConsumer] No user authenticated, closing connection')
            await self.close()
            return

        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': {'content': data.get('content', ''), 'sender': self.user.email},
            'conversation_id': data.get('conversation_id', '')
        }))

    async def disconnect(self, close_code):
        print(f'[ChatConsumer] WebSocket disconnected, code: {close_code}')
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)