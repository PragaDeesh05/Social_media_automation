import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, Campaign
from app.api.deps import get_current_user
from app.services.analytics.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])


@router.get("/campaign/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns verified metrics, distinguishing unavailable metrics from zero values."""
    camp_stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    camp_res = await db.execute(camp_stmt)
    if not camp_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Campaign not found")

    metrics = await analytics_service.get_campaign_analytics(db, str(campaign_id))
    return metrics
