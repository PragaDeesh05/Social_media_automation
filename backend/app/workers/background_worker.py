import asyncio
import signal
import sys
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.db.models import ScheduledPost, ContentAsset, BackgroundJob
from app.services.publishing.publisher_service import publisher_service

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Received termination signal. Shutting down worker gracefully...")
    running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


async def process_due_scheduled_posts(session: AsyncSession):
    """
    Finds and atomically claims due scheduled posts using row-level locking.
    Prevents race conditions and duplicate publishing across concurrent workers.
    """
    now_utc = datetime.now(timezone.utc)

    # Query due posts
    stmt = (
        select(ScheduledPost)
        .where(
            and_(
                ScheduledPost.status.in_(["scheduled", "pending"]),
                or_(
                    ScheduledPost.next_retry_at.is_(None),
                    ScheduledPost.next_retry_at <= now_utc
                ),
                ScheduledPost.scheduled_utc <= now_utc
            )
        )
        .with_for_update(skip_locked=True)
        .limit(10)
    )

    result = await session.execute(stmt)
    due_posts = result.scalars().all()

    if not due_posts:
        return

    logger.info(f"Worker claimed {len(due_posts)} due post(s) for publishing")

    for post in due_posts:
        # Check asset approval
        asset_res = await session.execute(select(ContentAsset).where(ContentAsset.id == post.content_asset_id))
        asset = asset_res.scalar_one_or_none()

        if not asset or asset.approval_status != "approved":
            logger.info(f"Skipping post {post.id}: Content asset approval is '{getattr(asset, 'approval_status', 'none')}' (requires 'approved')")
            continue

        # Mark post as publishing
        post.status = "publishing"
        await session.commit()

        # Execute publish
        try:
            pub_res = await publisher_service.publish_scheduled_post(session, post.id)
            logger.info(f"Publish execution for post {post.id} completed: success={pub_res.get('success')}")
        except Exception as e:
            logger.error(f"Unexpected error publishing post {post.id}: {e}")
            post.status = "failed"
            post.last_error = str(e)
            await session.commit()


async def run_worker():
    logger.info("==================================================================")
    logger.info(" IncuBrix Social Engine Background Worker Started (Python 3.13)   ")
    logger.info(f" Poll Interval: {settings.SCHEDULER_POLL_INTERVAL_SECONDS}s | DB: {settings.DATABASE_URL.split('@')[-1]} ")
    logger.info("==================================================================")

    while running:
        try:
            async with AsyncSessionLocal() as session:
                await process_due_scheduled_posts(session)
        except Exception as e:
            logger.error(f"Worker loop exception: {e}")

        # Sleep interval
        await asyncio.sleep(settings.SCHEDULER_POLL_INTERVAL_SECONDS)

    logger.info("IncuBrix Background Worker exited cleanly.")


if __name__ == "__main__":
    asyncio.run(run_worker())
