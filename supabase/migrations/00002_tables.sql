-- 00002_tables.sql
-- All application tables. Replaces DynamoDB single-table design.
-- Embedding columns use vector(1536) matching gemini-embedding-2-preview with MRL truncation.
-- If using a different embedding model, update the dimension accordingly.

-- ============================================================
-- SCOUTS (replaces SCRAPER# records)
-- ============================================================
CREATE TABLE scouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('web', 'pulse', 'social', 'civic')),

    -- Common fields (all scout types)
    criteria TEXT,
    preferred_language TEXT DEFAULT 'en',
    regularity TEXT CHECK (regularity IN ('daily', 'weekly', 'monthly')),
    schedule_cron TEXT,
    schedule_timezone TEXT DEFAULT 'UTC',
    topic TEXT,

    -- Web scout fields
    url TEXT,
    provider TEXT CHECK (provider IN ('firecrawl', 'firecrawl_plain')),

    -- Pulse scout fields
    source_mode TEXT CHECK (source_mode IN ('reliable', 'niche')),
    excluded_domains TEXT[],

    -- Social scout fields
    platform TEXT CHECK (platform IN ('instagram', 'x', 'facebook')),
    profile_handle TEXT,
    monitor_mode TEXT CHECK (monitor_mode IN ('summarize', 'criteria')),
    track_removals BOOLEAN DEFAULT FALSE,

    -- Civic scout fields
    root_domain TEXT,
    tracked_urls TEXT[],
    processed_pdf_urls TEXT[],

    -- Location (GeocodedLocation object)
    location JSONB,

    -- Overflow for rare/optional type-specific config
    config JSONB NOT NULL DEFAULT '{}',

    is_active BOOLEAN DEFAULT TRUE,
    consecutive_failures INT DEFAULT 0,
    baseline_established_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, name),
    CONSTRAINT chk_active_has_schedule
        CHECK (NOT is_active OR schedule_cron IS NOT NULL)
);

-- ============================================================
-- SCOUT RUNS (replaces TIME# records)
-- ============================================================
CREATE TABLE scout_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error', 'skipped')),
    scraper_status BOOLEAN DEFAULT FALSE,
    criteria_status BOOLEAN DEFAULT FALSE,
    notification_sent BOOLEAN DEFAULT FALSE,
    articles_count INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days')
);

-- ============================================================
-- EXECUTION RECORDS (replaces EXEC# records)
-- Card display summaries + deduplication via embedding similarity
-- ============================================================
CREATE TABLE execution_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    scout_type TEXT,
    summary_text TEXT NOT NULL,
    embedding vector(1536),
    content_hash TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days')
);

-- ============================================================
-- POST SNAPSHOTS (replaces POSTS# records -- social scouts)
-- Stores the baseline post list for ID-based diffing
-- ============================================================
CREATE TABLE post_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    platform TEXT,
    handle TEXT,
    post_count INT,
    posts JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scout_id)
);

-- ============================================================
-- SEEN RECORDS (replaces SEEN# records -- pulse dedup)
-- ============================================================
CREATE TABLE seen_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    signature TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days'),
    UNIQUE(scout_id, signature)
);

-- ============================================================
-- PROMISES (civic scout -- extracted council promises)
-- ============================================================
CREATE TABLE promises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    promise_text TEXT NOT NULL,
    context TEXT,
    source_url TEXT,
    source_title TEXT,
    meeting_date DATE,
    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'in_progress', 'fulfilled', 'broken', 'notified')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INFORMATION UNITS (replaces information-units table)
-- Atomic facts extracted from scout results
-- ============================================================
CREATE TABLE information_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    scout_id UUID REFERENCES scouts(id) ON DELETE CASCADE,
    scout_type TEXT,
    article_id UUID,
    statement TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('fact', 'event', 'entity_update')),
    entities TEXT[],
    embedding vector(1536),
    source_url TEXT,
    source_domain TEXT,
    source_title TEXT,
    event_date DATE,
    country TEXT,
    state TEXT,
    city TEXT,
    topic TEXT,
    dataset_id TEXT,
    used_in_article BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days')
);

-- ============================================================
-- USER PREFERENCES (replaces USER#/PROFILE -- simplified)
-- Tier + entitlements added by 00025_credits.sql
-- ============================================================
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    timezone TEXT DEFAULT 'UTC',
    preferred_language TEXT DEFAULT 'en',
    notification_email TEXT,
    default_location JSONB,
    excluded_domains TEXT[],
    preferences JSONB DEFAULT '{}',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_tour_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
