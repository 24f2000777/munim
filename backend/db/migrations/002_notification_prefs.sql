-- Migration 002: Add notification preference columns to users table
-- Run this on Neon PostgreSQL before deploying the Phase 3 backend changes.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS notify_on_anomaly BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS notify_weekly     BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS notify_monthly    BOOLEAN NOT NULL DEFAULT FALSE;

-- Also update file_type CHECK constraint to support image uploads (Phase 4)
ALTER TABLE uploads DROP CONSTRAINT IF EXISTS uploads_file_type_check;
ALTER TABLE uploads ADD CONSTRAINT uploads_file_type_check
  CHECK (file_type IN ('tally_xml', 'excel', 'csv', 'image'));
