"""M1-05 durable restart-safe reminders, breach transition and outbox retries.

Run `python -m services.m1.scheduler --once` or without --once for polling.
Tests inject `at`; HTTP callers cannot override the server clock.
"""
import argparse
import time
from datetime import timedelta
from uuid import uuid4
from services.platform import utc_text
from services.m1 import core, dependencies


def notification_context(row):
    return {'roomId':row['room_id'],'roomName':row['room_name'],'seatId':row['seat_id'],
            'seatNumber':row['seat_number'],'startsAt':utc_text(row['starts_at']),'endsAt':utc_text(row['ends_at'])}


def process_due(at=None):
    at = at or core.now()
    changed = 0
    with core.DB.connection() as conn:
        candidates = conn.execute("SELECT id,room_id,user_id FROM reservations WHERE status='RESERVED' AND starts_at - interval '15 minutes' <= %s",(at,)).fetchall()
    for candidate in candidates:
        with core.DB.connection() as conn:
            core.lock(conn,'room:'+candidate['room_id'],'user:'+candidate['user_id'])
            row = conn.execute('SELECT * FROM reservations WHERE id=%s FOR UPDATE',(candidate['id'],)).fetchone()
            if row['status']!='RESERVED':
                continue
            for name,delta in [('BEFORE_START',-15),('CHECKIN_REMINDER',10)]:
                scheduled = row['starts_at']+timedelta(minutes=delta)
                if scheduled<=at<row['starts_at']+timedelta(minutes=(0 if delta<0 else 15)):
                    event_id = f"{row['id']}:{name}"
                    core.enqueue(conn,event_id,'notification',{'userId':row['user_id'],'reservationId':row['id'],
                        'kind':name,'channel':'in_app','scheduledAt':utc_text(scheduled),**notification_context(row)},at)
            deadline = row['starts_at']+timedelta(minutes=15)
            if at>=deadline:
                conn.execute("UPDATE reservations SET status='NO_SHOW',cancelled_at=%s WHERE id=%s",(deadline,row['id']))
                conn.execute("INSERT INTO breaches(id,reservation_id,user_id,room_id,seat_id,reason,occurred_at) VALUES (%s,%s,%s,%s,%s,'NO_SHOW',%s) ON CONFLICT DO NOTHING",
                    (str(uuid4()),row['id'],row['user_id'],row['room_id'],row['seat_id'],deadline))
                core.enqueue(conn,f"{row['id']}:NO_SHOW",'notification',{'userId':row['user_id'],'reservationId':row['id'],
                    'kind':'NO_SHOW','channel':'in_app','scheduledAt':utc_text(deadline),**notification_context(row)},at)
                core.record(conn,'M1',row['id'],row['room_id'],'NO_SHOW',{'actorId':'m1-scheduler','seatId':row['seat_id'],'occurredAt':utc_text(deadline)},at)
                changed += 1
    return changed


def reminder_window(row,kind):
    if kind=='BEFORE_START':
        return row['starts_at']-timedelta(minutes=15),row['starts_at']
    return row['starts_at']+timedelta(minutes=10),row['starts_at']+timedelta(minutes=15)


def flush_outbox(at=None, limit=100):
    fixed_clock=at
    results = {'accepted':0,'delivered':0,'simulated':0,'failed':0,'suppressed':0}
    current=fixed_clock or core.now()
    # Snapshot candidate IDs without claiming rows. A bounded list avoids busy
    # retries of another worker's first locked row and gives each candidate a turn.
    with core.DB.connection() as conn:
        candidates=conn.execute("SELECT id,kind,payload FROM outbox WHERE state='PENDING' AND next_attempt_at<=%s ORDER BY created_at,id LIMIT %s",(current,limit)).fetchall()
    for candidate in candidates:
        # Reminder delivery acquires room/user before its outbox row, matching
        # scheduling/cancellation transaction order.
        reminder=(candidate['kind']=='notification' and candidate['payload'].get('kind') in {'BEFORE_START','CHECKIN_REMINDER'})
        with core.DB.connection() as conn:
            booking=None
            if reminder:
                booking=conn.execute('SELECT * FROM reservations WHERE id=%s',(candidate['payload'].get('reservationId'),)).fetchone()
                if booking:
                    core.lock(conn,'room:'+booking['room_id'],'user:'+booking['user_id'])
                    booking=conn.execute('SELECT * FROM reservations WHERE id=%s FOR UPDATE',(booking['id'],)).fetchone()
            current=fixed_clock or core.now()
            row=conn.execute("SELECT * FROM outbox WHERE id=%s AND state='PENDING' AND next_attempt_at<=%s FOR UPDATE SKIP LOCKED",(candidate['id'],current)).fetchone()
            if row is None:
                continue
            if reminder:
                opening,closing=reminder_window(booking,row['payload']['kind']) if booking else (None,None)
                if not booking or booking['status']!='RESERVED' or current>=closing:
                    conn.execute("UPDATE outbox SET state='SUPPRESSED',suppressed_at=%s,last_error='OBSOLETE_REMINDER' WHERE id=%s",(current,row['id']))
                    results['suppressed']+=1
                    continue
                if current<opening:
                    conn.execute('UPDATE outbox SET next_attempt_at=%s WHERE id=%s',(opening,row['id']))
                    continue
            # The row and, for reminders, reservation locks remain held through
            # this bounded HTTP request. Cancellation cannot race its preflight.
            try:
                state=dependencies.deliver(row['kind'],row['payload'])
            except Exception as exc:
                error=getattr(exc,'code',type(exc).__name__)
                attempts=row['attempts']+1
                conn.execute('UPDATE outbox SET attempts=%s,next_attempt_at=%s,last_error=%s WHERE id=%s',
                    (attempts,current+timedelta(seconds=min(3600,2**min(attempts,12))),error,row['id']))
                results['failed']+=1
            else:
                conn.execute("UPDATE outbox SET state=%s,attempts=attempts+1,acknowledged_at=%s,delivered_at=%s,last_error=NULL WHERE id=%s",(state,current,current if state=='DELIVERED' else None,row['id']))
                results[state.lower()]+=1
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--interval',type=float,default=30)
    args=parser.parse_args()
    if args.interval<=0:
        parser.error('--interval must be positive')
    core.migrate()
    print('M1 scheduler dependency mode:',dependencies.dependency_mode(),flush=True)
    while True:
        try:
            print({'noShows':process_due(),'outbox':flush_outbox()},flush=True)
        except Exception as exc:
            print({'schedulerError':getattr(exc,'code',type(exc).__name__)},flush=True)
            if args.once:
                raise
        if args.once:
            break
        time.sleep(args.interval)


if __name__=='__main__':
    main()
