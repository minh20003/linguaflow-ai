"""API routes for the application."""

import asyncio
import logging
import mimetypes
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import get_connection_manager
from src.config import get_settings
from src.core.crypto import encrypt as encrypt_secret
from src.core.deps import get_current_user, get_user_by_token
from src.core.rate_limit import llm_limit
from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from src.database import get_db
from src.database.models import (
    AGENT_CONSENT_POLICY_VERSION,
    ActionProposal,
    Attachment,
    BlockedUser,
    CalendarEvent,
    CalendarLink,
    CallSession,
    Conversation,
    Feedback,
    PasswordResetToken,
    RefreshSession,
    TranslationResult,
    User,
)
from src.schemas.agent_consent import (
    AgentConsentEntry,
    AgentConsentsResponse,
    AgentConsentsUpdate,
)
from src.schemas.auth import (
    SUPPORTED_LANGUAGES,
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TimezoneUpdate,
    UpdateInterfaceLanguageRequest,
    UpdateLanguageRequest,
    UserResponse,
)
from src.schemas.calendar import (
    CalendarCapabilityResponse,
    CalendarEventCreateRequest,
    CalendarEventResponse,
    CalendarEventUpdateRequest,
    CalendarLinkResponse,
    CalendarSyncResultResponse,
    GoogleAuthorizeResponse,
    GoogleCalendarCallbackRequest,
    ReminderResponse,
)
from src.schemas.chat import (
    AttachmentResponse,
    ConversationCreateRequest,
    ConversationMemberSummary,
    ConversationResponse,
    EditMessageRequest,
    FeedbackRequest,
    FeedbackResponse,
    MessageDeletedEvent,
    MessageHistoryResponse,
    MessageReactionSummary,
    MessageReactionsUpdatedEvent,
    MessageReadEvent,
    MessageResponse,
    MessageUpdatedEvent,
    ReadReceiptResponse,
    TranslationEditRequest,
    TranslationEditResponse,
    TranslationEditSummary,
    TranslationSummary,
    VoiceTranscriptionRetryResponse,
)
from src.schemas.intelligence import (
    ActionProposalResponse,
    ClarificationAnalysisResponse,
    ClarifyProposalRequest,
    ConfirmProposalRequest,
    ConversationSummaryRequest,
    ConversationSummaryResponse,
)
from src.services.action_proposals import (
    ActionProposalNotFoundError,
    ActionProposalOwnershipError,
    ActionProposalService,
    ActionProposalStatusError,
)
from src.services.agent_consent import (
    get_consents,
    has_consent,
    require_consent,
    set_consents,
)
from src.services.attachment_storage import (
    AttachmentStorage,
    AttachmentStorageError,
    AttachmentStorageNotFoundError,
)
from src.services.blocking import (
    DirectMessagingBlockedError,
    block_user,
    list_blocked_user_ids,
    unblock_user,
)
from src.services.calendar import (
    CalendarEventNotFoundError,
    CalendarEventReadOnlyError,
    CalendarService,
)
from src.services.calendar_push import schedule_calendar_push
from src.services.chat import (
    ChatService,
    ChatServiceError,
    ConversationMembershipError,
    ConversationNotFoundError,
    ConversationValidationError,
    MessageAlreadyDeletedError,
    MessageNotFoundError,
    MessageOwnershipError,
    ReferencedUsersNotFoundError,
    TranslationNotFoundError,
    VoiceTranscriptionRetryAttachmentError,
    VoiceTranscriptionRetryStateError,
    decode_message_cursor,
    encode_message_cursor,
    message_mentions,
)
from src.services.connection_manager import ConnectionManager
from src.services.conversation_intelligence import ConversationIntelligenceService
from src.services.correction_log import schedule_correction_record
from src.services.customization import resolve_conversation_profile
from src.services.display_language import render, render_many
from src.services.email import (
    EmailDeliveryError,
    send_password_reset_email,
    send_registration_otp_email,
)
from src.services.google_auth import GoogleAuthError, GoogleUserInfo, verify_google_token
from src.services.google_calendar import (
    GoogleCalendarError,
    GoogleCalendarNotLinkedError,
    build_authorization_url,
    exchange_code,
    is_configured_for_calendar,
    sync_user,
)
from src.services.profiles import (
    profile_for,
    resolve_profiles,
    resolve_profiles_for_conversations,
    select_for_reader,
)
from src.services.rtc import (
    CallJoin,
    CallNotFoundError,
    CallService,
    CallStateError,
    RTCProviderUnavailableError,
    get_rtc_provider,
)
from src.services.translation import schedule_translation_retry, schedule_translations
from src.services.user_settings import get_or_create_user_settings, update_user_settings
from src.services.voice_transcription import schedule_voice_transcription

logger = logging.getLogger(__name__)

router = APIRouter()

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_MAX_FILENAME_LENGTH = 120


def _safe_filename(filename: str | None) -> str:
    """Keep a human-readable filename while preventing path traversal."""
    name = Path(filename or "attachment").name
    name = _SAFE_FILENAME.sub("_", name).strip(" ._")
    return (name or "attachment")[:_MAX_FILENAME_LENGTH]


# ========================
# Authentication Endpoints
# ========================


async def _issue_auth_response(
    user: User,
    db: AsyncSession,
    *,
    remember: bool,
) -> AuthResponse:
    """Create an access token and a revocable, rotated refresh session."""
    settings = get_settings()
    refresh_token = create_refresh_token()
    refresh_days = settings.refresh_expire_days if remember else 1
    db.add(RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=refresh_days),
    ))
    await db.commit()
    return AuthResponse(
        access_token=create_access_token(subject=user.id),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> PendingRegisterResponse:
    """Start registration by sending an OTP; the account is created after verification."""
    # The interface language for an account that does not exist yet. The
    # registration form offers one language, and it becomes both settings;
    # naming it here keeps the two `PendingRegistration` builds and the OTP
    # email from drifting apart, which is how the resend already ended up
    # reading a different field from the first send.
    pending_interface_language = request.preferred_language

    duplicate = await db.execute(
        select(User).where((User.email == request.email) | (User.username == request.username))
    )
    existing_user = duplicate.scalar_one_or_none()
    if existing_user is not None:
        detail = "Email is already registered" if existing_user.email == request.email else "Username is already registered"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    now = datetime.now(UTC)
    otp = _generate_otp()
    otp_hash = get_password_hash(otp)
    password_hash = get_password_hash(request.password)
    display_name = (request.display_name or request.username).strip()
    cooldown_threshold = now - timedelta(seconds=60)
    window_threshold = now - timedelta(seconds=3600)

    # Check for existing pending registration by email or username
    pending_query = await db.execute(
        select(PendingRegistration).where(
            (PendingRegistration.email == request.email) | (PendingRegistration.username == request.username)
        )
    )
    existing_pending = pending_query.scalars().first()

    if existing_pending is not None:
        is_window_expired = PendingRegistration.rate_window_started_at <= window_threshold
        stmt = (
            update(PendingRegistration)
            .where(
                PendingRegistration.id == existing_pending.id,
                PendingRegistration.last_sent_at <= cooldown_threshold,
                (PendingRegistration.rate_window_started_at <= window_threshold)
                | (PendingRegistration.request_count < 5),
            )
            .values(
                email=request.email,
                username=request.username,
                display_name=display_name,
                password_hash=password_hash,
                preferred_language=request.preferred_language,
                interface_language=pending_interface_language,
                otp_hash=otp_hash,
                attempts=0,
                expires_at=now + timedelta(minutes=5),
                last_sent_at=now,
                rate_window_started_at=case(
                    (is_window_expired, now),
                    else_=PendingRegistration.rate_window_started_at,
                ),
                request_count=case(
                    (is_window_expired, 1),
                    else_=PendingRegistration.request_count + 1,
                ),
            )
            .execution_options(synchronize_session=False)
            .returning(
                PendingRegistration.id,
                PendingRegistration.email,
            )
        )
        update_res = await db.execute(stmt)
        updated_row = update_res.mappings().one_or_none()
        if updated_row is not None:
            await db.commit()
            pending_id = updated_row["id"]
        else:
            # Conditional update failed: check if due to cooldown or rate limit
            pending = await db.get(PendingRegistration, existing_pending.id)
            if pending is not None:
                last_sent = _ensure_utc(pending.last_sent_at)
                remaining_cooldown = math.ceil(60 - (now - last_sent).total_seconds())
                if remaining_cooldown > 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Please wait before requesting another code.",
                        headers={"Retry-After": str(max(1, remaining_cooldown))},
                    )
                win_start = _ensure_utc(pending.rate_window_started_at)
                if pending.request_count >= 5 and (now - win_start).total_seconds() < 3600:
                    retry_after = math.ceil(3600 - (now - win_start).total_seconds())
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many verification requests. Please try again later.",
                        headers={"Retry-After": str(max(1, retry_after))},
                    )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code.",
                headers={"Retry-After": "60"},
            )
    else:
        pending = PendingRegistration(
            email=request.email,
            username=request.username,
            display_name=display_name,
            password_hash=password_hash,
            preferred_language=request.preferred_language,
            interface_language=pending_interface_language,
            otp_hash=otp_hash,
            expires_at=now + timedelta(minutes=5),
            attempts=0,
            last_sent_at=now,
            rate_window_started_at=now,
            request_count=1,
        )
        db.add(pending)
        try:
            await db.commit()
            pending_id = pending.id
        except IntegrityError as exc:
            await db.rollback()
            # Concurrent insertion raced for this email/username:
            # check the newly inserted row and apply cooldown/rate limits
            raced_pending = (
                await db.execute(
                    select(PendingRegistration).where(
                        (PendingRegistration.email == request.email)
                        | (PendingRegistration.username == request.username)
                    )
                )
            ).scalars().first()
            if raced_pending is not None:
                last_sent = _ensure_utc(raced_pending.last_sent_at)
                remaining = math.ceil(60 - (now - last_sent).total_seconds())
                if remaining > 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Please wait before requesting another code.",
                        headers={"Retry-After": str(max(1, remaining))},
                    )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username is already registered",
            ) from exc

    # Delivery occurs strictly AFTER database commit
    try:
        await send_registration_otp_email(
            to_email=request.email,
            otp=otp,
            # System email follows the interface language, like every other
            # notification. At first registration there is no account yet and
            # the form offers only one language, which line 392 also stores as
            # the interface language -- so this is that value, named for what it
            # is rather than for where it came from. The resend path reads the
            # stored `interface_language` and now agrees with this one.
            language=pending_interface_language,
        )
    except EmailDeliveryError as exc:
        logger.error("Email delivery failed for pending registration %s: %s", pending_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="email_delivery_failed",
        ) from None

    return PendingRegisterResponse(
        pending_id=pending_id,
        email=request.email,
        expires_in_seconds=300,
        cooldown_seconds=60,
        message="Verification code sent to your email",
    )


