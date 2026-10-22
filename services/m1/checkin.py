"""M1-04: daily per-room Web code and atomic owner-only check-in."""
import hashlib
import hmac
import os
from datetime import timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from services.platform import Problem, utc_text
from services.m1 import core, dependencies

router = APIRouter(prefix='/api/v1')


class CheckIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1,max_length=64)


def daily_code(room_id, at):
    secret = os.getenv('M1_CHECKIN_SECRET','')
    if len(secret)<32:
        raise Problem(503,'CHECKIN_SECRET_NOT_CONFIGURED','Check-in secret must contain at least 32 characters.')
    day = at.astimezone(core.LOCAL_TZ).date().isoformat()
    digest = hmac.new(secret.encode(),f'{room_id}:{day}'.encode(),hashlib.sha256).hexdigest()
    # Ten hexadecimal characters are practical for display, with no small six-digit code space.
    return digest[:10].upper()


@router.get('/rooms/{room_id}/check-in-code')
def show_code(room_id: str,user=Depends(dependencies.identity)):
    dependencies.require(user,'room:manage')
    dependencies.room(room_id)
    at = core.now()
    local = at.astimezone(core.LOCAL_TZ)
    expiry = local.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    code = daily_code(room_id,at)
    with core.DB.connection() as conn:
        core.record(conn,'M1',room_id,room_id,'CHECKIN_CODE_VIEWED',{'actorId':user['id']},at)
    return {'roomId':room_id,'date':local.date().isoformat(),'code':code,'expiresAt':utc_text(expiry)}


@router.post('/reservations/{reservation_id}/check-in')
def check_in(reservation_id: str,body: CheckIn,user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    at = core.now()
    with core.DB.connection() as conn:
        original = core.owned(conn,reservation_id,user)
        core.lock(conn,'room:'+original['room_id'],'user:'+user['id'])
        at = core.now()
        row = core.owned(conn,reservation_id,user,True)
        if not row['starts_at']<=at<row['starts_at']+timedelta(minutes=15):
            raise Problem(409,'CHECKIN_WINDOW_CLOSED','Check-in is allowed from start until 15 minutes after start.')
        if not hmac.compare_digest(daily_code(row['room_id'],at).encode(),body.code.strip().upper().encode()):
            raise Problem(422,'INVALID_CHECKIN_CODE','Room code is invalid or expired.')
        if row['status']=='CHECKED_IN':
            return core.reservation_json(row,at)
        if row['status']!='RESERVED':
            raise Problem(409,'RESERVATION_NOT_ACTIVE','Reservation cannot be checked in.')
        row = conn.execute("UPDATE reservations SET status='CHECKED_IN',checked_in_at=%s WHERE id=%s RETURNING *",(at,reservation_id)).fetchone()
        core.record(conn,'M1',reservation_id,row['room_id'],'CHECKED_IN',{'actorId':user['id'],'seatId':row['seat_id']},at)
        return core.reservation_json(row,at)
