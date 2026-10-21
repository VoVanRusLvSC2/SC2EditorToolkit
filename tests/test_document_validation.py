import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.document_validation import validate_document
from sc2native.artifacts import ArtifactStore

class WorkerStub:
    def __init__(self,work):
        self.work=work;self.state=None;self.monitor=None;self.scene=None;self.last_result=None
        self.artifacts=ArtifactStore(work/'artifacts');self.reset=False
    def alive(self):return self.state is not None
    def ensure(self,baseline,**options):self.state={'pid':1,'createTimeFiletime':2,'desktop':'SC2Native-test','documentPath':str(baseline)}
    def _reset_owned_editor(self):self.state=None;self.reset=True

class DocumentValidation(unittest.TestCase):
    def test_invalid_arguments_never_start_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=WorkerStub(Path(directory))
            for request in ({'map':12},{'map':''},{'map':'x','include_diffs':'true'},{'map':'x','output':False}):
                with self.assertRaises(ValueError):validate_document(worker,request,roundtrip=True)
                self.assertIsNone(worker.state)
    def test_reopen_failure_retains_native_save_diff_but_publishes_no_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);source=work/'Source.SC2Mod';source.write_bytes(b'original')
            output=work/'Output.SC2Mod';worker=WorkerStub(work/'runtime');worker.work.mkdir()
            def phase(worker,directory,name,operation,**kwargs):
                if operation=='save-document':kwargs['path'].write_bytes(b'native serialization')
                confirmed=operation!='reopen-document'
                return {'phase':name,'nativeConfirmed':confirmed,'native':{'mapLoaded':1,'documentIo':{'saved':1,'dataLoaded':1}},
                    'diagnostics':{'newErrors':[],'newWarnings':[],'newErrorsClear':True,'inspectionComplete':True}}
            snapshot={'complete':True,'count':1,'members':{'0:Triggers':{'name':'Triggers','locale':'0','bytes':1,'sha256':'a'}}}
            with patch('sc2native.document_validation._phase',side_effect=phase),\
                 patch('sc2native.document_validation.files.mpq_tool',return_value='unused'),\
                 patch('sc2native.document_validation.snapshot_components',return_value=snapshot):
                result=validate_document(worker,{'map':str(source),'output':str(output),'include_diffs':True},roundtrip=True)
            self.assertEqual(result['status'],'FAILED');self.assertTrue(result['nativeSaveVerified'])
            self.assertFalse(result['nativeReopenVerified']);self.assertFalse(result['componentComparisonVerified'])
            self.assertFalse(output.exists());self.assertNotIn('savedArchive',result)
            report=json.loads(Path(result['componentDiffArtifact']['path']).read_text())
            self.assertIsNone(report['savedToReopened']);self.assertTrue(result['sourceUnchanged'])
            self.assertEqual(source.read_bytes(),b'original');self.assertTrue(worker.reset)

if __name__=='__main__':unittest.main()
