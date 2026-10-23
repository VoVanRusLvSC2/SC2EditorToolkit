import argparse,base64,io,json,os,sys
from pathlib import Path
from .modules import capabilities
from .runtime import watch_frozen_parent
from .session import Worker
from .jobs import JobQueue,OPERATIONS

PROPERTIES={'editor_path':{'type':'string','description':'Owned startup: original x64 Editor EXE or installation directory. Defaults to SC2_EDITOR_PATH, registry and standard install discovery. Supported binary required; restart to change installation.'},'template':{'type':'string'},'map':{'type':'string'},'startup_module':{'type':'string','enum':['triggers','terrain','default'],'default':'triggers'},'triggers_xml':{'type':'string'},'triggers_file':{'type':'string'},
 'render_backend':{'type':'string','enum':['auto','legacy','vulkan'],'description':'Owned worker startup only: auto uses bundled pinned DXVK/Vulkan when present, otherwise system D3D9. Restart the owned worker to change backend.'},
 'scope':{'type':'string'},'context_label':{'type':'string'},'locale':{'type':'string'},'compile':{'type':'boolean'},
 'output':{'type':'string'},'overwrite':{'type':'boolean'},'scene':{'type':'string'},'camera':{'type':'string'},
 'map_camera_id':{'type':'string','description':'Exact saved ObjectCamera ID from sc2_list_map_cameras; applies only to Terrain capture'},
 'time_ms':{'type':'number','minimum':0,'maximum':600000},'allow_empty':{'type':'boolean'},
 'size':{'type':'integer','enum':[512,1024,2048,4096],'default':2048},'include_units':{'type':'boolean','default':True},'include_doodads':{'type':'boolean','default':True},
 'query':{'type':'string','maxLength':256},'kinds':{'type':'array','minItems':1,'items':{'type':'string','enum':['unit','doodad','point','camera','other']}},
 'owner':{'type':'integer','minimum':0,'maximum':255},'offset':{'type':'integer','minimum':0,'maximum':500000},'limit':{'type':'integer','minimum':1,'maximum':500,'default':100},
 'bounds':{'type':'object','properties':{k:{'type':'number'} for k in ('left','bottom','right','top')},'required':['left','bottom','right','top'],'additionalProperties':False},
 'baseline_template':{'type':'string','description':'Optional healthy startup archive for diagnosing a failing map in a fresh worker'},
 'include_diffs':{'type':'boolean','default':False,'description':'Include bounded textual component diffs in the downloadable comparison report'},
 'start_ms':{'type':'number','minimum':0,'maximum':600000},'end_ms':{'type':'number','minimum':0,'maximum':600000},
 'fps':{'type':'integer','minimum':1,'maximum':60},'keep_frames':{'type':'boolean'},'include_audio':{'type':'boolean','default':True},
 'operation':{'type':'string','enum':list(OPERATIONS)},'arguments':{'type':'object'},'job_id':{'type':'string'},
 'timeout_seconds':{'type':'number','minimum':1,'maximum':14400},'wait_ms':{'type':'integer','minimum':0,'maximum':30000},
 'save_reopen':{'type':'boolean','default':False},'catalog':{'type':'string'},'object_id':{'type':'string'},
 'field_offset':{'type':'integer','minimum':0,'maximum':100000},'field_limit':{'type':'integer','minimum':1,'maximum':500},'include_xml':{'type':'boolean','default':False}}
