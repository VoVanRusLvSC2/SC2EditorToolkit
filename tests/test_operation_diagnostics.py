import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.diagnostics import operation_diagnostics,classify_native_message

class OperationDiagnostics(unittest.TestCase):
    def capture(self,before,after,events=(),complete=True):
        directory=Path(self.temp.name)
        for name,rows in [('before',before),('after',after)]:
            (directory/('diagnostics-'+name+'.json')).write_text(json.dumps({'complete':complete,'channels':[
                {'key':'Messages|13','complete':complete,'entries':[{'text':t} for t in rows]}]}))
        (directory/'diagnostics-events.json').write_text(json.dumps({'complete':complete,'events':events}))
        return operation_diagnostics(directory)
    def setUp(self):self.temp=tempfile.TemporaryDirectory()
    def tearDown(self):self.temp.cleanup()
    def test_old_errors_not_recounted(self):
        result=self.capture(['Error: old'],['Error: old','Warning: new'])
        self.assertEqual(result['newErrors'],[]);self.assertTrue(result['newErrorsClear'])
        self.assertEqual(len(result['baselineMessages']),1);self.assertEqual(len(result['newWarnings']),1)
    def test_identical_repeat_captured_by_append(self):
        result=self.capture(['Error: same'],['Error: same'],[{'channel':'Messages|13','kind':'append','text':'Error: same\n'}])
        self.assertEqual(result['newErrorCount'],1);self.assertFalse(result['newErrorsClear'])
    def test_replacement_is_unknown_even_when_empty(self):
        result=self.capture(['Error: old'],[],[{'channel':'Messages|13','kind':'clear','text':''}])
        self.assertIsNone(result['newErrorsClear']);self.assertIsNone(result['newErrorCount'])
    def test_truncated_empty_is_not_zero(self):
        self.assertIsNone(self.capture([],[],complete=False)['newErrorCount'])
    def test_append_then_clear_preserves_observed_error(self):
        result=self.capture([],[],[{'channel':'Messages|13','kind':'append','text':'Error: transient\n'},
                                 {'channel':'Messages|13','kind':'clear','text':''}])
        self.assertFalse(result['newErrorsClear']);self.assertEqual(result['knownNewErrorCount'],1)
        self.assertIsNone(result['newErrorCount'])
    def test_unclassified_preserved(self):
        result=self.capture([],['UI: strange message'])
        self.assertIsNone(result['newErrorsClear']);self.assertEqual(len(result['unclassifiedMessages']),1)
    def test_explicit_ids_only(self):
        error=classify_native_message("Error: model 'MissingModel' not found")
        self.assertEqual(error['type'],'missingModel');self.assertEqual(error['relatedIds'],['MissingModel'])
        error=classify_native_message("Error: XML parse error loading Unit from 'GameData/UnitData.xml'")
        self.assertEqual(error['type'],'dataValidation');self.assertEqual(error['relatedIds'],[])
    def test_text_classification_contract(self):
        for message,category in [
            ('Error: dependency not found','missingDependency'),
            ('Error: invalid parent="MissingParent"','invalidInheritance'),
            ("Warning: actor 'DuplicateActor' already exists",'actorConflict'),
            ('Error: texture missing','missingAsset')]:
            self.assertEqual(classify_native_message(message)['type'],category)
    def test_console_echo_is_preserved_without_masking_real_errors(self):
        channel='Console - StarCraft II Editor|RichEdit20W|15'
        echo=classify_native_message('> browse',channel=channel)
        self.assertEqual(echo['severity'],'info');self.assertEqual(echo['type'],'consoleCommandEcho')
        self.assertEqual(echo['message'],'> browse')
        self.assertEqual(classify_native_message('Error: actual failure',channel=channel)['severity'],'error')
        self.assertEqual(classify_native_message('> browse',channel='Messages|13')['severity'],'unknown')

    def test_missing_capture_unknown(self):
        self.assertIsNone(operation_diagnostics(self.temp.name)['newErrorsClear'])

if __name__=='__main__':unittest.main()
