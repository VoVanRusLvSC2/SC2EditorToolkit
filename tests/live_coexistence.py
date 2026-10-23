"""Opt-in existing normal Editor + owned hidden Editor, including worker restart.

The normal Editor is only observed. No visible process is started, injected,
activated, closed, or sent a GUI command. The already-running game is untouched.
"""
import argparse,ctypes,hashlib,json,subprocess,sys,threading,time,urllib.request,urllib.error
from ctypes import wintypes as W
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from editor_installation import resolve_editor
from sc2native.runtime import kernel,user,ENUM,input_desktop,process_time
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--visible-pid',type=int,required=True);p.add_argument('--template',required=True);p.add_argument('--work',required=True)
p.add_argument('--package',action='store_true');p.add_argument('--map');p.add_argument('--map-camera',default='2001')
p.add_argument('--scene');p.add_argument('--scene-template');p.add_argument('--scene-camera',default='Front Formation Camera')
p.add_argument('--roundtrip',action='store_true');a=p.parse_args()
work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
template=Path(a.template).resolve(strict=True);pins={str(template):sha(template)}
for value in (a.map,a.scene,a.scene_template):
    if value:pins[str(Path(value).resolve())]=sha(value)
editor=resolve_editor();pins[str(editor)]=sha(editor)
visible_time=process_time(a.visible_pid);assert visible_time,'Specified normal Editor PID is not running'
handle=kernel.OpenProcess(0x1000,False,a.visible_pid);path=ctypes.create_unicode_buffer(32768);length=W.DWORD(len(path))
assert handle and kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(length));kernel.CloseHandle(handle)
assert path.value.casefold()==str(editor).casefold(),'Visible PID is not the installed original Editor'
assert input_desktop()=='Default','No test starts on a locked/different input desktop'
user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
user.IsWindowEnabled.argtypes=[W.HWND];user.IsHungAppWindow.argtypes=[W.HWND]
def snapshot(pid):
    rows=[]
    @ENUM
    def enum(hwnd,param):
        owner=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:
            text=ctypes.create_unicode_buffer(2048);user.GetWindowTextW(hwnd,text,len(text))
            rows.append({'hwnd':int(hwnd),'title':text.value,'visible':bool(user.IsWindowVisible(hwnd)),
                'enabled':bool(user.IsWindowEnabled(hwnd)),'hung':bool(user.IsHungAppWindow(hwnd))})
        return True
    user.EnumWindows(enum,0);return rows
def documents(rows):
    return sorted((r['hwnd'],r['title']) for r in rows if r['visible'] and r['enabled'] and not r['hung'] and
        ' - [' in r['title'] and r['title'].endswith('] - StarCraft II Editor') and not r['title'].startswith('Script Test'))
class Module(ctypes.Structure):
    _fields_=[('dwSize',W.DWORD),('moduleId',W.DWORD),('pid',W.DWORD),('globalUse',W.DWORD),('processUse',W.DWORD),
        ('base',ctypes.c_void_p),('bytes',W.DWORD),('handle',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]
kernel.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];kernel.CreateToolhelp32Snapshot.restype=W.HANDLE
kernel.Module32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(Module)];kernel.Module32NextW.argtypes=[W.HANDLE,ctypes.POINTER(Module)]
def visible_bridge_modules():
    handle=kernel.CreateToolhelp32Snapshot(0x8|0x10,a.visible_pid)
    assert handle and handle!=ctypes.c_void_p(-1).value,'Cannot inspect visible module list'
    entry=Module();entry.dwSize=ctypes.sizeof(entry);found=[]
    try:
        ok=kernel.Module32FirstW(handle,ctypes.byref(entry));assert ok,'Cannot read visible module list'
        while ok:
            if entry.name.casefold() in ('sc2startupbootstrap.dll','sc2nativebridge.dll'):found.append(entry.name)
            ok=kernel.Module32NextW(handle,ctypes.byref(entry))
    finally:kernel.CloseHandle(handle)
    return found
