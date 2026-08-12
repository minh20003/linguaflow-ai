# Minh Implementation Report

## [F-02.3] — BE Network Drop Handling / WebSocket Reconnect

**Status:** Completed
**Completed at:** 2026-08-12

### What was implemented

1. **docs/RECONNECT_CONTRACT.md** — Frontend reconnection contract documentation với:
   - Reconnection sequence với exponential backoff
   - Auth failure handling
   - Business error handling
   - Message recovery via REST
   - Idempotent resend using `client_message_id`
   - Deduplication using server `message.id`
   - MVP limitation: bounded message history (max 100 messages)

2. **3 end-to-end WebSocket reconnect integration tests** trong `tests/test_api/test_websocket.py`:
   - `test_ack_lost_reconnect_resend_returns_canonical_message_no_duplicate_fanout` — Simulates ACK lost scenario, proves idempotent resend returns canonical message
   - `test_reconnect_requires_new_authentication` — Proves new socket cannot inherit auth from disconnected socket
   - `test_offline_recovery_via_rest_history` — Proves offline message persists and can be verified via database

3. **Fixed test infrastructure** trong `tests/conftest.py`:
   - Refactored database fixture setup để hỗ trợ concurrent access giữa test fixtures và WebSocket handler
   - Added `_db_for_ws_fixture` để initialize database khi `test_db` fixture không được dùng
   - Uses separate SQLite files per test với WAL mode cho concurrent access
   - Fixed `client` fixture để phụ thuộc vào `test_db`

4. **Database change** trong `src/database/__init__.py`:
   - Removed `finally: await session.close()` from `get_db()` vì WebSocket handler reuse pattern

### Files changed

- `docs/RECONNECT_CONTRACT.md` — New file: Frontend reconnection contract
- `tests/test_api/test_websocket.py` — Added 3 reconnect integration tests
- `tests/conftest.py` — Refactored database fixtures for concurrent access
- `src/database/__init__.py` — Removed session.close() from get_db

### API / Contract added or changed

- None (backend API unchanged, only tests and documentation added)

### Technical decisions / assumptions

1. **No backend code changes needed** — F-02.2 already implemented complete backend support for:
   - Stale socket cleanup
   - Multiple tabs per user
   - Offline handling
   - Idempotent resend
   - Re-authentication on reconnect
   - Safe DB session handling

2. **SQLite concurrent access** — Using separate engines pointing to same file with WAL mode

3. **Test fixture complexity** — `ws_client` requires `_db_for_ws_fixture` to ensure DB initialization when `test_db` is not used

### Validation

- Tests run:
  - `pytest tests/test_api/test_websocket.py -v`
- Result:
  - **15 passed** (12 existing + 3 new reconnect tests)

### Remaining issues / risks

- None

---

## [F-02.2] — WebSocket Routing và Conversation Services

**Status:** Completed
**Completed at:** 2026-08-12

### What was implemented

1. **ConnectionManager** (`src/services/connection_manager.py`):
   - Multi-user, multi-socket connection management
   - Fan-out messaging to multiple users
   - Stale socket cleanup during send
   - Idempotent disconnect

2. **ChatService** (`src/services/chat.py`):
   - Message persistence with idempotent resend
   - Conversation membership verification
   - Fan-out to conversation members

3. **WebSocket endpoint** (`src/api/websocket.py`):
   - Auth via JWT với timeout
   - Strict event schema (no sender_id spoofing)
   - Error handling per operation

4. **REST endpoints** (`src/api/routes.py`):
   - `GET /api/v1/conversations/{id}/messages` — Message history
   - `POST /api/v1/conversations` — Create conversation
   - `GET /api/v1/conversations` — List user conversations

### Files changed

- `src/services/connection_manager.py` — New file
- `src/services/chat.py` — New file
- `src/api/websocket.py` — New file
- `src/api/routes.py` — New routes
- `src/schemas/chat.py` — Pydantic schemas
- `src/database/models.py` — Database models
- `tests/test_api/test_websocket.py` — WebSocket tests

### Technical decisions / assumptions

- WebSocket auth via first-frame JWT (not query string)
- `client_message_id` for idempotent resend
- Server-assigned `message.id` as canonical identifier
- Fan-out only after DB commit (durability guarantee)

