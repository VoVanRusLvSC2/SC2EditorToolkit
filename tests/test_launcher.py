import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.launcher import run


class Launcher(unittest.TestCase):
    def test_duplicate_startup_preserves_identity_and_reports_without_raising(self):
        with tempfile.TemporaryDirectory() as root:
            info=Path(root)/'api-info.json';info.write_text('preserve live identity')
            def denied():raise RuntimeError('Work directory is already in use')
            with patch.object(sys,'argv',['api','serve','--work',root]),patch.object(sys,'stderr',io.StringIO()) as stderr:
                self.assertEqual(run(denied),2)
                self.assertEqual(json.loads(stderr.getvalue())['stage'],'startup')
            self.assertEqual(info.read_text(),'preserve live identity')
            errors=list((Path(root)/'startup-errors').glob('*.json'));self.assertEqual(len(errors),1)
            self.assertIn('already in use',json.loads(errors[0].read_text())['error'])
    def test_windowed_failure_with_no_stderr_still_exits_cleanly(self):
        with patch.object(sys,'argv',['api']),patch.object(sys,'stderr',None):
            self.assertEqual(run(lambda:(_ for _ in ()).throw(RuntimeError('failure'))),2)
        self.assertEqual(run(lambda:0),0)
