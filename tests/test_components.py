import shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.components import snapshot_components,compare_components,read_string_table
from map_archive_fixture import create_archive

ROOT=Path(__file__).resolve().parents[1]
class Components(unittest.TestCase):
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
