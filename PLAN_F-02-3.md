# F-02.3 — BE Network Drop Handling / WebSocket Reconnect

## Changes from Previous Plan

1. **ACK-lost test corrected** — sender socket A must NOT consume/read the original `message_created` ACK before disconnecting. Simulates uncertain/lost ACK from client perspective, not TCP packet loss.

2. **DB session lifecycle clarified** — the `AsyncSession` is scoped to the WebSocket connection (injected via `Depends(get_db)`), reused for the full connection lifetime. Creating `ChatService(db)` per message does NOT create a new `AsyncSession`. Transactions are explicitly ended per operation using `commit()`/`rollback()`. No DB connection remains checked out while idle.

3. **Auth test corrected** — uses existing `authentication_required` error code (already used in `websocket.py` line 105). Asserts socket B cannot inherit socket A's identity without fresh auth.

4. **Endpoint format corrected** — WebSocket endpoint documented as `WS /api/v1/ws` not `GET /api/v1/ws`.

5. **ID roles clarified** — `message.id` (server-assigned) is canonical for history deduplication; `client_message_id` correlates local pending sends, retries, acknowledgements, and can reconcile pending messages with their canonical persisted counterpart.

6. **Test coverage table revised** — distinguishes implementation behavior (source code) from explicit test coverage.

---

## A. CURRENT STATE

### What reconnect/reliability behavior is already implemented by F-02.2

**1. ConnectionManager** (`src/services/connection_manager.py`):
- ✅ `connect(user_id, websocket)` — registers authenticated socket per user_id
- ✅ `disconnect(user_id, websocket)` — removes only the closed socket, preserves others
- ✅ `send_to_user()` — handles offline users as no-op (does nothing for offline)
- ✅ `send_to_users()` — fan-out to multiple users with user-level deduplication
- ✅ **Stale socket cleanup during send** — catches `OSError`/`RuntimeError`/`WebSocketDisconnect` in `send_to_user()` and calls `disconnect()` to remove broken socket
- ✅ **Multiple sockets per user** — stores as `dict[str, set[WebSocket]]`
- ✅ **Idempotent cleanup** — `disconnect()` is safe to call multiple times (`discard` handles missing)

**2. WebSocket endpoint** (`src/api/websocket.py`):
- ✅ **Re-authentication on every connection** — auth event required, JWT validated via `get_user_by_token()`
- ✅ **Auth timeout** — `AUTH_TIMEOUT_SECONDS = 10` closes socket without auth
- ✅ **Invalid/expired JWT rejection** — returns error and closes with 4401/4403
- ✅ **WebSocketDisconnect handling** — `finally` block calls `manager.disconnect()`
- ✅ **Malformed event handling** — JSON decode error returns error and continues
- ✅ **Clean session lifecycle** — DB session rolled back after auth, new `ChatService(db)` instance per message
- ✅ **Strict event schema** — `SendMessageEvent` has no `sender_id` field (prevents spoofing)

**3. ChatService** (`src/services/chat.py`):
- ✅ **Idempotent message send** — checks `client_message_id` before insert
- ✅ **Database uniqueness constraint** — `UniqueConstraint(sender_id, conversation_id, client_message_id)`
- ✅ **IntegrityError handling** — catches concurrent duplicate, looks up existing message, returns canonical
- ✅ **Text conflict detection** — same ID + different text raises `ClientMessageIdConflictError`
- ✅ **`created` flag** — prevents duplicate fan-out when resend returns existing message
- ✅ **`get_message_history()`** — returns recent messages in chronological order, limit 1-100

**4. REST API** (`src/api/routes.py`):
- ✅ `GET /api/v1/conversations/{id}/messages` — for missed message recovery

**5. Message persistence contract**:
- ✅ Fan-out only happens AFTER `db.commit()` — message durable before delivery
- ✅ `created=False` flag prevents duplicate fan-out on resend

### DB Session Lifecycle Verification

In `src/api/websocket.py`, the WebSocket endpoint uses FastAPI's `Depends(get_db)`:

