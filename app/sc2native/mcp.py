import argparse,base64,io,json,os,sys
from pathlib import Path
from .modules import capabilities
from .runtime import watch_frozen_parent
from .session import Worker

PROPERTIES={'template':{'type':'string'},'map':{'type':'string'},'triggers_xml':{'type':'string'},'triggers_file':{'type':'string'},
 'scope':{'type':'string'},'context_label':{'type':'string'},'locale':{'type':'string'},'compile':{'type':'boolean'},
 'output':{'type':'string'},'overwrite':{'type':'boolean'},'scene':{'type':'string'},'camera':{'type':'string'},
 'time_ms':{'type':'number','minimum':0,'maximum':600000},'allow_empty':{'type':'boolean'},
 'start_ms':{'type':'number','minimum':0,'maximum':600000},'end_ms':{'type':'number','minimum':0,'maximum':600000},
 'fps':{'type':'integer','minimum':1,'maximum':60},'keep_frames':{'type':'boolean'}}
TOOLS=[
 ('sc2_modules','List native modules and implemented capabilities.',None,[]),
 ('sc2_editor_start','Start an owned hidden original SC2 Editor using a map/mod template.','start',['template']),
 ('sc2_open_document','Open a private copy of .SC2Map/.SC2Mod with the original loader.','open_document',['map']),
 ('sc2_convert_xml','Load complete Triggers XML, generate Galaxy using the original Editor and optionally compile.','execute',['template']),
 ('sc2_compile_all','Generate current native script and invoke original Compile All; return compiler/editor diagnostics.','compile_current',[]),
 ('sc2_export_galaxy','Export the last native Galaxy bytes to a file. Existing files require overwrite=true.','export_galaxy',[]),
 ('sc2_diagnostics','Read the current Messages/Console controls from the owned editor.','diagnostics',[]),
 ('sc2_cutscene_open','Load a private copy of a native cutscene in the hidden original Editor. Supply scene and optional template.','cutscene_open',[]),
 ('sc2_cutscene_seek','Select a unique native camera and time_ms. Return actual Editor time and confirmation.','cutscene_seek',[]),
 ('sc2_capture_frame','Capture the selected cutscene renderer to PNG. Optional camera/time_ms selects a frame first. Black frames fail by default.','capture_frame',[]),
 ('sc2_export_video','Export the entire cutscene or start_ms..end_ms (exclusive) to H.264 MP4 with the selected camera. Original native frames, silent video, requires FFmpeg/ffprobe.','export_video',[]),
]

def restore_pipes():
    if os.name!='nt':return
    import ctypes,msvcrt
    kernel=ctypes.WinDLL('kernel32');kernel.GetStdHandle.argtypes=[ctypes.c_ulong];kernel.GetStdHandle.restype=ctypes.c_void_p
    for attr,number,flags,mode in [('stdin',-10,os.O_RDONLY,'r'),('stdout',-11,os.O_WRONLY,'w'),('stderr',-12,os.O_WRONLY,'w')]:
        if getattr(sys,attr) is not None:continue
        handle=kernel.GetStdHandle(number&0xffffffff)
        if not handle or handle==ctypes.c_void_p(-1).value:continue
        fd=msvcrt.open_osfhandle(handle,flags|os.O_BINARY)
        setattr(sys,attr,io.TextIOWrapper(os.fdopen(fd,mode+'b',buffering=0),encoding='utf8',newline='\n',write_through=True))

def main():
    restore_pipes();watch_frozen_parent()
    if sys.stdin is None or sys.stdout is None:return 2
    if hasattr(sys.stdin,'reconfigure'):sys.stdin.reconfigure(encoding='utf8')
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8',newline='\n')
    p=argparse.ArgumentParser();p.add_argument('--work',default=str((Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2])/'mcp-data'))
    args=p.parse_args();worker=Worker(args.work);initialized=False
    try:
        for line in sys.stdin:
            ident=None
            try:
                request=json.loads(line);ident=request.get('id');method=request.get('method');params=request.get('params',{})
                if 'id' not in request:continue
                if method=='initialize':
                    version=params.get('protocolVersion','2025-06-18')
                    if version not in ('2024-11-05','2025-03-26','2025-06-18'):version='2025-06-18'
                    result={'protocolVersion':version,'serverInfo':{'name':'sc2-native-toolkit','version':'0.4.0'},'capabilities':{'tools':{'listChanged':False}},
                        'instructions':'Use an installed SC2 Editor. Load a cutscene using scene and a map/mod template, select a unique camera and time_ms, then capture its renderer. Time is sampled on the native 33 ms frame grid. Every editor window remains on a private desktop.'};initialized=True
                elif method=='ping':result={}
                elif not initialized:raise ValueError('Initialize the MCP session first')
                elif method=='tools/list':
                    result={'tools':[{'name':name,'description':description,'inputSchema':{'type':'object','properties':PROPERTIES,'required':required,'additionalProperties':False}} for name,description,target,required in TOOLS]}
                elif method=='tools/call':
                    name=params.get('name');tool=next((t for t in TOOLS if t[0]==name),None)
                    if not tool:raise ValueError('Unknown tool')
                    try:
                        data=capabilities() if tool[2] is None else getattr(worker,tool[2])(params.get('arguments',{}))
                        compact={k:v for k,v in data.items() if k!='galaxy'}
                        content=[{'type':'text','text':json.dumps(compact,ensure_ascii=False)}]
                        if name=='sc2_capture_frame' and data.get('artifact'):
                            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(data['artifact']['path']).read_bytes()).decode('ascii')})
                        if name=='sc2_export_video' and data.get('preview'):
                            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(data['preview']['path']).read_bytes()).decode('ascii')})
                        result={'content':content,'structuredContent':compact,'isError':data.get('status')=='FAILED'}
                    except Exception as e:result={'content':[{'type':'text','text':str(e)}],'isError':True}
                else:
                    sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}})+'\n');sys.stdout.flush();continue
                response={'jsonrpc':'2.0','id':ident,'result':result}
            except Exception as e:response={'jsonrpc':'2.0','id':ident,'error':{'code':-32602,'message':str(e)}}
            sys.stdout.write(json.dumps(response,ensure_ascii=False)+'\n');sys.stdout.flush()
    finally:worker.close()
    return 0
