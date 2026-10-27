# M3 agent rules

Read root AGENTS and `docs/2026-10-26-implementation.md` before edits. This module owns repair work orders only. Preserve the public contract at `contracts/m3-work-orders.md` and its generated OpenAPI. Update `STATUS.md` with actual evidence.

- Actor identity is a provider result; never trust client roles/user IDs. Default/production must reject demo identities and must not process a development outbox.
- State transitions, version checks, history, idempotency, and outbox writes must commit atomically. Network I/O stays outside DB transactions.
- A job retry keeps its source ID, revision, correlation ID, and complete payload. Only a fully validated M1 receipt completes start/accept. Complete/reject must not release a block.
- Outbox acknowledgement reloads the latest order so concurrent SLA/history updates are preserved. Respect leases, retry limits, and permanent error handling.
- Do not migrate or access M1/M2/D tables. Applied migrations are immutable; add a new ordered revision. PostgreSQL uses the `m3` schema; SQLite is explicit local development/test only.
- `dev_dependencies.py`, `run-dev.sh`, and provider doubles under tests are TEMPORARY-DEPENDENCY entries. Replacement/cleanup requires the integration scope and successful real-provider checks recorded in the task.
- Run `python -m unittest discover -s services/m3/tests -v`, then repository `bash scripts/check.sh`. A skipped PostgreSQL test is not PostgreSQL validation. No manual DB fixes or fake integration/deployment claims.