```python
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),   # ← same AsyncSession for full connection
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    try:
        # Auth: uses the injected session
        user = await get_user_by_token(auth_event.token, db)
        await db.rollback()  # ← ends read transaction after auth
        await _send_event(websocket, AuthOkEvent(user_id=user_id))

        # Per-message: same session reused
        # ChatService(db) does NOT create a new AsyncSession
        while True:
            service = ChatService(db)
            result = await service.send_message(...)
            await db.commit()  # or rollback — explicit per operation
```

**Verified:**
- The `AsyncSession` is scoped to the WebSocket connection via `Depends(get_db)` — the same session is used for the full connection lifetime
- `ChatService(db)` does NOT create a new `AsyncSession`; it merely wraps the existing session
- Auth uses one transaction (then `rollback()`)
- Each `send_message` call uses explicit `commit()` or `rollback()` with no shared transaction state between calls
- No DB connection/transaction remains checked out while the socket is idle between messages

This is **already safe**. No backend change needed.

### Which requirements are already covered by tests

| Test | Covers Scenario |
|------|-----------------|
| `test_unauthenticated_socket_cannot_send_messages` | Scenario H (reconnect auth required) |
| `test_invalid_jwt_is_rejected_before_registration` | Scenario H (invalid token rejected) |
| `test_socket_authentication_times_out_without_registration` | Auth timeout |
| `test_valid_user_authenticates` | Clean auth flow |
| `test_member_send_persists_and_fans_out_to_direct_recipient` | Basic send/ack flow |
| `test_group_message_fans_out_to_every_other_member` | Multi-recipient fan-out |
| `test_offline_member_does_not_prevent_persistence_or_acknowledgement` | Scenario C (offline recipient) |
| `test_non_member_cannot_send_to_conversation` | Membership enforcement |
| `test_sender_id_spoof_is_rejected_and_socket_stays_usable` | Invariant 4 (no trust of client sender_id) |
| `test_malformed_event_returns_error_and_connection_continues` | Scenario G (malformed event) |
| `test_same_client_message_id_is_idempotent_but_text_conflicts_are_errors` | Scenarios D, E (duplicate resend, ID conflict) |
| `test_multiple_recipient_sockets_survive_other_tab_disconnect` | Scenario B (multiple tabs) |
| `test_disconnect_removes_only_the_closed_socket_for_a_user` | Scenario A (clean disconnect) |
| `test_failed_socket_is_removed_without_affecting_another_tab` | Scenario F (stale socket) |

---

## B. GAPS

### Backend gaps (F-02.3 responsibility)

**NONE identified.** After thorough inspection, F-02.2 already provides complete backend support for:

1. Stale socket removal during send
2. Multiple tabs per user
3. Offline recipients (no-op)
4. Idempotent resend with duplicate prevention
5. Re-authentication on reconnect
6. Message history recovery
7. One broken socket doesn't affect fan-out to others
8. Safe DB session/transaction handling — `AsyncSession` scoped to WebSocket connection, explicit `commit()`/`rollback()` per operation, no idle transaction leakage

### Frontend responsibilities (NOT in this repository)

The frontend (React/Next.js) must implement:
- Exponential backoff reconnection: 1s → 2s → 4s → 8s → capped at 30s
- Storing `client_message_id` locally for retry
- Fetching missed messages from `GET /conversations/{id}/messages` after reconnect
- Deduplicating via server `message.id`
- Resending locally-pending messages using the SAME `client_message_id`

### What F-02.3 will add

Since the backend logic is already complete, **F-02.3 adds**:
1. **Three end-to-end reconnect integration tests** — simulating real disconnect/reconnect with separate WebSocket connections
2. **Frontend reconnection contract documentation** — concise, with clear failure handling and bounded history note

---

## C. FILES

### Files inspected but NOT requiring changes

| File | Reason no change needed |
|------|-------------------------|
| `src/services/connection_manager.py` | Already handles stale socket cleanup during send, multiple tabs, idempotent disconnect |
| `src/services/chat.py` | Already handles idempotency, IntegrityError, text conflict, `created` flag |
| `src/schemas/chat.py` | Schema already supports all required events |
| `src/database/models.py` | Uniqueness constraint already exists on (sender_id, conversation_id, client_message_id) |
| `src/core/deps.py` | Token validation already works |
| `src/core/security.py` | JWT encode/decode already works |
| `src/api/routes.py` | Message history endpoint already exists |
| `src/main.py` | No changes needed |
| `src/api/websocket.py` | DB session lifecycle verified safe; explicit commit/rollback per operation |

