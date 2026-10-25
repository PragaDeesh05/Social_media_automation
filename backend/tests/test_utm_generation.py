import pytest
import urllib.parse
from app.services.content.utm_service import utm_service


def test_utm_generation():
    result = utm_service.generate_tracking_url(
        base_url="https://incubrix.com/features?ref=header",
        platform="Instagram",
        format_type="carousel",
        campaign_name="Q4 Growth Launch",
        asset_id="12345678-abcd-ef01-2345-6789abcdef01"
    )

    final_url = result["final_url"]
    parsed = urllib.parse.urlparse(final_url)
    query = dict(urllib.parse.parse_qsl(parsed.query))

    assert query["ref"] == "header"  # preserved existing query param
    assert query["utm_source"] == "instagram"
    assert query["utm_medium"] == "social-carousel"
    assert query["utm_campaign"] == "q4-growth-launch"
    assert query["utm_content"] == "slot-12345678"
