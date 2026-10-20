import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
class Mcp(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows runtime')
    def test_initialize_tools_and_eof_without_editor(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sc2_modules','arguments':{}}}]
            run=subprocess.run([sys.executable,str(root/'app'/'mcp_server.py'),'--work',work],input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(run.returncode,0,run.stderr)
            output=[json.loads(line) for line in run.stdout.splitlines()]
            self.assertEqual([r['id'] for r in output],[1,2,3])
            self.assertEqual(output[0]['result']['protocolVersion'],'2025-06-18')
            self.assertIn('sc2_export_galaxy',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_validate_document',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_save_reopen',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_list_map_cameras',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_capture_terrain',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_export_map_image',{t['name'] for t in output[1]['result']['tools']})
            self.assertIn('sc2_search_objects',{t['name'] for t in output[1]['result']['tools']})
            region=next(t for t in output[1]['result']['tools'] if t['name']=='sc2_capture_map_region')
            self.assertEqual(region['inputSchema']['required'],['bounds'])
            self.assertFalse(Path(work,'worker.json').exists())
if __name__=='__main__':unittest.main()
