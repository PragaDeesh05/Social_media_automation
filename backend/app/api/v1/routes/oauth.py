import uuid
import re
import os
import secrets
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_token
from app.db.session import get_db
from app.db.models import User, ConnectedAccount, OAuthCredential, ScheduledPost, ContentAsset, Campaign
from app.api.deps import get_current_user
from app.integrations.meta.meta_client import meta_client
from app.integrations.youtube.youtube_client import youtube_client
from app.integrations.x.x_client import x_client
from app.core.logging import logger

router = APIRouter(prefix="/oauth", tags=["OAuth & Platform Connections"])

# In-memory or redis state storage for CSRF protection
OAUTH_STATES: Dict[str, Dict[str, Any]] = {}


def is_valid_client_id(val: Optional[str]) -> bool:
    """Returns True if client ID is non-empty and not a dummy/placeholder value."""
    if not val:
        return False
    val_lower = val.strip().lower()
    placeholders = ["incubrix_", "your-", "dummy", "placeholder", "xxx", "none", "client_id"]
    return not any(val_lower.startswith(p) for p in placeholders)


def mask_secret(val: Optional[str]) -> str:
    if not val or not is_valid_client_id(val):
        return "Not Configured"
    if len(val) <= 8:
        return "••••••••"
    return f"{val[:4]}••••{val[-4:]}"


async def auto_link_scheduled_posts(db: AsyncSession, user_id: uuid.UUID, platform: str, account_id: uuid.UUID):
    """Auto-links pending/failed scheduled posts for this user and platform to the newly connected account."""
    try:
        stmt = (
            select(ScheduledPost)
            .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
            .join(Campaign, ContentAsset.campaign_id == Campaign.id)
            .where(
                Campaign.user_id == user_id,
                ContentAsset.platform == platform.lower()
            )
        )
        res = await db.execute(stmt)
        posts = res.scalars().all()
        linked_count = 0
        for p in posts:
            p.connected_account_id = account_id
            if p.status == "failed" and ("Cannot publish live" in (p.last_error or "") or "No active OAuth" in (p.last_error or "")):
                p.status = "scheduled"
                p.last_error = None
                p.retry_count = 0
                p.next_retry_at = None
                linked_count += 1
            else:
                linked_count += 1
        if linked_count > 0:
            logger.info(f"Auto-linked {linked_count} scheduled post(s) to connected account {account_id} for platform {platform}")
    except Exception as e:
        logger.error(f"Error in auto_link_scheduled_posts: {e}")


class PlatformCredentialsInput(BaseModel):
    client_id: str
    client_secret: str


class ManualConnectInput(BaseModel):
    account_name: str
    username: Optional[str] = None
    account_id: Optional[str] = None
    access_token: Optional[str] = None
    account_type: Optional[str] = "standard"
    platform_subtype: Optional[str] = None  # for meta: 'facebook' or 'instagram'


SETUP_GUIDES = {
    "youtube": {
        "title": "Google Cloud Console Setup",
        "doc_url": "https://console.cloud.google.com/apis/credentials",
        "steps": [
            "1. Open Google Cloud Console and select or create a project.",
            "2. Navigate to 'APIs & Services' > 'Library' and enable 'YouTube Data API v3'.",
            "3. Go to 'APIs & Services' > 'OAuth consent screen' and configure as External (or Internal).",
            "4. Go to 'Credentials' > 'Create Credentials' > 'OAuth client ID'.",
            "5. Select Application type: 'Web application'.",
            f"6. Add Authorized redirect URI: {settings.YOUTUBE_REDIRECT_URI}",
            "7. Paste the Client ID and Client Secret into the IncuBrix Live OAuth tab."
        ]
    },
    "meta": {
        "title": "Meta for Developers Setup",
        "doc_url": "https://developers.facebook.com/apps",
        "steps": [
            "1. Go to developers.facebook.com and create an App of type 'Business'.",
            "2. Add the 'Facebook Login for Business' product.",
            f"3. Under Facebook Login > Settings, add Valid OAuth Redirect URI: {settings.META_REDIRECT_URI}",
            "4. Go to App Settings > Basic to find your App ID and App Secret.",
            "5. Paste the App ID and App Secret into the IncuBrix Live OAuth tab."
        ]
    },
    "x": {
        "title": "X Developer Portal Setup",
        "doc_url": "https://developer.x.com/en/portal/dashboard",
        "steps": [
            "1. Log in to the X Developer Portal with Developer account privileges.",
            "2. Create a Project and an App, then navigate to 'User authentication settings'.",
            "3. Enable OAuth 2.0 with App permissions 'Read and write'.",
            "4. Set Type of App to 'Web App, Automated App or Bot'.",
            f"5. Add Callback URI: {settings.X_REDIRECT_URI}",
            "6. Copy your Client ID and Client Secret into the IncuBrix Live OAuth tab."
        ]
    }
}


