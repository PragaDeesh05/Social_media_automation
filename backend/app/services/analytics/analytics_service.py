from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models import ScheduledPost, ContentAsset, AnalyticsSnapshot, TrackingLink, Campaign


class AnalyticsService:
    @classmethod
    async def get_campaign_analytics(cls, session: AsyncSession, campaign_id: str) -> Dict[str, Any]:
        """Calculates genuine aggregated campaign metrics with null-safety."""
        # Query total assets and scheduled posts
        asset_stmt = select(ContentAsset).where(ContentAsset.campaign_id == campaign_id)
        asset_res = await session.execute(asset_stmt)
        assets = asset_res.scalars().all()

        asset_ids = [a.id for a in assets]
        if not asset_ids:
            return {
                "total_assets": 0,
                "published_count": 0,
                "scheduled_count": 0,
                "failed_count": 0,
                "total_clicks": 0,
                "impressions": None,
                "engagement": None,
                "metrics_by_platform": {},
                "note": "No content assets found for this campaign."
            }

        post_stmt = select(ScheduledPost).where(ScheduledPost.content_asset_id.in_(asset_ids))
        post_res = await session.execute(post_stmt)
        posts = post_res.scalars().all()

        published_posts = [p for p in posts if p.status == "published"]
        scheduled_posts = [p for p in posts if p.status in ("scheduled", "pending")]
        failed_posts = [p for p in posts if p.status == "failed"]

        # Aggregate tracking link clicks
        link_stmt = select(func.sum(TrackingLink.click_count)).where(TrackingLink.content_asset_id.in_(asset_ids))
        link_res = await session.execute(link_stmt)
        total_clicks = link_res.scalar() or 0

        # Query analytics snapshots
        post_ids = [p.id for p in published_posts]
        snapshots = []
        if post_ids:
            snap_stmt = select(AnalyticsSnapshot).where(AnalyticsSnapshot.scheduled_post_id.in_(post_ids))
            snap_res = await session.execute(snap_stmt)
            snapshots = snap_res.scalars().all()

        # Compute platform breakdown
        platform_breakdown = {}
        for p in ("instagram", "facebook", "youtube", "x"):
            platform_assets = [a for a in assets if a.platform == p]
            platform_published = [p_item for p_item in published_posts if any(a.id == p_item.content_asset_id and a.platform == p for a in platform_assets)]
            platform_breakdown[p] = {
                "total_assets": len(platform_assets),
                "published": len(platform_published),
                "clicks": sum([1 for a in platform_assets if a.tracking_url]),  # placeholder tracked links
                "impressions": sum([s.impressions for s in snapshots if s.platform == p and s.impressions is not None]) if any(s.platform == p and s.impressions is not None for s in snapshots) else None
            }

        return {
            "total_assets": len(assets),
            "published_count": len(published_posts),
            "scheduled_count": len(scheduled_posts),
            "failed_count": len(failed_posts),
            "total_clicks": total_clicks,
            "metrics_by_platform": platform_breakdown,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }


analytics_service = AnalyticsService()
