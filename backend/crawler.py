import asyncio
import random
import re
from playwright.async_api import async_playwright
from typing import Dict, List, Optional
import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class NaverMapsCrawler:
    def __init__(self):
        self.browser = None
        self.context = None

    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )

    async def close_browser(self):
        if self.browser:
            await self.browser.close()

    def extract_url_from_text(self, text: str) -> Optional[str]:
        url_pattern = r'https?://[^\s{}()<>]+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def get_place_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r'place/(\d+)', url)
        if match:
            return match.group(1)
        return None

    async def crawl_restaurant(self, input_text: str) -> Dict:
        if not self.browser:
            await self.init_browser()

        debug_logs = []
        def log_debug(msg):
            print(msg)
            debug_logs.append(msg)

        url = self.extract_url_from_text(input_text)
        if not url:
            raise ValueError("No valid URL found in input")

        page = await self.context.new_page()
        log_debug(f"Starting crawl for: {url}")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.uniform(2.5, 4.0))

            current_url = page.url
            log_debug(f"Current URL after redirect/load: {current_url}")
            
            # 1. Handle "Search Result List" case
            if "search" in current_url:
                log_debug("Landed on search results. Attempting to select the first result.")
                search_iframe = page.frame_locator("#searchIframe")
                first_result = search_iframe.locator("li.VL6_C, li.UE7_r").first
                if await first_result.count() > 0:
                    await first_result.click()
                    await asyncio.sleep(2.0)
                    log_debug("Clicked first search result.")

            # 2. Extract Place ID
            current_url = page.url
            place_id = self.get_place_id_from_url(current_url)
            if not place_id:
                content = await page.content()
                match = re.search(r'"id":"(\d+)"', content)
                if match:
                    place_id = match.group(1)
            
            log_debug(f"Place ID determined: {place_id}")

            # 3. Extract Info from #entryIframe
            iframe_selector = "#entryIframe"
            try:
                iframe_element = await page.wait_for_selector(iframe_selector, timeout=15000)
                iframe = await iframe_element.content_frame()
                if not iframe:
                    raise Exception("Could not access iframe content")
                log_debug("DEBUG: Iframe #entryIframe exists and content frame accessed.")
            except Exception as e:
                log_debug(f"DEBUG: Iframe #entryIframe error: {e}")
                raise Exception(f"Place entry iframe not found or inaccessible: {e}")

            # Robust Name/Address Extraction
            name = ""
            name_selectors = ["span.GHAhO", "span.Fc7rM", "span.place_alias_self", ".GHAhO", "h1", "h2"]
            for selector in name_selectors:
                el = iframe.locator(selector).first
                if await el.count() > 0:
                    name = await el.inner_text()
                    if name: break
            
            address = ""
            address_selectors = ["span.pz7wy", "span.LDkhd", "span.yx8vA", "span.addr", ".LDkhd", "a.PkgBl span"]
            for selector in address_selectors:
                el = iframe.locator(selector).first
                if await el.count() > 0:
                    address = await el.inner_text()
                    if address: break

            log_debug(f"Extracted Name: {name}, Address: {address}")

            # 4. Extract Reviews (Robust Heuristic-based approach)
            log_debug("--- Review Extraction Debug ---")
            
            # Navigate to the review tab if not already there
            review_tabs = iframe.get_by_text(re.compile(r"리뷰|방문자리뷰|내용|Visitor Reviews"), exact=False)
            tab_count = await review_tabs.count()
            log_debug(f"DEBUG: Found {tab_count} potential review tabs.")
            
            if tab_count > 0:
                await review_tabs.first.click()
                log_debug("DEBUG: Clicked review tab. Waiting for content...")
                await asyncio.sleep(2.5)
            
            # Scroll to load initial reviews
            log_debug("DEBUG: Scrolling to load reviews...")
            for _ in range(3):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(0.8)

            # Use JavaScript evaluation for robust extraction
            log_debug("DEBUG: Executing JS extraction heuristic...")
            extraction_results = await iframe.evaluate("""() => {
                const diag = { container: 'none', itemsFound: 0, selectorsTried: [] };
                
                const selectors = ['ul#_review_list', 'ul.OTi6Q', 'ul[class*="review"]', 'div[class*="review_list"]'];
                diag.selectorsTried = selectors;
                
                let reviewContainer = null;
                for (const s of selectors) {
                    reviewContainer = document.querySelector(s);
                    if (reviewContainer) {
                        diag.container = s;
                        break;
                    }
                }
                
                if (!reviewContainer) {
                    const anyButton = document.querySelector('a[role="button"]');
                    if (anyButton) diag.info = "Found a button but no container";
                    return { reviews: [], diag };
                }

                const items = Array.from(reviewContainer.querySelectorAll('li, div.place_apply_pui'));
                diag.itemsFound = items.length;
                
                const reviews = items.map(li => {
                    const candidates = Array.from(li.querySelectorAll('a[role="button"], span, div'))
                        .map(el => el.innerText.trim())
                        .filter(text => {
                            if (!text || text.length < 5) return false;
                            const noise = ['팔로우', '펼치기', '더보기', '방문', '별점', '답글', '사진', '리뷰'];
                            if (noise.some(n => text === n)) return false;
                            return true;
                        });

                    const sorted = candidates.sort((a, b) => b.length - a.length);
                    return sorted[0] || "";
                }).filter(text => text.length > 5);
                
                return { reviews, diag };
            }""")
            
            reviews = extraction_results.get('reviews', [])
            diag = extraction_results.get('diag', {})
            log_debug(f"DEBUG DIAGNOSTICS: {diag}")
            
            # Remove duplicates while preserving order
            reviews = list(dict.fromkeys(reviews))
            log_debug(f"Successfully collected {len(reviews)} unique reviews.")
            log_debug("--- End Review Extraction Debug ---")

            # 5. Extract Coordinates (Lat/Lng) - Multi-layered Scraping
            log_debug("Extracting coordinates directly from page content...")
            lat, lng = None, None

            # Layer 1: Try Naver/OGP Metadata (Most reliable if present)
            meta_patterns = [
                "meta[name='naver:location:latitude']",
                "meta[name='twitter:data1']", # Sometimes contains coords
                "meta[property='og:latitude']",
                "meta[property='place:location:latitude']"
            ]
            
            for selector in meta_patterns:
                try:
                    meta_el = await page.locator(selector).first
                    if await meta_el.count() > 0:
                        content = await meta_el.get_attribute("content")
                        if content and re.match(r'^-?\d+(\.\d+)?$', content):
                            lat = float(content)
                            break
                except: continue

            if lat: # If we got lat from meta, try to get lng similarly
                 for selector in ["meta[name='naver:location:longitude']", "meta[property='og:longitude']", "meta[property='place:location:longitude']"]:
                    try:
                        meta_el = await page.locator(selector).first
                        if await meta_el.count() > 0:
                            content = await meta_el.get_attribute("content")
                            if content and re.match(r'^-?\d+(\.\d+)?$', content):
                                lng = float(content)
                                break
                    except: continue

            # Layer 2: Evaluate JavaScript State (Strongest data source if metadata is missing)
            if not lat or not lng:
                try:
                    # Look for coords in common Naver Maps JS state objects
                    js_coords = await page.evaluate(r"""() => {
                        try {
                            // 1. Check window.__INITIAL_STATE__
                            const state = window.__INITIAL_STATE__;
                            if (state && state.place && state.place.summary) {
                                return { lat: state.place.summary.y, lng: state.place.summary.x };
                            }
                            // 2. Check for other patterns
                            const scripts = Array.from(document.scripts);
                            for (const s of scripts) {
                                if (s.textContent.includes('center')) {
                                   const match = s.textContent.match(/"x":([\d.]+),"y":([\d.]+)/) || s.textContent.match(/"lng":([\d.]+),"lat":([\d.]+)/);
                                   if (match) return { lat: parseFloat(match[2]), lng: parseFloat(match[1]) };
                                }
                            }
                        } catch(e) {}
                        return null;
                    }""")
                    if js_coords:
                        lat, lng = js_coords['lat'], js_coords['lng']
                        print(f"Coordinates extracted from JS evaluation: {lat}, {lng}")
                except Exception as eval_e:
                    print(f"JS evaluation for coordinates failed: {eval_e}")

            # Layer 3: Robust Regex Fallback (Main + Iframe)
            if not lat or not lng:
                print("Falling back to regex extraction...")
                content_main = await page.content()
                content_iframe = ""
                try: content_iframe = await iframe.locator("html").inner_html()
                except: pass
                
                full_content = content_main + content_iframe
                
                # Broad patterns for coordinate pairs
                patterns_lat = [
                    r'"y"\s*:\s*"?([\d.]+)"?', 
                    r'latitude"\s+content="([\d.]+)"', 
                    r'"lat"\s*:\s*"?([\d.]+)"?', 
                    r'lat\s*:\s*"?([\d.]+)"?'
                ]
                patterns_lng = [
                    r'"x"\s*:\s*"?([\d.]+)"?', 
                    r'longitude"\s+content="([\d.]+)"', 
                    r'"lng"\s*:\s*"?([\d.]+)"?', 
                    r'lng\s*:\s*"?([\d.]+)"?'
                ]
                
                for p_lat in patterns_lat:
                    match = re.search(p_lat, full_content)
                    if match:
                        lat = float(match.group(1))
                        break
                
                for p_lng in patterns_lng:
                    match = re.search(p_lng, full_content)
                    if match:
                        lng = float(match.group(1))
                        break
                
                # Check for "127.123,37.123" format or similar
                if not lat or not lng:
                    pair_match = re.search(r'([\d.]+)\s*,\s*([\d.]+)', full_content)
                    if pair_match:
                        # Guess based on magnitude (lat is ~37 in Korea)
                        v1, v2 = float(pair_match.group(1)), float(pair_match.group(2))
                        if 33 <= v1 <= 39 and 124 <= v2 <= 132:
                            lat, lng = v1, v2
                        elif 33 <= v2 <= 39 and 124 <= v1 <= 132:
                            lat, lng = v2, v1

            # Layer 4: Hard Fallback to Seoul Center if everything fails
            if not lat or not lng:
                print("Warning: All coordinate extraction methods failed. Using fallback (Seoul).")
                lat, lng = 37.5665, 126.9780

            if not name:
                name = await page.title()
                name = name.replace(" : 네이버 플레이스", "").strip()

            return {
                "naver_place_id": place_id or "unknown",
                "name": name or "Unnamed Restaurant",
                "address": address or "Address Not Found",
                "latitude": lat,
                "longitude": lng,
                "reviews": reviews,
                "original_url": url,
                "debug_logs": debug_logs
            }

        except Exception as e:
            print(f"Error during extraction for {url}: {e}")
            # Even if it fails, try to return whatever we have
            return {
                "error": str(e),
                "original_url": url,
                "debug_logs": debug_logs
            }
        finally:
            await page.close()


async def main():
    crawler = NaverMapsCrawler()
    # Test shortened URL from user
    url = "https://naver.me/531ffw6H" 
    data = await crawler.crawl_restaurant(url)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    await crawler.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
