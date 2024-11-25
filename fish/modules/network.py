import asyncio

import websockets

from .log import logger


class WebSocketClient:
    def __init__(self, server_uri: str, loop: asyncio.AbstractEventLoop):
        self.server_uri = server_uri
        self.websocket = None
        self.async_queue = asyncio.Queue(maxsize=100)
        self.loop = loop

    async def connect(self):
        self.websocket = await websockets.connect(self.server_uri)
        logger.info(f"Connected to server at {self.server_uri}")

    async def send_data(self, data: bytes | str):
        if self.websocket:
            try:
                await self.websocket.send(data)
                # logger.info(f"Sent {len(data)} bytes of data to server.")
            except websockets.exceptions.ConnectionClosedOK:
                pass
            except Exception as e:
                logger.error(f"Error sending data: {e}")
        else:
            logger.warning("WebSocket connection is not established.")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed.")
        else:
            logger.warning("WebSocket connection is not established.")

    async def consume_data(self):
        # logger.warning(f"consume: {self.async_queue.qsize()}")
        while True:
            data = await self.async_queue.get()
            if data is None:
                logger.info("Received None, stop consuming...")
                break
            else:
                await self.send_data(data)

    async def start(self):
        await self.connect()
