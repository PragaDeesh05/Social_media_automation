from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.db.session import get_db
from app.db.models import User, BrandProfile
from app.schemas.common import BrandProfileSchema
from app.api.deps import get_current_user

router = APIRouter(prefix="/brand-profiles", tags=["Brand Profiles"])


@router.get("", response_model=List[BrandProfileSchema])
async def list_brand_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(BrandProfile).where(BrandProfile.user_id == current_user.id)
    res = await db.execute(stmt)
    profiles = res.scalars().all()
    return [BrandProfileSchema.model_validate(p) for p in profiles]


@router.post("", response_model=BrandProfileSchema)
async def create_brand_profile(
    profile_in: BrandProfileSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    profile = BrandProfile(
        user_id=current_user.id,
        brand_name=profile_in.brand_name,
        target_audience=profile_in.target_audience,
        tone_of_voice=profile_in.tone_of_voice,
        vocabulary_rules=profile_in.vocabulary_rules,
        words_to_avoid=profile_in.words_to_avoid,
        default_cta=profile_in.default_cta,
        primary_color=profile_in.primary_color,
        secondary_color=profile_in.secondary_color,
        verified_product_facts=profile_in.verified_product_facts
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return BrandProfileSchema.model_validate(profile)


@router.put("/{profile_id}", response_model=BrandProfileSchema)
async def update_brand_profile(
    profile_id: uuid.UUID,
    profile_in: BrandProfileSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(BrandProfile).where(BrandProfile.id == profile_id, BrandProfile.user_id == current_user.id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    for k, v in profile_in.model_dump(exclude_unset=True).items():
        if k != "id":
            setattr(profile, k, v)

    await db.commit()
    await db.refresh(profile)
    return BrandProfileSchema.model_validate(profile)
