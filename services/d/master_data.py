"""Room/seat master data. Each write is atomic inside D's own schema."""

from uuid import uuid4
from fastapi import APIRouter, Depends
from pydantic import ValidationError

from services.platform import Database, Problem
from services.d.dependencies import Identity, current_identity, require_admin, require_m1
from services.d.models import RoomCreate, RoomPatch, SeatCreate, SeatPatch

router = APIRouter()
db = Database("d")


def room_json(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "departmentId": row["department_id"],
            "openHour": row["open_hour"], "closeHour": row["close_hour"], "weekdays": row["weekdays"],
            "active": row["active"], "retired": row["retired"]}


def seat_json(row: dict) -> dict:
    return {"id": row["id"], "roomId": row["room_id"], "number": row["number"],
            "hasSocket": row["has_socket"], "active": row["active"], "retired": row["retired"]}


def get_room(conn, room_id: str, *, lock=False) -> dict:
    row = conn.execute("SELECT * FROM rooms WHERE id=%s" + (" FOR UPDATE" if lock else ""), (room_id,)).fetchone()
    if row is None:
        raise Problem(404, "ROOM_NOT_FOUND", "Room does not exist")
    return row


def check_room_access(room: dict, identity: Identity):
    if identity.can_read_all:
        return
    if not room["active"] or room["retired"]:
        raise Problem(404, "ROOM_NOT_FOUND", "Room is not available")
    if room["department_id"] is not None and room["department_id"] != identity.department_id:
        raise Problem(403, "ROOM_ACCESS_DENIED", "Room is restricted to another department")


def ensure_not_retired(row: dict, kind: str):
    if row["retired"]:
        raise Problem(409, "RESOURCE_RETIRED", f"Retired {kind} cannot be changed")


def locked_seat(conn, seat_id: str) -> tuple[dict, dict]:
    initial = conn.execute("SELECT room_id FROM seats WHERE id=%s", (seat_id,)).fetchone()
    if initial is None:
        raise Problem(404, "SEAT_NOT_FOUND", "Seat does not exist")
    # Every seat write locks parent first, matching room retirement lock order.
    room = get_room(conn, initial["room_id"], lock=True)
    seat = conn.execute("SELECT * FROM seats WHERE id=%s FOR UPDATE", (seat_id,)).fetchone()
    return room, seat


@router.get("/api/v1/rooms")
def list_rooms(identity: Identity = Depends(current_identity)):
    with db.connection() as conn:
        if identity.can_read_all:
            rows = conn.execute("SELECT * FROM rooms ORDER BY name,id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM rooms WHERE active AND NOT retired AND (department_id IS NULL OR department_id=%s) ORDER BY name,id", (identity.department_id,)).fetchall()
        return {"items": [room_json(row) for row in rows]}


