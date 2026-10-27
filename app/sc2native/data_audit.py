"""Revision-bound traversal of the original Editor's merged effective Data model.

The native adapter supplies typed values and resolves catalog identities. Python
only verifies pagination/coverage, aggregates findings and publishes artifacts.
"""
import json
import uuid
import shutil
import errno
import time
from collections import Counter
from pathlib import Path
import file_prepare as files
from .document_validation import _archive
from .diagnostics import operation_diagnostics
from .audit_store import build_index
from .revisions import snapshot as dependency_snapshot, bind_sources

AUDIT_MINIMUM_FREE=12*1024**3
AUDIT_STORAGE_RESERVE=512*1024**2


def check_storage(directory,required=AUDIT_MINIMUM_FREE):
    if shutil.disk_usage(directory).free<required:
        raise OSError(errno.ENOSPC,'Insufficient space for a complete Data value audit; use a --work volume with at least 12 GiB free. Native records, the field index and immutable artifact copies are retained.')


def check_page(value, catalog_index, offset, previous=None):
    if not isinstance(value, dict) or value.get('schemaVersion') not in (1,2) or value.get('traversalComplete') is not True:
        raise RuntimeError('Original Data page is incomplete or unsupported')
    if value.get('catalogIndex') != catalog_index or value.get('offset') != offset or value.get('variant') != 0:
        raise RuntimeError('Original Data page identity mismatch')
    total=value.get('totalEntries');objects=value.get('objects');following=value.get('nextOffset')
    if type(total) is not int or total < 0 or not isinstance(objects,list) or len(objects)>256:
        raise RuntimeError('Invalid original Data page bounds')
    end=offset+len(objects)
    if end>total or following != (end if end<total else None) or (not objects and offset<total):
        raise RuntimeError('Original Data pagination skipped or repeated entries')
    if not isinstance(value.get('catalog'),str) or not value['catalog'] or not isinstance(value.get('dataSources'),list) or not value['dataSources']:
        raise RuntimeError('Original catalog/source identity unavailable')
    if previous and any(value.get(k)!=previous.get(k) for k in ('catalog','totalEntries','dataSources','schemaVersion','fieldValueEncodingVersion')):
        raise RuntimeError('Original Data catalog changed during traversal')
    for obj in objects:
        if not isinstance(obj,dict) or not isinstance(obj.get('id'),str) or not obj['id'] or not isinstance(obj.get('nativeClass'),str):
            raise RuntimeError('Original Data object identity unavailable')
        for key in ('fieldsVisited','leafValuesVisited','getterErrors','unclassifiedValues'):
            if type(obj.get(key)) is not int or obj[key]<0:raise RuntimeError('Invalid original Data coverage counters')
        if not all(isinstance(obj.get(k),list) for k in ('references','resources','unclassifiedSamples')):
            raise RuntimeError('Invalid original typed Data observations')
        if value['schemaVersion']==2:
            if value.get('fieldValueEncodingVersion',1) not in (1,2):raise RuntimeError('Unsupported native field-value encoding')
            values=obj.get('fieldValues');errors=obj.get('valueSerializationErrors')
            if not isinstance(values,list) or type(errors) is not int or errors<0:raise RuntimeError('Missing native effective field values')
            seen=set();failed=0
            for field in values:
                if not isinstance(field,dict) or not isinstance(field.get('field'),str) or not field['field'] or field['field'] in seen:
                    raise RuntimeError('Missing or duplicate native field-value path')
                seen.add(field['field'])
                if not isinstance(field.get('type'),str) or field.get('status') not in ('serialized','error','unsupported','unavailable'):
                    raise RuntimeError('Invalid native field-value type/status')
                if field['status']=='serialized' and not isinstance(field.get('value'),str):raise RuntimeError('Missing serialized native value')
                if 'valueBits' in field:
                    bits=field['valueBits']
                    if not isinstance(bits,str) or not bits or len(bits)>32 or len(bits)%2 or any(c not in '0123456789abcdef' for c in bits):
                        raise RuntimeError('Invalid exact native value bits')
                failed+=field['status']!='serialized'
            if failed!=errors or len(values)<obj['leafValuesVisited']:raise RuntimeError('Native field-value coverage mismatch')
    return value


