import pytest
from app.services.validation.platform_validator import platform_validator


def test_platform_validator_instagram_limit():
    valid_text = "A" * 150
    result = platform_validator.validate_platform_asset(
        platform="instagram",
        fmt="image",
        hook="Breaking:",
        caption=valid_text,
        hashtags=["tech", "ai"],
        media_info={"duration_seconds": 0, "width": 1080, "height": 1080}
    )
    assert result["passed"] is True

    too_long = "A" * 2500
    res_fail = platform_validator.validate_platform_asset(
        platform="instagram",
        fmt="image",
        hook="Hook:",
        caption=too_long,
        hashtags=["tech"],
        media_info={"duration_seconds": 0, "width": 1080, "height": 1080}
    )
    assert res_fail["passed"] is False
    assert any("2200" in v for v in res_fail["violations"])


def test_platform_validator_unsupported_format():
    result = platform_validator.validate_platform_asset(
        platform="youtube",
        fmt="text",  # YouTube does not support standalone text posts in Shorts flow
        hook="Hook",
        caption="Caption",
        hashtags=[]
    )
    assert result["passed"] is False
    assert any("not supported" in v for v in result["violations"])


def test_platform_validator_short_video_duration():
    result = platform_validator.validate_platform_asset(
        platform="youtube",
        fmt="short_video",
        hook="How to Repurpose",
        caption="Shorts description",
        hashtags=["shorts"],
        media_info={"duration_seconds": 75.0, "width": 1080, "height": 1920}
    )
    assert result["passed"] is False
    assert any("60s" in v for v in result["violations"])
