import json,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import native_xml_oracle as oracle
from sc2native.gui_normalization import compare_native_gui
from sc2native.session import Worker


class ConversionRecovery(unittest.TestCase):
    def test_controller_loader_failure_keeps_win32_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory)
            def launch(command,stdout,stderr,**options):
                stderr.write(b'Cannot install Editor-thread focus veto (Win32=126)\n');stderr.flush()
                process=MagicMock();process.pid=123;process.wait.return_value=2;return process
            with patch.object(oracle.subprocess,'Popen',side_effect=launch):
                with self.assertRaises(oracle.NativeStepError) as caught:oracle.native_step(job,'00-inspect',1,'Seed.SC2Map')
            self.assertIn('Win32=126',str(caught.exception));self.assertEqual(caught.exception.native_result['controllerExitCode'],2)
            self.assertFalse(caught.exception.native_result['handlerCompletionKnown'])
    def test_library_qualified_loss_and_duplicate_identity(self):
        before=b'<TriggerData><Library Id="AAAA0001"><Element Type="Param" Id="1"/></Library><Library Id="AAAA0002"><Element Type="Param" Id="1"/></Library></TriggerData>'
        after=b'<TriggerData><Library Id="AAAA0002"><Element Type="Param" Id="1"/></Library></TriggerData>'
        result=compare_native_gui(before,after)
        self.assertEqual(result['removedElements'],[{'library':'AAAA0001','type':'Param','id':'1'}])
        self.assertFalse(result['semanticEquivalenceVerified'])
        with self.assertRaises(ValueError):compare_native_gui(b'<TriggerData><Element Type="Param" Id="1"/><Element Type="Param" Id="1"/></TriggerData>',after)

    def test_failed_request_cannot_export_previous_source(self):
        worker=Worker.__new__(Worker);worker.lock=threading.Lock();worker.last_result={'old':'source'}
        with self.assertRaises(FileNotFoundError):worker.execute({'template':'__missing_template__.SC2Map'})
        self.assertIsNone(worker.last_result)
        worker.last_result={'old':'source'};worker.alive=lambda:True
        worker._context=MagicMock(side_effect=ValueError('context missing'))
        with self.assertRaises(ValueError):worker.compile_current({})
        self.assertIsNone(worker.last_result)
        with self.assertRaises(RuntimeError):worker.export_galaxy({})

    def test_native_failure_retains_exact_step_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory);archive=job/'Input.SC2Map';archive.write_bytes(b'map');editor=job/'editor';editor.write_bytes(b'exe')
            manifest={'workingDocument':str(archive),'workingDocumentSha256':oracle.files.sha(archive),'editor':str(editor),
                'editorSha256':oracle.files.sha(editor),'contextLabel':'A','scope':'mapRoot'}
            (job/'manifest.json').write_text(json.dumps(manifest))
            args=SimpleNamespace(pid=1,job=str(job),current_document='Seed.SC2Map',marker='',expect_text=[],compile=True)
            native={'status':'NOT_CONFIRMED','error':11,'mapLoaded':0,'failure':'saved document mismatch'}
            def invoke(job,stage,*a,**kw):
                if stage=='00-inspect':return {'documentDirty':False}
                raise oracle.NativeStepError('exact failure',native,job/stage)
            with patch.object(oracle,'Session',return_value=MagicMock()),patch.object(oracle,'prepare',return_value=manifest),patch.object(oracle,'native_step',side_effect=invoke):
                result=oracle.convert(args)
            self.assertEqual(result['failureStage'],'load');self.assertEqual(result['failureNative'],native)
            self.assertEqual(result['steps']['load'],native);self.assertFalse(result['nativeGenerationVerified'])
            self.assertEqual(result['failureEvidence'],str(job/'01-load'))

    def test_dirty_document_is_saved_and_dropped_gui_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory);archive=job/'Input.SC2Map';archive.write_bytes(b'map');editor=job/'editor';editor.write_bytes(b'exe')
            submitted=b'<TriggerData><Element Type="Param" Id="1"/><Element Type="Param" Id="2"/></TriggerData>'
            components=job/'components';components.mkdir();(components/'Triggers').write_bytes(submitted)
            manifest={'jobId':'1234','workingDocument':str(archive),'workingDocumentSha256':oracle.files.sha(archive),'editor':str(editor),
                'editorSha256':oracle.files.sha(editor),'contextLabel':'A','scope':'mapRoot'}
            (job/'manifest.json').write_text(json.dumps(manifest));calls=[]
            args=SimpleNamespace(pid=1,job=str(job),current_document='Seed.SC2Map',marker='',expect_text=[],compile=True,mpqcli=None)
            def invoke(job,stage,*a,**kw):
                calls.append(stage)
                value={'editorForegroundEvents':0}
                if stage=='00-inspect':value['documentDirty']=False
                if stage=='01-load':value['mapLoaded']=1
                if stage=='01-inspect':value['documentDirty']=True
                if stage=='01-save-document':kw['map_path'].write_bytes(b'native archive');value['documentIo']={'saved':1}
                return value
            saved=SimpleNamespace(returncode=0,stdout=b'<TriggerData><Element Type="Param" Id="1"/></TriggerData>')
            with patch.object(oracle,'Session',return_value=MagicMock()),patch.object(oracle,'prepare',return_value=manifest),\
                 patch.object(oracle,'native_step',side_effect=invoke),patch.object(oracle.files,'mpq_tool',return_value='mpqcli'),\
                 patch.object(oracle.subprocess,'run',return_value=saved):result=oracle.convert(args)
            self.assertEqual(result['failureKind'],'NATIVE_GUI_NORMALIZATION_LOSS')
            self.assertEqual(result['nativeNormalization']['removedElementCount'],1)
            self.assertTrue(Path(result['currentDocumentPath']).is_file())
            self.assertEqual(calls,['00-inspect','01-load','01-inspect','01-save-document'])
            self.assertFalse(result['nativeGenerationVerified']);self.assertFalse(result['nativeCompilePassed'])


if __name__=='__main__':unittest.main()
