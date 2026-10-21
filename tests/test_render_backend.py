import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native import render_backend as backend
from sc2native.session import Worker

class RenderBackend(unittest.TestCase):
    def test_published_dependency_manifest_matches_runtime_pin_and_license(self):
        vendor=Path(__file__).resolve().parents[1]/'vendor/dxvk'
        manifest=json.loads((vendor/'manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['dllSHA256'],backend.DXVK_SHA256)
        self.assertEqual(manifest['version'],backend.DXVK_VERSION)
        self.assertEqual(hashlib.sha256((vendor/'LICENSE').read_bytes()).hexdigest(),manifest['licenseSHA256'])
    def test_missing_auto_uses_legacy_but_requested_vulkan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(backend.select_backend(directory,'auto'),'legacy')
            with self.assertRaisesRegex(ValueError,'missing'):backend.select_backend(directory,'vulkan')
    def test_auto_verifies_existing_renderer_and_never_falls_back_on_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'renderers/dxvk/d3d9.dll';path.parent.mkdir(parents=True);path.write_bytes(b'test renderer')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(backend,'DXVK_SHA256',digest):
                self.assertEqual(backend.select_backend(directory,'auto'),'vulkan')
                path.write_bytes(b'changed renderer')
                with self.assertRaisesRegex(ValueError,'SHA-256'):backend.select_backend(directory,'auto')
            self.assertEqual(backend.select_backend(directory,'legacy'),'legacy')
    def test_bad_backend_rejected_before_an_editor_can_start(self):
        for value in ('',False,12,'VULKAN','system'):
            with self.subTest(value=value),self.assertRaises(ValueError):backend.requested_backend(value)
        with patch.dict(os.environ,{'SC2EDITOR_RENDER_BACKEND':'legacy'}):self.assertEqual(backend.requested_backend(),'legacy')
    def test_child_logs_and_cache_are_private_without_mutating_parent(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'DXVK_LOG_PATH':'parent','SC2EDITOR_RENDER_BACKEND':'legacy'}):
            first=backend.render_environment('vulkan',Path(directory)/'a')
            second=backend.render_environment('vulkan',Path(directory)/'b')
            self.assertNotEqual(first['DXVK_LOG_PATH'],second['DXVK_LOG_PATH'])
            self.assertNotEqual(first['DXVK_SHADER_CACHE_PATH'],second['DXVK_SHADER_CACHE_PATH'])
            self.assertNotEqual(first['DXVK_CONFIG_FILE'],second['DXVK_CONFIG_FILE'])
            self.assertTrue(Path(first['DXVK_LOG_PATH']).is_dir())
            self.assertEqual(os.environ['DXVK_LOG_PATH'],'parent');self.assertEqual(os.environ['SC2EDITOR_RENDER_BACKEND'],'legacy')
            self.assertEqual(first['SC2EDITOR_RENDER_BACKEND'],'vulkan')
    def test_existing_worker_cannot_silently_change_backend(self):
        worker=Worker.__new__(Worker);worker.alive=lambda:True;worker.state={'renderBackend':'vulkan'}
        with self.assertRaisesRegex(ValueError,'restart'):worker.ensure('unused',render_backend='legacy')
        worker.ensure('unused',render_backend='vulkan');worker.ensure('unused',render_backend='auto')
    def test_invalid_renderer_does_not_create_worker_directories(self):
        worker=Worker.__new__(Worker);worker.alive=lambda:False
        with tempfile.TemporaryDirectory() as directory,patch('sc2native.session.RES',Path(directory)):
            with self.assertRaisesRegex(ValueError,'missing'):worker.ensure('unused',render_backend='vulkan')
            self.assertEqual(list(Path(directory).iterdir()),[])

if __name__=='__main__':unittest.main()
