"""Original Data UI observations, with exact identity and bounded completeness."""
import json
import csv
import io
import re
import uuid
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import file_prepare as files
from .diagnostics import operation_diagnostics
from .document_validation import _archive

CATALOGS=('Unit','Model','Actor','Abil','Behavior','Effect','Sound','Texture','Weapon','Validator','Upgrade','Requirement')
EXPLORER_GROUPS={'Abilities':'Abil','Actors':'Actor','Behaviors':'Behavior','Buttons':'Button','Effects':'Effect',
                 'Models':'Model','Movers':'Mover','Requirements':'Requirement','Requirement Nodes':'RequirementNode',
                 'Sounds':'Sound','Textures':'Texture','Units':'Unit','Upgrades':'Upgrade','Validators':'Validator','Weapons':'Weapon'}


def data_options(request):
    catalog=request.get('catalog');identifier=request.get('object_id')
    canonical=next((c for c in CATALOGS if isinstance(catalog,str) and c.casefold()==catalog.casefold()),None)
    if canonical is None:raise ValueError('catalog must be one of '+', '.join(CATALOGS))
    if not isinstance(identifier,str) or not identifier or identifier!=identifier.strip() or len(identifier)>255 or any(ord(c)<32 for c in identifier):
        raise ValueError('object_id must be an exact nonempty ID of at most 255 characters')
    for key in ('map','template'):
        if key in request and (not isinstance(request[key],str) or not request[key].strip()):raise ValueError(key+' must be a nonempty archive path')
    if 'include_xml' in request and type(request['include_xml']) is not bool:raise ValueError('include_xml must be a JSON boolean')
    for key,default,maximum in (('field_offset',0,100000),('field_limit',100,500)):
        value=request.get(key,default)
        if type(value) is not int or not (0 if key=='field_offset' else 1)<=value<=maximum:raise ValueError(key+' is outside its integer bounds')
    return canonical,identifier


def related_objects(trees,request):
    query=request.get('query','');offset=request.get('offset',0);limit=request.get('limit',100)
    if not isinstance(query,str) or len(query)>256:raise ValueError('query must be a string of at most 256 characters')
    if type(offset) is not int or not 0<=offset<=500000:raise ValueError('offset must be 0..500000')
    if type(limit) is not int or not 1<=limit<=500:raise ValueError('limit must be 1..500')
    records=[];seen=set()
    for tree in trees:
        group=None
        for node in tree['nodes']:
            if node['depth']==1:group=node['text']
            if node['depth']!=2 or group is None:continue
            match=re.match(r'^([A-Za-z0-9_.:@-]+)(?: \(|$)',node['text']);identifier=match.group(1) if match else None
            catalog=EXPLORER_GROUPS.get(group);key=(group,identifier,node['text'])
            if key in seen:continue
            seen.add(key)
            record={'catalog':catalog,'objectId':identifier,'nativeGroup':group,'nativeText':node['text'],
                    'idSource':'original raw-data tree label' if identifier else None}
            if query.casefold() in (' '.join(str(v) for v in record.values() if v)).casefold():records.append(record)
    return {'relatedObjects':records[offset:offset+limit],'totalMatches':len(records),'offset':offset,
            'nextOffset':offset+limit if offset+limit<len(records) else None,
            'relationshipSemantics':'native Object Explorer associations; direction and direct/transitive edge status are not inferred'}


def native_payload(path,catalog,identifier,*,require_xml=False):
    data=Path(path).read_bytes()
    if len(data)>16*1024**2:raise ValueError('Oversized original Data response')
    value=json.loads(data.decode('utf8'));selection=value.get('selection') or {}
    if selection.get('catalog')!=catalog or selection.get('requestedId')!=identifier:
        raise RuntimeError('Native Data selection does not match the requested catalog and ID')
    row=selection.get('nativeRow','')
    if row!=identifier and not row.startswith(identifier+' ('):raise RuntimeError('Native raw object ID readback mismatch')
    if require_xml:
        xml=[c['xml'] for c in value.get('controls',[]) if 'xml' in c]
        if len(xml)!=1:raise RuntimeError('Exactly one original Data XML view is required')
        encoded=xml[0].encode('utf8')
        if b'<!DOCTYPE' in encoded.upper() or b'<!ENTITY' in encoded.upper():raise ValueError('Native Data XML DTD/entity is unsupported')
        root=ET.fromstring(encoded)
        matches=[n for n in root if n.get('id')==identifier and n.tag.startswith('C'+catalog)]
        if len(matches)!=1:raise RuntimeError('Original Data XML did not confirm the exact selected catalog/ID')
        value['originalXml']=xml[0];value['nativeClass']=matches[0].tag;value['identityVerified']=True
    return value


