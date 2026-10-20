"""Opt-in original saved-map camera selection/readback/PNG regression."""
import argparse,hashlib,json,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--work',required=True)
p.add_argument('--camera-a',required=True);p.add_argument('--camera-b',required=True);p.add_argument('--package',action='store_true');a=p.parse_args()
source=Path(a.map).resolve();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest();before=sha(source)
work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);info=None;records=[]
command=[str(root/'dist/SC2NativeAPI.exe')] if a.package else [sys.executable,str(root/'app/hidden_api.py')]
proc=subprocess.Popen(command+['serve','--port','0','--work',str(work/'runtime')],creationflags=subprocess.CREATE_NO_WINDOW,
    stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'))
def call(route,body=None):
    request=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json','X-SC2-Token':info['token']})
    try:
        with urllib.request.urlopen(request,timeout=1200) as response:code=response.status;value=json.load(response)
    except urllib.error.HTTPError as error:code=error.code;value=json.load(error)
    records.append({'route':route,'http':code,'result':value});(work/('response-%02d.json'%len(records))).write_text(json.dumps(records[-1],indent=2),encoding='utf8')
    print(route,code,value.get('status'),value.get('error'),flush=True);return code,value
try:
    until=time.monotonic()+45
    while not (work/'runtime/api-info.json').exists():
        assert proc.poll() is None and time.monotonic()<until,'API startup failed'
        time.sleep(.1)
    info=json.loads((work/'runtime/api-info.json').read_text())
    code,listed=call('/terrain/cameras',{'map':str(source)});assert code==200 and listed['sourceUnchanged'] and not listed['editorRequired']
    cameras={c['cameraId']:c for c in listed['cameras']};assert a.camera_a in cameras and a.camera_b in cameras
    code,bad=call('/terrain/capture',{'map':str(source),'map_camera_id':'__nonexistent_camera__'})
    assert code==400 and not call('/health')[1]['workerRunning']
    frames=[]
    for index,ident in enumerate([a.camera_a,a.camera_b,a.camera_a]):
        request={'map_camera_id':ident,'output':str(work/('Camera%d.png'%index))}
        if not frames:request['map']=str(source)
        code,result=call('/terrain/capture',request);assert code==200 and result['status']=='TERRAIN_FRAME_CAPTURED',result
        assert result['requestedTerrainFrameVerified'] and result['imageHasDetail'] and not result['emptyFrame']
        assert result['mapCamera']['nativeSelectionVerified'] and not result['mapCamera']['triggerExecution'] and not result['timelineControl']
        actual=result['mapCamera']['actual'];assert actual['selected'] and actual['valuesRead']
        assert all(abs(actual['target'][axis]-cameras[ident]['target'][axis])<=.02 for axis in ['x','y'])
        observed=result['desktopObservation'];assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
        assert not observed['inputInjectionUsed'] and not observed['desktopSwitchApiUsed']
        request=urllib.request.Request(info['url']+result['artifact']['download'],headers={'X-SC2-Token':info['token']})
        with urllib.request.urlopen(request,timeout=30) as response:assert hashlib.sha256(response.read()).hexdigest()==sha(work/('Camera%d.png'%index))
        frames.append(result)
    assert frames[0]['artifact']['sha256']!=frames[1]['artifact']['sha256']
    code,compiled=call('/triggers/compile',{});assert compiled['nativeCompilePassed'] and code==200,compiled.get('error')
    assert sha(source)==before
    (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_MAP_CAMERAS_PASSED','package':a.package,'captures':3,
        'nativeCameraReadback':True,'sourceUnchanged':True,'nativeCompilePassed':True,'triggerPlaybackTested':False,
        'desktopObservation':compiled['desktopObservation']},indent=2),encoding='utf8')
finally:
    if info:call('/shutdown',{})
    proc.wait(timeout=30)
