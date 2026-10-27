"""M3 work-order policy and transactional state transitions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4
from sqlalchemy import insert, select, update
from .database import orders, keys, outbox

STATES = {"SUBMITTED", "ASSIGNED", "BLOCK_PENDING", "IN_PROGRESS",
          "PENDING_ACCEPTANCE", "RELEASE_PENDING", "CLOSED", "CANCELLED"}


class DomainError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class WorkOrderService:
    def __init__(self, db, directory, settings, clock=utcnow):
        self.db, self.directory, self.settings, self.clock = db, directory, settings, clock

    def history(self, order, action, actor=None, note="", now=None):
        order["history"].append({"id": str(uuid4()), "action": action,
            "actorId": actor.id if actor else "m3-system",
            "actorName": actor.name if actor else "M3 系统",
            "note": note, "createdAt": iso(now or self.clock())})

    @staticmethod
    def visible(order, actor):
        return (actor.can("dispatch") or order["reporterId"] == actor.id
                or actor.can("work") and order["assigneeId"] == actor.id)

    def allowed(self, order, actor):
        state, actions = order["status"], []
        if actor.can("dispatch") and state in {"SUBMITTED", "ASSIGNED", "IN_PROGRESS"}:
            actions.append("assign")
        if actor.can("work") and actor.id == order["assigneeId"]:
            if state == "ASSIGNED":
                actions.append("start")
            if state == "IN_PROGRESS":
                actions.append("complete")
        if (actor.can("dispatch") or actor.id == order["reporterId"]) and actor.id not in order["_participants"]:
            if state == "PENDING_ACCEPTANCE":
                actions.extend(["accept", "reject"])
        if (actor.can("dispatch") or actor.id == order["reporterId"]) and state in {"SUBMITTED", "ASSIGNED"}:
            actions.append("cancel")
        if actor.id == order["reporterId"] and state == "CLOSED" and order["rating"] is None:
            actions.append("rate")
        sync = order["sync"]
        if (actor.can("dispatch") and sync and sync["status"] == "failed" and sync["retryable"]
                and state in {"BLOCK_PENDING", "RELEASE_PENDING"}):
            actions.append("retry-sync")
        return actions

    def public(self, order, actor):
        result = deepcopy({k: v for k, v in order.items() if not k.startswith("_")})
        result["allowedActions"] = self.allowed(order, actor)
        return result

    def load(self, connection, order_id, actor=None):
        data = connection.execute(select(orders.c.data).where(orders.c.id == order_id)).scalar_one_or_none()
        if data is None or (actor is not None and not self.visible(data, actor)):
            raise DomainError("NOT_FOUND", "工单不存在或无权查看", 404)
        return deepcopy(data)

    def save(self, connection, order, now=None):
        order["version"] += 1
        order["updatedAt"] = iso(now or self.clock())
        connection.execute(update(orders).where(orders.c.id == order["id"]).values(data=order))

    def get(self, order_id, actor):
        with self.db.transaction() as connection:
            return self.public(self.load(connection, order_id, actor), actor)

    def list(self, actor, status=None, room_id=None, view="all", q=""):
        with self.db.transaction() as connection:
            items = [data for data in connection.execute(select(orders.c.data)).scalars() if self.visible(data, actor)]
        if status:
            items = [x for x in items if x["status"] == status]
        if room_id:
            items = [x for x in items if x["roomId"] == room_id]
        if view == "mine":
            items = [x for x in items if x["reporterId"] == actor.id]
        elif view == "assigned":
            items = [x for x in items if x["assigneeId"] == actor.id]
        elif view == "acceptance":
            items = [x for x in items if "accept" in self.allowed(x, actor)]
        elif view == "overdue":
            items = [x for x in items if x["escalated"] and x["dueAt"]]
        if q:
            search = q.casefold()
            items = [x for x in items if search in " ".join([x["id"], x["title"], x["description"], x["roomName"]]).casefold()]
        return [self.public(x, actor) for x in sorted(items, key=lambda x: (x["createdAt"], x["id"]), reverse=True)]

    def create(self, actor, payload, key):
        if not actor.can("report"):
            raise DomainError("FORBIDDEN", "当前身份没有报修权限", 403)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        room = next((r for r in self.directory.rooms(actor) if r["id"] == payload["roomId"]), None)
        if room is None:
            raise DomainError("INVALID_ROOM", "房间不存在或无权报修", 422)
        now = self.clock()
        with self.db.transaction() as connection:
            previous = connection.execute(select(keys).where(keys.c.actor_id == actor.id, keys.c.key == key)).mappings().first()
            if previous:
                if previous["request_hash"] != digest:
                    raise DomainError("IDEMPOTENCY_CONFLICT", "幂等键已用于不同的报修内容")
                return self.public(self.load(connection, previous["order_id"], actor), actor), False
            order = {"id": str(uuid4()), "roomId": room["id"], "roomName": room["name"],
                **payload, "reporterId": actor.id, "reporterName": actor.name,
                "assigneeId": None, "assigneeName": None, "status": "SUBMITTED", "version": 1,
                "createdAt": iso(now), "updatedAt": iso(now),
                "dueAt": iso(now + timedelta(hours=self.settings.assignment_sla_hours)),
                "escalated": False, "rating": None, "sync": None, "history": [],
                "_participants": [], "_stage": 0, "_jobId": None, "_blockStartsAt": None,
                "_dependencyModes": {"directory": self.settings.directory_mode, "m1": self.settings.m1_mode}}
            self.history(order, "submitted", actor, now=now)
            connection.execute(insert(orders).values(id=order["id"], data=order))
            connection.execute(insert(keys).values(actor_id=actor.id, key=key, request_hash=digest, order_id=order["id"]))
            return self.public(order, actor), True

    def enqueue(self, connection, order, status, now):
        job_id = str(uuid4())
        payload = {"roomId": order["roomId"], "revision": 1 if status == "ACTIVE" else 2,
                   "status": status, "startsAt": order["_blockStartsAt"]}
        connection.execute(insert(outbox).values(id=job_id, order_id=order["id"], payload=payload,
            correlation_id=str(uuid4()), status="pending", attempts=0, next_attempt=now.timestamp(),
            lease_until=None, lease_token=None, error=None, retryable=1))
        order["_jobId"] = job_id
        order["sync"] = {"status": "pending", "attempts": 0, "error": None, "retryable": True}

    def act(self, order_id, action, actor, payload):
        technician = None
        if action == "assign" and actor.can("dispatch"):
            snapshot = self.get(order_id, actor)
            if snapshot["version"] == payload["version"] and "assign" in snapshot["allowedActions"]:
                # A roster is external I/O. Fetch outside the write transaction;
                # version, state and authority are checked again before commit.
                technician = next((t for t in self.directory.technicians(actor)
                                   if t.id == payload["assigneeId"]), None)
        now = self.clock()
        with self.db.transaction() as connection:
            order = self.load(connection, order_id, actor)
            if payload["version"] != order["version"]:
                raise DomainError("VERSION_CONFLICT", "工单已更新，请刷新后重试")
            if action not in self.allowed(order, actor):
                # Differentiate role authorization from a state already advanced by another action.
                entitled = (actor.can("dispatch") if action in {"assign", "retry-sync"} else
                    actor.can("work") and actor.id == order["assigneeId"] if action in {"start", "complete"} else
                    actor.id == order["reporterId"] if action == "rate" else
                    actor.can("dispatch") or actor.id == order["reporterId"])
                if action in {"accept", "reject"} and actor.id in order["_participants"]:
                    entitled = False
                raise DomainError("INVALID_STATE" if entitled else "FORBIDDEN",
                                  "当前状态不允许此操作" if entitled else "无权执行此操作",
                                  409 if entitled else 403)
            note = payload.get("note", "")
            if action == "assign":
                if technician is None or not technician.can("work"):
                    raise DomainError("INVALID_ASSIGNEE", "请选择有效维修人员", 422)
                if order["status"] == "SUBMITTED":
                    order["status"], order["_stage"], order["escalated"] = "ASSIGNED", 1, False
                    order["dueAt"] = iso(now + timedelta(hours=self.settings.repair_sla_hours))
                order["assigneeId"], order["assigneeName"] = technician.id, technician.name
                note = f"派给 {technician.name}" + (f"；{note}" if note else "")
            elif action == "start":
                order["status"], order["_blockStartsAt"] = "BLOCK_PENDING", iso(now)
                if actor.id not in order["_participants"]:
                    order["_participants"].append(actor.id)
                self.enqueue(connection, order, "ACTIVE", now)
            elif action == "complete":
                order["status"], order["dueAt"], order["escalated"] = "PENDING_ACCEPTANCE", None, False
                if actor.id not in order["_participants"]:
                    order["_participants"].append(actor.id)
            elif action == "accept":
                if actor.id != order["reporterId"] and not note:
                    raise DomainError("REASON_REQUIRED", "管理员代验必须填写理由", 422)
                order["status"] = "RELEASE_PENDING"
                self.enqueue(connection, order, "RELEASED", now)
            elif action == "reject":
                order["status"], order["escalated"] = "IN_PROGRESS", False
                order["_stage"] += 1
                order["dueAt"] = iso(now + timedelta(hours=self.settings.repair_sla_hours))
            elif action == "cancel":
                order["status"], order["dueAt"], order["escalated"] = "CANCELLED", None, False
            elif action == "rate":
                order["rating"] = {"score": payload["score"], "comment": payload.get("comment", ""), "createdAt": iso(now)}
            elif action == "retry-sync":
                connection.execute(update(outbox).where(outbox.c.id == order["_jobId"]).values(
                    status="pending", attempts=0, next_attempt=now.timestamp(), lease_until=None,
                    lease_token=None, error=None, retryable=1))
                order["sync"] = {"status": "pending", "attempts": 0, "error": None, "retryable": True}
            self.history(order, action, actor, note, now)
            self.save(connection, order, now)
            return self.public(order, actor)

    def assert_production_data(self):
        """Never deliver a development or unclassified legacy outbox to real M1.

        Separate production databases are an explicit deployment boundary. This
        check preserves records for review rather than relabelling/deleting them.
        """
        with self.db.transaction() as connection:
            for order in connection.execute(select(orders.c.data)).scalars():
                if order.get("_dependencyModes") != {"directory": "http", "m1": "http"}:
                    raise ValueError("Production requires a separate database without development or unclassified M3 records")

    def scan_sla(self):
        now, count = self.clock(), 0
        with self.db.transaction() as connection:
            for original in connection.execute(select(orders.c.data)).scalars():
                order = deepcopy(original)
                if (order["dueAt"] and not order["escalated"] and
                    order["status"] in {"SUBMITTED", "ASSIGNED", "BLOCK_PENDING", "IN_PROGRESS"} and
                    now >= stamp(order["dueAt"])):
                    order["escalated"] = True
                    self.history(order, "sla-escalated", note=f"阶段 {order['_stage']} 超时，已列入管理员待办；D 通知未接入", now=now)
                    self.save(connection, order, now)
                    count += 1
        return count
