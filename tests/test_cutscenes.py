import math,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.cutscenes import scene_file,seek_arguments

class Cutscenes(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32','Windows session runtime')
    def test_hidden_invariant_rejects_visible_or_foreground_worker(self):
        from sc2native.session import Worker
        from types import SimpleNamespace
        for windows,foreground in ((0,0),(1,0),(0,1)):
            observation={'visibleWindowsOnUserDesktopPeak':windows,'editorForegroundSamples':foreground}
            worker=object.__new__(Worker);worker.monitor=SimpleNamespace(snapshot=lambda:observation)
            result=worker._background_result({'status':'RENDER_FRAME_CAPTURED','requestedCutsceneFrameVerified':True})
            self.assertEqual(result['status']=='FAILED',bool(windows or foreground))
            self.assertEqual(result['requestedCutsceneFrameVerified'],not bool(windows or foreground))
    def test_invalid_time_camera_rejected_before_native_commands(self):
        for value in (True,None,'1000',float('nan'),float('inf'),-1,600001):
            with self.subTest(value=value),self.assertRaises(ValueError):seek_arguments({'time_ms':value})
        for value in ('',[],3,'a'*501):
            with self.subTest(value=value),self.assertRaises(ValueError):seek_arguments({'camera':value})
        self.assertEqual(seek_arguments({'camera':'Front Formation Camera','time_ms':990}),('Front Formation Camera',990))
    def test_scene_metadata_does_not_rewrite_input(self):
        data=b'<CutsceneState cutsceneVersion="1.300000"><CCutsceneNodeTargetCamera guid="42" name="Camera" unknown="keep"/></CutsceneState>'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Scene.SC2Cutscene';path.write_bytes(data)
            actual,cameras=scene_file(path)
            self.assertEqual(actual,path.resolve());self.assertEqual(cameras[0]['guid'],'42');self.assertEqual(path.read_bytes(),data)
            path.write_text('<Triggers/>')
            with self.assertRaises(ValueError):scene_file(path)
if __name__=='__main__':unittest.main()
