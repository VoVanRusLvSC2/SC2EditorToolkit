"""Versioned local HTTP API over independently callable modules."""
import argparse,json,os,secrets,sys,threading,time,shutil
from pathlib import Path
from urllib.parse import quote
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .runtime import watch_frozen_parent
from .session import Worker
from .modules import capabilities

ROUTES={'/convert':'execute','/open':'open_document','/editor/start':'start','/triggers/compile':'compile_current',
 '/galaxy/export':'export_galaxy','/editor/diagnostics':'diagnostics','/cutscene/open':'cutscene_open','/cutscene/seek':'cutscene_seek',
 '/cutscene/export':'export_video','/cutscene/export/cancel':'cancel_video','/render/capture':'capture_frame'}

def main():
    watch_frozen_parent()
    p=argparse.ArgumentParser(description='SC2 Native Toolkit — hidden original Editor modules')
    p.add_argument('operation',nargs='?',choices=['serve','convert'],default='serve')
    base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]
    p.add_argument('--work',default=str(base/'api-data'));p.add_argument('--port',type=int,default=8765)
    p.add_argument('--request');p.add_argument('--response')
    args=p.parse_args();worker=Worker(args.work)
    if args.operation=='convert':
        try:
            if not args.request or not args.response:raise ValueError('--request and --response required')
            result=worker.execute(json.loads(Path(args.request).read_text(encoding='utf-8-sig')))
            Path(args.response).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            return 2 if result.get('status')=='FAILED' else 0
        except Exception as e:
            if args.response:Path(args.response).write_text(json.dumps({'status':'FAILED','error':str(e)}),encoding='utf8')
            return 2
        finally:worker.close()
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*values):
            with (worker.work/'http.log').open('a',encoding='utf8') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%S')+' '+fmt%values+'\n')
        def reply(self,code,value):
            data=json.dumps(value,ensure_ascii=False).encode('utf8');self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def authorized(self):
            return not self.headers.get('Origin') and secrets.compare_digest(self.headers.get('X-SC2-Token',''),token)
        def do_GET(self):
            if self.path=='/health':self.reply(200,{'ok':True,'version':'0.5.0','workerRunning':worker.alive(),'busy':worker.lock.locked()});return
            if not self.authorized():self.reply(403,{'error':'X-SC2-Token required; browser origins are not accepted'});return
            if self.path=='/modules':self.reply(200,capabilities());return
            if self.path=='/cutscene/export/status':self.reply(200,worker.export_video_status());return
            if self.path.startswith('/artifacts/'):
                try:
                    item=worker.artifacts.get(self.path[len('/artifacts/'):]);path=Path(item['path'])
                    self.send_response(200);self.send_header('Content-Type',item['mime']);self.send_header('Content-Length',str(path.stat().st_size))
                    self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(Path(item['path']).name,safe=''))
                    self.send_header('X-Content-SHA256',item['sha256']);self.end_headers()
                    with path.open('rb') as incoming:shutil.copyfileobj(incoming,self.wfile,1024**2)
                except KeyError:self.reply(404,{'error':'Unknown artifact'})
                except Exception as e:self.reply(409,{'error':str(e)})
                return
            self.reply(404,{'error':'Unknown endpoint'})
        def do_POST(self):
            if not self.authorized():self.reply(403,{'error':'X-SC2-Token required; browser origins are not accepted'});return
            if self.path=='/shutdown':
                if worker.lock.locked():self.reply(409,{'error':'Worker busy'});return
                self.reply(200,{'ok':True});threading.Thread(target=server.shutdown,daemon=True).start();return
            if self.path not in ROUTES:self.reply(404,{'error':'Unknown endpoint'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=80*1024**2:raise ValueError('Body must be 1 byte to 80 MiB')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict):raise ValueError('JSON object required')
                result=getattr(worker,ROUTES[self.path])(request)
                self.reply(422 if result.get('status')=='FAILED' else 200,result)
            except FileExistsError:self.reply(409,{'status':'FAILED','error':'Export target exists; use another path or overwrite=true'})
            except Exception as e:self.reply(409 if worker.lock.locked() else 400,{'status':'FAILED','error':str(e)})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    (worker.work/'api-info.json').write_text(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','token':token,'pid':os.getpid(),'version':'0.5.0'},indent=2),encoding='utf8')
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close();worker.close()
    return 0
