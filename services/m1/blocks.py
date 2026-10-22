"""M1-08 / X provider boundary: network-only room blocks and provenance."""
from typing import Literal
from fastapi import APIRouter, Depends, Header, Path, Query
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from services.platform import Problem,utc_text
from services.m1 import core,dependencies

router=APIRouter()


class M3Block(BaseModel):
    model_config=ConfigDict(extra='forbid')
    roomId: str=Field(min_length=1,max_length=128)
    revision: int=Field(ge=1,le=9007199254740991,strict=True)
    status: Literal['ACTIVE','RELEASED']
    startsAt: str
    endsAt: str | None=None


class M2Block(M3Block):
    endsAt: str


def state(row):
    result={'sourceSystem':row['source_system'],'sourceId':row['source_id'],'roomId':row['room_id'],
            'revision':row['revision'],'status':row['status'],'startsAt':utc_text(row['starts_at']),
            'appliedAt':utc_text(row['applied_at'])}
    if row['ends_at'] is not None:
        result['endsAt']=utc_text(row['ends_at'])
    return result


def apply_block(source,source_id,body,authorization):
    dependencies.service_identity(source,authorization)
    start=core.parse_utc(body.startsAt)
    end=core.parse_utc(body.endsAt) if body.endsAt is not None else None
    if end is not None and end<=start:
        raise Problem(422,'INVALID_INTERVAL','Block end must be later than start.')
    if 'endsAt' in body.model_fields_set and body.endsAt is None:
        raise Problem(422,'INVALID_TIMESTAMP','Omit an open end; null is not a timestamp.')
    payload=body.model_dump(exclude_none=True)
    at=core.now()
    with core.DB.connection() as conn:
        # Source lock prevents concurrent moving/revising a key across different rooms.
        core.lock(conn,'block:'+source+':'+source_id)
        old=conn.execute('SELECT * FROM room_blocks WHERE source_system=%s AND source_id=%s',(source,source_id)).fetchone()
        if old:
            if body.revision<old['revision']:
                raise Problem(409,'STALE_REVISION','A newer source revision is already applied.')
            if body.revision==old['revision']:
                if old['request_payload']!=payload:
                    raise Problem(409,'REVISION_PAYLOAD_MISMATCH','Same revision has a different payload.')
                return state(old)
            if body.roomId!=old['room_id']:
                raise Problem(422,'SOURCE_ROOM_MISMATCH','A source key cannot change its room.')
        core.lock(conn,'room:'+body.roomId)
        dependencies.room(body.roomId)
        at=core.now()
        if source=='M2' and body.status=='ACTIVE':
            conflict=conn.execute(f'SELECT 1 FROM reservations WHERE room_id=%s AND starts_at < %s AND ends_at > %s AND {core.ACTIVE_SQL} LIMIT 1',(body.roomId,end,start,at)).fetchone()
            if conflict:
                raise Problem(409,'ROOM_OCCUPANCY_CONFLICT','Existing individual reservations overlap the room block.')
        row=conn.execute('''INSERT INTO room_blocks(source_system,source_id,room_id,revision,status,starts_at,ends_at,applied_at,request_payload)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(source_system,source_id) DO UPDATE SET revision=EXCLUDED.revision,status=EXCLUDED.status,
            starts_at=EXCLUDED.starts_at,ends_at=EXCLUDED.ends_at,applied_at=EXCLUDED.applied_at,request_payload=EXCLUDED.request_payload RETURNING *''',
            (source,source_id,body.roomId,body.revision,body.status,start,end,at,Jsonb(payload))).fetchone()
        core.record(conn,source,source_id,body.roomId,body.status,{'revision':body.revision,'startsAt':body.startsAt,**({'endsAt':body.endsAt} if body.endsAt else {})},at)
        return state(row)


@router.put('/internal/v1/room-blocks/m2/{sourceId}')
def m2(body: M2Block,sourceId: str=Path(pattern=r'^[A-Za-z0-9._:-]+$',min_length=1,max_length=128),authorization: str | None=Header(default=None)):
    return apply_block('M2',sourceId,body,authorization)


@router.put('/internal/v1/room-blocks/m3/{sourceId}')
def m3(body: M3Block,sourceId: str=Path(pattern=r'^[A-Za-z0-9._:-]+$',min_length=1,max_length=128),authorization: str | None=Header(default=None)):
    return apply_block('M3',sourceId,body,authorization)


@router.get('/api/v1/rooms/{room_id}/provenance')
def provenance(room_id: str,offset: int=Query(default=0,ge=0),limit: int=Query(default=20,ge=1,le=100),user=Depends(dependencies.identity)):
    dependencies.require(user,'operations:read','room:manage')
    dependencies.room(room_id)
    with core.DB.connection() as conn:
        total=conn.execute('SELECT count(*) AS count FROM provenance WHERE room_id=%s',(room_id,)).fetchone()['count']
        rows=conn.execute('SELECT * FROM provenance WHERE room_id=%s ORDER BY created_at DESC,id LIMIT %s OFFSET %s',(room_id,limit,offset)).fetchall()
    return {'items':[{'id':row['id'],'sourceSystem':row['source_system'],'sourceId':row['source_id'],
            'roomId':row['room_id'],'action':row['action'],'createdAt':utc_text(row['created_at']),'detail':row['detail']} for row in rows],'total':total}
