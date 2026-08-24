"""API routes for the application."""

import logging
import math
import mimetypes
import re
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation_intelligence.errors import (
    IntelligenceError,
    IntelligenceErrorCode,
)
from src.api.websocket import get_connection_manager
from src.config import get_settings
from src.core.deps import get_current_user
from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from src.database import get_db
from src.database.models import (
    Attachment,
    BlockedUser,
    CallSession,
    Conversation,
    ConversationMember,
    Feedback,
    Message,
    PasswordResetToken,
    PendingRegistration,
    RefreshSession,
    TranslationResult,
    User,
)
from src.schemas.auth import (
    SUPPORTED_LANGUAGES,
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLinkResponse,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    PendingRegisterResponse,
    RefreshRequest,
    RegisterRequest,
    ResendRegisterOtpRequest,
    ResendRegisterOtpResponse,
    ResetPasswordRequest,
    UpdateInterfaceLanguageRequest,
    UpdateLanguageRequest,
    UserProfileUpdate,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
    VerifyRegisterRequest,
)
from src.schemas.chat import (
    AttachmentResponse,
    CallEvent,
    CallResponse,
    CallStartRequest,
    ConversationCreateRequest,
    ConversationMemberLeftEvent,
    ConversationMemberSummary,
    ConversationPreferencesUpdate,
    ConversationResponse,
    EditMessageRequest,
    FeedbackRequest,
    FeedbackResponse,
    GroupMembersRequest,
    GroupRoleRequest,
    GroupTransferOwnerRequest,
    GroupUpdateRequest,
    MessageDeletedEvent,
    MessageReactionSummary,
    MessageReactionsUpdatedEvent,
    MessageReadEvent,
    MessageResponse,
    MessageSearchResponse,
    MessageSearchResult,
    MessageUpdatedEvent,
    ReactionStateResponse,
    ReactionUpdateRequest,
    ReadReceiptResponse,
    SavedMessagesResponse,
    SavedMessageStateResponse,
    TranslationEditRequest,
    TranslationEditResponse,
    TranslationEditSummary,
    TranslationRetryResponse,
    TranslationSummary,
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
from src.services.blocking import (
    DirectMessagingBlockedError,
    block_user,
    list_blocked_user_ids,
    unblock_user,
)
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
)
from src.services.connection_manager import ConnectionManager
from src.services.conversation_intelligence import ConversationIntelligenceService
from src.services.correction_log import schedule_correction_record
from src.services.customization import resolve_conversation_profile
from src.services.email import EmailDeliveryError, send_registration_otp_email
from src.services.google_auth import GoogleAuthError, GoogleUserInfo, verify_google_token
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

logger = logging.getLogger(__name__)

router = APIRouter()

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_MAX_FILENAME_LENGTH = 120


def _safe_filename(filename: str | None) -> str:
    """Keep a human-readable filename while preventing path traversal."""
    name = Path(filename or "attachment").name
    name = _SAFE_FILENAME.sub("_", name).strip(" ._")
    return (name or "attachment")[:_MAX_FILENAME_LENGTH]


def _attachment_path(conversation_id: str, attachment_id: str) -> Path:
    """Resolve a server generated attachment id to its storage path."""
    root = Path(get_settings().upload_dir).resolve()
    candidate = (root / conversation_id / attachment_id).resolve()
    if root not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
    return candidate


def _supabase_storage_path(conversation_id: str, attachment_id: str) -> str:
    return f"{conversation_id}/{attachment_id}"


def _supabase_storage_configured() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _supabase_storage_headers(content_type: str | None = None) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _supabase_object_url(object_path: str) -> str:
    settings = get_settings()
    return (f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
            f"{settings.supabase_storage_bucket}/{object_path}")


