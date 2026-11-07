"""Opt-in: a missing startup DLL must retain its phase/code and close its child."""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--map',required=True);p.add_argument('--work',required=True);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
    binaries=work/'missing-dll';binaries.mkdir()
    shutil.copyfile(Path(a.native)/'HiddenEditorHost.exe',binaries/'HiddenEditorHost.exe')
    os.environ['SC2_NATIVE_BIN']=str(binaries)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
    from sc2native.session import Worker
    from sc2native.startup_failure import NativeStartupError
    from sc2native.runtime import process_time
    source=Path(a.map).resolve(strict=True);before=hashlib.sha256(source.read_bytes()).hexdigest()
    worker=Worker(work/'runtime')
    try:
        try:worker.ensure(source)
        except NativeStartupError as error:
            evidence=error.error_info['evidence'];native=evidence['native']
            assert native['status']=='HIDDEN_BOOTSTRAP_FAILED',evidence
            assert native['bootstrapFailure']['phase']=='load-local-bootstrap',evidence
            assert native['bootstrapFailure']['win32Error']==126,evidence
            assert not error.error_info['automaticRetry']
            assert process_time(native['pid'])!=native['createTimeFiletime'],'Failed owned child still running'
            assert not worker.alive()
            assert 'phase=load-local-bootstrap' in evidence['logs']['host.stderr.log']
        else:raise AssertionError('Startup unexpectedly accepted a missing bootstrap DLL')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_BOOTSTRAP_FAILURE_EVIDENCE_PASSED',
            'phase':'load-local-bootstrap','win32Error':126,'ownedChildClosed':True,'sourceUnchanged':True,
            'nativeCompilationTested':False,'renderingTested':False,'automaticRetry':False},indent=2),encoding='utf8')
        print('Missing startup DLL: exact phase/Win32 retained; owned suspended child closed',flush=True)
    finally:worker.close()

if __name__=='__main__':main()
