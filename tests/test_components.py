import shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.components import snapshot_components,compare_components,read_string_table
from sc2native.report import read_declared_dependencies
from map_archive_fixture import create_archive

ROOT=Path(__file__).resolve().parents[1]
class Components(unittest.TestCase):
    @unittest.skipUnless((ROOT/'tools/mpqcli/mpqcli.exe').is_file(),'mpqcli required')
    def test_dependency_header_only_is_empty_but_unclosed_root_stays_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);tool=ROOT/'tools/mpqcli/mpqcli.exe';source=create_archive(work,tool)
            cases=[(b'<?xml version="1.0" encoding="utf-8"?>\r\n',True,[]),
                   (b'\xef\xbb\xbf<?xml version="1.0"?>\n<!-- empty -->',True,[]),
                   (b' \r\n',True,[]),
                   (b'<?xml version="1.0"?><DocInfo>',False,None),
                   (b'<?xml version="1.0"?><DocInfo><Dependencies>',False,None),
                   (b'<!-- unclosed',False,None),
                   (b'<?xml version="1.0"?>garbage',False,None),
                   (b'<DocInfo><Dependencies><Value>file:Mods/Shared.SC2Mod</Value></Dependencies></DocInfo>',True,['file:Mods/Shared.SC2Mod'])]
            for text,complete,values in cases:
                with self.subTest(text=text):
                    payload=work/'DocumentInfo';payload.write_bytes(text)
                    subprocess.run([str(tool),'add','-w','-p','DocumentInfo',str(source),str(payload)],check=True,capture_output=True,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    result=read_declared_dependencies(source,work)
                    self.assertEqual(result['complete'],complete,result)
                    self.assertEqual(result['values'],values,result)
    @unittest.skipUnless((ROOT/'tools/mpqcli/mpqcli.exe').is_file(),'mpqcli required')
    def test_localized_context_uses_exact_stored_member_spelling(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);tool=ROOT/'tools/mpqcli/mpqcli.exe';source=create_archive(work,tool)
            payload=work/'strings';payload.write_bytes(b'Variable/Name/1234ABCD=Pretty Display Name\n')
            subprocess.run([str(tool),'add','-w','-p','enUS.SC2Data\\LocalizedData\\TriggerStrings.txt',str(source),str(payload)],check=True,capture_output=True)
            strings=read_string_table(source,tool,'enUS.SC2Data/LocalizedData/TriggerStrings.txt',work)
            self.assertEqual(strings,{'Variable/Name/1234ABCD':'Pretty Display Name'})
    @unittest.skipUnless((ROOT/'tools/mpqcli/mpqcli.exe').is_file(),'mpqcli required')
    def test_native_archive_member_changes_and_text_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);tool=ROOT/'tools/mpqcli/mpqcli.exe';source=create_archive(work,tool)
            nested=work/'nested';nested.write_bytes(b'<Catalog/>')
            subprocess.run([str(tool),'add','-w','-p','Base.SC2Data\\GameData\\UnitData.xml',str(source),str(nested)],check=True,capture_output=True)
            before=snapshot_components(source,tool,work);saved=work/'Saved.SC2Map';shutil.copyfile(source,saved)
            payload=work/'changed';payload.write_text('<PlacedObjects Version="27"/>')
            subprocess.run([str(tool),'add','-w','-p','Objects',str(saved),str(payload)],check=True,capture_output=True)
            after=snapshot_components(saved,tool,work)
            comparison=compare_components(before,after,before_archive=source,after_archive=saved,tool=tool,work=work,include_diffs=True)
            self.assertTrue(comparison['complete']);self.assertFalse(comparison['equal'])
            objects=next(c for c in comparison['changes'] if c['name']=='Objects')
            self.assertEqual(objects['change'],'modified');self.assertIn('-<ObjectUnit',objects['textDiff'])
            self.assertTrue(compare_components(before,snapshot_components(source,tool,work))['equal'])
    def test_incomplete_comparison_not_verified(self):
        result=compare_components({'members':{},'count':0,'complete':False},{'members':{},'count':0,'complete':True})
        self.assertFalse(result['complete'])

if __name__=='__main__':unittest.main()
