"""M1-06 personal reservation history, breaches and rebooking."""
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict
from services.platform import utc_text
from services.m1 import core, dependencies, scheduler
from services.m1.reservations import Booking, create_booking

router=APIRouter(prefix='/api/v1')


class Rebook(BaseModel):
    model_config=ConfigDict(extra='forbid')
    startsAt: str
    endsAt: str


@router.get('/reservations')
def list_reservations(scope: str=Query(default='current',pattern='^(current|history)$'),
                      offset: int=Query(default=0,ge=0),limit: int=Query(default=20,ge=1,le=100),
                      user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    at=core.now()
    scheduler.process_due(at)
    condition="status IN ('RESERVED','CHECKED_IN') AND ends_at > %s"
    if scope=='history':
        condition='NOT ('+condition+')'
    with core.DB.connection() as conn:
        count=conn.execute('SELECT count(*) AS count FROM reservations WHERE user_id=%s AND ('+condition+')',(user['id'],at)).fetchone()['count']
        rows=conn.execute('SELECT * FROM reservations WHERE user_id=%s AND ('+condition+') ORDER BY starts_at DESC,id LIMIT %s OFFSET %s',
                          (user['id'],at,limit,offset)).fetchall()
    return {'items':[core.reservation_json(row,at) for row in rows],'total':count}


@router.get('/reservations/{reservation_id}')
def detail(reservation_id: str,user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    at=core.now()
    scheduler.process_due(at)
    with core.DB.connection() as conn:
        return core.reservation_json(core.owned(conn,reservation_id,user),at)


@router.post('/reservations/{reservation_id}/rebook')
def rebook(reservation_id: str,body: Rebook,user=Depends(dependencies.identity),
           idempotency_key: str | None=Header(default=None)):
    dependencies.require(user,'seat:reserve')
    with core.DB.connection() as conn:
        row=core.owned(conn,reservation_id,user)
    return create_booking(Booking(roomId=row['room_id'],seatId=row['seat_id'],**body.model_dump()),user,idempotency_key)


@router.get('/breaches')
def breaches(offset: int=Query(default=0,ge=0),limit: int=Query(default=20,ge=1,le=100),user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    scheduler.process_due()
    with core.DB.connection() as conn:
        total=conn.execute('SELECT count(*) AS count FROM breaches WHERE user_id=%s',(user['id'],)).fetchone()['count']
        rows=conn.execute('SELECT * FROM breaches WHERE user_id=%s ORDER BY occurred_at DESC,id LIMIT %s OFFSET %s',(user['id'],limit,offset)).fetchall()
    return {'items':[{'id':row['id'],'reservationId':row['reservation_id'],'roomId':row['room_id'],
                     'seatId':row['seat_id'],'reason':row['reason'],'occurredAt':utc_text(row['occurred_at'])} for row in rows],'total':total}
