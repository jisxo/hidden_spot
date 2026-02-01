import json
import os
import google.generativeai as genai
from typing import Dict, List, Union
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Metric(BaseModel):
    label: str    # 평가 항목 (예: '커피의 산미', '고기의 육즙')
    score: int    # 1-5점
    text: str     # 상세 이유/특징 (짧은 문장)

class TasteProfile(BaseModel):
    category_name: str # 추론된 매장 카테고리 (예: '디저트 카페', '한우 전문점')
    metrics: List[Metric] # 해당 카테고리에 맞는 핵심 지표 4개

class ReviewSummary(BaseModel):
    one_line_copy: str
    tags: List[str]
    taste_profile: TasteProfile
    pro_tips: List[str]
    negative_points: List[str]

class AIAnalysisResult(BaseModel):
    restaurant_name: str
    recommendation_score: int
    must_eat_menus: List[str]
    categories: List[str]
    review_summary: ReviewSummary
    transport_info: str

class AIAnalyzer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API Key is required")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-3-flash-preview")

    async def analyze_restaurant(self, restaurant_data: Dict) -> AIAnalysisResult:
        system_prompt = """
        너는 '냉철한 미식가'이자 '데이터 분석 전문가'이다. 
        제공된 정보를 분석하여 반드시 다음 JSON 구조로 응답하라.
        
        # Strategy: Dynamic Evaluation System
        리뷰 내용을 바탕으로 매장의 성격(카테고리)을 먼저 파악하라. 
        그 카테고리에 가장 중요한 핵심 평가 지표 4가지를 동적으로 생성하여 점수를 매겨야 한다.
        예: 국밥집이면 [국물의 깊이, 고기의 양, 김치 맛, 회전율], 카페라면 [커피 풍미, 디저트 퀄리티, 공간의 무드, 작업 편의성] 등.

        # Output Structure
        {
          "restaurant_name": "매장명",
          "recommendation_score": 0-100,
          "must_eat_menus": ["메뉴1", "메뉴2"],
          "categories": ["카테고리1", "카테고리2"],
          "review_summary": {
            "one_line_copy": "매장을 한 줄로 정의하는 캐치프레이즈",
            "tags": ["#태그1", "#태그2"],
            "taste_profile": {
              "category_name": "추론된 매장 카테고리",
              "metrics": [
                { "label": "항목1", "score": 1-5, "text": "선정 이유" },
                { "label": "항목2", "score": 1-5, "text": "선정 이유" },
                { "label": "항목3", "score": 1-5, "text": "선정 이유" },
                { "label": "항목4", "score": 1-5, "text": "선정 이유" }
              ]
            },
            "pro_tips": ["꿀팁1", "꿀팁2"],
            "negative_points": ["아쉬운점1", "아쉬운점2"]
          },
          "transport_info": "교통 정보 요약"
        }

        # Analysis Guide
        - 'must_eat_menus'는 리뷰에서 가장 언급이 많고 평이 좋은 메뉴들이다. **그 중에서도 압도적으로 추천받는 시그니처 메뉴 1~2개에는 메뉴명 뒤에 '⭐' 기호를 붙여라.** (예: "불뚝감⭐")
        - 'metrics'는 반드시 4개를 생성하라.
        - 'score'는 1점에서 5점 사이의 정수여야 함.
        - 'negative_points'는 리뷰에서 언급된 실제 단점을 가감 없이 추출할 것.
        - 모든 텍스트는 한국어로 작성하라.
        """

        user_content = f"""
        매장 기본 정보:
        명칭: {restaurant_data.get('name')}
        주소: {restaurant_data.get('address')}
        
        리뷰 데이터:
        {chr(10).join(restaurant_data.get('reviews', []))[:8000]}
        """

        response = self.model.generate_content(
            f"{system_prompt}\n\n{user_content}",
            generation_config={"response_mime_type": "application/json"}
        )

        content = response.text
        result_json = json.loads(content)
        
        # Robustly handle if the LLM returns a list instead of a single object
        if isinstance(result_json, list) and len(result_json) > 0:
            result_json = result_json[0]
        
        if not isinstance(result_json, dict):
             raise ValueError(f"AI returned invalid format: {type(result_json)}")
        
        return AIAnalysisResult(**result_json)
