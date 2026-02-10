"""Message router — connects clients to sessions and claude processes.

Routes messages between WebSocket clients and their claude subprocess sessions.
Handles streaming responses, broadcasting push events, and session lifecycle.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from typing import Any

from .claude_pool import ClaudePool
from .protocol import (
    AuthError,
    AuthOk,
    AuthRequest,
    CancelRequest,
    ClientType,
    ErrorEvent,
    ResponseChunk,
    ResponseComplete,
    SessionAttach,
    SessionAttachOk,
    SessionCreate,
    SessionCreated,
    SessionDetach,
    SessionDetachOk,
    SessionList,
    SessionListOk,
    SessionResume,
    SessionResumed,
    SessionStatus,
    UserMessage,
    parse_request,
    to_dict,
)
from .sessions import Session, SessionManager

logger = logging.getLogger(__name__)


class Client:
    """A connected WebSocket client."""

    def __init__(self, ws: Any, client_id: str) -> None:
        self.ws = ws
        self.client_id = client_id
        self.client_type: ClientType | None = None
        self.authenticated: bool = False
        self.session_id: str | None = None
        self.metadata: dict = {}

    async def send(self, msg: Any) -> None:
        """Send a protocol message to this client."""
        try:
            await self.ws.send(json.dumps(to_dict(msg)))
        except Exception:
            logger.debug("Failed to send to client %s", self.client_id[:8])


class Router:
    """Routes messages between clients and claude processes."""

    def __init__(
        self,
        session_mgr: SessionManager,
        claude_pool: ClaudePool,
        auth_token: str,
        context_fn: Any = None,
    ) -> None:
        self._sessions = session_mgr
        self._pool = claude_pool
        self._auth_token = auth_token
        self._context_fn = context_fn  # Callable that returns context string
        self._clients: dict[str, Client] = {}  # client_id -> Client
        self._session_locks: dict[str, asyncio.Lock] = {}  # per-session message ordering

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register_client(self, ws: Any, client_id: str) -> Client:
        """Register a new WebSocket connection."""
        client = Client(ws, client_id)
        self._clients[client_id] = client
        logger.info("Client connected: %s", client_id[:8])
        return client

    def unregister_client(self, client_id: str) -> None:
        """Remove a disconnected client. Auto-detaches any TUI-attached sessions."""
        client = self._clients.pop(client_id, None)
        if client:
            self._sessions.detach_by_client(client_id)
            logger.info("Client disconnected: %s (type=%s)", client_id[:8],
                        client.client_type.value if client.client_type else "unknown")

    async def handle_message(self, client: Client, raw: str) -> None:
        """Handle an incoming WebSocket message from a client."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await client.send(ErrorEvent(code="invalid_json", message="Invalid JSON"))
            return

        try:
            request = parse_request(data)
        except ValueError as e:
            await client.send(ErrorEvent(code="unknown_type", message=str(e)))
            return

        if isinstance(request, AuthRequest):
            await self._handle_auth(client, request)
        elif not client.authenticated:
            await client.send(ErrorEvent(code="not_authenticated", message="Authenticate first"))
        elif isinstance(request, SessionCreate):
            await self._handle_session_create(client, request)
        elif isinstance(request, SessionResume):
            await self._handle_session_resume(client, request)
        elif isinstance(request, UserMessage):
            await self._handle_message(client, request)
        elif isinstance(request, CancelRequest):
            await self._handle_cancel(client, request)
        elif isinstance(request, SessionList):
            await self._handle_session_list(client, request)
        elif isinstance(request, SessionAttach):
            await self._handle_session_attach(client, request)
        elif isinstance(request, SessionDetach):
            await self._handle_session_detach(client, request)

    async def broadcast(self, msg: Any, exclude: str | None = None) -> None:
        """Send a message to all authenticated clients."""
        for client in self._clients.values():
            if client.authenticated and client.client_id != exclude:
                await client.send(msg)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    async def _get_session_or_error(self, client: Client, session_id: str) -> Session | None:
        """Look up a session, sending an error to the client if not found."""
        session = self._sessions.get_session(session_id)
        if not session:
            await client.send(ErrorEvent(
                session_id=session_id,
                code="session_not_found",
                message="Session not found",
            ))
        return session

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------

    async def _handle_auth(self, client: Client, req: AuthRequest) -> None:
        if not self._auth_token:
            await client.send(AuthError(message="Gateway has no auth token configured"))
            logger.error("Auth rejected: GATEWAY_TOKEN is not set")
            await client.ws.close()
            return
        if not hmac.compare_digest(req.token, self._auth_token):
            await client.send(AuthError(message="Invalid token"))
            logger.warning("Auth failed for client %s", client.client_id[:8])
            await client.ws.close()
            return

        client.authenticated = True
        try:
            client.client_type = ClientType(req.client_type)
        except ValueError:
            client.client_type = ClientType.DISCORD
        client.metadata = req.client_metadata
        await client.send(AuthOk(client_id=client.client_id))
        logger.info("Client %s authenticated (type=%s)", client.client_id[:8], client.client_type.value)

    async def _handle_session_create(self, client: Client, req: SessionCreate) -> None:
        session = self._sessions.create_session(
            client_type=client.client_type or ClientType.DISCORD,
            client_metadata=req.metadata or client.metadata,
        )
        client.session_id = session.id
        await client.send(SessionCreated(session_id=session.id))

    async def _handle_session_resume(self, client: Client, req: SessionResume) -> None:
        session = await self._get_session_or_error(client, req.session_id)
        if not session:
            return

        if session.status == SessionStatus.EXPIRED:
            await client.send(ErrorEvent(
                session_id=req.session_id,
                code="session_expired",
                message="Session has expired — create a new one",
            ))
            return

        # Reactivate idle sessions
        if session.status == SessionStatus.IDLE:
            self._sessions.set_status(session.id, SessionStatus.ACTIVE)

        client.session_id = session.id
        self._sessions.update_activity(session.id)
        await client.send(SessionResumed(
            session_id=session.id,
            message_count=session.message_count,
        ))

    async def _handle_message(self, client: Client, req: UserMessage) -> None:
        session_id = req.session_id or client.session_id
        if not session_id:
            await client.send(ErrorEvent(code="no_session", message="No active session"))
            return

        session = await self._get_session_or_error(client, session_id)
        if not session:
            return

        # Reactivate idle sessions on message (matches _handle_session_resume)
        if session.status == SessionStatus.IDLE:
            self._sessions.set_status(session.id, SessionStatus.ACTIVE)
            self._sessions.update_activity(session.id)

        # Reject messages for sessions attached to a TUI client
        if session.attached_by:
            await client.send(ErrorEvent(
                session_id=session_id,
                code="session_attached",
                message="Session is attached to a TUI client",
            ))
            return

        # Per-session lock for message ordering
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())

        async with lock:
            await self._route_to_claude(client, session_id, session, req.content, req.attachments)

    async def _handle_cancel(self, client: Client, req: CancelRequest) -> None:
        session_id = req.session_id or client.session_id
        if session_id:
            await self._pool.cancel(session_id)

    # -----------------------------------------------------------------------
    # TUI session management
    # -----------------------------------------------------------------------

    async def _handle_session_list(self, client: Client, req: SessionList) -> None:
        sessions = self._sessions.get_listable_sessions()
        await client.send(SessionListOk(
            sessions=[
                {
                    "id": s.id,
                    "client_type": s.client_type.value,
                    "claude_session_id": s.claude_session_id,
                    "message_count": s.message_count,
                    "status": s.status.value,
                    "attached_by": s.attached_by,
                    "last_activity": s.last_activity,
                    "created_at": s.created_at,
                }
                for s in sessions
            ],
        ))

    async def _handle_session_attach(self, client: Client, req: SessionAttach) -> None:
        session = await self._get_session_or_error(client, req.session_id)
        if not session:
            return

        if session.attached_by and session.attached_by != client.client_id:
            await client.send(ErrorEvent(
                session_id=req.session_id,
                code="session_attached",
                message="Session is already attached to another TUI client",
            ))
            return

        # Kill gateway's claude process for this session — TUI will run its own
        await self._pool.kill_session(req.session_id)

        self._sessions.attach_session(req.session_id, client.client_id)
        await client.send(SessionAttachOk(
            session_id=session.id,
            claude_session_id=session.claude_session_id or "",
        ))

    async def _handle_session_detach(self, client: Client, req: SessionDetach) -> None:
        session = await self._get_session_or_error(client, req.session_id)
        if not session:
            return

        # Only the attaching client (or an unattached session) can detach
        if session.attached_by and session.attached_by != client.client_id:
            await client.send(ErrorEvent(
                session_id=req.session_id,
                code="not_owner",
                message="Session is attached to a different client",
            ))
            return

        self._sessions.detach_session(
            req.session_id,
            claude_session_id=req.claude_session_id or None,
        )
        await client.send(SessionDetachOk(session_id=session.id))

    # -----------------------------------------------------------------------
    # Claude routing
    # -----------------------------------------------------------------------

    async def _route_to_claude(
        self,
        client: Client,
        session_id: str,
        session: Any,
        content: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """Route a user message to the claude process and stream the response."""
        # Record user message — text + attachment metadata, no base64 blobs
        source = client.client_type.value if client.client_type else "unknown"
        history_content = content
        for att in (attachments or []):
            size_kb = len(att.get("data", "")) * 3 // 4 // 1024
            history_content += f"\n[attachment: {att.get('filename', 'file')}, {size_kb}KB]"
        self._sessions.add_message(session_id, "user", history_content, source)

        # Get or spawn claude process
        cp = self._pool.get_process(session_id)
        if not cp:
            context = self._context_fn() if self._context_fn else None
            try:
                cp = await self._pool.spawn(
                    session_id=session_id,
                    claude_session_id=session.claude_session_id,
                    append_prompt=context,
                )
                self._sessions.set_claude_info(
                    session_id,
                    claude_session_id=cp.claude_session_id,
                    claude_pid=cp.pid,
                )
            except RuntimeError as e:
                await client.send(ErrorEvent(
                    session_id=session_id,
                    code="spawn_failed",
                    message=str(e),
                ))
                return

        # Send message to claude
        start = time.time()
        try:
            await cp.send_message(content, attachments=attachments)
        except RuntimeError as e:
            await client.send(ErrorEvent(
                session_id=session_id,
                code="send_failed",
                message=str(e),
            ))
            await self._pool.kill_session(session_id)
            return

        # Stream response back to client
        full_response = []
        try:
            async for event in cp.read_response(hang_timeout=120):
                event_type = event.get("type")

                if event_type == "assistant":
                    # Extract text from assistant message content blocks
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block["text"]
                            full_response.append(text)
                            await client.send(ResponseChunk(
                                session_id=session_id,
                                content=text,
                            ))

                elif event_type == "result":
                    result_text = event.get("result", "")
                    if result_text and not full_response:
                        full_response.append(result_text)

                    duration_ms = int((time.time() - start) * 1000)
                    final_text = result_text or "".join(full_response)
                    await client.send(ResponseComplete(
                        session_id=session_id,
                        content=final_text,
                        duration_ms=duration_ms,
                    ))

                    # Record assistant message
                    self._sessions.add_message(session_id, "assistant", final_text)
                    self._sessions.increment_message_count(session_id)

                    # Update claude session ID from result
                    new_sid = event.get("session_id")
                    if new_sid and new_sid != cp.claude_session_id:
                        cp.claude_session_id = new_sid
                        self._sessions.set_claude_info(
                            session_id, claude_session_id=new_sid, claude_pid=cp.pid,
                        )

        except TimeoutError:
            await client.send(ErrorEvent(
                session_id=session_id,
                code="timeout",
                message="Claude process timed out — no output for 120s",
            ))
            await self._pool.kill_session(session_id)

        except RuntimeError as e:
            err_msg = str(e)
            # Check for TCC permission denial patterns
            code = "process_died"
            if "denied" in err_msg.lower() or "permission" in err_msg.lower():
                code = "permission_denied"
                err_msg += " — check System Settings > Privacy & Security"

            await client.send(ErrorEvent(
                session_id=session_id,
                code=code,
                message=err_msg,
            ))
            await self._pool.kill_session(session_id)
