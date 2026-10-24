import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sc2native.data_audit import check_page,resource_key,audit_data,audit_options
from sc2native.artifacts import ArtifactStore


class DataAuditCoverageTests(unittest.TestCase):
    def page(self):
        return dict(schemaVersion=1,traversalComplete=True,variant=0,catalogIndex=94,catalog='Unit',
                    dataSources=['All Data','Liberty','PrivateMap'],totalEntries=2,offset=0,nextOffset=1,
                    objects=[dict(id='Marine',nativeClass='CUnit',fieldsVisited=10,leafValuesVisited=8,
                                  getterErrors=0,unclassifiedValues=0,references=[],resources=[],unclassifiedSamples=[])])

    def test_complete_pagination_and_revision_identity(self):
        first=self.page();check_page(first,94,0)
        last=copy.deepcopy(first);last.update(offset=1,nextOffset=None);last['objects'][0]['id']='Marauder'
        check_page(last,94,1,first)
        for key,value in [('catalog','Model'),('totalEntries',3),('dataSources',['OtherMap'])]:
            changed=copy.deepcopy(last);changed[key]=value
            with self.assertRaises(RuntimeError):check_page(changed,94,1,first)

    def test_skips_repeats_empty_and_incomplete_pages_are_rejected(self):
        for changes in [dict(nextOffset=0),dict(nextOffset=2),dict(nextOffset=None),dict(objects=[]),
                        dict(traversalComplete=False),dict(catalogIndex=54),dict(variant=1),dict(dataSources=[])]:
            with self.subTest(changes=changes):
                page=self.page();page.update(changes)
                with self.assertRaises(RuntimeError):check_page(page,94,0)

    def test_missing_coverage_is_not_zero_errors(self):
        for key in ('fieldsVisited','leafValuesVisited','getterErrors','unclassifiedValues'):
            page=self.page();del page['objects'][0][key]
            with self.assertRaises(RuntimeError):check_page(page,94,0)

    def test_canonical_paths_share_case_insensitive_virtual_identity(self):
        self.assertEqual(resource_key('Assets/Units/Marine.M3'),('assets\\units\\marine.m3',None))

    def test_tokens_and_nonfile_names_are_coverage_gaps(self):
        for path in ['Assets/##id##.m3','StandardFont','Assets/../bad.m3','C:/bad.m3','/bad.m3','Assets//bad.m3','bad\n.m3']:
            with self.subTest(path=path):
                key,reason=resource_key(path);self.assertIsNone(key);self.assertTrue(reason)

    def test_invalid_or_ambiguous_requests_fail_before_editor_start(self):
        for request in [{'map':''},{'map':True},{'limit':True},{'limit':501},{'output':'ignored.json'},
                        {'map':'A.SC2Map','template':'B.SC2Map'}]:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):audit_options(request)


class AuditWorkerFixture:
    def __init__(self,root,omit_resource=False):
        self.work=root;self.operation_progress={};self.omit_resource=omit_resource;self.calls=[]
        doc=root/'Map.SC2Map';doc.write_bytes(b'unchanged source')
        self.state={'documentPath':str(doc),'editorInfo':{'originalBinaryVerified':True}}
        self.artifacts=ArtifactStore(root/'artifacts')
    def alive(self):return True
    def _check_abort(self):pass
    def _background_result(self,result):result['desktopObservation']={'inputInjectionUsed':False}
    def _native(self,folder,op,**args):
        self.calls.append((op,args));out=folder/('01-'+op);out.mkdir()
        if op=='diagnostics':return {}
        if op=='data-audit':
            index=args['audit']['catalog'];obj=[]
            if index==94:
                obj=[dict(id='MarkerUnit',nativeClass='CUnit',defaultTemplate=False,fieldsVisited=7,leafValuesVisited=6,
                          getterErrors=0,unclassifiedValues=1,unclassifiedSamples=[{'type':'Opaque'}],
                          references=[{'field':'Weapon','type':'CWeaponLink','catalog':'Weapon','target':'MissingWeapon','status':'missing'}],
                          resources=[{'field':'Good','type':'CModelPath','path':'Assets/Marine.m3'},
                                     {'field':'Bad','type':'CModelPath','path':'Assets/Missing.m3'},
                                     {'field':'Token','type':'CModelPath','path':'Assets/##id##.m3'}])]
            value=dict(schemaVersion=1,traversalComplete=True,variant=0,catalogIndex=index,catalog=f'Catalog{index}',
                       dataSources=['All Data','Core.SC2Mod','Map.SC2Map'],totalEntries=len(obj),offset=0,nextOffset=None,objects=obj)
        else:
            paths=Path(args['map_path']).read_text().splitlines()
            value={'complete':True,'source':'original merged Archive Browser',
                   'resources':[{'path':p,'status':'missing' if 'Missing' in p else 'present'} for p in paths]}
            if self.omit_resource:value['resources'].pop()
        (out/'Native.data.json').write_text(json.dumps(value),encoding='utf8')
        return {}


class DataAuditAggregationTests(unittest.TestCase):
    def diagnostics(self):return {'newErrors':[],'newWarnings':[],'newErrorsClear':None}

    def test_full_catalog_coverage_artifacts_and_priority_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker=AuditWorkerFixture(Path(temporary))
            with patch('sc2native.data_audit.operation_diagnostics',return_value=self.diagnostics()):
                report=audit_data(worker,{'limit':1})
            self.assertTrue(report['catalogTraversalComplete']);self.assertEqual(len(report['catalogs']),109)
            self.assertFalse(report['referenceAndFileValidationComplete']);self.assertIsNone(report['validationPassed'])
            self.assertFalse(report['allObservedTypedTargetsPresent']);self.assertIsNone(report['nativeNewErrorsClear'])
            self.assertEqual(report['counts']['references_missing'],1);self.assertEqual(report['counts']['resources_missing'],1)
            self.assertEqual(report['counts']['resources_present'],1);self.assertEqual(report['counts']['uniqueResources'],2)
            self.assertEqual(report['findingSamples'][0]['kind'],'missing-resource')
            self.assertEqual(len(report['findingSamples']),1);self.assertTrue(report['findingSamplesTruncated'])
            self.assertEqual([args['audit']['catalog'] for op,args in worker.calls if op=='data-audit'],list(range(109)))
            for key in ('objectsArtifact','findingsArtifact','reportArtifact'):worker.artifacts.get(report[key]['id'])
            findings=[json.loads(line) for line in Path(report['findingsArtifact']['path']).read_text().splitlines()]
            reference=next(v for v in findings if v['kind']=='catalog-reference')
            self.assertEqual(reference['catalog'],'Catalog94');self.assertEqual(reference['targetCatalog'],'Weapon')

    def test_omitted_native_resource_cannot_publish_complete_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker=AuditWorkerFixture(Path(temporary),omit_resource=True)
            with patch('sc2native.data_audit.operation_diagnostics',return_value=self.diagnostics()):
                with self.assertRaisesRegex(RuntimeError,'omitted paths'):audit_data(worker,{})
            self.assertEqual(worker.artifacts.items,{})


if __name__=='__main__':unittest.main()
