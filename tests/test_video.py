import json,shutil,struct,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.video import video_plan,encoder_tools,validate_video,NO_WINDOW
from sc2native.artifacts import ArtifactStore
from sc2native.cutscenes import scene_duration

class Video(unittest.TestCase):
    def test_frame_count_time_grid_and_exclusive_range(self):
        full=video_plan({}, {'durationMs':3965,'durationSource':'directorEndScene'})
        self.assertEqual(full['frameCount'],119);self.assertEqual(full['sampleTimesMs'][0],0)
        self.assertTrue(all(t%33==0 for t in full['sampleTimesMs']))
        ranged=video_plan({'start_ms':990,'end_ms':1980,'fps':15},{})
        self.assertEqual(ranged['frameCount'],15);self.assertEqual(ranged['sampleTimesMs'][0],990)
        self.assertEqual(len(set(video_plan({'start_ms':0,'end_ms':1000,'fps':60},{})['sampleTimesMs'])),31)
    def test_invalid_ranges_rejected(self):
        for request in ({},{'end_ms':0},{'start_ms':2,'end_ms':1},{'end_ms':float('nan')},{'end_ms':1000,'fps':True},{'end_ms':1000,'fps':0},
            {'end_ms':1000,'overwrite':'false'},{'end_ms':1000,'keep_frames':'false'},{'end_ms':1000,'output':4}):
            with self.subTest(request=request),self.assertRaises(ValueError):video_plan(request,{})
    def test_duration_uses_enabled_end_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.xml';path.write_text('<CutsceneState><CCutsceneNodeDirector><CCutsceneElementEndScene start="3965"/><CCutsceneElementEndScene start="1" enabled="0"/></CCutsceneNodeDirector><CCutsceneElementObject duration="93261"/></CutsceneState>')
            self.assertEqual(scene_duration(path),{'durationMs':3965,'durationSource':'directorEndScene'})
    def test_large_export_refuses_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'encoded.mp4';source.write_bytes(b'new');target=root/'existing.mp4';target.write_bytes(b'old')
            artifacts=ArtifactStore(root/'artifacts')
            with self.assertRaises(FileExistsError):artifacts.publish_file(source,suffix='.mp4',mime='video/mp4',output=target)
            self.assertEqual(target.read_bytes(),b'old')
            artifact=artifacts.publish_file(source,suffix='.mp4',mime='video/mp4',output=target,overwrite=True)
            self.assertEqual(artifacts.get(artifact['id'])['bytes'],3)
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg integration')
    def test_real_mp4_encoder_and_full_decode_without_editor(self):
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        raw=b''.join(b'\0'+bytes(v for x in range(16) for v in (x*16,y*16,(x+y)*8)) for y in range(16))
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',16,16,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
        encoder,probe=encoder_tools()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.mp4'
            run=subprocess.run([encoder,'-v','error','-f','image2pipe','-framerate','1','-i','pipe:0','-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],input=png*3,capture_output=True,creationflags=NO_WINDOW,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            result=validate_video(path,encoder,probe,{'frameCount':3,'fps':1,'encodedDurationSeconds':3},1)
            self.assertTrue(result['fullDecodePassed']);self.assertEqual(result['frameCount'],3)
if __name__=='__main__':unittest.main()
