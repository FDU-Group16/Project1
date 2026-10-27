# Project rules for coding agents

## Document scope

This repository-root `AGENTS.md` contains global rules for all coding agents and applies to every module. Read it together with any module-local `AGENTS.md` for the area being changed.

Keep module-specific agent instructions and development documentation in the corresponding module directory: `services/m1/`, `services/m2/`, `services/m3/`, `services/d/`, or `apps/web/`. Use a module-local `AGENTS.md` for agent instructions and keep design, implementation, and test notes alongside that module's code. Module-local instructions may add detail but must not override these global rules. Keep shared requirements and decisions in `docs/` and cross-service contracts in `contracts/`, as described below.

## Current phase

The repository contains the first scoped M1 and D-02 business implementation. M2/M3 and D-01/D-03/D-04 remain provider dependencies; consult module status records for implemented, tested and deployed boundaries. A contract proposal alone is not an available endpoint. Do not implement additional M1, M2, M3, or D features without a scoped task and acceptance criteria.

## Sources of truth

1. `任务书.pdf` is the course brief and a versioned reference; do not alter or delete it.
2. `docs/requirements.md` tracks requirements and unresolved decisions.
3. `contracts/` contains proposed, versioned cross-service interface contracts. Contract status is stated in `contracts/README.md`.
4. `docs/decisions/` records architecture choices. `proposed` does not mean the team has approved a decision.

If these sources conflict, surface the conflict in the change description and request a team decision before implementing the disputed behavior.

## Boundaries

- `services/m1` (`services.m1.main:app`): individual seat search, reservation, check-in, breach history.
- `services/m2` (`services.m2.main:app`): whole-room requests and approvals.
- `services/m3` (`services.m3.main:app`): repair work orders.
- `services/d` (`services.d.main:app`): shared identity/RBAC, room and seat master data, notifications, audit. Confirmed subdomain ownership: M1 owns D-02 master data; M2 owns D-01 identity/RBAC; M3 owns D-03 notifications and D-04 audit. The user explicitly confirmed this task allocation on 2026-10-27; see `docs/decisions/0002-d-ownership.md`. This confirmation does not approve interface/schema proposals, detailed shared-frontend assignments, integration coordination arrangements, or release duties.
- `apps/web`: Vue Web client and browser-facing flows.
- `contracts/`: public cross-service API contracts; no service imports another service's internals or accesses another service's schema.

Backend dependencies are managed by the root `pyproject.toml` and `uv.lock`; the Web client has its own npm lockfile in `apps/web`. Shared code may cover technical infrastructure, but must not hide cross-service business calls. Each FastAPI service has a separate ASGI entry point.

The M2/M3 to M1 seat-status writeback must use a network API. M1 must retain provenance for changes caused by M1, M2, and M3. Use stable room IDs from D, UTC timestamps in APIs, and half-open time intervals `[start, end)`.

## Web collaboration

Keep `apps/web` as one Vue application. Organize business pages, components, API adapters, and route definitions under `src/modules/<module>/`, with each business module group responsible for its own directory. Shared UI, layout, authentication state, and HTTP infrastructure belong under `src/shared/`; they must not depend on business-module internals.

Read `apps/web/AGENTS.md` before changing the Web client. It defines frontend ownership, shared-file review, style and state boundaries, and integration checks. Changes to the application shell, root router, global styles, shared components, dependency manifests/lockfiles, or Web build/deployment configuration require coordination and review by the relevant maintainers and affected module groups. No individual frontend maintainer is assigned by these rules; identify integration and review responsibility in the task or PR.

## Cross-module collaboration and develop synchronization

Attempt to synchronize `develop` only when the current task actually needs capabilities or coordinated changes from another business module or a shared module such as D. Independent work within one module does not require a fetch at task start or on every message. Frontend and backend work belonging to the same business module is not by itself cross-module collaboration. Identify the concrete dependency and allowed directories in the task notes first.

