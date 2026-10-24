"""One immutable, revision-bound report of observed original Editor checks."""
import json
import time
import uuid
import xml.etree.ElementTree as ET
from xml.parsers import expat
from pathlib import Path
import file_prepare as files
from .document_validation import _archive
from .components import list_members,read_member


def read_declared_dependencies(source,work):
    try:
        tool=files.mpq_tool();members=[m for m in list_members(source,tool) if m['name'].casefold()=='documentinfo']
        if len(members)!=1 or members[0]['bytes']>2*1024**2:raise ValueError('Unique bounded DocumentInfo required')
        _,text=read_member(source,members[0],tool,work,text=True)
        if text is None or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('Unsupported DocumentInfo XML')
        # Original archives may store only an XML declaration (no root). Expat
        # distinguishes that empty document from an unclosed root, which can
        # produce the same NO_ELEMENTS error. Never treat malformed XML as empty.
        parser=expat.ParserCreate();elements=[]
        parser.StartElementHandler=lambda *args:elements.append(True)
        try:parser.Parse(text,True)
        except expat.ExpatError as error:
            if not elements and error.code==expat.errors.codes[expat.errors.XML_ERROR_NO_ELEMENTS]:
                return {'complete':True,'values':[],'source':'empty saved DocumentInfo; no explicit dependency declarations; native sources are checked separately'}
            raise
        root=ET.fromstring(text)
        return {'complete':True,'values':[n.text or '' for n in root.findall('./Dependencies/Value')],
                'source':'saved DocumentInfo declarations; original Editor performs actual dependency resolution'}
    except Exception as error:return {'complete':False,'values':None,'error':str(error),'source':'saved DocumentInfo declarations'}


def check_document(worker,request):
    for key in ('save_reopen','include_diffs'):
        if key in request and type(request[key]) is not bool:raise ValueError(key+' must be a JSON boolean')
    if 'output' in request:raise ValueError('Report artifacts use immutable managed paths; download the returned artifact')
    source=_archive(request.get('map') or request.get('template') or (worker.state or {}).get('documentPath',''))
    source_hash=files.sha(source);identifier=uuid.uuid4().hex;started=time.time()
    report={'schemaVersion':1,'reportId':identifier,'startedAt':started,'source':str(source),
            'sourceSha256':source_hash,'mapRevision':source_hash,'checks':{},'errors':[],
            'scope':'Original Editor loading, Data diagnostics, native Galaxy generation/type compilation and optional private save/reopen; not gameplay validation'}
    report['declaredDependencies']=read_declared_dependencies(source,worker.work)
    options={k:v for k,v in request.items() if k not in ('save_reopen','output')};options['map']=str(source)
    try:
        worker._check_abort()
        worker.operation_progress={'phase':'report-load-and-data'}
        result=worker.save_reopen_document(options) if request.get('save_reopen',False) else worker.validate_document(options)
        report['checks']['document']=result
        if result.get('sourceSha256') and result['sourceSha256']!=source_hash:raise RuntimeError('Native document check used another source revision')
        report['editorInfo']=(worker.state or {}).get('editorInfo')
        native_passed=result.get('nativeValidationPassed')
        report['nativeValidationPassed']=native_passed
        if result.get('nativeLoadVerified') and worker.alive():
            worker._check_abort();worker.operation_progress={'phase':'report-native-generation-and-compile'}
            compiled=worker.compile_current({k:v for k,v in request.items() if k in ('scope','context_label','locale')})
            report['checks']['triggers']={k:v for k,v in compiled.items() if k!='galaxy'}
            report['nativeGenerationVerified']=compiled.get('nativeGenerationVerified') is True
            report['nativeCompilePassed']=compiled.get('nativeCompilePassed') is True
            if compiled.get('nativeGenerationVerified'):
                report['checks']['galaxyExport']=worker.export_galaxy({})
        else:report.update(nativeGenerationVerified=False,nativeCompilePassed=False)
        if result.get('status')=='FAILED' or report['checks'].get('triggers',{}).get('status')=='FAILED':
            report['status']='FAILED'
        elif native_passed is True and report['nativeCompilePassed'] and report['declaredDependencies']['complete']:report['status']='NATIVE_MAP_CHECK_PASSED'
        else:report['status']='NATIVE_MAP_CHECK_INCOMPLETE'
    except Exception as error:report.update(status='FAILED');report['errors'].append(str(error))
    report['finishedAt']=time.time();report['seconds']=round(report['finishedAt']-started,3)
    try:report['sourceUnchanged']=files.sha(source)==source_hash
    except OSError:report['sourceUnchanged']=False
    if not report['sourceUnchanged']:report.update(status='FAILED');report['errors'].append('Supplied source archive changed')
    if worker.monitor:worker._background_result(report)
    # Exact full report is downloadable; summaries do not replace the evidence.
    artifact=worker.artifacts.export(json.dumps(report,ensure_ascii=False,indent=2).encode('utf8'),suffix='.json',mime='application/json')
    return {**report,'reportArtifact':artifact}
