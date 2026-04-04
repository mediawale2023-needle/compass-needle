-- add_query_indexes.sql
-- Indexes to support WhatsApp case query engine performance.
-- All statements use IF NOT EXISTS — safe to run multiple times.
--
-- Run once against the production DB:
--   psql $DATABASE_URL -f scripts/add_query_indexes.sql

-- Constituency / assembly filter
CREATE INDEX IF NOT EXISTS idx_cases_assembly
    ON cases (tenant_id, assembly)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Location text filter (ILIKE requires pg_trgm for full benefit, but index still helps range scans)
CREATE INDEX IF NOT EXISTS idx_cases_location
    ON cases (tenant_id, location)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Status filter
CREATE INDEX IF NOT EXISTS idx_cases_status
    ON cases (tenant_id, status)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Time range filter (most selective — used in every query)
CREATE INDEX IF NOT EXISTS idx_cases_created_at
    ON cases (tenant_id, created_at DESC)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Category / issue_type filter
CREATE INDEX IF NOT EXISTS idx_cases_category
    ON cases (tenant_id, category)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Composite: the most common query pattern (tenant + time + status)
CREATE INDEX IF NOT EXISTS idx_cases_query_composite
    ON cases (tenant_id, created_at DESC, status)
    WHERE is_deleted = false OR is_deleted IS NULL;

-- Trigram extension for ILIKE on location (optional but recommended for fuzzy search)
-- Uncomment if pg_trgm is available on your PostgreSQL instance:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE INDEX IF NOT EXISTS idx_cases_location_trgm
--     ON cases USING gin (location gin_trgm_ops);
