import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, ConnectedAccount, OAuthCredential
from app.api.deps import get_current_user
from app.services.publishing.platform_registry import get_platform_capability

router = APIRouter(prefix="/connected-accounts", tags=["Connected Accounts"])


@router.get("")
async def list_connected_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists connected platform accounts with live token status and capability checks."""
    stmt = (
        select(ConnectedAccount)
        .where(ConnectedAccount.user_id == current_user.id)
        .order_by(ConnectedAccount.created_at.desc())
    )
    res = await db.execute(stmt)
    accounts = res.scalars().all()

    output = []
    for acc in accounts:
        cred_res = await db.execute(select(OAuthCredential).where(OAuthCredential.connected_account_id == acc.id))
        cred = cred_res.scalar_one_or_none()

        has_token = cred is not None and bool(cred.encrypted_access_token)
        is_expired = False
        if cred and cred.expires_at:
            from datetime import datetime, timezone
            is_expired = cred.expires_at <= datetime.now(timezone.utc)

        output.append({
            "id": acc.id,
            "platform": acc.platform,
            "account_id": acc.account_id,
            "account_name": acc.account_name,
            "username": acc.username,
            "account_type": acc.account_type,
            "status": "expired" if is_expired else acc.status,
            "has_token": has_token,
            "is_expired": is_expired,
            "permissions": acc.permissions,
            "scopes": acc.scopes,
            "profile_image_url": acc.profile_image_url,
            "capabilities": get_platform_capability(acc.platform),
            "created_at": acc.created_at.isoformat()
        })

    return output


@router.delete("/{account_id}")
async def disconnect_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnects and safely deletes account and OAuth token."""
    stmt = select(ConnectedAccount).where(ConnectedAccount.id == account_id, ConnectedAccount.user_id == current_user.id)
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    await db.delete(account)
    await db.commit()
    return {"success": True, "message": f"Successfully disconnected {account.platform.upper()} account."}
