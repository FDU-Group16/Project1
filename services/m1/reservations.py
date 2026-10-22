"""M1-03: transactional reservations, bounded slots and explicit idempotency."""
from uuid import uuid4
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from services.platform import Problem
from services.m1 import core, dependencies

router = APIRouter(prefix='/api/v1')


class Booking(BaseModel):
    model_config = ConfigDict(extra='forbid')
    roomId: str = Field(min_length=1,max_length=128)
    seatId: str = Field(min_length=1,max_length=128)
    startsAt: str
    endsAt: str


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    maxReservationHours: int = Field(ge=1,le=24,strict=True)


@router.get('/settings')
def settings(user=Depends(dependencies.identity)):
    with core.DB.connection() as conn:
        return {'maxReservationHours':core.maximum(conn)}


@router.put('/settings')
def update_settings(body: Settings,user=Depends(dependencies.identity)):
    dependencies.require(user,'room:manage')
    with core.DB.connection() as conn:
        conn.execute('UPDATE settings SET max_reservation_hours=%s WHERE id=true',(body.maxReservationHours,))
        core.record(conn,'M1','settings','*','SETTINGS_UPDATED',{'maxReservationHours':body.maxReservationHours,'actorId':user['id']},core.now())
    return body.model_dump()


def create_booking(body, user, key):
    dependencies.require(user,'seat:reserve')
    if not key or len(key)>128 or not key.strip():
        raise Problem(422,'IDEMPOTENCY_KEY_REQUIRED','A nonempty Idempotency-Key of at most 128 characters is required.')
    payload = body.model_dump()
    at = core.now()
    with core.DB.connection() as conn:
        core.lock(conn,'room:'+body.roomId,'user:'+user['id'])
        at = core.now()
        previous = conn.execute('SELECT * FROM reservations WHERE user_id=%s AND idempotency_key=%s',(user['id'],key)).fetchone()
        if previous:
            if previous['request_payload'] != payload:
                raise Problem(409,'IDEMPOTENCY_PAYLOAD_MISMATCH','Idempotency key already belongs to another request.')
            return core.reservation_json(previous,at)
        room = dependencies.room(body.roomId)
        at = core.now()
        start,end = core.interval(body.startsAt,body.endsAt,core.maximum(conn),future=True,whole_hour=True,at=at)
        seat = core.validate_room(room,user,start,end,body.seatId)
        core.ensure_no_conflict(conn,body.roomId,body.seatId,user['id'],start,end,at)
        booking_id = str(uuid4())
        row = conn.execute('''INSERT INTO reservations(id,user_id,room_id,room_name,seat_id,seat_number,starts_at,ends_at,status,created_at,idempotency_key,request_payload)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'RESERVED',%s,%s,%s) RETURNING *''',
            (booking_id,user['id'],body.roomId,room['name'],body.seatId,seat['number'],start,end,at,key,Jsonb(payload))).fetchone()
        core.record(conn,'M1',booking_id,body.roomId,'RESERVED',{'actorId':user['id'],'seatId':body.seatId,'startsAt':body.startsAt,'endsAt':body.endsAt},at)
        return core.reservation_json(row,at)


@router.post('/reservations')
def create(body: Booking,user=Depends(dependencies.identity),idempotency_key: str | None=Header(default=None)):
    return create_booking(body,user,idempotency_key)


@router.post('/reservations/{reservation_id}/cancel')
def cancel(reservation_id: str,user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    at = core.now()
    with core.DB.connection() as conn:
        original = core.owned(conn,reservation_id,user)
        core.lock(conn,'room:'+original['room_id'],'user:'+user['id'])
        at = core.now()
        row = core.owned(conn,reservation_id,user,True)
        if row['status']=='CANCELLED':
            return core.reservation_json(row,at)
        if row['status']!='RESERVED' or at>=row['starts_at']:
            raise Problem(409,'CANCELLATION_CLOSED','Cancellation is allowed only before the reservation starts.')
        row = conn.execute("UPDATE reservations SET status='CANCELLED',cancelled_at=%s WHERE id=%s RETURNING *",(at,reservation_id)).fetchone()
        core.record(conn,'M1',reservation_id,row['room_id'],'CANCELLED',{'actorId':user['id'],'seatId':row['seat_id']},at)
        return core.reservation_json(row,at)
