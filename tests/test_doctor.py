from sc2native.version import VERSION,NATIVE_PROTOCOL
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from sc2native.doctor import doctor

class Preflight(unittest.TestCase):
    def test_optional_media_missing_and_gpu_unknown_are_honest(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work);names=['HiddenEditorHost.exe','SC2StartupBootstrap.dll','SC2NativeBridge.exe','SC2NativeBridge.dll','RenderCapture.exe']
            hashes={}
            for name in names:
                (root/name).write_bytes(name.encode());hashes[name]=hashlib.sha256(name.encode()).hexdigest()
            (root/'native-manifest.json').write_text(json.dumps({'version':VERSION,'nativeProtocol':NATIVE_PROTOCOL,'sha256':hashes}),encoding='utf8')
            worker=SimpleNamespace(work=root,editor_preference=None,alive=lambda:False)
            with patch('sc2native.runtime.RES',root),patch('sc2native.runtime.input_desktop',return_value='Default'),patch('sc2native.doctor.resolve_editor',return_value='editor'),patch('sc2native.doctor.validate_editor',return_value={'originalBinaryVerified':True}),patch('sc2native.doctor.select_backend',return_value='legacy'),patch('sc2native.video.encoder_tools',side_effect=RuntimeError('FFmpeg missing')):
                value=doctor(worker,{})
                self.assertEqual(value['status'],'PREFLIGHT_PASSED');self.assertIsNone(value['graphicsReady']);self.assertFalse(value['editorLaunched'])
                self.assertFalse(value['checks'][-1]['passed']);self.assertFalse(value['checks'][-1]['required'])
                (root/names[0]).write_bytes(b'mixed package')
                value=doctor(worker,{})
                self.assertEqual(value['status'],'PREFLIGHT_INCOMPLETE')
                self.assertEqual(next(c for c in value['checks'] if c['check']=='nativeComponents')['errorInfo']['code'],'INVALID_ARGUMENT')

if __name__=='__main__':unittest.main()
