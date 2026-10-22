"""M1-01/M1-02: permission-filtered availability from authoritative D data."""
from fastapi import APIRouter, Depends
from services.platform import Problem
from services.m1 import core, dependencies

router = APIRouter(prefix='/api/v1')


@router.get('/seats')
def search(startsAt: str, endsAt: str, hasSocket: bool | None = None,
           roomId: str | None = None, user=Depends(dependencies.identity)):
    dependencies.require(user,'seat:reserve')
    at = core.now()
    with core.DB.connection() as conn:
        start,end = core.interval(startsAt,endsAt,core.maximum(conn),future=True,whole_hour=True,at=at)
        if conn.execute(f'SELECT 1 FROM reservations WHERE user_id=%s AND starts_at < %s AND ends_at > %s AND {core.ACTIVE_SQL} LIMIT 1', (user['id'],end,start,at)).fetchone():
            return {'items':[]}
        available = []
        for room in dependencies.rooms():
            if roomId is not None and room['id'] != roomId:
                continue
            try:
                core.validate_room(room,user,start,end)
            except Problem as exc:
                if exc.status in (403,409):
                    continue
                raise
            if conn.execute("SELECT 1 FROM room_blocks WHERE room_id=%s AND status='ACTIVE' AND starts_at < %s AND (ends_at IS NULL OR ends_at > %s) LIMIT 1", (room['id'],end,start)).fetchone():
                continue
            occupied = {row['seat_id'] for row in conn.execute(f'SELECT seat_id FROM reservations WHERE room_id=%s AND starts_at < %s AND ends_at > %s AND {core.ACTIVE_SQL}', (room['id'],end,start,at)).fetchall()}
            for seat in room['seats']:
                if seat['active'] and not seat['retired'] and seat['id'] not in occupied and (hasSocket is None or seat['hasSocket']==hasSocket):
                    available.append({'id':seat['id'],'roomId':room['id'],'roomName':room['name'],
                                      'number':seat['number'],'hasSocket':seat['hasSocket'],'departmentId':room['departmentId']})
        return {'items':sorted(available,key=lambda item:(item['roomId'],item['number']))}
