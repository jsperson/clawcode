"""WebSocket server for the gateway.

Accepts client connections on 127.0.0.1:PORT, delegates message handling
to the Router. Each connection is an independent asyncio task.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import websockets
from websockets.asyncio.server import ServerConnection

from .router import Router

logger = logging.getLogger(__name__)


class GatewayServer:
    """Asyncio WebSocket server bound to localhost."""

    def __init__(self, router: Router, host: str = "127.0.0.1", port: int = 7429) -> None:
        self._router = router
        self._host = host
        self._port = port
        self._server: websockets.asyncio.server.Server | None = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await websockets.asyncio.server.serve(
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=20_000_000,  # 20 MB — accommodate base64 image payloads
        )
        logger.info("Gateway WebSocket server listening on ws://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Gateway WebSocket server stopped")

    async def _handle_connection(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        client_id = str(uuid.uuid4())
        client = self._router.register_client(ws, client_id)

        try:
            async for raw_message in ws:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8", errors="replace")
                await self._router.handle_message(client, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            logger.exception("Error in client connection %s", client_id[:8])
        finally:
            self._router.unregister_client(client_id)
