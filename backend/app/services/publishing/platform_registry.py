from typing import Dict, Any, List


PLATFORM_CAPABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "instagram": {
        "platform_name": "Instagram",
        "supported_account_types": ["professional", "business", "creator"],
        "supported_formats": {
            "image": {
                "aspect_ratios": ["1:1", "4:5"],
                "accepted_media": ["image/jpeg", "image/png"],
                "max_size_mb": 8,
                "endpoint": "https://graph.facebook.com/v19.0/{ig_user_id}/media"
            },
            "carousel": {
                "min_slides": 2,
                "max_slides": 10,
                "aspect_ratios": ["1:1", "4:5"],
                "accepted_media": ["image/jpeg", "image/png"],
                "endpoint": "https://graph.facebook.com/v19.0/{ig_user_id}/media"
            },
            "short_video": {
                "max_duration_seconds": 90,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "accepted_media": ["video/mp4", "video/quicktime"],
                "endpoint": "https://graph.facebook.com/v19.0/{ig_user_id}/media"
            }
        },
        "required_permissions": ["instagram_basic", "instagram_content_publish", "pages_show_list"],
        "direct_scheduling_supported": False,  # Managed by our persistent background worker
        "analytics_available": True,
        "docs_url": "https://developers.facebook.com/docs/instagram-api/guides/content-publishing"
    },
    "facebook": {
        "platform_name": "Facebook",
        "supported_account_types": ["page"],
        "supported_formats": {
            "text": {
                "max_chars": 63206,
                "endpoint": "https://graph.facebook.com/v19.0/{page_id}/feed"
            },
            "image": {
                "accepted_media": ["image/jpeg", "image/png"],
                "max_size_mb": 10,
                "endpoint": "https://graph.facebook.com/v19.0/{page_id}/photos"
            },
            "carousel": {
                "accepted_media": ["image/jpeg", "image/png"],
                "endpoint": "https://graph.facebook.com/v19.0/{page_id}/feed"
            },
            "short_video": {
                "max_duration_seconds": 240,
                "aspect_ratio": "9:16",
                "accepted_media": ["video/mp4"],
                "endpoint": "https://graph.facebook.com/v19.0/{page_id}/videos"
            }
        },
        "required_permissions": ["pages_read_engagement", "pages_manage_posts"],
        "direct_scheduling_supported": True,
        "analytics_available": True,
        "docs_url": "https://developers.facebook.com/docs/pages-api/posts"
    },
    "youtube": {
        "platform_name": "YouTube",
        "supported_account_types": ["channel"],
        "supported_formats": {
            "short_video": {
                "max_duration_seconds": 60,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "accepted_media": ["video/mp4", "video/quicktime"],
                "endpoint": "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable"
            }
        },
        "required_permissions": ["https://www.googleapis.com/auth/youtube.upload"],
        "direct_scheduling_supported": True,  # Via video privacyStatus & publishAt
        "analytics_available": True,
        "docs_url": "https://developers.google.com/youtube/v3/docs/videos/insert"
    },
    "x": {
        "platform_name": "X (Twitter)",
        "supported_account_types": ["standard", "premium"],
        "supported_formats": {
            "text": {
                "max_chars": 280,
                "endpoint": "https://api.twitter.com/2/tweets"
            },
            "image": {
                "max_chars": 280,
                "max_images": 4,
                "accepted_media": ["image/jpeg", "image/png", "image/webp"],
                "endpoint": "https://api.twitter.com/2/tweets"
            },
            "short_video": {
                "max_duration_seconds": 140,
                "max_size_mb": 512,
                "accepted_media": ["video/mp4"],
                "endpoint": "https://api.twitter.com/2/tweets"
            }
        },
        "required_permissions": ["tweet.read", "tweet.write", "users.read", "offline.access"],
        "direct_scheduling_supported": False,  # Managed by our background worker
        "analytics_available": True,
        "docs_url": "https://developer.x.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets"
    }
}


def get_platform_capability(platform: str) -> Dict[str, Any]:
    return PLATFORM_CAPABILITY_REGISTRY.get(platform.lower(), {})
