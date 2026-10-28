CREATE TABLE scheduler_workers (
    worker_id text PRIMARY KEY,
    run_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('STARTING','RUNNING','OK','ERROR','STOPPED')),
    stale_after_seconds integer NOT NULL CHECK (stale_after_seconds > 0),
    last_started_at timestamptz,
    last_finished_at timestamptz,
    last_success_at timestamptz,
    last_error_code text,
    cycles bigint NOT NULL DEFAULT 0,
    failures bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL
);
