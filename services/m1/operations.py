"""M1-07 aggregate facts without exposing student identities."""
from fastapi import APIRouter, Depends
from services.platform import utc_text
from services.m1 import core,dependencies,scheduler

router=APIRouter(prefix='/api/v1')


def counts():
    return {'reservations':0,'checkedIn':0,'cancelled':0,'noShows':0,'reservedHours':0.0}


@router.get('/operations')
def operations(startsAt: str,endsAt: str,user=Depends(dependencies.identity)):
    dependencies.require(user,'operations:read','room:manage')
    start,end=core.interval(startsAt,endsAt)
    scheduler.process_due()
    with core.DB.connection() as conn:
        rows=conn.execute('SELECT * FROM reservations WHERE starts_at < %s AND ends_at > %s ORDER BY room_id,seat_id,starts_at',(end,start)).fetchall()
    totals=counts()
    grouped={}
    for row in rows:
        room=grouped.setdefault(row['room_id'],{'roomId':row['room_id'],'roomName':row['room_name'],**counts(),'seats':{}})
        seat=room['seats'].setdefault(row['seat_id'],{'seatId':row['seat_id'],'seatNumber':row['seat_number'],**counts()})
        for target in (totals,room,seat):
            target['reservations']+=1
            if row['status']=='CHECKED_IN':
                target['checkedIn']+=1
            if row['status']=='CANCELLED':
                target['cancelled']+=1
            if row['status']=='NO_SHOW':
                target['noShows']+=1
            if row['status'] in ('RESERVED','CHECKED_IN'):
                target['reservedHours']+=(min(end,row['ends_at'])-max(start,row['starts_at'])).total_seconds()/3600
    for room in grouped.values():
        room['seats']=list(room['seats'].values())
    return {'startsAt':utc_text(start),'endsAt':utc_text(end),'totals':totals,'rooms':list(grouped.values())}
