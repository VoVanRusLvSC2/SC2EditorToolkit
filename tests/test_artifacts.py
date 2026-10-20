import hashlib,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.artifacts import ArtifactStore

class Exports(unittest.TestCase):
    def test_exact_bytes_and_no_silent_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ArtifactStore(directory);target=Path(directory)/'Native.galaxy';data=b'// native\r\nint x=1;\r\n'
            item=store.export(data,output=target)
            self.assertEqual(target.read_bytes(),data);self.assertEqual(item['sha256'],hashlib.sha256(data).hexdigest())
            with self.assertRaises(FileExistsError):store.export(b'bad',output=target)
            self.assertEqual(target.read_bytes(),data)
            store.export(b'new',output=target,overwrite=True);self.assertEqual(target.read_bytes(),b'new')
            with self.assertRaises(RuntimeError):store.get(item['id'])
    def test_opaque_download_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ArtifactStore(directory)
            with self.assertRaises(KeyError):store.get('../../anything')

if __name__=='__main__':unittest.main()
