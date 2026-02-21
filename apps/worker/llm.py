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
    review_summary = {
        "one_line_copy": merged,
        "tags": [],
        "taste_profile": {"category_name": "실사용 기반 후기 혼합", "metrics": []},
        "pro_tips": list({t for c in chunks for t in c.get("tips", [])})[:5],
        "negative_points": [],
    }
    return {
        "restaurant_name": "",
        "recommendation_score": 70,
        "must_eat_menus": list({m for c in chunks for m in c.get("signature_menu", [])})[:5],
        "categories": [],
        "review_summary": review_summary,
        "transport_info": "",
        "ad_review_ratio": 0.0,
    }


def _coerce_json_object(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
    return None


def _ensure_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = str(item or "").strip()
        if s:
            out.append(s)
    return out


def _normalize_metrics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        text = str(item.get("text") or "").strip()
        raw_score = item.get("score")
        score = 0
        try:
            score = int(float(raw_score))
        except Exception:
            score = 0
        if score < 1:
            score = 1
        if score > 5:
            score = 5
        if not label and not text:
            continue
        out.append({"label": label, "score": score, "text": text})
    return out[:4]


def _normalize_final(payload: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    review_summary = payload.get("review_summary")
    if not isinstance(review_summary, dict):
        review_summary = {}

    one_line_copy = str(
        review_summary.get("one_line_copy")
        or payload.get("summary_3lines")
        or ""
    ).strip()
    if not one_line_copy:
        summary_lines = [c.get("summary", "") for c in chunks if c.get("summary")]
        one_line_copy = ("\n".join(summary_lines[:3]) or "리뷰 기반 자동 요약을 생성하지 못했습니다.").strip()

    taste_profile = review_summary.get("taste_profile")
    if not isinstance(taste_profile, dict):
        taste_profile = {}
    category_name = str(
        taste_profile.get("category_name")
        or payload.get("vibe")
        or "리뷰 기반 카테고리"
    ).strip()
    metrics = _normalize_metrics(taste_profile.get("metrics"))

    must_eat_menus = _ensure_list_str(payload.get("must_eat_menus") or payload.get("signature_menu"))
    pro_tips = _ensure_list_str(review_summary.get("pro_tips") or payload.get("tips"))
    tags = _ensure_list_str(review_summary.get("tags"))
    negative_points = _ensure_list_str(review_summary.get("negative_points"))
    categories = _ensure_list_str(payload.get("categories"))
    if not categories and category_name:
        categories = [category_name]
    if not tags:
        for menu in must_eat_menus[:3]:
            compact = menu.replace("⭐", "").replace(" ", "")
            if compact:
                tags.append(f"#{compact}")
        if category_name:
            tags.append(f"#{category_name.replace(' ', '')}")

    if len(metrics) < 4:
        fallback_metrics = [
            {"label": "맛의 완성도", "score": 4, "text": "리뷰 기반으로 전반적 만족도가 높음"},
            {"label": "대표 메뉴 만족도", "score": 4, "text": "시그니처 메뉴 언급 비중이 높음"},
            {"label": "공간 분위기", "score": 4, "text": "분위기 관련 긍정 리뷰가 확인됨"},
            {"label": "재방문 의사", "score": 4, "text": "재방문/추천 의도가 관찰됨"},
        ]
        for metric in fallback_metrics:
            if len(metrics) >= 4:
                break
            metrics.append(metric)

    raw_score = payload.get("recommendation_score", payload.get("score", 70))
    try:
        score = int(float(raw_score))
    except Exception:
        score = 70
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    raw_ad_ratio = payload.get("ad_review_ratio", 0.0)
    try:
        ad_review_ratio = float(raw_ad_ratio)
    except Exception:
        ad_review_ratio = 0.0
    if ad_review_ratio < 0:
        ad_review_ratio = 0.0
    if ad_review_ratio > 1:
        ad_review_ratio = 1.0

    normalized_review_summary = {
        "one_line_copy": one_line_copy,
        "tags": tags,
        "taste_profile": {
            "category_name": category_name,
            "metrics": metrics,
        },
        "pro_tips": pro_tips,
        "negative_points": negative_points,
    }

    return {
        "restaurant_name": str(payload.get("restaurant_name") or "").strip(),
        "recommendation_score": score,
        "must_eat_menus": must_eat_menus,
        "categories": categories,
        "review_summary": normalized_review_summary,
        "transport_info": str(payload.get("transport_info") or "").strip(),
        "ad_review_ratio": ad_review_ratio,
        # backward-compatible flattened keys
        "summary_3lines": one_line_copy,
        "vibe": category_name,
        "signature_menu": must_eat_menus,
        "tips": pro_tips,
        "score": score,
    }


class ChunkedAnalyzer:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.requested_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.model_name = self.requested_model
        self.prompt_version = os.getenv("PROMPT_VERSION", "v1")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "80"))
        self._fallback_applied = False

        self.chunk_prompt_path = f"prompts/{self.prompt_version}/chunk_prompt.md"
        self.analysis_prompt_path = f"prompts/{self.prompt_version}/analysis_prompt.md"
        self.chunk_prompt = _load_prompt(self.chunk_prompt_path)
        self.analysis_prompt = _load_prompt(self.analysis_prompt_path)
        self.prompt_hash = hashlib.sha256((self.chunk_prompt + self.analysis_prompt).encode("utf-8")).hexdigest()

        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._resolve_model_name()
            self.model = genai.GenerativeModel(self.model_name)

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
                if "generateContent" in methods:
                    supported.add(m.name)
            return supported
        except Exception:
            return set()

    def _resolve_model_name(self) -> None:
        supported = self._list_supported_models()
        if not supported:
            return

        requested_full = self._normalize_model_name(self.requested_model)
        if requested_full in supported:
            self.model_name = self.requested_model
            return

        preferred = [
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-flash-latest",
            "models/gemini-3-flash-preview",
        ]
        chosen = next((m for m in preferred if m in supported), None)
        if not chosen:
            chosen = sorted(supported)[0]

        self.model_name = chosen.removeprefix("models/")
        self._fallback_applied = True

    def _switch_model_on_generation_error(self, exc: Exception) -> bool:
        if self.model is None:
            return False
        if self._fallback_applied:
            return False

        msg = str(exc).lower()
        if "404" not in msg and "not found" not in msg and "not supported" not in msg:
            return False

        supported = self._list_supported_models()
        if not supported:
            return False

        current_full = self._normalize_model_name(self.model_name)
        preferred = [
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-flash-latest",
            "models/gemini-3-flash-preview",
        ]
        fallback_full = next((m for m in preferred if m in supported and m != current_full), None)
        if not fallback_full:
            return False

        self.model_name = fallback_full.removeprefix("models/")
        self.model = genai.GenerativeModel(self.model_name)
        self._fallback_applied = True
        return True

    def analyze(self, reviews: list[str], context: dict[str, Any] | None = None) -> dict[str, Any]:
        chunks = _chunked(reviews, self.chunk_size)
        chunk_summaries: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        context = context or {}
        context_text = (
            f"매장명: {str(context.get('name') or '').strip()}\n"
            f"주소: {str(context.get('address') or '').strip()}\n"
        ).strip()

        for chunk in chunks:
            if self.model is None:
                chunk_summaries.append(_fallback_chunk_summary(chunk))
                continue

            try:
                response = self.model.generate_content(
                    f"{self.chunk_prompt}\n\n리뷰 묶음:\n" + "\n".join(chunk),
                    generation_config={"response_mime_type": "application/json"},
                )
            except Exception as exc:
                if self._switch_model_on_generation_error(exc):
                    response = self.model.generate_content(
                        f"{self.chunk_prompt}\n\n리뷰 묶음:\n" + "\n".join(chunk),
                        generation_config={"response_mime_type": "application/json"},
                    )
                else:
                    chunk_summaries.append(_fallback_chunk_summary(chunk))
                    continue

            try:
                parsed = _coerce_json_object(json.loads(response.text))
                if not parsed:
                    chunk_summaries.append(_fallback_chunk_summary(chunk))
                    continue
                chunk_summaries.append(parsed)
            except Exception:
                chunk_summaries.append(_fallback_chunk_summary(chunk))
                continue

            usage = getattr(response, "usage_metadata", None)
            if usage:
                total_input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                total_output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)

        if self.model is None:
            final = _normalize_final(_fallback_final(chunk_summaries), chunk_summaries)
            llm_model = "disabled"
        else:
            try:
                response = self.model.generate_content(
                    (
                        f"{self.analysis_prompt}\n\n"
                        f"매장 컨텍스트:\n{context_text}\n\n"
                        f"chunk summaries:\n{json.dumps(chunk_summaries, ensure_ascii=False)}"
                    ),
                    generation_config={"response_mime_type": "application/json"},
                )
                parsed_final = _coerce_json_object(json.loads(response.text)) or _fallback_final(chunk_summaries)
                final = _normalize_final(parsed_final, chunk_summaries)
                llm_model = self.model_name
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    total_input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                    total_output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)
            except Exception as exc:
                if self._switch_model_on_generation_error(exc):
                    try:
                        response = self.model.generate_content(
                            (
                                f"{self.analysis_prompt}\n\n"
                                f"매장 컨텍스트:\n{context_text}\n\n"
                                f"chunk summaries:\n{json.dumps(chunk_summaries, ensure_ascii=False)}"
                            ),
                            generation_config={"response_mime_type": "application/json"},
                        )
                        parsed_final = _coerce_json_object(json.loads(response.text)) or _fallback_final(chunk_summaries)
                        final = _normalize_final(parsed_final, chunk_summaries)
                        llm_model = self.model_name
                    except Exception:
                        final = _normalize_final(_fallback_final(chunk_summaries), chunk_summaries)
                        llm_model = f"{self.model_name}-fallback"
                else:
                    final = _normalize_final(_fallback_final(chunk_summaries), chunk_summaries)
                    llm_model = f"{self.model_name}-fallback"

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
