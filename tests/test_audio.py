import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.video import encoder_tools,video_plan,NO_WINDOW
from sc2native.audio import mux_audio

class Audio(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt' and shutil.which('ffmpeg') and shutil.which('ffprobe'),'Windows FFmpeg integration')
    def test_native_pcm_timeline_trim_and_aac_decode(self):
        from sc2native.session import Worker
        encoder,probe=encoder_tools()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'video.mp4';wave=root/'source.wav'
            subprocess.run([encoder,'-v','error','-f','lavfi','-i','testsrc2=size=32x32:rate=10:duration=1','-an','-c:v','libx264',str(video)],check=True,creationflags=NO_WINDOW)
            # A cue at 0.5 s in source PCM must survive a clip beginning at 0.4 s.
            subprocess.run([encoder,'-v','error','-f','lavfi','-i','sine=frequency=1000:sample_rate=48000:duration=1','-af','adelay=500:all=1','-c:a','pcm_f32le',str(wave)],check=True,creationflags=NO_WINDOW)
            worker=Worker(root/'owned');plan=video_plan({'start_ms':400,'end_ms':1400,'fps':10},{})
            try:
                evidence={'rate':48000,'timelineOriginSeconds':0}
                result=mux_audio(worker,video,wave,root/'final.mp4',encoder,probe,plan,evidence)
                self.assertEqual(result['codec'],'aac');self.assertFalse(result['silent']);self.assertTrue(result['fullDecodePassed'])
                decoded=subprocess.run([encoder,'-v','error','-i',str(root/'final.mp4'),'-map','0:a:0','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=NO_WINDOW)
                import array
                values=array.array('f');values.frombytes(decoded.stdout)
                first=next(i for i,v in enumerate(values) if abs(v)>.01)/48000
                self.assertAlmostEqual(first,.1,delta=.03)
            finally:worker.close()
    def test_audio_option_type_checked(self):
        with self.assertRaises(ValueError):video_plan({'end_ms':1000,'include_audio':'true'},{})
if __name__=='__main__':unittest.main()
