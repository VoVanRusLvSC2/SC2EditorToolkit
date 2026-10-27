"""Opt-in index and frozen MCP checks for a complete native field-value snapshot.

Resource existence/semantic findings are outside this acceptance dataset.
"""
import sys,json,sqlite3,time,subprocess,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.audit_store import build_index
from sc2native.artifacts import ArtifactStore
from sc2native.version import VERSION
parser=argparse.ArgumentParser();parser.add_argument('--native',required=True);parser.add_argument('--package',required=True);parser.add_argument('--work',required=True);args=parser.parse_args()
work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False)
native=Path(args.native).resolve(strict=True);verification=json.loads((native/'VERIFICATION.json').read_text(encoding='utf8'))
assert verification['status']=='ALL_NATIVE_EFFECTIVE_FIELD_VALUES_PASSED'
objects=native/'objects.jsonl';findings=work/'findings.jsonl';findings.write_text('',encoding='utf8');last=0
def progress():
 global last
 now=time.monotonic()
 if now-last>10:(work/'progress.json').write_text(json.dumps({'phase':'index-native-fields','elapsed':now-start}),encoding='utf8');last=now
start=time.monotonic();index=build_index(work,objects,findings,progress)
with sqlite3.connect(index) as db:
 count=db.execute('SELECT count(*) FROM fields').fetchone()[0];assert count==verification['counts']['values']
 obj=db.execute("SELECT payload FROM objects WHERE catalog='Unit' AND id='Marine'").fetchone();marine=json.loads(obj[0])
 real=json.loads(db.execute("SELECT payload FROM fields WHERE json_extract(payload,'$.type')='real32' LIMIT 1").fetchone()[0])
store=ArtifactStore(work/'runtime/exports')
state=json.loads((native/'runtime/worker.json').read_text(encoding='utf8'))
report={'status':'FIELD_VALUE_ACCEPTANCE_SNAPSHOT','schemaVersion':2,'fieldValueEncodingVersion':2,
 'catalogTraversalComplete':True,'fieldValuesRecorded':True,
 'fieldValueCoverage':{'recordingAvailable':True,'complete':True,'recordedValues':count,'serializationErrors':0},
 'mapRevision':verification['dependencyManifest']['archives'][0]['sha256'],'projectRevision':verification['projectRevision'],
 'dependencyManifest':verification['dependencyManifest'],'editorInfo':state['editorInfo'],
 'scope':'Full original effective field-value acceptance snapshot; file/resource validation is outside this standalone test',
 'referenceAndFileValidationComplete':False,'validationPassed':None,
 'objectsArtifact':store.publish_file(objects,suffix='.jsonl',mime='application/x-ndjson'),
 'indexArtifact':store.publish_file(index,suffix='.sqlite3',mime='application/vnd.sqlite3')}
artifact=store.export(json.dumps(report,ensure_ascii=False).encode('utf8'),suffix='.json',mime='application/json');ident=artifact['id']
(work/'snapshot.json').write_text(json.dumps({**report,'reportId':ident},ensure_ascii=False,indent=2),encoding='utf8')
messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
 {'jsonrpc':'2.0','method':'notifications/initialized'},
 {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'sc2_query_audit','arguments':{'report_id':ident,'section':'fields','catalog':'Unit','object_id':'Marine','field':'LifeMax'}}},
 {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sc2_query_audit','arguments':{'report_id':ident,'section':'fields','catalog':real['catalog'],'object_id':real['objectId'],'field':real['field']}}},
 {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'sc2_compare_audits','arguments':{'before_report_id':ident,'after_report_id':ident,'section':'fields'}}},
 {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'sc2_query_audit','arguments':{'report_id':ident,'section':'fields','limit':2}}}]
run=subprocess.run([str(Path(args.package).resolve(strict=True)),'--work',str(work/'runtime')],input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,encoding='utf8',capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
assert run.returncode==0,run.stderr
rows=[json.loads(line) for line in run.stdout.splitlines()];assert rows[0]['result']['serverInfo']['version']==VERSION
values={r['id']:r['result'].get('structuredContent') for r in rows[1:]}
assert all(v is not None for v in values.values()),run.stdout
life=next(v for v in marine['fieldValues'] if v['field']=='LifeMax')
assert values[2]['items'][0]['value']==life['value'] and values[2]['items'][0]['valueBits']==life['valueBits']
assert values[3]['items'][0]['valueBits']==real['valueBits']
assert values[4]['comparisonCoverageComplete'] and values[4]['totalChanges']==0
assert values[5]['totalMatches']==count and values[5]['nextOffset']==2
assert not (work/'runtime/worker.json').exists(),'Saved-field MCP unexpectedly launched an Editor'
(work/'mcp-response.json').write_text(run.stdout,encoding='utf8')
(work/'VERIFICATION.json').write_text(json.dumps({'status':'FROZEN_NATIVE_FIELDS_QUERY_COMPARE_PASSED','fieldCount':count,
 'nativeProtocol':16,'fieldValueEncodingVersion':2,'exactLifeMax':values[2]['items'][0],'exactReal32':values[3]['items'][0],
 'selfComparisonChanges':0,'nativeEditorStartedForQueries':False,'elapsedSeconds':time.monotonic()-start},indent=2),encoding='utf8')
print('FROZEN_NATIVE_FIELDS_QUERY_COMPARE_PASSED',count,flush=True)
