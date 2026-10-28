# M1 scheduler monitoring v0.1.0-proposed

2026-10-29 additive proposal; pending M1 and deployment-maintainer review. Wire schema: [OpenAPI](m1-scheduler.openapi.json). Existing reservation, delivery and `/healthz` semantics remain unchanged.

`GET /api/v1/scheduler` requires a D Bearer identity with `operations:read` or `room:manage`. Missing identity is 401, insufficient permission 403, unavailable/unmigrated M1 database 503 (Problem Details). A successfully read unhealthy scheduler still returns 200 so operators can inspect it. No user IDs, reservation IDs, event payloads, tokens or raw exception text are exposed.

Response fields:

- `observedAt`: UTC timestamp; `dependencyMode`: existing M1 dependency mode.
- `status`: `healthy` when a worker is healthy and neither failed pending deliveries nor overdue no-shows exist; `degraded` when a healthy worker exists but either backlog condition exists; `unhealthy` when none is healthy. This is operational status, not evidence of D notification delivery or full business readiness.
- `workers`: at most 100 most recently updated instances, each with `workerId`, `status` (`healthy`, `stale`, `starting`, `error`, `stopped`), nullable `lastStartedAt`, `lastFinishedAt`, `lastSuccessAt`, `lastErrorCode`, and integer `cycles`, `failures`, `staleAfterSeconds`. `healthyWorkers` counts all healthy instances, including those outside the display limit.
- `outbox`: integer counts `pending`, `due`, `failedPending`, `accepted`, `delivered`, `simulated`, `suppressed` and nullable `oldestPendingAt`. Due means PENDING with next attempt <= observed time. FailedPending means PENDING with attempts > 0; this may include a previously failed request awaiting backoff. ACCEPTED/SIMULATED do not establish delivery.
- `overdueNoShows`: RESERVED rows at or beyond start+15m, before the independent scheduler persists NO_SHOW.

Worker health requires a completed successful cycle less than its stale threshold ago and no later cycle error or stop. An initial cycle is `starting`; a running cycle may remain healthy based on its last successful completion until that expires. A fresh start clears the prior instance's success. The same worker ID fences old runs from updating its monitoring record; simultaneous instances must use distinct IDs. Old instance records can be retained as stopped/stale operational history.

Container-local `python -m services.m1.scheduler --healthcheck` checks only its own `M1_SCHEDULER_ID` (default hostname), exits 0 for a healthy instance and 1 otherwise, and never migrates or starts a worker. A delivery failure does not invalidate a completed scheduling cycle: pending/failed counters expose provider problems without restart storms. A cycle exception marks the instance unhealthy; after a bounded number of consecutive exceptions the process exits nonzero so the supervisor can restart it. A hung cycle expires its last successful heartbeat; Docker marks it unhealthy, but restart policy alone does not restart an unhealthy running process. Operators must alert/restart a hung instance or use an external supervisor.

Migration `004_scheduler_workers.sql` is additive in the M1 schema. Rollback to an older application may leave this table in place; never drop reservation/outbox data to roll back monitoring.
