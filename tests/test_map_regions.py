import hashlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from sc2native.map_regions import crop_region, pixel_bounds, validate_region
from sc2native.map_objects import terrain_metadata
from map_archive_fixture import TERRAIN


class MapRegions(unittest.TestCase):
    def test_crop_pixel_identity_orientation_and_covered_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source, target, preview = (directory / name for name in ('full.png', 'region.png', 'preview.png'))
            image = Image.new('RGB', (640, 480))
            image.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(480) for x in range(640)])
            image.save(source);original = source.read_bytes()
            bounds = {'left': 8, 'bottom': 12, 'right': 24, 'top': 36}
            result = crop_region(source, target, preview, bounds, terrain_metadata(TERRAIN))
            self.assertEqual(result['sourcePixelBounds'], [80, 120, 240, 360])
            self.assertEqual(result['coveredBounds'], bounds)
            with Image.open(target) as cropped:
                self.assertEqual(cropped.size, (160, 240))
                self.assertEqual(cropped.tobytes(), image.crop((80, 120, 240, 360)).tobytes())
            self.assertFalse(result['resampled'])
            self.assertFalse(result['coordinateMappingValidated'])
            self.assertEqual(source.read_bytes(), original)

    def test_outward_rounding_and_unsupported_mapping_fail_closed(self):
        meta = terrain_metadata(TERRAIN)
        self.assertEqual(pixel_bounds({'left': .11, 'bottom': .11, 'right': .21, 'top': .21}, meta['bounds'], 640, 480), (1, 477, 3, 479))
        for bounds in ({'left': -1, 'bottom': 0, 'right': 1, 'top': 1},
                       {'left': 0, 'bottom': 0, 'right': 65, 'top': 1}):
            with self.assertRaises(ValueError):validate_region(bounds, meta)
        transformed = terrain_metadata(TERRAIN.replace(b'scale="1 1 1"', b'scale="2 1 1"'))
        with self.assertRaises(ValueError):validate_region({'left': 1, 'bottom': 1, 'right': 2, 'top': 2}, transformed)
        with self.assertRaises(ValueError):pixel_bounds(meta['bounds'], meta['bounds'], 640, 640)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows session runtime')
    def test_region_publication_and_failure_paths_without_editor(self):
        from sc2native.session import Worker
        from sc2native.artifacts import ArtifactStore
        for failure in ('none', 'native', 'black', 'source_changed', 'visible'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary);source = work / 'Saved.SC2Map';source.write_bytes(b'unchanged')
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                worker = object.__new__(Worker);worker.work = work;worker.lock = threading.Lock()
                worker.artifacts = ArtifactStore(work / 'artifacts')
                worker.monitor = SimpleNamespace(snapshot=lambda: {'visibleWindowsOnUserDesktopPeak': int(failure == 'visible'), 'editorForegroundSamples': 0})
                worker._snapshot_map = lambda request: (source, digest, source, work)
                image = Image.new('RGB', (640, 480))
                if failure != 'black':image.putdata([(i % 256, (i // 4) % 256, (i // 8) % 256) for i in range(640 * 480)])
                full = work / 'full.png';image.save(full)
                def export(request, **kwargs):
                    self.assertTrue(kwargs['_locked']);self.assertFalse(kwargs['_publish'])
                    if failure == 'source_changed':source.write_bytes(b'changed')
                    return {'status': 'FAILED' if failure == 'native' else 'MAP_IMAGE_EXPORTED',
                            'capturePath': str(full), 'native': {}, 'nativeImageSha256': 'test'}
                worker.export_map_image = export
                target = work / 'chosen.png'
                with patch('sc2native.map_objects.read_components', return_value={'t3Terrain.xml': TERRAIN}):
                    result = worker.capture_map_region({'bounds': {'left': 8, 'bottom': 12, 'right': 24, 'top': 36}, 'output': str(target)})
                self.assertEqual(target.exists(), failure == 'none')
                self.assertEqual(result['status'], 'MAP_REGION_CAPTURED' if failure == 'none' else 'FAILED')
                if failure == 'none':
                    self.assertEqual(result['region']['sourcePixelBounds'], [80, 120, 240, 360])
                    self.assertEqual(Path(result['artifact']['path']), target)
                    self.assertFalse(result['coordinateMappingValidated'])
                self.assertFalse(worker.lock.locked())
