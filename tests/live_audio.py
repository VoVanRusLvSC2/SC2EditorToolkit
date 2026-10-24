"""Opt-in original Nydus scene plus a private Nydus copy with a native sound cue."""
import os
import argparse,concurrent.futures,hashlib,json,subprocess,sys,time,urllib.request,urllib.error,uuid,array
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--scene',required=True)
 p.add_argument('--camera',required=True);p.add_argument('--work',required=True);p.add_argument('--package',action='store_true');p.add_argument('--smoke',action='store_true');a=p.parse_args()
 root=Path(__file__).resolve().parents[1];work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
 sources=[Path(a.template).resolve(),Path(a.scene).resolve()];hashes=[hashlib.sha256(f.read_bytes()).hexdigest() for f in sources]
 # A private test derivative, never modify the user's source or dependencies.
 cue=work/'NydusAudioVerification.SC2Cutscene';text=sources[1].read_text(encoding='utf8')
 node=f'<CCutsceneNodeSound guid="{uuid.uuid4().int>>64}" name="Native audio test" soundLink="Marine_Ready" soundIndex="0" mode="2" useRandomIndex="0" nonSeeking="0"><CCutsceneElementObject guid="{uuid.uuid4().int>>64}" start="500" duration="3000"/></CCutsceneNodeSound>'
 cue.write_text(text.replace('</CutsceneState>',node+'</CutsceneState>'),encoding='utf8')
 command=[str(root/os.environ.get('SC2_PACKAGE_DIR','dist')/'SC2NativeAPI.exe')] if a.package else [sys.executable,str(root/'app'/'hidden_api.py')]
 proc=subprocess.Popen(command+['serve','--work',str(work/'runtime'),'--port','0'],creationflags=subprocess.CREATE_NO_WINDOW,
     stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'));info=None
 def call(route,body=None):
  request=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'X-SC2-Token':info['token'],'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(request,timeout=3600) as response:return json.load(response)
  except urllib.error.HTTPError as error:raise RuntimeError(str(error)+': '+error.read().decode()) from error
 def save(name,data):(work/(name+'.json')).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
 def export(name,request):
  with concurrent.futures.ThreadPoolExecutor() as pool:
   task=pool.submit(call,'/cutscene/export',dict(request,output=str(work/(name+'.mp4'))));last=None
   while not task.done():
    progress=call('/cutscene/export/status');key=(progress.get('stage'),progress.get('framesDone',0)//20)
    if key!=last:print(name,key,flush=True);last=key
    time.sleep(2)
   result=task.result()
  save(name,result);assert result['status']=='CUTSCENE_MP4_EXPORTED',result
  assert result['audioIncluded'] and result['audio']['fullDecodePassed'] and result['video']['fullDecodePassed'],result
  observation=result['desktopObservation'];assert not observation['visibleWindowsOnUserDesktopPeak'] and not observation['editorForegroundSamples'],observation
  return result
 try:
  until=time.monotonic()+30
  while not (work/'runtime'/'api-info.json').is_file():
   if proc.poll() is not None or time.monotonic()>until:raise RuntimeError('API startup failed')
   time.sleep(.1)
  info=json.loads((work/'runtime'/'api-info.json').read_text())
  initial={'template':str(sources[0]),'scene':str(sources[1]),'camera':a.camera}
  if a.smoke:initial.update(start_ms=990,end_ms=1320,fps=15)
  original=export('OriginalNydus',initial)
  sounded=export('NydusWithNativeCue',{'scene':str(cue),'camera':a.camera,'fps':10})
  assert not sounded['audio']['silent'] and sounded['audio']['capture']['renderedFrames']>0,sounded['audio']
  decoded=subprocess.run(['ffmpeg','-v','error','-i',str(work/'NydusWithNativeCue.mp4'),'-map','0:a:0','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  values=array.array('f');values.frombytes(decoded.stdout);rate=sounded['audio']['rate'];channels=sounded['audio']['channels']
  onset=next(i for i,v in enumerate(values) if abs(v)>.002)/channels/rate
  # Verify timing against the actual original Editor PCM, including its own
  # sound-engine latency and the recording's quiet intro. Threshold crossing
  # is not the same thing as an authored Sound element start.
  capture=sounded['audio']['capture'];manifest=Path(sounded['frameManifest']).parent
  raw=subprocess.run(['ffmpeg','-v','error','-i',str(manifest/'original-audio.wav'),'-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  encoded=subprocess.run(['ffmpeg','-v','error','-i',str(work/'NydusWithNativeCue.mp4'),'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
  def envelope(data):
   import math
   v=array.array('f');v.frombytes(data);return [math.sqrt(sum(x*x for x in v[i:i+480])/480) for i in range(0,len(v)-479,480)]
  original_envelope=envelope(raw.stdout)[100:200];aac_envelope=envelope(encoded.stdout)
  import math
  scores=[]
  for offset in range(50,151):
   window=aac_envelope[offset:offset+len(original_envelope)]
   if len(window)!=len(original_envelope):continue
   norm=math.sqrt(sum(x*x for x in original_envelope)*sum(x*x for x in window))
   if norm:scores.append((sum(x*y for x,y in zip(original_envelope,window))/norm,offset/100))
  correlation,position=max(scores);timing_error=position-(1+capture['timelineOriginSeconds'])
  assert correlation>.97 and abs(timing_error)<.025,('AAC changed native PCM timing/content',correlation,timing_error)
  ranged=export('SelectedCameraAndRange',{'camera':'Top','start_ms':990,'end_ms':1980,'fps':15})
  assert ranged['video']['frameCount']==15,ranged
  assert sounded['preview']['sha256']!=ranged['preview']['sha256'],'Camera choice did not affect frame'
  front=export('FrontRange',{'camera':a.camera,'start_ms':990,'end_ms':1980,'fps':15})
  assert not front['audio']['silent'],'Repeated native audio export lost the earlier cue'
  with concurrent.futures.ThreadPoolExecutor() as pool:
   pending=pool.submit(call,'/cutscene/export',{'camera':a.camera,'end_ms':3965,'output':str(work/'cancelled.mp4')})
   deadline=time.monotonic()+60
   while time.monotonic()<deadline:
    state=call('/cutscene/export/status')
    if state.get('stage')=='recordingAudio':break
    time.sleep(.05)
   else:raise RuntimeError('Audio pass never started for cancellation test')
   call('/cutscene/export/cancel',{'job_id':state['jobId']});cancel=pending.result();save('cancel',cancel)
   assert cancel['status']=='CANCELLED' and not (work/'cancelled.mp4').exists(),cancel
  assert [hashlib.sha256(f.read_bytes()).hexdigest() for f in sources]==hashes
  save('VERIFICATION',{'status':'NATIVE_AUDIO_MP4_BACKGROUND_PASSED','original':original['audio'],'cue':sounded['audio'],'cueOnsetSeconds':onset,'nativePcmCorrelation':correlation,'nativePcmTimingErrorMs':timing_error*1000,
      'range':ranged['audio'],'frontRange':front['audio'],'smoke':a.smoke,'sourcesUnchanged':True,'audioCancellation':True,'desktopObservation':ranged['desktopObservation'],'packaged':a.package})
  print('Original scene, native cue, AAC decode, timing, selected camera/range and cancellation passed',flush=True)
 finally:
  if info:
   try:call('/shutdown',{})
   except Exception:pass
  try:proc.wait(timeout=30)
  except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=20)
if __name__=='__main__':main()
