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
from services.m1 import core,dependencies
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
        self.assertEqual(self.client.get('/api/v1/seats',params=self.payload()).status_code,401)


    def test_m102_socket_inactive_and_closed_room_filters(self):
        self.assertTrue(all(i['hasSocket'] for i in self.search(hasSocket='true').json()['items']))
        self.rooms[0]['seats'][0]['active']=False
        self.rooms[1]['active']=False
        self.assertEqual([i['id'] for i in self.search().json()['items']],['public-s2'])
        self.assertEqual(self.search(startsAt=utc_text(BASE+timedelta(hours=15)),endsAt=utc_text(BASE+timedelta(hours=16))).json()['items'],[])


    def test_real_identity_fails_closed_and_validates_shape(self):
        with patch.dict(os.environ,{'M1_USE_DEV_DEPENDENCIES':'0'}):
            with patch.object(dependencies,'request_d',side_effect=Problem(503,'DEPENDENCY_UNAVAILABLE','Unavailable')):
                self.assertEqual(self.search().status_code,503)
            with patch.object(dependencies,'request_d',return_value={'id':'student','permissions':['seat:reserve']}):
                self.assertEqual(self.search().status_code,503)
        with patch.dict(os.environ,{'APP_ENV':'production'}):
            self.assertEqual(self.search().status_code,503)


if __name__=='__main__':
    unittest.main()