def fields_from_payload(value):
    tables={c['id']:c['table'] for c in value.get('controls',[]) if 'table' in c}
    names=tables.get(2025,{});values=tables.get(2026,{})
    if names.get('count')!=values.get('count'):raise RuntimeError('Original field names/value tables are not aligned')
    expected=names.get('count');columns=values.get('columns',[])
    copies=[entry.get('text','') for entry in value.get('copies',[])]+[value.get('copyText','')]
    for text in copies:
        if value.get('privateClipboard') is not True or not text.startswith('Field\t'):continue
        try:rows=[row for row in csv.reader(io.StringIO(text),delimiter='\t',strict=True) if row]
        except csv.Error:continue
        if not rows or rows[0][1:]!=columns or len(rows)-1!=expected:continue
        if any(len(row)!=len(rows[0]) or not row[0] for row in rows[1:]):continue
        fields=[]
        for row in rows[1:]:
            key=re.sub(r'^\(Basic\)\s+','',row[0]);key=re.sub(r'\s+[+-]$','',key)
            fields.append({'field':key,'displayField':row[0],'values':row[1:]})
        return {'fields':fields,'valueColumns':columns,'complete':bool(expected),'totalFields':expected,
                'source':'original Editor Copy As Text; complete field/value serialization into a process-private clipboard',
                'userClipboardAccessUsed':False,'cellTextClipped':False}
    complete=False
    fields=[]
    for name,row in zip(names.get('rows',[]),values.get('rows',[])):
        if not name:raise RuntimeError('Original Data field name is unreadable')
        if any('<TRUNCATED>' in cell for cell in name+row):complete=False
        fields.append({'field':name[0],'values':row})
    return {'fields':fields,'valueColumns':columns,'complete':complete,
            'totalFields':expected,'source':'original visible table text only; may be clipped to cell width',
            'cellTextClipped':True,'reason':'Complete original Copy As Text serialization was not confirmed'}


