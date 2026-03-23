-- Migration 003: Beta Waitlist
-- Phones on this list are allowed to use the WhatsApp bot.
-- approved=TRUE means they can use the bot immediately.
-- welcome_sent=TRUE means the onboarding WhatsApp message was delivered.

CREATE TABLE IF NOT EXISTS beta_waitlist (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone         TEXT        NOT NULL UNIQUE,
    name          TEXT,
    approved      BOOLEAN     NOT NULL DEFAULT TRUE,
    welcome_sent  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS beta_waitlist_phone_idx ON beta_waitlist (phone);
