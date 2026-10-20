"""Opt-in end-to-end original-Editor cutscene test. Never controls visible editors."""
import argparse,hashlib,json,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--scene',required=True)
    p.add_argument('--camera',required=True);p.add_argument('--other-camera',default='Top');p.add_argument('--work',required=True)
    p.add_argument('--package',action='store_true');p.add_argument('--compile-after',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False)
    source=Path(args.scene).resolve();template=Path(args.template).resolve()
    hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (source,template)}
    command=[str(root/'dist'/'SC2NativeAPI.exe')] if args.package else [sys.executable,str(root/'app'/'hidden_api.py')]
    proc=subprocess.Popen(command+['serve','--port','0','--work',str(work/'runtime')],stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'),creationflags=subprocess.CREATE_NO_WINDOW)
    info=None;pid=None;results=[]
    def call(route,body,timeout=900):
        request=urllib.request.Request(info['url']+route,json.dumps(body).encode(),{'X-SC2-Token':info['token'],'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=timeout) as response:return json.load(response)
    def save(name,data):
        (work/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    try:
        until=time.monotonic()+30
        while not (work/'runtime'/'api-info.json').is_file():
            if proc.poll() is not None or time.monotonic()>until:raise RuntimeError('API failed to start')
            time.sleep(.1)
        info=json.loads((work/'runtime'/'api-info.json').read_text())
        opened=call('/cutscene/open',{'template':str(template),'scene':str(source)});save('open',opened)
        assert opened['status']=='CUTSCENE_LOADED' and opened['sourceUnchanged'],opened
        pid=opened['native']['pid'];print('Original hidden scene loaded',flush=True)
        for index,(camera,stamp) in enumerate(((args.camera,990),(args.camera,1980),(args.camera,2970),(args.other_camera,1980))):
            frame=call('/render/capture',{'camera':camera,'time_ms':stamp});save('frame-'+str(index),frame)
            assert frame['requestedCutsceneFrameVerified'] and not frame['emptyFrame'] and frame['imageHasDetail'],frame
            observation=frame['desktopObservation']
            assert observation['visibleWindowsOnUserDesktopPeak']==0 and observation['editorForegroundSamples']==0,observation
            assert abs(frame['frame']['actualTimeMs']-stamp)<=21,frame
            results.append(frame);print('Frame',index,camera,stamp,frame['native']['width'],frame['native']['height'],frame['native']['nonBlackPixels'],flush=True)
        assert len({r['artifact']['sha256'] for r in results[:3]})>=2,'Time selection did not change rendered animation'
        assert results[1]['artifact']['sha256']!=results[3]['artifact']['sha256'],'Camera selection did not change image'
        try:call('/cutscene/seek',{'camera':'__missing_camera__','time_ms':0});raise AssertionError('Missing camera accepted')
        except urllib.error.HTTPError as e:assert e.code==400
        if args.compile_after:
            compiled=call('/triggers/compile',{});save('compile-after', {k:v for k,v in compiled.items() if k!='galaxy'})
            assert compiled['nativeCompilePassed'] and compiled['nativeGenerationVerified'],compiled
            print('Original trigger compile after cutscene passed',flush=True)
        assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items()),'User source changed'
        save('VERIFICATION',{'status':'NATIVE_CUTSCENE_BACKGROUND_PASSED','frames':[{'camera':r['frame']['camera'],'actualTimeMs':r['frame']['actualTimeMs'],'sha256':r['artifact']['sha256'],'png':r['artifact']['path']} for r in results],
            'sourceUnchanged':True,'mapUnchanged':True,'desktopObservation':results[-1]['desktopObservation'],'editorPid':pid})
        print('Full native cutscene cycle passed',flush=True)
    finally:
        if info:
            try:call('/shutdown',{},timeout=10)
            except Exception:pass
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=15)
    return 0
if __name__=='__main__':raise SystemExit(main())