def inspect_data(worker,request,operation='read'):
    catalog,identifier=data_options(request)
    if operation=='links':related_objects([],request) # Validate before starting Editor.
    supplied=request.get('map') or request.get('template')
    source=_archive(supplied or (worker.state or {}).get('documentPath',''));source_hash=files.sha(source)
    if supplied:
        if worker.alive():
            opened=worker.open_document({**request,'map':str(source)},_locked=True)
            if opened.get('status')=='FAILED':return opened
        else:worker.ensure(source,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'))
    if not worker.alive():raise RuntimeError('Open/start an owned document first, or supply map')
    if files.sha(worker.state['documentPath'])!=source_hash:raise RuntimeError('Opened private Data document does not match the supplied source revision')
    directory=worker.work/'data'/uuid.uuid4().hex;directory.mkdir(parents=True)
    def read(name,op,mode):
        folder=directory/name;folder.mkdir()
        native=worker._native(folder,op,camera=catalog,context=identifier,time_ms=mode)
        path=folder/('01-'+op)/'Native.data.json'
        if mode==5:
            payload=json.loads(path.read_text(encoding='utf8'))
            if payload.get('requestedCatalog')!=catalog or payload.get('requestedId')!=identifier or payload.get('prepared') is not True:
                raise RuntimeError('Original Data preparation identity mismatch')
        else:payload=native_payload(path,catalog,identifier,require_xml=mode==4)
        return native,payload,operation_diagnostics(folder/('01-'+op),native)
    # Return to the original outer GUI loop between selection and observation:
    # the Editor commits some Data/filter refreshes from its idle handler.
    read('prepare','data-read',5)
    from native_xml_oracle import NativeStepError
    for attempt in range(3):
        try:
            read('select' if attempt==0 else 'select-refresh-'+str(attempt),'data-read',0);break
        except NativeStepError as error:
            evidence=error.native_result or {}
            if attempt==2 or not evidence.get('completed') or evidence.get('error') not in (149,159):raise
            time.sleep(.25)
    read('select-ready','data-read',0)
    read('xml-view','data-read',1)
    xml_native,xml,_=read('identity','data-read',4)
    native,value,diagnostic=read('fields','data-read',0)
    prepared_table=fields_from_payload(value)
    asset_lookup=None;asset_native=None
    if operation=='resources' and catalog=='Model':
        asset_native,asset_value,asset_diagnostic=read('asset-lookup','data-resources',0)
        asset_lookup=asset_value.get('assetLookup')
        # Restore raw mode and the field selection after cancelling both native
        # dialogs so subsequent operations retain the same exact Data object.
        read('asset-restored','data-read',0)
    if operation=='links' or not fields_from_payload(value)['complete']:
        native,value,diagnostic=read('ready','data-links' if operation=='links' else 'data-read',0)
    if any(value['selection'].get(k)!=xml['selection'].get(k) for k in ('catalog','requestedId','nativeRow','source')):raise RuntimeError('Original Data identity/source changed between XML and fields')
    table=fields_from_payload(value)
    if operation=='resources' and prepared_table['complete']:table=prepared_table
    trees=[{'controlId':c['id'],'nodes':c['tree'],'complete':c.get('complete') is True} for c in value.get('controls',[]) if 'tree' in c]
    result={'status':'NATIVE_DATA_READ','catalog':catalog,'objectId':identifier,'identityVerified':True,
            'dataSpace':value.get('dataSpace'),'dataSourceScope':value.get('dataSource'),
            'nativeClass':xml['nativeClass'],'selection':value['selection'],'sourceSha256':source_hash,'mapRevision':source_hash,
            **table,'originalXml':xml['originalXml'],'native':native,'identityNative':xml_native,'diagnostics':diagnostic,
            'links':trees,'linksCoverage':'materialized original Object Explorer tree; not an exhaustive global usage index',
            'evidenceDirectory':str(directory)}
    if not table['complete']:result['status']='NATIVE_DATA_READ_INCOMPLETE'
    if operation=='links':result['status']='NATIVE_DATA_LINKS_READ' if trees and all(t['complete'] for t in trees) else 'NATIVE_DATA_LINKS_INCOMPLETE'
    if operation=='links':result.update(related_objects(trees,request))
    if operation=='resources':
        result.update(status='NATIVE_RESOURCE_CHECK_INCOMPLETE',resourceValidationPassed=None,
                      resourceScope='Main Model file presence in original merged Archive Browser and native operation diagnostics; binary integrity, nested assets and runtime behavior are not validated',
                      assetLookup=asset_lookup,previewRequested=False)
        if asset_lookup is not None:
            result['assetDiagnostics']=asset_diagnostic;result['assetNative']=asset_native
            if asset_lookup.get('confirmed') is True:
                if asset_lookup.get('exists') is False:
                    result.update(status='FAILED',resourceValidationPassed=False,
                                  resourceErrors=[{'type':'MAIN_MODEL_FILE_MISSING','path':asset_lookup.get('requestedPath'),
                                                   'source':'original Archive Browser merged virtual file tree'}])
                elif asset_lookup.get('exists') is True and asset_diagnostic['newErrorsClear'] is True and diagnostic['newErrorsClear'] is True:
                    result.update(status='NATIVE_MAIN_MODEL_FILE_CHECK_PASSED',resourceValidationPassed=True)
            if asset_diagnostic['newErrors']:result.update(status='FAILED',resourceValidationPassed=False)
        if diagnostic['newErrors']:result.update(status='FAILED',resourceValidationPassed=False)
    result['sourceUnchanged']=files.sha(source)==source_hash
    if not result['sourceUnchanged']:result.update(status='FAILED',error='Supplied source archive changed')
    worker._background_result(result)
    result['dataArtifact']=worker.artifacts.export(json.dumps(result,ensure_ascii=False,indent=2).encode('utf8'),suffix='.json',mime='application/json')
    offset=request.get('field_offset',0);limit=request.get('field_limit',100)
    result['fields']=result['fields'][offset:offset+limit];result['fieldOffset']=offset
    result['nextFieldOffset']=offset+limit if offset+limit<result['totalFields'] else None
    if not request.get('include_xml',False):result.pop('originalXml',None)
    return result