### Files requiring modification

| File | Change |
|------|--------|
| `tests/test_api/test_websocket.py` | Add 3 end-to-end reconnect integration tests |

### New files

| File | Purpose |
|------|---------|
| `docs/RECONNECT_CONTRACT.md` | Frontend developer contract for reconnect behavior |

---

## D. IMPLEMENTATION STEPS

Since the backend logic is already complete, implementation focuses on **testing and documentation**.

### Step 1: Add end-to-end reconnect integration tests

**Why:** Existing tests cover component behavior, but we need explicit end-to-end tests simulating real reconnect scenarios with separate WebSocket connections.

**Behavior changes:** None (tests only)

**File:** `tests/test_api/test_websocket.py`

**Test 1: `test_ack_lost_reconnect_resend_returns_canonical_message_no_duplicate_fanout`**
- Socket A: authenticate as sender → send `client_message_id="abc"`
- Server persists the message
- Sender does NOT observe/consume the original `message_created` ACK (do not call `receive_json()`)
- Socket A disconnects
- Recipient may observe the original `message_received`
- Sender opens NEW socket B and authenticates
- Sender resends the same logical message with `client_message_id="abc"`
- Socket B receives `message_created` with existing server-assigned `message.id`
- Database: exactly 1 Message
- Recipient: receives no second `message_received`

**Test 2: `test_reconnect_requires_new_authentication`**
- Socket A: authenticate as user → disconnect
- Socket B: connect WITHOUT sending auth frame → send `send_message` → expect `error` code `authentication_required` → socket closed
- New socket cannot inherit authentication from old socket

**Test 3: `test_offline_recovery_via_rest_history`**
- Recipient: offline (no socket)
- Sender: authenticate → send message → `message_created` received
- Recipient: connect NEW socket → authenticate → receive `auth_ok`
- Recipient: GET `/api/v1/conversations/{id}/messages`
- History contains the offline message with server-assigned `message.id`
- Recovery/deduplication uses `message.id`

### Step 2: Create frontend reconnect contract documentation

**Why:** Frontend developers need clear documentation of the reconnection contract, retry behavior, and MVP limitations.

**File:** `docs/RECONNECT_CONTRACT.md`

**Content:**
- Reconnection sequence with exponential backoff
- Auth failure handling (stop retry, refresh credentials)
- Business errors do NOT automatically stop reconnecting
- Missed message recovery via REST
- Idempotent resend using client_message_id
- Deduplication using server message.id
- **MVP Limitation:** message history bounded to max 100 messages — no cursor/pagination/replay infrastructure

---

## E. TEST PLAN

### F-02.2 Component Coverage (existing tests)

| Scenario | Explicitly Tested By | Behavior In Code |
|----------|---------------------|-----------------|
| Clean disconnect removes socket | `test_disconnect_removes_only_the_closed_socket_for_a_user` | `ConnectionManager.disconnect()` |
| Multiple tabs survive disconnect | `test_multiple_recipient_sockets_survive_other_tab_disconnect` | `ConnectionManager._connections` uses `set` |
| Offline recipient safe | `test_offline_member_does_not_prevent_persistence_or_acknowledgement` | `send_to_user()` is no-op for missing user |
| Stale socket removed during send | `test_failed_socket_is_removed_without_affecting_another_tab` | `send_to_user()` catches exceptions and calls `disconnect()` |
| Duplicate resend idempotent | `test_same_client_message_id_is_idempotent_but_text_conflicts_are_errors` | `ChatService._find_message_by_client_message_id()` |
| DB IntegrityError handled | (not explicitly tested end-to-end) | `ChatService.send_message()` IntegrityError block |
| `created=False` prevents fanout | (implementation behavior, not explicitly tested) | `websocket.py` line 208: `if result.created` |
| Auth required on connect | `test_unauthenticated_socket_cannot_send_messages` | `websocket.py` requires first frame type=auth |
| Invalid JWT rejected | `test_invalid_jwt_is_rejected_before_registration` | `websocket.py` calls `get_user_by_token()` |
| Auth timeout | `test_socket_authentication_times_out_without_registration` | `websocket.py` `asyncio.wait_for(timeout=AUTH_TIMEOUT_SECONDS)` |
| Malformed event safe | `test_malformed_event_returns_error_and_connection_continues` | `websocket.py` catches JSON decode errors and ValidationError |
| Text conflict error | `test_same_client_message_id_is_idempotent_but_text_conflicts_are_errors` | `ChatService._raise_if_text_conflicts()` |
| DB session safe during idle | (implementation behavior) | Explicit `rollback()` after auth; per-message `commit()`/`rollback()` |
| No auth inheritance between sockets | `test_unauthenticated_socket_cannot_send_messages` | Auth state not stored in ConnectionManager |

