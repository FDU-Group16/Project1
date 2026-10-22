-- A pending reminder is not useful after cancellation/check-in or its time window.
ALTER TABLE outbox DROP CONSTRAINT IF EXISTS outbox_state_check;
ALTER TABLE outbox ADD CONSTRAINT outbox_state_check
    CHECK (state IN ('PENDING','ACCEPTED','DELIVERED','SIMULATED','SUPPRESSED'));
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS suppressed_at timestamptz;
