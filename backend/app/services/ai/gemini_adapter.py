import asyncio
import json
import re
from typing import Dict, Any, Optional, Type

from pydantic import BaseModel
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import ProviderUnavailableError


class GeminiAdapter:
    """Gemini models served via Google Cloud Vertex AI (google-genai SDK, Vertex mode)."""

    def __init__(self):
        self.project = settings.GOOGLE_CLOUD_PROJECT
        self.location = settings.GOOGLE_CLOUD_LOCATION or "us-central1"
        self.primary_model = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Lazily build (and cache) the Vertex AI genai client."""
        if self._client is None:
            if not self.project:
                raise ProviderUnavailableError("gemini", "GOOGLE_CLOUD_PROJECT is not configured in environment")
            self._client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        return self._client

    def check_availability(self) -> Dict[str, Any]:
        """Runtime health check for Vertex AI Gemini access."""
        if not self.project:
            return {"available": False, "reason": "GOOGLE_CLOUD_PROJECT is not configured in environment"}

        client = self._get_client()
        for model in (self.primary_model, self.fallback_model):
            try:
                resp = client.models.generate_content(model=model, contents="Ping")
                if getattr(resp, "text", None):
                    return {
                        "available": True,
                        "model": model,
                        "status": "operational",
                        "provider": "vertex_ai",
                        "project": self.project,
                        "location": self.location,
                    }
            except Exception as e:
                logger.warning(f"Vertex AI health check for {model} failed: {e}")
        return {"available": False, "reason": "No Gemini model responded on Vertex AI"}

    def _generate_text_sync(
        self,
        contents: list,
        config: types.GenerateContentConfig,
        models: list,
    ) -> str:
        """Blocking call against Vertex AI with automatic model fallback."""
        client = self._get_client()
        last_error: Optional[str] = None
        for model in models:
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=config)
                if getattr(resp, "text", None):
                    return resp.text.strip()
                last_error = "empty response"
            except Exception as e:
                logger.warning(f"Gemini {model} failed: {e}")
                last_error = str(e)
        raise ProviderUnavailableError("gemini", f"All Gemini model attempts failed: {last_error}")

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate open-ended text response with automatic model fallback."""
        if not self.project:
            raise ProviderUnavailableError("gemini", "GOOGLE_CLOUD_PROJECT not configured")

        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Primary model first, then fallback, then a safe default.
        models = [self.primary_model, self.fallback_model, "gemini-3.5-flash-lite"]
        return await asyncio.to_thread(self._generate_text_sync, contents, config, models)

    async def generate_structured(
        self,
        prompt: str,
        response_model: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate strictly structured JSON response validated with Pydantic."""
        schema_instruction = ""
        if response_model:
            schema_instruction = f"\nReturn strictly valid JSON matching this schema:\n{json.dumps(response_model.model_json_schema())}\n"

        full_prompt = f"{prompt}\n{schema_instruction}\nStrictly output ONLY valid JSON without markdown fences."

        raw_response = await self.generate_text(
            prompt=full_prompt,
            system_instruction=system_instruction,
            temperature=temperature,
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
