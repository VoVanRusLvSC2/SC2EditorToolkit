"""Immutable, indexed audit observations. Queries never start an Editor."""
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def bounded_rows(rows, keys, *, budget=512*1024):
    """Preserve row identities when one native object exceeds the inline budget."""
    used=0;result=[]
    for row in rows:
        size=len(encoded(row).encode('utf8'))
        if used+size>budget:
            original=row
            row={key:row[key] for key in keys if key in row}
            for side in ('before','after'):
                if isinstance(original.get(side),dict):row[side]={key:original[side][key] for key in ('catalog','id','objectId','kind','field','path') if key in original[side]}
            row.update(payloadOmitted=True,reason='Inline page budget exceeded; exact observations remain in the report JSONL artifacts')
            size=len(encoded(row).encode('utf8'))
        result.append(row);used+=size
    return result


def build_index(directory, objects, findings, abort=lambda: None):
    path=Path(directory)/'audit.sqlite3'
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''CREATE TABLE objects(catalog TEXT,id TEXT,payload TEXT,digest TEXT,PRIMARY KEY(catalog,id));
            CREATE TABLE refs(catalog TEXT,id TEXT,target_catalog TEXT,target TEXT,field TEXT,payload TEXT);
            CREATE TABLE findings(seq INTEGER PRIMARY KEY,kind TEXT,status TEXT,catalog TEXT,id TEXT,payload TEXT,digest TEXT);
            CREATE TABLE fields(catalog TEXT,id TEXT,field TEXT,payload TEXT,digest TEXT,PRIMARY KEY(catalog,id,field));
            CREATE INDEX incoming ON refs(target_catalog,target);
            CREATE INDEX finding_object ON findings(catalog,id,kind,status);''')
        with Path(objects).open(encoding='utf8') as stream:
            for line in stream:
                abort();obj=json.loads(line);payload=encoded(obj)
                db.execute('INSERT INTO objects VALUES(?,?,?,?)',(obj['catalog'],obj['id'],payload,hashlib.sha256(payload.encode()).hexdigest()))
                for field in obj.get('fieldValues',[]):
                    value={'catalog':obj['catalog'],'objectId':obj['id'],**field};item=encoded(value)
                    db.execute('INSERT INTO fields VALUES(?,?,?,?,?)',(obj['catalog'],obj['id'],field['field'],item,hashlib.sha256(item.encode()).hexdigest()))
                for ref in obj['references']:
                    db.execute('INSERT INTO refs VALUES(?,?,?,?,?,?)',(obj['catalog'],obj['id'],ref['catalog'],ref['target'],ref['field'],encoded(ref)))
        with Path(findings).open(encoding='utf8') as stream:
            for line in stream:
                abort();value=json.loads(line);payload=encoded(value)
                db.execute('INSERT INTO findings(kind,status,catalog,id,payload,digest) VALUES(?,?,?,?,?,?)',
                    (value['kind'],value.get('status'),value.get('catalog'),value.get('objectId'),payload,hashlib.sha256(payload.encode()).hexdigest()))
        db.execute('PRAGMA user_version=2')
    return path


def load_report(worker, identifier):
    item=worker.artifacts.get(identifier)
    if item['mime']!='application/json' or item['bytes']>8*1024**2:raise ValueError('Expected a bounded Data audit report artifact ID')
    report=json.loads(Path(item['path']).read_text(encoding='utf8'))
    if not report.get('catalogTraversalComplete') or 'indexArtifact' not in report:raise ValueError('Report has no complete version 1 audit index; create a new audit')
    index=worker.artifacts.get(report['indexArtifact']['id'])
    if index['sha256']!=report['indexArtifact']['sha256']:raise RuntimeError('Audit index identity mismatch')
    return report,Path(index['path'])


def options(request, allowed):
    unknown=set(request)-set(allowed)-{'offset','limit'}
    if unknown:raise ValueError('Unsupported audit query arguments: '+', '.join(sorted(unknown)))
    offset=request.get('offset',0);limit=request.get('limit',100)
    if type(offset) is not int or not 0<=offset<=10000000:raise ValueError('offset must be 0..10000000')
    if type(limit) is not int or not 1<=limit<=500:raise ValueError('limit must be 1..500')
    for key in set(allowed)&request.keys():
        if not isinstance(request[key],str) or not request[key].strip() or len(request[key])>1024:raise ValueError(key+' must be a bounded nonempty string')
    return offset,limit


@contextmanager
def connect(path):
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        yield db


def query_audit(worker,request,*,uses=False):
    offset,limit=options(request,('report_id','section','catalog','object_id','field','kind','finding_status','target_catalog','target_id'))
    report,path=load_report(worker,request['report_id'])
    section=request.get('section','findings');clauses=[];params=[]
    with connect(path) as db:
        if uses:
            if not request.get('target_catalog') or not request.get('target_id'):raise ValueError('target_catalog and target_id are required')
            table='refs';columns='catalog,id,field,payload';order='catalog,id,field,payload'
            clauses=['target_catalog = ? COLLATE NOCASE','target = ?'];params=[request['target_catalog'],request['target_id']]
        else:
            if section not in ('objects','findings','fields'):raise ValueError('section must be objects, findings or fields')
            if section=='fields' and report.get('fieldValuesRecorded') is not True:raise ValueError('This audit has no complete field-value recording contract; create a new schema 2 audit')
            table=section;columns='payload';order='catalog,id,field' if section=='fields' else 'catalog,id' if section=='objects' else 'seq'
            if section!='findings' and ('kind' in request or 'finding_status' in request):raise ValueError('Finding filters require section=findings')
            if 'field' in request:
                if section!='fields':raise ValueError('field filter requires section=fields')
                clauses.append('field = ?');params.append(request['field'])
            for key,column in [('kind','kind'),('finding_status','status')]:
                if key in request:clauses.append(column+' = ?');params.append(request[key])
        for key,column in [('catalog','catalog'),('object_id','id')]:
            if key in request:clauses.append(column+' = ?'+(' COLLATE NOCASE' if key=='catalog' else ''));params.append(request[key])
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        total=db.execute('SELECT count(*) FROM '+table+where,params).fetchone()[0]
        rows=db.execute('SELECT '+columns+' FROM '+table+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',params+[limit,offset])
        decoded=({'catalog':r[0],'objectId':r[1],'field':r[2],'reference':json.loads(r[3])} for r in rows) if uses else (json.loads(r[0]) for r in rows)
        items=bounded_rows(decoded,('catalog','id','objectId','field','kind','status','path'))
    return {'status':'AUDIT_USES_READ' if uses else 'AUDIT_PAGE_READ','reportId':request['report_id'],'mapRevision':report['mapRevision'],
            'projectRevision':report.get('projectRevision'),'editorRequired':False,'section':'incoming-typed-references' if uses else section,
            'totalMatches':total,'offset':offset,'limit':limit,'nextOffset':offset+len(items) if offset+len(items)<total else None,'items':items,
            'fullObservations':{'objects':report.get('objectsArtifact'),'findings':report.get('findingsArtifact')},
            'fieldValueCoverage':report.get('fieldValueCoverage'),'fieldValueEncodingVersion':report.get('fieldValueEncodingVersion'),
            'scope':'Recorded original typed references only; actor strings, computed/runtime references and trigger uses are not inferred' if uses else 'Immutable recorded native observations'}


def compare_audits(worker,request):
    offset,limit=options(request,('before_report_id','after_report_id','section','catalog','object_id','field'))
    before,left=load_report(worker,request['before_report_id'])
    after,right=(before,left) if request['before_report_id']==request['after_report_id'] else load_report(worker,request['after_report_id'])
    section=request.get('section','findings')
    if section not in ('objects','findings','fields'):raise ValueError('section must be objects, findings or fields')
    if 'field' in request and section!='fields':raise ValueError('field filter requires section=fields')
    if section=='fields' and any(r.get('fieldValuesRecorded') is not True for r in (before,after)):
        raise ValueError('Field comparison requires two schema 2 field-value audits; old reports contain no scalar values')
    if section=='fields' and before.get('fieldValueEncodingVersion',1)!=after.get('fieldValueEncodingVersion',1):
        raise ValueError('Field-value encoding versions differ; create both audits with the same toolkit version')
    rows=[];counts={'added':0,'removed':0,'modified':0};matched=0;inline_bytes=0
    # Ordered merge streams instead of materializing either large audit in RAM.
    with connect(left) as a,connect(right) as b:
        def ordered(db):
            where=[];params=[]
            for key,column in [('catalog','catalog'),('object_id','id')]:
                if key in request:where.append(column+' = ?'+(' COLLATE NOCASE' if key=='catalog' else ''));params.append(request[key])
            if 'field' in request:where.append('field = ?');params.append(request['field'])
            condition=' WHERE '+' AND '.join(where) if where else ''
            keys='catalog,id,field' if section=='fields' else 'catalog,id' if section=='objects' else 'digest'
            return iter(db.execute('SELECT '+keys+',payload,digest FROM '+section+condition+' ORDER BY '+keys,params))
        identical=before['indexArtifact']['sha256']==after['indexArtifact']['sha256']
        ia,ib=(iter(()),iter(())) if identical else (ordered(a),ordered(b));x=next(ia,None);y=next(ib,None)
        def key(row):return row[:3] if section=='fields' else row[:2] if section=='objects' else row[:1]
        while x is not None or y is not None:
            worker._check_abort()
            if y is None or (x is not None and key(x)<key(y)):kind='removed';old=x;new=None;x=next(ia,None)
            elif x is None or key(y)<key(x):kind='added';old=None;new=y;y=next(ib,None)
            else:
                old,new=x,y;x=next(ia,None);y=next(ib,None)
                if old[-1]==new[-1]:continue
                kind='modified'
            counts[kind]+=1
            if offset<=matched<offset+limit:
                row={'change':kind,'before':json.loads(old[-2]) if old else None,'after':json.loads(new[-2]) if new else None}
                row=bounded_rows([row],('change',),budget=max(0,512*1024-inline_bytes))[0]
                inline_bytes+=len(encoded(row).encode('utf8'));rows.append(row)
            matched+=1
    rows=bounded_rows(rows,('change',))
    complete=all(r.get('fieldValueCoverage',{}).get('complete') is True for r in (before,after)) if section=='fields' else True
    return {'status':'AUDIT_COMPARISON_COMPLETED' if complete else 'AUDIT_COMPARISON_COMPLETED_WITH_COVERAGE_GAPS',
            'comparisonCoverageComplete':complete,'editorRequired':False,'section':section,'counts':counts,'totalChanges':matched,'offset':offset,'limit':limit,
            'nextOffset':offset+len(rows) if offset+len(rows)<matched else None,'changes':rows,
            'before':{'reportId':request['before_report_id'],'mapRevision':before['mapRevision'],'projectRevision':before.get('projectRevision')},
            'after':{'reportId':request['after_report_id'],'mapRevision':after['mapRevision'],'projectRevision':after.get('projectRevision')},
            'sameEditorAdapter':bool(before.get('editorInfo',{}).get('sha256')) and before.get('editorInfo',{}).get('sha256')==after.get('editorInfo',{}).get('sha256'),
            'sameProjectRevision':bool(before.get('projectRevision')) and before.get('projectRevision')==after.get('projectRevision'),
            'fieldValueCoverage':{'before':before.get('fieldValueCoverage'),'after':after.get('fieldValueCoverage')},
            'scope':'Original effective field serialization by catalog/object/path; unsupported values remain explicit and runtime player state is excluded' if section=='fields' else 'Immutable recorded object observations or findings; use section=fields for value changes'}