before=snapshot(a.visible_pid);baseline=documents(before);assert baseline,'Open a normal map/mod document before testing'
assert not visible_bridge_modules(),'Normal Editor already has a toolkit bridge; independent baseline required'
save=lambda name,value:(work/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')
save('visible-before',before)
stop=threading.Event();samples=[];runtime=None;owned={};observer_errors=[]
def observe():
    while not stop.is_set():
        try:
            if runtime:
                for state_file in runtime.glob('workers/*/startup/state.json'):
                    try:
                        state=json.loads(state_file.read_text(encoding='utf8'))
                        if state.get('pid') and state.get('createTimeFiletime'):owned[state['pid']]=state['createTimeFiletime']
                    except (OSError,ValueError):pass
            foreground=W.DWORD();user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(foreground))
            samples.append({'inputDesktop':input_desktop(),'foregroundPid':foreground.value,
                'visibleAlive':process_time(a.visible_pid)==visible_time,'visibleResponsive':bool(documents(snapshot(a.visible_pid))),
                'hiddenVisibleWindows':sum(r['visible'] for pid,created in list(owned.items()) if process_time(pid)==created for r in snapshot(pid))})
        except Exception as error:observer_errors.append(str(error))
        stop.wait(.2)
thread=threading.Thread(target=observe,daemon=True);thread.start()
api=None;info=None;responses=[];rounds=[];old_info=None;old_artifact=None
def call(route,body=None,*,token=None):
    req=urllib.request.Request(info['url']+route,None if body is None else json.dumps(body).encode(),
        {'X-SC2-Token':token or info['token'],'Content-Type':'application/json'})
    started=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=1200) as response:code=response.status;result=json.load(response)
    except urllib.error.HTTPError as error:code=error.code;result=json.load(error)
    responses.append({'route':route,'http':code,'seconds':time.monotonic()-started,'result':result})
    save('response-%03d'%len(responses),responses[-1]);print(route,code,result.get('status'),result.get('error'),flush=True)
    return code,result
def good(route,body=None):
    code,result=call(route,body);assert code==200 and result.get('status')!='FAILED',result.get('error')
    o=result.get('desktopObservation',{})
    if o:assert o['visibleWindowsOnUserDesktopPeak']==o['editorForegroundSamples']==o['inputDesktopChanges']==0
    assert process_time(a.visible_pid)==visible_time and documents(snapshot(a.visible_pid))==baseline
    return result
def convert(letter,pid):
    result=good('/convert',{'template':str(template),'triggers_file':str(ROOT/f'tests/fixtures/Triggers-{letter}.xml'),
        'context_label':'Native oracle marker 20261020','compile':True})
    assert result['nativeCompilePassed'] and result['compilerErrors']==0
    assert all(n['pid']==pid and n['dllPid']==pid for n in result['steps'].values())
    assert ('170121' if letter=='A' else '170122') in result['galaxy']
    artifact=good('/galaxy/export',{})['artifact'];assert artifact['sha256']==result['sourceSha256']
    req=urllib.request.Request(info['url']+artifact['download'],headers={'X-SC2-Token':info['token']})
    with urllib.request.urlopen(req) as response:assert hashlib.sha256(response.read()).hexdigest()==result['sourceSha256']
    return artifact
