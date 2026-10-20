from .runtime import *
from .artifacts import ArtifactStore
from .diagnostics import parse_native_diagnostics
from .cutscenes import scene_file,seek_arguments,scene_duration
class Worker:
    def _background_result(self,result):
        result['desktopObservation']=self.monitor.snapshot()
        observed=result['desktopObservation']
        if observed['visibleWindowsOnUserDesktopPeak'] or observed['editorForegroundSamples']:
            result.update(status='FAILED',error='Hidden desktop invariant failed',requestedCutsceneFrameVerified=False)
        return result
    def __init__(self,work):
        self.work=Path(work).resolve();self.work.mkdir(parents=True,exist_ok=True)
        self.state=None;self.monitor=None;self.lock=threading.Lock()
        self.artifacts=ArtifactStore(self.work/'exports');self.last_result=None;self.scene=None
        self.video_progress=None;self.video_cancel=threading.Event()
        self.job_name='Local\\SC2NativeApi-'+uuid.uuid4().hex
        self.job_handle=kernel.CreateJobObjectW(None,self.job_name)
        limit=ExtendedLimit();limit.Basic.Flags=0x2000
        if not self.job_handle or not kernel.SetInformationJobObject(self.job_handle,9,ctypes.byref(limit),ctypes.sizeof(limit)):
            raise OSError(ctypes.get_last_error(),'Cannot create owned-worker lifetime job')
        atexit.register(self.close)
    def alive(self):return bool(self.state and process_time(self.state['pid'])==self.state['createTimeFiletime'])
    def ensure(self,template):
        if self.alive():return
        self.scene=None
        if self.monitor:self.monitor.stop();self.monitor=None
        directory=self.work/'workers'/uuid.uuid4().hex;directory.mkdir(parents=True)
        # Seed is a private archive copy. Never ask the worker to edit the user's source.
        seed=directory/('Seed'+Path(template).suffix);shutil.copyfile(template,seed)
        startup=directory/'startup'
        command=[str(RES/'HiddenEditorHost.exe'),'--document',str(seed),'--out',str(startup),'--timeout','240','--job-name',self.job_name]
        with (directory/'host.stdout.log').open('wb') as out,(directory/'host.stderr.log').open('wb') as err:
            child=subprocess.Popen(command,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            # Start monitoring as soon as the host publishes its child PID.
            while child.poll() is None:
                state_path=startup/'state.json'
                if state_path.is_file() and self.monitor is None:
                    try:
                        state=json.loads(state_path.read_text());self.state=state;self.monitor=Observation(state['pid'])
                    except (OSError,ValueError):pass
                time.sleep(.05)
        state_path=startup/'state.json'
        if not state_path.is_file():raise RuntimeError('Hidden startup failed; see '+str(directory))
        self.state=json.loads(state_path.read_text())
        if child.returncode or self.state['status']!='HIDDEN_EDITOR_READY':raise RuntimeError('Hidden Editor not ready: '+str(self.state['status'])+'; '+str(directory))
        self.state['currentDocument']=seed.name;self.state['documentPath']=str(seed);self.state['startupReport']=str(state_path)
        if self.monitor is None:self.monitor=Observation(self.state['pid'])
        oracle.save(self.work/'worker.json',self.state)
    def close(self):
        if self.alive():
            handle=kernel.OpenProcess(0x1000|1,False,self.state['pid'])
            if handle:
                # Creation time protects against terminating an unrelated reused PID.
                if process_time(self.state['pid'])==self.state['createTimeFiletime']:kernel.TerminateProcess(handle,0)
                kernel.CloseHandle(handle)
        if self.monitor:self.monitor.stop();self.monitor=None
        self.state=None
        if self.job_handle:kernel.CloseHandle(self.job_handle);self.job_handle=None
    def execute(self,request,_locked=False):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy; serialize requests')
        try:
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
            self.ensure(template)
            oracle.ACTIVE_DESKTOP=self.state['desktop']
            args=SimpleNamespace(template=str(template),triggers=str(xml_path),job=str(request_dir/'job'),
                trigger_strings=request.get('trigger_strings'),game_strings=request.get('game_strings'),locale=request.get('locale','enUS'),
                scope=request.get('scope','mapRoot'),context_label=request.get('context_label'),editor=str(files.EDITOR),mpqcli=None,
                pid=self.state['pid'],current_document=self.state['currentDocument'],marker=request.get('marker',''),
                expect_text=request.get('expect_text',[]),compile=bool(request.get('compile',True)))
            result=oracle.convert(args)
            # Load may succeed even if generation/compilation subsequently fails.
            manifest=Path(args.job)/'manifest.json'
            if result.get('steps',{}).get('load',{}).get('mapLoaded'):
                self.scene=None
                self.state['currentDocument']=Path(json.loads(manifest.read_text(encoding='utf-8'))['workingDocument']).name
                self.state['documentPath']=json.loads(manifest.read_text(encoding='utf-8'))['workingDocument']
                oracle.save(self.work/'worker.json',self.state)
            result['hiddenWorker']={k:self.state[k] for k in ('pid','desktop','startupReport')}
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
            oracle.save(request_dir/'api-result.json',result)
            return result
        finally:
            if not _locked:self.lock.release()
    def open_document(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy; serialize requests')
        try:
            source=Path(request.get('map') or request.get('template','')).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('map must be an existing .SC2Map or .SC2Mod archive')
            directory=self.work/'opens'/uuid.uuid4().hex;directory.mkdir(parents=True)
            archive=directory/('NativeOpen-'+directory.name[:12]+source.suffix);shutil.copyfile(source,archive)
            original_hash=files.sha(source)
            if files.sha(archive)!=original_hash:raise RuntimeError('Document copy does not match original')
            self.ensure(archive);oracle.ACTIVE_DESKTOP=self.state['desktop']
            native=oracle.native_step(directory,'01-load',self.state['pid'],self.state['currentDocument'],map_path=archive)
            if not native['mapLoaded']:raise RuntimeError('Native loading not confirmed')
            self.state['currentDocument']=archive.name;oracle.save(self.work/'worker.json',self.state)
            self.state['documentPath']=str(archive);self.last_result=None
            self.scene=None
            result={'status':'HIDDEN_NATIVE_DOCUMENT_OPENED','source':str(source),'openedCopy':str(archive),
                'sourceUnchanged':files.sha(source)==original_hash,'nativeLoad':native,'desktopObservation':self.monitor.snapshot()}
            observed=result['desktopObservation']
            if observed['visibleWindowsOnUserDesktopPeak'] or observed['editorForegroundSamples']:
                result.update(status='FAILED',error='Hidden desktop invariant failed')
            oracle.save(directory/'open-result.json',result)
            return result
        finally:self.lock.release()

    def _native(self,directory,operation,scope='mapRoot',context=''):
        if not self.alive():raise RuntimeError('Start or open a document first')
        oracle.ACTIVE_DESKTOP=self.state['desktop']
        return oracle.native_step(directory,'01-'+operation,self.state['pid'],self.state['currentDocument'],context=context,scope=scope)

    def start(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            template=Path(request.get('template') or request.get('map','')).resolve(strict=True)
            if not template.is_file() or template.suffix.lower() not in ('.sc2map','.sc2mod'):raise ValueError('Existing .SC2Map/.SC2Mod template required')
            self.ensure(template)
            directory=self.work/'editor-actions'/uuid.uuid4().hex;directory.mkdir(parents=True)
            native=self._native(directory,'inspect')
            return {'status':'HIDDEN_EDITOR_STARTED','pid':self.state['pid'],'document':self.state['currentDocument'],
                'native':native,'desktopObservation':self.monitor.snapshot()}
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
            locale=request.get('locale','enUS')
            p=subprocess.run([str(files.mpq_tool()),'read',locale+'.SC2Data/LocalizedData/TriggerStrings.txt',self.state['documentPath']],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
            strings={}
            if not p.returncode:
                for line in p.stdout.decode('utf-8-sig').splitlines():
                    if '=' in line:k,v=line.split('=',1);strings[k]=v
            name=files.context_label(root,scope,strings)
        if not name:raise ValueError('Supply context_label for the authored root/library')
        return scope,name

    def compile_current(self,request):
        if not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
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
            return {'status':'EDITOR_DIAGNOSTICS_READ','native':native,**parse_native_diagnostics(directory/'01-diagnostics',native)}
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
                self.ensure(template)
            directory=self.work/'cutscenes'/uuid.uuid4().hex;directory.mkdir(parents=True)
            native=self._native(directory,'cutscene')
            result={'status':'CUTSCENE_MODULE_OPENED','native':native,'timelineControl':True}
            if source:
                original_hash=files.sha(source);copy=directory/source.name;shutil.copyfile(source,copy)
                if files.sha(copy)!=original_hash:raise RuntimeError('Scene changed while copying')
                self.scene=None
                loaded=oracle.native_step(directory,'02-scene-load',self.state['pid'],self.state['currentDocument'],map_path=copy)
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
            native=oracle.native_step(directory,'01-scene-advance' if _advance else '01-scene-seek',self.state['pid'],self.state['currentDocument'],camera=camera,time_ms=time_ms)
            if not native.get('cameraConfirmed') or not native.get('timeConfirmed'):raise RuntimeError('Native camera/time not confirmed')
            self.scene['frame']={'camera':camera,'requestedTimeMs':time_ms,'actualTimeMs':native['actualTimeMs'],'nativeStatus':native['sceneStatus'],'viewport':native['viewport'],
                'timeResolutionMs':33,'timeReadbackResolutionMs':10,'cameraConfirmed':True,'timeConfirmed':True}
            result={'status':'CUTSCENE_FRAME_SELECTED','frame':self.scene['frame'].copy(),'native':native,'desktopObservation':self.monitor.snapshot()}
            self._background_result(result);oracle.save(directory/'selection.json',result);return result
        finally:
            if not _locked:self.lock.release()

    def capture_frame(self,request,_locked=False,_directory=None,_register=True,_attempts=8):
        if not _locked and not self.lock.acquire(blocking=False):raise RuntimeError('Worker busy')
        try:
            if not self.alive():raise RuntimeError('Start/open the editor first')
            if 'camera' in request or 'time_ms' in request:self.cutscene_seek(request,_locked=True)
            directory=Path(_directory) if _directory else self.work/'frames'/uuid.uuid4().hex;directory.mkdir(parents=True)
            command=[str(RES/'RenderCapture.exe'),'--pid',str(self.state['pid']),'--out',str(directory/'frame.png')]
            frame=self.scene and self.scene.get('frame')
            if self.scene and not frame:raise ValueError('Select a cutscene camera/time first')
            if frame:command+=['--viewport',str(frame['viewport'])]
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
                'source':'original D3D9 backbuffer','desktopScreenshot':False,'timelineControl':True,
                'desktopObservation':self.monitor.snapshot()}
            result['emptyFrame']=evidence.get('emptyFrame',None);result['captureAttempts']=attempts
            if not _register:result['capturePath']=str(image)
            result['imageHasDetail']=evidence.get('luminanceBins',0)>=8 and evidence.get('nonBlackPixels',0)>evidence.get('width',0)*evidence.get('height',0)//1000
            result['requestedCutsceneFrameVerified']=bool(frame and evidence.get('sourceWindow')==frame['viewport'] and result['imageHasDetail'])
            if frame:result['frame']=frame.copy()
            if frame and evidence.get('sourceWindow')!=frame['viewport']:result.update(status='FAILED',error='Capture did not match selected native viewport')
            if (result['emptyFrame'] or not result['imageHasDetail']) and not request.get('allow_empty',False):result.update(status='FAILED',error='Original renderer returned a black or uniform frame')
            self._background_result(result)
            oracle.save(directory/'capture.json',result);return result
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
