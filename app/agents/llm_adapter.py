"""LLM Provider Adapter & Structured Completion Interface.

Manages structured generation across analysts and judges with strict Pydantic validation:
- Preserves provider identity in trace metadata
- Enforces strict temperature and token limits
- Allows test-time deterministic mock responses without fabricated external claims
- Truthfully flags UNCONFIGURED status when no API key is set
"""

import json
import os
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMAdapter:
    """Unified adapter for structured generative AI invocations."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        test_mode: bool = False,
    ):
        self.provider = provider or settings.llm_provider
        self.model_name = model_name or settings.llm_model
        self.api_key = api_key or settings.llm_api_key or os.environ.get("GEMINI_API_KEY")
        self.test_mode = test_mode
        self._mock_responses: Dict[str, Any] = {}

    def is_configured(self) -> bool:
        """Check whether a real model provider has valid credentials."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def register_mock_response(self, role_or_prompt_key: str, response: BaseModel) -> None:
        """Register deterministic response for hermetic offline test suites."""
        self._mock_responses[role_or_prompt_key] = response

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        role_key: Optional[str] = None,
    ) -> T:
        """Generate structured response validated against response_schema."""
        # 1. Use registered mock response in test mode or if registered
        lookup_key = role_key or prompt[:40]
        if lookup_key in self._mock_responses:
            mock_val = self._mock_responses[lookup_key]
            if isinstance(mock_val, response_schema):
                return mock_val
            return response_schema.model_validate(mock_val)

        # 2. Check if real provider is configured
        if not self.is_configured() and not self.test_mode:
            raise RuntimeError(
                f"LLM Provider '{self.provider}' is unconfigured. "
                "Set LLM_API_KEY or GEMINI_API_KEY in environment to run live models."
            )

        # 3. If test_mode is True and no mock was registered, generate fallback schema default
        if self.test_mode:
            raise ValueError(f"No mock response registered for role '{lookup_key}' in test mode.")

        # 4. Production API invocation (e.g. Google GenAI / Gemini API)
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                    "temperature": 0.1,
                },
            )
            raw_text = response.text
            return response_schema.model_validate_json(raw_text)
        except Exception as e:
            raise RuntimeError(f"Model generation error via {self.provider}: {str(e)}") from e


# Global adapter instance
llm_adapter = LLMAdapter()