def _supabase_object_missing(response: httpx.Response) -> bool:
    """Supabase may encode NoSuchKey as HTTP 400 with an inner 404 status."""
    if response.status_code == status.HTTP_404_NOT_FOUND:
        return True
    if response.status_code != status.HTTP_400_BAD_REQUEST:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return payload.get("code") == "NoSuchKey" or payload.get("error") == "not_found"


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


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware with UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _generate_otp() -> str:
    """Generate a zero-padded 6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


@router.post(
    "/auth/register",
    response_model=PendingRegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> PendingRegisterResponse:
    """Start registration by sending an OTP; the account is created after verification."""
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
                interface_language=request.preferred_language,
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
            interface_language=request.preferred_language,
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
            language=request.preferred_language,
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
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered",
        )

    # Create User and initial RefreshSession in the same single transaction
    user = User(
        email=consumed["email"],
        username=consumed["username"],
        display_name=consumed["display_name"],
        password_hash=consumed["password_hash"],
        preferred_language=consumed["preferred_language"],
        interface_language=consumed["interface_language"],
        role="member",
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered",
        ) from exc

    settings = get_settings()
    refresh_token = create_refresh_token()
    refresh_days = settings.refresh_expire_days
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=refresh_days),
        )
    )
    await db.commit()

    return AuthResponse(
        access_token=create_access_token(subject=user.id),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


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

    if user is None or not user.password_hash:
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


async def _user_by_google_sub(db: AsyncSession, google_sub: str) -> User | None:
    """Return the canonical owner of a Google subject, if one exists.

    The unique database constraint should make this a zero-or-one lookup. If a
    legacy or manually-corrupted database violates that invariant, fail closed
    rather than issuing a session for an arbitrary row.
    """
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    users = result.scalars().all()
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account identity conflict.",
        )
    return users[0] if users else None


async def _user_by_google_email(db: AsyncSession, email: str) -> User | None:
    """Return the account for an already verified, normalized Google email.

    The current application always normalizes email before storing it, but an
    older case-sensitive unique index could contain case variants. Treat that
    as an explicit conflict instead of logging into whichever row happens to
    be returned first.
    """
    result = await db.execute(select(User).where(func.lower(User.email) == email))
    users = result.scalars().all()
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email identity conflict.",
        )
    return users[0] if users else None


async def _user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Reload a user after a SQL UPDATE that bypasses the ORM identity map."""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _claim_google_sub(
    db: AsyncSession,
    *,
    user_id: str,
    google_sub: str,
) -> User | None:
    """Atomically attach a Google subject only while the account is unlinked.

    The conditional UPDATE is the concurrency boundary.  A competing request
    cannot overwrite a subject that another request has just attached, even
    when the two subjects are different and therefore would not hit the unique
    constraint.  Every unsuccessful claim rolls the session back before a
    caller re-fetches canonical state.
    """
    try:
        claimed_id = (
            await db.execute(
                update(User)
                .where(User.id == user_id, User.google_sub.is_(None))
                .values(google_sub=google_sub)
                .returning(User.id)
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()
        if claimed_id is None:
            await db.rollback()
            return None
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None

    return await _user_by_id(db, user_id)


async def _reconcile_google_login_race(
    db: AsyncSession,
    google_info: GoogleUserInfo,
) -> User:
    """Re-fetch authoritative state after a failed Google link/create claim."""
    # Subject ownership always wins: it is the immutable Google identity and is
    # intentionally checked before the mutable email address.
    by_sub = await _user_by_google_sub(db, google_info.google_sub)
    if by_sub is not None:
        return by_sub

    by_email = await _user_by_google_email(db, google_info.email)
    if by_email is not None and by_email.google_sub is None:
        # A concurrent create may have made the email appear after our first
        # lookup. Claim it through the same compare-and-swap boundary.
        linked = await _claim_google_sub(
            db,
            user_id=by_email.id,
            google_sub=google_info.google_sub,
        )
        if linked is not None:
            return linked

        by_sub = await _user_by_google_sub(db, google_info.google_sub)
        if by_sub is not None:
            return by_sub
        by_email = await _user_by_google_email(db, google_info.email)

    if by_email is not None and by_email.google_sub == google_info.google_sub:
        return by_email
    if by_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already linked to a different Google account.",
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Google account registration conflict.",
    )


@router.post("/auth/google/login", response_model=AuthResponse)
@router.post("/auth/google", response_model=AuthResponse)
async def google_login(
    request: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Log in or sign up with a Google ID token as a full authentication provider."""
    try:
        google_info: GoogleUserInfo = await verify_google_token(request.credential)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # CASE 1: Subject match takes precedence over email.
    user = await _user_by_google_sub(db, google_info.google_sub)
    if user is not None:
        return await _issue_auth_response(user, db, remember=request.remember)

    # CASE 2: The verified email may claim only an unlinked account.
    email_user = await _user_by_google_email(db, google_info.email)
    if email_user is not None:
        if email_user.google_sub is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already linked to a different Google account.",
            )

        linked = await _claim_google_sub(
            db,
            user_id=email_user.id,
            google_sub=google_info.google_sub,
        )
        if linked is None:
            linked = await _reconcile_google_login_race(db, google_info)

        logger.info("Google login resolved to existing user %s", linked.id)
        return await _issue_auth_response(linked, db, remember=request.remember)

    # CASE 3: Create a password-less Google-native account. The unique database
    # constraints remain authoritative; an IntegrityError is reconciled below.
    new_user = User(
        email=google_info.email,
        google_sub=google_info.google_sub,
        password_hash=None,
        display_name=google_info.name,
        username=None,
        role="member",
        preferred_language="en",
        interface_language="en",
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        canonical = await _reconcile_google_login_race(db, google_info)
        return await _issue_auth_response(canonical, db, remember=request.remember)

    logger.info("Created new Google-native user %s", new_user.id)
    return await _issue_auth_response(new_user, db, remember=request.remember)


@router.post("/auth/me/google/link", response_model=GoogleLinkResponse)
async def link_google_account(
    request: GoogleLoginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleLinkResponse:
    """Link a Google account to the current LinguaFlow account (Batch G).

    The user must have a valid session (JWT). After linking they can log in with
    Google on any device. One Google account maps to one LinguaFlow account.
    """
    # _claim_google_sub may roll back the AsyncSession, which expires ORM
    # instances. Keep the caller identity as an immutable primitive for every
    # operation after that concurrency boundary.
    current_user_id = current_user.id

    if current_user.google_sub is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already linked to a Google account.",
        )

    try:
        google_info: GoogleUserInfo = await verify_google_token(request.credential)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    linked = await _claim_google_sub(
        db,
        user_id=current_user_id,
        google_sub=google_info.google_sub,
    )
    if linked is None:
        owner = await _user_by_google_sub(db, google_info.google_sub)
        if owner is None or owner.id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another user.",
            )

    logger.info("Google account linked to user %s", current_user_id)
    return GoogleLinkResponse(
        google_linked=True,
        message="Google account linked successfully.",
    )


@router.delete("/auth/me/google/link", response_model=GoogleLinkResponse)
async def unlink_google_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleLinkResponse:
    """Remove the Google link from the current LinguaFlow account (Batch G).

    If already unlinked, returns 200 with google_linked=false (idempotent).
    If google_sub exists and password_hash is NULL, returns 409 Conflict
    to prevent locking the user out of their only authentication method.
    """
    if current_user.google_sub is None:
        return GoogleLinkResponse(
            google_linked=False,
            message="Google account unlinked successfully.",
        )

    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot unlink Google account without a password. Please set a password first.",
        )

    current_user.google_sub = None
    await db.commit()
    logger.info("Google account unlinked from user %s", current_user.id)

    return GoogleLinkResponse(
        google_linked=False,
        message="Google account unlinked successfully.",
    )



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

    logger.warning(
        "Password reset requested for %s. Reset token: %s (valid %s minutes)",
        user.email,
        raw_token,
        get_settings().password_reset_expire_minutes,
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
            ~select(BlockedUser.blocker_id)
            .where(
                BlockedUser.blocker_id == current_user.id,
                BlockedUser.blocked_id == User.id,
            )
            .exists(),
            ~select(BlockedUser.blocker_id)
            .where(
                BlockedUser.blocker_id == User.id,
                BlockedUser.blocked_id == current_user.id,
            )
            .exists(),
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


@router.put("/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def block_contact(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if await db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User was not found")
    try:
        await block_user(db, current_user.id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_contact(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await unblock_user(db, current_user.id, user_id)


@router.get("/auth/me/blocked-users", response_model=list[UserResponse])
async def get_blocked_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    user_ids = await list_blocked_user_ids(db, current_user.id)
    if not user_ids:
        return []
    users = await db.scalars(select(User).where(User.id.in_(user_ids)))
    by_id = {user.id: user for user in users}
    return [UserResponse.model_validate(by_id[user_id]) for user_id in user_ids if user_id in by_id]


# ========================
# Conversation Endpoints
# ========================


async def _conversation_response(
    service: ChatService,
    conversation: Conversation,
    last_message: tuple[str, datetime] | None = None,
    manager: ConnectionManager | None = None,
    unread_count: int = 0,
    members: Sequence[User] | None = None,
    profiles: dict[str, str] | None = None,
    preference: ConversationMember | None = None,
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
        profiles: Each member's standing in *this* conversation, already
            resolved. Passed in for the same reason `members` is: the list
            endpoint resolves every conversation in one query, and looking them
            up here would put an N+1 back into it.

    Returns:
        The conversation as the REST contract defines it (docs/CONTRACT.md §3.5).
    """
    if members is None:
        members = await service.get_conversation_members(conversation_id=conversation.id)
    profiles = profiles or {}
    role_rows = await service._db.execute(
        select(ConversationMember.user_id, ConversationMember.role).where(
            ConversationMember.conversation_id == conversation.id
        )
    )
    group_roles = dict(role_rows.all())
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        title=conversation.title,
        description=conversation.description,
        created_by=conversation.created_by,
        created_at=conversation.created_at,
        member_ids=[member.id for member in members],
        # Built field by field rather than validated from the ORM row: a
        # standing belongs to a member *within a conversation*, so it is not on
        # the User object and `from_attributes` has nowhere to read it from.
        members=[
            ConversationMemberSummary(
                id=member.id,
                email=member.email,
                username=member.username,
                display_name=member.display_name,
                preferred_language=member.preferred_language,
                group_role=group_roles.get(member.id, "member"),
                honorific_profile=profile_for(profiles, member.id),
            )
            for member in members
        ],
        last_message=last_message[0] if last_message else None,
        last_message_at=last_message[1] if last_message else None,
        online_member_ids=list(
            manager.online_user_ids(member.id for member in members)
        ) if manager else [],
        unread_count=unread_count,
        is_pinned=preference.is_pinned if preference else False,
        pinned_at=preference.pinned_at if preference else None,
        is_muted=preference.is_muted if preference else False,
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
    except DirectMessagingBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct messaging is unavailable",
        ) from exc

    if not result.created:
        response.status_code = status.HTTP_200_OK

    return await _conversation_response(
        service,
        result.conversation,
        profiles=await resolve_profiles(db, result.conversation.id),
        preference=await db.get(ConversationMember, (result.conversation.id, current_user.id)),
    )


async def _group_access(db: AsyncSession, conversation_id: str, user_id: str) -> tuple[Conversation, ConversationMember]:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Group was not found")
    if conversation.type != "group":
        raise HTTPException(status_code=400, detail="This operation is only available for groups")
    membership = await db.get(ConversationMember, (conversation_id, user_id))
    if membership is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    return conversation, membership


@router.post("/conversations/{conversation_id}/members", status_code=204)
async def add_group_members(conversation_id: str, payload: GroupMembersRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    _, actor = await _group_access(db, conversation_id, current_user.id)
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only group administrators can add members")
    found = set((await db.scalars(select(User.id).where(User.id.in_(payload.user_ids)))).all())
    if found != set(payload.user_ids):
        raise HTTPException(status_code=404, detail="One or more users were not found")
    existing = set((await db.scalars(select(ConversationMember.user_id).where(ConversationMember.conversation_id == conversation_id, ConversationMember.user_id.in_(payload.user_ids)))).all())
    db.add_all(ConversationMember(conversation_id=conversation_id, user_id=user_id, role="member") for user_id in found - existing)
    await db.commit()


@router.patch("/conversations/{conversation_id}", status_code=204)
async def update_group_details(conversation_id: str, payload: GroupUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    conversation, membership = await _group_access(db, conversation_id, current_user.id)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only group administrators can edit group information")
    conversation.title = payload.title
    conversation.description = payload.description
    await db.commit()


@router.delete("/conversations/{conversation_id}/members/{user_id}", status_code=204)
async def remove_group_member(conversation_id: str, user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    _, actor = await _group_access(db, conversation_id, current_user.id)
    target = await db.get(ConversationMember, (conversation_id, user_id))
    if actor.role not in {"owner", "admin"} or target is None:
        raise HTTPException(status_code=403 if target else 404, detail="Member cannot be removed")
    if target.role == "owner" or (actor.role == "admin" and target.role == "admin"):
        raise HTTPException(status_code=403, detail="You cannot remove this group administrator")
    await db.delete(target)
    await db.commit()


@router.patch("/conversations/{conversation_id}/members/{user_id}/role", status_code=204)
async def update_group_role(conversation_id: str, user_id: str, payload: GroupRoleRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    _, actor = await _group_access(db, conversation_id, current_user.id)
    target = await db.get(ConversationMember, (conversation_id, user_id))
    if actor.role != "owner" or target is None or target.role == "owner":
        raise HTTPException(status_code=403, detail="Only the owner can change this role")
    target.role = payload.role
    await db.commit()


@router.post("/conversations/{conversation_id}/leave", status_code=204)
async def leave_group(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    conversation, membership = await _group_access(db, conversation_id, current_user.id)
    member_ids = await ChatService(db).get_conversation_member_ids(conversation_id=conversation_id)
    if membership.role == "owner" and len(member_ids) > 1:
        raise HTTPException(status_code=409, detail="Transfer ownership before leaving the group")
    if len(member_ids) == 1:
        await db.delete(conversation)
    else:
        await db.delete(membership)
    await db.commit()
    await manager.send_to_users(
        (member_id for member_id in member_ids if member_id != current_user.id),
        ConversationMemberLeftEvent(
            conversation_id=conversation_id, user_id=current_user.id
        ).model_dump(mode="json"),
    )


@router.post("/conversations/{conversation_id}/owner", status_code=204)
async def transfer_group_owner(conversation_id: str, payload: GroupTransferOwnerRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    conversation, actor = await _group_access(db, conversation_id, current_user.id)
    target = await db.get(ConversationMember, (conversation_id, payload.user_id))
    if actor.role != "owner" or target is None or target.user_id == actor.user_id:
        raise HTTPException(status_code=403, detail="Ownership can only be transferred to another group member")
    actor.role = "admin"
    target.role = "owner"
    conversation.created_by = target.user_id
    await db.commit()


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_group(conversation_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    conversation, membership = await _group_access(db, conversation_id, current_user.id)
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the group owner can delete the group")
    conversation.deleted_at = datetime.now(UTC)
    await db.commit()


@router.patch(
    "/conversations/{conversation_id}/preferences",
    response_model=ConversationResponse,
)
async def update_conversation_preferences(
    conversation_id: str,
    payload: ConversationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    service = ChatService(db)
    try:
        preference = await service.update_conversation_preferences(
            user_id=current_user.id,
            conversation_id=conversation_id,
            is_pinned=payload.is_pinned,
            is_muted=payload.is_muted,
        )
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
    except ChatServiceError as exc:
        raise _message_error(exc) from exc
    return await _conversation_response(
        service,
        conversation,
        profiles=await resolve_profiles(db, conversation_id),
        preference=preference,
    )


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
    settings = await get_or_create_user_settings(db, current_user.id)
    profiles = await resolve_profiles_for_conversations(db, conversation_ids)
    last_messages = await service.get_last_messages(
        conversation_ids=conversation_ids,
        reader_language=current_user.preferred_language,
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
    preferences = await service.get_member_preferences_for_conversations(
        user_id=current_user.id,
        conversation_ids=conversation_ids,
    )
    return [
        await _conversation_response(
            service,
            conversation,
            last_messages.get(conversation.id),
            manager,
            unread.get(conversation.id, 0),
            members.get(conversation.id, []),
            profiles.get(conversation.id, {}),
            preferences.get(conversation.id),
        )
        for conversation in conversations
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Return recent original messages for an authorized conversation member."""
    service = ChatService(db)
    try:
        messages = await service.get_message_history(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=limit,
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

    live_message_ids = [message.id for message in messages if message.deleted_at is None]
    translations = await _translations_by_message(
        db,
        live_message_ids,
        reader_id=current_user.id,
        conversation_id=conversation_id,
    )
    attachments = await service.get_attachments_by_message(message_ids=live_message_ids)
    saved_message_ids = await service.saved_message_ids(
        user_id=current_user.id, message_ids=live_message_ids
    )
    reactions_by_message = await service.reactions_by_message(message_ids=live_message_ids)
    return [
        _message_response(
            message,
            translations=translations.get(message.id, []),
            attachment=attachments.get(message.id),
            is_saved=message.id in saved_message_ids,
            reactions=reactions_by_message.get(message.id, []),
        )
        for message in messages
    ]


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
        source_language=message.source_language,
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
async def retry_message_translation(
    conversation_id: str,
    message_id: str,
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

    schedule_translation_retry(
        message=message,
        reader_id=current_user.id,
        publisher=manager,
    )
    return TranslationRetryResponse(message_id=message_id)


@router.post(
    "/conversations/{conversation_id}/summary",
    response_model=ConversationSummaryResponse,
)
async def summarize_conversation(
    conversation_id: str,
    request: ConversationSummaryRequest = Body(default_factory=ConversationSummaryRequest),
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
            message_limit=request.message_limit,
            target_language=request.target_language,
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
async def extract_actions_from_message_endpoint(
    conversation_id: str,
    message_id: str,
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
async def analyze_message_clarification(
    conversation_id: str,
    message_id: str,
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


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/detect-commitments",
    response_model=list[ActionProposalResponse],
)
async def detect_message_self_commitments(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActionProposalResponse]:
    """Detect proactive first-person self-commitments from a message (B-10)."""
    service = ConversationIntelligenceService()
    try:
        return await service.detect_self_commitments_from_message(
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
        return [ActionProposalResponse.model_validate(p) for p in proposals]
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
        confirmed = await service.confirm_proposal(proposal_id=proposal_id, user_id=current_user.id, corrections=payload.model_dump(exclude_none=True))
        return ActionProposalResponse.model_validate(confirmed)
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
        return ActionProposalResponse.model_validate(rejected)
    except ActionProposalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal was not found",
        ) from exc
    except ActionProposalOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned owner can reject this proposal") from exc
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
        return ActionProposalResponse.model_validate(proposal)
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
    if isinstance(exc, MessageAlreadyDeletedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _call_response(call: CallSession, join: CallJoin | None = None) -> CallResponse:
    """Serialize public call state without leaking a provider credential."""
    return CallResponse(
        call_id=call.id,
        conversation_id=call.conversation_id,
        caller_id=call.caller_id,
        callee_id=call.callee_id,
        call_type=call.call_type,
        status=call.status,
        room_url=join.room_url if join else None,
        join_token=join.join_token if join else None,
        created_at=call.created_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
    )


def _call_event(call: CallSession, event_type: str) -> dict[str, object]:
    """Build the safe WebSocket notification consumed by the call UI."""
    return CallEvent(
        type=event_type,  # type: ignore[arg-type]
        call_id=call.id,
        conversation_id=call.conversation_id,
        caller_id=call.caller_id,
        callee_id=call.callee_id,
        call_type=call.call_type,
        status=call.status,
    ).model_dump(mode="json")


def _call_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CallNotFoundError | ConversationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConversationMembershipError | DirectMessagingBlockedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, RTCProviderUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/conversations/{conversation_id}/calls",
    response_model=CallResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_conversation_call(
    conversation_id: str,
    payload: CallStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> CallResponse:
    """Begin a direct call and notify only the authenticated callee."""
    try:
        provider = get_rtc_provider()
        service = CallService(db, provider)
        join = await service.start_call(
            caller_id=current_user.id,
            conversation_id=conversation_id,
            call_type=payload.call_type,
        )
    except (
        CallNotFoundError,
        CallStateError,
        ConversationNotFoundError,
        ConversationMembershipError,
        DirectMessagingBlockedError,
        RTCProviderUnavailableError,
    ) as exc:
        raise _call_error(exc) from exc

    await manager.send_to_user(join.session.callee_id, _call_event(join.session, "call_incoming"))
    return _call_response(join.session)


@router.post("/calls/{call_id}/accept", response_model=CallResponse)
async def accept_incoming_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> CallResponse:
    """Accept a ringing call and issue the callee's short-lived join token."""
    try:
        provider = get_rtc_provider()
        service = CallService(db, provider)
        join = await service.accept_call(call_id=call_id, user_id=current_user.id)
    except (CallNotFoundError, CallStateError, RTCProviderUnavailableError) as exc:
        # A failed token issue transitions the durable call row to `failed`.
        # Tell the caller immediately instead of leaving their ring UI stuck.
        if isinstance(exc, RTCProviderUnavailableError):
            try:
                service = CallService(db)
                failed_call = await service.get_call(call_id=call_id, user_id=current_user.id)
                await manager.send_to_user(failed_call.caller_id, _call_event(failed_call, "call_failed"))
            except Exception:
                pass
        raise _call_error(exc) from exc

    await manager.send_to_user(join.session.caller_id, _call_event(join.session, "call_accepted"))
    return _call_response(join.session, join)


@router.get("/calls/{call_id}/join", response_model=CallResponse)
async def join_accepted_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    """Issue this authenticated participant's Daily token after acceptance."""
    try:
        provider = get_rtc_provider()
        service = CallService(db, provider)
        join = await service.join_call(call_id=call_id, user_id=current_user.id)
    except (CallNotFoundError, CallStateError, RTCProviderUnavailableError) as exc:
        raise _call_error(exc) from exc
    return _call_response(join.session, join)


@router.post("/calls/{call_id}/reject", response_model=CallResponse)
async def reject_incoming_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> CallResponse:
    """Reject a ringing call and notify its caller."""
    try:
        try:
            provider = get_rtc_provider()
        except RTCProviderUnavailableError:
            provider = None
        service = CallService(db, provider)
        call = await service.reject_call(call_id=call_id, user_id=current_user.id)
    except (CallNotFoundError, CallStateError) as exc:
        raise _call_error(exc) from exc
    await manager.send_to_user(call.caller_id, _call_event(call, "call_rejected"))
    return _call_response(call)


@router.post("/calls/{call_id}/end", response_model=CallResponse)
async def end_active_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> CallResponse:
    """End an active/ringing call for both participants."""
    try:
        try:
            provider = get_rtc_provider()
        except RTCProviderUnavailableError:
            provider = None
        service = CallService(db, provider)
        call = await service.end_call(call_id=call_id, user_id=current_user.id)
    except CallNotFoundError as exc:
        raise _call_error(exc) from exc
    other_id = call.callee_id if current_user.id == call.caller_id else call.caller_id
    await manager.send_to_user(other_id, _call_event(call, "call_ended"))
    return _call_response(call)


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

    reader_settings = await get_or_create_user_settings(db, current_user.id)
    if reader_settings.read_receipts:
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
    schedule_translations(message=message, publisher=manager)

    return MessageResponse(
        id=message.id,
        client_message_id=message.client_message_id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        original_text=message.original_text,
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

    With `consent_to_share`, and only with it, a second and much narrower record
    is written in the background: the term the machine used, the term this
    reader used instead, and a few words around it with identifiers removed.
    That record — not this one — is what the glossary is mined from (ADR-28).
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

    # After the edit is safely stored, and detached from it: this is a
    # by-product, and nothing about mining a glossary may put a reader's own
    # correction at risk. `schedule_correction_record` checks consent itself, so
    # no future call site can forget to.
    profile = await resolve_conversation_profile(db, translation.message_id)
    schedule_correction_record(
        machine_text=translation.translated_text,
        human_text=edit.edited_text,
        source_language=profile.source_language,
        target_language=translation.target_language,
        domain=profile.domain,
        audience=profile.audience,
        user_id=current_user.id,
        translation_id=translation.id,
        consent_to_share=payload.consent_to_share,
    )

    return TranslationEditResponse(
        edit_id=edit.id,
        translation_id=translation.id,
        message_id=translation.message_id,
        target_language=translation.target_language,
        honorific_profile=translation.honorific_profile,
        edited_text=edit.edited_text,
        edited_at=edit.created_at,
    )


async def _translations_by_message(
    db: AsyncSession,
    message_ids: list[str],
    reader_id: str,
    conversation_id: str,
) -> dict[str, list[TranslationSummary]]:
    """Load every translation for a page of messages in one query.

    History is how a client recovers translations it missed while disconnected,
    so this is what keeps a socket dropping mid-translation from losing data.
    Each summary also carries `reader_id`'s own feedback, which is what lets a
    rating button still look rated after a reload.

    Since `honorific_profile` joined the unique key, one message can hold
    several translations into the same language, differing only in how they
    address the reader. This collapses each language back to one row, so the
    array stays the shape docs/CONTRACT.md §3.2 describes and the client is
    never handed two candidates with nothing to choose between them.

    Which row wins is decided by `select_for_reader`, using the standing of
    somebody who actually reads that language: the caller's own for the caller's
    language, and otherwise the first member who reads it. That second half is
    not a nicety — in a `direct` conversation the sender is shown the
    translation the *other* person reads, so the rating and edit controls can
    sit under their own message (§4.4 rule 3, ADR-19), and picking that row with
    the sender's standing would show them a register meant for nobody.

    Args:
        db: Open session.
        message_ids: Messages whose translations are being rendered.
        reader_id: Account whose feedback is attached; never another member's.
        conversation_id: Conversation the messages belong to, needed because a
            standing is only defined inside one.

    Returns:
        Translations grouped by message id, one per target language, in no
        guaranteed order.
    """
    if not message_ids:
        return {}

    # Ordered newest first so the latest translation candidate (from retry/Translate Again)
    # is picked by select_for_reader.
    candidates = list(
        (
            await db.scalars(
                select(TranslationResult)
                .where(TranslationResult.message_id.in_(message_ids))
                .order_by(
                    TranslationResult.version.desc(),
                    TranslationResult.created_at.desc(),
                    TranslationResult.id.desc(),
                )
            )
        ).all()
    )

    profiles = await resolve_profiles(db, conversation_id)
    members = await ChatService(db).get_conversation_members(
        conversation_id=conversation_id
    )
    reader_language = next(
        (
            member.preferred_language
            for member in members
            if member.id == reader_id
        ),
        "",
    )
    reader_settings = await get_or_create_user_settings(db, reader_id)
    # Sorted so that a language read by several members always resolves through
    # the same one of them, however the database happened to return the rows.
    readers_by_language: dict[str, str] = {}
    for member in sorted(members, key=lambda member: member.id):
        readers_by_language.setdefault(member.preferred_language, member.id)

    def standing_for(language: str) -> str:
        """Whose standing decides the wording a given language is rendered in."""
        if language == reader_language:
            return profile_for(profiles, reader_id)
        return profile_for(profiles, readers_by_language.get(language, ""))

    rows = []
    by_message: dict[str, list[TranslationResult]] = {}
    for row in candidates:
        by_message.setdefault(row.message_id, []).append(row)
    for message_rows in by_message.values():
        for language in dict.fromkeys(row.target_language for row in message_rows):
            chosen = select_for_reader(
                message_rows,
                target_language=language,
                honorific_profile=standing_for(language),
                translation_tone=reader_settings.translation_tone,
            )
            if chosen is not None:
                rows.append(chosen)

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
                honorific_profile=row.honorific_profile,
                translation_tone=row.translation_tone,
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
    written = 0
    chunks: list[bytes] = []
    try:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > settings.max_upload_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Attachment exceeds the 20 MB limit",
                )
            chunks.append(chunk)
    finally:
        await file.close()

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    payload = b"".join(chunks)
    object_path = _supabase_storage_path(conversation_id, attachment_id)
    if _supabase_storage_configured():
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    _supabase_object_url(object_path),
                    content=payload,
                    headers=_supabase_storage_headers(content_type),
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Supabase Storage upload failed for %s", attachment_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to store attachment") from exc
    else:
        destination = _attachment_path(conversation_id, attachment_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

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
) -> Response:
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

    attachment = await db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.conversation_id == conversation_id,
        )
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")

    if _supabase_storage_configured():
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    _supabase_object_url(_supabase_storage_path(conversation_id, attachment_id)),
                    headers=_supabase_storage_headers(),
                )
            if _supabase_object_missing(response):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
            response.raise_for_status()
            return Response(
                content=response.content,
                media_type=attachment.content_type,
                headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
            )
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            logger.exception("Supabase Storage download failed for %s", attachment_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to retrieve attachment") from exc

    path = _attachment_path(conversation_id, attachment_id)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment was not found")
    return FileResponse(path, filename=attachment.filename, media_type=attachment.content_type)

