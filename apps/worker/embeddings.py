import os
from typing import Any

import google.generativeai as genai


class EmbeddingGenerator:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")
        self.enabled = bool(self.api_key)
        if self.enabled:
            genai.configure(api_key=self.api_key)

    def embed(self, text: str) -> list[float] | None:
        if not self.enabled:
            return None
        result: Any = genai.embed_content(model=self.model, content=text)
        emb = result.get("embedding")
        if not emb:
            return None
        return [float(v) for v in emb]
