import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from sc2native.artifacts import ArtifactStore
from sc2native.audit_store import build_index,query_audit,compare_audits,bounded_rows


class Queries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.worker=SimpleNamespace(artifacts=ArtifactStore(self.root/'exports'),_check_abort=lambda:None)
    def tearDown(self):self.temp.cleanup()
    def report(self,name,objects,findings,revision='a'):
        folder=self.root/name;folder.mkdir();a=folder/'objects.jsonl';b=folder/'findings.jsonl'
        a.write_text(''.join(json.dumps(o)+'\n' for o in objects),encoding='utf8');b.write_text(''.join(json.dumps(o)+'\n' for o in findings),encoding='utf8')
        index=build_index(folder,a,b)
        artifact=self.worker.artifacts.publish_file(index,suffix='.sqlite3',mime='application/vnd.sqlite3')
        report={'catalogTraversalComplete':True,'mapRevision':revision,'projectRevision':revision,'editorInfo':{'sha256':'editor'},'indexArtifact':artifact,
                'fieldValuesRecorded':all('fieldValues' in o for o in objects),'fieldValueCoverage':{'complete':True}}
        return self.worker.artifacts.export(json.dumps(report).encode(),suffix='.json',mime='application/json')['id']
    def unit(self,id='Marine',target='Gauss'):
        return {'id':id,'catalog':'Unit','references':[{'catalog':'Weapon','target':target,'field':'WeaponArray[0].Link','status':'present'}],'resources':[]}
    def test_uses_exact_target_case_and_catalog_normalization(self):
        ident=self.report('a',[self.unit(),self.unit('Other','gauss')],[])
        page=query_audit(self.worker,{'report_id':ident,'target_catalog':'weapon','target_id':'Gauss'},uses=True)
        self.assertEqual(page['totalMatches'],1);self.assertEqual(page['items'][0]['objectId'],'Marine')
        self.assertEqual(page['items'][0]['field'],'WeaponArray[0].Link');self.assertFalse(page['editorRequired'])
    def test_findings_pagination_filters_and_empty_page(self):
        findings=[{'kind':'catalog-reference','status':'missing','catalog':'Unit','objectId':str(i)} for i in range(3)]
        ident=self.report('a',[self.unit()],findings)
        page=query_audit(self.worker,{'report_id':ident,'catalog':'unit','finding_status':'missing','limit':2})
        self.assertEqual(page['totalMatches'],3);self.assertEqual(page['nextOffset'],2)
        self.assertEqual(query_audit(self.worker,{'report_id':ident,'offset':5})['items'],[])
        with self.assertRaises(ValueError):query_audit(self.worker,{'report_id':ident,'section':'objects','kind':'missing-resource'})
    def test_object_diff_and_finding_multiset_change(self):
        f={'kind':'coverage-gap','catalog':'Unit','objectId':'Marine'}
        a=self.report('a',[self.unit(),self.unit('Removed')],[f,f])
        b=self.report('b',[self.unit(target='Changed'),self.unit('Added')],[f],revision='b')
        result=compare_audits(self.worker,{'before_report_id':a,'after_report_id':b,'section':'objects','limit':1})
        self.assertEqual(result['counts'],{'added':1,'removed':1,'modified':1});self.assertEqual(result['nextOffset'],1)
        self.assertFalse(result['sameProjectRevision']);self.assertTrue(result['sameEditorAdapter'])
        diff=compare_audits(self.worker,{'before_report_id':a,'after_report_id':b})
        self.assertEqual(diff['counts']['removed'],1);self.assertEqual(diff['totalChanges'],1)
        same=compare_audits(self.worker,{'before_report_id':a,'after_report_id':a})
        self.assertEqual(same['totalChanges'],0)
    def test_no_cross_store_paths_or_tampered_index(self):
        ident=self.report('a',[self.unit()],[])
        with self.assertRaises(KeyError):query_audit(self.worker,{'report_id':'../a'})
        stored=self.worker.artifacts.get(ident);report=json.loads(Path(stored['path']).read_text())
        Path(report['indexArtifact']['path']).write_bytes(b'tampered')
        with self.assertRaisesRegex(RuntimeError,'changed'):query_audit(self.worker,{'report_id':ident})
    def test_restart_keeps_queryable_artifact_identity(self):
        ident=self.report('a',[self.unit()],[])
        self.worker.artifacts=ArtifactStore(self.root/'exports')
        self.assertEqual(query_audit(self.worker,{'report_id':ident,'section':'objects'})['totalMatches'],1)
    def test_large_payload_omission_retains_comparison_identity(self):
        row={'change':'added','after':{'id':'Large','catalog':'Unit','references':['x'*10000]},'before':None}
        compact=bounded_rows([row],('change',),budget=100)[0]
        self.assertTrue(compact['payloadOmitted']);self.assertEqual(compact['after'],{'id':'Large','catalog':'Unit'})

    def test_scalar_and_nested_array_values_are_compared_by_exact_path(self):
        def unit(life,flag):
            return {**self.unit(),'fieldValues':[
                {'field':'LifeMax','type':'CFixed','status':'serialized','value':str(life)},
                {'field':'AbilArray[0].Flags[3]','type':'bool','status':'serialized','value':str(flag)}]}
        a=self.report('a',[unit(45,False)],[]);b=self.report('b',[unit(73,True)],[],revision='b')
        result=compare_audits(self.worker,{'before_report_id':a,'after_report_id':b,'section':'fields','limit':1})
        self.assertEqual(result['counts'],{'added':0,'removed':0,'modified':2});self.assertEqual(result['nextOffset'],1)
        life=compare_audits(self.worker,{'before_report_id':a,'after_report_id':b,'section':'fields','field':'LifeMax'})
        self.assertEqual(life['changes'][0]['before']['value'],'45');self.assertEqual(life['changes'][0]['after']['value'],'73')
        page=query_audit(self.worker,{'report_id':b,'section':'fields','catalog':'unit','object_id':'Marine','field':'LifeMax'})
        self.assertEqual(page['totalMatches'],1);self.assertEqual(page['items'][0]['value'],'73')
        self.assertEqual(compare_audits(self.worker,{'before_report_id':a,'after_report_id':a,'section':'fields'})['totalChanges'],0)

    def test_legacy_audit_cannot_claim_no_scalar_changes(self):
        old=self.report('old',[self.unit()],[])
        with self.assertRaisesRegex(ValueError,'old reports'):
            compare_audits(self.worker,{'before_report_id':old,'after_report_id':old,'section':'fields'})
        with self.assertRaisesRegex(ValueError,'schema 2'):
            query_audit(self.worker,{'report_id':old,'section':'fields'})
        with self.assertRaises(ValueError):query_audit(self.worker,{'report_id':old,'field':'LifeMax'})

    def test_duplicate_field_identity_fails_instead_of_overwriting(self):
        o={**self.unit(),'fieldValues':[{'field':'LifeMax','status':'serialized','value':'45'}]*2}
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):self.report('duplicates',[o],[])
    def test_different_field_encodings_are_not_reported_as_value_changes(self):
        o={**self.unit(),'fieldValues':[{'field':'LifeMax','status':'serialized','type':'CFixed','value':'45'}]}
        a=self.report('a',[o],[]);item=self.worker.artifacts.get(a)
        report=json.loads(Path(item['path']).read_text());report['fieldValueEncodingVersion']=2
        b=self.worker.artifacts.export(json.dumps(report).encode(),suffix='.json',mime='application/json')['id']
        with self.assertRaisesRegex(ValueError,'encoding versions differ'):
            compare_audits(self.worker,{'before_report_id':a,'after_report_id':b,'section':'fields'})

if __name__=='__main__':unittest.main()