1. When collaboration is needed, inspect the current branch, HEAD, working tree, configured remotes, and any unfinished merge/rebase or unresolved conflicts. Preserve all existing changes. Use the confirmed team remote, normally the existing `origin`; do not invent a remote or silently substitute another base branch.
2. Fetch the remote `develop` branch and verify the fetched remote-tracking SHA. For `origin`, an explicit command is `git fetch origin refs/heads/develop:refs/remotes/origin/develop`. If the remote/branch is missing or the fetch fails, record that the latest remote state is unconfirmed. Describe what the current checkout provides without claiming the remote module also lacks the capability. Independent work within the authorized module may continue; integration depending on unavailable code must remain explicitly unverified.
3. If the fetched `<remote>/develop` commit is already an ancestor of HEAD, no branch update is needed. Otherwise, if HEAD is an ancestor of that commit, the index and tracked working files are clean, and no untracked file would be overwritten, this rule authorizes `git merge --ff-only <remote>/develop` on the assigned working branch. Unrelated untracked reference files such as `任务书.pdf` do not by themselves prevent synchronization and must remain untouched.
4. If histories have diverged, the file-safety conditions above are not met, or a Git operation is unfinished, preserve the checkout and report the required human integration. The fetched module status and contracts may be inspected read-only, for example with `git show <remote>/develop:<path>`, to distinguish code present on develop from code integrated into the working branch. Do not automatically stash, commit, discard, reset, rebase, cherry-pick, create a merge commit, or resolve conflicts to force synchronization.
5. After a branch update, re-read the applicable `AGENTS.md`, module status records and dependency contracts from that checkout. When only inspecting a fetched ref, label its evidence with that ref and SHA. Record why synchronization was needed, the time, remote, working branch, fetched `develop` SHA, resulting HEAD, and outcome in the task notes or the current module's handoff record. Validate the actual checked-out code; reading a remote ref is not evidence of successful local integration.
6. If the needed capability is not implemented in another business module, explain the missing interface or behavior, its effect on the current task, and the next integration step. Record the gap in the current module's task/status; do not implement or edit that other module's code, tests, rules or status files to fill it. Consumer-owned temporary substitutes may support parallel development under the rules below. A planned contract, static page or substitute is not an available provider capability. Report partial completion and the unverified dependency honestly.

The authored changes for a module task stay within that business module's authorized frontend/backend directories. D and other clearly identified shared infrastructure are exceptions when needed by the task: define the requirement, limited scope and acceptance criteria before implementing shared changes, update their contracts/status when affected, and obtain the normal affected-owner review before merge. This exception does not change the confirmed D subdomain ownership or authorize unrelated shared features. Impacts on other business modules are described in the current task/PR for their owners to handle.

The permitted fast-forward synchronizes already-integrated team code into the checkout; subsequent authored edits still follow the module boundaries above. This limited authorization does not permit moving `main`, a release branch or detached HEAD to `develop`, merging work into `develop`, pushing, force-pushing or releasing. Other branch merges and conflict handling remain subject to the human-review rules below.

## Parallel development and temporary dependencies

Implement the current module's scoped business behavior while keeping its external dependency surface as small as the acceptance criteria allow. When a provider is unavailable or its integration is unverified, the consuming module may implement a minimal, replaceable development/test substitute. Create substitutes only for an explicit task with acceptance criteria, not merely to fill scaffold directories. This permission does not bypass contract review or the conditional develop inspection above, or authorize implementing another group's business module.

1. Keep substitutes in isolated files or directories within the consuming module's authorized frontend/backend scope, behind an explicit dependency interface or adapter. Do not copy the provider's full business logic, access its schema, or modify its code, tests, rules or status records. Actual shared infrastructure changes still follow the scoped shared-change and review rules above.
2. Use the applicable contract and record its path, version and approval status. If the contract is still proposed or missing, record the temporary assumptions and unresolved differences; shared interface proposals belong in `contracts/`. Such assumptions support local development only and do not settle disputed business rules or commit the provider to an interface.
3. Implement only the responses, synthetic data and behavior needed to exercise the consumer's acceptance criteria, including relevant failure cases such as rejection, conflict or timeout. Keep the consumer's business logic and error handling real. Tests may replace external dependencies, but must not replace the behavior being tested.
4. Enable substitutes only through explicit development/test configuration. Normal runtime and deployment configuration must use real dependencies; a real-service failure must not silently fall back to simulated success. Record the active dependency mode in development/demo output so simulated behavior is identifiable.
5. Mark temporary files, or their dedicated directory README, with `TEMPORARY-DEPENDENCY` and a stable dependency ID. Maintain a cleanup inventory in the module's task notes, linked from its `STATUS.md`: consumer and provider, missing capability, contract version/status, assumptions, exact temporary paths and configuration, activation method, owning/integrating groups, replacement trigger, required integration checks, and the code that must remain. A marker alone is not a deletion instruction.
6. Report implementation and verification separately: the consumer behavior implemented, scenarios verified with substitutes, and real-provider integration still unverified. Substitute tests do not establish provider availability, real authentication, cross-service state changes or deployment readiness. M2/M3 to M1 writeback still requires a real network API and actual state/provenance verification for integrated acceptance.
7. When the real provider is available, an integration task must identify the responsible groups and authorized replacement paths, reconcile contract differences, switch to the real adapter, and run the relevant integration checks. After those pass, remove the inventoried temporary implementation, temporary fixtures and activation/startup configuration, rerun affected checks including `bash scripts/check.sh`, and update the consumer's task/status with evidence and remaining gaps. Preserve its business logic, real API client, error handling and lasting behavioral tests.
8. Other groups may perform the cleanup only within that integration task's authorized scope. A disposable marker does not authorize automatic conflict resolution, discarding existing working-tree changes, deleting whole modules, or overwriting a provider implementation. Existing human-review and merge rules continue to apply.