TOOLS=[
 ('sc2_submit_job','Queue one operation on the owned hidden Editor. Returns immediately; use job status/wait. FIFO, bounded queue, deadline, no automatic replay.','jobs.submit',['operation']),
 ('sc2_job_status','Read queued/running/finished job state and native phase without controlling the desktop.','jobs.status',['job_id']),
 ('sc2_job_wait','Wait up to 30 seconds for a job; may return RUNNING.','jobs.wait',['job_id']),
 ('sc2_job_cancel','Cancel a queued job, or discard only the owned private Editor to stop a running job. Running cancellation can leave private artifacts; no automatic retry.','jobs.cancel',['job_id']),
 ('sc2_check_map','Create an immutable report bound to the source SHA-256: original loading/Data diagnostics, Galaxy generation, native compilation and Galaxy export; optional private save/reopen. Unknown is not success.','check_document',[]),
 ('sc2_read_data','Select exact catalog/object ID in the original Data editor and read native fields, inherited/effective UI values, original object columns and observed object source.','read_data',['catalog','object_id']),
 ('sc2_data_links','Read original Editor object explorer links for an exact catalog/object ID. Returns observed native links, not a reconstructed XML graph.','data_links',['catalog','object_id']),
 ('sc2_check_resources','Check the selected Model main file in the original merged Archive Browser with native path-token resolution and diagnostics. Binary integrity, nested resources and other catalogs remain unvalidated.','check_resources',['catalog','object_id']),
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
 ('sc2_capture_terrain','Capture original Terrain to PNG in the background. Optional map opens a private .SC2Map; map_camera_id selects a unique saved camera with native target readback. Captures editor placements; does not execute Galaxy triggers or play a trigger cinematic. Cutscene time_ms/camera remain separate.','capture_terrain',[]),
 ('sc2_list_map_cameras','List saved ObjectCamera IDs, names, original attributes and CameraValue entries without starting Editor. Supply map or use the current saved map. Optional locale resolves GameStrings names. Runtime-created/moved cameras and trigger playback are outside this operation.','list_map_cameras',[]),
 ('sc2_export_map_image','Export the COMPLETE map from above with the original Editor Map Image Export: full bounds, all quadrants, 90 degree camera, terrain/water/shadows and units/doodads enabled by default. Unit and doodad visibility are independent original-model filters with native readback before PNG publication. Optional map autostarts a hidden worker. size is horizontal pixel resolution; native bounds determine height. Returns full PNG download plus bounded preview.','export_map_image',[]),
 ('sc2_export_video','Export the entire cutscene or start_ms..end_ms (exclusive) to H.264 MP4 with the selected camera. Original native frames and original Editor audio (AAC by default; include_audio=false for silent video), requires FFmpeg/ffprobe.','export_video',[]),
 ('sc2_search_objects','Read saved map Objects XML without starting an Editor. Supply map or use this worker current saved .SC2Map. Search case-insensitive query over saved ID/type/name, kinds, owner and optional map XY bounds; paginate with offset/limit. Returns original XYZ (Z may be a placement offset), unique snapshot object keys and map SHA-256. Excludes unsaved/live/runtime-created objects and inherited dependency placements.','search_objects',[]),
 ('sc2_capture_map_region','EXPERIMENTAL: capture a map XY rectangle from the original hidden full-map overhead export. Required bounds={left,bottom,right,top}; optional map, size (resolution of the FULL map), include_units/include_doodads and output. Crops original pixels without upscaling or input injection. Native render and north/up coordinate calibration remain pending live test; coordinateMappingValidated is false. Returns PNG download and bounded preview.','capture_map_region',['bounds']),
 ('sc2_validate_document','Load a private map/mod copy and its original Data module in an owned hidden Editor. Return per-operation native before/after log snapshots, new errors/warnings, explicitly observed IDs and unclassified messages. Old messages are preserved as baseline. Unreadable/ambiguous logs remain unknown; this is not exhaustive runtime validation. Optional baseline_template provides a healthy startup archive.','validate_document',[]),
 ('sc2_save_reopen','Load a private saved map/mod, serialize it using original File/Save As, close it, reopen the saved archive from disk and compare every enumerated MPQ component by locale/name/bytes/SHA-256. Return per-phase new native diagnostics and a downloadable comparison report; include_diffs requests bounded text diffs. Optional output exports only the verified native saved archive, never the supplied source.','save_reopen_document',[]),
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
    p.add_argument('--editor',help='Original Editor EXE/install directory; otherwise SC2_EDITOR_PATH or discovery')
    args=p.parse_args();worker=Worker(args.work,editor_path=args.editor);jobs=JobQueue(worker);initialized=False
    try:
        for line in sys.stdin:
            ident=None
            try:
                request=json.loads(line);ident=request.get('id');method=request.get('method');params=request.get('params',{})
                if 'id' not in request:continue
                if method=='initialize':
                    version=params.get('protocolVersion','2025-06-18')
                    if version not in ('2024-11-05','2025-03-26','2025-06-18'):version='2025-06-18'
                    result={'protocolVersion':version,'serverInfo':{'name':'sc2-native-toolkit','version':'0.13.0-rc.1'},'capabilities':{'tools':{'listChanged':False}},
                        'instructions':'Use an installed SC2 Editor. Load a cutscene using scene and a map/mod template, select a unique camera and time_ms, then capture its renderer. Time is sampled on the native 33 ms frame grid. Every editor window remains on a private desktop.'};initialized=True
                elif method=='ping':result={}
                elif not initialized:raise ValueError('Initialize the MCP session first')
                elif method=='tools/list':
                    result={'tools':[{'name':name,'description':description,'inputSchema':{'type':'object','properties':PROPERTIES,'required':required,'additionalProperties':False}} for name,description,target,required in TOOLS]}
                elif method=='tools/call':
                    name=params.get('name');tool=next((t for t in TOOLS if t[0]==name),None)
                    if not tool:raise ValueError('Unknown tool')
                    try:
                        arguments=params.get('arguments',{})
                        data=capabilities() if tool[2] is None else getattr(jobs,tool[2].split('.',1)[1])(arguments) if tool[2].startswith('jobs.') else jobs.run(tool[2],arguments)
                        compact={k:v for k,v in data.items() if k!='galaxy'}
                        content=[{'type':'text','text':json.dumps(compact,ensure_ascii=False)}]
                        if name in ('sc2_capture_frame','sc2_capture_terrain') and data.get('artifact'):
                            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(data['artifact']['path']).read_bytes()).decode('ascii')})
                        if name in ('sc2_export_video','sc2_export_map_image','sc2_capture_map_region') and data.get('preview'):
                            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(data['preview']['path']).read_bytes()).decode('ascii')})
                        if name=='sc2_check_resources' and data.get('previewFrame',{}).get('artifact'):
                            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(data['previewFrame']['artifact']['path']).read_bytes()).decode('ascii')})
                        result={'content':content,'structuredContent':compact,'isError':data.get('status')=='FAILED'}
                    except Exception as e:result={'content':[{'type':'text','text':str(e)}],'isError':True}
                else:
                    sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}})+'\n');sys.stdout.flush();continue
                response={'jsonrpc':'2.0','id':ident,'result':result}
            except Exception as e:response={'jsonrpc':'2.0','id':ident,'error':{'code':-32602,'message':str(e)}}
            sys.stdout.write(json.dumps(response,ensure_ascii=False)+'\n');sys.stdout.flush()
    finally:jobs.close();worker.close()
    return 0