@router.get("/status")
async def get_oauth_status():
    """Returns credential configuration status and setup guides for all supported platforms."""
    return {
        "youtube": {
            "platform": "youtube",
            "name": "YouTube Data API v3",
            "is_configured": is_valid_client_id(settings.YOUTUBE_CLIENT_ID),
            "client_id_masked": mask_secret(settings.YOUTUBE_CLIENT_ID),
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "setup_guide": SETUP_GUIDES["youtube"]
        },
        "meta": {
            "platform": "meta",
            "name": "Meta Graph API (Facebook & Instagram)",
            "is_configured": is_valid_client_id(settings.META_APP_ID),
            "client_id_masked": mask_secret(settings.META_APP_ID),
            "redirect_uri": settings.META_REDIRECT_URI,
            "setup_guide": SETUP_GUIDES["meta"]
        },
        "x": {
            "platform": "x",
            "name": "X API v2",
            "is_configured": is_valid_client_id(settings.X_CLIENT_ID),
            "client_id_masked": mask_secret(settings.X_CLIENT_ID),
            "redirect_uri": settings.X_REDIRECT_URI,
            "setup_guide": SETUP_GUIDES["x"]
        }
    }


@router.post("/{platform}/credentials")
async def save_platform_credentials(
    platform: str,
    payload: PlatformCredentialsInput,
    current_user: User = Depends(get_current_user)
):
    """Saves official platform Client ID and Secret to active runtime settings and .env."""
    platform = platform.lower()
    cid = payload.client_id.strip()
    sec = payload.client_secret.strip()

    if not cid or not sec:
        raise HTTPException(status_code=400, detail="Client ID and Client Secret are required.")

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")

    if platform == "youtube":
        settings.YOUTUBE_CLIENT_ID = cid
        settings.YOUTUBE_CLIENT_SECRET = sec
        _update_env_keys(env_path, {"YOUTUBE_CLIENT_ID": cid, "YOUTUBE_CLIENT_SECRET": sec})
    elif platform == "meta":
        settings.META_APP_ID = cid
        settings.META_APP_SECRET = sec
        _update_env_keys(env_path, {"META_APP_ID": cid, "META_APP_SECRET": sec})
    elif platform == "x":
        settings.X_CLIENT_ID = cid
        settings.X_CLIENT_SECRET = sec
        _update_env_keys(env_path, {"X_CLIENT_ID": cid, "X_CLIENT_SECRET": sec})
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    logger.info(f"Updated credentials for {platform.upper()} by user {current_user.email}")
    return {
        "success": True,
        "platform": platform,
        "message": f"Successfully updated and saved {platform.upper()} OAuth credentials."
    }


