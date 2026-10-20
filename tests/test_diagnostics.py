import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.diagnostics import parse_native_diagnostics
class Diagnostics(unittest.TestCase):
    def test_unreadable_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:self.assertIsNone(parse_native_diagnostics(d)['editorLog']['clear'])
    def test_errors_stay_separate(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'native-log.txt').write_text('compiler row=0 column=1 text=Invalid parameter list\n'
                'diagnostics window=Console\ndiagnostics readable=text\ndiagnostics text=ERROR missing texture\n',encoding='utf8')
            result=parse_native_diagnostics(d)
            self.assertEqual(result['compilerErrors'][0]['message'],'Invalid parameter list')
            self.assertEqual(result['editorLog']['recognizedErrors'],['ERROR missing texture'])
            self.assertFalse(result['editorLog']['clear'])
if __name__=='__main__':unittest.main()