Use the temporary-dependency section of `docs/ai-task-template.md` to define this scope before implementation and record the replacement outcome at handoff.

## Module status and agent handoff

Read `docs/module-status.md`, the affected module's `STATUS.md`, and the status and approved contracts of any provider the task will call. When collaboration is needed, apply the conditional develop procedure above and refresh those records before relying on the provider. These files are repository handoff records, not shared chat memory. If a status entry is stale or contradicts code or a contract, verify the evidence and report the discrepancy before relying on the capability. A proposed contract must never be treated as an available endpoint.

Maintain backend handoff records at `services/m1/STATUS.md`, `services/m2/STATUS.md`, `services/m3/STATUS.md`, and `services/d/STATUS.md`. Each frontend module maintains `apps/web/src/modules/<module>/STATUS.md`; `apps/web/STATUS.md` covers only the common shell and shared infrastructure. Keep `docs/module-status.md` as a stable link index so normal module work does not require editing one shared progress table.

Before reporting a task complete, update the affected status records in the same change as the code. Record the update date, associated requirement IDs, completed behavior and source paths, available endpoints or frontend entry points, contract versions, verification commands/results, dependencies, unresolved issues, and the next integration step. Separate what is implemented, what has been tested, and what is deployed; include PR/commit, environment, release and migration evidence when available, and explicitly mark unknown or unverified fields. Keep a short handoff history with links to task notes rather than duplicating detailed logs. Do not invent a review, deployment, passing test, or implementation claim.

API request/response fields, errors, authentication, examples, and compatibility rules remain in `contracts/`; status records link to these definitions and state whether they are proposed, implemented, or verified. Update affected requirement traceability and shared contract compatibility notes when behavior or interfaces change. Record frontend/backend integration gaps even when one side is complete; describe other business modules' required follow-up in the current task/status for their owners instead of editing their records. Keep credentials and personal data out of all handoff records.

Agents in the same checkout can read these files immediately. Other branches, worktrees, or teammates receive them through the normal code-and-documentation commit/PR workflow; local edits are not automatically synchronized or deployed. Each task must preserve the distinction between its working tree and an integrated or released version.

## Change workflow

1. For a feature task, use `docs/ai-task-template.md` to identify requirement IDs, scope, acceptance criteria, affected contract and schema, and verification before coding.
2. Change shared contracts first; review cross-module, D, and schema changes with the affected module owners. Update the contract version or compatibility note when needed.
3. Keep migrations versioned, replayable from an empty database, and separate from idempotent seed data. Never rely on manual database edits.
4. Run `bash scripts/check.sh` before requesting review. It checks the contract file, backend HTTP smoke behavior, Vue types, and Web build. Future tests should exercise behavior and fail when that behavior is deliberately broken; do not mock the unit under test.
5. Commit small, reviewable changes with the reason in the message. A human reviews AI changes and resolves merge conflicts. Do not merge branches or release to production on behalf of the team without a specific task.
6. Keep credentials and real student data out of the repository. Use least privilege and update `docs/ethics-log.md` with decisions affecting privacy, fairness, or accessibility as they arise.

## Branch and release convention (proposed)

The proposed convention uses `m1`, `m2`, and `m3` for module work; integration would use reviewed pull requests into `develop`, with releases from reviewed `main` and a tag. A later delivery stage plans automatic testing deployments after integration; production would require human approval and a rollback path. Record the deployed tag and migration version when that pipeline exists. The collaboration-triggered develop synchronization rule above applies now; the remaining branch naming, review and release convention must be ratified by the team before being used as a gate.
