import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.startup_failure import NativeStartupError
from sc2native.contracts import error_info
from sc2native.recent_files import worker_key,remove_worker_history


class StartupEvidenceTests(unittest.TestCase):
    def test_failure_retains_native_reason_and_bounded_logs(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root);(directory/'startup').mkdir()
            (directory/'host.stderr.log').write_bytes(b'x'*10000+b' Win32=126')
            state={'status':'HIDDEN_BOOTSTRAP_FAILED','pid':123,'bootstrapFailure':{'phase':'load-local-bootstrap','win32Error':126}}
            error=NativeStartupError(directory,2,state,{'editorForegroundSamples':0})
            report=error_info(error)
            self.assertEqual(report['code'],'EDITOR_STARTUP_FAILED')
            self.assertFalse(report['automaticRetry'])
            self.assertEqual(report['evidence']['native']['bootstrapFailure']['win32Error'],126)
            self.assertEqual(len(report['evidence']['logs']['host.stderr.log']),8192)
            self.assertTrue(report['evidence']['logs']['host.stderr.log'].endswith('Win32=126'))
            self.assertEqual(json.loads((directory/'startup-failure.json').read_text()),report)

    def test_missing_startup_state_still_preserves_available_logs(self):
        with tempfile.TemporaryDirectory() as root:
            error=NativeStartupError(root,2,reason='state unavailable')
            self.assertEqual(error.error_info['evidence']['native'],{})
            self.assertIn('state unavailable',str(error))

    def test_failure_to_save_evidence_does_not_hide_startup_cause(self):
        with tempfile.TemporaryDirectory() as root,patch('pathlib.Path.write_text',side_effect=OSError(28,'disk full')):
            error=NativeStartupError(root,2,{'status':'HIDDEN_BOOTSTRAP_FAILED'})
            self.assertEqual(error_info(error)['code'],'EDITOR_STARTUP_FAILED')
            self.assertIn('disk full',error.error_info['evidencePersistenceError'])

    def test_registry_cleanup_rejects_unowned_paths_before_access(self):
        with patch('sc2native.recent_files.winreg.OpenKey') as opened:
            for identifier in (None,'','..\\Blizzard Entertainment','{bad}','12345678-1234-1234-1234-123456789abc'):
                self.assertIsNone(worker_key(identifier));self.assertFalse(remove_worker_history(identifier))
            opened.assert_not_called()
        self.assertEqual(worker_key('{12345678-1234-1234-1234-123456789ABC}'),
            'Software\\SC2EditorToolkit\\Workers\\{12345678-1234-1234-1234-123456789ABC}')
