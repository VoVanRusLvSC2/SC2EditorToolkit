import json,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))

@unittest.skipUnless(sys.platform=='win32','Windows session runtime')
class Terrain(unittest.TestCase):
    def test_terrain_does_not_capture_the_previously_selected_cutscene(self):
        from sc2native.session import Worker
        with tempfile.TemporaryDirectory() as tmp:
            w=object.__new__(Worker);w.work=Path(tmp);w.state={'pid':123};w.alive=lambda:True
            w.scene={'frame':{'viewport':999,'camera':'Front'}}
            w.monitor=SimpleNamespace(snapshot=lambda:{'visibleWindowsOnUserDesktopPeak':0,'editorForegroundSamples':0})
            for actual in (42,999):
                calls=[]
                def run(command,**kwargs):
                    calls.append(command)
                    return SimpleNamespace(returncode=0,stdout=json.dumps({'sourceWindow':actual,'width':100,'height':100,'nonBlackPixels':10000,'luminanceBins':30,'emptyFrame':False}).encode())
                with patch('sc2native.session.subprocess.run',run):
                    result=w.capture_frame({},_locked=True,_register=False,_directory=Path(tmp)/str(actual),_terrain={'viewport':42})
                self.assertEqual(calls[0][-2:],['--viewport','42'])
                self.assertEqual(result['requestedTerrainFrameVerified'],actual==42)
                self.assertEqual(result['status']=='FAILED',actual!=42)
                self.assertFalse(result['requestedCutsceneFrameVerified'])
                self.assertFalse(result['timelineControl'])
                self.assertEqual(w.scene['frame']['viewport'],999)

    def test_mod_and_cutscene_options_rejected_before_native_work(self):
        from sc2native.session import Worker
        with tempfile.TemporaryDirectory() as tmp:
            mod=Path(tmp)/'Only.SC2Mod';mod.write_bytes(b'test')
            w=object.__new__(Worker);w.lock=threading.Lock()
            for request in ({'map':str(mod)},{'camera':'Front'},{'time_ms':0}):
                with self.assertRaises(ValueError):w.capture_terrain(request)
                self.assertFalse(w.lock.locked())

if __name__=='__main__':unittest.main()
