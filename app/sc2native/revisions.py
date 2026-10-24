"""Bind local declared archives and installed CASC build identity to an audit."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote
from .report import read_declared_dependencies

BUILTIN={'core.sc2mod','liberty.sc2mod','libertymulti.sc2mod','libertystory.sc2mod','swarm.sc2mod','swarmmulti.sc2mod','swarmstory.sc2mod','void.sc2mod','voidmulti.sc2mod','voidstory.sc2mod','novastory.sc2mod'}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def snapshot(source,editor,work,abort=lambda:None):
    source=Path(source).resolve();installation=Path(editor).resolve().parent.parent if editor else None
    archives=[];declarations=[];unresolved=[];seen=set();pending=[source]
    while pending:
        abort();path=pending.pop(0)
        if str(path).casefold() in seen:continue
        if len(seen)>=256:raise RuntimeError('Dependency manifest exceeds 256 local archives')
        seen.add(str(path).casefold());before=digest(path)
        declared=read_declared_dependencies(path,work)
        if digest(path)!=before:raise RuntimeError('Dependency changed while reading its declarations')
        archives.append({'name':path.name,'path':str(path),'sha256':before,'bytes':path.stat().st_size})
        if not declared['complete']:
            unresolved.append({'archive':path.name,'reason':declared.get('error','Declarations unavailable')});continue
        for value in declared['values']:
            declarations.append({'archive':path.name,'declaration':value})
            match=re.search(r'(?:^|,)file:([^,]+)',value,re.I)
            if not match:unresolved.append({'archive':path.name,'declaration':value,'reason':'No local file identity; published/cache dependency is not independently resolved'});continue
            name=unquote(match.group(1)).replace('\\','/');relative=Path(name);base=relative.name
            if relative.is_absolute() or '..' in relative.parts:unresolved.append({'declaration':value,'reason':'Non-relative dependency identity'});continue
            candidates={str(p.resolve()).casefold():p.resolve() for p in (path.parent/relative,path.parent/base,installation/relative if installation else path.parent/relative) if p.is_file()}
            if len(candidates)==1:pending.extend(candidates.values())
            elif not candidates and base.casefold() in BUILTIN:pass
            else:unresolved.append({'declaration':value,'reason':'Ambiguous local candidates' if candidates else 'Local archive not found'})
    build=[]
    if installation:
        for path in sorted(installation.glob('*.build.info')):
            build.append({'name':path.name,'path':str(path),'sha256':digest(path)})
    identity={'archives':[{'name':v['name'],'sha256':v['sha256']} for v in archives],
              'declarations':declarations,'gameBuildManifests':[{'name':v['name'],'sha256':v['sha256']} for v in build]}
    fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return {'schemaVersion':1,'revision':fingerprint,'archives':archives,'declaredDependencies':declarations,'gameBuildManifests':build,'unresolved':unresolved,
            'localDeclaredArchiveRevisionsVerified':not unresolved,'gameBuildIdentityVerified':bool(build),
            'scope':'SHA-256 of recursively declared local archives and installed CASC build manifest. CASC resource bytes and remote cache resolution are not independently hashed.'}


def bind_sources(manifest,sources,private_name):
    known={v['name'].casefold() for v in manifest['archives']};known.add(private_name.casefold())
    observed=sources[1:] if sources else [] # First palette entry is the localized aggregate filter.
    unknown=[name for name in observed if name.casefold() not in known and not(name.casefold() in BUILTIN and manifest['gameBuildIdentityVerified'])]
    return {**manifest,'nativeObservedSources':sources,'unmatchedNativeSources':unknown,
            'projectRevisionComplete':not unknown and not manifest['unresolved'] and manifest['gameBuildIdentityVerified'],
            'nativeResolvedPhysicalPathsVerified':False}
