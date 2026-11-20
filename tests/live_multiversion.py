"""Opt-in portable Editor path, real original compilation and safe ABI refusal."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from editor_installation import inspect_editor,inspect_trusted_editor,EditorCapabilityUnavailable
from sc2native.session import Worker
from sc2native.runtime import process_time
from sc2native.document_validation import _loaded
import native_xml_oracle as oracle

def main():
    p=argparse.ArgumentParser();p.add_argument('--editor',required=True);p.add_argument('--map',required=True);p.add_argument('--work',required=True);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
    source=Path(a.map).resolve(strict=True);before=hashlib.sha256(source.read_bytes()).hexdigest()
    identity=inspect_editor(a.editor);portable=inspect_trusted_editor(identity)
    assert portable['trusted'] and portable['verificationMethod']=='authenticode-blizzard' and not portable['nativeOffsets']
    w=Worker(work/'runtime',editor_path=a.editor);state=None
    try:
        result=w.start({'template':str(source),'startup_module':'triggers','render_backend':'vulkan'})
        assert result['status']=='HIDDEN_EDITOR_STARTED',result
        state=dict(w.state);print('PORTABLE_EDITOR_READY',state['editorInfo']['version'],flush=True)
        saved=w.work/('NativeSaved'+source.suffix);folder=work/'save';folder.mkdir()
        native=w._native(folder,'save-document',map_path=saved);assert native.get('documentIo',{}).get('saved'),native
        _loaded(w,saved)
        compiled=w.compile_current({});assert compiled['nativeGenerationVerified'] and compiled['nativeCompilePassed'],compiled
        print('ORIGINAL_GENERATION_AND_COMPILE_PASSED',flush=True)
        folder=work/'blocked-python';folder.mkdir()
        try:w._native(folder,'data-audit',audit={'catalog':0,'offset':0,'limit':1})
        except EditorCapabilityUnavailable:pass
        else:raise AssertionError('Unverified offset capability accepted by Python')
        folder=work/'blocked-native';folder.mkdir();oracle.ACTIVE_DESKTOP=w.state['desktop']
        try:oracle.native_step(folder,'01-data-audit',state['pid'],w.state['currentDocument'],editor=a.editor,audit={'catalog':0,'offset':0,'limit':1})
        except oracle.NativeStepError as error:assert error.native_result['error']==160,error.native_result
        else:raise AssertionError('Unverified native offset operation accepted by DLL')
        frame=w.capture_terrain({'output':str(work/'Terrain.png')})
        assert frame['status']=='TERRAIN_FRAME_CAPTURED' and frame['imageHasDetail'] and not frame['emptyFrame'],frame
        observation=w.monitor.snapshot()
        assert not observation['visibleWindowsOnUserDesktopPeak'] and not observation['editorForegroundSamples'],observation
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        (work/'VERIFICATION.json').write_text(json.dumps({'status':'PORTABLE_EDITOR_VERSION_PASSED','editor':state['editorInfo'],
            'authenticodeFallbackVerified':True,'nativeCompilePassed':True,'unsafeOffsetCallsRefusedByPythonAndDll':True,
            'terrainViewportCaptured':True,'observation':observation,'sourceUnchanged':True},indent=2),encoding='utf8')
        print('PORTABLE_VIEWPORT_AND_OFFSET_GUARDS_PASSED',flush=True)
    finally:
        w.close()
        assert not state or process_time(state['pid'])!=state['createTimeFiletime']
        (work/'closed.json').write_text(json.dumps({'ownedClosed':True}),encoding='utf8')

if __name__=='__main__':main()
