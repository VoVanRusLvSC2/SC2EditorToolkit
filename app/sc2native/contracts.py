"""Version 1 transport contracts shared by HTTP and MCP."""
import math

START='editor_path render_backend template map'
CONTEXT='scope context_label locale'
CAPTURE='output overwrite allow_empty'
FIELDS={
 'start':('template editor_path render_backend startup_module','template'),
 'open_document':('map editor_path render_backend','map'),
 'execute':(START+' '+CONTEXT+' startup_module triggers_xml triggers_file trigger_strings game_strings marker expect_text compile','template'),
 'compile_current':(CONTEXT,''),'export_galaxy':('output overwrite',''),'diagnostics':('',''),
 'validate_document':(START+' baseline_template',''),
 'save_reopen_document':(START+' baseline_template include_diffs output overwrite',''),
 'check_document':(START+' '+CONTEXT+' baseline_template save_reopen include_diffs',''),
 'audit_data':(START+' limit',''),
 'read_data':(START+' catalog object_id field_offset field_limit include_xml','catalog object_id'),
 'data_links':(START+' catalog object_id','catalog object_id'),
 'check_resources':(START+' catalog object_id','catalog object_id'),
 'cutscene_open':(START+' scene',''), 'cutscene_seek':('camera time_ms',''),
 'capture_frame':('camera time_ms '+CAPTURE,''),
 'capture_terrain':(START+' map_camera_id terrain_camera '+CAPTURE,''),
 'export_map_image':(START+' size include_units include_doodads output overwrite',''),
 'capture_map_region':(START+' bounds size include_units include_doodads output overwrite','bounds'),
 'list_map_cameras':('map locale',''),'search_objects':('map locale query kinds owner bounds offset limit',''),
 'export_video':(START+' scene camera start_ms end_ms fps keep_frames include_audio output overwrite',''),
 'query_audit':('report_id section catalog object_id field kind finding_status offset limit','report_id'),
 'find_object_uses':('report_id target_catalog target_id catalog object_id offset limit','report_id target_catalog target_id'),
 'compare_audits':('before_report_id after_report_id section catalog object_id field offset limit','before_report_id after_report_id'),
 'doctor':('editor_path render_backend',''),
 'jobs.submit':('operation arguments timeout_seconds','operation'),
 'jobs.status':('job_id','job_id'),'jobs.wait':('job_id wait_ms','job_id'),'jobs.cancel':('job_id','job_id'),
 'modules':('',''),
}


def schema(target,properties):
    allowed,required=FIELDS[target or 'modules']
    props={key:properties[key] for key in allowed.split()}
    if target in ('query_audit','find_object_uses','compare_audits'):props['offset']={'type':'integer','minimum':0,'maximum':10000000}
    return {'type':'object','properties':props,'required':required.split(),'additionalProperties':False}


def validate(value,definition,path='arguments'):
    kind=definition.get('type')
    valid={'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),
           'boolean':lambda:type(value) is bool,'integer':lambda:type(value) is int,
           'number':lambda:type(value) in (int,float) and math.isfinite(value)}
    if kind and not valid[kind]():raise ValueError(path+' must be a JSON '+kind)
    if kind=='object':
        props=definition.get('properties',{})
        if definition.get('additionalProperties') is False and set(value)-props.keys():raise ValueError(path+' has unsupported arguments: '+', '.join(sorted(set(value)-props.keys())))
        for key in definition.get('required',[]):
            if key not in value:raise ValueError(path+'.'+key+' is required')
        for key,item in value.items():
            if key in props:validate(item,props[key],path+'.'+key)
    if kind=='array':
        if len(value)<definition.get('minItems',0) or len(value)>definition.get('maxItems',100000):raise ValueError(path+' array size is outside supported bounds')
        for item in value:validate(item,definition['items'],path+'[]')
    if kind=='string':
        if len(value)<definition.get('minLength',0) or len(value)>definition.get('maxLength',67108864):raise ValueError(path+' must be a bounded nonempty string')
    if kind in ('number','integer'):
        if value<definition.get('minimum',-math.inf) or value>definition.get('maximum',math.inf):raise ValueError(path+' is outside supported bounds')
    if 'enum' in definition and value not in definition['enum']:raise ValueError(path+' is not a supported value')


def validate_call(target,arguments,properties):
    validate(arguments,schema(target,properties))
    if target=='jobs.submit':validate_call(arguments['operation'],arguments.get('arguments',{}),properties)
    if target=='execute' and 'triggers_xml' in arguments and 'triggers_file' in arguments:raise ValueError('Supply triggers_xml or triggers_file, not both')


def error_info(error):
    if getattr(error,'error_info',None):
        result=dict(error.error_info)
        if getattr(error,'job_id',None):result['jobId']=error.job_id
        return result
    text=str(error);lower=text.lower()
    if isinstance(error,(ValueError,TypeError)):code='INVALID_ARGUMENT';step='Correct the request using the tool input schema.'
    elif isinstance(error,KeyError):code='NOT_FOUND';step='Use an ID returned by this server and work directory.'
    elif isinstance(error,FileExistsError):code='OUTPUT_EXISTS';step='Choose another output path or explicitly set overwrite=true.'
    elif isinstance(error,FileNotFoundError):code='FILE_NOT_FOUND';step='Check the configured installation and input paths.'
    elif 'busy' in lower or 'queue is full' in lower:code='WORKER_BUSY';step='Wait for the current job or cancel it explicitly.'
    elif '0x88760868' in lower:code='GRAPHICS_UNAVAILABLE';step='Check the doctor report and graphics backend; retry after the graphics resource conflict is resolved.'
    elif getattr(error,'winerror',None)==112 or getattr(error,'errno',None)==28:code='STORAGE_FULL';step='Free space in the selected work/output volume.'
    else:code='OPERATION_FAILED';step='Inspect native diagnostics and job evidence before retrying.'
    result={'code':code,'message':text,'nextStep':step,'automaticRetry':False}
    if getattr(error,'evidence_directory',None):
        native=getattr(error,'native_result',None) or {}
        result['evidence']={'directory':str(error.evidence_directory),'native':{key:native[key] for key in ('status','operation','error','failure','exceptionCode') if key in native}}
    return result


def decorate(data):
    value=dict(data);status=value.get('status','')
    if status in ('FAILED','TIMED_OUT','INTERRUPTED'):outcome='failed'
    elif status=='CANCELLED':outcome='cancelled'
    elif status in ('QUEUED','RUNNING'):outcome='pending'
    elif value.get('validationPassed',True) is None or 'INCOMPLETE' in status or 'COVERAGE_GAPS' in status:outcome='incomplete'
    elif value.get('validationPassed') is False or (value.get('nativeCompilePassed') is False and (value.get('compilerErrors',0) or value.get('steps',{}).get('compile'))):outcome='failed'
    else:outcome='completed'
    value['outcome']=outcome
    if status=='FAILED' and 'errorInfo' not in value:value['errorInfo']=error_info(RuntimeError(value.get('error','Operation failed; inspect diagnostics')))
    return value


OUTPUT_SCHEMA={'type':'object','required':['outcome'],'properties':{
    'outcome':{'type':'string','enum':['completed','failed','incomplete','pending','cancelled']},
    'errorInfo':{'type':'object','required':['code','message','nextStep','automaticRetry'],'properties':{
        'code':{'type':'string'},'message':{'type':'string'},'nextStep':{'type':'string'},'automaticRetry':{'type':'boolean'},'evidence':{'type':'object'},'jobId':{'type':'string'}},'additionalProperties':False}},'additionalProperties':True}
