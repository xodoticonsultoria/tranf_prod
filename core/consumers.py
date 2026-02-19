import json
from channels.generic.websocket import AsyncWebsocketConsumer

class OrderConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.channel_layer.group_add(
            "orders_group",
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            "orders_group",
            self.channel_name
        )

    async def order_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "order_update",
            "message": event["message"]
        }))
