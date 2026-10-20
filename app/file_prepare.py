"""Original SC2 Editor reference frontend. No Galaxy emitter is implemented here.

prepare/compare/API dispatch do not start UI unless operation=generate is requested.
The native menu backend is product code reused from the local MAP application.
"""
from __future__ import annotations
import argparse,difflib,hashlib,json,os,shutil,subprocess,sys,time,tomllib,traceback,uuid
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET

RES=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
sys.path.insert(0,str(RES/'backend'))
EDITOR=Path(r'C:\Program Files (x86)\StarCraft II\Support64\SC2Editor_x64.exe')
LOCAL_MPQ=Path(os.environ.get('SC2_MPQCLI',str(Path(__file__).resolve().parent.parent/'tools'/'mpqcli'/'mpqcli.exe')))

def stamp(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def checked_xml(path):
    data=Path(path).read_bytes()
    if len(data)>64*1024**2: raise ValueError('Triggers XML exceeds 64 MiB')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper(): raise ValueError('DTD/entity declarations are not accepted')
    root=ET.fromstring(data)
    if root.tag!='TriggerData': raise ValueError('Expected a complete TriggerData document')
    return data,root
def mpq_tool(value=None):
    options=[Path(value)] if value else [RES/'mpqcli.exe',LOCAL_MPQ]
    for p in options:
        if p.is_file():return p.resolve()
    raise FileNotFoundError('mpqcli.exe not found; supply --mpqcli')
def command(args):
    result=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('MPQ operation failed: '+result.stderr[-3000:]+result.stdout[-1000:])
    return result.stdout
def read_strings(path):
    result={}
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig',errors='strict').splitlines():
            if '=' in line:
                key,value=line.split('=',1);result[key]=value
    return result
def context_label(root,scope,strings):
    if scope.startswith('library:'):
        ident=scope.split(':',1)[1].upper()
        libs=[x for x in root.findall('Library') if x.get('Id','').upper()==ident]
        if len(libs)!=1:raise ValueError('Library ID absent or ambiguous: '+ident)
        labels={strings[k] for k in ['Library/Name/'+ident,'Library/Name/lib_'+ident] if k in strings}
        if len(labels)>1:raise ValueError('Conflicting library display names in TriggerStrings')
        return next(iter(labels),None)
    if scope!='mapRoot':raise ValueError('Scope must be mapRoot or library:<LibraryId>')
    items=root.findall('./Root/Item')
    elements={(x.get('Type'),x.get('Id')):x for x in root.findall('Element')}
    for item in items:
        typ,ident=item.get('Type'),item.get('Id')
        e=elements.get((typ,ident))
        label=strings.get(f'{typ}/Name/{ident}')
        if label:return label
        if e is not None and e.findtext('Identifier'):return e.findtext('Identifier')
    return None

def prepare(args):
    template=Path(args.template).resolve(strict=True)
    xml,root=checked_xml(args.triggers)
    job=Path(args.job).resolve()
    if job.exists():raise FileExistsError('Job already exists; each attempt needs a fresh directory')
    if template.is_dir() and job.is_relative_to(template):raise ValueError('Job must be outside the template directory')
    if args.locale not in ('enUS','ruRU','enGB','deDE','frFR','esES','esMX','itIT','koKR','plPL','ptBR','zhCN','zhTW'):raise ValueError('Unsupported locale code')
    original_hashes={str(p.relative_to(template)):sha(p) for p in template.rglob('*') if p.is_file()} if template.is_dir() else {'archive':sha(template)}
    job.mkdir(parents=True)
    components=job/'components'
    tool=mpq_tool(getattr(args,'mpqcli',None))
    if template.is_dir():
        if any(p.is_symlink() for p in template.rglob('*')):raise ValueError('Template symlinks are not supported')
        shutil.copytree(template,components,ignore=shutil.ignore_patterns('.sc2mcp-*'))
    else:
        components.mkdir()
        (job/'mpq-extract.log').write_text(command([tool,'extract',template,'--output',components,'--keep']),encoding='utf8')
    if not (components/'ComponentList.SC2Components').is_file():raise ValueError('Template has no ComponentList.SC2Components')
    if not (components/'DocumentInfo').is_file():raise ValueError('Template has no DocumentInfo context')
    (components/'Triggers').write_bytes(xml)
    locale=components/(args.locale+'.SC2Data')/'LocalizedData';locale.mkdir(parents=True,exist_ok=True)
    for option,name in [('trigger_strings','TriggerStrings.txt'),('game_strings','GameStrings.txt')]:
        source=getattr(args,option,None)
        if source:shutil.copyfile(source,locale/name)
    label=args.context_label or context_label(root,args.scope,read_strings(locale/'TriggerStrings.txt'))
    suffix=template.suffix.lower()
    if suffix not in ('.sc2map','.sc2mod'):suffix='.SC2Map'
    name=template.name if template.suffix.lower() in ('.sc2map','.sc2mod') else 'NativeReference'+suffix
    working=job/'working-map'/name;working.parent.mkdir()
    (job/'mpq-create.log').write_text(command([tool,'create',components,'--output',working,'--game','starcraft2']),encoding='utf8')
    original_after={str(p.relative_to(template)):sha(p) for p in template.rglob('*') if p.is_file()} if template.is_dir() else {'archive':sha(template)}
    if original_after!=original_hashes:raise RuntimeError('Template changed during preparation')
    editor=Path(args.editor).resolve(strict=True)
    build_info=editor.parent.parent/'.build.info'
    manifest={'schema':1,'jobId':str(uuid.uuid4()),'createdUtc':stamp(),'status':'PREPARED_NOT_NATIVE_GENERATED','workingDocument':str(working),'workingDocumentSha256':sha(working),'sourceTemplate':str(template),'templateHashes':original_hashes,'triggersSha256':hashlib.sha256(xml).hexdigest(),'editor':str(editor),'editorSha256':sha(editor),'buildInfoSha256':sha(build_info) if build_info.is_file() else None,'locale':args.locale,'scope':args.scope,'contextLabel':label,'componentHashes':{str(p.relative_to(components)):sha(p) for p in components.rglob('*') if p.is_file()},'dependencyResolutionVerified':False,'savedGalaxyIsNotNativeReference':True}
    save(job/'manifest.json',manifest)
    return {'status':manifest['status'],'job':str(job),'manifest':str(job/'manifest.json'),'workingDocument':str(working),'contextLabel':label,'editorStarted':False}
