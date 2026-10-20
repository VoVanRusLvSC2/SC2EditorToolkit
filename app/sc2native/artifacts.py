"""Immutable exports and opaque download identifiers."""
import hashlib, os, uuid
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
    def get(self,ident):
        if ident not in self.items:raise KeyError('Unknown artifact')
        item=self.items[ident]
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Artifact changed after export')
        return item
