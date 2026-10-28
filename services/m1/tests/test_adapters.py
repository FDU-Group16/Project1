"""D wire-boundary tests use no database and no real identity provider."""
import copy
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Thread
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from services.m1 import core,dependencies
from services.m1.main import app
from services.platform import Problem

ROOM={'id':'room','name':'Room','departmentId':None,'openHour':8,'closeHour':22,
      'weekdays':[0,1,2,3,4],'active':True,'retired':False,
      'seats':[{'id':'seat','roomId':'room','number':'01','hasSocket':True,'active':True,'retired':False}]}


@contextmanager
def http_provider(*, raw=None, body=b'{}', status=200):
    """Serve real HTTP, including intentionally broken wire responses."""
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.command,self.path))
            if raw is not None:
                self.wfile.write(raw)
            else:
                self.send_response(status)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            self.close_connection=True
        do_POST=do_GET
        def log_message(self,*args):
            pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=lambda:server.serve_forever(poll_interval=0.01),daemon=True)
    thread.start()
    try:
        with patch.dict(os.environ,{'D_BASE_URL':f'http://127.0.0.1:{server.server_port}'}):
            yield requests
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


class HttpFailureBoundary(unittest.TestCase):
    def test_broken_provider_returns_public_503_problem_details(self):
        cases={
            'truncated':{'raw':b'HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n{"id":"partial'},
            'invalid-status':{'raw':b'not-an-http-status\r\n\r\n'},
            'disconnected':{'raw':b''},
            'invalid-json':{'body':b'{"id":'},
            'non-object':{'body':b'[]'},
        }
        with patch.dict(os.environ,{'M1_USE_DEV_DEPENDENCIES':'0','M1_DATABASE_URL':''}):
            with TestClient(app,raise_server_exceptions=False) as client:
                for name,response in cases.items():
                    with self.subTest(response=name),http_provider(**response) as requests:
                        result=client.get('/api/v1/settings',headers={'Authorization':'Bearer synthetic-review-token'})
                        self.assertEqual(result.status_code,503)
                        self.assertEqual(result.headers['content-type'],'application/problem+json')
                        self.assertEqual(result.json()['code'],'DEPENDENCY_UNAVAILABLE')
                        self.assertEqual(result.json()['status'],503)
                        self.assertNotIn('synthetic-review-token',result.text)
                        self.assertNotIn('partial',result.text)
                        self.assertEqual(requests,[('GET','/api/v1/auth/me')])

    def test_post_truncated_delivery_response_is_unavailable(self):
        with http_provider(raw=b'HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n{"eventId":') as requests:
            with self.assertRaises(Problem) as failure:
                dependencies.request_d('/internal/v1/notifications','synthetic-token',{'eventId':'synthetic-event'})
            self.assertEqual((failure.exception.status,failure.exception.code),(503,'DEPENDENCY_UNAVAILABLE'))
            self.assertEqual(requests,[('POST','/internal/v1/notifications')])

    def test_valid_responses_and_http_error_mapping_remain_compatible(self):
        with http_provider(body=b'{"id":"synthetic-user"}'):
            self.assertEqual(dependencies.request_d('/api/v1/auth/me','synthetic-token'),{'id':'synthetic-user'})
        cases=[(401,'/api/v1/auth/me',401,'DEPENDENCY_AUTH_REJECTED'),
               (403,'/api/v1/auth/me',403,'DEPENDENCY_AUTH_REJECTED'),
               (404,'/internal/v1/rooms/missing',404,'ROOM_NOT_FOUND'),
               (404,'/api/v1/auth/me',503,'DEPENDENCY_UNAVAILABLE'),
               (500,'/api/v1/auth/me',503,'DEPENDENCY_UNAVAILABLE')]
        for status,path,expected,code in cases:
            with self.subTest(status=status,path=path),http_provider(status=status):
                with self.assertRaises(Problem) as failure:
                    dependencies.request_d(path,'synthetic-token')
                self.assertEqual((failure.exception.status,failure.exception.code),(expected,code))


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
