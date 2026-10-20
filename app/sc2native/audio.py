"""PCM from the owned Editor output stream, then AAC muxing; no loopback."""
import json,math,subprocess,threading
from pathlib import Path
from .video import NO_WINDOW

def capture_audio(worker,directory,plan):
    from .runtime import oracle
    path=directory/'original-audio.wav';cancel=Path(str(path)+'.cancel');finished=threading.Event()
    def watch():
        while not finished.wait(.05):
            if worker.video_cancel.is_set():cancel.touch();return
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        oracle.ACTIVE_DESKTOP=worker.state['desktop']
        native=oracle.native_step(directory,'01-scene-audio',worker.state['pid'],worker.state['currentDocument'],
            camera=plan['camera'],time_ms=math.ceil(plan['endMs']),map_path=path)
    except Exception:
        if worker.video_cancel.is_set():raise InterruptedError('Video export cancelled')
        raise
    finally:finished.set();thread.join(timeout=2)
    if worker.video_cancel.is_set():raise InterruptedError('Video export cancelled')
    a=native['audio']
    if not a['ready'] or a['error'] or not native['timeConfirmed'] or not native['cameraConfirmed'] or not a['frames']:
        raise RuntimeError('Original Editor audio playback/capture not confirmed')
    if not a['sceneStartQpc'] or not a['frequency']:raise RuntimeError('Native audio/timeline synchronization unavailable')
    origin=(a['firstQpc']-a['sceneStartQpc'])/a['frequency'];duration=a['frames']/a['rate']
    if abs(origin)>.5:raise RuntimeError('Native mixer/timeline start skew exceeds 500 ms')
    delta=origin+duration-plan['endMs']/1000
    if delta<-.1:raise RuntimeError('Original audio capture ended before requested range')
    if delta>.25:raise RuntimeError('Native playback could not maintain audio/video synchronization')
    evidence=dict(a,source='owned Editor render buffers before speaker silencing',systemLoopback=False,microphone=False,
        silent=a['nonzero']==0,rms=math.sqrt(a['sumSquares']/(a['frames']*a['channels'])),
        timelineOriginSeconds=origin,captureDurationSeconds=duration,timelineDurationDeltaSeconds=delta,synchronizationResolutionMs=33)
    (directory/'audio-capture.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
    return path,evidence

def audio_filter(plan,evidence):
    rate=evidence['rate'];start=round((plan['startMs']/1000-evidence['timelineOriginSeconds'])*rate)
    trim=f'atrim=start_sample={start},asetpts=PTS-STARTPTS' if start>=0 else f'asetpts=PTS-STARTPTS,adelay={-start}S:all=1'
    count=round(plan['encodedDurationSeconds']*rate)
    return trim+f',apad,atrim=end_sample={count}'

def mux_audio(worker,video,wave,target,encoder,probe,plan,evidence):
    command=[encoder,'-v','error','-nostdin','-n','-i',str(video),'-i',str(wave),'-map','0:v:0','-map','1:a:0',
        '-c:v','copy','-af',audio_filter(plan,evidence),'-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)]
    with target.with_suffix('.log').open('wb') as log:
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=log,creationflags=NO_WINDOW)
        try:
            if __import__('os').name=='nt':
                from .runtime import kernel
                import ctypes
                kernel.AssignProcessToJobObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p];kernel.AssignProcessToJobObject.restype=ctypes.c_int
                if not kernel.AssignProcessToJobObject(worker.job_handle,int(process._handle)):raise RuntimeError('Cannot own audio encoder')
            while process.poll() is None:
                if worker.video_cancel.wait(.1):raise InterruptedError('Video export cancelled')
            if process.returncode:raise RuntimeError('AAC mux failed; see '+str(target.with_suffix('.log')))
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
    return validate_audio(target,encoder,probe,plan,evidence)

def validate_audio(path,encoder,probe,plan,evidence):
    inspected=subprocess.run([probe,'-v','error','-select_streams','a','-show_entries','stream=codec_name,sample_rate,channels,duration','-of','json',str(path)],
        capture_output=True,creationflags=NO_WINDOW,timeout=120)
    if inspected.returncode:raise RuntimeError('Cannot inspect encoded audio')
    streams=json.loads(inspected.stdout)['streams']
    if len(streams)!=1 or streams[0]['codec_name']!='aac':raise RuntimeError('Exactly one AAC track required')
    a=streams[0];duration=float(a['duration'])
    if abs(duration-plan['encodedDurationSeconds'])>.05:raise RuntimeError('AAC/video duration mismatch')
    # Stream decoder output to disk: long exports never accumulate PCM in RAM.
    decoded=Path(path).with_suffix('.decoded.f32')
    try:
        with decoded.open('xb') as out:
            run=subprocess.run([encoder,'-v','error','-nostdin','-i',str(path),'-map','0:a:0','-f','f32le','pipe:1'],
                stdout=out,stderr=subprocess.PIPE,creationflags=NO_WINDOW,timeout=max(120,duration*4))
        if run.returncode or run.stderr.strip():raise RuntimeError('AAC full decode failed')
        import array
        nonzero=0;total=0;power=0.;peak=0.
        with decoded.open('rb') as source:
            while chunk:=source.read(1024*1024):
                values=array.array('f');values.frombytes(chunk);total+=len(values)
                for v in values:
                    if not math.isfinite(v):raise RuntimeError('Nonfinite decoded audio')
                    nonzero+=v!=0;power+=v*v;peak=max(peak,abs(v))
        if not total:raise RuntimeError('Decoded AAC is empty')
        return dict(codec='aac',rate=int(a['sample_rate']),channels=a['channels'],durationSeconds=duration,
            fullDecodePassed=True,silent=not nonzero,rms=math.sqrt(power/total),peak=peak,**{'capture':evidence})
    finally:decoded.unlink(missing_ok=True)
