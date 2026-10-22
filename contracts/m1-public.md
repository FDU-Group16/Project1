# M1 public API v0.1.0-proposed

2026-10-22 implementation baseline; pending affected-owner review. This version is additive to the scaffold. D-01/D-03/D-04 remain external dependencies; the consumer development substitutes do not establish their availability.

All endpoints require `Authorization: Bearer <D identity token>`. The default identity adapter calls D `/api/v1/auth/me`; only explicit development/test configuration allows synthetic tokens. Responses include `X-Dependency-Mode: real|development-substitutes`. Errors use Problem Details `{type,title,status,code,detail}`. Missing identity is 401; permission mismatch 403; missing resource 404; conflicts 409; invalid input 422; unavailable dependencies/configuration 503. APIs accept only UTC RFC3339 timestamps ending in `Z` (fractional seconds up to six digits). Intervals are half-open.

| Method/path | Input | Output / permission |
| --- | --- | --- |
| GET `/api/v1/seats` | required startsAt, endsAt; optional hasSocket boolean, roomId | `{items:[{id,roomId,roomName,number,hasSocket,departmentId}]}`; seat:reserve; only authorized, active, available, open and unoccupied seats; empty if the caller already has an overlapping active reservation |
| GET `/api/v1/settings` | — | `{maxReservationHours}`; any authenticated identity |
| PUT `/api/v1/settings` | `{maxReservationHours: integer 1..24}` | same; room:manage |
| POST `/api/v1/reservations` | `{roomId,seatId,startsAt,endsAt}` and mandatory Idempotency-Key (1..128 characters) | reservation; seat:reserve; idempotent by user+key; changed payload 409 |
| GET `/api/v1/reservations` | scope=current\|history (default current), offset>=0, limit=1..100 | `{items:[reservation],total}`; only caller's reservations |
| GET `/api/v1/reservations/{id}` | — | caller-owned reservation |
| POST `/api/v1/reservations/{id}/cancel` | — | caller-owned reservation; only before start; repeated cancellation is idempotent |
| POST `/api/v1/reservations/{id}/check-in` | `{code}` | caller-owned reservation; only `[start,start+15m)` and correct current room daily code |
| POST `/api/v1/reservations/{id}/rebook` | `{startsAt,endsAt}` and mandatory Idempotency-Key | new reservation of the same seat; applies current authorization/availability/conflict limits |
| GET `/api/v1/breaches` | offset>=0, limit=1..100 | `{items:[{id,reservationId,roomId,seatId,reason,occurredAt}],total}`; caller only |
| GET `/api/v1/operations` | required startsAt, endsAt | `{startsAt,endsAt,totals,rooms:[{roomId,roomName,...counts,seats:[{seatId,seatNumber,...counts}]}]}`; operations:read or room:manage |
| GET `/api/v1/rooms/{roomId}/check-in-code` | — | `{roomId,date,code,expiresAt}`; room:manage; daily Asia/Shanghai code |
| GET `/api/v1/rooms/{roomId}/provenance` | offset>=0, limit=1..100 | `{items:[{id,sourceSystem,sourceId,roomId,action,createdAt,detail}],total}`; operations:read or room:manage |

Reservation fields: `id,userId,roomId,roomName,seatId,seatNumber,startsAt,endsAt,status,createdAt,checkedInAt,dependencyMode`. `status` is RESERVED, CHECKED_IN, CANCELLED, NO_SHOW or COMPLETED. Effective COMPLETED is reported when a checked-in reservation ends. Current includes future and running RESERVED/CHECKED_IN; history includes ended and cancelled/no-show records. Names are booking-time snapshots for stable history. An unconfirmed reservation at start+15m no longer blocks seats, even before the scheduler processes it; the next scheduler/consumer pass persists the breach and outbox events exactly once.

Reservations and search require whole-hour boundaries, future starts, a positive duration <= configured maximum (default 4h), and start/end within `M1_BOOKING_HORIZON_DAYS` (default 7). A user may not hold overlapping active reservations across rooms. Opening hours use Asia/Shanghai with D's `openHour`, `closeHour` and `weekdays` (Monday=0); the complete interval must fit one opening day. Room or seat deactivation prevents new reservations; existing reservations remain historical facts.

