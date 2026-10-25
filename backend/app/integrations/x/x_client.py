import base64
import hashlib
import os
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import IncuBrixException


class XClient:
    AUTH_ENDPOINT = "https://twitter.com/i/oauth2/authorize"
    TOKEN_ENDPOINT = "https://api.twitter.com/2/oauth2/token"
    API_BASE = "https://api.twitter.com/2"
    UPLOAD_ENDPOINT = "https://upload.twitter.com/1.1/media/upload.json"

    @classmethod
    def generate_pkce_pair(cls) -> Dict[str, str]:
        """Generates code_verifier and code_challenge for OAuth 2.0 PKCE."""
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
        hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(hashed).decode("utf-8").rstrip("=")
        return {"code_verifier": code_verifier, "code_challenge": code_challenge}

    @classmethod
    def get_authorization_url(cls, state: str, code_challenge: str) -> str:
        """Builds X OAuth 2.0 authorization URL with PKCE."""
        if not settings.X_CLIENT_ID:
            raise IncuBrixException(status_code=400, detail="X_CLIENT_ID is not configured in environment")

        params = {
            "response_type": "code",
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": settings.X_REDIRECT_URI,
            "scope": "tweet.read tweet.write users.read offline.access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        return f"{cls.AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    @classmethod
    async def exchange_code_for_token(cls, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchanges authorization code with PKCE verifier for access token."""
        auth_header = base64.b64encode(f"{settings.X_CLIENT_ID}:{settings.X_CLIENT_SECRET}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.X_REDIRECT_URI,
            "code_verifier": code_verifier
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cls.TOKEN_ENDPOINT, headers=headers, data=data)
            if resp.status_code != 200:
                logger.error(f"X token exchange error: {resp.text}")
                raise IncuBrixException(
                    status_code=400,
                    detail=f"X token exchange failed: {resp.json().get('error_description', resp.text)}"
                )
            return resp.json()

    @classmethod
    async def get_me(cls, access_token: str) -> Dict[str, Any]:
        """Fetches the authenticated user profile from X API v2."""
        url = f"{cls.API_BASE}/users/me?user.fields=profile_image_url,verified"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "platform": "x",
                    "account_id": data.get("id"),
                    "account_name": data.get("name"),
                    "username": data.get("username"),
                    "account_type": "standard",
                    "profile_image_url": data.get("profile_image_url"),
                    "permissions": ["tweet.read", "tweet.write"]
                }
            return {}

    @classmethod
    async def publish_tweet(
        cls,
        access_token: str,
        text: str,
        media_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Publishes a tweet using official X API v2."""
        if access_token.startswith("dev_token_") or access_token.startswith("sandbox_"):
            import uuid
            tweet_id = f"sandbox_x_{uuid.uuid4().hex[:10]}"
            logger.info(f"[X Sandbox] Validated tweet text ({len(text)} chars). Staged without external API: {tweet_id}")
            return {
                "success": True,
                "is_sandbox": True,
                "post_id": tweet_id,
                "url": None,
                "response": {"id": tweet_id, "text": text[:280], "mode": "developer_sandbox"}
            }

        url = f"{cls.API_BASE}/tweets"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {"text": text[:280]}
        if media_ids:
            payload["media"] = {"media_ids": media_ids[:4]}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                tweet_id = data.get("id")
                return {
                    "success": True,
                    "post_id": tweet_id,
                    "url": f"https://x.com/i/status/{tweet_id}",
                    "response": data
                }
            err_data = resp.json()
            err_msg = err_data.get("detail", resp.text)
            logger.error(f"X Tweet publishing failed: {err_msg}")
            return {
                "success": False,
                "error": f"X API v2 Error ({resp.status_code}): {err_msg}",
                "error_details": err_data
            }


x_client = XClient()
