-- =============================================================================
-- Munim — Initial Database Migration
-- Run once against Neon PostgreSQL to create all tables.
-- =============================================================================
-- How to run:
--   psql $DATABASE_URL -f backend/db/migrations/001_initial.sql
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- USERS
-- CA firms and direct SMB owners
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                   TEXT UNIQUE NOT NULL,
    name                    TEXT NOT NULL,
    phone                   TEXT,
    user_type               TEXT NOT NULL CHECK (user_type IN ('ca_firm', 'smb_owner')),
    language_preference     TEXT NOT NULL DEFAULT 'hi' CHECK (language_preference IN ('hi', 'en', 'hinglish')),
    whatsapp_opted_in       BOOLEAN NOT NULL DEFAULT FALSE,
    google_id               TEXT UNIQUE,                    -- Google OAuth sub
    avatar_url              TEXT,
    subscription_status     TEXT NOT NULL DEFAULT 'trial' CHECK (
                                subscription_status IN ('trial', 'active', 'cancelled', 'expired')
                            ),
    trial_ends_at           TIMESTAMPTZ,
    razorpay_subscription_id TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

-- =============================================================================
-- CA CLIENTS
-- SMB clients managed by a CA firm
-- =============================================================================
CREATE TABLE IF NOT EXISTS ca_clients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_name         TEXT NOT NULL,
    client_phone        TEXT,
    client_email        TEXT,
    whatsapp_opted_in   BOOLEAN NOT NULL DEFAULT FALSE,
    white_label_name    TEXT,           -- Name shown in reports (CA firm's brand)
    white_label_logo_url TEXT,
    language_preference TEXT NOT NULL DEFAULT 'hi',
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ca_clients_ca_user_id ON ca_clients(ca_user_id);
CREATE INDEX IF NOT EXISTS idx_ca_clients_phone ON ca_clients(client_phone);

-- =============================================================================
-- UPLOADS
-- File upload records (actual files stored in Cloudflare R2)
-- =============================================================================
CREATE TABLE IF NOT EXISTS uploads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ca_client_id        UUID REFERENCES ca_clients(id) ON DELETE SET NULL,
    file_name           TEXT NOT NULL,
    file_path           TEXT NOT NULL,      -- Cloudflare R2 object key
    file_type           TEXT NOT NULL CHECK (file_type IN ('tally_xml', 'excel', 'csv')),
    file_size_bytes     BIGINT,
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (
                            status IN ('pending', 'processing', 'done', 'error')
                        ),
    data_health_score   SMALLINT CHECK (data_health_score BETWEEN 0 AND 100),
    health_report       JSONB,              -- Full HealthReport as JSON
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    delete_after        TIMESTAMPTZ GENERATED ALWAYS AS (
                            created_at + INTERVAL '30 days'
                        ) STORED
);

CREATE INDEX IF NOT EXISTS idx_uploads_user_id ON uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_uploads_ca_client_id ON uploads(ca_client_id);
CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
CREATE INDEX IF NOT EXISTS idx_uploads_delete_after ON uploads(delete_after);

-- =============================================================================
-- ANALYSIS RESULTS
-- Computed metrics and anomalies per upload
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id           UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    metrics             JSONB NOT NULL,     -- BusinessMetrics as JSON
    anomalies           JSONB NOT NULL,     -- AnomalyReport as JSON
    products            JSONB NOT NULL,     -- Product rankings + dead stock
    customers           JSONB NOT NULL,     -- RFM segmentation
    seasonality_context JSONB,             -- SeasonalContext as JSON
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_upload_id ON analysis_results(upload_id);
CREATE INDEX IF NOT EXISTS idx_analysis_user_id ON analysis_results(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_period ON analysis_results(period_start, period_end);

-- =============================================================================
-- REPORTS
-- Generated WhatsApp/PDF reports
-- =============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL REFERENCES analysis_results(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_type         TEXT NOT NULL CHECK (
                            report_type IN ('weekly', 'monthly', 'alert', 'on_demand')
                        ),
    language            TEXT NOT NULL CHECK (language IN ('hi', 'en', 'hinglish')),
    content_hindi       TEXT,
    content_english     TEXT,
    whatsapp_sent       BOOLEAN NOT NULL DEFAULT FALSE,
    whatsapp_sent_at    TIMESTAMPTZ,
    whatsapp_message_id TEXT,              -- Meta's message ID for delivery tracking
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_analysis_id ON reports(analysis_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);

-- =============================================================================
-- WHATSAPP CONVERSATIONS
-- All inbound + outbound WhatsApp messages
-- =============================================================================
CREATE TABLE IF NOT EXISTS wa_conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    phone_number        TEXT NOT NULL,      -- Always store phone — user may not be registered
    direction           TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_text        TEXT NOT NULL,
    intent_detected     TEXT,              -- e.g. 'revenue_query'
    wa_message_id       TEXT,             -- Meta's message ID
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NOTE: message_text is NOT indexed — financial content must not be searchable in logs
CREATE INDEX IF NOT EXISTS idx_wa_conversations_user_id ON wa_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_wa_conversations_phone ON wa_conversations(phone_number);
CREATE INDEX IF NOT EXISTS idx_wa_conversations_created_at ON wa_conversations(created_at DESC);

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Critical: users can ONLY see their own data
-- =============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE ca_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE wa_conversations ENABLE ROW LEVEL SECURITY;

-- Users: can only see/edit their own row
CREATE POLICY users_self_access ON users
    USING (id = current_setting('app.current_user_id', TRUE)::UUID);

-- CA clients: CA firm sees only their clients
CREATE POLICY ca_clients_owner_access ON ca_clients
    USING (ca_user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- Uploads: user sees only their uploads
CREATE POLICY uploads_owner_access ON uploads
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- Analysis results: user sees only their results
CREATE POLICY analysis_owner_access ON analysis_results
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- Reports: user sees only their reports
CREATE POLICY reports_owner_access ON reports
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- WhatsApp conversations: user sees only their conversations
CREATE POLICY wa_conversations_owner_access ON wa_conversations
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- =============================================================================
-- UPDATED_AT trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER ca_clients_updated_at
    BEFORE UPDATE ON ca_clients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
