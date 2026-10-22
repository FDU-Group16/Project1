"""D wire-boundary tests use no database and no real identity provider."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Thread
import unittest
from unittest.mock import patch
from services.m1 import core,dependencies
from services.platform import Problem

ROOM={'id':'room','name':'Room','departmentId':None,'openHour':8,'closeHour':22,
      'weekdays':[0,1,2,3,4],'active':True,'retired':False,
      'seats':[{'id':'seat','roomId':'room','number':'01','hasSocket':True,'active':True,'retired':False}]}


class AdapterBoundary(unittest.TestCase):
    def rejected(self,payload,detail=False):
        with patch.object(dependencies,'request_d',return_value=payload):
            with self.assertRaises(Problem) as failure:
                dependencies.room('room') if detail else dependencies.rooms()
        self.assertEqual((failure.exception.status,failure.exception.code),(503,'INVALID_MASTER_DATA'))

    def test_strict_required_room_and_seat_fields(self):
        for field in ROOM:
            value=copy.deepcopy(ROOM);del value[field]
            with self.subTest(missing_room=field):
                self.rejected(value,True)
        for field in ROOM['seats'][0]:
            value=copy.deepcopy(ROOM);del value['seats'][0][field]
            with self.subTest(missing_seat=field):
                self.rejected({'items':[value]})
        with self.assertRaises(Problem) as failure:
            core.authorized_room({'id':'unscoped'},{'id':'student','departmentId':None})
        self.assertEqual(failure.exception.status,503)

    def test_strict_types_and_opening_constraints(self):
        bad=[('id',''),('name','  '),('departmentId',''),('departmentId',False),
             ('openHour','8'),('openHour',True),('openHour',24),('closeHour',0),
             ('closeHour',8),('weekdays',[]),('weekdays',[1,1]),('weekdays',[7]),
             ('weekdays',[True]),('weekdays',['1']),('active','false'),('active',0),
             ('retired','false'),('seats',{}),('seats',[None])]
        for field,value in bad:
            room=copy.deepcopy(ROOM);room[field]=value
            with self.subTest(field=field,value=value):
                self.rejected({'items':[room]})
        for field,value in [('id',''),('number',''),('hasSocket','false'),('active','false'),('retired',1),('roomId','other')]:
            room=copy.deepcopy(ROOM);room['seats'][0][field]=value
            with self.subTest(seat_field=field,value=value):
                self.rejected(room,True)

    def test_ids_seat_numbers_and_requested_room_must_match(self):
        self.rejected({'items':[ROOM,ROOM]})
        room=copy.deepcopy(ROOM);room['seats'].append(copy.deepcopy(room['seats'][0]))
        self.rejected(room,True)
        room['seats'][1]['id']='another-seat'
        self.rejected(room,True)
        other=copy.deepcopy(ROOM);other['id']='other';other['seats'][0]['roomId']='other'
        self.rejected({'items':[ROOM,other]})
        room=copy.deepcopy(ROOM);room['id']='other';room['seats'][0]['roomId']='other'
        self.rejected(room,True)

    def test_retirement_flags_and_additive_compatibility(self):
        room=copy.deepcopy(ROOM);room['retired']=True
        self.rejected(room,True)
        room=copy.deepcopy(ROOM);room['seats'][0]['retired']=True
        self.rejected(room,True)
        room=copy.deepcopy(ROOM);room['futureField']='safe addition'
        with patch.object(dependencies,'request_d',return_value=room):
            self.assertEqual(dependencies.room('room'),ROOM)
        with patch.object(dependencies,'request_d',return_value={'items':[room],'futureField':'addition'}):
            self.assertEqual(dependencies.rooms(),[ROOM])
        self.rejected({'items':'wrong'})
        self.rejected({})
        self.rejected({'items':[None]})

    def test_request_d_never_follows_redirect_or_forwards_credentials(self):
        sink_requests=[]
        redirects=[]
        class Sink(BaseHTTPRequestHandler):
            def do_GET(self):
                sink_requests.append(bool(self.headers.get('Authorization')))
                self.send_response(200);self.end_headers();self.wfile.write(b'{}')
            do_POST=do_GET
            def log_message(self,*args):
                pass
        sink=ThreadingHTTPServer(('127.0.0.1',0),Sink)
        target=f'http://127.0.0.1:{sink.server_port}/credential-sink'
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                redirects.append(bool(self.headers.get('Authorization')))
                self.send_response(int(self.path.strip('/')))
                self.send_header('Location',target);self.end_headers()
            do_POST=do_GET
            def log_message(self,*args):
                pass
        source=ThreadingHTTPServer(('127.0.0.1',0),Redirect)
        threads=[Thread(target=server.serve_forever,daemon=True) for server in (sink,source)]
        for thread in threads:
            thread.start()
        try:
            with patch.dict(os.environ,{'D_BASE_URL':f'http://127.0.0.1:{source.server_port}'}):
                for code in (301,302,303,307,308):
                    for payload in (None,{'eventId':'synthetic-event'}):
                        with self.subTest(code=code,method='GET' if payload is None else 'POST'):
                            with self.assertRaises(Problem) as failure:
                                dependencies.request_d('/'+str(code),'synthetic-secret',payload)
                            self.assertEqual(failure.exception.status,503)
            self.assertEqual(len(redirects),10)
            self.assertTrue(all(redirects))
            self.assertEqual(sink_requests,[])
        finally:
            for server in (sink,source):
                server.shutdown();server.server_close()
            for thread in threads:
                thread.join(timeout=2)


if __name__=='__main__':
    unittest.main()
