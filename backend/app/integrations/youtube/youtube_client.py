import urllib.parse
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import IncuBrixException


class YouTubeClient:
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3/videos"

    @classmethod
    def get_authorization_url(cls, state: str) -> str:
        """Builds YouTube Data API OAuth 2.0 authorization URL."""
        if not settings.YOUTUBE_CLIENT_ID:
            raise IncuBrixException(status_code=400, detail="YOUTUBE_CLIENT_ID is not configured in environment")

        params = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state
        }
        return f"{cls.AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def exchange_code_for_tokens(cls, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for access and refresh tokens."""
        payload = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cls.TOKEN_ENDPOINT, data=payload)
            if resp.status_code != 200:
                logger.error(f"YouTube token exchange failed: {resp.text}")
                raise IncuBrixException(
                    status_code=400,
                    detail=f"YouTube token exchange failed: {resp.json().get('error_description', resp.text)}"
                )
            return resp.json()

    @classmethod
    async def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Refreshes an expired Google OAuth access token using a refresh token."""
        payload = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cls.TOKEN_ENDPOINT, data=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"YouTube token refresh failed: {resp.text}")
            return {}

    @classmethod
    async def get_channels(cls, access_token: str) -> List[Dict[str, Any]]:
        """Retrieves user's YouTube channels."""
        url = f"{cls.API_BASE}/channels"
        params = {"part": "snippet,statistics", "mine": "true"}
        headers = {"Authorization": f"Bearer {access_token}"}
        channels = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            items = resp.json().get("items", [])
            for item in items:
                snippet = item.get("snippet", {})
                channels.append({
                    "platform": "youtube",
                    "account_id": item.get("id"),
                    "account_name": snippet.get("title"),
                    "username": snippet.get("customUrl"),
                    "account_type": "channel",
                    "profile_image_url": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                    "permissions": ["youtube.upload"]
                })
        return channels

    @classmethod
    async def upload_video(
        cls,
        access_token: str,
        video_bytes: bytes,
        title: str,
        description: str,
        tags: List[str],
        privacy_status: str = "public"
    ) -> Dict[str, Any]:
        """Uploads video / Shorts to YouTube Data API v3."""
        # Add #Shorts hashtag to title or description for vertical short videos
        if "#Shorts" not in title and "#Shorts" not in description:
            title = f"{title[:85]} #Shorts"

        metadata = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags[:15],
                "categoryId": "27"  # Education
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        # Developer Sandbox / Quick Connect mode (when live Google OAuth tokens are not configured)
        if access_token.startswith("dev_token_") or access_token.startswith("sandbox_"):
            import uuid
            logger.info(
                f"[YouTube Sandbox] Validated video payload for '{title[:40]}' "
                f"({len(video_bytes)} bytes MP4 from MinIO). Staged without external third-party API."
            )
            sim_id = f"sandbox_{uuid.uuid4().hex[:10]}"
            return {
                "success": True,
                "is_sandbox": True,
                "post_id": sim_id,
                "url": None,  # Handled by publisher_service to point to MinIO presigned video URL
                "response": {
                    "id": sim_id,
                    "snippet": metadata["snippet"],
                    "status": metadata["status"],
                    "mode": "developer_sandbox",
                    "channel_name": "IncuBrix Developer Channel"
                }
            }

        # Official Google YouTube Data API v3 Resumable Upload Protocol
        # Step 1: Initiate upload session
        init_url = f"{cls.UPLOAD_BASE}?uploadType=resumable&part=snippet,status"
        init_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(len(video_bytes))
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            init_resp = await client.post(init_url, headers=init_headers, json=metadata)
            if init_resp.status_code not in (200, 201):
                err_data = init_resp.json().get("error", {})
                err_msg = err_data.get("message", init_resp.text)
                logger.error(f"YouTube initiate upload session failed ({init_resp.status_code}): {err_msg}")
                return {
                    "success": False,
                    "error": f"YouTube Data API Error ({init_resp.status_code}): {err_msg}",
                    "error_code": err_data.get("code")
                }

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                return {
                    "success": False,
                    "error": "Google YouTube API did not return resumable upload Location header"
                }

        # Step 2: Upload raw video binary to the designated upload session URL
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_bytes))
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            upload_resp = await client.put(upload_url, headers=upload_headers, content=video_bytes)
            if upload_resp.status_code in (200, 201):
                data = upload_resp.json()
                video_id = data.get("id")
                logger.info(f"YouTube video successfully uploaded to channel! Video ID: {video_id}")
                return {
                    "success": True,
                    "post_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "shorts_url": f"https://www.youtube.com/shorts/{video_id}",
                    "response": data
                }
            else:
                err_data = upload_resp.json().get("error", {})
                err_msg = err_data.get("message", upload_resp.text)
                logger.error(f"YouTube video transfer failed ({upload_resp.status_code}): {err_msg}")
                return {
                    "success": False,
                    "error": f"YouTube video transfer error ({upload_resp.status_code}): {err_msg}",
                    "error_code": err_data.get("code")
                }


youtube_client = YouTubeClient()