def _update_env_keys(env_file_path: str, key_values: Dict[str, str]):
    if not os.path.exists(env_file_path):
        return
    with open(env_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    for k, v in key_values.items():
        pattern = re.compile(rf"^{k}=.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{k}={v}", content)
        else:
            content += f"\n{k}={v}"

    with open(env_file_path, "w", encoding="utf-8") as f:
        f.write(content)


@router.get("/{platform}/authorize")
async def start_oauth_flow(
    platform: str,
    request: Request,
    redirect: bool = Query(False),
    current_user: User = Depends(get_current_user)
):
    """
    Initiates official OAuth 2.0 flow with state CSRF protection.
    If requested by a browser (Accept: text/html) or redirect=true, directly redirects to Google/Meta.
    Otherwise returns JSON with authorization_url.
    """
    platform = platform.lower()
    state = secrets.token_urlsafe(24)

    is_browser = redirect or "text/html" in request.headers.get("accept", "")

    if platform == "meta":
        if not is_valid_client_id(settings.META_APP_ID):
            return {
                "is_configured": False,
                "platform": "meta",
                "error": "OAUTH_CLIENT_NOT_CONFIGURED",
                "detail": "Meta App ID is not configured or is a placeholder.",
                "redirect_uri": settings.META_REDIRECT_URI,
                "setup_guide": SETUP_GUIDES["meta"]
            }
        OAUTH_STATES[state] = {"user_id": current_user.id, "platform": "meta"}
        auth_url = meta_client.get_authorization_url(state)
        if is_browser:
            return RedirectResponse(auth_url)
        return {"is_configured": True, "authorization_url": auth_url, "state": state}

    elif platform == "youtube":
        if not is_valid_client_id(settings.YOUTUBE_CLIENT_ID):
            return {
                "is_configured": False,
                "platform": "youtube",
                "error": "OAUTH_CLIENT_NOT_CONFIGURED",
                "detail": "YouTube Google Cloud Client ID is not configured or is a placeholder.",
                "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
                "setup_guide": SETUP_GUIDES["youtube"]
            }
        OAUTH_STATES[state] = {"user_id": current_user.id, "platform": "youtube"}
        auth_url = youtube_client.get_authorization_url(state)
        if is_browser:
            return RedirectResponse(auth_url)
        return {"is_configured": True, "authorization_url": auth_url, "state": state}

    elif platform == "x":
        if not is_valid_client_id(settings.X_CLIENT_ID):
            return {
                "is_configured": False,
                "platform": "x",
                "error": "OAUTH_CLIENT_NOT_CONFIGURED",
                "detail": "X Client ID is not configured or is a placeholder.",
                "redirect_uri": settings.X_REDIRECT_URI,
                "setup_guide": SETUP_GUIDES["x"]
            }
        pkce = x_client.generate_pkce_pair()
        OAUTH_STATES[state] = {
            "user_id": current_user.id,
            "platform": "x",
            "code_verifier": pkce["code_verifier"]
        }
        auth_url = x_client.get_authorization_url(state, pkce["code_challenge"])
        return {"is_configured": True, "authorization_url": auth_url, "state": state}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth platform: {platform}")


@router.post("/{platform}/connect-manual")
async def connect_manual_account(
    platform: str,
    payload: ManualConnectInput,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Connects a platform account using developer tokens or evaluation environment sandbox credentials.
    Permits full end-to-end testing of publishing, permissions, and scheduling workflows without third-party redirects.
    """
    platform = platform.lower()
    raw_token = payload.access_token or f"dev_token_{platform}_{secrets.token_hex(16)}"
    account_id = payload.account_id or f"{platform}_{uuid.uuid4().hex[:10]}"
    username = payload.username or f"@{payload.account_name.lower().replace(' ', '_')}"

    connected_records = []

    if platform == "youtube":
        account_name = payload.account_name
        profile_image = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150&auto=format&fit=crop"

        # If live Google OAuth token provided, verify directly with Google API
        if raw_token.startswith("ya29."):
            try:
                channels = await youtube_client.get_channels(raw_token)
                if channels:
                    ch = channels[0]
                    account_id = ch["account_id"]
                    account_name = ch["account_name"]
                    username = ch.get("username") or username
                    profile_image = ch.get("profile_image_url") or profile_image
                    logger.info(f"Verified live YouTube channel via Google API: {account_name} ({account_id})")
            except Exception as e:
                logger.warning(f"Could not fetch YouTube channel via token: {e}")

        conn = ConnectedAccount(
            user_id=current_user.id,
            platform="youtube",
            account_id=account_id,
            account_name=account_name,
            username=username,
            account_type=payload.account_type or "channel",
            status="connected",
            permissions=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"],
            scopes=["youtube.upload", "youtube.readonly"],
            profile_image_url=profile_image
        )
        db.add(conn)
        await db.flush()

        cred = OAuthCredential(
            connected_account_id=conn.id,
            encrypted_access_token=encrypt_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=90)
        )
        db.add(cred)
        connected_records.append(conn)

    elif platform == "meta":
        subtype = payload.platform_subtype or "both"
        fb_page_id = payload.account_id or account_id
        ig_user_id = payload.account_id or account_id
        fb_token = raw_token
        ig_token = raw_token

        # If live Meta token provided (starts with EAA), discover connected Page and Instagram account
        if raw_token.startswith("EAA"):
            try:
                meta_accs = await meta_client.get_accounts_and_pages(raw_token)
                for ma in meta_accs:
                    if ma.get("platform") == "facebook" and not payload.account_id:
                        fb_page_id = ma["account_id"]
                        fb_token = ma.get("page_access_token", raw_token)
                    elif ma.get("platform") == "instagram":
                        ig_user_id = ma["account_id"]
                        ig_token = ma.get("page_access_token", raw_token)
            except Exception as e:
                logger.warning(f"Could not discover Meta accounts via live token: {e}")

        if subtype in ("facebook", "both"):
            fb_conn = ConnectedAccount(
                user_id=current_user.id,
                platform="facebook",
                account_id=fb_page_id,
                account_name=f"{payload.account_name} (Facebook Page)",
                username=username,
                account_type="page",
                status="connected",
                permissions=["pages_manage_posts", "pages_read_engagement", "pages_show_list"],
                scopes=["pages_manage_posts", "pages_read_engagement"],
                profile_image_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150&auto=format&fit=crop"
            )
            db.add(fb_conn)
            await db.flush()
            db.add(OAuthCredential(
                connected_account_id=fb_conn.id,
                encrypted_access_token=encrypt_token(fb_token),
                expires_at=datetime.now(timezone.utc) + timedelta(days=90)
            ))
            connected_records.append(fb_conn)

        if subtype in ("instagram", "both"):
            ig_conn = ConnectedAccount(
                user_id=current_user.id,
                platform="instagram",
                account_id=ig_user_id,
                account_name=f"{payload.account_name} (Instagram Professional)",
                username=username,
                account_type="professional",
                status="connected",
                permissions=["instagram_content_publish", "instagram_basic"],
                scopes=["instagram_content_publish", "instagram_basic"],
                profile_image_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150&auto=format&fit=crop"
            )
            db.add(ig_conn)
            await db.flush()
            db.add(OAuthCredential(
                connected_account_id=ig_conn.id,
                encrypted_access_token=encrypt_token(ig_token),
                expires_at=datetime.now(timezone.utc) + timedelta(days=90)
            ))
            connected_records.append(ig_conn)

    elif platform == "x":
        x_conn = ConnectedAccount(
            user_id=current_user.id,
            platform="x",
            account_id=account_id,
            account_name=payload.account_name,
            username=username,
            account_type=payload.account_type or "standard",
            status="connected",
            permissions=["tweet.write", "tweet.read", "users.read"],
            scopes=["tweet.write", "tweet.read", "users.read", "offline.access"],
            profile_image_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150&auto=format&fit=crop"
        )
        db.add(x_conn)
        await db.flush()
        db.add(OAuthCredential(
            connected_account_id=x_conn.id,
            encrypted_access_token=encrypt_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=90)
        ))
        connected_records.append(x_conn)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    for r in connected_records:
        await auto_link_scheduled_posts(db, current_user.id, r.platform, r.id)

    await db.commit()
    logger.info(f"Connected manual account for {platform} (User: {current_user.email})")

    return {
        "success": True,
        "connected_count": len(connected_records),
        "accounts": [
            {
                "id": str(r.id),
                "platform": r.platform,
                "account_name": r.account_name,
                "username": r.username,
                "status": r.status,
                "permissions": r.permissions
            }
            for r in connected_records
        ]
    }


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Handles OAuth callback, token exchange, account discovery, and encrypted token storage."""
    platform = platform.lower()
    if error:
        logger.error(f"OAuth error returned by {platform}: {error} - {error_description}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connected-accounts?error={error}")

    if not state or state not in OAUTH_STATES:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state parameter (CSRF protection failed)")

    state_info = OAUTH_STATES.pop(state)
    user_id = state_info["user_id"]

    try:
        if platform == "meta":
            token_data = await meta_client.exchange_code_for_token(code)
            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 5184000)

            # Discover Facebook pages and Instagram accounts
            accounts = await meta_client.get_accounts_and_pages(access_token)
            if not accounts:
                accounts = [{
                    "platform": "facebook",
                    "account_id": f"fb_user_{uuid.uuid4().hex[:8]}",
                    "account_name": "Connected Meta Account",
                    "account_type": "page",
                    "page_access_token": access_token,
                    "permissions": ["pages_manage_posts"]
                }]

            for acc in accounts:
                p_token = acc.get("page_access_token", access_token)
                conn = ConnectedAccount(
                    user_id=user_id,
                    platform=acc["platform"],
                    account_id=acc["account_id"],
                    account_name=acc["account_name"],
                    username=acc.get("username"),
                    account_type=acc.get("account_type", "page"),
                    status="connected",
                    permissions=acc.get("permissions", []),
                    profile_image_url=acc.get("profile_image_url")
                )
                db.add(conn)
                await db.flush()

                cred = OAuthCredential(
                    connected_account_id=conn.id,
                    encrypted_access_token=encrypt_token(p_token),
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                )
                db.add(cred)
                await auto_link_scheduled_posts(db, user_id, acc["platform"], conn.id)

            await db.commit()

            # Update .env with fresh active tokens
            try:
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), ".env")
                env_updates = {"YOUTUBE_ACCESS_TOKEN": access_token}
                if refresh_token:
                    env_updates["YOUTUBE_REFRESH_TOKEN"] = refresh_token
                _update_env_keys(env_path, env_updates)
                logger.info("Saved fresh YouTube tokens to .env file.")
            except Exception as e:
                logger.warning(f"Could not persist fresh YouTube tokens to .env: {e}")

        elif platform == "youtube":
            tokens = await youtube_client.exchange_code_for_tokens(code)
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)

            channels = await youtube_client.get_channels(access_token)
            if not channels:
                channels = [{
                    "platform": "youtube",
                    "account_id": f"yt_channel_{uuid.uuid4().hex[:8]}",
                    "account_name": "Official YouTube Channel",
                    "account_type": "channel",
                    "permissions": ["https://www.googleapis.com/auth/youtube.upload"]
                }]

            for ch in channels:
                conn = ConnectedAccount(
                    user_id=user_id,
                    platform="youtube",
                    account_id=ch["account_id"],
                    account_name=ch["account_name"],
                    username=ch.get("username"),
                    account_type="channel",
                    status="connected",
                    permissions=["https://www.googleapis.com/auth/youtube.upload"],
                    profile_image_url=ch.get("profile_image_url")
                )
                db.add(conn)
                await db.flush()

                cred = OAuthCredential(
                    connected_account_id=conn.id,
                    encrypted_access_token=encrypt_token(access_token),
                    encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                )
                db.add(cred)
                await auto_link_scheduled_posts(db, user_id, "youtube", conn.id)

            await db.commit()

            # Update .env with fresh active tokens
            try:
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), ".env")
                env_updates = {"YOUTUBE_ACCESS_TOKEN": access_token}
                if refresh_token:
                    env_updates["YOUTUBE_REFRESH_TOKEN"] = refresh_token
                _update_env_keys(env_path, env_updates)
                logger.info("Saved fresh YouTube tokens to .env file.")
            except Exception as e:
                logger.warning(f"Could not persist fresh YouTube tokens to .env: {e}")

        elif platform == "x":
            code_verifier = state_info.get("code_verifier", "")
            tokens = await x_client.exchange_code_for_token(code, code_verifier)
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 7200)

            user_profile = await x_client.get_me(access_token)
            account_id = user_profile.get("account_id") or f"x_user_{uuid.uuid4().hex[:8]}"
            account_name = user_profile.get("account_name") or "Connected X Account"

            conn = ConnectedAccount(
                user_id=user_id,
                platform="x",
                account_id=account_id,
                account_name=account_name,
                username=user_profile.get("username"),
                account_type="standard",
                status="connected",
                permissions=["tweet.write", "tweet.read"],
                profile_image_url=user_profile.get("profile_image_url")
            )
            db.add(conn)
            await db.flush()

            cred = OAuthCredential(
                connected_account_id=conn.id,
                encrypted_access_token=encrypt_token(access_token),
                encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            )
            db.add(cred)
            await auto_link_scheduled_posts(db, user_id, "x", conn.id)
            await db.commit()

            # Update .env with fresh active tokens
            try:
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), ".env")
                env_updates = {"YOUTUBE_ACCESS_TOKEN": access_token}
                if refresh_token:
                    env_updates["YOUTUBE_REFRESH_TOKEN"] = refresh_token
                _update_env_keys(env_path, env_updates)
                logger.info("Saved fresh YouTube tokens to .env file.")
            except Exception as e:
                logger.warning(f"Could not persist fresh YouTube tokens to .env: {e}")

        return RedirectResponse(f"{settings.FRONTEND_URL}/connected-accounts?status=success&platform={platform}")

    except Exception as e:
        logger.error(f"Error completing OAuth callback for {platform}: {e}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connected-accounts?error={urllib.parse.quote(str(e))}")
