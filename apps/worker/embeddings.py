import os
from typing import Any

import google.generativeai as genai


class EmbeddingGenerator:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.requested_model = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")
        self.model = self.requested_model
        self.target_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
        self._fallback_applied = False
        self.enabled = bool(self.api_key)
        if self.enabled:
            genai.configure(api_key=self.api_key)
            self._resolve_model()

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        if name.startswith("models/"):
            return name
        return f"models/{name}"

    def _list_supported_models(self) -> set[str]:
        try:
            supported: set[str] = set()
            for m in genai.list_models():
                methods = set(getattr(m, "supported_generation_methods", []) or [])
                if "embedContent" in methods:
                    supported.add(m.name)
            return supported
        except Exception:
            return set()

    def _resolve_model(self) -> None:
        supported = self._list_supported_models()
        if not supported:
            return

        requested_full = self._normalize_model_name(self.requested_model)
        if requested_full in supported:
            self.model = requested_full
            return

        preferred = ["models/gemini-embedding-001"]
        chosen = next((m for m in preferred if m in supported), None)
        if not chosen:
            chosen = sorted(supported)[0]

        self.model = chosen
        self._fallback_applied = True

    def _switch_model_on_error(self, exc: Exception) -> bool:
        if self._fallback_applied:
            return False

        msg = str(exc).lower()
        if "404" not in msg and "not found" not in msg and "not supported" not in msg:
            return False

        supported = self._list_supported_models()
        if not supported:
            return False

        current_full = self._normalize_model_name(self.model)
        fallback_full = next((m for m in sorted(supported) if m != current_full), None)
        if not fallback_full:
            return False

        self.model = fallback_full
        self._fallback_applied = True
        return True

    def _embed_once(self, text: str) -> Any:
        try:
            return genai.embed_content(model=self.model, content=text, output_dimensionality=self.target_dim)
        except TypeError:
            return genai.embed_content(model=self.model, content=text)

    def embed(self, text: str) -> list[float] | None:
        if not self.enabled:
            return None
        try:
            result: Any = self._embed_once(text)
        except Exception as exc:
            if self._switch_model_on_error(exc):
                try:
                    result = self._embed_once(text)
                except Exception:
                    return None
            else:
                return None
        emb = result.get("embedding")
        if not emb:
            return None
        vector = [float(v) for v in emb]
        if self.target_dim > 0:
            if len(vector) < self.target_dim:
                return None
            if len(vector) > self.target_dim:
                vector = vector[: self.target_dim]
        return vector
