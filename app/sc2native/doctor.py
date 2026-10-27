"""Read-only installation preflight. Graphics readiness requires a live probe."""
import os
import shutil
import subprocess
import uuid
import json
from pathlib import Path
from editor_installation import resolve_editor,validate_editor
from .render_backend import select_backend
from .contracts import error_info
from .version import VERSION,NATIVE_PROTOCOL


def doctor(worker,request):
    from .runtime import RES,input_desktop
    checks=[]
    def check(name,action,required=True):
        try:checks.append({'check':name,'required':required,'passed':True,'details':action()})
        except Exception as error:checks.append({'check':name,'required':required,'passed':False,'errorInfo':error_info(error)})
    check('originalEditor',lambda:validate_editor(resolve_editor(request.get('editor_path') or worker.editor_preference)))
    check('rendererPackage',lambda:{'selected':select_backend(RES,request.get('render_backend')),'graphicsDeviceLiveTest':'not-run'})
    def helpers():
        names=['HiddenEditorHost.exe','SC2StartupBootstrap.dll','SC2NativeBridge.exe','SC2NativeBridge.dll','RenderCapture.exe']
        missing=[name for name in names if not (RES/name).is_file()]
        if missing:raise FileNotFoundError('Missing matching package components: '+', '.join(missing))
        manifest=json.loads((RES/'native-manifest.json').read_text(encoding='utf-8-sig'))
        if manifest.get('version')!=VERSION or manifest.get('nativeProtocol')!=NATIVE_PROTOCOL:raise ValueError('Mixed toolkit/native package versions')
        from .revisions import digest
        if any(manifest.get('sha256',{}).get(name)!=digest(RES/name) for name in names):raise ValueError('Native package component SHA-256 mismatch')
        return {'nativeProtocol':NATIVE_PROTOCOL,'directory':str(RES),'components':names,'componentHashesVerified':True,'matchingBundleRequired':True,'binaryRuntimeHandshake':'checked on each live request'}
    check('nativeComponents',helpers)
    def storage():
        probe=worker.work/('doctor-'+uuid.uuid4().hex+'.tmp')
        try:
            with probe.open('xb') as stream:stream.write(b'SC2 Editor Toolkit write probe')
        finally:probe.unlink(missing_ok=True)
        free=shutil.disk_usage(worker.work).free
        from .data_audit import AUDIT_MINIMUM_FREE
        return {'work':str(worker.work),'freeBytes':free,'largeAuditSpaceRecommendedBytes':AUDIT_MINIMUM_FREE,
                'fullDataAuditCanStart':free>=AUDIT_MINIMUM_FREE,'lowSpace':free<AUDIT_MINIMUM_FREE}
    check('workStorage',storage)
    def desktop():
        name=input_desktop()
        if not name:raise RuntimeError('An accessible interactive Windows desktop is required')
        return {'inputDesktop':name,'sessionId':os.environ.get('SESSIONNAME'),'sessionIndependentService':False}
    check('interactiveDesktop',desktop)
    from .video import encoder_tools
    def media():
        encoder,probe=encoder_tools()
        versions=[]
        for path in (encoder,probe):
            run=subprocess.run([str(path),'-version'],capture_output=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if run.returncode:raise RuntimeError('Media helper failed: '+str(path))
            versions.append(run.stdout.decode('utf8',errors='replace').splitlines()[0])
        return {'ffmpeg':str(encoder),'ffprobe':str(probe),'versions':versions}
    check('optionalVideoTools',media,False)
    passed=all(c['passed'] for c in checks if c['required'])
    return {'status':'PREFLIGHT_PASSED' if passed else 'PREFLIGHT_INCOMPLETE','checks':checks,'editorLaunched':False,
            'graphicsReady':None,'liveTestRequired':'Use a queued check_document and render on a private map to confirm native startup, GPU and adapter handshake.',
            'workerRunning':worker.alive()}