def resource_key(path):
    if not isinstance(path,str) or not path or len(path)>32767 or any(ord(c)<32 for c in path):
        return None,'Unsupported native resource path'
    path=path.replace('/','\\')
    if '##' in path:return None,'Unresolved original Data token'
    if path.startswith('\\') or ':' in path or any(p in ('','.','..') for p in path.split('\\')):
        return None,'Noncanonical virtual resource path'
    # Font styles and description names use the same native path wrapper, but
    # are not files in the merged Archive Browser.
    if '.' not in path.rsplit('\\',1)[-1]:return None,'Native path has no file identity'
    return path.casefold(),None


def audit_options(request):
    unknown=set(request)-{'map','template','editor_path','render_backend','limit'}
    if unknown:raise ValueError('Unsupported Data audit arguments: '+', '.join(sorted(unknown)))
    for key in ('map','template'):
        if key in request and (not isinstance(request[key],str) or not request[key].strip()):
            raise ValueError(key+' must be a nonempty archive path')
    if 'map' in request and 'template' in request and request['map']!=request['template']:
        raise ValueError('Supply one Data audit source with map or template')
    limit=request.get('limit',100)
    if type(limit) is not int or not 1<=limit<=500:raise ValueError('limit must be 1..500')
    return limit


def resource_batches(resources):
    """Bound each original browser request independently of project size/load."""
    batch=[];size=0
    for item in sorted(resources.values(),key=lambda value:value['path'].casefold()):
        following=len(item['path'].encode('utf8'))+1
        if batch and (len(batch)>=512 or size+following>1024**2):
            yield batch;batch=[];size=0
        batch.append(item);size+=following
    if batch:yield batch


