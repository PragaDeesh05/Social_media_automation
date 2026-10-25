import pytest
from app.services.validation.brand_validator import brand_validator


def test_brand_validator_clean_asset():
    brand = {
        "words_to_avoid": ["overnight", "magic", "guaranteed"],
        "verified_product_facts": ["IncuBrix automates social media workflows."]
    }
    result = brand_validator.validate_asset(
        hook="How top creators turn 1 input into 30 days of social assets:",
        caption="A structured breakdown of autonomous content distribution.",
        cta="Try IncuBrix Free → incubrix.com/start",
        tracking_url="https://incubrix.com/start?utm_source=x",
        brand_profile=brand
    )
    assert result["passed"] is True
    assert result["quality_score"] >= 80
    assert len(result["violations"]) == 0


def test_brand_validator_prohibited_words():
    brand = {
        "words_to_avoid": ["overnight", "magic"],
        "verified_product_facts": []
    }
    result = brand_validator.validate_asset(
        hook="Get overnight success with our magic AI tool!",
        caption="This produces instant riches.",
        cta="Click here",
        tracking_url="https://incubrix.com",
        brand_profile=brand
    )
    assert result["passed"] is False
    assert any("Prohibited" in v for v in result["violations"])


def test_brand_validator_invalid_url():
    brand = {"words_to_avoid": []}
    result = brand_validator.validate_asset(
        hook="How to streamline your multi-platform distribution:",
        caption="Solid content framework for growth.",
        cta="Learn more",
        tracking_url="invalid-url-without-scheme",
        brand_profile=brand
    )
    assert result["passed"] is False
    assert any("URL" in v for v in result["violations"])
