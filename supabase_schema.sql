-- restaurants 테이블 생성 SQL
-- Supabase SQL Editor에서 실행하세요.

-- 1. 확장 기능 활성화 (PostGIS는 선택 사항, 여기서는 기본 기능만 사용)
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. 테이블 생성
CREATE TABLE IF NOT EXISTS public.restaurants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    naver_place_id VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    address VARCHAR NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    ai_score INT CHECK (ai_score >= 0 AND ai_score <= 100),
    transport_info VARCHAR(100), -- 50자에서 100자로 여유 있게 조정
    summary_json JSONB,
    must_eat_menus JSONB,
    search_tags TEXT[],
    original_url VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. 검색 최적화를 위한 GIN 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_restaurants_search_tags ON public.restaurants USING GIN (search_tags);
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON public.restaurants (name);

-- 4. RLS (Row Level Security) 설정 (데이터 조회 권한 부여)
ALTER TABLE public.restaurants ENABLE ROW LEVEL SECURITY;

-- 누구나 조회 가능하도록 정책 추가
CREATE POLICY "Allow public read-only access" 
ON public.restaurants FOR SELECT 
USING (true);

-- API를 통한 입력을 위해 (service_role 사용 시 보통 체크 안 해도 되지만, anon 사용 시 필요할 수 있음)
CREATE POLICY "Allow authenticated insert" 
ON public.restaurants FOR INSERT 
WITH CHECK (true);
