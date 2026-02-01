from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from crawler import NaverMapsCrawler
from ai_analyzer import AIAnalyzer
from database import db

app = FastAPI(title="Hidden Spot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.post("/api/v1/restaurants/analyze")
async def analyze_restaurant(request: AnalyzeRequest):
    crawler = NaverMapsCrawler()
    try:
        # 1. Extract URL and get Place ID (handling naver.me redirects)
        raw_url = crawler.extract_url_from_text(request.url)
        if not raw_url:
            raise HTTPException(status_code=400, detail="No valid Naver Maps URL found in input")
        
        # We need to crawl to get the final place_id if it's a short URL
        # But we can try to check DB first if it's a standard URL
        place_id = crawler.get_place_id_from_url(raw_url)
        
        if place_id:
            existing = await db.get_restaurant_by_naver_id(place_id)
            if existing:
                return {
                    "restaurant": existing,
                    "raw_reviews": [],
                    "debug_logs": ["Restaurant found in database, skipped crawling."]
                }
        
        # 2. Crawl (This handles naver.me redirects internally now)
        data = await crawler.crawl_restaurant(request.url)
        if "error" in data:
            raise HTTPException(status_code=500, detail=f"Crawling failed: {data['error']}")
        
        # Update place_id from crawled data if we didn't have it
        place_id = data.get("naver_place_id")
        
        # Check DB again with the actual ID after redirect
        existing = await db.get_restaurant_by_naver_id(place_id)
        if existing:
            return {
                "restaurant": existing,
                "raw_reviews": data.get("reviews", []),
                "debug_logs": data.get("debug_logs", [])
            }
        
        # 3. AI Analysis
        analyzer = AIAnalyzer()
        try:
            analysis = await analyzer.analyze_restaurant(data)
        except Exception as ai_e:
            print(f"AI Analysis failed: {ai_e}")
            # Fallback for save if AI fails but we have basic data
            # (Though in this app AI is core, so we might want to fail)
            raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(ai_e)}")
        
        # 4. Prepare for DB
        lat = data.get("latitude") or 37.5665
        lng = data.get("longitude") or 126.9780 
        
        save_data = {
            "naver_place_id": place_id,
            "name": analysis.restaurant_name,
            "address": data.get("address", ""),
            "latitude": lat,
            "longitude": lng,
            "ai_score": analysis.recommendation_score,
            "transport_info": analysis.transport_info,
            "summary_json": analysis.review_summary.model_dump(),
            "must_eat_menus": analysis.must_eat_menus,
            "search_tags": list(set(analysis.must_eat_menus + analysis.categories + [analysis.restaurant_name, data.get("address", "")])),
            "original_url": raw_url,
            "raw_reviews": data.get("reviews", [])
        }
        
        saved = await db.save_restaurant(save_data)
        return {
            "restaurant": saved,
            "raw_reviews": data.get("reviews", []),
            "debug_logs": data.get("debug_logs", [])
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await crawler.close_browser()

@app.get("/api/v1/restaurants")
async def list_restaurants(
    min_score: int = Query(0, ge=0, le=100),
    keyword: Optional[str] = None
):
    try:
        restaurants = await db.get_restaurants(min_score=min_score, keyword=keyword)
        return restaurants
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/restaurants/{id}/refresh")
async def refresh_restaurant(id: str):
    crawler = NaverMapsCrawler()
    try:
        # 1. Get existing restaurant to get original URL
        existing = await db.get_restaurant_by_id(id)
        if not existing:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        
        url = existing.get("original_url")
        if not url:
            raise HTTPException(status_code=400, detail="Original URL not found for this restaurant")

        # 2. Re-crawl
        data = await crawler.crawl_restaurant(url)
        if "error" in data:
            raise HTTPException(status_code=500, detail=f"Crawling failed: {data['error']}")
        
        # 3. AI Re-Analysis
        analyzer = AIAnalyzer()
        analysis = await analyzer.analyze_restaurant(data)
        
        # 4. Prepare Data (Keep same Place ID and ID)
        lat = data.get("latitude") or existing.get("latitude") or 37.5665
        lng = data.get("longitude") or existing.get("longitude") or 126.9780
        
        update_data = {
            "id": id, # Maintained UUID
            "naver_place_id": existing.get("naver_place_id"),
            "name": analysis.restaurant_name,
            "address": data.get("address") or existing.get("address"),
            "latitude": lat,
            "longitude": lng,
            "ai_score": analysis.recommendation_score,
            "transport_info": analysis.transport_info,
            "summary_json": analysis.review_summary.model_dump(),
            "must_eat_menus": analysis.must_eat_menus,
            "search_tags": list(set(analysis.must_eat_menus + analysis.categories + [analysis.restaurant_name, data.get("address", "")])),
            "original_url": url,
            "raw_reviews": data.get("reviews", [])
        }
        
        saved = await db.save_restaurant(update_data)
        return {
            "restaurant": saved,
            "raw_reviews": data.get("reviews", []),
            "debug_logs": data.get("debug_logs", [])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await crawler.close_browser()

@app.delete("/api/v1/restaurants/{id}")
async def delete_restaurant(id: str):
    try:
        result = await db.delete_restaurant(id)
        if not result:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        return {"status": "success", "message": "Restaurant deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
