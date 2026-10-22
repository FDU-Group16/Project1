CREATE TABLE IF NOT EXISTS settings (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    max_reservation_hours integer NOT NULL DEFAULT 4 CHECK (max_reservation_hours BETWEEN 1 AND 24)
);
INSERT INTO settings(id) VALUES (true) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS reservations (
    id text PRIMARY KEY,
    user_id text NOT NULL,
    room_id text NOT NULL,
    room_name text NOT NULL,
    seat_id text NOT NULL,
    seat_number text NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK (ends_at > starts_at),
    status text NOT NULL CHECK (status IN ('RESERVED','CHECKED_IN','CANCELLED','NO_SHOW')),
    created_at timestamptz NOT NULL,
    checked_in_at timestamptz,
    cancelled_at timestamptz,
    idempotency_key text NOT NULL,
    request_payload jsonb NOT NULL,
    UNIQUE(user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS reservation_seat_range ON reservations(seat_id,starts_at,ends_at);
CREATE INDEX IF NOT EXISTS reservation_user_range ON reservations(user_id,starts_at,ends_at);
CREATE TABLE IF NOT EXISTS room_blocks (
    source_system text NOT NULL CHECK (source_system IN ('M2','M3')),
    source_id text NOT NULL,
    room_id text NOT NULL,
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    status text NOT NULL CHECK (status IN ('ACTIVE','RELEASED')),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz,
    applied_at timestamptz NOT NULL,
    request_payload jsonb NOT NULL,
    PRIMARY KEY(source_system,source_id),
    CHECK (ends_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX IF NOT EXISTS block_room_range ON room_blocks(room_id,starts_at,ends_at);
CREATE TABLE IF NOT EXISTS provenance (
    id text PRIMARY KEY,
    source_system text NOT NULL,
    source_id text NOT NULL,
    room_id text NOT NULL,
    action text NOT NULL,
    created_at timestamptz NOT NULL,
    detail jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS provenance_room ON provenance(room_id,created_at);
CREATE TABLE IF NOT EXISTS breaches (
    id text PRIMARY KEY,
    reservation_id text NOT NULL UNIQUE REFERENCES reservations(id),
    user_id text NOT NULL,
    room_id text NOT NULL,
    seat_id text NOT NULL,
    reason text NOT NULL,
    occurred_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    id text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('notification','audit')),
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING','ACCEPTED','DELIVERED','SIMULATED')),
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    delivered_at timestamptz,
    last_error text
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(state,next_attempt_at);
