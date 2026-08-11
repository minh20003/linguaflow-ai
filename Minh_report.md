# Minh Implementation Report

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
