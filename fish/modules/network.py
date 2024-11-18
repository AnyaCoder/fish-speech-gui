import asyncio

import websockets

from .log import logger


class WebSocketClient:
    def __init__(self, server_uri: str):
        self.server_uri = server_uri
        self.websocket = None  # WebSocket connection object

    async def connect(self):
        self.websocket = await websockets.connect(self.server_uri)
        logger.info(f"Connected to server at {self.server_uri}")

    async def send_data(self, data: bytes):
        if self.websocket:
            await self.websocket.send(data)
            logger.info(f"Sent {len(data)} bytes of data to server.")
        else:
            logger.warning("WebSocket connection is not established.")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed.")
        else:
            logger.warning("WebSocket connection is not established.")

    async def consume_data(self, queue: asyncio.Queue):
        while True:
            data = (
                await queue.get()
            )  # Block and wait for data to be available in the queue
            if data is None:  # A 'None' value is used as a termination signal
                break
            await self.send_data(data)

    async def start(self, queue: asyncio.Queue):
        await self.connect()
        try:
            await self.consume_data(queue)
        except asyncio.CancelledError:
            logger.warning("Data sending was cancelled.")
        finally:
            await self.close()
