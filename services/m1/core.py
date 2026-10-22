"""M1 persistence and shared invariants; no provider database access."""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from services.platform import Database, Problem, utcnow, utc_text
from services.m1 import dependencies

DB = Database('m1')
LOCAL_TZ = ZoneInfo('Asia/Shanghai')
ACTIVE_SQL = "(status='CHECKED_IN' OR (status='RESERVED' AND starts_at + interval '15 minutes' > %s))"


def migrate():
    DB.migrate(Path(__file__).parent / 'migrations')


def now():
    return utcnow()


def parse_utc(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise Problem(422, 'UTC_REQUIRED', 'Timestamps must use UTC with a Z suffix.')
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError:
        raise Problem(422, 'INVALID_TIMESTAMP', 'Invalid timestamp.') from None
    return parsed.astimezone(timezone.utc)


def interval(starts, ends, maximum=366*24, future=False, whole_hour=False, at=None):
    start, end = parse_utc(starts), parse_utc(ends)
    at = at or now()
    if end <= start or end-start > timedelta(hours=maximum):
        raise Problem(422, 'INVALID_INTERVAL', 'Duration must be positive and within the configured maximum.')
    if whole_hour and any((value.minute or value.second or value.microsecond) for value in (start,end)):
        raise Problem(422, 'WHOLE_HOUR_REQUIRED', 'Reservation boundaries must be whole hours.')
    if future:
        horizon = int(os.getenv('M1_BOOKING_HORIZON_DAYS', '7'))
        if start <= at or end > at + timedelta(days=horizon):
            raise Problem(422, 'OUTSIDE_BOOKING_WINDOW', 'Reservation must start in the future and end within the booking horizon.')
    return start,end


def lock(conn, *keys):
    # Stable order prevents cross-room user bookings from acquiring inconsistent locks.
    for key in sorted(set(keys)):
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (key,))


def authorized_room(room, user):
    if 'departmentId' not in room:
        raise Problem(503,'INVALID_MASTER_DATA','Room department scope is missing.')
    return room['departmentId'] is None or room['departmentId'] == user.get('departmentId')


def validate_room(room, user, start, end, seat_id=None):
    if not authorized_room(room,user):
        raise Problem(403, 'ROOM_FORBIDDEN', 'This room is not open to your department.')
    if not room['active'] or room['retired']:
        raise Problem(409, 'ROOM_UNAVAILABLE', 'Room is unavailable.')
    local_start,local_end = start.astimezone(LOCAL_TZ),end.astimezone(LOCAL_TZ)
    day_start = local_start.replace(hour=0,minute=0,second=0,microsecond=0)
    opening = day_start + timedelta(hours=room['openHour'])
    closing = day_start + timedelta(hours=room['closeHour'])
    if local_start.weekday() not in room['weekdays'] or local_start < opening or local_end > closing:
        raise Problem(409, 'ROOM_CLOSED', 'Requested interval is outside room opening hours.')
    if seat_id is not None:
        seat = next((s for s in room['seats'] if s['id']==seat_id),None)
        if seat is None:
            raise Problem(404, 'SEAT_NOT_FOUND', 'Seat does not belong to this room.')
        if not seat['active'] or seat['retired']:
            raise Problem(409, 'SEAT_UNAVAILABLE', 'Seat is unavailable.')
        return seat


def maximum(conn):
    return conn.execute('SELECT max_reservation_hours FROM settings WHERE id=true').fetchone()['max_reservation_hours']


def reservation_json(row, at=None):
    at = at or now()
    status = 'COMPLETED' if row['status']=='CHECKED_IN' and row['ends_at'] <= at else row['status']
    return {'id':row['id'],'userId':row['user_id'],'roomId':row['room_id'],'roomName':row['room_name'],
            'seatId':row['seat_id'],'seatNumber':row['seat_number'],'startsAt':utc_text(row['starts_at']),
            'endsAt':utc_text(row['ends_at']),'status':status,'createdAt':utc_text(row['created_at']),
            'checkedInAt':utc_text(row['checked_in_at']) if row['checked_in_at'] else None,
            'dependencyMode':dependencies.dependency_mode()}


def owned(conn, reservation_id, user, for_update=False):
    row = conn.execute('SELECT * FROM reservations WHERE id=%s' + (' FOR UPDATE' if for_update else ''), (reservation_id,)).fetchone()
    if row is None or row['user_id'] != user['id']:
        raise Problem(404, 'RESERVATION_NOT_FOUND', 'Reservation not found.')
    return row


def enqueue(conn, event_id, kind, payload, at):
    conn.execute('INSERT INTO outbox(id,kind,payload,next_attempt_at,created_at) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                 (event_id,kind,Jsonb({'eventId':event_id,**payload}),at,at))


def record(conn, source, source_id, room_id, action, detail, at):
    event_id = str(uuid4())
    conn.execute('INSERT INTO provenance(id,source_system,source_id,room_id,action,created_at,detail) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                 (event_id,source,source_id,room_id,action,at,Jsonb(detail)))
    enqueue(conn, 'audit:'+event_id, 'audit', {'sourceSystem':source,'sourceId':source_id,'roomId':room_id,
        'action':action,'actorId':detail.get('actorId',source.lower()+'-service'),'result':'success','occurredAt':utc_text(at),'detail':detail}, at)


def ensure_no_conflict(conn, room_id, seat_id, user_id, start, end, at):
    block = conn.execute("SELECT 1 FROM room_blocks WHERE room_id=%s AND status='ACTIVE' AND starts_at < %s AND (ends_at IS NULL OR ends_at > %s) LIMIT 1", (room_id,end,start)).fetchone()
    if block:
        raise Problem(409, 'ROOM_BLOCKED', 'Room is blocked by an active source.')
    occupied = conn.execute(f'SELECT 1 FROM reservations WHERE (seat_id=%s OR user_id=%s) AND starts_at < %s AND ends_at > %s AND {ACTIVE_SQL} LIMIT 1', (seat_id,user_id,end,start,at)).fetchone()
    if occupied:
        raise Problem(409, 'RESERVATION_CONFLICT', 'Seat or student already has an overlapping reservation.')
