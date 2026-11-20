import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import editor_installation as install
from editor_profiles import PROFILES
from sc2native.contracts import error_info
ROOT=Path(__file__).resolve().parents[1]

class EditorProfiles(unittest.TestCase):
    def test_generated_native_and_python_profiles_are_current(self):
        subprocess.run([sys.executable,str(ROOT/'tools/generate_editor_profiles.py'),'--check'],check=True,capture_output=True)
        self.assertEqual({p['version'] for p in PROFILES},{'5.0.17.98310','5.0.17.98745'})

    def test_known_new_patch_uses_its_own_identity_without_legacy_offsets(self):
        identity={'path':'original/SC2Editor_x64.exe','sha256':PROFILES[1]['sha256']}
        with patch.object(install,'inspect_editor',return_value=identity),patch.object(install,'inspect_trusted_editor') as portable:
            result=install.validate_editor(identity['path'])
        portable.assert_not_called()
        self.assertEqual(result['version'],'5.0.17.98745')
        self.assertTrue(result['originalBinaryVerified'])
        self.assertTrue(result['capabilities']['hiddenStartup'])
        self.assertFalse(result['capabilities']['dataAudit'])
        with self.assertRaises(install.EditorCapabilityUnavailable) as caught:install.require_editor_capability(result,'dataAudit')
        self.assertEqual(error_info(caught.exception)['code'],'NATIVE_ADAPTER_UNAVAILABLE')

    def test_legacy_profile_keeps_offset_capabilities(self):
        with patch.object(install,'inspect_editor',return_value={'path':'editor','sha256':PROFILES[0]['sha256']}):
            result=install.validate_editor('editor')
        self.assertTrue(result['capabilities']['dataAudit']);self.assertTrue(result['capabilities']['terrainObjectFilters'])

    def test_unlisted_signed_build_never_inherits_offsets_from_same_version_string(self):
        identity={'path':'original/SC2Editor_x64.exe','sha256':'a'*64}
        native={'trusted':True,'sha256':identity['sha256'],'version':'5.0.17.98310','nativeOffsets':True,'editorLaunched':False,'verificationMethod':'authenticode-blizzard'}
        with tempfile.TemporaryDirectory() as work:
            helper=Path(work)/'HiddenEditorHost.exe';helper.write_bytes(b'fixture')
            with patch.dict('os.environ',{'SC2_NATIVE_BIN':work}),patch.object(install,'inspect_editor',return_value=identity),patch.object(install.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(native).encode(),b'')):
                result=install.validate_editor(identity['path'])
        self.assertFalse(result['nativeOffsetsVerified']);self.assertEqual(result['adapter'],'portable-editor-ui')

    def test_changed_identity_unsigned_or_wrong_publisher_are_refused(self):
        identity={'path':'original/SC2Editor_x64.exe','sha256':'a'*64}
        with tempfile.TemporaryDirectory() as work:
            (Path(work)/'HiddenEditorHost.exe').write_bytes(b'fixture')
            for result in ({'trusted':False,'sha256':'a'*64,'editorLaunched':False},
                           {'trusted':True,'sha256':'b'*64,'editorLaunched':False}):
                with patch.dict('os.environ',{'SC2_NATIVE_BIN':work}),patch.object(install.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(result).encode(),b'')):
                    with self.assertRaisesRegex(ValueError,'Unsupported Editor binary'):install.inspect_trusted_editor(identity)

    def test_unavailable_capability_is_refused_before_native_ipc(self):
        from sc2native.session import Worker
        worker=Worker.__new__(Worker);worker.alive=lambda:True
        worker.state={'editorInfo':{'version':'future','capabilities':{'dataAudit':False}}}
        with patch('sc2native.session.oracle.native_step') as native:
            with self.assertRaises(install.EditorCapabilityUnavailable):worker._native(Path('unused'),'data-audit')
            native.assert_not_called()
