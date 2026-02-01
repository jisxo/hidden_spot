import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        load_dotenv(override=True)
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            # We allow it to be empty for now but it will fail on actual calls
            print("Warning: Supabase credentials not found in environment variables.")
        self.supabase: Client = create_client(url, key) if url and key else None

    async def get_restaurants(self, min_score: int = 0, keyword: str = None):
        if not self.supabase:
            return []
        
        query = self.supabase.table("restaurants").select("*")
        
        if min_score > 0:
            query = query.gte("ai_score", min_score)
        
        response = query.execute()
        data = response.data
        
        if not data:
            return []

        if keyword:
            keyword = keyword.lower()
            
            # Synonym expansion
            synonyms = {
                "회": ["사시미", "스시"],
                "사시미": ["회"],
                "초밥": ["스시"],
                "스시": ["초밥", "사시미", "회"],
                "탕": ["국물", "찌개"],
                "국물": ["탕", "찌개"],
                "면": ["국수", "라멘", "우동", "파스타"],
                "고기": ["구이", "스테이크", "바베큐"]
            }
            
            search_keywords = [keyword]
            if keyword in synonyms:
                search_keywords.extend(synonyms[keyword])

            filtered_data = []
            for item in data:
                # Prepare searchable text from item
                name = item.get("name", "").lower()
                address = item.get("address", "").lower()
                menus = [m.lower() for m in item.get("must_eat_menus", [])]
                tags = [t.lower() for t in item.get("search_tags", [])]
                
                match = False
                for kw in search_keywords:
                    if kw in name or kw in address or any(kw in m for m in menus) or any(kw in t for t in tags):
                        match = True
                        break
                
                if match:
                    filtered_data.append(item)
            return filtered_data
            
        return data

    async def save_restaurant(self, data: dict):
        if not self.supabase:
            return None
        
        response = self.supabase.table("restaurants").upsert(data, on_conflict="naver_place_id").execute()
        return response.data[0] if response.data else None

    async def get_restaurant_by_naver_id(self, naver_place_id: str):
        if not self.supabase:
            return None
        
        response = self.supabase.table("restaurants").select("*").eq("naver_place_id", naver_place_id).execute()
        return response.data[0] if response.data else None

    async def get_restaurant_by_id(self, restaurant_id: str):
        if not self.supabase:
            return None
        
        response = self.supabase.table("restaurants").select("*").eq("id", restaurant_id).execute()
        return response.data[0] if response.data else None

    async def delete_restaurant(self, restaurant_id: str):
        if not self.supabase:
            return None
        
        response = self.supabase.table("restaurants").delete().eq("id", restaurant_id).execute()
        return response.data

    async def delete_all_restaurants(self):
        if not self.supabase:
            return None
        
        # Supabase requires a filter for delete, so we use a filter that matches everything
        # or we can use a raw SQL if needed, but via SDK we usually use .neq("id", "00000000-0000-0000-0000-000000000000")
        response = self.supabase.table("restaurants").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return response.data

db = Database()