### F-02.3 New End-to-End Reconnect Coverage

| Test | What It Proves | File |
|------|----------------|------|
| `test_ack_lost_reconnect_resend_returns_canonical_message_no_duplicate_fanout` | Real reconnect with separate socket B; sender does not consume original ACK on socket A; idempotent resend returns canonical message; recipient receives no second fan-out | `tests/test_api/test_websocket.py` |
| `test_reconnect_requires_new_authentication` | New socket B cannot send without fresh auth frame; `authentication_required` error proves no auth inheritance from socket A | `tests/test_api/test_websocket.py` |
| `test_offline_recovery_via_rest_history` | Offline message persisted during sender's send; recipient reconnects on new socket and authenticates; REST history contains offline message with server `message.id`; recovery uses `message.id` for deduplication | `tests/test_api/test_websocket.py` |

---

## F. FRONTEND HANDOFF CONTRACT

### docs/RECONNECT_CONTRACT.md

```markdown
# WebSocket Reconnect Contract — CHAT-03

## Connection Failure Handling

### Network / Server Drop
- Retry with exponential backoff: 1s → 2s → 4s → 8s → cap at 30s
- On each reconnect, open a new WebSocket and authenticate again

### Authentication Failure (auth_ok never received after auth frame)
- **Stop the reconnect loop immediately**
- Refresh credentials or prompt user to re-login
- Do NOT continue retrying with the same token

### Business Errors (conversation_not_found, not_conversation_member, client_message_id_conflict, etc.)
- These are application errors, not connection failures
- The socket remains usable after business errors
- Continue retrying if appropriate for the use case (but handle conflict appropriately)

## Reconnection Sequence

1. Connection lost
2. Retry with backoff: 1s → 2s → 4s → 8s → cap 30s
3. Open new WebSocket: `WS /api/v1/ws`
4. Send auth: `{ "type": "auth", "token": "<jwt>" }`
5. Wait for: `{ "type": "auth_ok", "user_id": "..." }`
   - If auth error: stop retry and refresh credentials
6. For each conversation: `GET /api/v1/conversations/{id}/messages?limit=50`
7. Deduplicate using server-assigned `message.id`
8. Resend pending messages with the SAME `client_message_id`

## Message Recovery

### Missed Messages
- After reconnect, fetch history: `GET /api/v1/conversations/{id}/messages?limit=50`
- Deduplicate using **server `message.id`** (the canonical identifier assigned on persist)
- **Maximum 100 messages per request**; newest messages returned last

### Pending Message Resend
- Store `client_message_id` locally for messages without `message_created` acknowledgment
- After reconnect/auth, resend with the SAME `client_message_id`
- Same ID + same text → returns existing `message_created` (no duplicate fanout)
- Same ID + different text → returns `client_message_id_conflict` error
- `client_message_id` also lets the client reconcile a locally pending message with its canonical persisted server message

### Idempotency Key
`(sender_id, conversation_id, client_message_id)`

### ID Roles Summary
| ID | Owner | Purpose |
|----|-------|---------|
| `message.id` | Server | Canonical identifier for persisted/history messages; use for deduplication |
| `client_message_id` | Client | Correlates local pending sends, retries, and acknowledgements; idempotency key |

## MVP Limitation

Message history is bounded to a recent window (max 100 messages per request).
This mechanism does **NOT** guarantee recovery of arbitrarily large backlogs
after a long offline period.

Cursor/pagination/replay infrastructure is out of scope for MVP.
If a user is offline for an extended period, older messages beyond the 100-message
window cannot be recovered through the reconnect mechanism.

## WebSocket Events

### Endpoint
`WS /api/v1/ws`

### Client → Server
```json
{ "type": "auth", "token": "<jwt>" }
{ "type": "send_message", "client_message_id": "...", "conversation_id": "...", "text": "..." }
```

### Server → Client
```json
{ "type": "auth_ok", "user_id": "..." }
{ "type": "message_created", "client_message_id": "...", "message": { "id": "...", "conversation_id": "...", "sender_id": "...", "original_text": "...", "created_at": "..." } }
{ "type": "message_received", "message": { ... } }
{ "type": "error", "code": "...", "message": "..." }
```

### Error Codes
| Code | Meaning | Retry? |
|------|---------|--------|
| `authentication_required` | Auth frame not sent | Stop, refresh auth |
| `authentication_failed` | Invalid/expired token | Stop, refresh auth |
| `authentication_timeout` | Auth not received in time | Retry connect |
| `conversation_not_found` | Invalid conversation ID | Check conversation list |
| `not_conversation_member` | User not in conversation | Check membership |
| `client_message_id_conflict` | Same ID, different text | Handle conflict |
| `internal_error` | Server error | Retry may help |
| `invalid_event` | Malformed event | Fix event format |
```
```

---

## G. RISKS / ASSUMPTIONS

### Known limitations

1. **Single-process only** — `ConnectionManager` is an in-memory `dict`. In a multi-process deployment (e.g., Gunicorn with multiple workers), a user's sockets may be distributed across processes. This is acceptable for MVP.

2. **No application-level heartbeat** — Relying on ASGI/WebSocket transport ping/pong. For this MVP, this is acceptable. Production would add application-level heartbeat for faster dead-connection detection.

3. **No delivery receipts** — The server does not track whether a message was successfully delivered to each recipient. Messages are durable in DB regardless of realtime delivery success.

4. **Bounded message history** — Max 100 messages per GET request. Long offline periods may miss older messages. No cursor/pagination in MVP.

5. **JWT expiration** — If the JWT expires while the WebSocket is connected, the socket remains open. The client should handle token refresh and reconnect when needed.

### Assumptions

1. Frontend will store `client_message_id` locally for retry scenarios
2. Frontend will implement exponential backoff reconnection
3. Frontend will fetch message history after reconnect before resuming send
4. The current `GET /conversations/{id}/messages` endpoint is sufficient for MVP recovery
5. Server-assigned `message.id` is used for deduplication, not `client_message_id`

### Clarification needed

None — the current implementation satisfies all F-02.3 requirements.

---

## H. SCOPE CHECK

### Confirmed OUT of scope (not added)

- ❌ Redis / queues / message brokers
- ❌ LangGraph / translation logic
- ❌ Custom E2E encryption
- ❌ Custom heartbeat protocol
- ❌ Presence / online status
- ❌ Read receipts / typing indicators
- ❌ Unread counts / notification system
- ❌ Cursor / pagination / replay infrastructure
- ❌ Celery / Kafka / pub/sub
- ❌ Any unrelated refactors

### Confirmed IN scope

- ✅ 3 end-to-end reconnect integration tests (real disconnect/reconnect with separate WebSocket connections)
- ✅ `docs/RECONNECT_CONTRACT.md` (concise, with bounded history limitation clearly documented)

---

## Summary

F-02.2 already implements complete backend support for network drop handling and WebSocket reconnection. The idempotency, stale socket cleanup, multiple tabs, offline handling, re-authentication, and safe per-operation DB session/transaction handling are all satisfied by existing code. The `AsyncSession` is scoped to the WebSocket connection (injected via `Depends(get_db)`) and reused for the full connection lifetime, with explicit `commit()`/`rollback()` per auth and per-message operation — no transaction remains checked out while idle.

**F-02.3 adds only:**
1. 3 integration tests simulating real reconnect scenarios with separate WebSocket connections
2. Frontend reconnection contract documentation with clear failure handling and MVP limitations

**No backend code changes are required.**
