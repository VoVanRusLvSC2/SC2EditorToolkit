import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sc2native.revisions import snapshot,bind_sources

class Revisions(unittest.TestCase):
    def test_changed_dependency_changes_project_revision_with_same_map(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work);mods=root/'Mods';mods.mkdir();source=mods/'Map.SC2Mod';dep=mods/'Shared.SC2Mod'
            source.write_bytes(b'map');dep.write_bytes(b'old');(root/'.build.info').write_bytes(b'game build')
            read=lambda p,w:{'complete':True,'values':['file:Mods/Shared.SC2Mod'] if p==source else []}
            with patch('sc2native.revisions.read_declared_dependencies',side_effect=read):
                a=snapshot(source,root/'Support64/SC2Editor_x64.exe',root)
                dep.write_bytes(b'new');b=snapshot(source,root/'Support64/SC2Editor_x64.exe',root)
            self.assertNotEqual(a['revision'],b['revision']);self.assertEqual(a['archives'][0]['sha256'],b['archives'][0]['sha256'])
            bound=bind_sources(b,['All Data','Core.SC2Mod','Shared.SC2Mod','Seed.SC2Mod'],'Seed.SC2Mod')
            self.assertTrue(bound['projectRevisionComplete']);self.assertFalse(bound['nativeResolvedPhysicalPathsVerified'])
            self.assertFalse(bind_sources(b,['All Data','Unknown.SC2Mod'],'Seed.SC2Mod')['projectRevisionComplete'])
    def test_unresolved_published_dependency_is_explicit(self):
        with tempfile.TemporaryDirectory() as work:
            source=Path(work)/'Map.SC2Mod';source.write_bytes(b'map')
            with patch('sc2native.revisions.read_declared_dependencies',return_value={'complete':True,'values':['bnet:Published/1/99']}):
                value=snapshot(source,None,Path(work))
            self.assertFalse(value['localDeclaredArchiveRevisionsVerified']);self.assertTrue(value['unresolved'])

if __name__=='__main__':unittest.main()
