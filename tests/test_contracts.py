import unittest
from sc2native.mcp import PROPERTIES,TOOLS
from sc2native.contracts import schema,validate_call,decorate,error_info

class Contracts(unittest.TestCase):
    def test_every_tool_has_precise_supported_schema(self):
        for name,_,target,_ in TOOLS:
            definition=schema(target,PROPERTIES)
            self.assertFalse(definition['additionalProperties'],name)
            self.assertLess(len(definition['properties']),len(PROPERTIES),name)
        self.assertNotIn('editor_path',schema('query_audit',PROPERTIES)['properties'])
    def test_rejects_extra_missing_wrong_types_nonfinite_and_nested_bounds(self):
        for target,args in [('audit_data',{'camera':'A'}),('query_audit',{}),('export_map_image',{'include_units':'false'}),
                            ('cutscene_seek',{'time_ms':float('nan')}),('capture_map_region',{'bounds':{'left':1}}),
                            ('jobs.submit',{'operation':'audit_data','arguments':{'scene':'x'}}),('modules',{'editor_path':'x'}),
                            ('execute',{'template':'x','triggers_xml':'x','triggers_file':'x'})]:
            with self.subTest(target=target,args=args):
                with self.assertRaises(ValueError):validate_call(target,args,PROPERTIES)
    def test_outcome_separates_incomplete_from_queue_execution(self):
        self.assertEqual(decorate({'status':'SUCCEEDED'})['outcome'],'completed')
        self.assertEqual(decorate({'status':'NATIVE_DATA_AUDIT_COMPLETED_WITH_COVERAGE_GAPS','validationPassed':None})['outcome'],'incomplete')
        self.assertEqual(decorate({'status':'GENERATED','nativeCompilePassed':False,'compilerErrors':2})['outcome'],'failed')
        self.assertEqual(decorate({'status':'GENERATED','nativeCompilePassed':False,'steps':{'generate':{}}})['outcome'],'completed')
        self.assertEqual(error_info(ValueError('bad'))['code'],'INVALID_ARGUMENT')
        self.assertEqual(error_info(FileExistsError('exists'))['code'],'OUTPUT_EXISTS')
        from native_xml_oracle import NativeStepError
        self.assertEqual(error_info(NativeStepError('native failed',{'error':171},'private-evidence'))['evidence']['directory'],'private-evidence')
    def test_valid_nested_job_uses_the_same_contract(self):
        validate_call('jobs.submit',{'operation':'audit_data','arguments':{'limit':100},'timeout_seconds':60},PROPERTIES)
        validate_call('export_map_image',{'include_units':False,'size':512},PROPERTIES)

if __name__=='__main__':unittest.main()
