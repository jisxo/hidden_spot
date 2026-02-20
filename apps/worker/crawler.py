import asyncio
import os
import random
import re
from typing import Any

from playwright.async_api import async_playwright


class NaverMapsCrawler:
    async def crawl(self, url: str) -> dict[str, Any]:
        retry_count = int(os.getenv("CRAWL_RETRY_COUNT", "2"))
        delay_ms = int(os.getenv("CRAWL_DELAY_MS", "1200"))
        last_error: Exception | None = None

        for attempt in range(retry_count + 1):
            try:
                return await self._crawl_once(url=url, delay_ms=delay_ms)
            except Exception as exc:
                last_error = exc
                if attempt >= retry_count:
                    break
                await asyncio.sleep((delay_ms / 1000.0) * (attempt + 1))

        raise RuntimeError(f"crawl failed after retry: {last_error}")

    async def _crawl_once(self, url: str, delay_ms: int) -> dict[str, Any]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=os.getenv("PLAYWRIGHT_HEADLESS", "true") == "true")
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(delay_ms / 1000.0 + random.uniform(0.2, 0.8))

            current_url = page.url
            place_id = self._extract_place_id(current_url)

            html = await page.content()

            name = ""
            address = ""
            reviews: list[str] = []

            try:
                iframe_el = await page.wait_for_selector("#entryIframe", timeout=10000)
                frame = await iframe_el.content_frame()
                if frame:
                    name = await self._first_text(frame, ["span.GHAhO", "span.Fc7rM", "h1", "h2"])
                    address = await self._first_text(frame, ["span.LDkhd", "span.yx8vA", "span.addr"])
                    reviews = await self._extract_reviews(frame)
            except Exception:
                pass

            if not place_id:
                place_id = self._extract_place_id(url) or ""

            await context.close()
            await browser.close()

            return {
                "source_url": url,
                "final_url": current_url,
                "naver_place_id": place_id,
                "name": name,
                "address": address,
                "review_count": len(reviews),
                "reviews": reviews,
                "raw_html": html,
            }

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

        result = await frame.evaluate(
            """() => {
            const list = [];
            const nodes = Array.from(document.querySelectorAll('li, div'));
            for (const node of nodes) {
              const t = (node.innerText || '').trim();
              if (!t || t.length < 12) continue;
              if (t.includes('더보기') || t.includes('답글')) continue;
              list.push(t.split('\n')[0]);
            }
            const dedup = Array.from(new Set(list));
            return dedup.slice(0, 500);
            }"""
        )
        return result

    def _extract_place_id(self, url: str) -> str | None:
        match = re.search(r"/place/(\d+)", url)
        if match:
            return match.group(1)
        return None
