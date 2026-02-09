"""WebSocket client for the Discord bot to communicate with the gateway.

When gateway.enabled is True, the bot routes messages through the gateway
instead of invoking Claude Code CLI directly. Falls back to ClaudeBridge
if the gateway is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import websockets

logger = logging.getLogger(__name__)


class GatewayClient:
    """WebSocket client that connects the Discord bot to the gateway."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7429,
        auth_token: str = "",
    ) -> None:
        self._uri = f"ws://{host}:{port}"
        self._auth_token = auth_token
        self._ws: websockets.ClientConnection | None = None
        self._connected = False
        self._client_id: str | None = None
        self._sessions: dict[str, str] = {}  # channel_id -> gateway session_id
        self._response_queues: dict[str, asyncio.Queue] = {}  # session_id -> response queue
        self._reader_task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    async def connect(self) -> bool:
        """Connect to the gateway and authenticate.

        Returns True if connection + auth succeeded, False otherwise.
        """
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self._uri,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=20_000_000,
                ),
                timeout=5,
            )
        except (OSError, asyncio.TimeoutError, Exception) as e:
            logger.warning("Gateway connection failed (%s): %s", self._uri, e)
            self._connected = False
            return False

        # Authenticate
        auth_msg = json.dumps({
            "type": "auth",
            "token": self._auth_token,
            "client_type": "discord",
        })
        await self._ws.send(auth_msg)

        try:
            resp = await asyncio.wait_for(self._ws.recv(), timeout=5)
            data = json.loads(resp)
            if data.get("type") == "auth.ok":
                self._client_id = data.get("client_id")
                self._connected = True
                self._reader_task = asyncio.create_task(self._read_loop())
                logger.info("Connected to gateway at %s (client=%s)", self._uri, self._client_id[:8])
                return True
            else:
                logger.warning("Gateway auth failed: %s", data)
                await self._ws.close()
                self._connected = False
                return False
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("Gateway auth timeout/error: %s", e)
            if self._ws:
                await self._ws.close()
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Disconnected from gateway")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        attachments: list[dict] | None = None,
    ) -> str:
        """Send a message through the gateway and collect the full response.

        Args:
            channel_id: Discord channel ID (maps to a gateway session).
            content: The user's message text.
            attachments: Optional list of attachment dicts with keys:
                filename, content_type, data (base64-encoded).

        Returns:
            The complete assistant response text.

        Raises:
            RuntimeError: If sending fails or the session can't be created.
            TimeoutError: If no response within timeout.
        """
        if not self.connected:
            raise RuntimeError("Not connected to gateway")

        # Get or create a session for this channel
        session_id = self._sessions.get(channel_id)
        if not session_id:
            session_id = await self._create_session(channel_id)
            self._sessions[channel_id] = session_id

        # Set up response queue
        queue: asyncio.Queue = asyncio.Queue()
        self._response_queues[session_id] = queue

        # Send the message
        msg = json.dumps({
            "type": "message",
            "session_id": session_id,
            "content": content,
            "attachments": attachments or [],
        })
        await self._ws.send(msg)

        # Collect response chunks until complete
        full_response = []
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                event_type = event.get("type")

                if event_type == "chunk":
                    full_response.append(event.get("content", ""))

                elif event_type == "response":
                    # Complete response — use result text
                    return event.get("content", "".join(full_response))

                elif event_type == "error":
                    code = event.get("code", "unknown")
                    message = event.get("message", "Unknown error")

                    # Session not found — clear cached session and retry
                    if code in ("session_not_found", "session_expired"):
                        self._sessions.pop(channel_id, None)
                        raise RuntimeError(f"Session error ({code}): {message}")

                    raise RuntimeError(f"Gateway error ({code}): {message}")
        except asyncio.TimeoutError:
            raise TimeoutError("Gateway response timed out after 300s")
        finally:
            self._response_queues.pop(session_id, None)

    async def _create_session(self, channel_id: str) -> str:
        """Create a new gateway session for a Discord channel."""
        queue: asyncio.Queue = asyncio.Queue()
        # Use a temporary key to receive the session.created response
        temp_key = f"_pending_{channel_id}"
        self._response_queues[temp_key] = queue

        msg = json.dumps({
            "type": "session.create",
            "metadata": {"channel_id": channel_id},
        })
        await self._ws.send(msg)

        try:
            event = await asyncio.wait_for(queue.get(), timeout=10)
            if event.get("type") == "session.created":
                session_id = event["session_id"]
                logger.info("Created gateway session %s for channel %s", session_id[:8], channel_id)
                # Move queue to the real session key
                self._response_queues[session_id] = self._response_queues.pop(temp_key, queue)
                return session_id
            else:
                raise RuntimeError(f"Failed to create session: {event}")
        except asyncio.TimeoutError:
            raise RuntimeError("Timed out creating gateway session")
        finally:
            self._response_queues.pop(temp_key, None)

    async def _read_loop(self) -> None:
        """Background task that reads messages from the gateway WebSocket."""
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = data.get("type")
                session_id = data.get("session_id")

                # Route to the appropriate response queue
                if session_id and session_id in self._response_queues:
                    await self._response_queues[session_id].put(data)
                elif event_type == "session.created":
                    # Route to pending session creation queues
                    for key, q in list(self._response_queues.items()):
                        if key.startswith("_pending_"):
                            await q.put(data)
                            break
                elif event_type == "push":
                    # Push events (schedule output, etc.) — log for now
                    logger.info("Push event: source=%s task=%s",
                                data.get("source"), data.get("task"))
                elif event_type == "lifecycle":
                    logger.info("Gateway lifecycle: %s", data.get("event"))

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Gateway connection closed")
            self._connected = False
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in gateway read loop")
            self._connected = False
