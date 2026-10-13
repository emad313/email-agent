"""Small Ollama HTTP client with bounded JSON output."""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from config import OllamaConfig


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: OllamaConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.logger = logging.getLogger(__name__)

    def check_available(self) -> bool:
        try:
            response = self.session.get(
                f"{self.config.endpoint}/api/tags", timeout=self.config.timeout_seconds
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            return any(item.get("name") == self.config.model for item in models)
        except (requests.RequestException, ValueError) as exc:
            raise OllamaError(f"Ollama unavailable: {exc}") from exc

    def generate(self, prompt: str, system: str = "") -> str:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "format": "json",
            "options": {
                "num_ctx": self.config.context_length,
                "num_predict": self.config.max_output_tokens,
            },
        }
        try:
            response = self.session.post(
                f"{self.config.endpoint}/api/generate",
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            result: Any = response.json()
            text = result.get("response")
            if not isinstance(text, str) or not text.strip():
                raise OllamaError("Ollama returned no response text")
            return text
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama generation failed: {exc}") from exc
        except ValueError as exc:
            raise OllamaError("Ollama returned invalid JSON") from exc

    def generate_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        text = self.generate(prompt, system)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OllamaError("Model returned invalid task JSON") from exc
        if not isinstance(value, dict):
            raise OllamaError("Model JSON must be an object")
        return value
