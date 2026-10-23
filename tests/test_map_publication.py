"""Failed native/visibility checks must not publish an apparently usable image."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))


@unittest.skipUnless(sys.platform == 'win32', 'Windows session runtime')
class MapPublication(unittest.TestCase):
    def test_invalid_output_never_opens_editor_or_prepares_map(self):
        from sc2native.session import Worker
        worker=object.__new__(Worker);worker.lock=threading.Lock();worker._prepare_terrain=Mock()
        for value in ('', '   ', None, 12, True, []):
            with self.subTest(output=value),self.assertRaisesRegex(ValueError,'nonempty PNG path'):
                worker.export_map_image({'output':value})
            self.assertFalse(worker.lock.locked())
        worker._prepare_terrain.assert_not_called()

    def test_unconfirmed_black_and_visible_exports_are_not_published(self):
        from sc2native.session import Worker
        for failure in ('unconfirmed', 'filters_unconfirmed', 'wrong_filter', 'missing_filter', 'not_custom', 'black', 'visible'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                source = work / 'Private.SC2Map'
                source.write_bytes(b'unchanged test archive')
                worker = object.__new__(Worker)
                worker.work = work
                worker.lock = threading.Lock()
                worker.scene = None
                worker.artifacts = Mock()
                worker.monitor = SimpleNamespace(snapshot=lambda: {
                    'visibleWindowsOnUserDesktopPeak': int(failure == 'visible'),
                    'editorForegroundSamples': 0})
                import hashlib
                worker._prepare_terrain = lambda request: (source, hashlib.sha256(source.read_bytes()).hexdigest())

                def native(directory, operation, map_path, terrain):
                    image = Image.new('RGB', (512, 512))
                    if failure != 'black':
                        image.putdata([(i % 256, (i // 4) % 256, (i // 8) % 256) for i in range(512 * 512)])
                    image.save(map_path)
                    settings={'exported': failure != 'unconfirmed', 'fullMap': True,
                            'topDown': True, 'optionsConfirmed': True, 'size': 512,
                            'includeUnits': True, 'includeDoodads': True,'filtersConfirmed': failure != 'filters_unconfirmed',
                            'customOptions': failure != 'not_custom', 'actualUnits': int(failure != 'wrong_filter'),'actualDoodads':1}
                    if failure=='missing_filter':del settings['actualUnits']
                    return {'terrainExport':settings}

                worker._native = native
                if failure in ('unconfirmed','filters_unconfirmed','not_custom'):
                    with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                        worker.export_map_image({'size': 512})
                elif failure in ('wrong_filter','missing_filter'):
                    with self.assertRaisesRegex(RuntimeError,'readback did not match'):
                        worker.export_map_image({'size':512})
                else:
                    result = worker.export_map_image({'size': 512})
                    self.assertEqual(result['status'], 'FAILED')
                    self.assertFalse(result['wholeMapVerified'])
                    self.assertNotIn('artifact', result)
                worker.artifacts.publish_file.assert_not_called()
                worker.artifacts.register_png.assert_not_called()
                self.assertFalse(worker.lock.locked())


if __name__ == '__main__':
    unittest.main()
