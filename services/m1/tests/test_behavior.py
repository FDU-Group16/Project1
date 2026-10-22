"""Behavioral M1 tests against a disposable real PostgreSQL database.

Set TEST_M1_DATABASE_URL explicitly. External D responses are isolated fixtures;
root network integration tests additionally verify the actual D02 HTTP adapter.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from services.m1 import core,dependencies,scheduler,checkin
from services.m1.main import app
from services.platform import Problem,utc_text

BASE=datetime(2026,10,22,0,tzinfo=timezone.utc)
ROOMS=[{'id':rid,'name':rid,'departmentId':dept,'openHour':8,'closeHour':22,
        'weekdays':list(range(7)),'active':True,'retired':False,
        'seats':[{'id':rid+'-s1','roomId':rid,'number':'01','hasSocket':True,'active':True,'retired':False},
                 {'id':rid+'-s2','roomId':rid,'number':'02','hasSocket':False,'active':True,'retired':False}]}
       for rid,dept in [('public',None),('cs','cs'),('ee','ee')]]


@unittest.skipUnless(os.getenv('TEST_M1_DATABASE_URL'),'Requires explicit disposable TEST_M1_DATABASE_URL')
class M1Behavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=patch.dict(os.environ,{'M1_DATABASE_URL':os.environ['TEST_M1_DATABASE_URL'],
            'APP_ENV':'test','M1_USE_DEV_DEPENDENCIES':'1','M1_CHECKIN_SECRET':'test-only-secret-value-with-more-than-32-characters',
            'M1_M2_TOKEN':'test-m2','M1_M3_TOKEN':'test-m3'})
        cls.env.start()
        core.migrate()
        cls.client=TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.env.stop()

    def setUp(self):
        with core.DB.connection() as conn:
            conn.execute('TRUNCATE breaches,outbox,provenance,room_blocks,reservations')
            conn.execute('UPDATE settings SET max_reservation_hours=4')
        self.rooms=copy.deepcopy(ROOMS)
        self.clock=BASE
        self.patches=[patch.object(core,'now',lambda:self.clock),
            patch.object(dependencies,'rooms',lambda:self.rooms),
            patch.object(dependencies,'room',self.get_room)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def get_room(self,room_id):
        for room in self.rooms:
            if room['id']==room_id:
                return room
        raise Problem(404,'ROOM_NOT_FOUND','Room not found.')

    def headers(self,user='dev-student-cs',key=None):
        result={'Authorization':'Bearer '+user}
        if key:
            result['Idempotency-Key']=key
        return result

    def payload(self,room='public',seat='s1',start=2,end=3):
        return {'roomId':room,'seatId':room+'-'+seat,'startsAt':utc_text(BASE+timedelta(hours=start)),
                'endsAt':utc_text(BASE+timedelta(hours=end))}

    def book(self,key='one',user='dev-student-cs',**kwargs):
        return self.client.post('/api/v1/reservations',json=self.payload(**kwargs),headers=self.headers(user,key))

    def search(self,**params):
        args={'startsAt':self.payload()['startsAt'],'endsAt':self.payload()['endsAt'],**params}
        return self.client.get('/api/v1/seats',params=args,headers=self.headers())

    def block(self,source='m3',key='repair',revision=1,status='ACTIVE',**kwargs):
        payload={'roomId':'public','revision':revision,'status':status,'startsAt':self.payload()['startsAt'],**kwargs}
        return self.client.put(f'/internal/v1/room-blocks/{source}/{key}',json=payload,
                              headers={'Authorization':'Bearer test-'+source})

    def test_m101_department_filter_and_direct_booking_denial(self):
        result=self.search()
        self.assertEqual(result.status_code,200)
        self.assertEqual({i['roomId'] for i in result.json()['items']},{'public','cs'})
        self.assertEqual(self.book(room='ee').status_code,403)
        self.assertEqual(self.client.get('/api/v1/seats',params=self.payload()).status_code,401)

    def test_m102_socket_inactive_and_closed_room_filters(self):
        self.assertTrue(all(i['hasSocket'] for i in self.search(hasSocket='true').json()['items']))
        self.rooms[0]['seats'][0]['active']=False
        self.rooms[1]['active']=False
        self.assertEqual([i['id'] for i in self.search().json()['items']],['public-s2'])
        self.assertEqual(self.search(startsAt=utc_text(BASE+timedelta(hours=15)),endsAt=utc_text(BASE+timedelta(hours=16))).json()['items'],[])

    def test_m103_duration_whole_hour_window_and_utc_validation(self):
        for start,end in [(2,7),(2,2),(2,2.5),(-1,1),(167,169)]:
            self.assertEqual(self.book(start=start,end=end).status_code,422)
        body=self.payload();body['startsAt']='2026-10-22T10:00:00+08:00'
        self.assertEqual(self.client.post('/api/v1/reservations',json=body,headers=self.headers(key='x')).status_code,422)
        body['startsAt']='20261022T020000Z'
        self.assertEqual(self.client.post('/api/v1/reservations',json=body,headers=self.headers(key='x')).status_code,422)

    def test_m103_settings_and_idempotency(self):
        self.assertEqual(self.client.put('/api/v1/settings',json={'maxReservationHours':6},headers=self.headers()).status_code,403)
        self.assertEqual(self.client.put('/api/v1/settings',json={'maxReservationHours':6},headers=self.headers('dev-room-admin')).status_code,200)
        first=self.book(end=7)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.book(end=7).json()['id'],first.json()['id'])
        self.assertEqual(self.book(end=6).status_code,409)
        self.assertEqual(self.client.post('/api/v1/reservations',json=self.payload(),headers=self.headers()).status_code,422)

    def test_m103_concurrent_seat_and_user_conflicts(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda user:self.book(key=user,user=user),['dev-student-cs','dev-student-ee']))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        winner=next(r.json()['userId'] for r in results if r.status_code==200)
        self.assertEqual(self.book(key='other-seat',user=winner,seat='s2').status_code,409)

    def test_m103_half_open_boundary_and_cancel(self):
        first=self.book().json()
        self.assertEqual(self.book(key='adjacent',start=3,end=4).status_code,200)
        path='/api/v1/reservations/'+first['id']+'/cancel'
        self.assertEqual(self.client.post(path,headers=self.headers('dev-student-ee')).status_code,404)
        self.assertEqual(self.client.post(path,headers=self.headers()).status_code,200)
        self.assertEqual(self.client.post(path,headers=self.headers()).status_code,200)
        self.assertEqual(self.book(key='replacement').status_code,200)
        self.clock=BASE+timedelta(hours=2)
        replacement=self.client.get('/api/v1/reservations',headers=self.headers()).json()['items']
        current=next(r for r in replacement if r['startsAt']==self.payload()['startsAt'])
        self.assertEqual(self.client.post('/api/v1/reservations/'+current['id']+'/cancel',headers=self.headers()).status_code,409)

    def test_m104_owner_room_day_and_time_window(self):
        reservation=self.book().json()
        path='/api/v1/reservations/'+reservation['id']+'/check-in'
        code=checkin.daily_code('public',BASE)
        self.assertEqual(self.client.post(path,json={'code':code},headers=self.headers()).status_code,409)
        self.clock=BASE+timedelta(hours=2)
        self.assertEqual(self.client.post(path,json={'code':code},headers=self.headers('dev-student-ee')).status_code,404)
        for wrong in ['错误编码',checkin.daily_code('cs',self.clock),checkin.daily_code('public',self.clock-timedelta(days=1))]:
            self.assertEqual(self.client.post(path,json={'code':wrong},headers=self.headers()).status_code,422)
        response=self.client.post(path,json={'code':code},headers=self.headers())
        self.assertEqual(response.json()['status'],'CHECKED_IN')
        self.assertEqual(self.client.post(path,json={'code':code},headers=self.headers()).status_code,200)
        self.clock+=timedelta(minutes=15)
        self.assertEqual(self.client.post(path,json={'code':code},headers=self.headers()).status_code,409)

    def test_m104_deadline_rechecked_after_lock_wait(self):
        reservation=self.book().json()
        self.clock=BASE+timedelta(hours=2,minutes=14,seconds=59)
        original_lock=core.lock
        def delayed_lock(conn,*keys):
            original_lock(conn,*keys)
            self.clock+=timedelta(seconds=2)
        with patch.object(core,'lock',delayed_lock):
            result=self.client.post('/api/v1/reservations/'+reservation['id']+'/check-in',json={'code':checkin.daily_code('public',self.clock)},headers=self.headers())
        self.assertEqual(result.status_code,409)

    def test_m102_user_overlap_hides_unbookable_seats(self):
        self.book()
        self.assertEqual(self.search().json()['items'],[])

    def test_m104_code_permission_and_missing_secret(self):
        self.assertEqual(self.client.get('/api/v1/rooms/public/check-in-code',headers=self.headers()).status_code,403)
        self.assertEqual(self.client.get('/api/v1/rooms/public/check-in-code',headers=self.headers('dev-room-admin')).status_code,200)
        with patch.dict(os.environ,{'M1_CHECKIN_SECRET':''}):
            self.assertEqual(self.client.get('/api/v1/rooms/public/check-in-code',headers=self.headers('dev-room-admin')).status_code,503)

    def test_m105_exact_deadlines_restart_and_breach_idempotency(self):
        reservation=self.book().json()
        for minutes,expected in [(104,0),(105,1),(129,1),(130,2),(134,2),(135,3)]:
            self.clock=BASE+timedelta(minutes=minutes)
            scheduler.process_due();scheduler.process_due()
            with core.DB.connection() as conn:
                events=conn.execute("SELECT count(*) AS n FROM outbox WHERE kind='notification'").fetchone()['n']
            self.assertEqual(events,expected)
        with core.DB.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM breaches').fetchone()['n'],1)
        response=self.client.get('/api/v1/reservations/'+reservation['id'],headers=self.headers())
        self.assertEqual(response.json()['status'],'NO_SHOW')
        self.assertEqual(self.book(key='released',user='dev-student-ee',start=3,end=4).status_code,200)

    def test_m105_downtime_skips_obsolete_reminders(self):
        self.book()
        self.clock=BASE+timedelta(hours=4)
        self.assertEqual(scheduler.process_due(),1)
        with core.DB.connection() as conn:
            events=conn.execute("SELECT payload FROM outbox WHERE kind='notification'").fetchall()
        self.assertEqual([r['payload']['kind'] for r in events],['NO_SHOW'])

    def test_m105_expired_reservation_does_not_block_without_scheduler(self):
        self.book(end=5)
        self.clock=BASE+timedelta(hours=2,minutes=15)
        self.assertEqual(self.book(key='new',user='dev-student-ee',start=3,end=4).status_code,200)
        self.assertIn('public-s1',[item['id'] for item in self.search(startsAt=utc_text(BASE+timedelta(hours=4)),endsAt=utc_text(BASE+timedelta(hours=5))).json()['items']])

    def test_m105_outbox_retry_and_simulated_not_delivered(self):
        self.book()
        with patch.dict(os.environ,{'M1_DEV_DELIVERY_FAIL':'1'}):
            self.assertGreater(scheduler.flush_outbox()['failed'],0)
        with core.DB.connection() as conn:
            self.assertTrue(all(r['state']=='PENDING' for r in conn.execute('SELECT state FROM outbox').fetchall()))
        self.clock+=timedelta(seconds=10)
        self.assertGreater(scheduler.flush_outbox()['simulated'],0)
        with core.DB.connection() as conn:
            self.assertTrue(all(r['state']=='SIMULATED' for r in conn.execute('SELECT state FROM outbox').fetchall()))

    def test_m105_failed_reminder_is_suppressed_after_cancellation(self):
        reservation=self.book().json()
        self.clock=BASE+timedelta(hours=1,minutes=45)
        scheduler.process_due()
        with patch.dict(os.environ,{'M1_DEV_DELIVERY_FAIL':'1'}):
            scheduler.flush_outbox()
        self.client.post('/api/v1/reservations/'+reservation['id']+'/cancel',headers=self.headers())
        self.clock+=timedelta(seconds=10)
        result=scheduler.flush_outbox()
        self.assertEqual(result['suppressed'],1)
        with core.DB.connection() as conn:
            notification=conn.execute("SELECT * FROM outbox WHERE kind='notification'").fetchone()
            audits=conn.execute("SELECT state FROM outbox WHERE kind='audit'").fetchall()
        self.assertEqual(notification['state'],'SUPPRESSED')
        self.assertIsNotNone(notification['suppressed_at'])
        self.assertIsNone(notification['delivered_at'])
        self.assertTrue(all(row['state']=='SIMULATED' for row in audits))

    def test_m105_failed_reminders_expire_but_no_show_still_delivers(self):
        self.book()
        self.clock=BASE+timedelta(hours=1,minutes=45)
        scheduler.process_due()
        with patch.dict(os.environ,{'M1_DEV_DELIVERY_FAIL':'1'}):
            scheduler.flush_outbox()
        self.clock=BASE+timedelta(hours=2,minutes=10)
        scheduler.process_due()
        with patch.dict(os.environ,{'M1_DEV_DELIVERY_FAIL':'1'}):
            self.assertEqual(scheduler.flush_outbox()['suppressed'],1)
        self.clock=BASE+timedelta(hours=2,minutes=15)
        scheduler.process_due()
        self.assertEqual(scheduler.flush_outbox()['suppressed'],1)
        with core.DB.connection() as conn:
            events=conn.execute("SELECT payload,state FROM outbox WHERE kind='notification'").fetchall()
        self.assertEqual({row['payload']['kind']:row['state'] for row in events},
            {'BEFORE_START':'SUPPRESSED','CHECKIN_REMINDER':'SUPPRESSED','NO_SHOW':'SIMULATED'})

    def test_m105_failed_reminder_suppressed_after_checkin(self):
        reservation=self.book().json()
        self.clock=BASE+timedelta(hours=2,minutes=10)
        scheduler.process_due()
        with patch.dict(os.environ,{'M1_DEV_DELIVERY_FAIL':'1'}):
            scheduler.flush_outbox()
        result=self.client.post('/api/v1/reservations/'+reservation['id']+'/check-in',
            json={'code':checkin.daily_code('public',self.clock)},headers=self.headers())
        self.assertEqual(result.status_code,200)
        self.clock+=timedelta(seconds=10)
        self.assertEqual(scheduler.flush_outbox()['suppressed'],1)
        with core.DB.connection() as conn:
            self.assertEqual(conn.execute("SELECT state FROM outbox WHERE kind='notification'").fetchone()['state'],'SUPPRESSED')

    def test_m106_history_is_private_and_rebook_checks_current_rules(self):
        reservation=self.book().json()
        self.client.post('/api/v1/reservations/'+reservation['id']+'/cancel',headers=self.headers())
        self.assertEqual(self.client.get('/api/v1/reservations?scope=history',headers=self.headers()).json()['total'],1)
        self.assertEqual(self.client.get('/api/v1/reservations?scope=history',headers=self.headers('dev-student-ee')).json()['total'],0)
        self.rooms[0]['active']=False
        result=self.client.post('/api/v1/reservations/'+reservation['id']+'/rebook',json={'startsAt':self.payload()['startsAt'],'endsAt':self.payload()['endsAt']},headers=self.headers(key='rebook'))
        self.assertEqual(result.status_code,409)

    def test_m107_statistics_facts_and_permissions(self):
        self.book()
        cancelled=self.book(key='other',seat='s2',start=3,end=4).json()
        self.client.post('/api/v1/reservations/'+cancelled['id']+'/cancel',headers=self.headers())
        params={'startsAt':utc_text(BASE),'endsAt':utc_text(BASE+timedelta(hours=5))}
        self.assertEqual(self.client.get('/api/v1/operations',params=params,headers=self.headers()).status_code,403)
        result=self.client.get('/api/v1/operations',params=params,headers=self.headers('dev-operator')).json()
        self.assertEqual(result['totals'],{'reservations':2,'checkedIn':0,'cancelled':1,'noShows':0,'reservedHours':1.0})
        self.assertNotIn('userId',str(result))

    def test_m108_revision_tombstone_union_and_payload_identity(self):
        first=self.block()
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.block().json()['appliedAt'],first.json()['appliedAt'])
        self.assertEqual(self.block(status='RELEASED').status_code,409)
        self.assertEqual(self.block(key='second').status_code,200)
        self.assertEqual(self.block(revision=2,status='RELEASED').status_code,200)
        self.assertEqual(self.book().status_code,409)
        self.assertEqual(self.block().status_code,409)
        self.assertEqual(self.block(key='second',revision=2,status='RELEASED').status_code,200)
        self.assertEqual(self.book().status_code,200)
        self.assertEqual(self.block(key='tombstone',revision=3,status='RELEASED').status_code,200)
        self.assertEqual(self.block(key='tombstone',revision=2).status_code,409)

    def test_m108_m2_conflict_m3_retains_booking_and_provenance(self):
        booking=self.book().json()
        response=self.block(source='m2',endsAt=self.payload()['endsAt'])
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['code'],'ROOM_OCCUPANCY_CONFLICT')
        self.assertEqual(self.block().status_code,200)
        self.assertEqual(self.client.get('/api/v1/reservations/'+booking['id'],headers=self.headers()).json()['status'],'RESERVED')
        self.assertEqual(self.block(source='m2',key='later',startsAt=utc_text(BASE+timedelta(hours=3)),endsAt=utc_text(BASE+timedelta(hours=4))).status_code,200)
        result=self.client.get('/api/v1/rooms/public/provenance',headers=self.headers('dev-operator')).json()
        self.assertEqual({row['sourceSystem'] for row in result['items']},{'M1','M2','M3'})

    def test_m108_service_identity_and_invalid_interval(self):
        payload={'roomId':'public','revision':1,'status':'ACTIVE','startsAt':self.payload()['startsAt'],'endsAt':self.payload()['endsAt']}
        self.assertEqual(self.client.put('/internal/v1/room-blocks/m2/id',json=payload,headers={'Authorization':'Bearer test-m3'}).status_code,403)
        self.assertEqual(self.client.put('/internal/v1/room-blocks/m2/id',json=payload).status_code,401)
        self.assertEqual(self.block(endsAt=self.payload()['startsAt']).status_code,422)
        self.assertEqual(self.block(endsAt=None).status_code,422)
        self.assertEqual(self.block(roomId='missing').status_code,404)

    def test_real_identity_fails_closed_and_validates_shape(self):
        with patch.dict(os.environ,{'M1_USE_DEV_DEPENDENCIES':'0'}):
            with patch.object(dependencies,'request_d',side_effect=Problem(503,'DEPENDENCY_UNAVAILABLE','Unavailable')):
                self.assertEqual(self.search().status_code,503)
            with patch.object(dependencies,'request_d',return_value={'id':'student','permissions':['seat:reserve']}):
                self.assertEqual(self.search().status_code,503)
        with patch.dict(os.environ,{'APP_ENV':'production'}):
            self.assertEqual(self.search().status_code,503)

    def test_outbox_receipt_timestamp_is_not_delivery_timestamp(self):
        self.book()
        with patch.object(dependencies,'deliver',return_value='ACCEPTED'):
            self.assertGreater(scheduler.flush_outbox()['accepted'],0)
        with core.DB.connection() as conn:
            rows=conn.execute('SELECT * FROM outbox').fetchall()
        self.assertTrue(all(r['state']=='ACCEPTED' and r['acknowledged_at'] is not None and r['delivered_at'] is None for r in rows))

    def test_real_delivery_accepted_is_not_delivery(self):
        with patch.dict(os.environ,{'M1_USE_DEV_DEPENDENCIES':'0','D_NOTIFICATION_TOKEN':'test'}):
            with patch.object(dependencies,'request_d',return_value={'eventId':'event','status':'accepted'}):
                self.assertEqual(dependencies.deliver('notification',{'eventId':'event'}),'ACCEPTED')


if __name__=='__main__':
    unittest.main()
