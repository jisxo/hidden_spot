

## 1. 개요 (Overview)
* **목표:** 사용자가 네이버 지도 URL을 입력하면, 해당 매장의 리뷰를 AI가 분석하여 핵심 정보(추천 메뉴, 검색용 카테고리, 요약 정보, 추천 점수)를 제공하고, 이를 지도상에서 실시간으로 관리하는 서비스.
* **핵심 가치:** 실제 방문자 리뷰 기반의 정제된 정보 제공, AI 기반의 동적 카테고리 분석, 프리미엄 다크 테마 UI, PC/모바일 최적화된 반응형 UX.

## 2. 주요 기능 (Core Features)

### A. AI 기반 심층 분석 (AI Analysis)
1.  **Dynamic Taste Profile:** 
    *   AI가 매장의 성격(예: '디저트 카페', '한우 전문점')을 스스로 추론.
    *   카테고리에 최적화된 4가지 핵심 평가 지표(Metrics)를 동적으로 생성하여 1~5점 평점 및 상세 이유 제공.
2.  **Signature Menu Extraction:** 
    *   리뷰에서 압도적으로 추천받는 시그니처 메뉴를 자동 판별하여 '⭐' 기호 부여.
3.  **Insight Summary:**
    *   **One-line Copy:** 매장을 정의하는 감각적인 캐치프레이즈 생성.
    *   **Secret Note (Pro Tips):** 실제 방문자들만 알 수 있는 이용 꿀팁 제공.
    *   **Check Point:** 리뷰에서 언급된 실제 단점이나 주의사항을 솔직하게 요약.

### B. 스마트 검색 및 필터 (Smart Search & Exploration)
1.  **동의어 확장 검색:** 
    *   백엔드에서 "회" 검색 시 "사시미", "스시" 등 관련 키워드를 포함하는 매장을 자동 탐색.
    *   "탕" → "국물", "찌개", "전골" 등 유의어 필터링 지원.
2.  **통합 검색 태그:** 매장명, 주소, 메뉴명, AI 카테고리 태그를 통합한 `search_tags` 기반의 고속 검색.
3.  **현 지도 검색:** 지도를 움직일 때마다 현재 영역 내의 맛집을 실시간으로 다시 로드하고 거리순/점수순 정렬 제공.

### C. 인터랙티브 지도 (Interactive Map)
1.  **Map-List Sync:** 리스트에서 매장 클릭 시 지도가 부드럽게 이동(Pan/Zoom)하며 핀 활성화.
2.  **Stable List:** 지도 이동 시에도 사용자가 선택한 리스트 순서가 급격하게 바뀌지 않도록 설계.
3.  **네이버 지도 연동:** 상세 카드 내 "네이버 지도에서 보기" 버튼을 통해 원본 데이터 확인 및 길 찾기 연결.

## 3. 기술 스택 (Tech Stack)
* **Frontend:** Next.js, TailwindCSS (v4), Lucide Icons, Naver Maps API v3, Radix UI.
* **Backend:** FastAPI (Python), Playwright (Headless Browser Crawler).
    *   **Crawler Strategy:** Iframe 컨텐츠 접근 및 다단계 좌표 추출 (API -> JS State -> Regex Fallback).
* **AI:** Google Gemini 3 Preview (`gemini-3-flash-preview`).
* **Database:** PostgreSQL (Supabase).
    *   **Schema:** `JSONB`를 활용하여 유연한 AI 분석 결과 저장.
    *   **Search:** GIN 인덱스를 통한 태그 기반 고속 검색.

## 4. 데이터베이스 스키마 (Database Schema)

### Table: `restaurants`
| 컬럼명 | 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 고유 ID (PK) |
| `naver_place_id` | `VARCHAR` | 네이버 고유 ID (중복 방지) |
| `name` | `VARCHAR` | 매장명 |
| `address` | `VARCHAR` | 도로명 주소 |
| `latitude/longitude` | `FLOAT` | 위도/경도 |
| `ai_score` | `INT` | AI 추출 추천 점수 (0-100) |
| `transport_info` | `VARCHAR` | AI 추출 교통/접근성 정보 |
| `summary_json` | `JSONB` | catchphrase, tags, taste_profile(metrics), pro_tips, negative_points 포함 |
| `must_eat_menus` | `JSONB` | 추천 메뉴 리스트 (시그니처 '⭐' 포함) |
| `search_tags` | `TEXT[]` | 검색용 통합 태그 (메뉴, 카테고리, 이름 등) |
| `original_url` | `VARCHAR` | 원본 네이버 지도 URL |

## 5. UI/UX 디자인 시스템
* **Theme:** Luxury Dark / Glassmorphism 스타일. Slate-900 배경과 Orange/Emerald 포인트 컬러 활용.
* **Component-wise Details:**
    *   **Restaurant Card:** 모바일 바텀 시트 형태, 드래그 핸들 비주얼, 아코디언 스타일의 정보 상세 제공.
    *   **Dynamic Taste Chart:** AI 분석 지표를 시각화하는 부드러운 애니메이션 바.
    *   **Feedback:** 주소 복사 시 완료 아이콘 변경 애니메이션, 데이터 분석 중 스켈레톤 UI 적용.

