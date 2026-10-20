import sys,tempfile,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.map_images import export_options,inspect_image

class MapImages(unittest.TestCase):
    def test_invalid_options_rejected_before_editor_work(self):
        for size in (True,1.0,'2048',0,8192):
            with self.subTest(size=size),self.assertRaises(ValueError):export_options({'size':size})
        for key in ('include_units','include_doodads'):
            for value in (0,1,'false',None):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):export_options({key:value})
        for request in ({'camera':'Front'},{'time_ms':0},{'overwrite':'false'}):
            with self.assertRaises(ValueError):export_options(request)

    def test_original_image_integrity_and_bounded_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'native.png';preview=Path(tmp)/'preview.png'
            image=Image.new('RGB',(2048,1024));image.putdata([(x%256,(x//8)%256,(x//16)%256) for x in range(2048*1024)]);image.save(source)
            original=source.read_bytes();r=inspect_image(source,preview)
            self.assertTrue(r['imageHasDetail']);self.assertEqual((r['width'],r['height']),(2048,1024));self.assertEqual(source.read_bytes(),original)
            with Image.open(preview) as p:self.assertEqual(p.size,(1280,640))
            tga=Path(tmp)/'native.tga';png=Path(tmp)/'converted.png';image.save(tga)
            native_bytes=tga.read_bytes();stats=inspect_image(tga,png_output=png)
            self.assertEqual(stats['format'],'TGA');self.assertEqual(tga.read_bytes(),native_bytes)
            with Image.open(png) as converted:self.assertEqual(converted.tobytes(),image.tobytes())
            Image.new('RGB',(512,512),'black').save(source)
            self.assertFalse(inspect_image(source)['imageHasDetail'])
            Image.new('RGB',(512,512),'gray').save(source)
            self.assertFalse(inspect_image(source)['imageHasDetail'])
            source.write_bytes(b'\x89PNG\r\n\x1a\ntruncated')
            with self.assertRaises(OSError):inspect_image(source)

if __name__=='__main__':unittest.main()