def audit_data(worker,request):
    limit=audit_options(request);load_diagnostics=None;fresh_session=not worker.alive()
    check_storage(worker.work)
    last_storage_check=0
    def guard():
        nonlocal last_storage_check
        worker._check_abort();now=time.monotonic()
        if now-last_storage_check>=1:
            check_storage(worker.work,AUDIT_STORAGE_RESERVE);last_storage_check=now
    supplied=request.get('map') or request.get('template')
    source=_archive(supplied or (worker.state or {}).get('documentPath',''));source_hash=files.sha(source)
    editor=(worker.state or {}).get('editorInfo',{}).get('path')
    if editor is None and hasattr(worker,'editor_preference'):
        from editor_installation import resolve_editor
        editor=str(resolve_editor(request.get('editor_path') or worker.editor_preference))
    revision_before=dependency_snapshot(source,editor,worker.work,worker._check_abort)
    if supplied:
        if worker.alive():
            opened=worker.open_document({**request,'map':str(source)},_locked=True)
            if opened.get('status')=='FAILED':return opened
            load_diagnostics=opened.get('loadDiagnostics')
        else:worker.ensure(source,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'))
    if not worker.alive():raise RuntimeError('Open an owned document first or supply map')
    document=Path(worker.state['documentPath']);document_hash=files.sha(document)
    if document_hash!=source_hash:raise RuntimeError('Private Data document revision does not match source')
    directory=worker.work/'data-audits'/uuid.uuid4().hex;directory.mkdir(parents=True)
    counts=Counter({key:0 for key in ('objects','fieldsVisited','leafValuesVisited','getterErrors','unclassifiedValues','valueSerializationErrors','recordedFieldValues','serializedFieldValues','references','references_present','references_missing','references_unknown','resourceOccurrences','resourceOccurrencesUnclassified','resources_present','resources_missing','uniqueResources','findings','diagnosticPhasesNotConfirmedClear','nativeDiagnosticErrors')});catalogs=[];sources=None;resources={};sample_groups={};catalog_names=set();native_calls=0;field_recording=True
    phase_diagnostics=[];value_encoding=None
    if load_diagnostics is not None:phase_diagnostics.append({'phase':'document-load',**load_diagnostics})
    records_path=directory/'objects.jsonl';findings_path=directory/'findings.jsonl'
    def finding(stream,value):
        stream.write(json.dumps(value,ensure_ascii=False)+'\n');counts['findings']+=1
        group=value['kind']
        if group=='catalog-reference':group+='-'+value['status']
        sample=sample_groups.setdefault(group,[])
        if len(sample)<limit:sample.append(value)
    with records_path.open('x',encoding='utf8',newline='\n') as records,findings_path.open('x',encoding='utf8',newline='\n') as findings:
        for catalog_index in range(109):
            offset=0;previous=None;seen=set();entry_count=0
            while True:
                guard();folder=directory/f'catalog-{catalog_index:03d}-{offset:07d}';folder.mkdir()
                native=worker._native(folder,'data-audit',audit={'catalog':catalog_index,'offset':offset,'limit':256},_progress={'catalog':previous['catalog'] if previous else None,'catalogIndex':catalog_index,'catalogsTotal':109,'objectsVisited':counts['objects'],'fieldsVisited':counts['fieldsVisited']});native_calls+=1
                path=folder/'01-data-audit'/'Native.data.json'
                diagnostic=operation_diagnostics(path.parent,native,fresh_session=fresh_session and native_calls==1)
                if not phase_diagnostics or diagnostic['newErrors'] or diagnostic['newWarnings']:
                    phase_diagnostics.append({'phase':f'catalog-{catalog_index}-{offset}',**diagnostic})
                if diagnostic['newErrorsClear'] is not True:counts['diagnosticPhasesNotConfirmedClear']+=1
                if path.stat().st_size>16*1024**2:raise RuntimeError('Oversized original Data page')
                value=check_page(json.loads(path.read_text(encoding='utf8')),catalog_index,offset,previous)
                field_recording=field_recording and value['schemaVersion']==2
                if value['schemaVersion']==2:
                    current=value.get('fieldValueEncodingVersion',1)
                    if value_encoding is not None and value_encoding!=current:raise RuntimeError('Native field-value encoding changed during audit')
                    value_encoding=current
                if sources is None:sources=value['dataSources']
                if sources!=value['dataSources']:raise RuntimeError('Loaded original Data sources changed during audit')
                if previous is None:
                    if value['catalog'] in catalog_names:raise RuntimeError('Original Data catalogs were repeated')
                    catalog_names.add(value['catalog'])
                for obj in value['objects']:
                    if obj['id'] in seen:raise RuntimeError('Original Data object repeated across pages')
                    seen.add(obj['id']);entry_count+=1;counts['objects']+=1
                    identity={'catalog':value['catalog'],'objectId':obj['id'],'nativeClass':obj['nativeClass'],'defaultTemplate':obj['defaultTemplate']}
                    records.write(json.dumps({**identity,**obj},ensure_ascii=False)+'\n')
                    for key in ('fieldsVisited','leafValuesVisited','getterErrors','unclassifiedValues'):counts[key]+=obj[key]
                    counts['valueSerializationErrors']+=obj.get('valueSerializationErrors',0)
                    counts['recordedFieldValues']+=len(obj.get('fieldValues',[]))
                    counts['serializedFieldValues']+=sum(f['status']=='serialized' for f in obj.get('fieldValues',[]))
                    for field in obj.get('fieldValues',[]):
                        if field['status']!='serialized':finding(findings,{'kind':'field-value-gap',**identity,**field})
                    for ref in obj['references']:
                        status=ref.get('status')
                        if status not in ('present','missing','unknown'):raise RuntimeError('Unknown original reference resolution state')
                        counts['references']+=1;counts['references_'+status]+=1
                        if status!='present':finding(findings,{'kind':'catalog-reference',**ref,**identity,'targetCatalog':ref['catalog']})
                    for resource in obj['resources']:
                        counts['resourceOccurrences']+=1;key,reason=resource_key(resource.get('path'))
                        if key is None:
                            counts['resourceOccurrencesUnclassified']+=1
                            finding(findings,{'kind':'unclassified-resource',**identity,**resource,'reason':reason})
                        else:
                            item=resources.setdefault(key,{'path':resource['path'].replace('/','\\'),'occurrences':0,'samples':[]})
                            item['occurrences']+=1
                            if len(item['samples'])<5:item['samples'].append({**identity,'field':resource['field'],'type':resource['type']})
                    if obj['getterErrors'] or obj['unclassifiedValues']:
                        finding(findings,{'kind':'coverage-gap',**identity,'getterErrors':obj['getterErrors'],
                                          'unclassifiedValues':obj['unclassifiedValues'],'samples':obj['unclassifiedSamples']})
                worker.operation_progress.update(phase='data-catalog-traversal',catalog=value['catalog'],catalogIndex=catalog_index,
                                                 catalogsTotal=109,objectsVisited=counts['objects'],fieldsVisited=counts['fieldsVisited'])
                following=value['nextOffset'];previous=value
                if following is None:break
                offset=following
            if entry_count!=value['totalEntries']:raise RuntimeError('Original Data catalog was not fully traversed')
            catalogs.append({'catalog':value['catalog'],'index':catalog_index,'objects':entry_count,'complete':True})
        # Paths come from original typed getters; the original merged Archive
        # Browser performs file existence checks, including dependency/imports.
        checked=set()
        for number,batch in enumerate(resource_batches(resources)):
            guard();folder=directory/f'resources-{number:04d}';folder.mkdir()
            request_file=folder/'paths.txt';request_file.write_text(''.join(v['path']+'\n' for v in batch),encoding='utf8',newline='\n')
            expected={resource_key(v['path'])[0] for v in batch}
            progress={'resourcePathsChecked':len(checked),'uniquePaths':len(resources),'resourceBatch':number,'resourceBatchSize':len(batch)}
            native=worker._native(folder,'data-audit-files',map_path=request_file,_progress=progress);native_calls+=1
            phase_diagnostics.append({'phase':f'merged-resources-{number}',**operation_diagnostics(folder/'01-data-audit-files',native)})
            result=json.loads((folder/'01-data-audit-files'/'Native.data.json').read_text(encoding='utf8'))
            if result.get('complete') is not True or result.get('source')!='original merged Archive Browser':
                raise RuntimeError('Original virtual resource index was not confirmed complete')
            observed=set()
            for item in result.get('resources',[]):
                key,reason=resource_key(item.get('path'))
                if reason or key not in expected or key in checked or item.get('status') not in ('present','missing'):
                    raise RuntimeError('Original resource check identity/coverage mismatch')
                checked.add(key);observed.add(key);counts['resources_'+item['status']]+=1
                if item['status']=='missing':finding(findings,{'kind':'missing-resource',**resources[key],'status':'missing'})
            if observed!=expected:raise RuntimeError('Original resource check omitted paths in its batch')
        if checked!=resources.keys():raise RuntimeError('Original resource check omitted paths')
        counts['uniqueResources']=len(resources)
    worker._check_abort()
    if files.sha(source)!=source_hash or files.sha(document)!=document_hash:raise RuntimeError('Source/private document changed during Data audit')
    revision_after=dependency_snapshot(source,editor,worker.work,worker._check_abort)
    if revision_after['revision']!=revision_before['revision']:raise RuntimeError('Project dependencies changed during Data audit; discard this result and audit again')
    dependency_manifest=bind_sources(revision_after,sources,document.name)
    folder=directory/'diagnostics';folder.mkdir();native=worker._native(folder,'diagnostics');native_calls+=1
    diagnostics=operation_diagnostics(folder/'01-diagnostics',native)
    phase_diagnostics.append({'phase':'final-diagnostics',**diagnostics})
    if any(d.get('newErrors') for d in phase_diagnostics):counts['nativeDiagnosticErrors']=sum(len(d.get('newErrors',[])) for d in phase_diagnostics)
    diagnostics_clear=not counts['diagnosticPhasesNotConfirmedClear'] and all(d['newErrorsClear'] is True for d in phase_diagnostics)
    coverage=not any(counts[k] for k in ('getterErrors','unclassifiedValues','references_unknown','resourceOccurrencesUnclassified','valueSerializationErrors'))
    all_targets_present=not counts['references_missing'] and not counts['resources_missing']
    priority=('missing-resource','catalog-reference-missing','catalog-reference-unknown','unclassified-resource','field-value-gap','coverage-gap')
    samples=[entry for group in priority for entry in sample_groups.get(group,[])][:limit]
    report={'status':'NATIVE_DATA_AUDIT_COMPLETED' if coverage else 'NATIVE_DATA_AUDIT_COMPLETED_WITH_COVERAGE_GAPS',
            'schemaVersion':2 if field_recording else 1,'mapRevision':source_hash,'sourceUnchanged':True,'privateDocumentUnchanged':True,
            'fieldValuesRecorded':field_recording,
            'fieldValueEncodingVersion':value_encoding,
            'fieldValueCoverage':{'recordingAvailable':field_recording,'complete':field_recording and not counts['valueSerializationErrors'] and not counts['getterErrors'],
                                  'recordedValues':counts['recordedFieldValues'],'serializedValues':counts['serializedFieldValues'],'serializationErrors':counts['valueSerializationErrors'],
                                  'representation':'original native UTF-8 type serialization; verified numeric/color/vector storage includes valueBits (encoding 2); CFixed also retains scalarBits',
                                  'runtimePlayerStateIncluded':False},
            'projectRevision':dependency_manifest['revision'],'dependencyManifest':dependency_manifest,
            'scope':'All effective catalog entries in the opened map/mod and loaded dependencies; overridden historical definitions are not separate effective objects',
            'variant':0,'catalogTraversalComplete':True,'catalogs':catalogs,'dataSources':sources,'counts':dict(counts),
            'referenceAndFileValidationComplete':coverage,'nativeCalls':native_calls,'diagnostics':diagnostics,'diagnosticPhases':phase_diagnostics,
            'editorInfo':worker.state.get('editorInfo'),'loadedDataSourcesStable':True,'dependencyFileRevisionsVerified':False,
            'allObservedTypedTargetsPresent':all_targets_present,
            'nativeNewErrorsClear':False if counts['nativeDiagnosticErrors'] else True if diagnostics_clear else None,
            'validationPassed':False if counts['nativeDiagnosticErrors'] else True if coverage and diagnostics_clear and all_targets_present else None,
            'limitations':['Opaque native types and unresolved tokens are counted as coverage gaps.',
                           'Actor event strings, computed trigger/runtime references, nested binary dependencies and resource binary integrity require separate validation.',
                           'A missing catalog/file identity is an observed finding; runtime reachability and intentional optional references are not inferred.'],
            'evidenceDirectory':str(directory),'findingSamples':samples,'findingSamplesTruncated':counts['findings']>len(samples)}
    worker._background_result(report)
    if report['status']=='FAILED':report['validationPassed']=False
    check_storage(worker.work,records_path.stat().st_size+AUDIT_STORAGE_RESERVE)
    report['objectsArtifact']=worker.artifacts.publish_file(records_path,suffix='.jsonl',mime='application/x-ndjson')
    check_storage(worker.work,findings_path.stat().st_size+AUDIT_STORAGE_RESERVE)
    report['findingsArtifact']=worker.artifacts.publish_file(findings_path,suffix='.jsonl',mime='application/x-ndjson')
    worker.operation_progress.update(phase='audit-index',objectsTotal=counts['objects'],fieldValuesTotal=counts['recordedFieldValues'])
    index=build_index(directory,records_path,findings_path,guard)
    check_storage(worker.work,index.stat().st_size+AUDIT_STORAGE_RESERVE)
    report['indexArtifact']=worker.artifacts.publish_file(index,suffix='.sqlite3',mime='application/vnd.sqlite3')
    report['reportArtifact']=worker.artifacts.export(json.dumps(report,ensure_ascii=False,indent=2).encode('utf8'),suffix='.json',mime='application/json')
    report['reportId']=report['reportArtifact']['id']
    return report
