"""WebSocket transport for realtime chat events."""

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect

from src.core.deps import get_user_by_token
from src.database import get_db
from src.schemas.chat import (
    AuthEvent,
    AuthOkEvent,
    ErrorEvent,
    MessageCreatedEvent,
    MessageReceivedEvent,
    RealtimeMessage,
    SendMessageEvent,
)
from src.services.chat import (
    ChatService,
    ClientMessageIdConflictError,
    ConversationMembershipError,
    ConversationNotFoundError,
)
from src.services.connection_manager import ConnectionManager

AUTH_TIMEOUT_SECONDS = 10

router = APIRouter()
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Provide the single-process connection manager for dependency overrides."""
    return connection_manager


async def _send_event(websocket: WebSocket, event: BaseModel) -> None:
    """Serialize a typed event into a JSON-safe WebSocket payload."""
    await websocket.send_json(event.model_dump(mode="json"))


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    """Send a structured application error without exposing internal details."""
    await _send_event(websocket, ErrorEvent(code=code, message=message))


async def _send_error_and_close(
    websocket: WebSocket,
    code: str,
    message: str,
    close_code: int,
) -> None:
    """Best-effort error response before closing an unauthenticated socket."""
    try:
        await _send_error(websocket, code, message)
        await websocket.close(code=close_code)
    except (OSError, RuntimeError, WebSocketDisconnect):
        return


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    """Authenticate a socket, persist messages, then fan them out to members."""
    await websocket.accept()
    user_id: str | None = None

    try:
        try:
            initial_event = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=AUTH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            await _send_error_and_close(
                websocket,
                "authentication_timeout",
                "Authentication was not received in time",
                4401,
            )
            return
        except json.JSONDecodeError:
            await _send_error_and_close(
                websocket,
                "authentication_failed",
                "The first event must be a valid auth event",
                4401,
            )
            return
        except WebSocketDisconnect:
            return

        if not isinstance(initial_event, dict) or initial_event.get("type") != "auth":
            await _send_error_and_close(
                websocket,
                "authentication_required",
                "The first event must be an auth event",
                4401,
            )
            return

        try:
            auth_event = AuthEvent.model_validate(initial_event)
        except ValidationError:
            await _send_error_and_close(
                websocket,
                "authentication_failed",
                "The auth event is invalid",
                4401,
            )
            return

        try:
            user = await get_user_by_token(auth_event.token, db)
        except SQLAlchemyError:
            await db.rollback()
            await _send_error_and_close(
                websocket,
                "internal_error",
                "Authentication could not be completed",
                1011,
            )
            return

        if user is None:
            await db.rollback()
            await _send_error_and_close(
                websocket,
                "authentication_failed",
                "Invalid or expired token",
                4401,
            )
            return

        user_id = user.id
        # The WebSocket dependency lives for the full connection. End the read
        # transaction now so an idle authenticated socket does not retain it.
        await db.rollback()
        await _send_event(websocket, AuthOkEvent(user_id=user_id))
        manager.connect(user_id, websocket)

        while True:
            try:
                raw_event = await websocket.receive_json()
            except json.JSONDecodeError:
                await _send_error(websocket, "invalid_event", "Event must be valid JSON")
                continue

            if not isinstance(raw_event, dict) or raw_event.get("type") != "send_message":
                await _send_error(websocket, "invalid_event", "Unsupported event type")
                continue

            try:
                event = SendMessageEvent.model_validate(raw_event)
            except ValidationError:
                await _send_error(websocket, "invalid_event", "The send_message event is invalid")
                continue

            service = ChatService(db)
            try:
                result = await service.send_message(
                    sender_id=user_id,
                    conversation_id=event.conversation_id,
                    client_message_id=event.client_message_id,
                    text=event.text,
                )
            except ConversationNotFoundError:
                await db.rollback()
                await _send_error(websocket, "conversation_not_found", "Conversation was not found")
                continue
            except ConversationMembershipError:
                await db.rollback()
                await _send_error(
                    websocket,
                    "not_conversation_member",
                    "You are not a member of this conversation",
                )
                continue
            except ClientMessageIdConflictError:
                await db.rollback()
                await _send_error(
                    websocket,
                    "client_message_id_conflict",
                    "client_message_id was already used for different text",
                )
                continue
            except SQLAlchemyError:
                await db.rollback()
                await _send_error(websocket, "internal_error", "Message could not be persisted")
                continue

            realtime_message = RealtimeMessage.model_validate(result.message)
            await manager.send_to_user(
                user_id,
                MessageCreatedEvent(
                    client_message_id=event.client_message_id,
                    message=realtime_message,
                ).model_dump(mode="json"),
            )
            if result.created:
                await manager.send_to_users(
                    result.recipient_ids,
                    MessageReceivedEvent(message=realtime_message).model_dump(mode="json"),
                )
    except WebSocketDisconnect:
        return
    finally:
        if user_id is not None:
            manager.disconnect(user_id, websocket)
