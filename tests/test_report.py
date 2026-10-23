import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.report import check_document
from sc2native.artifacts import ArtifactStore


class Report(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'Source.SC2Map';self.source.write_bytes(b'original source')
        self.deps=patch('sc2native.report.read_declared_dependencies',return_value={'complete':True,'values':['file:Mods/Liberty.SC2Mod']});self.deps.start()
        self.worker=SimpleNamespace(work=self.root,state={'editorInfo':{'version':'verified-build'}},monitor=None,
            artifacts=ArtifactStore(self.root/'artifacts'),_check_abort=Mock(),alive=lambda:True,
            validate_document=Mock(return_value={'status':'NATIVE_DOCUMENT_VALIDATED','nativeValidationPassed':True,'nativeLoadVerified':True}),
            save_reopen_document=Mock(return_value={'status':'NATIVE_SAVE_REOPEN_VERIFIED','nativeValidationPassed':True,'nativeLoadVerified':True}),
            compile_current=Mock(return_value={'status':'NATIVE_XML_TO_GALAXY_BACKGROUND_PASSED','nativeGenerationVerified':True,'nativeCompilePassed':True}),
            export_galaxy=Mock(return_value={'status':'GALAXY_EXPORTED'}))
    def tearDown(self):self.deps.stop();self.temp.cleanup()
    def test_revision_exact_downloadable_report_and_native_exports(self):
        result=check_document(self.worker,{'map':str(self.source)})
        report=json.loads(Path(result['reportArtifact']['path']).read_text(encoding='utf8'))
        self.assertEqual(result['mapRevision'],result['sourceSha256']);self.assertTrue(report['sourceUnchanged'])
        self.assertEqual(report['status'],'NATIVE_MAP_CHECK_PASSED');self.assertIn('galaxyExport',report['checks'])
        self.assertNotIn('reportArtifact',report)
    def test_unreadable_diagnostics_never_become_success(self):
        self.worker.validate_document.return_value.update(status='NATIVE_DOCUMENT_CHECK_INCOMPLETE',nativeValidationPassed=None)
        result=check_document(self.worker,{'map':str(self.source)})
        self.assertEqual(result['status'],'NATIVE_MAP_CHECK_INCOMPLETE');self.assertTrue(result['nativeCompilePassed'])
    def test_missing_dependency_declarations_are_incomplete_not_empty(self):
        with patch('sc2native.report.read_declared_dependencies',return_value={'complete':False,'values':None}):
            result=check_document(self.worker,{'map':str(self.source)})
        self.assertEqual(result['status'],'NATIVE_MAP_CHECK_INCOMPLETE');self.assertIsNone(result['declaredDependencies']['values'])
    def test_compiler_failure_keeps_generation_separate(self):
        self.worker.compile_current.return_value.update(status='FAILED',nativeCompilePassed=False,compilerErrors=2)
        result=check_document(self.worker,{'map':str(self.source),'save_reopen':True})
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['nativeGenerationVerified']);self.assertFalse(result['nativeCompilePassed'])
        self.worker.save_reopen_document.assert_called_once();self.worker.export_galaxy.assert_called_once()
    def test_unconfirmed_load_does_not_compile_and_changed_source_fails(self):
        def load(options):
            self.source.write_bytes(b'externally changed')
            return {'status':'FAILED','nativeLoadVerified':False,'nativeValidationPassed':False}
        self.worker.validate_document.side_effect=load
        result=check_document(self.worker,{'map':str(self.source)})
        self.assertEqual(result['status'],'FAILED');self.assertFalse(result['sourceUnchanged']);self.worker.compile_current.assert_not_called()

if __name__=='__main__':unittest.main()
