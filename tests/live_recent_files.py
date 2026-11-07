"""Opt-in original Editor open/save/compile with unchanged normal MRU values."""
import argparse
import hashlib
import json
import sys
import winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.session import Worker
from sc2native.runtime import process_time
from sc2native.recent_files import worker_key
from sc2native.document_validation import _loaded

NORMAL='Software\\Blizzard Entertainment\\StarCraft II Editor\\Recent Files'

def snapshot(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path,0,winreg.KEY_READ) as key:
            subkeys,values,_=winreg.QueryInfoKey(key)
            content=[]
            for i in range(values):
                name,value,kind=winreg.EnumValue(key,i)
                if isinstance(value,bytes):value={'hex':value.hex()}
                content.append((name,kind,value))
            children={name:snapshot(path+'\\'+name) for name in (winreg.EnumKey(key,i) for i in range(subkeys))}
            return {'values':sorted(content),'children':children}
    except FileNotFoundError:return None

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--work',required=True);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False)
    source=Path(a.map).resolve(strict=True);original=hashlib.sha256(source.read_bytes()).hexdigest()
    baseline=digest(snapshot(NORMAL));records=[]
    for index in range(2):
        w=Worker(work/('worker-'+str(index)));state=None
        try:
            started=w.start({'template':str(source),'startup_module':'triggers','render_backend':'vulkan'})
            assert started['status']=='HIDDEN_EDITOR_STARTED',started
            state=dict(w.state)
            save=work/('save-'+str(index));save.mkdir()
            saved=w.work/'NativeSaved.SC2Map'
            native=w._native(save,'save-document',map_path=saved)
            assert native.get('documentIo',{}).get('saved'),native
            _loaded(w,saved)
            compiled=w.compile_current({})
            assert compiled['nativeGenerationVerified'] and compiled['nativeCompilePassed'],compiled
            private=snapshot(worker_key(state['instanceId'])+'\\Recent Files')
            assert private is not None,'Private MRU key missing'
            assert private['values'],'No native Recent Files writes observed'
            assert digest(snapshot(NORMAL))==baseline,'Normal Editor Recent Files changed'
            observation=w.monitor.snapshot()
            assert observation['visibleWindowsOnUserDesktopPeak']==observation['editorForegroundSamples']==0,observation
            assert not observation['inputDesktopChanges'],observation
            records.append({'pid':state['pid'],'instanceId':state['instanceId'],'privateRecentValues':len(private['values']),
                'nativeCompilePassed':True,'observation':observation})
            print('OWNED_OPEN_SAVE_COMPILE_AND_NORMAL_MRU_PASSED',index,flush=True)
        finally:
            w.close()
            if state:
                assert process_time(state['pid'])!=state['createTimeFiletime'],'Owned worker still running'
                assert snapshot(worker_key(state['instanceId'])) is None,'Private MRU key not cleaned up'
    assert digest(snapshot(NORMAL))==baseline
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original
    assert records[0]['instanceId']!=records[1]['instanceId']
    (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_RECENT_FILES_ISOLATION_PASSED','workers':records,
        'normalRecentFilesUnchanged':True,'sourceUnchanged':True,'ownedWorkersClosed':True,'privateKeysRemoved':True},indent=2),encoding='utf8')

if __name__=='__main__':main()
