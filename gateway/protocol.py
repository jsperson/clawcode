"""Wire protocol message types for gateway ↔ client communication.

All messages are JSON-serializable dataclasses. Clients send Request types,
gateway sends Response/Event types. Messages are newline-delimited JSON over WebSocket.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClientType(str, Enum):
    DISCORD = "discord"
    TUI = "tui"
    SCHEDULE = "schedule"
    ONESHOT = "oneshot"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Client → Gateway messages
# ---------------------------------------------------------------------------


@dataclass
class AuthRequest:
    """Client authenticates with a shared secret token."""

    type: str = field(default="auth", init=False)
    token: str = ""
    client_type: str = "discord"  # ClientType value
    client_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionCreate:
    """Client requests a new session."""

    type: str = field(default="session.create", init=False)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionResume:
    """Client resumes an existing session."""

    type: str = field(default="session.resume", init=False)
    session_id: str = ""


@dataclass
class UserMessage:
    """Client sends a message to their session's claude process."""

    type: str = field(default="message", init=False)
    session_id: str = ""
    content: str = ""


@dataclass
class CancelRequest:
    """Client requests cancellation of the current claude response."""

    type: str = field(default="cancel", init=False)
    session_id: str = ""


@dataclass
class SessionList:
    """Client requests list of active/idle sessions."""

    type: str = field(default="session.list", init=False)


@dataclass
class SessionAttach:
    """TUI client claims a session — gateway kills its claude process."""

    type: str = field(default="session.attach", init=False)
    session_id: str = ""


@dataclass
class SessionDetach:
    """TUI client releases a session, passes back claude_session_id."""

    type: str = field(default="session.detach", init=False)
    session_id: str = ""
    claude_session_id: str = ""  # Updated ID from interactive claude run


# ---------------------------------------------------------------------------
# Gateway → Client messages
# ---------------------------------------------------------------------------


@dataclass
class AuthOk:
    """Authentication succeeded."""

    type: str = field(default="auth.ok", init=False)
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AuthError:
    """Authentication failed."""

    type: str = field(default="auth.error", init=False)
    message: str = ""


@dataclass
class SessionCreated:
    """A new session was created."""

    type: str = field(default="session.created", init=False)
    session_id: str = ""


@dataclass
class SessionResumed:
    """An existing session was resumed."""

    type: str = field(default="session.resumed", init=False)
    session_id: str = ""
    message_count: int = 0


@dataclass
class ResponseChunk:
    """A partial response chunk from claude (streaming)."""

    type: str = field(default="chunk", init=False)
    session_id: str = ""
    content: str = ""


@dataclass
class ResponseComplete:
    """A complete response from claude."""

    type: str = field(default="response", init=False)
    session_id: str = ""
    content: str = ""
    duration_ms: int = 0


@dataclass
class ErrorEvent:
    """An error occurred."""

    type: str = field(default="error", init=False)
    session_id: str = ""
    code: str = ""  # timeout, process_died, permission_denied, etc.
    message: str = ""


@dataclass
class PushEvent:
    """A pushed event (schedule output, lifecycle, etc.)."""

    type: str = field(default="push", init=False)
    source: str = ""  # schedule, lifecycle, system
    task: str = ""  # schedule task name, or event name
    content: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionListOk:
    """Response with list of active/idle sessions."""

    type: str = field(default="session.list.ok", init=False)
    sessions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SessionAttachOk:
    """Session successfully attached to TUI client."""

    type: str = field(default="session.attach.ok", init=False)
    session_id: str = ""
    claude_session_id: str = ""


@dataclass
class SessionDetachOk:
    """Session successfully detached from TUI client."""

    type: str = field(default="session.detach.ok", init=False)
    session_id: str = ""


@dataclass
class LifecycleEvent:
    """Gateway lifecycle event."""

    type: str = field(default="lifecycle", init=False)
    event: str = ""  # gateway.starting, gateway.stopping, session.expired


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def to_dict(msg: Any) -> dict[str, Any]:
    """Convert a protocol message to a JSON-serializable dict."""
    import dataclasses

    result = {}
    for f in dataclasses.fields(msg):
        v = getattr(msg, f.name)
        if isinstance(v, Enum):
            result[f.name] = v.value
        else:
            result[f.name] = v
    return result


# Map of type string → dataclass for deserialization
_REQUEST_TYPES: dict[str, type] = {
    "auth": AuthRequest,
    "session.create": SessionCreate,
    "session.resume": SessionResume,
    "message": UserMessage,
    "cancel": CancelRequest,
    "session.list": SessionList,
    "session.attach": SessionAttach,
    "session.detach": SessionDetach,
}


def parse_request(
    data: dict[str, Any],
) -> AuthRequest | SessionCreate | SessionResume | UserMessage | CancelRequest | SessionList | SessionAttach | SessionDetach:
    """Parse a JSON dict into a typed request object.

    Raises:
        ValueError: If the message type is unknown or missing.
    """
    msg_type = data.get("type")
    if not msg_type or msg_type not in _REQUEST_TYPES:
        raise ValueError(f"Unknown message type: {msg_type}")

    cls = _REQUEST_TYPES[msg_type]
    # Build kwargs from dataclass fields, using data values where present
    kwargs = {}
    for f in cls.__dataclass_fields__:
        if f == "type":
            continue
        if f in data:
            kwargs[f] = data[f]
    return cls(**kwargs)
