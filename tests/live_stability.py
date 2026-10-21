"""Opt-in repeated native requests, negative cases and recovery in one worker."""
import argparse,hashlib,json,subprocess,sys,time,urllib.request,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--work',required=True)
p.add_argument('--package',action='store_true');p.add_argument('--gui-request');p.add_argument('--repeat',type=int,default=6);a=p.parse_args()
work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);info=None;responses=[];passed=False
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
template=Path(a.template).resolve();pins={str(template):sha(template)}
gui=json.loads(Path(a.gui_request).read_text(encoding='utf8')) if a.gui_request else None
if gui:
 for key in ('template','triggers_file','trigger_strings'):
  if gui.get(key):pins[gui[key]]=sha(gui[key])
cmd=[str(root/'dist/SC2NativeAPI.exe')] if a.package else [sys.executable,str(root/'app/hidden_api.py')]
proc=subprocess.Popen(cmd+['serve','--port','0','--work',str(work/'runtime')],creationflags=subprocess.CREATE_NO_WINDOW,
 stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'))
def call(route,body=None):
 req=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json','X-SC2-Token':info['token']})
 started=time.monotonic()
 try:
  with urllib.request.urlopen(req,timeout=1200) as response:code=response.status;result=json.load(response)
 except urllib.error.HTTPError as error:code=error.code;result=json.load(error)
 entry={'route':route,'http':code,'seconds':time.monotonic()-started,'result':result};responses.append(entry)
 (work/('response-%03d.json'%len(responses))).write_text(json.dumps(entry,indent=2),encoding='utf8')
 print(route,code,result.get('status'),result.get('failureKind'),result.get('error'),flush=True);return code,result
def valid(letter):
 code,result=call('/convert',{'template':str(template),'triggers_file':str(root/('tests/fixtures/Triggers-'+letter+'.xml')),
  'context_label':'Native oracle marker 20261020','expect_text':[],'compile':True})
 assert code==200 and result['nativeCompilePassed'] and result['compilerErrors']==0,result.get('error')
 for native in result['steps'].values():
  assert native['transport']=='owned-startup-thread-local' and not native['crossProcessHookRegistrationUsed']
  assert native['requestGuardRemoved'] and native['dllPid']==native['pid'] and native['dllThread']==native['ownerThread']
 value='170121' if letter=='A' else '170122';assert value in result['galaxy']
 code,exported=call('/galaxy/export',{});assert code==200 and exported['artifact']['sha256']==result['sourceSha256']
 req=urllib.request.Request(info['url']+exported['artifact']['download'],headers={'X-SC2-Token':info['token']})
 with urllib.request.urlopen(req) as response:assert hashlib.sha256(response.read()).hexdigest()==result['sourceSha256']
 observed=result['desktopObservation'];assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
 return result
try:
 until=time.monotonic()+45
 while not (work/'runtime/api-info.json').exists():
  assert proc.poll() is None and time.monotonic()<until;time.sleep(.1)
 info=json.loads((work/'runtime/api-info.json').read_text());last=None
 for index in range(a.repeat):last=valid('A' if index%2==0 else 'B')
 code,bad=call('/convert',{'template':str(template),'triggers_file':str(root/'tests/fixtures/Triggers-A.xml'),'context_label':'__missing_native_context__','compile':True})
 assert code==422 and bad['failureStage']=='generate' and bad['failureNative']['error']==45 and not bad['nativeGenerationVerified']
 assert call('/galaxy/export',{})[0]==400;last=valid('A')
 code,bad=call('/convert',{'template':str(template),'triggers_file':str(root/'tests/fixtures/Triggers-Orphan.xml'),'context_label':'NativeOrphanProbe','compile':True})
 assert code==422 and bad['failureKind']=='NATIVE_GUI_NORMALIZATION_LOSS' and bad['steps']['save']['documentIo']['saved']
 assert bad['nativeNormalization']['removedElementCount']>0 and not bad['nativeGenerationVerified']
 assert call('/galaxy/export',{})[0]==400;last=valid('B')
 assert call('/convert',{'template':str(template),'triggers_xml':'<TriggerData>','compile':True})[0]==400
 assert call('/galaxy/export',{})[0]==400;last=valid('A')
 if gui:
  code,result=call('/convert',gui);assert code==200 and result['nativeCompilePassed'],result.get('error')
  # Private negative: remove only array declarations, retaining their uses.
  tree=ET.fromstring(Path(gui['triggers_file']).read_bytes());removed=0
  for typ in tree.findall('.//VariableType'):
   for extent in typ.findall('ArraySize'):typ.remove(extent);removed+=1
  assert removed;negative=work/'ScalarDeclarations.xml';negative.write_bytes(ET.tostring(tree,encoding='utf-8',xml_declaration=True))
  code,result=call('/convert',{**gui,'triggers_file':str(negative)})
  assert code==422 and result['failureKind']=='NATIVE_COMPILE_ERRORS' and result['compilerErrors']>0,result.get('error')
  last=valid('B')
 assert all(sha(path)==digest for path,digest in pins.items())
 report={'status':'NATIVE_STABILITY_PASSED','package':a.package,'repeatedValidConversions':a.repeat,'extraGuiTested':bool(gui),
  'nativeGuiLossRejected':True,'failedGenerationClearedExport':True,'recoveryPassed':True,'sourcesUnchanged':True,
  'desktopObservation':last['desktopObservation'],'requestCount':len(responses)}
 (work/'VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf8');passed=True
finally:
 if info:call('/shutdown',{})
 proc.wait(timeout=30)
