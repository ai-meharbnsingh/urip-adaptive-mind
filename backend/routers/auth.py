import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import create_access_token, get_current_user, verify_password
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse, UserProfile

router = APIRouter()

# ─── Rate Limiting ────────────────────────────────────────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 900  # 15 minutes
RATE_LIMIT_MAX = 5


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    attempts = _login_attempts[ip]
    # Clean old attempts
    _login_attempts[ip] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    return len(_login_attempts[ip]) < RATE_LIMIT_MAX


def record_failed_attempt(ip: str):
    _login_attempts[ip].append(time.time())


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    client_ip = req.client.host if req.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again in 15 minutes.",
        )

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Embed tenant_id in JWT — str() works whether tenant_id is UUID or None (legacy users)
    tenant_id_str = str(user.tenant_id) if user.tenant_id else None
    token = create_access_token(str(user.id), user.role, tenant_id=tenant_id_str)
    return TokenResponse(
        access_token=token,
        user=UserProfile(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            team=user.team,
        ),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        team=current_user.team,
    )
