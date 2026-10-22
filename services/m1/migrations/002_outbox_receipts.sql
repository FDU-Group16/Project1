-- Receipt time is not delivery evidence; accepted/simulated states keep delivery null.
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS acknowledged_at timestamptz;
UPDATE outbox SET acknowledged_at=delivered_at WHERE delivered_at IS NOT NULL;
UPDATE outbox SET delivered_at=NULL WHERE state<>'DELIVERED';
