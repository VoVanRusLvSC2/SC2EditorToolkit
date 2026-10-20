"""Original Editor frame sampling followed by an independent MP4 encoder."""
import ctypes,hashlib,json,math,os,shutil,subprocess,time,uuid
from fractions import Fraction
from pathlib import Path
from .cutscenes import scene_file,scene_duration,seek_arguments

NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)

def video_plan(request,scene):
    for flag in ('overwrite','keep_frames'):
        if flag in request and not isinstance(request[flag],bool):raise ValueError(flag+' must be a JSON boolean')
    if request.get('output') is not None and (not isinstance(request['output'],str) or not request['output'].strip()):
        raise ValueError('output must be a nonempty MP4 path')
    camera,_=seek_arguments({'camera':request.get('camera','Director')})
    fps=request.get('fps',30)
    if isinstance(fps,bool) or not isinstance(fps,int) or not 1<=fps<=60:raise ValueError('fps must be an integer, 1..60')
    start=request.get('start_ms',0);end=request.get('end_ms',scene.get('durationMs'))
    for key,value in (('start_ms',start),('end_ms',end)):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=600000:
            raise ValueError(key+' must be finite, 0..600000; provide end_ms when scene duration is unknown')
    start,end=Fraction(str(start)),Fraction(str(end))
    if end<=start:raise ValueError('end_ms must be greater than start_ms (end is exclusive)')
    count=math.ceil((end-start)*fps/1000)
    samples=[int((start+Fraction(index*1000,fps)+Fraction(33,2))//33)*33 for index in range(count)]
    if samples[-1]>600000:raise ValueError('Native sample exceeds supported timeline')
    return {'camera':camera,'fps':fps,'startMs':float(start),'endMs':float(end),'frameCount':count,
        'sampleTimesMs':samples,'timeResolutionMs':33,'encodedDurationSeconds':count/fps,
        'durationSource':scene.get('durationSource') if 'end_ms' not in request else 'explicitRange'}

def encoder_tools():
    encoder=shutil.which(os.environ.get('SC2_FFMPEG','ffmpeg'))
    if not encoder:raise RuntimeError('FFmpeg required: install it on PATH or set SC2_FFMPEG')
    probe=os.environ.get('SC2_FFPROBE') or str(Path(encoder).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe'))
    probe=shutil.which(probe) or shutil.which('ffprobe')
    if not probe:raise RuntimeError('ffprobe required alongside FFmpeg or on PATH')
    return encoder,probe

def validate_video(path,encoder,probe,plan,preview_index):
    inspected=subprocess.run([probe,'-v','error','-select_streams','v:0','-count_frames','-show_entries',
        'stream=codec_name,width,height,avg_frame_rate,nb_read_frames,pix_fmt,duration:format=duration','-of','json',str(path)],
        capture_output=True,creationflags=NO_WINDOW,timeout=120)
    if inspected.returncode:raise RuntimeError('ffprobe failed: '+inspected.stderr.decode(errors='replace')[-2000:])
    info=json.loads(inspected.stdout);stream=info['streams'][0]
    if stream['codec_name']!='h264' or int(stream['nb_read_frames'])!=plan['frameCount'] or Fraction(stream['avg_frame_rate'])!=plan['fps']:
        raise RuntimeError('Encoded video codec/frame count/FPS mismatch')
    duration=float(stream.get('duration') or info['format']['duration'])
    if abs(duration-plan['encodedDurationSeconds'])>1/plan['fps']+.01:raise RuntimeError('Encoded video duration mismatch')
    decoded=subprocess.run([encoder,'-v','error','-nostdin','-i',str(path),'-map','0:v:0','-f','null','-'],
        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=NO_WINDOW,timeout=max(120,duration*4))
    if decoded.returncode or decoded.stderr.strip():raise RuntimeError('MP4 full decode failed: '+decoded.stderr.decode(errors='replace')[-2000:])
    sample=subprocess.run([encoder,'-v','error','-nostdin','-i',str(path),'-vf',f'select=eq(n\\,{preview_index})',
        '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,creationflags=NO_WINDOW,timeout=120)
    if sample.returncode or len(sample.stdout)!=int(stream['width'])*int(stream['height'])*3:raise RuntimeError('Cannot verify decoded MP4 image')
    data=sample.stdout;bins=set();nonblack=0
    for i in range(0,len(data),3):
        r,g,b=data[i:i+3];nonblack+=bool(r or g or b);bins.add((77*r+150*g+29*b)>>8)
    if len(bins)<8 or nonblack<=len(data)//3000:raise RuntimeError('Decoded MP4 preview is black or uniform')
    return {'codec':stream['codec_name'],'pixelFormat':stream['pix_fmt'],'width':stream['width'],'height':stream['height'],
        'frameCount':int(stream['nb_read_frames']),'fps':stream['avg_frame_rate'],'durationSeconds':duration,
        'fullDecodePassed':True,'decodedFrameVerified':True,'decodedSampleIndex':preview_index,'decodedLuminanceBins':len(bins)}

def export_video(worker,request):
    metadata=scene_duration(scene_file(request['scene'])[0]) if request.get('scene') else worker.scene
    if not metadata:raise ValueError('Load a cutscene or supply scene and template')
    plan=video_plan(request,metadata);encoder,probe=encoder_tools()
    output=request.get('output');overwrite=request.get('overwrite',False)
    if output:
        target=Path(output).resolve()
        if target.suffix.lower()!='.mp4':raise ValueError('Output extension must be .mp4')
        if target.exists() and not overwrite:raise FileExistsError(target)
    ident=uuid.uuid4().hex;directory=worker.work/'videos'/ident;directory.mkdir(parents=True)
    progress={'status':'RUNNING','stage':'loading','jobId':ident,'framesDone':0,'frameCount':plan['frameCount'],'percent':0}
    worker.video_progress=progress.copy();started=time.monotonic();process=None
    def update(**values):
        progress.update(values);worker.video_progress=progress.copy()
        (directory/'progress.json').write_text(json.dumps(progress,indent=2),encoding='utf8')
    def cancelled():
        if worker.video_cancel.is_set():raise InterruptedError('Video export cancelled')
    try:
        if request.get('scene'):
            opened=worker.cutscene_open(request,_locked=True)
            if opened['status']=='FAILED':raise RuntimeError(opened.get('error','Scene load failed'))
        if not worker.alive() or not worker.scene:raise RuntimeError('Original Editor scene not loaded')
        source=Path(worker.scene['source']);source_hash=worker.scene['sha256'];cancelled()
        samples=plan['sampleTimesMs'];previous_time=None;previous_bytes=None;preview_index=None;detailed=0;black=0;duplicates=0;dimensions=None
        temporary=directory/'encoded.mp4';update(stage='rendering')
        with (directory/'encoder.log').open('wb') as error_log,(directory/'frames.jsonl').open('w',encoding='utf8') as manifest:
            for index,stamp in enumerate(samples):
                cancelled()
                if stamp==previous_time:
                    duplicates+=1;pixels=previous_bytes
                    evidence=dict(evidence,repeatedSample=True)
                else:
                    selected=worker.cutscene_seek({'camera':plan['camera'],'time_ms':stamp},_locked=True,_advance=previous_time is not None)
                    if selected['status']=='FAILED':raise RuntimeError(selected.get('error','Frame selection failed'))
                    frame_dir=directory/'frames'/f'{index:06d}'
                    captured=worker.capture_frame({'allow_empty':True},_locked=True,_directory=frame_dir,_register=False,_attempts=8 if index==0 else 1)
                    native=captured['native'];selection=captured['frame']
                    if captured['status']=='FAILED' or native['sourceWindow']!=selection['viewport'] or not selection['timeConfirmed'] or not selection['cameraConfirmed']:
                        raise RuntimeError('Native video frame identity/time/camera not confirmed')
                    size=(native['width'],native['height'])
                    if dimensions and size!=dimensions:raise RuntimeError('Native viewport dimensions changed during video export')
                    dimensions=size;path=Path(captured['capturePath']);pixels=path.read_bytes()
                    evidence={'nativeTimeMs':stamp,'readbackTimeMs':selection['actualTimeMs'],'sequence':native['sequence'],
                        'sourceWindow':native['sourceWindow'],'nonBlackPixels':native['nonBlackPixels'],'imageHasDetail':captured['imageHasDetail'],
                        'emptyFrame':captured['emptyFrame'],'pngSha256':hashlib.sha256(pixels).hexdigest(),'repeatedSample':False}
                    if not request.get('keep_frames',False):
                        for attempt in frame_dir.glob('*.png'):attempt.unlink()
                if evidence['imageHasDetail']:
                    detailed+=1
                    if preview_index is None or index==len(samples)//2:
                        (directory/'preview.png').write_bytes(pixels);preview_index=index
                if evidence['emptyFrame']:black+=1
                if process is None:
                    process=subprocess.Popen([encoder,'-hide_banner','-v','error','-nostdin','-n','-f','image2pipe','-vcodec','png',
                        '-framerate',str(plan['fps']),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','18',
                        '-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-pix_fmt','yuv420p','-movflags','+faststart',str(temporary)],
                        stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=error_log,creationflags=NO_WINDOW)
                    # Encoder lifetime belongs to the same owned worker job.
                    if os.name=='nt':
                        from .runtime import kernel
                        kernel.AssignProcessToJobObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p];kernel.AssignProcessToJobObject.restype=ctypes.c_int
                        if not kernel.AssignProcessToJobObject(worker.job_handle,int(process._handle)):raise OSError(ctypes.get_last_error(),'Cannot own encoder lifetime')
                process.stdin.write(pixels);process.stdin.flush()
                manifest.write(json.dumps(dict(evidence,index=index,videoTimeSeconds=index/plan['fps']))+'\n');manifest.flush()
                previous_time=stamp;previous_bytes=pixels
                update(framesDone=index+1,percent=round(100*(index+1)/len(samples),2),nativeTimeMs=stamp,elapsedSeconds=round(time.monotonic()-started,1))
            cancelled();process.stdin.close()
            if process.wait(timeout=120):raise RuntimeError('MP4 encoder failed; see '+str(directory/'encoder.log'))
        if not detailed or preview_index is None:raise RuntimeError('Entire requested video range is black or uniform')
        cancelled();update(stage='verifying')
        verified=validate_video(temporary,encoder,probe,plan,preview_index);cancelled()
        if hashlib.sha256(source.read_bytes()).hexdigest()!=source_hash:raise RuntimeError('Source scene changed during export')
        result={'status':'CUTSCENE_MP4_EXPORTED','jobId':ident,'range':{k:v for k,v in plan.items() if k!='sampleTimesMs'},
            'firstNativeTimeMs':samples[0],'lastNativeTimeMs':samples[-1],'sourceResolution':list(dimensions),'video':verified,
            'detailedFrames':detailed,'blackFrames':black,'repeatedSamples':duplicates,'audioIncluded':False,
            'source':'original Editor D3D9 cutscene viewport','sourceUnchanged':True,'inputInjectionUsed':False,'desktopScreenshot':False,
            'frameManifest':str(directory/'frames.jsonl'),'elapsedSeconds':round(time.monotonic()-started,1)}
        worker._background_result(result)
        if result['status']=='FAILED':raise RuntimeError(result['error'])
        result['artifact']=worker.artifacts.publish_file(temporary,suffix='.mp4',mime='video/mp4',output=output,overwrite=overwrite)
        result['preview']=worker.artifacts.register_png(directory/'preview.png')
        update(status='COMPLETED',stage='complete',artifact=result['artifact'])
        (directory/'export.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
    except Exception as error:
        update(status='CANCELLED' if isinstance(error,InterruptedError) else 'FAILED',stage='stopped',error=str(error))
        if isinstance(error,InterruptedError):return {'status':'CANCELLED','jobId':ident,'framesDone':progress['framesDone'],'artifact':None}
        raise
    finally:
        if process and process.poll() is None:
            if process.stdin:
                try:process.stdin.close()
                except OSError:pass
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