@router.post("/auth/register/resend", response_model=ResendRegisterOtpResponse)
async def resend_register_otp(
    request: ResendRegisterOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> ResendRegisterOtpResponse:
    """Replace an expired or misplaced registration OTP, subject to rate limits."""
    now = datetime.now(UTC)
    otp = _generate_otp()
    otp_hash = get_password_hash(otp)
    cooldown_threshold = now - timedelta(seconds=60)
    window_threshold = now - timedelta(seconds=3600)

    is_window_expired = PendingRegistration.rate_window_started_at <= window_threshold
    stmt = (
        update(PendingRegistration)
        .where(
            PendingRegistration.id == request.pending_id,
            PendingRegistration.last_sent_at <= cooldown_threshold,
            (PendingRegistration.rate_window_started_at <= window_threshold)
            | (PendingRegistration.request_count < 5),
        )
        .values(
            otp_hash=otp_hash,
            attempts=0,
            expires_at=now + timedelta(minutes=5),
            last_sent_at=now,
            rate_window_started_at=case(
                (is_window_expired, now),
                else_=PendingRegistration.rate_window_started_at,
            ),
            request_count=case(
                (is_window_expired, 1),
                else_=PendingRegistration.request_count + 1,
            ),
        )
        .execution_options(synchronize_session=False)
        .returning(
            PendingRegistration.id,
            PendingRegistration.email,
            PendingRegistration.interface_language,
        )
    )
    update_res = await db.execute(stmt)
    row = update_res.mappings().one_or_none()
    if row is not None:
        await db.commit()
        # Delivery occurs strictly AFTER database commit
        try:
            await send_registration_otp_email(
                to_email=row["email"],
                otp=otp,
                language=row["interface_language"],
            )
        except EmailDeliveryError as exc:
            logger.error("Email delivery failed for pending registration %s: %s", row["id"], type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="email_delivery_failed",
            ) from None

        return ResendRegisterOtpResponse(
            pending_id=row["id"],
            expires_in_seconds=300,
            cooldown_seconds=60,
            message="New verification code sent to your email",
        )

    # If update matched 0 rows, check reasons (not found, cooldown, or rate limit)
    pending = await db.get(PendingRegistration, request.pending_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending registration not found or already verified",
        )

    last_sent = _ensure_utc(pending.last_sent_at)
    remaining_cooldown = math.ceil(60 - (now - last_sent).total_seconds())
    if remaining_cooldown > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another code.",
            headers={"Retry-After": str(max(1, remaining_cooldown))},
        )

    win_start = _ensure_utc(pending.rate_window_started_at)
    if pending.request_count >= 5 and (now - win_start).total_seconds() < 3600:
        retry_after = math.ceil(3600 - (now - win_start).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification requests. Please try again later.",
            headers={"Retry-After": str(max(1, retry_after))},
        )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Please wait before requesting another code.",
        headers={"Retry-After": "60"},
    )


@router.post("/auth/register/verify", response_model=AuthResponse)
async def verify_register_otp(
    request: VerifyRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create the account and authenticate it after a valid, unused OTP."""
    pending = await db.get(PendingRegistration, request.pending_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification session",
        )

    now = datetime.now(UTC)
    expires_at = _ensure_utc(pending.expires_at)

    if pending.attempts >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new code.",
        )

    if now >= expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )

    if not verify_password(request.otp, pending.otp_hash):
        update_stmt = (
            update(PendingRegistration)
            .where(
                PendingRegistration.id == request.pending_id,
                PendingRegistration.otp_hash == pending.otp_hash,
                PendingRegistration.expires_at > now,
                PendingRegistration.attempts < 3,
            )
            .values(attempts=PendingRegistration.attempts + 1)
            .execution_options(synchronize_session=False)
            .returning(PendingRegistration.attempts)
        )
        update_res = await db.execute(update_stmt)
        new_attempts = update_res.scalar_one_or_none()
        await db.commit()

        if new_attempts is None or new_attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new code.",
            )
        remaining = max(0, 3 - new_attempts)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        )

    # Atomic conditional DELETE ... RETURNING
    delete_stmt = (
        delete(PendingRegistration)
        .where(
            PendingRegistration.id == request.pending_id,
            PendingRegistration.otp_hash == pending.otp_hash,
            PendingRegistration.expires_at > now,
            PendingRegistration.attempts < 3,
        )
        .execution_options(synchronize_session=False)
        .returning(
            PendingRegistration.id,
            PendingRegistration.email,
            PendingRegistration.username,
            PendingRegistration.display_name,
            PendingRegistration.password_hash,
            PendingRegistration.preferred_language,
            PendingRegistration.interface_language,
        )
    )
    delete_res = await db.execute(delete_stmt)
    consumed = delete_res.mappings().one_or_none()
    if consumed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code already used or invalid.",
        )

    # Check for existing user conflict
    duplicate = await db.execute(
        select(User).where((User.email == consumed["email"]) | (User.username == consumed["username"]))
    )
    existing = duplicate.scalar_one_or_none()
    if existing is not None:
        detail = "Email is already registered" if existing.email == request.email else "Username is already registered"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    display_name = (request.display_name or request.username).strip()
    user = User(
        email=request.email,
        username=request.username,
        display_name=display_name,
        password_hash=get_password_hash(request.password),
        preferred_language=request.preferred_language,
        # One language question at sign-up, two settings behind it. Someone who
        # picks Japanese wants to read Japanese *and* see a Japanese menu; the
        # two only part company later, if they go and change one of them
        # (docs/CONTRACT.md §1.3).
        interface_language=request.preferred_language,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username is already registered") from exc
    return await _issue_auth_response(user, db, remember=True)


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate user and return JWT token.

    Args:
        request: Login credentials (email and password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return await _issue_auth_response(user, db, remember=request.remember)


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_session(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Rotate a valid refresh token and return a fresh authenticated session."""
    result = await db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(request.refresh_token))
    )
    session = result.scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if session is None or session.revoked_at is not None:
        raise invalid

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        session.revoked_at = datetime.now(UTC)
        await db.commit()
        raise invalid

    user = await db.get(User, session.user_id)
    if user is None:
        raise invalid
    session.revoked_at = datetime.now(UTC)
    return await _issue_auth_response(user, db, remember=(expires_at - datetime.now(UTC)).days > 1)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a browser session. The operation is idempotent."""
    result = await db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(request.refresh_token))
    )
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()


@router.post("/auth/password/forgot", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Create a short-lived reset token without revealing account existence."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    generic = "If the account exists, password reset instructions are ready."
    if user is None:
        return ForgotPasswordResponse(message=generic)

    raw_token = create_refresh_token()
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_expire_minutes),
    ))
    await db.commit()
    # There is no mail provider yet (docs/DEPLOY.md). In development the token
    # comes back in the response so the flow is testable in one screen; anywhere
    # else it goes to the server log only, for an administrator to read out to
    # the person who asked. It is never both — a reset token in an HTTP response
    # is a password anyone who can reach the endpoint may claim.
    if get_settings().app_env == "development":
        return ForgotPasswordResponse(message=generic, reset_token=raw_token)

    reset_url = f"{settings.frontend_url}/reset-password?{urlencode({'token': raw_token})}"
    try:
        await send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
            expires_in_minutes=settings.password_reset_expire_minutes,
            language=user.interface_language,
        )
    except EmailDeliveryError as exc:
        # Preserve the same response for existing and unknown emails. Returning
        # an SMTP error only for real accounts would reintroduce account probing.
        logger.error("Password-reset email delivery failed for user %s: %s", user.id, type(exc).__name__)

    # Non-production environments keep the opaque token available for automated
    # tests and offline work. Production never exposes it through the API response.
    return ForgotPasswordResponse(
        message=generic,
        reset_token=raw_token if settings.app_env != "production" else None,
    )
    return ForgotPasswordResponse(message=generic)


@router.post("/auth/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a reset token, change the password, and revoke all sessions."""
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_refresh_token(request.token)
        )
    )
    reset = result.scalar_one_or_none()
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    if reset is None or reset.used_at is not None:
        raise invalid
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise invalid
    user = await db.get(User, reset.user_id)
    if user is None:
        raise invalid

    now = datetime.now(UTC)
    user.password_hash = get_password_hash(request.new_password)
    reset.used_at = now
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's information.

    Args:
        current_user: The authenticated user from JWT token

    Returns:
        User information (excludes password hash)
    """
    return UserResponse.model_validate(current_user)


@router.patch("/auth/me", response_model=UserResponse)
async def update_current_user_profile(
    request: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Persist the current user's editable profile fields only."""
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get("/auth/me/settings", response_model=UserSettingsResponse)
async def get_current_user_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    return UserSettingsResponse.model_validate(await get_or_create_user_settings(db, current_user.id))


