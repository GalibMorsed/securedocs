import re
import uuid
from unicodedata import normalize

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Organization, OrganizationMember, User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


def _organization_slug(name: str) -> str:
    ascii_name = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:88]
    return f"{base or 'organization'}-{uuid.uuid4().hex[:8]}"


def _issue_auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user and create their organization",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    organization = Organization(
        name=payload.organization_name,
        slug=_organization_slug(payload.organization_name),
    )
    membership = OrganizationMember(
        organization=organization,
        user=user,
        role="owner",
    )
    db.add_all([user, organization, membership])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # A concurrent registration can race with the preflight email lookup.
        if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            ) from exc
        raise

    db.refresh(user)
    return _issue_auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in and receive a bearer access token",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or not verify_password(payload.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_auth_response(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the authenticated user",
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
