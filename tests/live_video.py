"""Opt-in native full-scene/range/cancel MP4 validation, always on a hidden copy."""
import os
import argparse,concurrent.futures,hashlib,json,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--scene',required=True)
    p.add_argument('--camera',required=True);p.add_argument('--work',required=True);p.add_argument('--package',action='store_true');p.add_argument('--smoke',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
    sources=[Path(a.template).resolve(),Path(a.scene).resolve()];hashes=[hashlib.sha256(f.read_bytes()).hexdigest() for f in sources]
    cmd=[str(root/os.environ.get('SC2_PACKAGE_DIR','dist')/'SC2NativeAPI.exe')] if a.package else [sys.executable,str(root/'app'/'hidden_api.py')]
    proc=subprocess.Popen(cmd+['serve','--work',str(work/'runtime'),'--port','0'],creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'))
    info=None
    def call(route,body=None):
        request=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'X-SC2-Token':info['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=3600) as response:return json.load(response)
        except urllib.error.HTTPError as error:raise RuntimeError(str(error)+': '+error.read().decode()) from error
    def save(name,data):(work/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    try:
        until=time.monotonic()+30
        while not (work/'runtime'/'api-info.json').is_file():
            if proc.poll() is not None or time.monotonic()>until:raise RuntimeError('API did not start')
            time.sleep(.1)
        info=json.loads((work/'runtime'/'api-info.json').read_text())
        with concurrent.futures.ThreadPoolExecutor() as pool:
            initial={'template':str(sources[0]),'scene':str(sources[1]),'camera':a.camera,'output':str(work/'FullScene.mp4')}
            if a.smoke:initial.update(start_ms=990,end_ms=1320,fps=15)
            task=pool.submit(call,'/cutscene/export',initial)
            last=-1
            while not task.done():
                state=call('/cutscene/export/status')
                if state.get('framesDone',0)//20!=last:
                    last=state.get('framesDone',0)//20;print('Full scene:',state.get('stage'),state.get('framesDone'),state.get('frameCount'),flush=True)
                time.sleep(2)
            full=task.result();save('full',full)
        assert full['status']=='CUTSCENE_MP4_EXPORTED' and full['video']['fullDecodePassed'] and full['video']['decodedFrameVerified'],full
        if a.smoke:assert full['video']['frameCount']==5 and full['range']['startMs']==990,full
        else:assert full['range']['startMs']==0 and full['range']['durationSource']=='directorEndScene',full
        clip=call('/cutscene/export',{'camera':'Top','start_ms':990,'end_ms':1980,'fps':15,'output':str(work/'SelectedRange.mp4')});save('range',clip)
        assert clip['status']=='CUTSCENE_MP4_EXPORTED' and clip['video']['frameCount']==15 and clip['video']['fps']=='15/1',clip
        assert clip['preview']['sha256']!=full['preview']['sha256'],'Camera choice did not change video preview'
        with urllib.request.urlopen(urllib.request.Request(info['url']+full['artifact']['download'],headers={'X-SC2-Token':info['token']}),timeout=20) as response:
            assert hashlib.sha256(response.read()).hexdigest()==full['artifact']['sha256']
        try:call('/cutscene/export',{'camera':a.camera,'start_ms':0,'end_ms':1000,'output':str(work/'FullScene.mp4')});raise AssertionError('Overwrite accepted')
        except RuntimeError as error:assert '409' in str(error),error
        with concurrent.futures.ThreadPoolExecutor() as pool:
            task=pool.submit(call,'/cutscene/export',{'camera':a.camera,'start_ms':0,'end_ms':3965,'output':str(work/'Cancelled.mp4')})
            until=time.monotonic()+60
            while time.monotonic()<until:
                state=call('/cutscene/export/status')
                if state.get('status')=='RUNNING' and state.get('framesDone',0)>=2:break
                time.sleep(.2)
            else:raise RuntimeError('Cancel test never reached rendering')
            assert call('/cutscene/export/cancel',{'job_id':state['jobId']})['status']=='CANCEL_REQUESTED'
            cancelled=task.result();save('cancel',cancelled);assert cancelled['status']=='CANCELLED' and not (work/'Cancelled.mp4').exists(),cancelled
        for result in (full,clip):
            observed=result['desktopObservation'];assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples'],observed
        assert [hashlib.sha256(f.read_bytes()).hexdigest() for f in sources]==hashes
        save('VERIFICATION',{'status':'NATIVE_MP4_BACKGROUND_PASSED','full':full['video'],'range':clip['video'],'cancellation':True,
            'overwriteProtected':True,'downloadVerified':True,'sourcesUnchanged':True,'desktopObservation':clip['desktopObservation']})
        print('Full scene, selected range/camera, decode, download, cancellation and hidden desktop passed',flush=True)
    finally:
        if info:
            try:call('/shutdown',{})
            except Exception:pass
        try:proc.wait(timeout=20)
        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=20)
if __name__=='__main__':main()
