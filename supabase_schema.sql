-- Hidden Spot Serving Schema (Supabase/Postgres compatible)
-- Apply in Supabase SQL Editor or local Postgres.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.stores (
    store_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    name TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.store_snapshots (
    store_id TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    run_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    bronze_path TEXT,
    silver_path TEXT,
    gold_path TEXT,
    status TEXT NOT NULL,
    progress INT NOT NULL DEFAULT 0,
    error_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_store_snapshots_status ON public.store_snapshots(status);

CREATE TABLE IF NOT EXISTS public.analysis (
    store_id TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    run_id TEXT PRIMARY KEY,
    summary_3lines TEXT,
    vibe TEXT,
    signature_menu_json JSONB,
    tips_json JSONB,
    score DOUBLE PRECISION,
    ad_review_ratio DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.embeddings (
    store_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    vector vector(1536),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (store_id, doc_type)
);

CREATE TABLE IF NOT EXISTS public.reviews (
    store_id TEXT NOT NULL,
    review_key TEXT NOT NULL,
    date DATE,
    rating DOUBLE PRECISION,
    text TEXT NOT NULL,
    is_ad_suspect BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (store_id, review_key)
);

ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='stores' AND policyname='Allow read stores'
  ) THEN
      CREATE POLICY "Allow read stores" ON public.stores FOR SELECT USING (true);
  END IF;
END$$;