@router.patch("/auth/me/settings", response_model=UserSettingsResponse)
async def patch_current_user_settings(
    request: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    settings = await update_user_settings(
        db, current_user.id, request.model_dump(exclude_unset=True)
    )
    return UserSettingsResponse.model_validate(settings)


@router.get("/auth/me/agent-consents", response_model=AgentConsentsResponse)
async def get_current_user_agent_consents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentConsentsResponse:
    """Return every assistant permission for the caller (`CONTRACT.md` §3.15)."""
    return AgentConsentsResponse(
        policy_version=AGENT_CONSENT_POLICY_VERSION,
        consents=[
            AgentConsentEntry.model_validate(row)
            for row in await get_consents(db, current_user.id)
        ],
    )


@router.put("/auth/me/agent-consents", response_model=AgentConsentsResponse)
async def put_current_user_agent_consents(
    request: AgentConsentsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentConsentsResponse:
    """Grant or revoke the named scopes and return the full current set."""
    return AgentConsentsResponse(
        policy_version=AGENT_CONSENT_POLICY_VERSION,
        consents=[
            AgentConsentEntry.model_validate(row)
            for row in await set_consents(db, current_user.id, request.consents)
        ],
    )


@router.get("/me/calendar/events", response_model=list[CalendarEventResponse])
async def list_calendar_events(
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    include_cancelled: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarEventResponse]:
    """Return the caller's calendar over a range (`CONTRACT.md` §3.16)."""
    events = await CalendarService(db).list_events(
        user_id=current_user.id,
        starts_after=starts_after,
        starts_before=starts_before,
        include_cancelled=include_cancelled,
    )
    # Same reason as the task inbox, with one extra condition: only an event the
    # assistant created is known to be stored in the owner's translation
    # language. A manually typed title holds whatever they typed and a synced
    # one holds whatever Google had, so translating those would be answering a
    # question nobody asked -- and feeding an English title to the translator as
    # Vietnamese returns it mangled.
    rows = [CalendarEventResponse.model_validate(event) for event in events]
    assistant_titles = [
        row.title if row.source == "assistant" else None for row in rows
    ]
    rendered = await render_many(
        assistant_titles,
        stored_language=current_user.preferred_language,
        interface_language=current_user.interface_language,
    )
    return [
        row.model_copy(update={"display_title": title})
        for row, title in zip(rows, rendered, strict=True)
    ]


@router.post(
    "/me/calendar/events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_calendar_event(
    request: CalendarEventCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    """Add an entry the caller typed themselves."""
    lead = (
        timedelta(minutes=request.reminder_minutes_before)
        if request.reminder_minutes_before is not None
        else None
    )
    scheduled = await CalendarService(db).create_event(
        user_id=current_user.id,
        title=request.title,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        details=request.details,
        location=request.location,
        all_day=request.all_day,
        timezone=request.timezone,
        source="manual",
        reminder_lead=lead,
    )
    # Scheduled rather than awaited: the entry is saved and the response is
    # owed now. Google being slow or down must not delay or fail a save the
    # user already made (ADR-36).
    schedule_calendar_push(event_id=scheduled.event.id, user_id=current_user.id)
    return CalendarEventResponse.model_validate(scheduled.event)


@router.patch("/me/calendar/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: str,
    request: CalendarEventUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    """Change an entry the caller owns and did not import from Google."""
    try:
        event = await CalendarService(db).update_event(
            user_id=current_user.id,
            event_id=event_id,
            changes=request.model_dump(exclude_unset=True),
        )
        schedule_calendar_push(event_id=event.id, user_id=current_user.id)
    except CalendarEventReadOnlyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This entry mirrors a Google Calendar event and is read-only here",
        ) from exc
    except CalendarEventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calendar entry was not found"
        ) from exc
    return CalendarEventResponse.model_validate(event)


@router.delete("/me/calendar/events/{event_id}", response_model=CalendarEventResponse)
async def cancel_calendar_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    """Withdraw an entry. The row stays; a reminder may already have fired."""
    try:
        event = await CalendarService(db).cancel_event(
            user_id=current_user.id, event_id=event_id
        )
        # A cancellation is a change like any other; Google needs to hear about
        # it or the meeting stays on the user's phone after they called it off.
        schedule_calendar_push(event_id=event.id, user_id=current_user.id)
    except CalendarEventReadOnlyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This entry mirrors a Google Calendar event and is read-only here",
        ) from exc
    except CalendarEventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calendar entry was not found"
        ) from exc
    return CalendarEventResponse.model_validate(event)


@router.get("/me/calendar/google/status", response_model=CalendarCapabilityResponse)
async def get_google_calendar_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarCapabilityResponse:
    """Report what the interface may offer for Google Calendar.

    Three facts rather than one flag, because the right thing to show differs
    for each. Not configured means the deployment has no credentials and the
    controls should not be drawn; not consented means show the permission, not
    the connect button; not linked means show connect rather than sync.

    Deliberately not gated on consent: the interface has to be able to ask this
    *before* the user has granted anything, or it cannot decide what to render.
    Nothing here reveals calendar content.
    """
    link = await db.get(CalendarLink, current_user.id)
    return CalendarCapabilityResponse(
        configured=is_configured_for_calendar(),
        consented=await has_consent(db, current_user.id, "calendar_read"),
        linked=link is not None,
        sync_enabled=bool(link and link.sync_enabled),
        last_synced_at=link.last_synced_at if link else None,
        last_sync_error=link.last_sync_error if link else None,
    )


@router.get("/me/calendar/google/authorize", response_model=GoogleAuthorizeResponse)
async def start_google_calendar_link(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleAuthorizeResponse:
    """Return the Google consent URL for connecting a calendar.

    Requires `calendar_read` up front. Sending someone through a consent screen
    for a permission they have not granted here would collect access this
    application has already been told not to use.
    """
    await require_consent(db, current_user.id, "calendar_read")
    if not is_configured_for_calendar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar is not configured on this deployment",
        )
    # A signed, short-lived state. Google echoes it back verbatim, so signing it
    # is what stops a stranger's authorization code being attached to somebody
    # else's account by crafting the callback URL.
    state = create_access_token(subject=current_user.id, expires_delta=timedelta(minutes=10))
    return GoogleAuthorizeResponse(authorization_url=build_authorization_url(state=state))


