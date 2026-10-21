"""Opt-in acceptance of a known startup failure, never native compile acceptance."""
import argparse,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--work',required=True)
p.add_argument('--expected-win32',required=True);a=p.parse_args()
work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);info=None
proc=subprocess.Popen([str(root/'dist/SC2NativeAPI.exe'),'serve','--port','0','--work',str(work/'runtime')],
 creationflags=subprocess.CREATE_NO_WINDOW,stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'))
def call(route,body=None):
 req=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'X-SC2-Token':info['token'],'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=300) as response:code=response.status;result=json.load(response)
 except urllib.error.HTTPError as error:code=error.code;result=json.load(error)
 (work/(route.strip('/').replace('/','-')+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
 print(route,code,result.get('failureKind'),flush=True);return code,result
try:
 until=time.monotonic()+45
 while not (work/'runtime/api-info.json').exists():assert proc.poll() is None and time.monotonic()<until;time.sleep(.1)
 info=json.loads((work/'runtime/api-info.json').read_text())
 code,result=call('/editor/start',{'template':str(Path(a.template).resolve())})
 assert code==422 and result['failureKind']=='NATIVE_CONTROLLER_FAILED' and result['ownedWorkerReset']
 assert 'Win32='+a.expected_win32 in result['error']
 assert result['failureNative']['controllerExitCode']==2 and result['automaticRetry'] is False
 observed=result['desktopObservation'];assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
 assert not call('/health')[1]['workerRunning'] and call('/galaxy/export',{})[0]==400
 (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_STARTUP_FAILURE_HANDLED','expectedWin32':a.expected_win32,
  'packaged':True,'ownedWorkerReset':True,'staleExportRefused':True,'nativeGenerationVerified':False,
  'nativeCompilationTested':False,'desktopObservation':observed},indent=2),encoding='utf8')
finally:
 if info:call('/shutdown',{})
 proc.wait(timeout=30)
