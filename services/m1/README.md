# M1 seat reservation service

Scheduler deployment, instance health, backlog inspection and operator actions: [deployment guide](deployment/README.md). The independent worker is now defined in staging Compose; local Compose enables it with profile `m1-business`. `GET /api/v1/scheduler` exposes management-only aggregate monitoring ([contract](../../contracts/m1-scheduler.md)); `/healthz` remains process liveness. A scheduler container is marked unhealthy on stale/error heartbeats, and consecutive cycle exceptions cause nonzero exit for supervised restart. Notification provider failures are reported as backlog rather than treated as successful delivery.

Implemented requirement paths and verification are recorded in [STATUS.md](STATUS.md). Public and internal interfaces are versioned in `contracts/m1-public.md`, `contracts/m1-public.openapi.json` and `contracts/m1-room-blocks.openapi.json` (pending review).

Configure a provisioned PostgreSQL schema through `M1_DATABASE_URL`. Run `uv run uvicorn services.m1.main:app --port 3101`; startup replays ordered migrations under `migrations/`. An unset database URL still allows `/healthz` for scaffold smoke checks, while business APIs return 503. The scheduler is a separate required process: `uv run python -m services.m1.scheduler`, or add `--once` for a bounded pass. It polls every 30 seconds by default, persists all state and supports restarts/multiple workers. Readiness and deployment supervision are integration responsibilities; `/healthz` does not assert dependency or scheduler health.

Environment:

- `D_BASE_URL` defaults to `http://127.0.0.1:3104`; `D_M1_TOKEN` authorizes the real D-02 master-data API.
- `M1_M2_TOKEN` and `M1_M3_TOKEN` are distinct service credentials required by the writeback endpoints. Do not use the same credential for both sources.
- `M1_CHECKIN_SECRET` must contain at least 32 characters and be supplied through secret configuration. Rotating it invalidates current codes.
- `M1_BOOKING_HORIZON_DAYS` defaults to 7. The persisted maximum duration defaults to 4 hours and is managed through the settings API.
- `D_NOTIFICATION_TOKEN` and `D_AUDIT_TOKEN` authorize real delivery adapters; the current task does not implement those D providers.
- Explicit development dependencies and cleanup scope are listed in [temporary_dependencies/README.md](temporary_dependencies/README.md). They never replace D-02 and never imply real authentication or notification delivery.

Run PostgreSQL behavior tests with an explicitly disposable `TEST_M1_DATABASE_URL`: `uv run python -m unittest discover -s services/m1/tests -v`. The suite truncates M1-owned business tables in that test database; never point it at a shared or production database. Without that variable these database tests are skipped, which is not business verification. Provider fixture replacements are confined to tests; the M1 unit under test remains real.

Delivery semantics: PENDING retries using event IDs and capped backoff; obsolete reminders become SUPPRESSED after a locked eligibility check (cancelled, checked in, or deadline passed), while NO_SHOW and audit events remain deliverable; ACCEPTED records a D durable receipt, DELIVERED records a provider delivery acknowledgement, SIMULATED is development-only. `acknowledged_at` and `delivered_at` are separate; neither ACCEPTED nor SIMULATED is reported as actual delivery. No payload contains bearer credentials or room check-in codes. The no-show transition, breach and outbox event are committed together.
