import io
import json
import socket
import struct
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.http_transport import LocalHTTPHandler


class BrokenWriter:
    def __init__(self,error,fail_at):self.error=error;self.fail_at=fail_at;self.calls=0
    def write(self,data):
        self.calls+=1
        if self.calls==self.fail_at:raise self.error
        return len(data)


class TransportTests(unittest.TestCase):
    def handler(self,writer):
        h=object.__new__(LocalHTTPHandler)
        h.wfile=writer;h.request_version='HTTP/1.1';h.requestline='POST /test HTTP/1.1'
        h.command='POST';h.log_request=lambda *args:None;h.close_connection=False
        return h

    def test_json_disconnect_during_headers_or_body_never_replies_twice(self):
        for error in (BrokenPipeError(),ConnectionResetError(),ConnectionAbortedError(10053,'aborted')):
            for fail_at in (1,2):
                with self.subTest(error=type(error).__name__,fail_at=fail_at):
                    writer=BrokenWriter(error,fail_at);h=self.handler(writer)
                    self.assertFalse(h.reply(200,{'completed':True}))
                    self.assertTrue(h.close_connection)
                    count=writer.calls
                    self.assertFalse(h.reply(400,{'error':'must not be sent'}))
                    self.assertEqual(writer.calls,count)

    def test_artifact_disconnect_during_headers_or_body(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'image.png';path.write_bytes(b'original artifact')
            item={'path':str(path),'mime':'image/png','sha256':'test'}
            for fail_at in (1,2):
                h=self.handler(BrokenWriter(ConnectionAbortedError(10053,'aborted'),fail_at))
                self.assertFalse(h.send_artifact(item));self.assertTrue(h.close_connection)
                self.assertEqual(path.read_bytes(),b'original artifact')

    def test_non_connection_errors_remain_visible(self):
        h=self.handler(BrokenWriter(OSError(28,'disk full'),1))
        with self.assertRaises(OSError):h.reply(200,{'completed':True})
        h=self.handler(io.BytesIO())
        with self.assertRaises(FileNotFoundError):h.send_artifact({'path':'missing/never-created'})
        self.assertFalse(getattr(h,'_response_started',False))

    def test_real_aborted_posts_leave_service_usable_without_replaying_work(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event()
        completed=[];errors=[]
        class Handler(LocalHTTPHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                entered.set();release.wait(5)
                completed.append('original result')
                self.reply(200,{'result':'x'*1024**2});finished.set()
            def do_GET(self):self.reply(200,{'ok':True,'completed':len(completed)})
        class Server(ThreadingHTTPServer):
            def handle_error(self,*args):errors.append(sys.exc_info()[1])
        server=Server(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True);thread.start()
        try:
            for _ in range(3):
                entered.clear();release.clear();finished.clear()
                client=socket.create_connection(server.server_address,timeout=5)
                client.sendall(b'POST /test HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}')
                self.assertTrue(entered.wait(5))
                linger=struct.pack('HH',1,0) if sys.platform=='win32' else struct.pack('ii',1,0)
                client.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,linger);client.close()
                release.set();self.assertTrue(finished.wait(5))
            with urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+'/health',timeout=5) as response:
                self.assertEqual(json.load(response),{'ok':True,'completed':3})
            self.assertEqual(errors,[]);self.assertEqual(len(completed),3)
        finally:
            release.set();server.shutdown();server.server_close();thread.join(5)
