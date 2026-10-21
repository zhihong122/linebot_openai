-- Run once using Render PostgreSQL's PSQL connection or another SQL client.
-- Uses the existing app_users UUID key. Never maps family/caregiver to patients.
BEGIN;
CREATE TABLE IF NOT EXISTS google_health_accounts (
  user_id UUID PRIMARY KEY REFERENCES app_users(id),
  health_user_id TEXT NOT NULL UNIQUE,
  refresh_token_cipher TEXT NOT NULL,
  access_token_cipher TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  scope TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS google_health_oauth_tickets (
  ticket_hash TEXT PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES app_users(id),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS google_health_oauth_states (
  state_hash TEXT PRIMARY KEY,
  browser_hash TEXT NOT NULL,
  user_id UUID NOT NULL REFERENCES app_users(id),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS google_health_step_snapshots (
  user_id UUID PRIMARY KEY REFERENCES app_users(id),
  health_user_id TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMIT;
