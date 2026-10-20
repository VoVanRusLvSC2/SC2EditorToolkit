import hashlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from sc2native.map_objects import placement_records, search_options, search_records, terrain_metadata, read_components
from map_archive_fixture import OBJECTS, TERRAIN, create_archive


class SavedObjects(unittest.TestCase):
    def test_filters_coordinates_and_pagination(self):
        records = placement_records(OBJECTS)
        first = search_records(records, search_options({'query': 'MARINE', 'limit': 1}))
        self.assertEqual(first['totalMatches'], 2)
        self.assertEqual(first['objects'][0]['position'], {'x': 8, 'y': 12, 'z': 0})
        self.assertEqual(first['nextOffset'], 1)
        second = search_records(records, search_options({'query': 'marine', 'offset': 1}))
        self.assertEqual(second['objects'][0]['owner'], 2)
        self.assertEqual(len({r['objectKey'] for r in records}), 6)
        chosen = search_records(records, search_options({'kinds': ['unit'], 'owner': 1,
            'bounds': {'left': 0, 'bottom': 0, 'right': 16, 'top': 24}}))
        self.assertEqual([r['id'] for r in chosen['objects']], ['1'])
        self.assertEqual(chosen['objectsWithoutPosition'], 1)
        self.assertEqual(search_records(records, search_options({'query': 'rally'}))['objects'][0]['kind'], 'point')
        self.assertEqual(terrain_metadata(TERRAIN)['bounds'], {'left': 0, 'bottom': 0, 'right': 64, 'top': 48})

    def test_invalid_search_and_xml_are_rejected(self):
        for request in ({'query': 1}, {'kinds': []}, {'kinds': ['region']}, {'limit': True},
                        {'limit': 501}, {'offset': -1}, {'owner': False},
                        {'bounds': {'left': 0, 'bottom': 0, 'right': 0, 'top': 1}},
                        {'bounds': {'left': float('nan'), 'bottom': 0, 'right': 1, 'top': 1}},
                        {'bounds': {'left': 0, 'bottom': 0, 'right': 10**1000, 'top': 1}}):
            with self.subTest(request=str(request)[:80]), self.assertRaises(ValueError):
                search_options(request)
        for data in (b'<!DOCTYPE PlacedObjects [<!ENTITY x "boom">]><PlacedObjects>&x;</PlacedObjects>',
                     b'<Wrong/>', b'<PlacedObjects><broken>', '<PlacedObjects/>'.encode('utf16')):
            with self.assertRaises((ValueError, UnicodeError)):
                placement_records(data)
        self.assertIsNone(placement_records(b'<PlacedObjects><ObjectUnit Id="1" Position="NaN,1,0"/></PlacedObjects>')[0]['position'])

    def test_omitted_archive_member_is_read_by_name_and_failure_is_not_empty(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch('sc2native.map_objects.subprocess.run', side_effect=[
                SimpleNamespace(returncode=0, stdout=b'', stderr=b''),
                SimpleNamespace(returncode=0, stdout=OBJECTS, stderr=b'')]):
            self.assertEqual(read_components('map.SC2Map', 'mpqcli')['Objects'], OBJECTS)
        with patch('sc2native.map_objects.subprocess.run', side_effect=[
                SimpleNamespace(returncode=0, stdout=b'', stderr=b''),
                SimpleNamespace(returncode=1, stdout=b'', stderr=b'cannot open member')]):
            with self.assertRaises(RuntimeError):read_components('map.SC2Map', 'mpqcli')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows archive runtime')
    def test_real_archive_query_never_starts_editor_or_changes_source(self):
        from sc2native.session import Worker
        from file_prepare import mpq_tool
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = create_archive(directory / 'fixture', mpq_tool())
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            worker = object.__new__(Worker)
            worker.work = directory / 'worker';worker.lock = threading.Lock()
            worker.ensure = Mock(side_effect=AssertionError('Object search must not start Editor'))
            result = worker.search_objects({'map': str(source), 'query': 'scout', 'owner': 2})
            self.assertEqual(result['totalMatches'], 1)
            self.assertEqual(result['objects'][0]['position']['x'], 48)
            self.assertFalse(result['editorRequired'])
            self.assertEqual(result['mapSha256'], before)
            self.assertTrue(result['sourceUnchanged'])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            worker.ensure.assert_not_called()
            self.assertFalse(worker.lock.locked())
