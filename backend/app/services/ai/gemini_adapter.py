import json
import re
import time
from typing import Dict, Any, Optional, List, Type
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import ProviderUnavailableError


class GeminiAdapter:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.primary_model = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def check_availability(self) -> Dict[str, Any]:
        """Runtime health check for Gemini API access."""
        if not self.api_key:
            return {"available": False, "reason": "GEMINI_API_KEY is not configured in environment"}
        
        url = f"{self.base_url}/{self.primary_model}:generateContent?key={self.api_key}"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json={"contents": [{"parts": [{"text": "Ping"}]}]})
                if res.status_code == 200:
                    return {"available": True, "model": self.primary_model, "status": "operational"}
                elif res.status_code == 404:
                    # Test fallback model
                    fb_url = f"{self.base_url}/{self.fallback_model}:generateContent?key={self.api_key}"
                    fb_res = client.post(fb_url, json={"contents": [{"parts": [{"text": "Ping"}]}]})
                    if fb_res.status_code == 200:
                        return {"available": True, "model": self.fallback_model, "status": "operational"}
                    return {"available": False, "reason": f"Models unavailable: {res.text}"}
                else:
                    return {"available": False, "reason": f"API error HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"available": False, "reason": f"Connection error: {e}"}

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate open-ended text response with automatic model fallback."""
        if not self.api_key:
            raise ProviderUnavailableError("gemini", "GEMINI_API_KEY not configured")

        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        # Try primary model first, then fallback
        models = [self.primary_model, self.fallback_model, "gemini-3.5-flash-lite"]
        last_error = None

        for model in models:
            url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                    else:
                        logger.warning(f"Gemini {model} returned {resp.status_code}: {resp.text}")
                        last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                logger.warning(f"Gemini call to {model} failed: {e}")
                last_error = str(e)

        raise ProviderUnavailableError("gemini", f"All Gemini model attempts failed: {last_error}")

    async def generate_structured(
        self,
        prompt: str,
        response_model: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """Generate strictly structured JSON response validated with Pydantic."""
        schema_instruction = ""
        if response_model:
            schema_instruction = f"\nReturn strictly valid JSON matching this schema:\n{json.dumps(response_model.model_json_schema())}\n"

        full_prompt = f"{prompt}\n{schema_instruction}\nStrictly output ONLY valid JSON without markdown fences."

        raw_response = await self.generate_text(
            prompt=full_prompt,
            system_instruction=system_instruction,
            temperature=temperature
        )

        clean_json = raw_response.strip()
        clean_json = re.sub(r"^```json\s*", "", clean_json)
        clean_json = re.sub(r"^```\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)

        try:
            parsed = json.loads(clean_json)
            if response_model:
                validated = response_model.model_validate(parsed)
                return validated.model_dump()
            return parsed
        except Exception as e:
            logger.error(f"JSON validation error: {e}. Raw was: {clean_json[:500]}")
            # Attempt targeted regex repair
            match = re.search(r"(\{.*\}|\[.*\])", clean_json, re.DOTALL)
            if match:
                try:
                    repaired = json.loads(match.group(1))
                    if response_model:
                        return response_model.model_validate(repaired).model_dump()
                    return repaired
                except Exception:
                    pass
            raise ProviderUnavailableError("gemini", f"Model returned invalid JSON structure: {e}")


gemini_adapter = GeminiAdapter()
