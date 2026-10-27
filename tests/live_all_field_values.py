"""Opt-in full original effective value traversal; resource checks are separate."""
import argparse,json,sys,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.session import Worker
from sc2native.data_audit import check_page
from sc2native.revisions import snapshot,bind_sources


def main():
    p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--work',required=True);p.add_argument('--baseline-jsonl');a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);source=Path(a.map).resolve(strict=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest();w=Worker(work/'runtime');counts=collections.Counter();catalogs=[];sources=None
    baseline={}
    if a.baseline_jsonl:
        with Path(a.baseline_jsonl).open(encoding='utf8') as stream:
            for line in stream:
                if not line.endswith('\n'):break
                o=json.loads(line);baseline[(o['catalog'],o['id'])]=o
    try:
        w.ensure(source);revision=snapshot(source,w.state['editorPath'],work,w._check_abort)
        with (work/'objects.jsonl').open('x',encoding='utf8') as objects:
            for catalog in range(109):
                offset=0;previous=None;ids=set()
                while True:
                    folder=work/('catalog-%03d-%07d'%(catalog,offset));folder.mkdir()
                    w._native(folder,'data-audit',audit=dict(catalog=catalog,offset=offset,limit=256))
                    data=check_page(json.loads((folder/'01-data-audit/Native.data.json').read_text(encoding='utf8')),catalog,offset,previous)
                    assert data.get('fieldValueEncodingVersion')==2
                    if sources is not None:assert sources==data['dataSources']
                    sources=data['dataSources']
                    for o in data['objects']:
                        assert o['id'] not in ids;ids.add(o['id']);counts['objects']+=1
                        assert not o['getterErrors'] and not o['valueSerializationErrors']
                        counts['values']+=len(o['fieldValues']);counts['exactStorageValues']+=sum('valueBits' in v for v in o['fieldValues'])
                        record={'catalog':data['catalog'],**o};objects.write(json.dumps(record,ensure_ascii=False)+'\n')
                        old=baseline.get((data['catalog'],o['id']))
                        if old:
                            key=lambda v:(v['field'],v['type'],v['status'],v['value'])
                            assert sorted(map(key,old['fieldValues']))==sorted(map(key,o['fieldValues']))
                            assert old['references']==o['references'] and old['resources']==o['resources']
                            counts['baselineObjectsCompared']+=1
                    following=data['nextOffset'];previous=data
                    if following is None:break
                    offset=following
                assert len(ids)==data['totalEntries'];catalogs.append(data['catalog'])
                (work/'progress.json').write_text(json.dumps({'catalog':data['catalog'],'catalogs':len(catalogs),'counts':counts}),encoding='utf8')
        after=snapshot(source,w.state['editorPath'],work,w._check_abort);assert after['revision']==revision['revision']
        manifest=bind_sources(after,sources,Path(w.state['documentPath']).name)
        assert manifest['projectRevisionComplete'] and hashlib.sha256(source.read_bytes()).hexdigest()==before
        observed=w.monitor.snapshot();assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
        result={'status':'ALL_NATIVE_EFFECTIVE_FIELD_VALUES_PASSED','nativeProtocol':16,'fieldValueEncodingVersion':2,'catalogs':catalogs,
                'counts':counts,'getterErrors':0,'serializationErrors':0,'projectRevision':revision['revision'],'dependencyManifest':manifest,
                'sourceUnchanged':True,'observation':observed,'resourcePresenceChecksRepeated':False,
                'scope':'all effective default-variant field values; original typed links/paths compared where an explicit baseline was supplied; resource file presence and gameplay are separate checks'}
        (work/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'status':result['status'],'counts':counts}),flush=True)
    finally:
        observed=w.monitor.snapshot() if w.monitor else None;w.close()
        (work/'closed.json').write_text(json.dumps({'ownedClosed':not w.alive(),'observation':observed}),encoding='utf8')


if __name__=='__main__':main()