@router.post("/me/calendar/google/callback", response_model=CalendarLinkResponse)
async def complete_google_calendar_link(
    request: GoogleCalendarCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarLinkResponse:
    """Exchange the authorization code and store the encrypted tokens.

    The state is verified against the authenticated caller rather than merely
    checked for validity: a token signed for a different account proves the
    callback was replayed, which is exactly what the signature is there to
    catch.
    """
    await require_consent(db, current_user.id, "calendar_read")
    subject = await get_user_by_token(request.state, db)
    if subject is None or subject.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The authorization state did not match this account",
        )

    try:
        tokens = await exchange_code(request.code)
    except GoogleCalendarError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    link = await db.get(CalendarLink, current_user.id) or CalendarLink(user_id=current_user.id)
    link.refresh_token_encrypted = encrypt_secret(tokens["refresh_token"])
    link.access_token_encrypted = encrypt_secret(tokens["access_token"])
    link.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(tokens.get("expires_in", 3600))
    )
    # A fresh authorization invalidates whatever cursor the old one produced.
    link.sync_token = None
    link.sync_enabled = True
    link.last_sync_error = None
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return CalendarLinkResponse.model_validate(link)


@router.delete("/me/calendar/google/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_google_calendar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect the calendar and delete the stored tokens.

    Idempotent: disconnecting something already disconnected is the state the
    caller asked for, not an error.

    Events already pushed to Google are left there. They are the user's real
    appointments, and deleting them because they unlinked an integration would
    be destroying data they never asked to lose.
    """
    link = await db.get(CalendarLink, current_user.id)
    if link is None:
        return
    await db.delete(link)
    await db.commit()


@router.post("/me/calendar/sync", response_model=CalendarSyncResultResponse)
async def sync_google_calendar_now(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarSyncResultResponse:
    """Run one sync cycle immediately, for the "Sync now" button.

    Polling is what carries incoming changes (ADR-36), so this exists to make
    the wait skippable rather than to be the mechanism.
    """
    await require_consent(db, current_user.id, "calendar_read")
    try:
        counts = await sync_user(db, current_user.id)
    except GoogleCalendarNotLinkedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No Google Calendar is connected to this account",
        ) from exc
    link = await db.get(CalendarLink, current_user.id)
    return CalendarSyncResultResponse(
        pushed=counts["pushed"],
        pulled=counts["pulled"],
        last_synced_at=link.last_synced_at if link else None,
        last_sync_error=link.last_sync_error if link else None,
    )


@router.get("/me/reminders", response_model=list[ReminderResponse])
async def list_reminders(
    include_delivered: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReminderResponse]:
    """Return the caller's pending nudges, soonest first."""
    reminders = await CalendarService(db).list_reminders(
        user_id=current_user.id, include_delivered=include_delivered
    )
    return [ReminderResponse.model_validate(reminder) for reminder in reminders]


@router.post("/me/reminders/{reminder_id}/dismiss", response_model=ReminderResponse)
async def dismiss_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    """Mark one nudge as dealt with."""
    try:
        reminder = await CalendarService(db).dismiss_reminder(
            user_id=current_user.id, reminder_id=reminder_id
        )
    except CalendarEventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reminder was not found"
        ) from exc
    return ReminderResponse.model_validate(reminder)