try:
    for index in range(2):
        run=work/('round-'+str(index+1));run.mkdir();runtime=run/'runtime'
        command=[str(ROOT/'dist/SC2NativeAPI.exe')] if a.package else [sys.executable,str(ROOT/'app/hidden_api.py')]
        api=subprocess.Popen(command+['serve','--port','0','--work',str(runtime)],creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=(run/'stdout.log').open('wb'),stderr=(run/'stderr.log').open('wb'))
        until=time.monotonic()+45
        while not (runtime/'api-info.json').is_file():assert api.poll() is None and time.monotonic()<until;time.sleep(.1)
        info=json.loads((runtime/'api-info.json').read_text(encoding='utf8'))
        if old_info:
            assert info['token']!=old_info['token'] and call('/modules',token=old_info['token'])[0]==403
            assert call('/artifacts/'+old_artifact)[0]==404
        started=good('/editor/start',{'template':str(template),'render_backend':'vulkan'})
        pid=started['pid'];created=process_time(pid);assert pid!=a.visible_pid and created and started['renderBackend']=='vulkan'
        assert started['instanceId'] and all(r['instanceId']!=started['instanceId'] for r in rounds)
        artifact=convert('A',pid);convert('B',pid)
        diagnostic=good('/editor/diagnostics',{});assert diagnostic['status']=='EDITOR_DIAGNOSTICS_READ'
        if index==0:
            if a.roundtrip:
                saved=good('/editor/save-reopen',{'map':str(template),'include_diffs':True})
                assert saved['nativeSaveVerified'] and saved['nativeReopenVerified'] and saved['componentComparisonVerified']
            if a.map:
                frame=good('/terrain/capture',{'map':str(Path(a.map).resolve()),'map_camera_id':a.map_camera,'output':str(work/'Terrain.png')})
                assert frame['requestedTerrainFrameVerified'] and frame['imageHasDetail'] and not frame['emptyFrame']
                assert frame['mapCamera']['nativeSelectionVerified'] and frame['renderBackend']=='vulkan'
            if a.scene:
                assert a.scene_template,'--scene-template required'
                good('/open',{'map':str(Path(a.scene_template).resolve())})
                good('/cutscene/open',{'scene':str(Path(a.scene).resolve())})
                frame=good('/render/capture',{'camera':a.scene_camera,'time_ms':1980})
                assert frame['requestedCutsceneFrameVerified'] and frame['imageHasDetail'] and not frame['emptyFrame']
                image=Path(frame['artifact']['path']);assert sha(image)==frame['artifact']['sha256']
                (work/'Cutscene.png').write_bytes(image.read_bytes())
        rounds.append({'pid':pid,'instanceId':started['instanceId'],'renderBackend':started['renderBackend'],'conversions':2,
            'nativeCompilerErrors':0,'diagnosticsRead':True,'nativeTransport':started['native']['transport']})
        assert call('/shutdown',{})[0]==200;api.wait(timeout=30)
        old_info=info;old_artifact=artifact['id'];info=None
        until=time.monotonic()+10
        while process_time(pid)==created and time.monotonic()<until:time.sleep(.1)
        assert process_time(pid)!=created,'Owned hidden worker survived shutdown'
        assert process_time(a.visible_pid)==visible_time and documents(snapshot(a.visible_pid))==baseline
    assert all(sha(path)==digest for path,digest in pins.items()) and not visible_bridge_modules()
    stop.set();thread.join(5)
    assert samples and not observer_errors
    assert all(r['visibleAlive'] and r['visibleResponsive'] and r['inputDesktop']=='Default' and not r['hiddenVisibleWindows'] and r['foregroundPid'] not in owned for r in samples)
    report={'status':'VISIBLE_FIRST_HIDDEN_RESTART_PASSED','package':a.package,'visiblePid':a.visible_pid,'visibleEditorRemainsOpen':True,
        'visibleDocumentAndWindowUnchanged':True,'visibleBridgeModules':[],'visibleUiCommandsUsed':False,'inputInjectionUsed':False,
        'desktopSwitchApiUsed':False,'rounds':rounds,'nativeConversions':4,'exactGalaxyDownloads':True,'oldTokenRejected':True,
        'oldArtifactRejected':True,'roundtripTested':a.roundtrip,'terrainFrameTested':bool(a.map),'cutsceneFrameTested':bool(a.scene),
        'sourcesUnchanged':True,'allOwnedEditorsClosed':True,'observationSamples':len(samples),'hiddenForegroundSamples':0,
        'hiddenVisibleWindowSamples':0,'inputDesktopChanges':0}
    save('VERIFICATION',report);save('visible-after',snapshot(a.visible_pid));print(json.dumps(report,indent=2),flush=True)
finally:
    if info:
        try:call('/shutdown',{})
        except Exception:pass
    if api and api.poll() is None:
        try:api.wait(timeout=20)
        except subprocess.TimeoutExpired:api.terminate();api.wait(timeout=20)
    stop.set();thread.join(5);save('observations',samples)
