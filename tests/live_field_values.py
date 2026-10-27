"""Opt-in original scalar, nested array and link serialization regression."""
import argparse,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.session import Worker
from sc2native.data_audit import check_page


def main():
    p=argparse.ArgumentParser();p.add_argument('--healthy',required=True);p.add_argument('--changed',required=True);p.add_argument('--work',required=True);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);observations=[]
    for label,filename,life in [('before',a.healthy,'45'),('after',a.changed,'73')]:
        source=Path(filename).resolve(strict=True);digest=hashlib.sha256(source.read_bytes()).hexdigest();folder=work/label;w=Worker(folder/'runtime')
        try:
            w.ensure(source);offset=0;previous=None;marine=None
            while marine is None:
                page=folder/f'page-{offset}';page.mkdir()
                native=w._native(page,'data-audit',audit={'catalog':94,'offset':offset,'limit':128})
                data=check_page(json.loads((page/'01-data-audit/Native.data.json').read_text(encoding='utf8')),94,offset,previous)
                marine=next((o for o in data['objects'] if o['id']=='Marine'),None)
                if marine:break
                if data['nextOffset'] is None:raise AssertionError('Marine absent from effective original catalog')
                previous=data;offset=data['nextOffset']
            values={v['field']:v for v in marine['fieldValues']}
            assert not marine['getterErrors'] and not marine['valueSerializationErrors']
            assert values['LifeMax']['value']==life and values['LifeMax']['status']=='serialized'
            assert int(values['LifeMax']['scalarBits'],16)==int(life)*4096
            weapon=values['WeaponArray[0].Link'];reference=next(r for r in marine['references'] if r['field']==weapon['field'])
            assert weapon['value']==reference['target'] and reference['catalog']=='Weapon'
            ui=w.read_data({'catalog':'Unit','object_id':'Marine','field_limit':500})
            assert ui['complete'] and next(f for f in ui['fields'] if f['field']=='CUnit_LifeMax')['values'][0]==life
            observed=w.monitor.snapshot();assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
            (folder/'Marine.json').write_text(json.dumps(marine,ensure_ascii=False,indent=2),encoding='utf8')
            observations.append({'label':label,'LifeMax':values['LifeMax'],'fieldValues':len(values),'referenceMatchesSerialization':True,'uiMatchesSerialization':True,'sourceUnchanged':True,'observation':observed})
            print(label,'ORIGINAL_FIELD_VALUES_PASSED',flush=True)
        finally:
            w.close();(folder/'closed.json').write_text(json.dumps({'ownedClosed':not w.alive()}),encoding='utf8')
    assert observations[0]['LifeMax']['value']!=observations[1]['LifeMax']['value']
    snapshots=[json.loads((work/label/'Marine.json').read_text(encoding='utf8')) for label in ('before','after')]
    left,right=({v['field']:v for v in o['fieldValues']} for o in snapshots)
    changed=sorted(key for key in left.keys()|right.keys() if left.get(key)!=right.get(key))
    assert changed==['LifeMax'],changed
    (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_EFFECTIVE_FIELD_VALUES_PASSED','checks':observations,'nativeChangedFields':changed},indent=2),encoding='utf8')


if __name__=='__main__':main()