@router.put("/auth/me/language", response_model=UserResponse)
async def update_preferred_language(
    request: UpdateLanguageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the current user's preferred language.

    Args:
        request: New language preference
        current_user: The authenticated user from JWT token
        db: Database session

    Returns:
        Updated user information
    """
    current_user.preferred_language = request.preferred_language
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.put("/auth/me/interface-language", response_model=UserResponse)
async def update_interface_language(
    request: UpdateInterfaceLanguageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the language the interface is drawn in (docs/CONTRACT.md §1.2).

    Deliberately does not touch `preferred_language`. The two are set together
    only once, when the account is created; from then on someone reading
    Japanese messages behind a Vietnamese menu is a choice the product allows.

    Args:
        request: New interface language.
        current_user: The authenticated user from JWT token.
        db: Database session.

    Returns:
        Updated user information.
    """
    current_user.interface_language = request.interface_language
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.put("/auth/me/timezone", response_model=UserResponse)
async def update_timezone(
    request: TimezoneUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Record the caller's IANA timezone, as reported by their browser.

    Stored so proposals can carry a real time. A wall clock like "3 giờ chiều
    thứ Sáu" is not an instant without an offset, and `normalize_action_time`
    will not take one from model output -- a guessed offset books the meeting at
    the wrong hour and nothing says so. Before this the server had no trusted
    source at all, so every extracted time reached the owner as an empty field.

    Validated against the zone database rather than stored as typed: an
    unknown name would be accepted here and then silently ignored at every read,
    which is the failure that looks like the feature simply not working.
    """
    try:
        ZoneInfo(request.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown IANA timezone name",
        ) from exc
    current_user.timezone = request.timezone
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get("/languages", response_model=list[str])
async def list_supported_languages() -> list[str]:
    """Return the language codes the system accepts.

    Serving the allowlist is what lets the frontend stop keeping its own copy;
    `SUPPORTED_LANGUAGES` stays the single source of truth (CONTRACT section 1).
    """
    return sorted(SUPPORTED_LANGUAGES)


@router.get("/users", response_model=list[UserResponse])
async def find_users(
    q: str = Query(..., min_length=2, max_length=255),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Find accounts to start a conversation with (docs/CONTRACT.md §3.1).

    Matches a case-insensitive prefix of the email, the username or the display
    name. Prefix rather than substring: matching anywhere inside the string turns
    this into a way to walk the whole user table one letter at a time, while a
    prefix still finds the person whose name or address the caller is typing.

    `func.lower` rather than `ilike`: SQLite — which the tests run on — applies
    `LIKE` case-insensitively to ASCII only, so `ilike` would agree with
    PostgreSQL on the test data and quietly disagree on real names.

    The caller is excluded: offering someone a conversation with themselves is
    the one result that is never what they meant.

    A list rather than a single object: an empty list is an unambiguous "no such
    account", where a 404 would be confused with a broken route.

    Authentication is required so it is not an anonymous enumeration oracle. It
    remains one for signed-in users, which is accepted at this stage — see the
    rate-limiting note in docs/DEPLOY.md.
    """
    # `%` and `_` are LIKE wildcards, so a query of "%" would otherwise list the
    # whole table — exactly what prefix matching is here to prevent.
    needle = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix = f"{needle}%"
    # A display name is several words, and people search for the one they know:
    # "An" must find "Nguyễn An". Any word may start the match, but no match
    # starts inside a word, so the walk-the-table problem above stays closed.
    word_prefix = f"% {needle}%"
    users = await db.scalars(
        select(User)
        .where(
            User.id != current_user.id,
            or_(
                func.lower(User.email).like(prefix, escape="\\"),
                func.lower(User.username).like(prefix, escape="\\"),
                func.lower(User.display_name).like(prefix, escape="\\"),
                func.lower(User.display_name).like(word_prefix, escape="\\"),
            ),
        )
        .order_by(User.email)
        .limit(20)
    )
    return [UserResponse.model_validate(user) for user in users]


# ========================
# Conversation Endpoints
# ========================


async def _conversation_response(
    service: ChatService,
    conversation: Conversation,
    last_message: tuple[str, datetime, str | None, str | None] | None = None,
    manager: ConnectionManager | None = None,
    unread_count: int = 0,
    members: Sequence[User] | None = None,
) -> ConversationResponse:
    """Build the minimal conversation representation for an authorized user.

    Args:
        service: Open chat service.
        conversation: Conversation being rendered.
        last_message: Preview text and time, already resolved for the calling
            account. A conversation with no messages passes None.
        manager: Live connection registry, for `online_member_ids`.
        unread_count: Messages this reader has not seen (§3.8).
        members: Already-loaded members. The list endpoint passes them in from
            one batched query; a single-conversation caller lets this load them.

    Returns:
        The conversation as the REST contract defines it (docs/CONTRACT.md §3.5).
    """
    if members is None:
        members = await service.get_conversation_members(conversation_id=conversation.id)
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        title=conversation.title,
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        member_ids=[member.id for member in members],
        members=[ConversationMemberSummary.model_validate(member) for member in members],
        last_message=last_message[0] if last_message else None,
        last_message_at=last_message[1] if last_message else None,
        last_message_type=last_message[2] if last_message else None,
        last_message_transcription_status=last_message[3] if last_message else None,
        online_member_ids=list(
            manager.online_user_ids(member.id for member in members)
        ) if manager else [],
        unread_count=unread_count,
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create the minimal direct or group conversation required for chat.

    Asking twice for the same direct conversation is answered with `200` and the
    conversation that already exists, not a second one (docs/CONTRACT.md §3.5).
    """
    service = ChatService(db)
    try:
        result = await service.create_conversation(
            creator_id=current_user.id,
            conversation_type=request.type,
            member_ids=request.member_ids,
            title=request.title,
        )
    except ReferencedUsersNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more referenced users do not exist",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not result.created:
        response.status_code = status.HTTP_200_OK

    return await _conversation_response(service, result.conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> list[ConversationResponse]:
    """List conversations that contain the authenticated user."""
    service = ChatService(db)
    conversations = await service.list_conversations(user_id=current_user.id)
    conversation_ids = [conversation.id for conversation in conversations]
    last_messages = await service.get_last_messages(
        conversation_ids=conversation_ids,
        reader_language=current_user.preferred_language,
        reader_id=current_user.id,
        # The caller's own standing per conversation, so the sidebar preview
        # picks the same translation the conversation itself will show.
        reader_profiles={
            conversation_id: profile_for(members, current_user.id)
            for conversation_id, members in profiles.items()
        },
        reader_tones={conversation_id: settings.translation_tone for conversation_id in conversation_ids},
    )
    unread = await service.get_unread_counts(
        user_id=current_user.id,
        conversation_ids=conversation_ids,
    )
    members = await service.get_members_by_conversation(conversation_ids=conversation_ids)
    return [
        await _conversation_response(
            service,
            conversation,
            last_messages.get(conversation.id),
            manager,
            unread.get(conversation.id, 0),
            members.get(conversation.id, []),
        )
        for conversation in conversations
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageHistoryResponse | list[MessageResponse],
)
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None, description="Opaque composite message cursor"),
    offset: int = Query(default=0, ge=0, le=10_000),
    paginated: bool = Query(default=False, description="Return the cursor page envelope"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageHistoryResponse | list[MessageResponse]:
    """Return a deterministic cursor page for an authorized member."""
    service = ChatService(db)
    try:
        before_created_at, before_id = decode_message_cursor(before) if before else (None, None)
        use_page_envelope = paginated or before is not None
        messages = await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=limit + 1 if use_page_envelope else limit,
            before_created_at=before_created_at,
            before_id=before_id,
            offset=offset,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    has_more = use_page_envelope and len(messages) > limit
    page = messages[-limit:] if has_more else messages
    live_message_ids = [message.id for message in page if message.deleted_at is None]
    translations = await _translations_by_message(
        db,
        live_message_ids,
        reader_id=current_user.id,
    )
    attachments = await service.get_attachments_by_message(message_ids=live_message_ids)
    saved_message_ids = await service.saved_message_ids(
        user_id=current_user.id, message_ids=live_message_ids
    )
    reactions_by_message = await service.reactions_by_message(message_ids=live_message_ids)
    items = [
        _message_response(
            message,
            translations=translations.get(message.id, []),
            created_at=message.created_at,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            attachment=(
                AttachmentResponse.model_validate(attachments[message.id])
                if message.id in attachments else None
            ),
            reply_to_message_id=message.reply_to_message_id,
        )
        for message in page
    ]
    if not use_page_envelope:
        return items
    return MessageHistoryResponse(
        items=items,
        has_more=has_more,
        next_cursor=(encode_message_cursor(page[0].created_at, page[0].id) if has_more and page else None),
    )


def _message_response(
    message: Message,
    *,
    translations: list[TranslationSummary],
    attachment: Attachment | None,
    is_saved: bool,
    reactions: list[tuple[str, int, list[str]]],
) -> MessageResponse:
    """Serialize a message consistently for history and search results."""
    return MessageResponse(
        id=message.id,
        client_message_id=message.client_message_id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        original_text="" if message.deleted_at else message.original_text,
        message_type=message.message_type,
        transcription_status=message.transcription_status,
        source_language=message.source_language,
        mentions=message_mentions(message),
        assistant_generated=message.assistant_generated,
        translations=translations,
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        attachment=AttachmentResponse.model_validate(attachment) if attachment else None,
        reply_to_message_id=message.reply_to_message_id,
        forwarded_from_message_id=message.forwarded_from_message_id,
        is_saved=is_saved,
        reactions=_reaction_summaries(reactions),
    )


def _search_snippet(text: str, query: str, *, radius: int = 72) -> str:
    """Return a short, stable excerpt around the case-insensitive match."""
    index = text.lower().find(query.lower())
    if index < 0:
        return text[: radius * 2]
    start = max(0, index - radius)
    end = min(len(text), index + len(query) + radius)
    return f"{'…' if start else ''}{text[start:end]}{'…' if end < len(text) else ''}"


@router.get(
    "/conversations/{conversation_id}/messages/search",
    response_model=MessageSearchResponse,
)
async def search_conversation_messages(
    conversation_id: str,
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=20, ge=1, le=100),
    before_created_at: datetime | None = None,
    before_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageSearchResponse:
    """Search a conversation without exposing another reader's translation.

    Search can match a stored translated rendering, but the response is built
    from the same reader-specific selection as history.  A manager's rendering
    can therefore never be returned to a peer merely because both rows contain
    a similar word.
    """
    service = ChatService(db)
    lowered_query = q.strip().lower()
    preferred_language = current_user.preferred_language
    visible_items: list[MessageSearchResult] = []

    current_before_created_at = before_created_at
    current_before_id = before_id
    batch_size = min(max(limit * 2, 50), 100)
    has_more = False

    while len(visible_items) <= limit:
        try:
            candidates = await service.search_messages(
                user_id=current_user.id,
                conversation_id=conversation_id,
                query=q,
                reader_language=preferred_language,
                limit=batch_size,
                before_created_at=current_before_created_at,
                before_id=current_before_id,
            )
        except ChatServiceError as exc:
            raise _message_error(exc) from exc

        if not candidates:
            break

        candidate_has_more = len(candidates) > batch_size
        batch_candidates = candidates[:batch_size]
        message_ids = [message.id for message in batch_candidates]

        translations = await _translations_by_message(
            db,
            message_ids,
            reader_id=current_user.id,
            conversation_id=conversation_id,
        )
        attachments = await service.get_attachments_by_message(message_ids=message_ids)
        saved_message_ids = await service.saved_message_ids(
            user_id=current_user.id, message_ids=message_ids
        )
        reactions_by_message = await service.reactions_by_message(message_ids=message_ids)

        for message in batch_candidates:
            original_match = lowered_query in message.original_text.lower()
            readable_translation = next(
                (
                    row
                    for row in translations.get(message.id, [])
                    if row.target_language == preferred_language
                    and lowered_query in row.translated_text.lower()
                ),
                None,
            )
            if not original_match and readable_translation is None:
                continue
            matched_text = message.original_text if original_match else readable_translation.translated_text
            visible_items.append(
                MessageSearchResult(
                    message=_message_response(
                        message,
                        translations=translations.get(message.id, []),
                        attachment=attachments.get(message.id),
                        is_saved=message.id in saved_message_ids,
                        reactions=reactions_by_message.get(message.id, []),
                    ),
                    matched_in="original" if original_match else "translation",
                    snippet=_search_snippet(matched_text, q.strip()),
                )
            )

        if len(visible_items) > limit:
            has_more = True
            break

        if not candidate_has_more:
            has_more = False
            break

        last_candidate = batch_candidates[-1]
        current_before_created_at = last_candidate.created_at
        current_before_id = last_candidate.id

    page = visible_items[:limit]
    last = page[-1].message if page else None
    return MessageSearchResponse(
        items=page,
        has_more=has_more,
        next_before_created_at=last.created_at if has_more and last else None,
        next_before_id=last.id if has_more and last else None,
    )


@router.get(
    "/saved-messages",
    response_model=SavedMessagesResponse,
)
async def list_saved_messages(
    limit: int = Query(default=20, ge=1, le=100),
    before_created_at: datetime | None = None,
    before_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedMessagesResponse:
    """List bookmark history ordered by bookmark creation time."""
    service = ChatService(db)
    try:
        rows = await service.list_saved_messages(
            user_id=current_user.id,
            limit=limit,
            before_created_at=before_created_at,
            before_id=before_id,
        )
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    has_more = len(rows) > limit
    page_rows = rows[:limit]

    messages = [msg for msg, _ in page_rows]
    saved_entries = [saved for _, saved in page_rows]
    message_ids = [msg.id for msg in messages]

    conversations_by_message = {msg.id: msg.conversation_id for msg in messages}
    translations_by_msg: dict[str, list[TranslationSummary]] = {}
    for conv_id in set(conversations_by_message.values()):
        c_msg_ids = [m.id for m in messages if m.conversation_id == conv_id]
        t = await _translations_by_message(
            db,
            c_msg_ids,
            reader_id=current_user.id,
            conversation_id=conv_id,
        )
        translations_by_msg.update(t)

    attachments = await service.get_attachments_by_message(message_ids=message_ids)
    reactions_by_message = await service.reactions_by_message(message_ids=message_ids)

    items = [
        _message_response(
            message,
            translations=translations_by_msg.get(message.id, []),
            attachment=attachments.get(message.id),
            is_saved=True,
            reactions=reactions_by_message.get(message.id, []),
        )
        for message in messages
    ]

    last_saved = saved_entries[-1] if saved_entries else None
    return SavedMessagesResponse(
        items=items,
        has_more=has_more,
        next_before_created_at=last_saved.created_at if has_more and last_saved else None,
        next_before_id=last_saved.id if has_more and last_saved else None,
    )


@router.put(
    "/conversations/{conversation_id}/messages/{message_id}/saved",
    response_model=SavedMessageStateResponse,
)
async def save_message(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedMessageStateResponse:
    service = ChatService(db)
    try:
        is_saved = await service.set_saved_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
            is_saved=True,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc
    return SavedMessageStateResponse(message_id=message_id, is_saved=is_saved)


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}/saved",
    response_model=SavedMessageStateResponse,
)
async def unsave_message(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedMessageStateResponse:
    service = ChatService(db)
    try:
        is_saved = await service.set_saved_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
            is_saved=False,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc
    return SavedMessageStateResponse(message_id=message_id, is_saved=is_saved)


def _reaction_summaries(rows: list[tuple[str, int, list[str]]]) -> list[MessageReactionSummary]:
    return [MessageReactionSummary(emoji=emoji, count=count, user_ids=user_ids) for emoji, count, user_ids in rows]


@router.put(
    "/conversations/{conversation_id}/messages/{message_id}/reactions",
    response_model=ReactionStateResponse,
)
async def add_message_reaction(
    conversation_id: str,
    message_id: str,
    payload: ReactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> ReactionStateResponse:
    service = ChatService(db)
    try:
        reactions = await service.update_reaction(
            user_id=current_user.id, conversation_id=conversation_id,
            message_id=message_id, emoji=payload.emoji, add=True,
        )
        member_ids = await service.get_conversation_member_ids(conversation_id=conversation_id)
    except ChatServiceError as exc:
        raise _message_error(exc) from exc
    response = ReactionStateResponse(message_id=message_id, reactions=_reaction_summaries(reactions))
    await manager.send_to_users(
        member_ids,
        MessageReactionsUpdatedEvent(
            conversation_id=conversation_id, message_id=message_id, reactions=response.reactions
        ).model_dump(mode="json"),
    )
    return response


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}/reactions",
    response_model=ReactionStateResponse,
)
async def remove_message_reaction(
    conversation_id: str,
    message_id: str,
    payload: ReactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> ReactionStateResponse:
    service = ChatService(db)
    try:
        reactions = await service.update_reaction(
            user_id=current_user.id, conversation_id=conversation_id,
            message_id=message_id, emoji=payload.emoji, add=False,
        )
        member_ids = await service.get_conversation_member_ids(conversation_id=conversation_id)
    except ChatServiceError as exc:
        raise _message_error(exc) from exc
    response = ReactionStateResponse(message_id=message_id, reactions=_reaction_summaries(reactions))
    await manager.send_to_users(
        member_ids,
        MessageReactionsUpdatedEvent(
            conversation_id=conversation_id, message_id=message_id, reactions=response.reactions
        ).model_dump(mode="json"),
    )
    return response


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/translate",
    response_model=TranslationRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@llm_limit
async def retry_message_translation(
    conversation_id: str,
    message_id: str,
    request: Request,
    response: Response,
    review_recipient: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> TranslationRetryResponse:
    """Request a fresh translation for the calling member only.

    This is an explicit retry, not an implicit cache refresh.  The scheduler
    bypasses its phrase cache and updates the caller's persisted language /
    standing / tone bucket in place before sending the normal realtime event.
    """
    service = ChatService(db)
    try:
        message = await service.get_message_for_member(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if message.deleted_at is not None:
            raise MessageAlreadyDeletedError(message_id)
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    reader_id = current_user.id
    viewer_ids = (current_user.id,)
    if review_recipient:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.type != "direct" or message.sender_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient translation can only be retried for your own direct message",
            )
        member_ids = tuple(
            member_id
            for member_id in await service.get_conversation_member_ids(conversation_id=conversation_id)
            if member_id != current_user.id
        )
        if len(member_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The direct conversation no longer has exactly one recipient",
            )
        reader_id = member_ids[0]
        viewer_ids = (current_user.id, reader_id)

    schedule_translation_retry(
        message=message,
        reader_id=reader_id,
        viewer_ids=viewer_ids,
        publisher=manager,
    )
    return TranslationRetryResponse(message_id=message_id)


@router.post(
    "/messages/{message_id}/transcription/retry",
    response_model=VoiceTranscriptionRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_voice_transcription(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> VoiceTranscriptionRetryResponse:
    """Atomically retry STT for the same failed voice message and audio."""
    try:
        result = await ChatService(db).retry_voice_transcription(
            user_id=current_user.id,
            message_id=message_id,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    # The service commit is authoritative. Only its guarded transition winner
    # reaches this call, so concurrent requests cannot launch another STT task.
    schedule_voice_transcription(
        message_id=result.message_id,
        conversation_id=result.conversation_id,
        publisher=manager,
    )
    return VoiceTranscriptionRetryResponse(
        message_id=result.message_id,
        conversation_id=result.conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/summary",
    response_model=ConversationSummaryResponse,
)
@llm_limit
async def summarize_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    payload: ConversationSummaryRequest = Body(default_factory=ConversationSummaryRequest),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    """Generate an on-demand grounded conversation summary for authorized members (B-03)."""
    service = ConversationIntelligenceService()
    try:
        return await service.summarize_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            db=db,
            message_limit=payload.message_limit,
            target_language=payload.target_language,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntelligenceError as exc:
        if exc.code == IntelligenceErrorCode.TIMEOUT:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Conversation summarization timed out",
            ) from exc
        if exc.code == IntelligenceErrorCode.PROVIDER_UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider is currently unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/extract-actions",
    response_model=list[ActionProposalResponse],
)
@llm_limit
async def extract_actions_from_message_endpoint(
    conversation_id: str,
    message_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActionProposalResponse]:
    """Extract candidate actions/appointments from a specific message (B-04)."""
    service = ConversationIntelligenceService()
    try:
        return await service.extract_actions_from_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user.id,
            db=db,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message was not found",
        ) from exc
    except IntelligenceError as exc:
        if exc.code == IntelligenceErrorCode.TIMEOUT:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Action extraction timed out",
            ) from exc
        if exc.code == IntelligenceErrorCode.PROVIDER_UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider is currently unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/clarify",
    response_model=ClarificationAnalysisResponse,
)
@llm_limit
async def analyze_message_clarification(
    conversation_id: str,
    message_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClarificationAnalysisResponse:
    """Analyze message for execution-relevant ambiguity and suggest clarification question (B-08)."""
    service = ConversationIntelligenceService()
    try:
        return await service.analyze_ambiguity_and_clarification(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user.id,
            db=db,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message was not found",
        ) from exc
    except IntelligenceError as exc:
        if exc.code == IntelligenceErrorCode.TIMEOUT:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Clarification analysis timed out",
            ) from exc
        if exc.code == IntelligenceErrorCode.PROVIDER_UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider is currently unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        # Do not expose an unhandled provider/SDK exception as an HTTP 500 to
        # the chat UI.  Preserve the trace in server logs while returning a
        # stable, actionable response that the client can present to the user.
        logger.exception(
            "Unexpected clarification analysis failure for conversation %s, message %s",
            conversation_id,
            message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clarification service is temporarily unavailable",
        ) from exc


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/detect-commitments",
    response_model=list[ActionProposalResponse],
)
@llm_limit
async def detect_message_self_commitments(
    conversation_id: str,
    message_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActionProposalResponse]:
    """Detect proactive first-person self-commitments from a message (B-10).

    Detection now writes one proposal per member, so the caller is handed only
    their own. The other rows are real and their owners are told over the
    socket; returning them here would put another member's proposal id in the
    caller's hands, and a list endpoint that answers with rows the caller may
    not act on invites exactly that confusion.
    """
    service = ConversationIntelligenceService()
    try:
        proposals = await service.detect_self_commitments_from_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user.id,
            db=db,
        )
        return [p for p in proposals if p.owner_user_id == current_user.id]
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except MessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message was not found",
        ) from exc
    except IntelligenceError as exc:
        if exc.code == IntelligenceErrorCode.TIMEOUT:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Commitment detection timed out",
            ) from exc
        if exc.code == IntelligenceErrorCode.PROVIDER_UNAVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider is currently unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc



async def _proposal_for_reader(proposal: "ActionProposal", reader: User) -> ActionProposalResponse:
    """One proposal, with the wording the reader's screens should show.

    Every endpoint that answers with a single proposal goes through here. They
    used to return the stored row while the list endpoint returned a rendered
    one, so approving from the inbox pushed the raw row back into the list and
    the title visibly changed language mid-flow.
    """
    row = ActionProposalResponse.model_validate(proposal)
    title, details = await asyncio.gather(
        render(
            row.title,
            stored_language=reader.preferred_language,
            interface_language=reader.interface_language,
        ),
        render(
            row.details,
            stored_language=reader.preferred_language,
            interface_language=reader.interface_language,
        ),
    )
    return row.model_copy(update={"display_title": title, "display_details": details})


@router.get(
    "/me/action-proposals",
    response_model=list[ActionProposalResponse],
)
async def list_conversation_proposals(
    conversation_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status: needs_clarification, pending_confirmation, confirmed, rejected, stale"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActionProposalResponse]:
    """List only the authenticated owner's proposals (B-05)."""
    service = ActionProposalService(db)
    try:
        proposals = await service.list_for_owner(current_user.id, status_filter, conversation_id)
        # The inbox is chrome, so its rows read in the interface language even
        # though the title was stored in the owner's translation language --
        # which is the right language for the card in the chat thread, beside
        # the message it came from, and the wrong one for a screen whose labels
        # are all in the other setting.
        #
        # Into `display_*`, never over `title`: the client sends `title` back on
        # approval, so rewriting it here persisted the machine translation over
        # what the person said.
        rows = [ActionProposalResponse.model_validate(p) for p in proposals]
        titles, details = await asyncio.gather(
            render_many(
                [row.title for row in rows],
                stored_language=current_user.preferred_language,
                interface_language=current_user.interface_language,
            ),
            render_many(
                [row.details for row in rows],
                stored_language=current_user.preferred_language,
                interface_language=current_user.interface_language,
            ),
        )
        return [
            row.model_copy(
                update={"display_title": title, "display_details": detail}
            )
            for row, title, detail in zip(rows, titles, details, strict=True)
        ]
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        ) from exc


@router.post(
    "/action-proposals/{proposal_id}/dismiss",
    response_model=ActionProposalResponse,
)
async def dismiss_action_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalResponse:
    """Clear one proposal out of the caller's task inbox.

    Hides the row. It does not cancel anything: a proposal that was approved has
    already put an event on the calendar, and that event and its reminders are
    untouched.
    """
    try:
        dismissed = await ActionProposalService(db).dismiss(
            proposal_id=proposal_id, user_id=current_user.id
        )
    except ActionProposalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal was not found"
        ) from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action proposal belongs to someone else",
        ) from exc
    return await _proposal_for_reader(dismissed, current_user)


