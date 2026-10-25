from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, BrandProfile
from app.schemas.common import UserCreate, UserLogin, UserResponse, Token, APIResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.exceptions import AuthenticationError
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == user_in.email.lower().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email is already registered")

    user = User(
        email=user_in.email.lower().strip(),
        full_name=user_in.full_name.strip(),
        hashed_password=get_password_hash(user_in.password),
        is_active=True
    )
    db.add(user)
    await db.flush()

    # Create default brand profile for new user
    brand = BrandProfile(
        user_id=user.id,
        brand_name=user.full_name or "My Brand",
        target_audience="Creators, Marketers, Founders",
        tone_of_voice="Educational, Action-Oriented, High-Signal",
        default_cta="Learn more → incubrix.com/start",
        verified_product_facts=["Automated multi-platform content repurposing engine."]
    )
    db.add(brand)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == user_in.email.lower().strip()))
    user = res.scalar_one_or_none()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password")

    token = create_access_token(user.id)
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
