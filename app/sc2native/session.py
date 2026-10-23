from .runtime import *
from editor_installation import resolve_editor,validate_editor
from .artifacts import ArtifactStore
from .diagnostics import parse_native_diagnostics,operation_diagnostics
from .cutscenes import scene_file,seek_arguments,scene_duration
from .render_backend import requested_backend,select_backend,render_environment
class Worker:
    def _background_result(self,result):
        state=getattr(self,'state',None) or {}
        if state.get('renderBackend'):result.update(renderBackend=state['renderBackend'],instanceId=state.get('instanceId'))
        result['desktopObservation']=self.monitor.snapshot()
        observed=result['desktopObservation']
        if observed['visibleWindowsOnUserDesktopPeak'] or observed['editorForegroundSamples']:
            result.update(status='FAILED',error='Hidden desktop invariant failed',requestedCutsceneFrameVerified=False)
            if 'requestedTerrainFrameVerified' in result:result['requestedTerrainFrameVerified']=False
            if 'wholeMapVerified' in result:result['wholeMapVerified']=False
            if 'regionCropVerified' in result:result['regionCropVerified']=False
        return result
    def __init__(self,work,editor_path=None):
        self.editor_preference=editor_path
        self.work=Path(work).resolve();self.work.mkdir(parents=True,exist_ok=True)
        import msvcrt
        self._work_lock=(self.work/'.server.lock').open('a+b')
        try:
            self._work_lock.seek(0,2)
            if self._work_lock.tell()==0:self._work_lock.write(b'\0');self._work_lock.flush()
            self._work_lock.seek(0);msvcrt.locking(self._work_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            self._work_lock.close();raise RuntimeError('Work directory is already in use; select a different --work for each server')
        self.state=None;self.monitor=None;self.lock=threading.Lock()
        self.artifacts=ArtifactStore(self.work/'exports');self.last_result=None;self.scene=None
        self.video_progress=None;self.video_cancel=threading.Event()
        self.operation_abort=threading.Event();self.operation_progress={};self.operation_id=None
        self.job_name='Local\\SC2NativeApi-'+uuid.uuid4().hex
        self.job_handle=kernel.CreateJobObjectW(None,self.job_name)
        limit=ExtendedLimit();limit.Basic.Flags=0x2000
        if not self.job_handle or not kernel.SetInformationJobObject(self.job_handle,9,ctypes.byref(limit),ctypes.sizeof(limit)):
            raise OSError(ctypes.get_last_error(),'Cannot create owned-worker lifetime job')
        atexit.register(self.close)
    def alive(self):return bool(self.state and process_time(self.state['pid'])==self.state['createTimeFiletime'])
    def begin_operation(self,identifier):
        self.operation_id=identifier;self.operation_abort.clear();self.video_cancel.clear();self.operation_progress={'phase':'starting'}
    def _check_abort(self):
        if getattr(self,'operation_abort',None) and self.operation_abort.is_set():raise RuntimeError('Owned operation was cancelled or exceeded its deadline')
    def abort_owned_operation(self,reason):
        self.operation_abort.set();self.video_cancel.set()
        self.operation_progress={**self.operation_progress,'stopRequested':reason}
        state=self.state
        if state and process_time(state['pid'])==state['createTimeFiletime']:
            handle=kernel.OpenProcess(0x1000|1,False,state['pid'])
            if handle:
                if process_time(state['pid'])==state['createTimeFiletime']:kernel.TerminateProcess(handle,0)
                kernel.CloseHandle(handle)
    def ensure(self,template,startup_module='triggers',render_backend=None,editor_path=None):
        self._check_abort()
        if startup_module not in ('triggers','terrain','default'):raise ValueError('startup_module must be triggers, terrain or default')
        requested=requested_backend(render_backend)
        if self.alive():
            if editor_path is not None and not resolve_editor(editor_path).samefile(self.state['editorPath']):
                raise ValueError('The owned worker uses another Editor installation; restart that API/MCP worker to change it')
            if render_backend is not None and requested!='auto' and requested!=self.state.get('renderBackend','legacy'):
                raise ValueError('The owned worker already uses another render backend; restart that API/MCP worker to change it')
            return
        selected=select_backend(RES,requested)
        self.operation_progress={'phase':'starting-owned-editor'}
        installation=validate_editor(resolve_editor(editor_path if editor_path is not None else getattr(self,'editor_preference',None)))
        self.scene=None
        if self.monitor:self.monitor.stop();self.monitor=None
        directory=self.work/'workers'/uuid.uuid4().hex;directory.mkdir(parents=True)
        # Seed is a private archive copy. Never ask the worker to edit the user's source.
        seed=directory/('Seed'+Path(template).suffix);shutil.copyfile(template,seed)
        startup=directory/'startup'
        command=[str(RES/'HiddenEditorHost.exe'),'--document',str(seed),'--out',str(startup),'--timeout','240','--job-name',self.job_name,'--module',startup_module,'--render-backend',selected,'--editor',installation['path']]
        with (directory/'host.stdout.log').open('wb') as out,(directory/'host.stderr.log').open('wb') as err:
            child=subprocess.Popen(command,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW,env=render_environment(selected,directory))
            # Start monitoring as soon as the host publishes its child PID.
            while child.poll() is None:
                state_path=startup/'state.json'
                if state_path.is_file() and self.monitor is None:
                    try:
                        state=json.loads(state_path.read_text());self.state=state;self.monitor=Observation(state['pid'])
                    except (OSError,ValueError):pass
                if getattr(self,'operation_abort',None) and self.operation_abort.is_set():self.abort_owned_operation('STARTUP_ABORT')
                time.sleep(.05)
        state_path=startup/'state.json'
        if not state_path.is_file():raise RuntimeError('Hidden startup failed; see '+str(directory))
        self.state=json.loads(state_path.read_text())
        if child.returncode or self.state['status']!='HIDDEN_EDITOR_READY':
            reason='Hidden Editor not ready: '+str(self.state['status'])+'; hostExitCode='+str(child.returncode)+'; '+str(directory)
            self._reset_owned_editor()
            raise RuntimeError(reason)
        self.state['currentDocument']=seed.name;self.state['documentPath']=str(seed);self.state['startupReport']=str(state_path);self.state['renderBackend']=selected;self.state['editorPath']=installation['path'];self.state['editorInfo']=installation
        if self.monitor is None:self.monitor=Observation(self.state['pid'])
        oracle.save(self.work/'worker.json',self.state)
    def _reset_owned_editor(self):
        if self.alive():
            handle=kernel.OpenProcess(0x1000|1,False,self.state['pid'])
            if handle:
                # Creation time protects against terminating an unrelated reused PID.
                if process_time(self.state['pid'])==self.state['createTimeFiletime']:kernel.TerminateProcess(handle,0)
                kernel.CloseHandle(handle)
        if self.monitor:self.monitor.stop();self.monitor=None
        self.state=None;self.scene=None;self.last_result=None
    def close(self):
        self._reset_owned_editor()
        if self.job_handle:kernel.CloseHandle(self.job_handle);self.job_handle=None
        handle=getattr(self,'_work_lock',None)
        if handle and not handle.closed:handle.close()
    def execute(self,request,_locked=False):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy; serialize requests')
        try:
            self.last_result=None
            if 'compile' in request and type(request['compile']) is not bool:raise ValueError('compile must be a JSON boolean')
            template=Path(request.get('template') or request.get('map','')).resolve(strict=True)
            if not template.is_file() or template.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('template must be an existing .SC2Map or .SC2Mod archive')
            request_dir=self.work/'requests'/uuid.uuid4().hex;request_dir.mkdir(parents=True)
            xml_path=request_dir/'Triggers.xml'
            if 'triggers_xml' in request:
                text=request['triggers_xml']
                if not isinstance(text,str):raise ValueError('triggers_xml must be a string')
                xml_path.write_bytes(text.encode('utf-8'))
            elif request.get('triggers_file'):shutil.copyfile(Path(request['triggers_file']).resolve(strict=True),xml_path)
            else:
                result=subprocess.run([str(files.mpq_tool()),'read','Triggers',str(template)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
                if result.returncode:raise ValueError('Cannot read Triggers from the supplied map/mod')
                xml_path.write_bytes(result.stdout)
            files.checked_xml(xml_path)
            self.ensure(template,request.get('startup_module','triggers'),request.get('render_backend'),editor_path=request.get('editor_path'))
            oracle.ACTIVE_DESKTOP=self.state['desktop']
            args=SimpleNamespace(template=str(template),triggers=str(xml_path),job=str(request_dir/'job'),
                trigger_strings=request.get('trigger_strings'),game_strings=request.get('game_strings'),locale=request.get('locale','enUS'),
                scope=request.get('scope','mapRoot'),context_label=request.get('context_label'),editor=self.state['editorPath'],mpqcli=None,
                pid=self.state['pid'],current_document=self.state['currentDocument'],marker=request.get('marker',''),
                expect_text=request.get('expect_text',[]),compile=bool(request.get('compile',True)))
            args.check_abort=self._check_abort
            args.progress=lambda phase,directory:setattr(self,'operation_progress',{'phase':phase,'evidenceDirectory':directory})
            result=oracle.convert(args)
            # Load may succeed even if generation/compilation subsequently fails.
            manifest=Path(args.job)/'manifest.json'
            if result.get('currentDocumentPath'):
                self.scene=None
                self.state['currentDocument']=Path(result['currentDocumentPath']).name
                self.state['documentPath']=result['currentDocumentPath']
                oracle.save(self.work/'worker.json',self.state)
            result['hiddenWorker']={k:self.state.get(k) for k in ('pid','desktop','startupReport','instanceId','renderBackend')}
            result['desktopObservation']=self.monitor.snapshot()
            observed=result['desktopObservation']
            # A person may lock/unlock Windows while this job runs. Desktop
            # changes are observational; this program never calls SwitchDesktop.
            if observed['visibleWindowsOnUserDesktopPeak'] or observed['editorForegroundSamples']:
                result.update(status='FAILED',error='Hidden desktop invariant failed')
            if result.get('nativeGenerationVerified'):
                result['galaxy']=Path(result['output']).read_bytes().decode('utf-8')
                self.last_result=result
            if (Path(args.job)/'03-compile').exists():result['diagnostics']=parse_native_diagnostics(Path(args.job)/'03-compile',result.get('steps',{}).get('compile'))
            result['operationDiagnostics']={}
            for stage in result.get('stepEvidence',{}).values():
                evidence=Path(args.job)/stage
                if (evidence/'result.json').is_file():
                    native=json.loads((evidence/'result.json').read_text(encoding='utf8'))
                    if native.get('operation') not in ('load','save-document','generate','compile'):continue
                    result['operationDiagnostics'][stage]=operation_diagnostics(evidence,native)
            result['newMapDataErrors']=[{'phase':name,**entry} for name,diagnostic in result['operationDiagnostics'].items() for entry in diagnostic['newErrors']]
            if result['newMapDataErrors']:result.update(status='FAILED',error='New native map/Data errors were reported; compiler results remain separate')
            fatal=not result.get('currentDocumentPath') or any(n.get('exceptionCode') for n in result.get('steps',{}).values())
            if result['status']=='FAILED' and fatal:
                self._reset_owned_editor();result['ownedWorkerReset']=True
            oracle.save(request_dir/'api-result.json',result)
            return result
        finally:
            if not _locked:self.lock.release()
    def open_document(self,request,_locked=False):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy; serialize requests')
        try:
            self.last_result=None
            source=Path(request.get('map') or request.get('template','')).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('map must be an existing .SC2Map or .SC2Mod archive')
            directory=self.work/'opens'/uuid.uuid4().hex;directory.mkdir(parents=True)
            archive=directory/('NativeOpen-'+directory.name[:12]+source.suffix);shutil.copyfile(source,archive)
            original_hash=files.sha(source)
            if files.sha(archive)!=original_hash:raise RuntimeError('Document copy does not match original')
            self.ensure(archive,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'));oracle.ACTIVE_DESKTOP=self.state['desktop']
            try:native=oracle.native_step(directory,'01-load',self.state['pid'],self.state['currentDocument'],map_path=archive,editor=self.state['editorPath'])
            except oracle.NativeStepError as error:
                result={'status':'FAILED','error':str(error),'source':str(source),'openedCopy':str(archive),
                    'sourceUnchanged':files.sha(source)==original_hash,'nativeLoad':error.native_result,
                    'loadDiagnostics':operation_diagnostics(directory/'01-load',error.native_result)}
                self._background_result(result);self._reset_owned_editor();oracle.save(directory/'open-result.json',result);return result
            if not native['mapLoaded']:raise RuntimeError('Native loading not confirmed')
            self.state['currentDocument']=archive.name;oracle.save(self.work/'worker.json',self.state)
            self.state['documentPath']=str(archive);self.last_result=None
            self.scene=None
            result={'status':'HIDDEN_NATIVE_DOCUMENT_OPENED','source':str(source),'openedCopy':str(archive),
                'sourceUnchanged':files.sha(source)==original_hash,'nativeLoad':native,'desktopObservation':self.monitor.snapshot(),
                'loadDiagnostics':operation_diagnostics(directory/'01-load',native)}
            observed=result['desktopObservation']
            if observed['visibleWindowsOnUserDesktopPeak'] or observed['editorForegroundSamples']:
                result.update(status='FAILED',error='Hidden desktop invariant failed')
            oracle.save(directory/'open-result.json',result)
            return result
        finally:
            if not _locked:self.lock.release()

    def _native(self,directory,operation,scope='mapRoot',context='',**options):
        self._check_abort()
        if not self.alive():raise RuntimeError('Start or open a document first')
        self.operation_progress={'phase':operation,'evidenceDirectory':str(directory)}
        oracle.ACTIVE_DESKTOP=self.state['desktop']
        return oracle.native_step(directory,'01-'+operation,self.state['pid'],self.state['currentDocument'],context=context,scope=scope,editor=self.state['editorPath'],**options)

    def start(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            template=Path(request.get('template') or request.get('map','')).resolve(strict=True)
            if not template.is_file() or template.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('Existing .SC2Map/.SC2Mod template required')
            self.ensure(template,request.get('startup_module','triggers'),request.get('render_backend'),editor_path=request.get('editor_path'))
            directory=self.work/'editor-actions'/uuid.uuid4().hex;directory.mkdir(parents=True)
            try:native=self._native(directory,'inspect')
            except oracle.NativeStepError as error:
                result={'status':'FAILED','error':str(error),'failureStage':'inspectCurrent','failureKind':
                    'NATIVE_CONTROLLER_FAILED' if (error.native_result or {}).get('status')=='NATIVE_CONTROLLER_FAILED' else 'NATIVE_STEP_FAILED',
                    'failureNative':error.native_result,'failureEvidence':str(error.evidence_directory),
                    'desktopObservation':self.monitor.snapshot(),'ownedWorkerReset':True,'automaticRetry':False}
                self._reset_owned_editor();oracle.save(directory/'start-result.json',result);return result
            return {'status':'HIDDEN_EDITOR_STARTED','pid':self.state['pid'],'document':self.state['currentDocument'],
                'instanceId':self.state.get('instanceId'),'renderBackend':self.state['renderBackend'],
                'editorInfo':self.state.get('editorInfo'),'native':native,'desktopObservation':self.monitor.snapshot()}
        finally:self.lock.release()

    def _context(self,request):
        import xml.etree.ElementTree as ET
        command=[str(files.mpq_tool()),'read','Triggers',self.state['documentPath']]
        p=subprocess.run(command,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        if p.returncode:raise RuntimeError('Cannot resolve current document trigger scope')
        root=ET.fromstring(p.stdout);scope=request.get('scope')
        if not scope:
            libs=root.findall('Library')
            scope='library:'+libs[0].get('Id') if not root.findall('./Root/Item') and len(libs)==1 else 'mapRoot'
        name=request.get('context_label')
        if not name:
            from .components import read_string_table
            locale=request.get('locale','enUS')
            strings=read_string_table(self.state['documentPath'],files.mpq_tool(),locale+'.SC2Data/LocalizedData/TriggerStrings.txt',self.work)
            name=files.context_label(root,scope,strings)
        if not name:raise ValueError('Supply context_label for the authored root/library')
        return scope,name

    def compile_current(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            self.last_result=None
            if not self.alive():raise RuntimeError('Start/open a document first')
            scope,context=self._context(request)
            # Reuse the proven native pipeline with the document's own XML.
            options=dict(request,template=self.state['documentPath'],scope=scope,context_label=context,compile=True)
            options.pop('triggers_xml',None);options.pop('triggers_file',None)
            return self.execute(options,_locked=True)
        finally:self.lock.release()

    def export_galaxy(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            if not self.last_result or not self.last_result.get('nativeGenerationVerified'):raise RuntimeError('Generate/compile current script first')
            source=Path(self.last_result['output']);data=source.read_bytes()
            if hashlib.sha256(data).hexdigest()!=self.last_result['sourceSha256']:raise RuntimeError('Generated source changed after native reading')
            entry=self.artifacts.export(data,output=request.get('output'),overwrite=bool(request.get('overwrite',False)))
            return {'status':'GALAXY_EXPORTED','artifact':entry,'nativeCompilePassed':self.last_result['nativeCompilePassed']}
        finally:self.lock.release()

    def diagnostics(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            directory=self.work/'diagnostics'/uuid.uuid4().hex;directory.mkdir(parents=True)
            native=self._native(directory,'diagnostics')
            return {'status':'EDITOR_DIAGNOSTICS_READ','native':native,**parse_native_diagnostics(directory/'01-diagnostics',native),
                'operationDiagnostics':operation_diagnostics(directory/'01-diagnostics',native)}
        finally:self.lock.release()

    def validate_document(self,request):
        from .document_validation import validate_document
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:return validate_document(self,request)
        finally:self.lock.release()

    def check_document(self,request):
        from .report import check_document
        return check_document(self,request)

    def read_data(self,request):
        from .data import inspect_data
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:return inspect_data(self,request)
        finally:self.lock.release()

    def data_links(self,request):
        from .data import inspect_data
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:return inspect_data(self,request,'links')
        finally:self.lock.release()

    def check_resources(self,request):
        from .data import inspect_data
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:return inspect_data(self,request,'resources')
        finally:self.lock.release()

    def save_reopen_document(self,request):
        from .document_validation import validate_document
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:return validate_document(self,request,roundtrip=True)
        finally:self.lock.release()

    def cutscene_open(self,request,_locked=False):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            source=None
            if request.get('scene'):source,cameras=scene_file(request['scene'])
            if not self.alive():
                template=request.get('template') or request.get('map')
                if not template:raise ValueError('Start a worker or supply a map/mod template')
                template=Path(template).resolve(strict=True)
                if not template.is_file() or template.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('Existing .SC2Map/.SC2Mod template required')
                self.ensure(template,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'))
            directory=self.work/'cutscenes'/uuid.uuid4().hex;directory.mkdir(parents=True)
            native=self._native(directory,'cutscene')
            result={'status':'CUTSCENE_MODULE_OPENED','native':native,'timelineControl':True}
            if source:
                original_hash=files.sha(source);copy=directory/source.name;shutil.copyfile(source,copy)
                if files.sha(copy)!=original_hash:raise RuntimeError('Scene changed while copying')
                self.scene=None
                loaded=oracle.native_step(directory,'02-scene-load',self.state['pid'],self.state['currentDocument'],map_path=copy,editor=self.state['editorPath'])
                if not loaded.get('sceneLoaded'):raise RuntimeError('Original scene loading not confirmed')
                self.scene={'source':str(source),'copy':str(copy),'sha256':original_hash,'cameras':cameras,'frame':None,**scene_duration(copy)}
                result.update(status='CUTSCENE_LOADED',scene=self.scene.copy(),load=loaded,sourceUnchanged=files.sha(source)==original_hash)
            return self._background_result(result)
        finally:
            if not _locked:self.lock.release()

    def cutscene_seek(self,request,_locked=False,_advance=False):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            if not self.alive() or not self.scene:raise RuntimeError('Load a cutscene first')
            camera,time_ms=seek_arguments(request)
            directory=self.work/'cutscenes'/uuid.uuid4().hex;directory.mkdir(parents=True)
            oracle.ACTIVE_DESKTOP=self.state['desktop']
            self.scene['frame']=None
            native=oracle.native_step(directory,'01-scene-advance' if _advance else '01-scene-seek',self.state['pid'],self.state['currentDocument'],camera=camera,time_ms=time_ms,editor=self.state['editorPath'])
            if not native.get('cameraConfirmed') or not native.get('timeConfirmed'):raise RuntimeError('Native camera/time not confirmed')
            self.scene['frame']={'camera':camera,'requestedTimeMs':time_ms,'actualTimeMs':native['actualTimeMs'],'nativeStatus':native['sceneStatus'],'viewport':native['viewport'],
                'timeResolutionMs':33,'timeReadbackResolutionMs':10,'cameraConfirmed':True,'timeConfirmed':True}
            result={'status':'CUTSCENE_FRAME_SELECTED','frame':self.scene['frame'].copy(),'editorInfo':self.state.get('editorInfo'),'native':native,'desktopObservation':self.monitor.snapshot()}
            self._background_result(result);oracle.save(directory/'selection.json',result);return result
        finally:
            if not _locked:self.lock.release()

    def capture_frame(self,request,_locked=False,_directory=None,_register=True,_attempts=8,_terrain=None):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            if not self.alive():raise RuntimeError('Start/open the editor first')
            if _terrain is None and ('camera' in request or 'time_ms' in request):self.cutscene_seek(request,_locked=True)
            directory=Path(_directory) if _directory else self.work/'frames'/uuid.uuid4().hex;directory.mkdir(parents=True)
            command=[str(RES/'RenderCapture.exe'),'--editor',self.state['editorPath'],'--pid',str(self.state['pid']),'--out',str(directory/'frame.png')]
            frame=None if _terrain is not None else self.scene and self.scene.get('frame')
            if _terrain is None and not frame:raise ValueError('Select a cutscene camera/time first; use terrain/capture for a map view')
            viewport=_terrain['viewport'] if _terrain is not None else frame['viewport']
            command+=['--viewport',str(viewport)]
            attempts=[]
            for attempt in range(_attempts):
                image=directory/('frame-'+str(attempt)+'.png');command[command.index('--out')+1]=str(image)
                run=subprocess.run(command,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90)
                if run.returncode:raise RuntimeError('Native frame capture failed: '+run.stdout.decode('utf8',errors='replace')+run.stderr.decode('utf8',errors='replace'))
                evidence=json.loads(run.stdout.decode('utf8'));attempts.append(evidence)
                if evidence.get('luminanceBins',0)>=8 and evidence.get('nonBlackPixels',0)>evidence.get('width',0)*evidence.get('height',0)//1000:break
                # Scene import/device resize can present cleared buffers while
                # assets stream. Wait for more frames at the SAME paused time.
                time.sleep(.2)
            artifact=self.artifacts.register_png(image) if _register else None
            result={'status':'RENDER_FRAME_CAPTURED','artifact':artifact,'native':evidence,
                'source':'original D3D9 backbuffer','desktopScreenshot':False,'timelineControl':_terrain is None,
                'desktopObservation':self.monitor.snapshot()}
            result['emptyFrame']=evidence.get('emptyFrame',None);result['captureAttempts']=attempts
            if not _register:result['capturePath']=str(image)
            result['imageHasDetail']=evidence.get('luminanceBins',0)>=8 and evidence.get('nonBlackPixels',0)>evidence.get('width',0)*evidence.get('height',0)//1000
            result['requestedCutsceneFrameVerified']=bool(frame and evidence.get('sourceWindow')==frame['viewport'] and result['imageHasDetail'])
            if frame:result['frame']=frame.copy()
            if frame and evidence.get('sourceWindow')!=frame['viewport']:result.update(status='FAILED',error='Capture did not match selected native viewport')
            if _terrain is not None:
                result.update(module='terrain',terrain=_terrain,requestedTerrainFrameVerified=bool(evidence.get('sourceWindow')==viewport and result['imageHasDetail']))
                if evidence.get('sourceWindow')!=viewport:result.update(status='FAILED',error='Capture did not match the original Terrain viewport')
            if (result['emptyFrame'] or not result['imageHasDetail']) and not request.get('allow_empty',False):result.update(status='FAILED',error='Original renderer returned a black or uniform frame')
            self._background_result(result)
            oracle.save(directory/'capture.json',result);return result
        finally:
            if not _locked:self.lock.release()

    def _prepare_terrain(self,request):
        supplied=request.get('map') or request.get('template')
        path=Path(supplied).resolve(strict=True) if supplied else Path(self.state['documentPath']) if self.alive() else None
        if path is None or not path.is_file() or path.suffix.lower()!='.sc2map':raise ValueError('Terrain operations require a .SC2Map; a mod has no terrain')
        original_hash=files.sha(path)
        if supplied:
            if self.alive():
                opened=self.open_document({'map':str(path),'render_backend':request.get('render_backend'),'editor_path':request.get('editor_path')},_locked=True)
                if opened['status']=='FAILED':raise RuntimeError(opened.get('error','Native opening failed; see load diagnostics'))
            else:self.ensure(path,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'))
        if files.sha(self.state['documentPath'])!=original_hash:raise RuntimeError('Opened private map does not match the source archive')
        return path,original_hash

    def capture_terrain(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            for key in ('overwrite','allow_empty'):
                if key in request and type(request[key]) is not bool:raise ValueError(key+' must be a JSON boolean')
            if 'output' in request:
                if not isinstance(request['output'],str) or not request['output'].strip():raise ValueError('output must be a nonempty PNG path')
                target=Path(request['output']).resolve()
                if target.suffix.lower()!='.png':raise ValueError('Terrain output must be a .png file')
                if target.exists() and not request.get('overwrite',False):raise FileExistsError(target)
            # Camera and time_ms refer to cutscenes; never silently reuse those
            # arguments for a terrain screenshot of a different module.
            if 'camera' in request or 'time_ms' in request:raise ValueError('Terrain capture uses the current native map view; cutscene camera/time_ms are not supported')
            selected=None
            if 'map_camera_id' in request:
                from .map_cameras import read_camera_records,choose_camera
                # Resolve/reject identity before launching the original Editor.
                source,digest,snapshot,query_dir=self._snapshot_map(request)
                selected=choose_camera(read_camera_records(snapshot,files.mpq_tool(),request.get('locale','enUS')),request['map_camera_id'])
                if selected['target'] is None:raise ValueError('Saved camera has no explicit valid CameraTarget XY')
            path,original_hash=self._prepare_terrain(request)
            if selected and original_hash!=digest:raise RuntimeError('Map changed after camera identity resolution')
            directory=self.work/'terrain'/uuid.uuid4().hex;directory.mkdir(parents=True)
            if selected:
                # Layer creation and palette binding finish in the original
                # outer GUI loop, between requests on this owned desktop.
                self._native(directory,'terrain-camera-layer',camera=selected['name'])
                time.sleep(.3)
                self._native(directory,'terrain-camera-select',camera=selected['name'])
                time.sleep(.3)
                native=self._native(directory,'terrain-camera',camera=selected['name'])
            else:native=self._native(directory,'terrain')
            if not native.get('viewport'):raise RuntimeError('Original Terrain viewport was not confirmed')
            if selected:
                from .map_cameras import verify_readback
                actual=native.get('mapCamera',{})
                verification=verify_readback(selected,actual)
            if self.scene:self.scene['frame']=None
            # Let the outer GUI loop present newly selected Terrain resources.
            time.sleep(.5)
            result=self.capture_frame(request,_locked=True,_directory=directory/'capture',_register=False,_attempts=20,_terrain={
                'viewport':native['viewport'],'document':self.state['currentDocument'],'nativeTitle':native['loadedTitle'],'view':'current native Terrain view'})
            result.update(nativeSelection=native,sourceUnchanged=files.sha(path)==original_hash)
            if selected:
                result['mapCamera']={'saved':selected,'actual':native['mapCamera'],'nativeSelectionVerified':True,
                    'verification':verification,
                    'triggerExecution':False,'scope':'saved map camera and editor placement state; no Galaxy/gameplay execution'}
            if not result['sourceUnchanged']:result.update(status='FAILED',error='Source map changed during capture')
            # Publish only after viewport, pixels and background checks passed.
            if result['status']!='FAILED':
                result['artifact']=self.artifacts.publish_file(result.pop('capturePath'),suffix='.png',mime='image/png',output=request.get('output'),overwrite=bool(request.get('overwrite',False)))
                result['status']='TERRAIN_FRAME_CAPTURED'
            oracle.save(directory/'terrain-result.json',result)
            return result
        finally:self.lock.release()

    def list_map_cameras(self,request):
        from .map_cameras import read_camera_records
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            source,digest,snapshot,directory=self._snapshot_map(request)
            cameras=read_camera_records(snapshot,files.mpq_tool(),request.get('locale','enUS'))
            if files.sha(source)!=digest:raise RuntimeError('Source map changed during camera enumeration')
            result={'status':'MAP_CAMERAS_LISTED','map':str(source),'mapSha256':digest,'cameras':cameras,
                    'count':len(cameras),'sourceUnchanged':True,'editorRequired':False,
                    'scope':'saved map cameras only; excludes cameras created or moved by running triggers'}
            oracle.save(directory/'cameras.json',result);return result
        finally:self.lock.release()

    def _snapshot_map(self,request):
        supplied=request.get('map') or request.get('template')
        source=Path(supplied).resolve(strict=True) if supplied else Path(self.state['documentPath']) if self.alive() else None
        if source is None or not source.is_file() or source.suffix.lower()!='.sc2map':raise ValueError('Supply a saved .SC2Map or open one in this owned worker')
        digest=files.sha(source)
        directory=self.work/'map-queries'/uuid.uuid4().hex;directory.mkdir(parents=True)
        snapshot=directory/'Snapshot.SC2Map';shutil.copyfile(source,snapshot)
        if files.sha(snapshot)!=digest or files.sha(source)!=digest:raise RuntimeError('Source map changed while creating a read-only snapshot')
        return source,digest,snapshot,directory

    def search_objects(self,request):
        from .map_objects import search_options,read_components,placement_records,search_records,terrain_metadata
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            options=search_options(request)
            source,digest,snapshot,directory=self._snapshot_map(request)
            components=read_components(snapshot,files.mpq_tool())
            records=placement_records(components['Objects'])
            result={'status':'MAP_OBJECTS_FOUND','module':'objects','source':'saved map archive Objects XML; not live Editor state',
                'map':str(source),'mapSha256':digest,'editorRequired':False,'inputAutomation':False,
                'scope':'saved placements only; excludes runtime-created units and inherited dependency placements',
                'coordinateMeaning':'original saved Position XYZ; Z may be a placement offset, not absolute terrain elevation',
                'nameMeaning':'saved XML name/reference; localized display strings are not resolved',
                'objectsComponentPresent':'Objects' in components,**search_records(records,options)}
            if 't3Terrain.xml' in components:result['terrain']=terrain_metadata(components['t3Terrain.xml'])
            if files.sha(source)!=digest:raise RuntimeError('Source map changed during object search; results discarded')
            result['sourceUnchanged']=True
            oracle.save(directory/'search-result.json',result);return result
        finally:self.lock.release()

    def capture_map_region(self,request):
        from .map_objects import bounds_option,read_components,terrain_metadata
        from .map_regions import validate_region,crop_region
        from .map_images import export_options
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            options=export_options(request);bounds=bounds_option(request.get('bounds'))
            output=Path(request['output']).resolve() if request.get('output') else None
            if output and output.suffix.lower()!='.png':raise ValueError('Output extension must be .png')
            if output and output.exists() and not request.get('overwrite',False):raise FileExistsError(output)
            source,digest,snapshot,directory=self._snapshot_map(request)
            components=read_components(snapshot,files.mpq_tool(),required=('t3Terrain.xml',))
            metadata=terrain_metadata(components['t3Terrain.xml']);validate_region(bounds,metadata)
            # Export a private immutable map snapshot. Do not publish the full
            # frame before the region itself passes all validation checks.
            full=self.export_map_image({**options,'map':str(snapshot)},_locked=True,_publish=False)
            if full['status']=='FAILED':return full
            png=directory/'Region.png';preview=directory/'Preview.png'
            crop=crop_region(full['capturePath'],png,preview,bounds,metadata)
            result={'status':'MAP_REGION_CAPTURED','module':'terrain','source':'crop of original Editor full-map export',
                'implementationStatus':'experimental; native rendering and coordinate calibration pending live test',
                'desktopScreenshot':False,'regionCropVerified':crop['image']['imageHasDetail'],
                'coordinateMappingValidated':False,'region':crop,'terrain':metadata,'options':options,
                'map':str(source),'mapSha256':digest,'sourceUnchanged':files.sha(source)==digest,
                'native':full['native'],'nativeImageSha256':full['nativeImageSha256'],
                'sourceFullMapPngSha256':files.sha(full['capturePath'])}
            if not crop['image']['imageHasDetail']:result.update(status='FAILED',regionCropVerified=False,error='Selected region is black or uniform')
            if not result['sourceUnchanged']:result.update(status='FAILED',regionCropVerified=False,error='Source map changed during region capture')
            self._background_result(result)
            if result['status']!='FAILED':
                result['artifact']=self.artifacts.publish_file(png,suffix='.png',mime='image/png',output=output,overwrite=request.get('overwrite',False))
                result['preview']=self.artifacts.register_png(preview)
            else:result['diagnosticImage']=str(png)
            oracle.save(directory/'region-result.json',result);return result
        finally:self.lock.release()

    def export_map_image(self,request,_locked=False,_publish=True):
        from .map_images import export_options,inspect_image
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            options=export_options(request)
            if 'output' in request and (not isinstance(request['output'],str) or not request['output'].strip()):raise ValueError('output must be a nonempty PNG path')
            output=Path(request['output']).resolve() if 'output' in request else None
            if output and output.suffix.lower()!='.png':raise ValueError('Output extension must be .png')
            if output and output.exists() and not request.get('overwrite',False):raise FileExistsError(output)
            path,original_hash=self._prepare_terrain(request)
            directory=self.work/'map-images'/uuid.uuid4().hex;directory.mkdir(parents=True)
            native_image=directory/('NativeMap-'+directory.name[:12]+'.tga');png=directory/'FullMap.png';preview=directory/'Preview.png'
            native=self._native(directory,'terrain-export',map_path=native_image,terrain=options)
            selected=native.get('terrainExport',{})
            if not all(selected.get(key) for key in ('exported','fullMap','topDown','optionsConfirmed','filtersConfirmed','customOptions')):raise RuntimeError('Original complete overhead map export and native object filters were not confirmed')
            if selected.get('size')!=options['size'] or bool(selected.get('includeUnits'))!=options['include_units'] or bool(selected.get('includeDoodads'))!=options['include_doodads']:raise RuntimeError('Original map export options did not match the request')
            for key,option in (('actualUnits','include_units'),('actualDoodads','include_doodads')):
                if selected.get(key) not in (0,1) or bool(selected[key])!=options[option]:raise RuntimeError('Original map export flag-model readback did not match the request')
            if self.scene:self.scene['frame']=None
            image=inspect_image(native_image,preview,png)
            if image['width']!=options['size']:raise RuntimeError('Native output width did not match the requested image size')
            result={'status':'MAP_IMAGE_EXPORTED','module':'terrain','source':'original Editor Export Map Image / CMapImageGenerator',
                'implementationStatus':'native full-map export with verified original flag-model readback',
                'objectFiltersVerified':True,'filterVerification':'original Editor model getter and custom export mode; not checkbox state alone',
                'view':'complete map, top down','desktopScreenshot':False,'wholeMapVerified':image['imageHasDetail'],
                'native':native,'options':options,'image':image,'sourceUnchanged':files.sha(path)==original_hash,
                'nativeImageSha256':files.sha(native_image),'nativeImageFormat':image['format'],'outputEncoding':'lossless RGB PNG'}
            if not image['imageHasDetail']:result.update(status='FAILED',error='Original map exporter returned a black or uniform image',wholeMapVerified=False)
            if not result['sourceUnchanged']:result.update(status='FAILED',error='Source map changed during export',wholeMapVerified=False)
            self._background_result(result)
            if result['status']!='FAILED' and _publish:
                result['artifact']=self.artifacts.publish_file(png,suffix='.png',mime='image/png',output=output,overwrite=bool(request.get('overwrite',False)))
                result['preview']=self.artifacts.register_png(preview)
            elif result['status']=='FAILED':result['diagnosticImage']=str(png)
            else:result['capturePath']=str(png)
            oracle.save(directory/'export-result.json',result);return result
        finally:
            if not _locked:self.lock.release()

    def export_video(self,request):
        from .video import export_video
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        self.video_cancel.clear()
        try:return export_video(self,request)
        finally:self.lock.release()

    def export_video_status(self,request=None):
        return dict(self.video_progress) if self.video_progress else {'status':'IDLE'}

    def cancel_video(self,request):
        if not self.video_progress or self.video_progress['status']!='RUNNING':return {'status':'NO_VIDEO_EXPORT_RUNNING'}
        if request.get('job_id') and request['job_id']!=self.video_progress['jobId']:raise ValueError('Video job ID mismatch')
        self.video_cancel.set();return {'status':'CANCEL_REQUESTED','jobId':self.video_progress['jobId']}
