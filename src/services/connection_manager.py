"""In-memory management of authenticated WebSocket connections."""

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    """Track live sockets by user without owning application business logic.

    This manager intentionally has no database or authorization dependency.  A
    WebSocket endpoint authenticates and accepts a socket before registering it
    here, then supplies already-authorized recipient user IDs for fan-out.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    @property
    def connections(self) -> dict[str, set[WebSocket]]:
        """Expose the live-connection mapping for narrow operational inspection."""
        return self._connections

    def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Register an already accepted, authenticated socket for ``user_id``."""
        self._connections.setdefault(user_id, set()).add(websocket)

    def register(self, user_id: str, websocket: WebSocket) -> None:
        """Alias for :meth:`connect` that emphasizes registration semantics."""
        self.connect(user_id, websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove only ``websocket``, preserving any other sockets for the user."""
        sockets = self._connections.get(user_id)
        if sockets is None:
            return

        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    def is_online(self, user_id: str) -> bool:
        """Whether ``user_id`` currently holds at least one live socket."""
        return bool(self._connections.get(user_id))

    def online_user_ids(self, candidates: Iterable[str]) -> tuple[str, ...]:
        """Filter ``candidates`` down to those with a live socket, order kept."""
        return tuple(user_id for user_id in candidates if self.is_online(user_id))

    async def send_to_user(self, user_id: str, event: Mapping[str, Any]) -> None:
        """Deliver an event to every live socket for one user.

        Offline users are deliberately a no-op.  A socket that has disconnected
        while an event is being sent is removed without affecting the user's
        remaining sockets or delivery to any other recipient.
        """
        for websocket in tuple(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(dict(event))
            except (OSError, RuntimeError, WebSocketDisconnect):
                self.disconnect(user_id, websocket)

    async def send_to_users(self, user_ids: Iterable[str], event: Mapping[str, Any]) -> None:
        """Deliver an event to each distinct user ID in ``user_ids``."""
        delivered_to: set[str] = set()
        for user_id in user_ids:
            if user_id in delivered_to:
                continue
            delivered_to.add(user_id)
            await self.send_to_user(user_id, event)