@router.post("/api/v1/rooms", status_code=201)
def create_room(body: RoomCreate, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        row = conn.execute("""INSERT INTO rooms(id,name,department_id,open_hour,close_hour,weekdays,active)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (str(uuid4()), body.name, body.departmentId, body.openHour, body.closeHour, body.weekdays, body.active)).fetchone()
        return room_json(row)


@router.get("/api/v1/rooms/{room_id}")
def read_room(room_id: str, identity: Identity = Depends(current_identity)):
    with db.connection() as conn:
        row = get_room(conn, room_id)
        check_room_access(row, identity)
        return room_json(row)


@router.patch("/api/v1/rooms/{room_id}")
def update_room(room_id: str, body: RoomPatch, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        row = get_room(conn, room_id, lock=True)
        ensure_not_retired(row, "room")
        merged = {key: value for key, value in room_json(row).items() if key not in {"id", "retired"}}
        merged.update(body.model_dump(exclude_unset=True))
        try:
            validated = RoomCreate.model_validate(merged)
        except ValidationError as exc:
            raise Problem(422, "INVALID_OPENING_HOURS", "openHour must precede closeHour") from exc
        row = conn.execute("""UPDATE rooms SET name=%s,department_id=%s,open_hour=%s,close_hour=%s,weekdays=%s,active=%s
            WHERE id=%s RETURNING *""", (validated.name, validated.departmentId, validated.openHour,
            validated.closeHour, validated.weekdays, validated.active, room_id)).fetchone()
        return room_json(row)


@router.delete("/api/v1/rooms/{room_id}")
def retire_room(room_id: str, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        get_room(conn, room_id, lock=True)
        row = conn.execute("UPDATE rooms SET active=false,retired=true WHERE id=%s RETURNING *", (room_id,)).fetchone()
        conn.execute("UPDATE seats SET active=false,retired=true WHERE room_id=%s", (room_id,))
        return room_json(row)


@router.get("/api/v1/rooms/{room_id}/seats")
def list_seats(room_id: str, identity: Identity = Depends(current_identity)):
    with db.connection() as conn:
        room = get_room(conn, room_id)
        check_room_access(room, identity)
        query = "SELECT * FROM seats WHERE room_id=%s"
        if not identity.can_read_all:
            query += " AND active AND NOT retired"
        rows = conn.execute(query + " ORDER BY number,id", (room_id,)).fetchall()
        return {"items": [seat_json(row) for row in rows]}


@router.post("/api/v1/rooms/{room_id}/seats", status_code=201)
def create_seat(room_id: str, body: SeatCreate, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        room = get_room(conn, room_id, lock=True)
        ensure_not_retired(room, "room")
        row = conn.execute("""INSERT INTO seats(id,room_id,number,has_socket,active)
            VALUES (%s,%s,%s,%s,%s) RETURNING *""", (str(uuid4()), room_id, body.number, body.hasSocket, body.active)).fetchone()
        return seat_json(row)


@router.patch("/api/v1/seats/{seat_id}")
def update_seat(seat_id: str, body: SeatPatch, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        room, row = locked_seat(conn, seat_id)
        ensure_not_retired(room, "room")
        ensure_not_retired(row, "seat")
        fields = seat_json(row)
        fields.update(body.model_dump(exclude_unset=True))
        row = conn.execute("UPDATE seats SET number=%s,has_socket=%s,active=%s WHERE id=%s RETURNING *",
                           (fields["number"], fields["hasSocket"], fields["active"], seat_id)).fetchone()
        return seat_json(row)


@router.delete("/api/v1/seats/{seat_id}")
def retire_seat(seat_id: str, identity: Identity = Depends(current_identity)):
    require_admin(identity)
    with db.connection() as conn:
        locked_seat(conn, seat_id)
        row = conn.execute("UPDATE seats SET active=false,retired=true WHERE id=%s RETURNING *", (seat_id,)).fetchone()
        return seat_json(row)


@router.get("/internal/v1/rooms", dependencies=[Depends(require_m1)])
def internal_list_rooms():
    with db.connection() as conn:
        # One statement gives a consistent snapshot of room/seat state.
        rows = conn.execute("""SELECT r.*, COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY s.number,s.id)
            FROM seats s WHERE s.room_id=r.id), '[]'::jsonb) AS seats
            FROM rooms r ORDER BY r.name,r.id""").fetchall()
        return {"items": [{**room_json(row), "seats": [seat_json(s) for s in row["seats"]]} for row in rows]}


@router.get("/internal/v1/rooms/{room_id}", dependencies=[Depends(require_m1)])
def internal_read_room(room_id: str):
    with db.connection() as conn:
        row = conn.execute("""SELECT r.*, COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY s.number,s.id)
            FROM seats s WHERE s.room_id=r.id), '[]'::jsonb) AS seats FROM rooms r WHERE r.id=%s""", (room_id,)).fetchone()
        if row is None:
            raise Problem(404, "ROOM_NOT_FOUND", "Room does not exist")
        return {**room_json(row), "seats": [seat_json(s) for s in row["seats"]]}