@router.post("/me/action-proposals/dismiss-decided")
async def dismiss_decided_action_proposals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Clear every already-decided proposal at once ("xoá tất cả").

    Deliberately leaves anything still awaiting a decision: sweeping those away
    would drop a question the assistant is waiting on, and nobody would learn it
    had been asked. Calendars are untouched, as with a single dismissal.
    """
    return {"dismissed": await ActionProposalService(db).dismiss_all_decided(user_id=current_user.id)}


@router.post(
    "/action-proposals/{proposal_id}/confirm",
    response_model=ActionProposalResponse,
)
async def confirm_action_proposal(
    proposal_id: str,
    payload: ConfirmProposalRequest = Body(default_factory=ConfirmProposalRequest),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalResponse:
    """Explicitly confirm an action proposal by its assigned owner (B-05)."""
    service = ActionProposalService(db)
    try:
        # The lead time is not a correction to the proposal — it shapes the
        # calendar entry that confirming creates — so it travels as its own
        # argument. Left in `corrections` it would be filtered out silently by
        # the allowlist there and the person's choice would vanish.
        corrections = payload.model_dump(exclude_none=True)
        corrections.pop("reminder_minutes_before", None)
        confirmed = await service.confirm_proposal(
            proposal_id=proposal_id,
            user_id=current_user.id,
            corrections=corrections,
            reminder_minutes_before=payload.reminder_minutes_before,
        )
        # Approving a proposal is the product's main way of putting something on
        # a calendar, so it gets the same immediate push a manual entry does.
        # The entry only exists when the proposal carried a time; one without is
        # a task in the inbox and has nothing to send.
        scheduled = await db.scalar(
            select(CalendarEvent.id).where(CalendarEvent.action_proposal_id == confirmed.id)
        )
        if scheduled:
            schedule_calendar_push(event_id=scheduled, user_id=current_user.id)
        return await _proposal_for_reader(confirmed, current_user)
    except ActionProposalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal was not found",
        ) from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned owner can confirm this proposal",
        ) from exc
    except ActionProposalStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/action-proposals/{proposal_id}/reject",
    response_model=ActionProposalResponse,
)
async def reject_action_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalResponse:
    """Explicitly reject an action proposal by its assigned owner (B-05)."""
    service = ActionProposalService(db)
    try:
        rejected = await service.reject_proposal(proposal_id=proposal_id, user_id=current_user.id)
        return await _proposal_for_reader(rejected, current_user)
    except ActionProposalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal was not found",
        ) from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned owner can reject this proposal") from exc
    except ActionProposalStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/action-proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_terminal_action_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete an inbox item only after it has been rejected or become stale."""
    service = ActionProposalService(db)
    try:
        await service.delete_terminal_proposal(proposal_id, current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ActionProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal was not found") from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned owner can delete this proposal") from exc
    except ActionProposalStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/action-proposals/{proposal_id}/clarify", response_model=ActionProposalResponse)
