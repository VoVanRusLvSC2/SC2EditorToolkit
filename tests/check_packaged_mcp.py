"""No Editor required: verify the windowed MCP EXE inherits and restores stdio."""
from pathlib import Path
import json,subprocess,sys
from map_archive_fixture import create_archive
root=Path(__file__).resolve().parents[1]
work=root/'local-tests'/'packaged-mcp';work.mkdir(parents=True,exist_ok=True)
import tempfile
archive_dir=tempfile.TemporaryDirectory();archive=create_archive(Path(archive_dir.name),root/'tools/mpqcli/mpqcli.exe')
messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
 {'jsonrpc':'2.0','method':'notifications/initialized'},
 {'jsonrpc':'2.0','id':2,'method':'tools/list'},
 {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sc2_modules','arguments':{}}},
 {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'sc2_search_objects','arguments':{'map':str(archive),'query':'marine','owner':2}}}]
run=subprocess.run([str(root/'dist'/'SC2NativeMCP.exe'),'--work',str(work)],input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,encoding='utf8',capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=30)
assert run.returncode==0,run.stderr
result=[json.loads(line) for line in run.stdout.splitlines()]
assert [r['id'] for r in result]==[1,2,3,4],run.stdout
assert 'sc2_capture_frame' in {t['name'] for t in result[1]['result']['tools']}
assert 'sc2_capture_terrain' in {t['name'] for t in result[1]['result']['tools']}
assert 'sc2_export_map_image' in {t['name'] for t in result[1]['result']['tools']}
assert 'sc2_capture_map_region' in {t['name'] for t in result[1]['result']['tools']}
search=result[3]['result']['structuredContent']
assert not result[3]['result']['isError'] and search['totalMatches']==1,search
assert search['objects'][0]['position']=={'x':48,'y':36,'z':0},search
assert search['sourceUnchanged'] and not search['editorRequired']
archive_dir.cleanup()
assert not (work/'worker.json').exists()
(work/'VERIFICATION.json').write_text(json.dumps({'status':'PACKAGED_MCP_STDIO_PASSED','tools':len(result[1]['result']['tools']),'editorStarted':False},indent=2),encoding='utf8')
print('Packaged windowed MCP stdio: passed; '+str(len(result[1]['result']['tools']))+' tools')
