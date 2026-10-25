from typing import Dict, Any, List, Optional

PLATFORM_CONSTRAINTS = {
    "facebook": {
        "max_length": 63206,
        "max_hashtags": 10,
        "supported_formats": ["text", "image", "carousel", "short_video"],
        "video_max_duration": 240,
    },
    "instagram": {
        "max_length": 2200,
        "max_hashtags": 30,
        "supported_formats": ["image", "carousel", "short_video"],
        "video_max_duration": 90,
    },
    "youtube": {
        "max_title_length": 100,
        "max_length": 5000,
        "max_hashtags": 15,
        "supported_formats": ["short_video"],
        "video_max_duration": 60,
    }
}


class PlatformValidator:
    @classmethod
    def validate_platform_asset(
        cls,
        platform: str,
        fmt: str,
        hook: str,
        caption: str,
        hashtags: List[str],
        media_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validates asset content and media against official platform API constraints."""
        platform = platform.lower()
        fmt = fmt.lower()
        violations = []
        warnings = []

        rules = PLATFORM_CONSTRAINTS.get(platform)
        if not rules:
            violations.append(f"Unsupported platform: {platform}")
            return {"passed": False, "violations": violations, "warnings": []}

        # 1. Supported Format Check
        if fmt not in rules["supported_formats"]:
            violations.append(f"Format '{fmt}' is not supported on platform '{platform}'")

        # 2. Text Length Check
        if len(caption) > rules["max_length"]:
            violations.append(f"Caption exceeds {platform} limit ({len(caption)}/{rules['max_length']} chars)")

        # 3. Hashtag Limit Check
        if len(hashtags) > rules["max_hashtags"]:
            warnings.append(f"Too many hashtags ({len(hashtags)} > {rules['max_hashtags']})")

        # 4. Media Requirements Check
        if fmt in ("image", "carousel", "short_video"):
            if not media_info:
                warnings.append(f"Media asset generation is pending for {fmt}")
            else:
                if fmt == "short_video":
                    dur = media_info.get("duration_seconds", 0)
                    if dur > 60.0:
                        violations.append(f"Short video duration ({dur:.1f}s) exceeds the strict 60s limit")
                    w = media_info.get("width")
                    h = media_info.get("height")
                    if w and h and w > h:
                        violations.append(f"Short video must be vertical 9:16 aspect ratio, got {w}x{h}")

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "platform_rules": rules
        }


platform_validator = PlatformValidator()
