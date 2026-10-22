# Project rules for coding agents

## Document scope

This repository-root `AGENTS.md` contains global rules for all coding agents and applies to every module. Read it together with any module-local `AGENTS.md` for the area being changed.

Keep module-specific agent instructions and development documentation in the corresponding module directory: `services/m1/`, `services/m2/`, `services/m3/`, `services/d/`, or `apps/web/`. Use a module-local `AGENTS.md` for agent instructions and keep design, implementation, and test notes alongside that module's code. Module-local instructions may add detail but must not override these global rules. Keep shared requirements and decisions in `docs/` and cross-service contracts in `contracts/`, as described below.

## Current phase

This repository is at the architecture scaffold phase. Only health endpoints and a static Web shell are implemented. Do not infer that business endpoints in `contracts/` already exist. Do not implement M1, M2, M3, or D business features without a scoped task and acceptance criteria.

## Sources of truth

1. `任务书.pdf` is the course brief. It is currently a local, untracked reference; do not alter or delete it.
2. `docs/requirements.md` tracks requirements and unresolved decisions.
3. `contracts/` contains proposed, versioned cross-service interface contracts. Contract status is stated in `contracts/README.md`.
4. `docs/decisions/` records architecture choices. `proposed` does not mean the team has approved a decision.

If these sources conflict, surface the conflict in the change description and request a team decision before implementing the disputed behavior.

## Boundaries

- `services/m1` (`services.m1.main:app`): individual seat search, reservation, check-in, breach history.
- `services/m2` (`services.m2.main:app`): whole-room requests and approvals.
- `services/m3` (`services.m3.main:app`): repair work orders.
- `services/d` (`services.d.main:app`): shared identity/RBAC, room and seat master data, notifications, audit. Ownership of this work is still a proposed team decision.
- `apps/web`: Vue Web client shell and, later, browser-facing flows.
- `contracts/`: public cross-service API contracts; no service imports another service's internals or accesses another service's schema.

Backend dependencies are managed by the root `pyproject.toml` and `uv.lock`; the Web client has its own npm lockfile in `apps/web`. Shared code may cover technical infrastructure, but must not hide cross-service business calls. Each FastAPI service has a separate ASGI entry point.

The M2/M3 to M1 seat-status writeback must use a network API. M1 must retain provenance for changes caused by M1, M2, and M3. Use stable room IDs from D, UTC timestamps in APIs, and half-open time intervals `[start, end)`.

## Web collaboration

Keep `apps/web` as one Vue application. Organize business pages, components, API adapters, and route definitions under `src/modules/<module>/`, with each business module group responsible for its own directory. Shared UI, layout, authentication state, and HTTP infrastructure belong under `src/shared/`; they must not depend on business-module internals.

Read `apps/web/AGENTS.md` before changing the Web client. It defines frontend ownership, shared-file review, style and state boundaries, and integration checks. Changes to the application shell, root router, global styles, shared components, dependency manifests/lockfiles, or Web build/deployment configuration require coordination and review by the relevant maintainers and affected module groups. No individual frontend maintainer is assigned by these rules; identify integration and review responsibility in the task or PR.

## Change workflow

1. For a feature task, use `docs/ai-task-template.md` to identify requirement IDs, scope, acceptance criteria, affected contract and schema, and verification before coding.
2. Change shared contracts first; review cross-module, D, and schema changes with the affected module owners. Update the contract version or compatibility note when needed.
3. Keep migrations versioned, replayable from an empty database, and separate from idempotent seed data. Never rely on manual database edits.
4. Run `bash scripts/check.sh` before requesting review. It checks the contract file, backend HTTP smoke behavior, Vue types, and Web build. Future tests should exercise behavior and fail when that behavior is deliberately broken; do not mock the unit under test.
5. Commit small, reviewable changes with the reason in the message. A human reviews AI changes and resolves merge conflicts. Do not merge branches or release to production on behalf of the team without a specific task.
6. Keep credentials and real student data out of the repository. Use least privilege and update `docs/ethics-log.md` with decisions affecting privacy, fairness, or accessibility as they arise.

## Branch and release convention (proposed)

The proposed convention uses `m1`, `m2`, and `m3` for module work; integration would use reviewed pull requests into `develop`, with releases from reviewed `main` and a tag. A later delivery stage plans automatic testing deployments after integration; production would require human approval and a rollback path. Record the deployed tag and migration version when that pipeline exists. The team must ratify this convention before using it as a gate.
