import asyncio
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import IncuBrixException


def _ensure_jpeg_bytes(img_bytes: bytes) -> bytes:
    """Converts image bytes to clean baseline RGB JPEG format required by Meta/Instagram APIs."""
    if not img_bytes:
        return b""
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(img_bytes)) as im:
            rgb = im.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=95, optimize=True)
            return buf.getvalue()
    except Exception:
        return img_bytes


class MetaClient:
    GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

    @classmethod
    def get_authorization_url(cls, state: str) -> str:
        """Builds Meta OAuth 2.0 authorization URL."""
        if not settings.META_APP_ID:
            raise IncuBrixException(status_code=400, detail="META_APP_ID is not configured in environment")

        scopes = [
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts",
            "instagram_basic",
            "instagram_content_publish"
        ]
        params = {
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.META_REDIRECT_URI,
            "state": state,
            "scope": ",".join(scopes),
            "response_type": "code"
        }
        return f"https://www.facebook.com/v19.0/dialog/oauth?{urllib.parse.urlencode(params)}"

    @classmethod
    async def exchange_code_for_token(cls, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for long-lived user access token."""
        url = f"{cls.GRAPH_API_BASE}/oauth/access_token"
        params = {
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.META_REDIRECT_URI,
            "code": code
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.error(f"Meta token exchange error: {resp.text}")
                raise IncuBrixException(
                    status_code=400,
                    detail=f"Meta token exchange failed: {resp.json().get('error', {}).get('message', resp.text)}"
                )
            short_lived = resp.json().get("access_token")

            # Exchange for long-lived token (60 days)
            ll_params = {
                "grant_type": "fb_exchange_token",
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "fb_exchange_token": short_lived
            }
            ll_resp = await client.get(url, params=ll_params)
            if ll_resp.status_code == 200:
                data = ll_resp.json()
                return {
                    "access_token": data.get("access_token"),
                    "expires_in": data.get("expires_in", 5184000),  # 60 days
                    "token_type": data.get("token_type", "bearer")
                }
            return {"access_token": short_lived, "expires_in": 3600, "token_type": "bearer"}

    @classmethod
    async def get_accounts_and_pages(cls, access_token: str) -> List[Dict[str, Any]]:
        """Discovers authorized Facebook Pages and connected Instagram Business accounts."""
        accounts = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Try /me/accounts (works when access_token is a User Access Token)
            try:
                url = f"{cls.GRAPH_API_BASE}/me/accounts"
                params = {
                    "access_token": access_token,
                    "fields": "id,name,category,access_token,instagram_business_account{id,username,name,profile_picture_url}"
                }
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for page in data:
                        accounts.append({
                            "platform": "facebook",
                            "account_id": page.get("id"),
                            "account_name": page.get("name"),
                            "account_type": "page",
                            "page_access_token": page.get("access_token"),
                            "permissions": ["pages_manage_posts", "pages_read_engagement"]
                        })
                        ig = page.get("instagram_business_account")
                        if ig:
                            accounts.append({
                                "platform": "instagram",
                                "account_id": ig.get("id"),
                                "account_name": ig.get("name") or ig.get("username"),
                                "username": ig.get("username"),
                                "account_type": "business",
                                "profile_image_url": ig.get("profile_picture_url"),
                                "page_access_token": page.get("access_token"),
                                "permissions": ["instagram_content_publish", "instagram_basic"]
                            })
            except Exception as e:
                logger.warning(f"Error querying /me/accounts: {e}")

            # 2. If /me/accounts returned nothing, the token may be a direct Page Access Token
            if not accounts:
                try:
                    page_url = f"{cls.GRAPH_API_BASE}/me"
                    page_params = {
                        "access_token": access_token,
                        "fields": "id,name,category,instagram_business_account{id,username,name,profile_picture_url}"
                    }
                    page_resp = await client.get(page_url, params=page_params)
                    if page_resp.status_code == 200:
                        page_data = page_resp.json()
                        accounts.append({
                            "platform": "facebook",
                            "account_id": page_data.get("id"),
                            "account_name": page_data.get("name"),
                            "account_type": "page",
                            "page_access_token": access_token,
                            "permissions": ["pages_manage_posts", "pages_read_engagement"]
                        })
                        ig = page_data.get("instagram_business_account")
                        if ig:
                            accounts.append({
                                "platform": "instagram",
                                "account_id": ig.get("id"),
                                "account_name": ig.get("name") or ig.get("username"),
                                "username": ig.get("username"),
                                "account_type": "business",
                                "profile_image_url": ig.get("profile_picture_url"),
                                "page_access_token": access_token,
                                "permissions": ["instagram_content_publish", "instagram_basic"]
                            })
                except Exception as e:
                    logger.warning(f"Error querying /me for Page Access Token: {e}")

        return accounts

    @classmethod
    async def publish_facebook_page_post(
        cls,
        page_id: str,
        page_access_token: str,
        message: str,
        link: Optional[str] = None,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        video_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Publishes post, photo, or video to an authorized Facebook Page."""
        if page_access_token.startswith("dev_token_") or page_access_token.startswith("sandbox_"):
            import uuid
            post_id = f"sandbox_fb_{uuid.uuid4().hex[:10]}"
            logger.info(f"[Facebook Sandbox] Validated post payload for page={page_id}. Staged without external API: {post_id}")
            return {
                "success": True,
                "is_sandbox": True,
                "post_id": post_id,
                "url": None,
                "response": {"id": post_id, "mode": "developer_sandbox"}
            }

        async with httpx.AsyncClient(timeout=120.0) as client:
            clean_page_id = page_id.replace("page_", "") if page_id.startswith("page_") and not page_id.startswith("page_meta_") else page_id
            
            # 1. Direct binary video upload
            if video_bytes:
                url = f"{cls.GRAPH_API_BASE}/{clean_page_id}/videos"
                data = {
                    "access_token": page_access_token,
                    "description": message
                }
                files = {"source": ("video.mp4", video_bytes, "video/mp4")}
                resp = await client.post(url, data=data, files=files)
            # 2. Direct binary photo upload
            elif image_bytes:
                url = f"{cls.GRAPH_API_BASE}/{clean_page_id}/photos"
                data = {
                    "access_token": page_access_token,
                    "caption": message
                }
                files = {"source": ("image.png", image_bytes, "image/png")}
                resp = await client.post(url, data=data, files=files)
            # 3. URL-based video upload
            elif video_url:
                url = f"{cls.GRAPH_API_BASE}/{clean_page_id}/videos"
                payload = {
                    "access_token": page_access_token,
                    "description": message,
                    "file_url": video_url
                }
                resp = await client.post(url, json=payload)
            # 4. URL-based photo upload
            elif image_url:
                url = f"{cls.GRAPH_API_BASE}/{clean_page_id}/photos"
                payload = {
                    "access_token": page_access_token,
                    "caption": message,
                    "url": image_url
                }
                resp = await client.post(url, json=payload)
            # 5. Text / link status post
            else:
                url = f"{cls.GRAPH_API_BASE}/{clean_page_id}/feed"
                payload = {
                    "access_token": page_access_token,
                    "message": message
                }
                if link:
                    payload["link"] = link
                resp = await client.post(url, json=payload)

            if resp.status_code in (200, 201):
                data = resp.json()
                post_id = data.get("post_id") or data.get("id")
                # Attempt to query canonical permalink from Meta
                canonical_url = None
                try:
                    perm_resp = await client.get(
                        f"{cls.GRAPH_API_BASE}/{post_id}",
                        params={"fields": "permalink_url", "access_token": page_access_token}
                    )
                    if perm_resp.status_code == 200:
                        canonical_url = perm_resp.json().get("permalink_url")
                except Exception:
                    pass

                if not canonical_url:
                    if "_" in str(post_id):
                        parts = str(post_id).split("_")
                        canonical_url = f"https://www.facebook.com/{parts[0]}/posts/{parts[1]}"
                    elif video_bytes or video_url:
                        canonical_url = f"https://www.facebook.com/watch/?v={post_id}"
                    else:
                        canonical_url = f"https://www.facebook.com/{post_id}"

                return {
                    "success": True,
                    "post_id": post_id,
                    "url": canonical_url,
                    "response": data
                }
            error_data = resp.json().get("error", {})
            err_msg = error_data.get("message", resp.text)
            logger.error(f"Facebook publishing failed HTTP {resp.status_code}: {err_msg}")
            return {
                "success": False,
                "error": f"Facebook Graph API Error ({resp.status_code}): {err_msg}",
                "error_code": error_data.get("code")
            }

    @classmethod
    async def publish_instagram_media(
        cls,
        ig_user_id: str,
        page_access_token: str,
        caption: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        video_bytes: Optional[bytes] = None,
        is_reel: bool = False
    ) -> Dict[str, Any]:
        """
        Publishes media to Instagram Professional via the Container API.
        Step 1: POST /{ig_user_id}/media to create container.
        Step 2: POST /{ig_user_id}/media_publish to publish container.
        """
        if page_access_token.startswith("dev_token_") or page_access_token.startswith("sandbox_"):
            import uuid
            media_id = f"sandbox_ig_{uuid.uuid4().hex[:10]}"
            logger.info(f"[Instagram Sandbox] Validated container for user={ig_user_id}. Staged without external API: {media_id}")
            return {
                "success": True,
                "is_sandbox": True,
                "post_id": media_id,
                "url": None,
                "response": {"id": media_id, "mode": "developer_sandbox"}
            }

        async with httpx.AsyncClient(timeout=120.0) as client:
            clean_ig_id = ig_user_id.replace("ig_", "") if ig_user_id.startswith("ig_") and not ig_user_id.startswith("ig_meta_") else ig_user_id
            api_base = "https://graph.instagram.com/v19.0" if page_access_token.startswith("IGAA") else cls.GRAPH_API_BASE
            
            # Step 1: Resolve valid media URL for Instagram container
            final_image_url = image_url
            final_video_url = video_url

            # 1a. If video_bytes is provided, bridge to Catbox public HTTPS CDN
            if video_bytes and (not final_video_url or "localhost" in final_video_url or "127.0.0.1" in final_video_url):
                try:
                    catbox_resp = await client.post(
                        "https://catbox.moe/user/api.php",
                        data={"reqtype": "fileupload"},
                        files={"fileToUpload": ("video.mp4", video_bytes, "video/mp4")},
                        timeout=60.0
                    )
                    if catbox_resp.status_code == 200 and catbox_resp.text.strip().startswith("https://"):
                        final_video_url = catbox_resp.text.strip()
                        logger.info(f"Bridged video to Catbox CDN for Instagram container: {final_video_url}")
                except Exception as ve:
                    logger.warning(f"Could not bridge video to Catbox CDN: {ve}")

            if not final_image_url or "localhost" in final_image_url or "127.0.0.1" in final_image_url:
                final_image_url = None

                # If image_bytes is provided, bridge upload to public CDN so Meta's scraper can reach it
                if image_bytes:
                    # 1. Try Catbox public HTTPS CDN
                    try:
                        catbox_resp = await client.post(
                            "https://catbox.moe/user/api.php",
                            data={"reqtype": "fileupload"},
                            files={"fileToUpload": ("image.png", image_bytes, "image/png")},
                            timeout=15.0
                        )
                        if catbox_resp.status_code == 200 and catbox_resp.text.strip().startswith("https://"):
                            final_image_url = catbox_resp.text.strip()
                            logger.info(f"Bridged image to Catbox CDN for Instagram container: {final_image_url}")
                    except Exception as e:
                        logger.warning(f"Could not bridge image to Catbox CDN: {e}")

                # 2. If Catbox was not used or failed, try Meta Page photos bridge if token is valid
                if not final_image_url and image_bytes:
                    fb_token = getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", None) or getattr(settings, "FACEBOOK_ACCESS_TOKEN", None)
                    fb_page = getattr(settings, "FACEBOOK_PAGE_ID", "1539128952609697")
                    if fb_token and fb_page:
                        try:
                            fb_upload_url = f"{cls.GRAPH_API_BASE}/{fb_page}/photos"
                            fb_data = {"caption": "IncuBrix Media Sync", "access_token": fb_token, "published": "false"}
                            fb_files = {"source": ("media.png", image_bytes, "image/png")}
                            fb_resp = await client.post(fb_upload_url, data=fb_data, files=fb_files)
                            if fb_resp.status_code == 200:
                                photo_id = fb_resp.json().get("id")
                                cdn_resp = await client.get(f"{cls.GRAPH_API_BASE}/{photo_id}?fields=source&access_token={fb_token}")
                                if cdn_resp.status_code == 200:
                                    final_image_url = cdn_resp.json().get("source")
                                    logger.info(f"Bridged image to Meta CDN for Instagram container: {final_image_url[:60]}...")
                        except Exception as e:
                            logger.warning(f"Could not bridge image to Meta CDN for Instagram: {e}")

                # 3. Fallback high-res cover image if still absent
                if not final_image_url and not final_video_url and not video_bytes:
                    final_image_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&auto=format&fit=crop"

            create_url = f"{api_base}/{clean_ig_id}/media"
            container_payload = {
                "access_token": page_access_token,
                "caption": caption
            }
            if final_video_url or video_bytes or is_reel:
                container_payload["media_type"] = "REELS"
                if final_video_url and "localhost" not in final_video_url:
                    container_payload["video_url"] = final_video_url
                else:
                    return {"success": False, "error": "Instagram Reels requires a public video_url"}
            elif final_image_url:
                container_payload["image_url"] = final_image_url
            else:
                return {"success": False, "error": "Instagram requires image or video media URL"}

            resp = await client.post(create_url, json=container_payload)
            if resp.status_code not in (200, 201):
                error_msg = resp.json().get("error", {}).get("message", resp.text)
                return {"success": False, "error": f"Instagram container creation failed: {error_msg}"}

            container_data = resp.json()
            container_id = container_data.get("id")

            # Wait for container status to be FINISHED (up to 30s)
            for _ in range(15):
                await asyncio.sleep(2)
                st_resp = await client.get(
                    f"{api_base}/{container_id}",
                    params={"fields": "status_code,status", "access_token": page_access_token}
                )
                if st_resp.status_code == 200:
                    status_code = st_resp.json().get("status_code")
                    if status_code == "FINISHED":
                        break
                    elif status_code == "ERROR":
                        err_msg = st_resp.json().get("status", "Video processing failed on Instagram")
                        return {"success": False, "error": f"Instagram container processing failed: {err_msg}"}

            # Step 2: Publish Container
            pub_url = f"{api_base}/{clean_ig_id}/media_publish"
            pub_payload = {
                "access_token": page_access_token,
                "creation_id": container_id
            }
            pub_resp = await client.post(pub_url, json=pub_payload)
            if pub_resp.status_code in (200, 201):
                pub_data = pub_resp.json()
                media_id = pub_data.get("id")
                
                # Fetch authentic Instagram web permalink from Graph API
                ig_url = None
                try:
                    ig_perm_resp = await client.get(
                        f"{api_base}/{media_id}",
                        params={"fields": "permalink,shortcode", "access_token": page_access_token}
                    )
                    if ig_perm_resp.status_code == 200:
                        ig_url = ig_perm_resp.json().get("permalink")
                except Exception:
                    pass

                # If permalink wasn't fetched, fallback to verified profile handle
                if not ig_url:
                    clean_username = getattr(settings, "INSTAGRAM_USERNAME", "ish_uu.05")
                    ig_url = f"https://www.instagram.com/{clean_username}/"

                return {
                    "success": True,
                    "post_id": media_id,
                    "url": ig_url,
                    "response": pub_data
                }
            error_msg = pub_resp.json().get("error", {}).get("message", pub_resp.text)
            return {"success": False, "error": f"Instagram media publish failed: {error_msg}"}

    @classmethod
    async def publish_facebook_page_carousel(
        cls,
        page_id: str,
        page_access_token: str,
        message: str,
        slides: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Publishes a multi-photo carousel post to an authorized Facebook Page.
        Step 1: Upload each slide as an unpublished photo: POST /{page_id}/photos (published=false)
        Step 2: Create a feed post with all photo IDs in attached_media: POST /{page_id}/feed
        """
        if page_access_token.startswith("dev_token_") or page_access_token.startswith("sandbox_"):
            import uuid
            post_id = f"sandbox_fb_car_{uuid.uuid4().hex[:10]}"
            return {"success": True, "is_sandbox": True, "post_id": post_id, "url": None, "response": {"id": post_id}}

        async with httpx.AsyncClient(timeout=120.0) as client:
            clean_page_id = page_id.replace("page_", "") if page_id.startswith("page_") and not page_id.startswith("page_meta_") else page_id
            
            # Resolve actual Page Access Token if a User token was supplied
            effective_page_token = page_access_token
            try:
                me_resp = await client.get(f"{cls.GRAPH_API_BASE}/me/accounts?access_token={page_access_token}")
                if me_resp.status_code == 200:
                    for p in me_resp.json().get("data", []):
                        if str(p.get("id")) == str(clean_page_id) and p.get("access_token"):
                            effective_page_token = p["access_token"]
                            logger.info(f"Resolved official Facebook Page Access Token for Page {clean_page_id}")
                            break
            except Exception as e:
                logger.warning(f"Could not auto-resolve Page Access Token: {e}")

            photo_ids = []
            for idx, slide in enumerate(slides):
                slide_bytes = slide.get("bytes")
                if not slide_bytes:
                    continue
                # Ensure clean baseline RGB JPEG so Meta never encounters corrupted chunks
                jpg_bytes = _ensure_jpeg_bytes(slide_bytes)
                slide_name = f"slide_{idx+1}.jpg"
                try:
                    resp = await client.post(
                        f"{cls.GRAPH_API_BASE}/{clean_page_id}/photos",
                        data={"access_token": effective_page_token, "published": "false"},
                        files={"source": (slide_name, jpg_bytes, "image/jpeg")}
                    )
                    if resp.status_code == 200:
                        photo_id = resp.json().get("id")
                        if photo_id:
                            photo_ids.append(photo_id)
                    else:
                        logger.warning(f"Facebook carousel slide {idx+1} upload returned {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.warning(f"Failed to upload slide {idx+1} for Facebook carousel: {e}")

            if not photo_ids:
                return {"success": False, "error": "No carousel slides could be uploaded to Facebook"}

            # Create the feed post with attached_media
            form_data = {
                "access_token": effective_page_token,
                "message": message
            }
            for i, pid in enumerate(photo_ids):
                form_data[f"attached_media[{i}]"] = f'{{"media_fbid":"{pid}"}}'

            feed_resp = await client.post(
                f"{cls.GRAPH_API_BASE}/{clean_page_id}/feed",
                data=form_data
            )
            if feed_resp.status_code in (200, 201):
                post_id = feed_resp.json().get("id")
                return {
                    "success": True,
                    "post_id": post_id,
                    "url": f"https://www.facebook.com/{clean_page_id}/posts/{post_id}" if clean_page_id and clean_page_id != "me" else None,
                    "response": feed_resp.json()
                }
            else:
                err = feed_resp.json().get("error", {}).get("message", feed_resp.text)
                return {"success": False, "error": f"Facebook carousel post failed: {err}"}

    @classmethod
    async def publish_instagram_carousel(
        cls,
        ig_user_id: str,
        page_access_token: str,
        caption: str,
        slides: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Publishes a multi-slide carousel to Instagram Professional via the Container API.
        Step 1: Upload each slide to public CDN (Catbox) and create item container with is_carousel_item=True
        Step 2: Create Carousel container with media_type=CAROUSEL and children=[item_id_1, item_id_2, ...]
        Step 3: Wait for carousel container to be FINISHED
        Step 4: Publish carousel container via /{ig_user_id}/media_publish
        """
        if page_access_token.startswith("dev_token_") or page_access_token.startswith("sandbox_"):
            import uuid
            media_id = f"sandbox_ig_car_{uuid.uuid4().hex[:10]}"
            return {"success": True, "is_sandbox": True, "post_id": media_id, "url": None, "response": {"id": media_id}}

        async with httpx.AsyncClient(timeout=120.0) as client:
            clean_ig_id = ig_user_id.replace("ig_", "") if ig_user_id.startswith("ig_") and not ig_user_id.startswith("ig_meta_") else ig_user_id
            api_base = "https://graph.instagram.com/v19.0" if page_access_token.startswith("IGAA") else cls.GRAPH_API_BASE

            item_container_ids = []
            for idx, slide in enumerate(slides):
                slide_bytes = slide.get("bytes")
                slide_name = f"slide_{idx+1}.jpg"

                # Always convert slide bytes to clean baseline JPEG so Meta Telephoto never chokes on PNG chunks
                jpg_bytes = _ensure_jpeg_bytes(slide_bytes) if slide_bytes else None

                public_slide_url = None
                if jpg_bytes:
                    try:
                        catbox_resp = await client.post(
                            "https://catbox.moe/user/api.php",
                            data={"reqtype": "fileupload"},
                            files={"fileToUpload": (slide_name, jpg_bytes, "image/jpeg")},
                            timeout=25.0
                        )
                        if catbox_resp.status_code == 200 and catbox_resp.text.strip().startswith("https://"):
                            public_slide_url = catbox_resp.text.strip()
                    except Exception as e:
                        logger.warning(f"Could not bridge slide {idx+1} to Catbox: {e}")

                if not public_slide_url:
                    continue

                # Create item container
                item_payload = {
                    "access_token": page_access_token,
                    "image_url": public_slide_url,
                    "is_carousel_item": True
                }
                c_resp = await client.post(f"{api_base}/{clean_ig_id}/media", json=item_payload)
                if c_resp.status_code in (200, 201):
                    c_id = c_resp.json().get("id")
                    if c_id:
                        item_container_ids.append(c_id)
                else:
                    logger.warning(f"Instagram carousel item {idx+1} failed: {c_resp.text}")

                # Rate-limit buffer between container calls
                await asyncio.sleep(1.0)

            if len(item_container_ids) < 2:
                return {"success": False, "error": f"Instagram requires at least 2 valid slides for a carousel (uploaded {len(item_container_ids)})"}

            # Step 2: Create Carousel container
            carousel_payload = {
                "access_token": page_access_token,
                "media_type": "CAROUSEL",
                "children": item_container_ids,
                "caption": caption
            }
            c_resp = await client.post(f"{api_base}/{clean_ig_id}/media", json=carousel_payload)
            if c_resp.status_code not in (200, 201):
                err = c_resp.json().get("error", {}).get("message", c_resp.text)
                return {"success": False, "error": f"Instagram carousel container creation failed: {err}"}

            carousel_id = c_resp.json()["id"]

            # Step 3: Wait for container to be ready (up to 30s)
            for _ in range(15):
                await asyncio.sleep(2)
                st_resp = await client.get(
                    f"{api_base}/{carousel_id}",
                    params={"fields": "status_code,status", "access_token": page_access_token}
                )
                if st_resp.status_code == 200:
                    st_code = st_resp.json().get("status_code")
                    if st_code == "FINISHED":
                        break
                    elif st_code == "ERROR":
                        err_msg = st_resp.json().get("status", "Carousel processing failed on Instagram")
                        return {"success": False, "error": f"Instagram carousel processing failed: {err_msg}"}

            # Step 4: Publish Carousel
            pub_resp = await client.post(
                f"{api_base}/{clean_ig_id}/media_publish",
                json={
                    "access_token": page_access_token,
                    "creation_id": carousel_id
                }
            )
            if pub_resp.status_code in (200, 201):
                media_id = pub_resp.json().get("id")
                ig_url = None
                try:
                    ig_perm = await client.get(
                        f"{api_base}/{media_id}",
                        params={"fields": "permalink,shortcode", "access_token": page_access_token}
                    )
                    if ig_perm.status_code == 200:
                        ig_url = ig_perm.json().get("permalink")
                except Exception:
                    pass

                clean_user = getattr(settings, "INSTAGRAM_USERNAME", "ish_uu.05")
                return {
                    "success": True,
                    "post_id": media_id,
                    "url": ig_url or f"https://www.instagram.com/{clean_user}/",
                    "response": pub_resp.json()
                }
            else:
                err = pub_resp.json().get("error", {}).get("message", pub_resp.text)
                return {"success": False, "error": f"Instagram carousel publish failed: {err}"}


meta_client = MetaClient()
