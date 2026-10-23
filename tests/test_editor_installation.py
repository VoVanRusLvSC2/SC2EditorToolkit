import hashlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import editor_installation as install
from sc2native.session import Worker


class EditorInstallation(unittest.TestCase):
    def editor(self,root,name='SC2Editor_x64.exe'):
        path=Path(root)/'Support64'/name;path.parent.mkdir(parents=True)
        data=bytearray(160);data[:2]=b'MZ';struct.pack_into('<I',data,60,128);data[128:134]=b'PE\0\0\x64\x86'
        path.write_bytes(data);return path

    def test_directory_and_unicode_spaces_are_supported(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.editor(Path(root)/'Custom drive installation Юникод')
            self.assertEqual(install.editor_candidate(path.parent.parent),path.resolve())
            self.assertEqual(install.editor_candidate(path.parent),path.resolve())

    def test_explicit_and_environment_selection_precede_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.editor(root)
            with patch.object(install,'discovery_locations',side_effect=AssertionError('unexpected scan')):
                self.assertEqual(install.resolve_editor(path),path.resolve())
                with patch.dict(os.environ,{'SC2_EDITOR_PATH':str(path.parent.parent)}):
                    self.assertEqual(install.resolve_editor(),path.resolve())

    def test_bad_explicit_selection_never_falls_back(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.editor(root,name='SC2_x64.exe')
            with self.assertRaisesRegex(ValueError,'not a game'):install.resolve_editor(path)
            for value in ('',12,False):
                with self.subTest(value=value),self.assertRaises(ValueError):install.resolve_editor(value)

    def test_auto_discovery_deduplicates_and_requires_unambiguous_installation(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{},clear=True):
            first=self.editor(Path(root)/'first');second=self.editor(Path(root)/'second')
            with patch.object(install,'discovery_locations',return_value=[first,first.parent.parent]):
                self.assertEqual(install.resolve_editor(),first.resolve())
            with patch.object(install,'discovery_locations',return_value=[first,second]):
                with self.assertRaisesRegex(ValueError,'Multiple'):install.resolve_editor()
            with patch.object(install,'discovery_locations',return_value=[]):
                with self.assertRaisesRegex(FileNotFoundError,'SC2_EDITOR_PATH'):install.resolve_editor()

    def test_modified_or_unsupported_binaries_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.editor(root)
            with self.assertRaisesRegex(ValueError,'Unsupported Editor binary'):install.validate_editor(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(install,'SUPPORTED_SHA256',digest):
                self.assertTrue(install.validate_editor(path)['originalBinaryVerified'])
                path.write_bytes(path.read_bytes()+b'changed')
                with self.assertRaisesRegex(ValueError,'Unsupported'):install.validate_editor(path)

    def test_x86_and_non_pe_are_rejected_before_hash_validation(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.editor(root);data=bytearray(path.read_bytes());data[132:134]=b'\x4c\x01';path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'AMD64'):install.validate_editor(path)
            path.write_bytes(b'not an exe')
            with self.assertRaisesRegex(ValueError,'Windows executable'):install.validate_editor(path)

    def test_existing_worker_rejects_different_installation(self):
        with tempfile.TemporaryDirectory() as root:
            first=self.editor(Path(root)/'first');second=self.editor(Path(root)/'second')
            worker=Worker.__new__(Worker);worker.alive=lambda:True;worker.state={'editorPath':str(first),'renderBackend':'vulkan'}
            worker.ensure('unused',editor_path=str(first))
            with self.assertRaisesRegex(ValueError,'restart'):worker.ensure('unused',editor_path=str(second))

    def test_missing_editor_is_rejected_before_worker_files_or_process_creation(self):
        worker=Worker.__new__(Worker);worker.alive=lambda:False
        with patch('sc2native.session.select_backend',return_value='legacy'),patch('sc2native.session.resolve_editor',side_effect=FileNotFoundError('missing')):
            with self.assertRaises(FileNotFoundError):worker.ensure('unused')


if __name__=='__main__':unittest.main()
