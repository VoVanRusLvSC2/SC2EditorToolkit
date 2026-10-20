"""Raw Triggers XML -> original Editor document loader -> native Galaxy, no input injection."""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
from types import SimpleNamespace
import file_prepare as files

RES=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent/'bin-release'))
ACTIVE_DESKTOP=None

def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

class Session:
    """Serialize complete converter jobs per original Editor process."""
    def __init__(self,pid): self.pid=pid;self.handle=None
    def __enter__(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];kernel.WaitForSingleObject.restype=ctypes.c_uint
        self.handle=kernel.CreateMutexW(None,False,f'Local\\SC2NativeXmlJob-{self.pid}')
        if not self.handle: raise OSError(ctypes.get_last_error(),'Cannot create converter mutex')
        state=kernel.WaitForSingleObject(self.handle,0)
        if state not in (0,0x80):
            kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(self.handle);self.handle=None
            raise RuntimeError('Another XML conversion already owns this Editor session')
        self.kernel=kernel;return self
    def __exit__(self,*exc):
        self.kernel.ReleaseMutex.argtypes=[ctypes.c_void_p];self.kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        self.kernel.ReleaseMutex(self.handle);self.kernel.CloseHandle(self.handle)

def prepare(args):
    # This is the earlier file-only preparer, with its original generator path removed.
    options=SimpleNamespace(template=args.template,triggers=args.triggers,job=args.job,trigger_strings=args.trigger_strings,
        game_strings=args.game_strings,locale=args.locale,scope=args.scope,context_label=args.context_label,editor=args.editor,mpqcli=args.mpqcli)
    result=files.prepare(options)
    job=Path(args.job).resolve();manifest_path=job/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    old=Path(manifest['workingDocument']);new=old.with_name('NativeXml-'+manifest['jobId'].replace('-','')[:12]+old.suffix)
    old.rename(new);manifest['workingDocument']=str(new)
    # Prove that the packed document contains precisely the submitted XML bytes.
    command=[str(files.mpq_tool(args.mpqcli)),'read','Triggers',str(new)]
    check=subprocess.run(command,capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    expected=Path(args.triggers).read_bytes()
    if check.returncode or check.stdout!=expected:raise RuntimeError('Packed Triggers bytes differ from the submitted XML')
    manifest['packedTriggersByteEqual']=True;manifest['loader']='original Editor via thread-scoped DLL';manifest['xmlSource']=str(Path(args.triggers).resolve())
    save(manifest_path,manifest)
    return {**result,'workingDocument':str(new),'packedTriggersByteEqual':True}

def native_step(job,stage,pid,current,marker='',context='',map_path=None,scope='mapRoot',camera=None,time_ms=None,terrain=None):
    out=job/stage
    command=[str(RES/'SC2NativeBridge.exe'),stage.split('-',1)[1],'--pid',str(pid),'--expect-document',current,'--out',str(out)]
    if marker:command+=['--marker',marker]
    if context:command+=['--context-label',context]
    if map_path:command+=['--map',str(map_path)]
    if camera is not None:command+=['--camera',camera]
    if time_ms is not None:command+=['--time-ms',str(time_ms)]
    if terrain is not None:command+=['--image-size',str(terrain['size']),'--include-units','yes' if terrain['include_units'] else 'no','--include-doodads','yes' if terrain['include_doodads'] else 'no']
    command+=['--scope',scope]
    if ACTIVE_DESKTOP:command+=['--desktop',ACTIVE_DESKTOP]
    # A child with redirected stdio has no console to activate. Native controls
    # are handled inside the DLL under its thread-specific activation veto.
    with (job/(stage+'.stdout.txt')).open('wb') as stdout,(job/(stage+'.stderr.txt')).open('wb') as stderr:
        process=subprocess.Popen(command,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        save(job/'active-worker.json',{'pid':process.pid,'stage':stage,'exe':command[0],'editorPid':pid,'editorMustRemainOpen':True})
        # Do not terminate a handler that may still be running inside the Editor.
        code=process.wait()
    result_path=out/'result.json'
    if not result_path.is_file():raise RuntimeError(f'Native {stage} failed before an evidence result; see stderr')
    result=json.loads(result_path.read_text(encoding='utf-8'))
    compile_diagnostic=stage.endswith('-compile') and code==1 and result.get('compilerErrors',-1)>0
    if (code and not compile_diagnostic) or result['status']!='NATIVE_DLL_REQUEST_COMPLETED' or result['error']:
        reason=result.get('failure') or 'Native handler did not finish; no successful output is confirmed'
        raise RuntimeError(f'Native {stage} not confirmed: {reason}; exit={code}')
    if result['editorForegroundEvents'] or not result['hooksRemoved']:raise RuntimeError('Background invariant not satisfied')
    return result

def convert(args):
    with Session(args.pid):
        prepared=prepare(args)
        job=Path(args.job).resolve();manifest=json.loads((job/'manifest.json').read_text(encoding='utf-8'))
        result={'status':'STARTED_NOT_CONFIRMED','originalGenerator':True,'replacementEmitterUsed':False,'job':str(job),'nativeGenerationVerified':False,'nativeCompilePassed':False,'inputInjectionUsed':False,'steps':{}}
        save(job/'conversion.json',result)
        try:
            path=Path(prepared['workingDocument'])
            if files.sha(path)!=manifest['workingDocumentSha256']:raise RuntimeError('Prepared document changed before native loading')
            if files.sha(manifest['editor'])!=manifest['editorSha256']:raise RuntimeError('Original Editor build changed')
            if not manifest['contextLabel']:raise ValueError('Supply an exact authored map root --context-label or matching TriggerStrings')
            loaded=native_step(job,'01-load',args.pid,args.current_document,map_path=path)
            if not loaded['mapLoaded']:raise RuntimeError('Original document loader did not confirm the new archive')
            result['steps']['load']=loaded;save(job/'conversion.json',result)
            generated=native_step(job,'02-generate',args.pid,path.name,args.marker,manifest['contextLabel'],scope=manifest['scope'])
            result['steps']['generate']=generated
            source=(job/'02-generate'/'Native.galaxy').read_bytes()
            for text in args.expect_text:
                if text.encode('utf-8') not in source:raise RuntimeError('Expected source text absent: '+text)
            result.update(nativeGenerationVerified=True,currentDocument=path.name,output=str(job/'Native.galaxy'),sourceSha256=hashlib.sha256(source).hexdigest(),sourceBytes=len(source))
            shutil.copyfile(job/'02-generate'/'Native.galaxy',job/'Native.galaxy');save(job/'conversion.json',result)
            if args.compile:
                compiled=native_step(job,'03-compile',args.pid,path.name,args.marker,scope=manifest['scope'])
                result['steps']['compile']=compiled
                if not compiled['nativeCompilePassed']:raise RuntimeError('Fresh native compilation not proven')
                result['nativeCompilePassed']=True
            if Path(args.triggers).read_bytes()!=expected_xml(job):raise RuntimeError('Original XML source changed during conversion')
            result['status']='NATIVE_XML_TO_GALAXY_BACKGROUND_PASSED'
            result['allNativeStepsHadZeroEditorForegroundEvents']=all(v['editorForegroundEvents']==0 for v in result['steps'].values())
            result['manualExportByteIdentityVerified']=False
        except Exception as error:
            result.update(status='FAILED',error=str(error))
        save(job/'conversion.json',result)
        return result

def expected_xml(job):return (job/'components'/'Triggers').read_bytes()

def parser():
    p=argparse.ArgumentParser(description='Raw full Triggers XML -> original SC2 Editor loader/generator via a background DLL')
    sub=p.add_subparsers(dest='operation',required=True)
    for name in ('prepare','convert'):
        a=sub.add_parser(name)
        for option in ('template','triggers','job'):a.add_argument('--'+option,required=True)
        a.add_argument('--trigger-strings');a.add_argument('--game-strings');a.add_argument('--locale',default='enUS');a.add_argument('--context-label')
        a.add_argument('--scope',default='mapRoot',help='mapRoot or library:<8 hex library ID>')
        a.add_argument('--editor',default=str(files.EDITOR));a.add_argument('--mpqcli')
        if name=='convert':
            a.add_argument('--pid',type=int,required=True);a.add_argument('--current-document',required=True);a.add_argument('--marker',default='');a.add_argument('--expect-text',action='append',default=[]);a.add_argument('--compile',action='store_true')
    sub.add_parser('api',help='JSON lines requests: operation prepare/convert and args using the same names')
    return p

def dispatch(args):return prepare(args) if args.operation=='prepare' else convert(args)
def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    args=parser().parse_args()
    if args.operation=='api':
        for line in sys.stdin:
            try:
                request=json.loads(line)
                if request.get('operation') not in ('prepare','convert'):raise ValueError('Unsupported operation')
                argv=[request['operation']]
                for k,v in request.get('args',{}).items():
                    if v is None or v is False:continue
                    values=v if isinstance(v,list) else [v]
                    for value in values:
                        argv.append('--'+k.replace('_','-'))
                        if value is not True:argv.append(str(value))
                result=dispatch(parser().parse_args(argv));response={'ok':result.get('status')!='FAILED','result':result}
            except (Exception,SystemExit) as error:response={'ok':False,'error':str(error)}
            print(json.dumps(response,ensure_ascii=False),flush=True)
        return 0
    try:
        result=dispatch(args);print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('status')=='FAILED' else 0
    except Exception as error:print(json.dumps({'status':'FAILED','error':str(error)},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
