"""Opt-in original Archive Browser equality/performance probe on a private map."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.session import Worker
from sc2native.revisions import digest

def main():
    p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--paths',required=True);p.add_argument('--baseline',required=True);p.add_argument('--work',required=True)
    p.add_argument('--present',action='append',default=[]);p.add_argument('--missing',action='append',default=[]);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);source=Path(a.map).resolve(strict=True);before=digest(source)
    paths=Path(a.paths).read_text(encoding='utf8').splitlines()+a.present+a.missing
    request=work/'paths.txt';request.write_text('\n'.join(paths)+'\n',encoding='utf8');worker=Worker(work/'runtime')
    try:
        worker.ensure(source);print('OWNED_EDITOR_READY',flush=True);folder=work/'files';folder.mkdir();started=time.monotonic()
        worker._native(folder,'data-audit-files',map_path=request);elapsed=time.monotonic()-started
        native=json.loads((folder/'01-data-audit-files/Native.data.json').read_text(encoding='utf8'))
        assert native['complete'];baseline=json.loads(Path(a.baseline).read_text(encoding='utf8'))
        expected={v['path'].casefold():v['status'] for v in baseline['resources']};actual={v['path'].casefold():v['status'] for v in native['resources']}
        assert all(actual[key]==value for key,value in expected.items())
        assert all(actual[key.casefold()]=='present' for key in a.present)
        assert all(actual[key.casefold()]=='missing' for key in a.missing)
        observed=worker.monitor.snapshot();assert observed['visibleWindowsOnUserDesktopPeak']==observed['editorForegroundSamples']==0
        result={'status':'NATIVE_RESOURCE_TRAVERSAL_PROBE_PASSED','elapsedSeconds':elapsed,'baselinePathsCompared':len(expected),'nodes':native['nodesEnumerated'],'folders':native['foldersEnumerated'],'observation':observed}
        (work/'VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result),flush=True)
    finally:
        worker.close();(work/'closed.json').write_text(json.dumps({'ownedClosed':not worker.alive(),'sourceUnchanged':digest(source)==before}),encoding='utf8')

if __name__=='__main__':main()
