import hashlib
import json
import os
from pathlib import Path
from typing import Any

import google.generativeai as genai


def _load_prompt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fallback_chunk_summary(reviews: list[str]) -> dict[str, Any]:
    top = reviews[:2]
    return {
        "vibe": "담백하고 실사용자 중심 리뷰가 많은 분위기",
        "signature_menu": [],
        "tips": ["피크타임 대기 가능성 확인"],
        "summary": " ".join(top)[:300] if top else "리뷰 데이터가 제한적입니다.",
    }


def _fallback_final(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    summary_lines = [c.get("summary", "") for c in chunks if c.get("summary")]
    merged = "\n".join(summary_lines[:3]) or "리뷰 기반 자동 요약을 생성하지 못했습니다."
    return {
        "summary_3lines": merged,
        "vibe": "실사용 기반 후기 혼합",
        "signature_menu": list({m for c in chunks for m in c.get("signature_menu", [])})[:5],
        "tips": list({t for c in chunks for t in c.get("tips", [])})[:5],
        "score": 70,
        "ad_review_ratio": 0.0,
    }


class ChunkedAnalyzer:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.prompt_version = os.getenv("PROMPT_VERSION", "v1")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "80"))

        self.chunk_prompt_path = f"prompts/{self.prompt_version}/chunk_prompt.md"
        self.analysis_prompt_path = f"prompts/{self.prompt_version}/analysis_prompt.md"
        self.chunk_prompt = _load_prompt(self.chunk_prompt_path)
        self.analysis_prompt = _load_prompt(self.analysis_prompt_path)
        self.prompt_hash = hashlib.sha256((self.chunk_prompt + self.analysis_prompt).encode("utf-8")).hexdigest()

        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)

    def analyze(self, reviews: list[str]) -> dict[str, Any]:
        chunks = _chunked(reviews, self.chunk_size)
        chunk_summaries: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0

        for chunk in chunks:
            if self.model is None:
                chunk_summaries.append(_fallback_chunk_summary(chunk))
                continue

            response = self.model.generate_content(
                f"{self.chunk_prompt}\n\n리뷰 묶음:\n" + "\n".join(chunk),
                generation_config={"response_mime_type": "application/json"},
            )
            parsed = json.loads(response.text)
            chunk_summaries.append(parsed)

            usage = getattr(response, "usage_metadata", None)
            if usage:
                total_input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                total_output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)

        if self.model is None:
            final = _fallback_final(chunk_summaries)
            llm_model = "disabled"
        else:
            response = self.model.generate_content(
                f"{self.analysis_prompt}\n\nchunk summaries:\n{json.dumps(chunk_summaries, ensure_ascii=False)}",
                generation_config={"response_mime_type": "application/json"},
            )
            final = json.loads(response.text)
            llm_model = self.model_name
            usage = getattr(response, "usage_metadata", None)
            if usage:
                total_input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                total_output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)

        return {
            "result": final,
            "chunk_summaries": chunk_summaries,
            "chunk_count": len(chunks),
            "llm_model": llm_model,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
        }
