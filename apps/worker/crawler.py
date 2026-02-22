import asyncio
import os
import random
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from playwright.async_api import async_playwright


class NaverMapsCrawler:
    async def crawl(self, url: str) -> dict[str, Any]:
        retry_count = int(os.getenv("CRAWL_RETRY_COUNT", "2"))
        delay_ms = int(os.getenv("CRAWL_DELAY_MS", "1200"))
        target_url = self._resolve_source_url(url)
        last_error: Exception | None = None

        for attempt in range(retry_count + 1):
            try:
                return await self._crawl_once(url=target_url, source_url=url, delay_ms=delay_ms)
            except Exception as exc:
                last_error = exc
                if attempt >= retry_count:
                    break
                await asyncio.sleep((delay_ms / 1000.0) * (attempt + 1))

        raise RuntimeError(f"crawl failed after retry: {last_error}")

    async def _crawl_once(self, url: str, source_url: str, delay_ms: int) -> dict[str, Any]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=os.getenv("PLAYWRIGHT_HEADLESS", "true") == "true")
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            context.set_default_timeout(20000)
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(delay_ms / 1000.0 + random.uniform(0.2, 0.8))

            current_url = page.url
            place_id = self._extract_place_id(current_url)

            html = await page.content()

            name = ""
            address = ""
            reviews: list[str] = []
            latitude: float | None = None
            longitude: float | None = None

            try:
                iframe_el = await page.wait_for_selector("#entryIframe", timeout=10000)
                frame = await iframe_el.content_frame()
                if frame:
                    name = await self._first_text(frame, ["span.GHAhO", "span.Fc7rM", "h1", "h2"])
                    address = await self._first_text(frame, ["span.pz7wy", "span.LDkhd", "span.yx8vA", "span.addr"])
                    reviews = await self._extract_reviews(frame)
                    # Prefer place iframe content over outer map shell HTML.
                    html = await frame.content()
                    latitude, longitude = await self._extract_coordinates(page=page, frame=frame)
            except Exception:
                pass

            if not place_id:
                place_id = self._extract_place_id(url) or ""

            await context.close()
            await browser.close()

            return {
                "source_url": source_url,
                "final_url": current_url,
                "naver_place_id": place_id,
                "name": name,
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
                "review_count": len(reviews),
                "reviews": reviews,
                "raw_html": html,
            }

    def _resolve_source_url(self, url: str) -> str:
        candidate = (url or "").strip()
        if not candidate:
            return url

        parsed = urlparse(candidate)
        host = parsed.netloc.lower()

        # naver.me short links frequently redirect to map entry URLs.
        if host.endswith("naver.me"):
            try:
                req = Request(
                    candidate,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        )
                    },
                    method="GET",
                )
                with urlopen(req, timeout=15) as resp:
                    resolved = (resp.geturl() or "").strip()
                if resolved:
                    return resolved
            except Exception:
                return candidate

        return candidate

    async def _first_text(self, frame, selectors: list[str]) -> str:
        for selector in selectors:
            loc = frame.locator(selector).first
            if await loc.count() > 0:
                text = (await loc.inner_text()).strip()
                if text:
                    return text
        return ""

    async def _extract_reviews(self, frame) -> list[str]:
        try:
            tabs = frame.get_by_text(re.compile(r"리뷰|방문자리뷰|Visitor Reviews"), exact=False)
            if await tabs.count() > 0:
                await tabs.first.click()
                await asyncio.sleep(1.2)
        except Exception:
            pass

        for _ in range(8):
            try:
                await frame.evaluate("window.scrollBy(0, 1800)")
            except Exception:
                pass
            await asyncio.sleep(0.5)

        blocks: list[str] = await frame.evaluate(
            """() => {
            const list = [];
            const nodes = Array.from(document.querySelectorAll('li'));
            for (const node of nodes) {
              const t = (node.innerText || '').trim();
              if (!t || t.length < 20) continue;
              list.push(t);
            }
            return list.slice(0, 300);
            }"""
        )

        cleaned: list[str] = []
        for block in blocks:
            text = self._clean_review_block(block)
            if text:
                cleaned.append(text)

        dedup = list(dict.fromkeys(cleaned))
        return dedup[:500]

    def _clean_review_block(self, raw: str) -> str:
        text = raw.replace("\r", "\n")
        if "더보기" in text:
            text = text.split("더보기", 1)[0]

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        filtered: list[str] = []
        for line in lines:
            if len(line) < 8:
                continue
            if any(
                marker in line
                for marker in [
                    "이 키워드를 선택한 인원",
                    "개의 리뷰가 더 있습니다",
                    "펼쳐보기",
                    "반응 남기기",
                    "방문일",
                    "인증 수단",
                    "알림받기",
                    "홈 메뉴 예약 리뷰 사진 정보",
                    "방문자 리뷰",
                    "블로그 리뷰",
                    "저장 거리뷰 공유 예약",
                ]
            ):
                continue
            if re.match(r"^리뷰\s*[\d,]+", line):
                continue
            if re.match(r"^\d{4}년 \d{1,2}월 \d{1,2}일", line):
                continue
            if re.match(r"^\d+번째 방문$", line):
                continue
            if line in {"팔로우", "다음"}:
                continue
            filtered.append(line)

        if not filtered:
            return ""

        merged = re.sub(r"\s+", " ", " ".join(filtered)).strip()
        if len(merged) < 25:
            return ""
        return merged

    def _extract_place_id(self, url: str) -> str | None:
        match = re.search(r"/(?:entry/)?place/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        return None

    async def _extract_coordinates(self, page, frame) -> tuple[float | None, float | None]:
        lat: float | None = None
        lng: float | None = None

        meta_patterns = [
            ("meta[name='naver:location:latitude']", "meta[name='naver:location:longitude']"),
            ("meta[property='og:latitude']", "meta[property='og:longitude']"),
            ("meta[property='place:location:latitude']", "meta[property='place:location:longitude']"),
        ]

        for lat_sel, lng_sel in meta_patterns:
            try:
                lat_el = page.locator(lat_sel).first
                lng_el = page.locator(lng_sel).first
                if await lat_el.count() > 0 and await lng_el.count() > 0:
                    lat_text = (await lat_el.get_attribute("content") or "").strip()
                    lng_text = (await lng_el.get_attribute("content") or "").strip()
                    if self._looks_number(lat_text) and self._looks_number(lng_text):
                        lat = float(lat_text)
                        lng = float(lng_text)
                        return lat, lng
            except Exception:
                continue

        try:
            js_coords = await page.evaluate(
                """() => {
                try {
                    const state = window.__INITIAL_STATE__;
                    if (state && state.place && state.place.summary) {
                        return { lat: Number(state.place.summary.y), lng: Number(state.place.summary.x) };
                    }
                } catch (_) {}
                return null;
                }"""
            )
            if (
                js_coords
                and isinstance(js_coords, dict)
                and isinstance(js_coords.get("lat"), (int, float))
                and isinstance(js_coords.get("lng"), (int, float))
            ):
                return float(js_coords["lat"]), float(js_coords["lng"])
        except Exception:
            pass

        try:
            content_main = await page.content()
            content_frame = await frame.content()
            full = f"{content_main}\n{content_frame}"
            lat_match = re.search(r'"y"\s*:\s*"?([\d.]+)"?', full) or re.search(r'"lat"\s*:\s*"?([\d.]+)"?', full)
            lng_match = re.search(r'"x"\s*:\s*"?([\d.]+)"?', full) or re.search(r'"lng"\s*:\s*"?([\d.]+)"?', full)
            if lat_match and lng_match:
                lat = float(lat_match.group(1))
                lng = float(lng_match.group(1))
                return lat, lng
        except Exception:
            pass

        return None, None

    def _looks_number(self, text: str) -> bool:
        return bool(re.match(r"^-?\d+(\.\d+)?$", text))