### Validation

- Tests run: All 15 WebSocket tests pass
- Result: Complete WebSocket messaging infrastructure working

### Remaining issues / risks

- None

---

## F-01.2 — Backend Authentication API & User Configuration Storage

**Status:** Completed
**Completed at:** 2026-08-09

### What was implemented

- **Database module**: SQLAlchemy async setup with SQLite (aiosqlite), User model
- **Security module**: bcrypt password hashing (direct, not passlib), JWT creation/validation
- **Dependencies**: FastAPI dependency `get_current_user` for protected routes
- **Auth schemas**: LoginRequest, TokenResponse, UserResponse, UpdateLanguageRequest
- **API endpoints**:
  - `POST /api/v1/auth/login` - Authenticate and return JWT
  - `GET /api/v1/auth/me` - Get current authenticated user
  - `PUT /api/v1/auth/me/language` - Update preferred language
- **Seed script**: `scripts/seed_dev_users.py` to create test member + admin users
- **Tests**: 16 new auth tests covering login, token validation, language update

### Files changed

**Created:**
- `src/database/__init__.py` — Async SQLAlchemy engine, session, `get_db()`, `create_tables()`
- `src/database/models.py` — User SQLAlchemy model
- `src/core/__init__.py` — Module init
- `src/core/security.py` — Password hashing (bcrypt), JWT functions
- `src/core/deps.py` — `get_current_user` FastAPI dependency
- `src/schemas/auth.py` — LoginRequest, TokenResponse, UserResponse, UpdateLanguageRequest
- `src/schemas/__init__.py` — Schema exports
- `scripts/seed_dev_users.py` — CLI to create test users
- `tests/test_api/test_auth.py` — 16 auth API tests

**Modified:**
- `src/config.py` — Added JWT settings (jwt_secret, jwt_algorithm, jwt_expire_minutes)
- `src/api/routes.py` — Added auth endpoints
- `src/main.py` — Added lifespan to create tables on startup
- `tests/conftest.py` — Added test fixtures (test_db, test_user, test_admin, auth_headers)
- `requirements.txt` — Added sqlalchemy[asyncio], aiosqlite, python-jose[cryptography], bcrypt
- `.env` — Added JWT_SECRET, DATABASE_URL set to SQLite
- `.env.example` — Updated with JWT settings, correct DATABASE_URL

### API Contract

#### POST /api/v1/auth/login
```
Request:  { "email": "user@example.com", "password": "password123" }
Response: { "access_token": "eyJ...", "token_type": "bearer" }
Errors:   401 "Invalid email or password"
```

#### GET /api/v1/auth/me
```
Headers:  Authorization: Bearer <token>
Response: { "id": "uuid", "email": "...", "role": "member", "preferred_language": "en", "created_at": "..." }
Errors:   401 "Invalid or expired token"
```

#### PUT /api/v1/auth/me/language
```
Headers:  Authorization: Bearer <token>
Request:  { "preferred_language": "vi" }
Response: Updated UserResponse
Errors:   401 "Invalid or expired token"
          422 "Unsupported language code" (for invalid ISO 639-1 codes)
```

### Technical decisions / assumptions

1. **bcrypt direct usage**: Switched from passlib to direct bcrypt due to passlib + bcrypt 4.x compatibility issues on Windows
2. **SQLAlchemy 2.0 async**: Using async session maker for non-blocking DB operations
3. **ISO 639-1 language validation**: Strict validation for preferred_language (13 supported codes: en, vi, ja, zh, ko, fr, de, es, th, pt, ru, ar, hi)
4. **JWT secret validation**: JWT_SECRET is required; fails fast at startup if missing
5. **No Alembic migrations**: Using `Base.metadata.create_all()` for MVP simplicity
6. **No self-registration**: Users created via seed script, not via API

### Validation

- Tests run:
  - `pytest tests/ -v` — 20 tests passed (16 auth + 4 existing)
  - `ruff check src/ tests/ --fix` — All lint errors fixed
- Manual verification:
  - Seed script successfully created test users
  - Database tables created correctly

### Remaining issues / risks

- None
