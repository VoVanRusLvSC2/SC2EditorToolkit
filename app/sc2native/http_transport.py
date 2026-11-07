"""Loopback responses that tolerate clients leaving during long native jobs."""
import json
import os
import shutil
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote


class LocalHTTPHandler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        self._response_started=False
        try:return super().handle_one_request()
        except ConnectionError:
            # A disconnected HTTP client does not invalidate a completed job.
            # Do not send an error response into the same closed connection.
            self.close_connection=True

    def reply(self,code,value):
        if getattr(self,'_response_started',False):
            self.close_connection=True
            return False
        data=json.dumps(value,ensure_ascii=False).encode('utf8')
        try:
            self._response_started=True
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(data)
            return True
        except ConnectionError:
            self.close_connection=True
            return False

    def send_artifact(self,item):
        path=Path(item['path'])
        # Resolve/read metadata before committing the success headers.
        with path.open('rb') as incoming:
            size=os.fstat(incoming.fileno()).st_size
            try:
                self._response_started=True
                self.send_response(200)
                self.send_header('Content-Type',item['mime'])
                self.send_header('Content-Length',str(size))
                self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name,safe=''))
                self.send_header('X-Content-SHA256',item['sha256'])
                self.end_headers()
                shutil.copyfileobj(incoming,self.wfile,1024**2)
                return True
            except ConnectionError:
                self.close_connection=True
                return False
