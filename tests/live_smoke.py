"""Opt-in real Editor test; all UI belongs to the private worker desktop."""
import argparse,json,subprocess,sys,time,urllib.request,urllib.error,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--work',required=True);p.add_argument('--scope',default='library:810D62ED');p.add_argument('--package',action='store_true');args=p.parse_args()
work=Path(args.work);work.mkdir(parents=True,exist_ok=False)
command=[str(root/'dist'/'SC2NativeAPI.exe')] if args.package else [sys.executable,str(root/'app'/'hidden_api.py')]
command+=['serve','--port','18771','--work',str(work)]
process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW,stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'))
for _ in range(300):
    if (work/'api-info.json').exists():break
    if process.poll() is not None:raise RuntimeError('Server exited before startup')
    time.sleep(.1)
info=json.loads((work/'api-info.json').read_text())
def call(path,data):
    req=urllib.request.Request(info['url']+path,data=json.dumps(data).encode('utf8'),headers={'Content-Type':'application/json','X-SC2-Token':info['token']})
    started=time.time()
    try:
        with urllib.request.urlopen(req,timeout=1200) as response:result=json.load(response)
    except urllib.error.HTTPError as e:result=json.load(e)
    (work/(path.strip('/').replace('/','-')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'path':path,'seconds':round(time.time()-started,1),'status':result.get('status'),'error':result.get('error')}),flush=True)
    return result
try:
    started=call('/editor/start',{'template':args.template});assert started['status']=='HIDDEN_EDITOR_STARTED'
    compiled=call('/triggers/compile',{'scope':args.scope});assert compiled['nativeCompilePassed']
    exported=call('/galaxy/export',{'output':str(work/'Exported.galaxy')});assert exported['status']=='GALAXY_EXPORTED'
    assert hashlib.sha256((work/'Exported.galaxy').read_bytes()).hexdigest()==compiled['sourceSha256']
    duplicate=call('/galaxy/export',{'output':str(work/'Exported.galaxy')});assert duplicate['status']=='FAILED'
    req=urllib.request.Request(info['url']+exported['artifact']['download'],headers={'X-SC2-Token':info['token']})
    with urllib.request.urlopen(req,timeout=10) as response:assert response.read()==(work/'Exported.galaxy').read_bytes()
    diagnostic=call('/editor/diagnostics',{});assert diagnostic['status']=='EDITOR_DIAGNOSTICS_READ'
    frame=call('/render/capture',{})
    cutscene=call('/cutscene/open',{})
    if cutscene.get('status')!='FAILED':call('/render/capture',{})
    (work/'VERIFICATION.json').write_text(json.dumps({'status':'LIVE_CORE_PASSED','nativeCompilePassed':True,'exportByteIdentity':True,'frameStatus':frame.get('status'),'cutsceneStatus':cutscene.get('status'),'editorLog':compiled.get('diagnostics',{}).get('editorLog')},ensure_ascii=False,indent=2),encoding='utf8')
finally:
    call('/shutdown',{});process.wait(timeout=30)