async def clarify_action_proposal(
    proposal_id: str,
    payload: ClarifyProposalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionProposalResponse:
    service = ActionProposalService(db)
    try:
        proposal = await service.clarify(proposal_id, current_user.id, payload.answer, payload.timezone)
        return await _proposal_for_reader(proposal, current_user)
    except ActionProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal was not found") from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned owner can clarify this proposal") from exc
    except ActionProposalStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _message_error(exc: ChatServiceError) -> HTTPException:
    """Map a message-mutation failure onto its documented status (§3.6)."""
    if isinstance(exc, MessageNotFoundError | ConversationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, MessageOwnershipError | ConversationMembershipError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(
        exc,
        (
            MessageAlreadyDeletedError,
            VoiceTranscriptionRetryAttachmentError,
            VoiceTranscriptionRetryStateError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ReadReceiptResponse,
)
async def mark_conversation_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> ReadReceiptResponse:
    """Mark everything in a conversation as read by the caller (§3.8).

    Other members are told so their own copy of the thread can show the message
    as seen rather than merely delivered.
    """
    service = ChatService(db)
    try:
        read_at = await service.mark_conversation_read(
            user_id=current_user.id,
            conversation_id=conversation_id,
        )
        member_ids = await service.get_conversation_member_ids(
            conversation_id=conversation_id,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        tuple(member_id for member_id in member_ids if member_id != current_user.id),
        MessageReadEvent(
            conversation_id=conversation_id,
            user_id=current_user.id,
            read_at=read_at,
        ).model_dump(mode="json"),
    )
    return ReadReceiptResponse()


@router.patch(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=MessageResponse,
)
async def edit_message(
    conversation_id: str,
    message_id: str,
    payload: EditMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> MessageResponse:
    """Replace the text of a message the caller sent (F-06).

    The previous translations are discarded and the message is translated again
    in the background, because a translation of retracted text is worse than no
    translation at all.
    """
    service = ChatService(db)
    try:
        message, recipient_ids = await service.edit_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
            text=payload.text,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        recipient_ids,
        MessageUpdatedEvent(
            message_id=message.id,
            conversation_id=message.conversation_id,
            original_text=message.original_text,
            edited_at=message.edited_at,
        ).model_dump(mode="json"),
    )
    if message.visible_to_user_id is None:
        schedule_translations(message=message, publisher=manager)

    return MessageResponse(
        id=message.id,
        client_message_id=message.client_message_id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        original_text=message.original_text,
        message_type=message.message_type,
        transcription_status=message.transcription_status,
        source_language=message.source_language,
        translations=[],
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
    )


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    """Withdraw a message the caller sent, keeping its row (F-06)."""
    service = ChatService(db)
    try:
        message, recipient_ids = await service.delete_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    except ChatServiceError as exc:
        raise _message_error(exc) from exc

    await manager.send_to_users(
        recipient_ids,
        MessageDeletedEvent(
            message_id=message.id,
            conversation_id=message.conversation_id,
            deleted_at=message.deleted_at,
        ).model_dump(mode="json"),
    )


@router.post(
    "/translations/{translation_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_translation_feedback(
    translation_id: str,
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Record the authenticated reader's rating and optional correction (F-05).

    Re-submitting replaces that reader's previous verdict on the same
    translation rather than adding a second row.
    """
    service = ChatService(db)
    try:
        feedback = await service.submit_translation_feedback(
            user_id=current_user.id,
            translation_id=translation_id,
            rating=payload.rating,
            correction=payload.correction,
        )
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return FeedbackResponse(feedback_id=feedback.id)


@router.post(
    "/translations/{translation_id}/edits",
    response_model=TranslationEditResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_translation_edit(
    translation_id: str,
    payload: TranslationEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranslationEditResponse:
    """Store the caller's own wording for a translation (docs/CONTRACT.md §3.10).

    Each call appends, so editing again keeps the earlier attempt. The text is
    private to its author and no WebSocket event follows: nobody else's screen
    changes because of it.
    """
    service = ChatService(db)
    try:
        edit, translation = await service.submit_translation_edit(
            user_id=current_user.id,
            translation_id=translation_id,
            edited_text=payload.edited_text,
        )
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation was not found",
        ) from exc
    except ConversationMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        ) from exc
    except ConversationValidationError as exc:
        # A withdrawn message, which is a conflict with the message's state
        # rather than a malformed request — same code §3.6 uses for editing one.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return TranslationEditResponse(
        edit_id=edit.id,
        translation_id=translation.id,
        message_id=translation.message_id,
        target_language=translation.target_language,
        edited_text=edit.edited_text,
        edited_at=edit.created_at,
    )


async def _translations_by_message(
    db: AsyncSession,
    message_ids: list[str],
    reader_id: str,
) -> dict[str, list[TranslationSummary]]:
    """Load every translation for a page of messages in one query.

    History is how a client recovers translations it missed while disconnected,
    so this is what keeps a socket dropping mid-translation from losing data.
    Each summary also carries `reader_id`'s own feedback, which is what lets a
    rating button still look rated after a reload.

    Args:
        db: Open session.
        message_ids: Messages whose translations are being rendered.
        reader_id: Account whose feedback is attached; never another member's.

    Returns:
        Translations grouped by message id, in no guaranteed order.
    """
    if not message_ids:
        return {}

    rows = list(
        (
            await db.scalars(
                select(TranslationResult).where(
                    TranslationResult.message_id.in_(message_ids)
                )
            )
        ).all()
    )

    my_feedback = {
        feedback.translation_id: feedback
        for feedback in (
            await db.scalars(
                select(Feedback).where(
                    Feedback.user_id == reader_id,
                    Feedback.translation_id.in_([row.id for row in rows]),
                )
            )
        ).all()
    }

    # The caller's own edits only. Loaded here rather than joined above so the
    # privacy rule is visible in one place: this dict is keyed by translation
    # and filtered by reader, and nothing else ever reaches these rows (§3.10).
    my_edits = await ChatService(db).latest_translation_edits(
        translation_ids=[row.id for row in rows],
        editor_id=reader_id,
    )

    grouped: dict[str, list[TranslationSummary]] = {}
    for row in rows:
        feedback = my_feedback.get(row.id)
        edit = my_edits.get(row.id)
        grouped.setdefault(row.message_id, []).append(
            # Built field by field rather than validated from the ORM object:
            # the row's primary key is `id`, and the client needs it under the
            # name `translation_id` so F-05 can attach feedback to it
            # (docs/CONTRACT.md section 4.4). `from_attributes` cannot rename.
            TranslationSummary(
                translation_id=row.id,
                target_language=row.target_language,
                translated_text=row.translated_text,
                model=row.model,
                latency_ms=row.latency_ms,
                is_fallback=row.is_fallback,
                my_rating=feedback.rating if feedback else None,
                my_correction=feedback.correction if feedback else None,
                my_edit=TranslationEditSummary(
                    edit_id=edit.id,
                    edited_text=edit.edited_text,
                    edited_at=edit.created_at,
                ) if edit else None,
            )
        )
    return grouped


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_conversation_attachment(
    conversation_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Upload one file for a conversation the current user belongs to.

    Files are stored outside public static paths. A download requires the same
    conversation-membership check, so knowing a URL never grants access.
    """
    service = ChatService(db)
    try:
        await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=1,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation was not found") from exc
    except ConversationMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this conversation") from exc
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    attachment_id = f"{uuid.uuid4().hex}_{_safe_filename(file.filename)}"
    destination = _attachment_path(conversation_id, attachment_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Attachment exceeds the 20 MB limit",
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    payload = b"".join(chunks)
    try:
        await AttachmentStorage(settings).write(
            conversation_id=conversation_id,
            attachment_id=attachment_id,
            data=payload,
            content_type=content_type,
        )
    except AttachmentStorageError:
        logger.warning("Attachment storage upload failed for %s", attachment_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to store attachment",
        ) from None

    # Persisted so a message can claim it later; until then the row is an
    # unattached upload, which is a normal state (docs/CONTRACT.md §3.7).
    attachment = Attachment(
        id=attachment_id,
        conversation_id=conversation_id,
        uploader_id=current_user.id,
        filename=_safe_filename(file.filename),
        content_type=content_type,
        size=written,
    )
    db.add(attachment)
    await db.commit()

    return AttachmentResponse.model_validate(attachment)


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[AttachmentResponse],
)
async def list_conversation_attachments(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AttachmentResponse]:
    """List files that are carried by visible messages in a conversation.

    Uploaded-but-unsent files are intentionally omitted. This keeps the
    conversation details aligned with what members can actually see in chat.
    """
    service = ChatService(db)
    try:
        await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=1,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation was not found") from exc
    except ConversationMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this conversation") from exc
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    attachments = (
        await db.scalars(
            select(Attachment)
            .join(Message, Message.id == Attachment.message_id)
            .where(
                Attachment.conversation_id == conversation_id,
                Attachment.message_id.is_not(None),
                Message.deleted_at.is_(None),
                or_(
                    Message.visible_to_user_id.is_(None),
                    Message.visible_to_user_id == current_user.id,
                ),
            )
            .order_by(Attachment.created_at.desc(), Attachment.id.desc())
        )
    ).all()
    return [AttachmentResponse.model_validate(attachment) for attachment in attachments]


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}")
async def download_conversation_attachment(
    conversation_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download an attachment after verifying conversation membership."""
    service = ChatService(db)
    try:
        await service.get_message_history(user_id=current_user.id, conversation_id=conversation_id, limit=1)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation was not found") from exc
    except ConversationMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this conversation") from exc
    except ConversationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # OUTER join, not inner. The visibility filter below is right and has to
    # stay — an attachment carried by a private assistant reply belongs to its
    # one reader (ADR-31) — but an inner join also drops every attachment whose
    # `message_id` is still NULL, and that is every attachment between being
    # uploaded and being sent. The product uploads first and attaches on send,
    # so an inner join makes a file undownloadable during exactly the window the
    # composer needs it.
    #
    # Membership is already enforced above, by `get_message_history`, which is
    # what protects an attachment that no message carries yet.
    attachment = await db.scalar(
        select(Attachment)
        .outerjoin(Message, Message.id == Attachment.message_id)
        .where(
            Attachment.id == attachment_id,
            Attachment.conversation_id == conversation_id,
            or_(
                # Uploaded, not yet sent: no message to judge visibility by.
                Attachment.message_id.is_(None),
                and_(
                    Message.conversation_id == conversation_id,
                    Message.deleted_at.is_(None),
                    or_(
                        Message.visible_to_user_id.is_(None),
                        Message.visible_to_user_id == current_user.id,
                    ),
                ),
            ),
        )
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")

    try:
        stored = await AttachmentStorage().download(attachment)
    except AttachmentStorageNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment was not found",
        ) from None
    except AttachmentStorageError:
        logger.warning("Attachment storage download failed for %s", attachment_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve attachment",
        ) from None

    if stored.local_path is not None:
        return FileResponse(
            stored.local_path,
            filename=stored.filename,
            media_type=stored.content_type,
        )
    return Response(
        content=stored.data or b"",
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{stored.filename}"'},
    )

