from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token, get_current_user, is_admin_user
from app.schemas import SignupRequest, LoginRequest, TokenResponse, UserOut
from app.rate_limit import limiter, AUTH_LIMIT

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, state=user.state, age=user.age,
        occupation=user.occupation, annual_income=user.annual_income, gender=user.gender,
        category=user.category, is_admin=is_admin_user(user),
    )


@router.post("/signup", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An account with this email already exists")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return _to_user_out(current_user)


@router.put("/me", response_model=UserOut)
def update_profile(
    profile: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile fields used for personalized recommendations (all optional)."""
    allowed_fields = {"name", "state", "age", "occupation", "annual_income", "gender", "category"}
    for key, value in profile.items():
        if key in allowed_fields:
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return _to_user_out(current_user)
