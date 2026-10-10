-- Online, idempotent indexes for account/session and streaming-profile workloads.
-- Run as the migration owner using psql (outside a transaction).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_expiry ON sessions(user_id,expires_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_session_profile ON session_profiles(profile_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_device_approver ON device_logins(approver_token);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profile_progress_recent ON profile_progress(profile_id,updated_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profile_history_recent ON profile_history(profile_id,watched_at DESC);
