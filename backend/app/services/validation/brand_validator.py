import re
from typing import Dict, Any, List, Tuple


class BrandValidator:
    @classmethod
    def validate_asset(
        cls,
        hook: str,
        caption: str,
        cta: str,
        tracking_url: str,
        brand_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates content asset against configured brand profile guidelines and factual rules.
        Returns check results with pass/fail and actionable warning details.
        """
        violations = []
        warnings = []

        full_text = f"{hook} {caption} {cta}".lower()
        words_to_avoid = brand_profile.get("words_to_avoid", [])
        verified_facts = brand_profile.get("verified_product_facts", [])

        # 1. Prohibited words check
        for prohibited in words_to_avoid:
            pattern = r"\b" + re.escape(prohibited.lower()) + r"\b"
            if re.search(pattern, full_text):
                violations.append(f"Prohibited word/claim detected: '{prohibited}'")

        # 2. CTA Presence Check
        if not cta or len(cta.strip()) < 5:
            warnings.append("Call to action (CTA) is missing or too short")

        # 3. Tracking URL validity
        if not tracking_url or not (tracking_url.startswith("http://") or tracking_url.startswith("https://")):
            violations.append("Invalid or missing trackable destination URL")

        # 4. Check for unverified numerical claims (e.g. '100x roi', 'overnight')
        unverified_patterns = [
            (r"\b\d{3,}% roi\b", "Unverified high percentage ROI claim"),
            (r"\bguaranteed \$\d+\b", "Unverified guaranteed revenue promise"),
            (r"\b(overnight|magic|instant riches)\b", "Exaggerated or misleading claim")
        ]
        for pat, desc in unverified_patterns:
            if re.search(pat, full_text):
                violations.append(desc)

        # 5. Hook Quality
        if len(hook.strip()) < 15:
            warnings.append("Hook is very short, may not drive sufficient curiosity")
        elif not any(char in hook for char in ["?", "!", ":", "-", "How", "Why", "The"]):
            warnings.append("Hook lacks a strong curiosity punctuation or prompt")

        passed = len(violations) == 0
        quality_score = max(0, 100 - (len(violations) * 35) - (len(warnings) * 10))

        return {
            "passed": passed,
            "quality_score": quality_score,
            "status": "passed" if passed and len(warnings) == 0 else ("warnings" if passed else "failed"),
            "violations": violations,
            "warnings": warnings,
            "checks": {
                "prohibited_words_clean": len([v for v in violations if "Prohibited" in v]) == 0,
                "cta_present": len([w for w in warnings if "CTA" in w]) == 0,
                "url_valid": len([v for v in violations if "URL" in v]) == 0,
                "unverified_claims_clean": len([v for v in violations if "Unverified" in v]) == 0,
            }
        }


brand_validator = BrandValidator()
