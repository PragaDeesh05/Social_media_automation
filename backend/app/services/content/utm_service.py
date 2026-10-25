import urllib.parse
import re
from typing import Dict, Any, Optional


class UTMService:
    @staticmethod
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-")

    @classmethod
    def generate_tracking_url(
        cls,
        base_url: str,
        platform: str,
        format_type: str,
        campaign_name: str,
        asset_id: str,
        custom_params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Builds a robust, normalized UTM tracking URL.
        Preserves existing query parameters, handles URL encoding safely.
        """
        if not base_url:
            base_url = "https://incubrix.com/start"

        parsed = urllib.parse.urlparse(base_url)
        query_dict = dict(urllib.parse.parse_qsl(parsed.query))

        # Standard UTM parameters
        utm_params = {
            "utm_source": platform.lower().strip(),
            "utm_medium": "social-" + format_type.lower().replace("_", "-"),
            "utm_campaign": cls.slugify(campaign_name),
            "utm_content": f"slot-{asset_id[:8]}"
        }

        if custom_params:
            for k, v in custom_params.items():
                if v:
                    utm_params[k] = str(v)

        # Merge with existing
        query_dict.update(utm_params)
        new_query = urllib.parse.urlencode(query_dict)

        final_url = urllib.parse.urlunparse((
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        return {
            "base_url": base_url,
            "final_url": final_url,
            "utm_parameters": utm_params
        }


utm_service = UTMService()
