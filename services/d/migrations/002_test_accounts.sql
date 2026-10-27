-- Isolated, explicitly enabled course test accounts; not the campus D-01 domain.
CREATE TABLE test_accounts (
    id text PRIMARY KEY,
    username text NOT NULL UNIQUE,
    display_name text NOT NULL,
    department_id text,
    permissions text[] NOT NULL,
    password_salt bytea NOT NULL CHECK (octet_length(password_salt) = 32),
    password_hash bytea NOT NULL CHECK (octet_length(password_hash) = 32),
    password_iterations integer NOT NULL CHECK (password_iterations = 600000),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    disabled boolean NOT NULL DEFAULT false,
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '30 days')
);

CREATE TABLE test_sessions (
    token_digest bytea PRIMARY KEY CHECK (octet_length(token_digest) = 32),
    account_id text NOT NULL REFERENCES test_accounts(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '2 hours')
);
CREATE INDEX test_sessions_account_idx ON test_sessions(account_id);
CREATE INDEX test_sessions_expiry_idx ON test_sessions(expires_at);

CREATE TABLE test_login_limits (
    bucket text PRIMARY KEY,
    window_start timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts > 0)
);
