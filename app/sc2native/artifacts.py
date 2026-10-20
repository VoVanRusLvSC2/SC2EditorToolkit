"""Immutable exports and opaque download identifiers."""
import hashlib, os, uuid, shutil
from pathlib import Path

class ArtifactStore:
    def __init__(self,root):self.root=Path(root);self.items={}
    def export(self,data,*,suffix='.galaxy',mime='text/plain; charset=utf-8',output=None,overwrite=False):
        if not isinstance(data,bytes):raise TypeError('Export must use exact bytes')
        ident=uuid.uuid4().hex
        path=Path(output).resolve() if output else (self.root/ident/('Native'+suffix)).resolve()
        if path.suffix.lower()!=suffix:raise ValueError('Output extension must be '+suffix)
        path.parent.mkdir(parents=True,exist_ok=True)
        if overwrite:
            temporary=path.with_name(path.name+'.'+ident+'.tmp')
            try:
                with temporary.open('xb') as f:f.write(data)
                os.replace(temporary,path)
            finally:temporary.unlink(missing_ok=True)
        else:
            with path.open('xb') as f:f.write(data)
        entry={'id':ident,'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mime':mime,'download':'/artifacts/'+ident}
        self.items[ident]=entry;return entry
    def register_png(self,path):
        data=Path(path).read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Native renderer did not produce a PNG')
        ident=uuid.uuid4().hex
        entry={'id':ident,'path':str(Path(path).resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mime':'image/png','download':'/artifacts/'+ident}
        self.items[ident]=entry;return entry
    def publish_file(self,source,*,suffix,mime,output=None,overwrite=False):
        """Publish a large validated artifact atomically without reading it all."""
        ident=uuid.uuid4().hex
        target=Path(output).resolve() if output else (self.root/ident/('Native'+suffix)).resolve()
        if target.suffix.lower()!=suffix:raise ValueError('Output extension must be '+suffix)
        target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.'+ident+'.tmp')
        try:
            with Path(source).open('rb') as incoming,temporary.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing,1024**2)
            if overwrite:os.replace(temporary,target)
            elif os.name=='nt':os.rename(temporary,target) # Windows rename refuses an existing target.
            else:os.link(temporary,target)
        finally:temporary.unlink(missing_ok=True)
        digest=hashlib.sha256()
        with target.open('rb') as incoming:
            for chunk in iter(lambda:incoming.read(1024**2),b''):digest.update(chunk)
        entry={'id':ident,'path':str(target),'bytes':target.stat().st_size,'sha256':digest.hexdigest(),'mime':mime,'download':'/artifacts/'+ident}
        self.items[ident]=entry;return entry
    def get(self,ident):
        if ident not in self.items:raise KeyError('Unknown artifact')
        item=self.items[ident]
        digest=hashlib.sha256()
        with Path(item['path']).open('rb') as incoming:
            for chunk in iter(lambda:incoming.read(1024**2),b''):digest.update(chunk)
        if digest.hexdigest()!=item['sha256']:raise RuntimeError('Artifact changed after export')
        return item
