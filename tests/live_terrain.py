"""Opt-in HTTP test of Triggers startup and original Terrain PNG, no input."""
import argparse,hashlib,json,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--work',required=True)
 p.add_argument('--package',action='store_true');p.add_argument('--autostart',action='store_true');a=p.parse_args()
 root=Path(__file__).resolve().parents[1];work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
 source=Path(a.map).resolve();digest=hashlib.sha256(source.read_bytes()).hexdigest()
 command=[str(root/'dist'/'SC2NativeAPI.exe')] if a.package else [sys.executable,str(root/'app'/'hidden_api.py')]
 proc=subprocess.Popen(command+['serve','--work',str(work/'runtime'),'--port','0'],creationflags=subprocess.CREATE_NO_WINDOW,
  stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'));info=None;pid=None
 def call(route,body=None):
  request=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'X-SC2-Token':info['token'],'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(request,timeout=1200) as response:return json.load(response)
  except urllib.error.HTTPError as e:raise RuntimeError(str(e)+': '+e.read().decode()) from e
 def save(name,data):(work/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
 try:
  until=time.monotonic()+30
  while not (work/'runtime'/'api-info.json').is_file():
   if proc.poll() is not None or time.monotonic()>until:raise RuntimeError('API startup failed')
   time.sleep(.1)
  info=json.loads((work/'runtime'/'api-info.json').read_text())
  print('Autostart and Terrain capture' if a.autostart else 'Opening original document in Triggers',flush=True)
  first=None
  if a.autostart:first=call('/terrain/capture',{'map':str(source),'output':str(work/'Terrain.png')})
  else:
   started=call('/editor/start',{'template':str(source),'startup_module':'triggers'});save('start',started)
  state=json.loads((work/'runtime'/'worker.json').read_text());pid=state['pid'];startup=json.loads(Path(state['startupReport']).read_text())
  assert startup['status']=='HIDDEN_EDITOR_READY' and startup['readyModule']=='Triggers',startup
  assert not any(w['title'].startswith('Terrain - [') for w in startup['windows']),startup
  print('Triggers-only readiness confirmed; capturing Terrain',flush=True)
  results=[]
  for name in ('Terrain','TerrainRepeat'):
   result=first if name=='Terrain' and first else call('/terrain/capture',{'output':str(work/(name+'.png'))});save(name,result);results.append(result)
   assert result['status']=='TERRAIN_FRAME_CAPTURED' and result['requestedTerrainFrameVerified'],result
   assert result['native']['sourceWindow']==result['terrain']['viewport'] and result['imageHasDetail'] and not result['emptyFrame'],result
   assert result['sourceUnchanged'] and not result['timelineControl'] and not result['requestedCutsceneFrameVerified'],result
   observed=result['desktopObservation'];assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples'],observed
   with urllib.request.urlopen(urllib.request.Request(info['url']+result['artifact']['download'],headers={'X-SC2-Token':info['token']}),timeout=30) as response:
    assert hashlib.sha256(response.read()).hexdigest()==result['artifact']['sha256']
  try:call('/terrain/capture',{'output':str(work/'Terrain.png')})
  except RuntimeError as error:assert 'target exists' in str(error).lower() or 'file exists' in str(error).lower(),str(error)
  else:raise AssertionError('Existing PNG overwritten without permission')
  assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
  save('VERIFICATION',{'status':'TRIGGERS_STARTUP_AND_TERRAIN_BACKGROUND_PASSED','readyModule':startup['readyModule'],'terrainWindowDuringStartup':False,
   'captures':len(results),'autostart':a.autostart,'sourceUnchanged':True,'desktopObservation':results[-1]['desktopObservation'],'editorPid':pid})
  print('Original Terrain PNG and repeat capture passed',flush=True)
 finally:
  if info:
   try:call('/shutdown',{})
   except Exception:pass
  try:proc.wait(timeout=15)
  except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=15)
 return 0
if __name__=='__main__':raise SystemExit(main())
