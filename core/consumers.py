from channels.generic.websocket import AsyncWebsocketConsumer
import json


class OrderConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("🔥 CONECTOU")
        await self.channel_layer.group_add(
            "orders_group",
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        print("❌ DESCONECTOU")
        await self.channel_layer.group_discard(
            "orders_group",
            self.channel_name
        )

    async def order_update(self, event):
        print("📩 RECEBEU EVENTO:", event)
        await self.send(text_data=json.dumps(event))