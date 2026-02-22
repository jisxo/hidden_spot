import asyncio
import json
import os
import random
import re
from html import unescape
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

            html_main = await page.content()
            html = html_main

            name = ""
            address = ""
            reviews: list[str] = []
            latitude: float | None = None
            longitude: float | None = None

            frame = await self._get_entry_frame(page=page, retries=3, retry_delay_ms=700)
            if frame:
                try:
                    name, address = await self._extract_name_address_with_retry(
                        frame=frame, retries=3, retry_delay_ms=450
                    )
                    reviews = await self._extract_reviews_with_retry(frame=frame, retries=3)
                    html = await frame.content()
                    latitude, longitude = await self._extract_coordinates(page=page, frame=frame)
                except Exception:
                    pass

            html_name, html_address = self._extract_name_address_from_html(html)
            if not name:
                name = html_name
            if not address:
                address = html_address

            if latitude is None or longitude is None:
                lat_guess, lng_guess = self._extract_coordinates_from_text(f"{html_main}\n{html}")
                latitude = latitude if latitude is not None else lat_guess
                longitude = longitude if longitude is not None else lng_guess

            if not place_id:
                place_id = self._extract_place_id(url) or ""

            # Fallback route: if iframe extraction is weak, use mobile place pages.
            if place_id and (not name or len(reviews) < 3):
                mobile = await self._crawl_mobile_fallback(context=context, place_id=place_id, delay_ms=delay_ms)
                if mobile:
                    name = name or mobile.get("name", "")
                    address = address or mobile.get("address", "")
                    latitude = latitude if latitude is not None else mobile.get("latitude")
                    longitude = longitude if longitude is not None else mobile.get("longitude")
                    reviews = self._dedupe_texts([*reviews, *mobile.get("reviews", [])])[:500]
                    mobile_html = mobile.get("raw_html", "")
                    if mobile_html:
                        html = mobile_html

            if not name:
                name = self._extract_title_name(html_main) or self._extract_title_name(html) or place_id

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

    async def _get_entry_frame(self, page, retries: int, retry_delay_ms: int):
        for _ in range(max(1, retries)):
            try:
                iframe_el = await page.query_selector("#entryIframe")
                if iframe_el:
                    frame = await iframe_el.content_frame()
                    if frame:
                        return frame
            except Exception:
                pass
            await asyncio.sleep(retry_delay_ms / 1000.0)
        return None

    async def _extract_name_address_with_retry(self, frame, retries: int, retry_delay_ms: int) -> tuple[str, str]:
        name = ""
        address = ""
        for _ in range(max(1, retries)):
            if not name:
                name = await self._first_text(frame, ["span.GHAhO", "span.Fc7rM", "h1", "h2", "[data-testid='place-title']"])
            if not address:
                address = await self._first_text(
                    frame,
                    [
                        "span.pz7wy",
                        "span.LDkhd",
                        "span.yx8vA",
                        "span.addr",
                        "[data-testid='address']",
                    ],
                )
            if name and address:
                break
            try:
                await frame.evaluate("window.scrollBy(0, 400)")
            except Exception:
                pass
            await asyncio.sleep(retry_delay_ms / 1000.0)
        return name.strip(), address.strip()

    async def _extract_reviews_with_retry(self, frame, retries: int) -> list[str]:
        merged: list[str] = []
        for idx in range(max(1, retries)):
            blocks = await self._extract_reviews(frame, scroll_rounds=8 + idx * 4)
            merged.extend(blocks)
            merged = self._dedupe_texts(merged)
            if len(merged) >= 20:
                break
        return merged[:500]

    async def _first_text(self, frame, selectors: list[str]) -> str:
        for selector in selectors:
            loc = frame.locator(selector).first
            if await loc.count() > 0:
                text = (await loc.inner_text()).strip()
                if text:
                    return text
        return ""

    async def _extract_reviews(self, frame, scroll_rounds: int = 8) -> list[str]:
        try:
            tabs = frame.get_by_text(re.compile(r"리뷰|방문자리뷰|Visitor Reviews"), exact=False)
            if await tabs.count() > 0:
                await tabs.first.click()
                await asyncio.sleep(1.2)
        except Exception:
            pass

        for _ in range(max(1, scroll_rounds)):
            try:
                await frame.evaluate("window.scrollBy(0, 1800)")
            except Exception:
                pass
            await asyncio.sleep(0.5)

        try:
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
        except Exception:
            return []

        cleaned: list[str] = []
        for block in blocks:
            text = self._clean_review_block(block)
            if text:
                cleaned.append(text)

        return self._dedupe_texts(cleaned)[:500]

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

    async def _crawl_mobile_fallback(self, context, place_id: str, delay_ms: int) -> dict[str, Any]:
        page = await context.new_page()
        try:
            home_url = f"https://m.place.naver.com/restaurant/{place_id}/home"
            await page.goto(home_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(delay_ms / 1000.0 + random.uniform(0.2, 0.8))
            home_html = await page.content()

            name, address = self._extract_name_address_from_html(home_html)
            lat, lng = self._extract_coordinates_from_text(home_html)

            review_url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor"
            await page.goto(review_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1.0)
            for _ in range(8):
                try:
                    await page.evaluate("window.scrollBy(0, 1800)")
                except Exception:
                    pass
                await asyncio.sleep(0.3)

            blocks: list[str] = await page.evaluate(
                """() => {
                const list = [];
                const nodes = Array.from(document.querySelectorAll('li, div'));
                for (const node of nodes) {
                  const t = (node.innerText || '').trim();
                  if (!t || t.length < 20) continue;
                  list.push(t);
                }
                return list.slice(0, 400);
                }"""
            )
            cleaned_reviews = [self._clean_review_block(block) for block in blocks]
            reviews = self._dedupe_texts([x for x in cleaned_reviews if x])[:500]

            review_html = await page.content()
            if not name or not address:
                r_name, r_addr = self._extract_name_address_from_html(review_html)
                name = name or r_name
                address = address or r_addr
            if lat is None or lng is None:
                lat2, lng2 = self._extract_coordinates_from_text(review_html)
                lat = lat if lat is not None else lat2
                lng = lng if lng is not None else lng2

            return {
                "name": name,
                "address": address,
                "latitude": lat,
                "longitude": lng,
                "reviews": reviews,
                "raw_html": review_html or home_html,
            }
        except Exception:
            return {}
        finally:
            try:
                await page.close()
            except Exception:
                pass

    def _extract_name_address_from_html(self, html: str) -> tuple[str, str]:
        if not html:
            return "", ""
        name = ""
        address = ""

        for key in ["businessName", "name", "title", "placeName"]:
            value = self._extract_json_string(html, key)
            if self._looks_like_place_name(value):
                name = value
                break

        for key in ["roadAddress", "address", "jibunAddress"]:
            value = self._extract_json_string(html, key)
            if value and self._looks_like_address(value):
                address = value
                break

        if not name:
            name = self._extract_title_name(html)
        return name, address

    def _extract_coordinates_from_text(self, text: str) -> tuple[float | None, float | None]:
        if not text:
            return None, None

        lat_match = (
            re.search(r'"y"\s*:\s*"?(-?[\d.]+)"?', text)
            or re.search(r'"lat(?:itude)?"\s*:\s*"?(-?[\d.]+)"?', text)
            or re.search(r'"mapy"\s*:\s*"?(-?[\d.]+)"?', text)
        )
        lng_match = (
            re.search(r'"x"\s*:\s*"?(-?[\d.]+)"?', text)
            or re.search(r'"(?:lng|longitude)"\s*:\s*"?(-?[\d.]+)"?', text)
            or re.search(r'"mapx"\s*:\s*"?(-?[\d.]+)"?', text)
        )

        if not lat_match or not lng_match:
            return None, None
        try:
            return float(lat_match.group(1)), float(lng_match.group(1))
        except Exception:
            return None, None

    def _extract_json_string(self, text: str, key: str) -> str:
        pattern = rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\]|\\.)*)"'
        match = re.search(pattern, text)
        if not match:
            return ""
        raw = match.group(1)
        try:
            value = json.loads(f'"{raw}"')
        except Exception:
            value = unescape(raw).replace("\\n", " ")
        return re.sub(r"\s+", " ", str(value)).strip()

    def _extract_title_name(self, html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        title = re.sub(r"\s+", " ", unescape(match.group(1))).strip()
        title = re.sub(r"\s*[:\-|]\s*네이버.*$", "", title).strip()
        return title if self._looks_like_place_name(title) else ""

    def _looks_like_place_name(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        if any(marker in lowered for marker in ["naver", "네이버 지도", "localhost"]):
            return False
        if len(text) > 80:
            return False
        return len(text.strip()) >= 2

    def _looks_like_address(self, text: str) -> bool:
        if not text:
            return False
        return any(token in text for token in ["시", "군", "구", "로", "길", "동", "읍", "면"])

    def _dedupe_texts(self, texts: list[str]) -> list[str]:
        dedup: list[str] = []
        seen: set[str] = set()
        for item in texts:
            value = re.sub(r"\s+", " ", (item or "")).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            dedup.append(value)
        return dedup

    def _extract_place_id(self, url: str) -> str | None:
        match = re.search(r"/(?:entry/)?place/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/restaurant/([A-Za-z0-9_-]+)", url)
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
