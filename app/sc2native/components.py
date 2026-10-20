"""Read exact MPQ members and compare native save results without repacking."""
import difflib
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)


def list_members(archive,tool):
    run=subprocess.run([str(tool),'list','--all','--detailed',str(archive)],capture_output=True,creationflags=NO_WINDOW,timeout=120)
    if run.returncode:raise RuntimeError('Cannot enumerate archive members: '+run.stderr.decode('utf8',errors='replace')[-1000:])
    members=[];keys=set()
    for line in run.stdout.decode('utf-8-sig').splitlines():
        found=re.fullmatch(r'\s*(\d+)\s+(\S+)\s+(.+)',line)
        if not found:raise ValueError('Unsupported mpqcli member listing; no complete comparison is claimed')
        size,locale,archive_name=found.groups();name=archive_name.replace('\\','/');key=locale+':'+name.casefold()
        if key in keys:raise ValueError('Ambiguous case-insensitive archive member and locale: '+name)
        keys.add(key);members.append({'key':key,'name':name,'archiveName':archive_name,'locale':locale,'bytes':int(size)})
    if not members:raise ValueError('Archive enumeration returned no members')
    return members


def read_member(archive,member,tool,work,*,text=False):
    # A native read-only helper may be terminated on timeout; an injected Editor
    # handler must never be terminated this way. Payloads stream to a private
    # temporary file rather than allocating memory for large embedded media.
    with tempfile.TemporaryFile(dir=work) as payload:
        run=subprocess.run([str(tool),'read','--locale',member['locale'],member.get('archiveName',member['name']),str(archive)],
            stdout=payload,stderr=subprocess.PIPE,creationflags=NO_WINDOW,timeout=120)
        if run.returncode:raise RuntimeError('Cannot read archive component '+member['name']+': '+run.stderr.decode('utf8',errors='replace')[-1000:])
        size=payload.tell()
        if size!=member['bytes']:raise RuntimeError('Component locale/size readback mismatch: '+member['name'])
        payload.seek(0);digest=hashlib.sha256()
        for chunk in iter(lambda:payload.read(1024**2),b''):digest.update(chunk)
        content=None
        if text and size<=2*1024**2:
            payload.seek(0);raw=payload.read()
            if b'\x00' not in raw:
                try:content=raw.decode('utf-8-sig')
                except UnicodeError:pass
        return {**member,'sha256':digest.hexdigest()},content


def snapshot_components(archive,tool,work):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    members=list_members(archive,tool);result={}
    for member in members:
        value,_=read_member(archive,member,tool,work);result[value['key']]=value
    return {'complete':True,'scope':'all mpqcli-enumerated members, including archive metadata and locales',
            'count':len(result),'members':result}


def compare_components(before,after,*,before_archive=None,after_archive=None,tool=None,work=None,include_diffs=False):
    changes=[];a,b=before['members'],after['members'];diff_budget=1024*1024
    for key in sorted(a.keys()|b.keys()):
        old,new=a.get(key),b.get(key)
        if old and new and old['sha256']==new['sha256']:continue
        value=new or old
        row={'name':value['name'],'locale':value['locale'],'change':'added' if old is None else 'removed' if new is None else 'modified',
             'before':old,'after':new,'archiveMetadata':value['name'] in ('(listfile)','(attributes)','(signature)')}
        if include_diffs and diff_budget>0:
            left=read_member(before_archive,old,tool,work,text=True)[1] if old else ''
            right=read_member(after_archive,new,tool,work,text=True)[1] if new else ''
            if left is not None and right is not None:
                lines=list(difflib.unified_diff(left.splitlines(),right.splitlines(),fromfile='before/'+value['name'],tofile='after/'+value['name'],lineterm=''))
                excerpt='\n'.join(lines[:200]).encode('utf8');cap=min(65536,diff_budget)
                row['textDiff']=excerpt[:cap].decode('utf8',errors='ignore')
                row['diffTruncated']=len(lines)>200 or len(excerpt)>cap;diff_budget-=len(row['textDiff'].encode('utf8'))
            else:row['textDiffUnavailable']='binary, non-UTF8 or above 2 MiB; exact hashes and byte sizes retained'
        changes.append(row)
    return {'complete':before.get('complete') is True and after.get('complete') is True,'equal':not changes,
            'beforeCount':before['count'],'afterCount':after['count'],'changedCount':len(changes),
            'added':sum(c['change']=='added' for c in changes),'removed':sum(c['change']=='removed' for c in changes),
            'modified':sum(c['change']=='modified' for c in changes),'changes':changes}
