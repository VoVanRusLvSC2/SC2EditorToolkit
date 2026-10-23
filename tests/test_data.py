import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.data import data_options,native_payload,fields_from_payload,related_objects


class Data(unittest.TestCase):
    def payload(self,**changes):
        return {'selection':{'catalog':'Unit','requestedId':'Marine','nativeRow':'Marine (Marine)','source':'Liberty.SC2Mod'},
                'controls':[{'id':2029,'xml':'<Catalog><CUnit id="Marine"><LifeMax value="73"/></CUnit></Catalog>'}],**changes}
    def read(self,value):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'native.json';path.write_text(json.dumps(value),encoding='utf8')
            return native_payload(path,'Unit','Marine',require_xml=True)
    def test_original_xml_and_raw_id_both_required(self):
        result=self.read(self.payload());self.assertTrue(result['identityVerified']);self.assertEqual(result['nativeClass'],'CUnit')
        for value in (self.payload(selection={'catalog':'Unit','requestedId':'Marine','nativeRow':'MarineACGluescreenDummy (Marine)'}),
                      self.payload(controls=[{'xml':'<Catalog><CUnit id="MarineACGluescreenDummy"/></Catalog>'}]),
                      self.payload(controls=[{'xml':'<Catalog><CModel id="Marine"/></Catalog>'}]),
                      self.payload(controls=[])):
            with self.assertRaises(RuntimeError):self.read(value)
    def test_duplicate_identity_or_unsafe_xml_is_rejected(self):
        with self.assertRaises(RuntimeError):self.read(self.payload(controls=[{'xml':'<Catalog><CUnit id="Marine"/><CUnit id="Marine"/></Catalog>'}]))
        with self.assertRaises(ValueError):self.read(self.payload(controls=[{'xml':'<!DOCTYPE Catalog><Catalog/>'}]))
    def test_field_source_columns_preserved_and_truncation_unknown(self):
        controls=[{'id':2025,'table':{'count':1,'complete':True,'rows':[['LifeMax']]}},
                  {'id':2026,'table':{'count':1,'complete':True,'columns':['Core','Liberty','Map'],'rows':[['0','45','73']]}}]
        payload={'controls':controls,'privateClipboard':True,'copyText':'Field\tCore\tLiberty\tMap\r\n(Basic) LifeMax\t0\t45\t73\r\n'}
        result=fields_from_payload(payload);self.assertTrue(result['complete'])
        self.assertEqual(result['fields'],[{'field':'LifeMax','displayField':'(Basic) LifeMax','values':['0','45','73']}])
        self.assertFalse(fields_from_payload({'controls':controls})['complete'])
        payload['copyText']='Field\tWrong object\nLifeMax\t73\n';self.assertFalse(fields_from_payload(payload)['complete'])
        controls[1]['table']['count']=2
        with self.assertRaises(RuntimeError):fields_from_payload({'controls':controls})
    def test_invalid_arguments_before_editor(self):
        self.assertEqual(data_options({'catalog':'uNiT','object_id':'Marine'}),('Unit','Marine'))
        for request in ({'catalog':'Wrong','object_id':'Marine'},{'catalog':'Unit','object_id':' Marine'},
                        {'catalog':'Unit','object_id':'Marine\n'},{'catalog':'Unit','object_id':3},
                        {'catalog':'Unit','object_id':'Marine','map':''}):
            with self.assertRaises(ValueError):data_options(request)
    def test_native_associations_keep_catalog_identity_and_pagination(self):
        tree={'nodes':[{'text':'Marine (Marine)','depth':0},{'text':'Effects','depth':1},
             {'text':'GuassRifle (Damage)','depth':2},{'text':'Weapons','depth':1},
             {'text':'GuassRifle (C-14 Gauss Rifle)','depth':2}]}
        result=related_objects([tree],{'query':'guass','limit':1})
        self.assertEqual(result['totalMatches'],2);self.assertEqual(result['nextOffset'],1)
        self.assertEqual(result['relatedObjects'][0]['catalog'],'Effect')
        self.assertEqual(related_objects([tree],{'offset':1})['relatedObjects'][0]['catalog'],'Weapon')
        with self.assertRaises(ValueError):related_objects([],{ 'limit':True })

if __name__=='__main__':unittest.main()