Counts are `reservations` (all overlapping reservations), `checkedIn` (checked-in or completed), `cancelled`, `noShows`, `reservedHours` (clipped overlap hours of active/completed reservations; excludes cancellations/no-shows). Metrics count facts rather than promise occupancy or attendance; no student identifiers are returned. Time ranges may cover at most 366 days.

Daily codes require a configured `M1_CHECKIN_SECRET` of at least 32 characters. Code exposure requires room:manage and is audited. Server time controls check-in and expiry. The code is shared by a room for the calendar day and is not proof of physical presence; stronger anti-proxy attendance requires a later approved design.

Scheduler: durable reservation state plus unique event keys supports restart/retry. Reminder events are scheduled at start−15m and start+10m; at start+15m a still-unconfirmed reservation becomes NO_SHOW, releases availability, records one breach and queues a cancellation notification. Before each delivery/retry, reminder eligibility is rechecked against current reservation state and time under the same reservation locks. Pending reminders become SUPPRESSED after cancellation, check-in or their delivery window; NO_SHOW and audit events remain eligible. Catch-up after downtime skips obsolete reminders: the first is emitted only before start, the second only before the no-show deadline; at or after the deadline only the no-show event is created. Consumers must deduplicate `eventId`. Real D notification/audit calls use the outbox, expose delivery failures, retry with capped backoff, and never silently claim simulated success. D `accepted` persists as ACCEPTED (not delivered); only D `delivered` persists as DELIVERED; development delivery persists as SIMULATED.

M2/M3 writeback remains defined by `m1-room-blocks.openapi.json`. M2 ACTIVE overlapping an existing active personal reservation returns 409 without changing prior state. M3 ACTIVE retains existing reservations and prevents new bookings. Restrictions are a union of sources; releases preserve revision tombstones. Source provenance is retained for M1 and accepted M2/M3 changes.

## External D dependency requests (proposed)

Identity uses `GET /api/v1/auth/me` with the caller's Bearer token and requires `{id: nonempty string, departmentId: string|null, permissions: string[]}`. A missing field or malformed response fails closed. D-02 uses its own versioned `d-master-data` contract with the service credential `D_M1_TOKEN`. Its complete response is validated before use: required nullable department scope, strict booleans/integers, opening bounds, unique IDs/numbers and seat ownership must be consistent; malformed responses or a detail ID different from the requested room return 503. Additive unknown fields are ignored for compatibility. D requests never follow redirects, so bearer credentials are not forwarded to a redirected destination.

Notifications call `POST /internal/v1/notifications` with `Authorization: Bearer $D_NOTIFICATION_TOKEN` and `{eventId,userId,reservationId,kind,channel:"in_app",scheduledAt,roomId,roomName,seatId,seatNumber,startsAt,endsAt}`. `kind` is BEFORE_START, CHECKIN_REMINDER or NO_SHOW. The durable event ID is `<reservationId>:<kind>` and remains unchanged across retries. A provider must deduplicate this ID and retain the same durable acceptance after its own restart.

Audit calls `POST /internal/v1/audit` with `Authorization: Bearer $D_AUDIT_TOKEN` and `{eventId,sourceSystem,sourceId,roomId,action,actorId,result:"success",occurredAt,detail}`. Actor IDs identify the authenticated user or explicit source service/scheduler. `detail` contains only action-specific references and nonsecret values. The event is created atomically with the M1 change; payload retries keep the same ID.

Both delivery endpoints must return `{eventId,status:"accepted"|"delivered"}` matching the submitted ID. ACCEPTED transfers durable retry responsibility to D and is not proof of channel delivery; DELIVERED is provider-asserted delivery. An invalid/missing acknowledgement, rejection, timeout or transport failure retains PENDING for retry with capped exponential backoff. This consumer does not implement provider delivery/read-receipt lookup; actual D delivery integration remains unverified. Error classifications are retained without provider response bodies or tokens.
