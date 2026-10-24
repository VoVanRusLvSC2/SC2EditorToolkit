"""Create a checksummed, allowlisted release from a tested frozen package.

Requires the packaging Python environment (PyInstaller). Never includes work
directories or private acceptance evidence. Run after committing reviewed source.
"""
import argparse
import hashlib
import json
import marshal
import shutil
import subprocess
import zipfile
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.0.0'
NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--dist',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();dist=Path(args.dist).resolve();native=Path(args.native).resolve();output=Path(args.output).resolve()
    def git(*parts):return subprocess.check_output(['git',*parts],cwd=ROOT,text=True,creationflags=NO_WINDOW).strip()
    if git('status','--porcelain'):raise RuntimeError('Commit reviewed source and acceptance documentation before packaging')
    commit=git('rev-parse','HEAD');components=json.loads((native/'native-manifest.json').read_text(encoding='utf-8-sig'))
    assert components['version']==VERSION and components['nativeProtocol']==15
    hashes={name:sha(native/name) for name in components['sha256']};assert hashes==components['sha256']
    for name in ('SC2NativeAPI.exe','SC2NativeMCP.exe'):
        archive=CArchiveReader(str(dist/name));pyz=archive.open_embedded_archive('PYZ.pyz')
        assert json.loads(archive.extract('native-manifest.json').decode('utf-8-sig'))==components
        for file,digest in hashes.items():assert hashlib.sha256(archive.extract(file)).hexdigest()==digest
        for source in (ROOT/'app/sc2native').glob('*.py'):
            module='sc2native' if source.stem=='__init__' else 'sc2native.'+source.stem
            if module not in pyz.toc:
                if name=='SC2NativeMCP.exe' and module=='sc2native.service':continue
                raise RuntimeError('Missing toolkit module: '+module)
            code=pyz.extract(module)
            if code!=compile(source.read_bytes(),code.co_filename,'exec'):raise RuntimeError('Frozen source differs from committed source: '+module)
        entry='hidden_api' if name=='SC2NativeAPI.exe' else 'mcp_server'
        code=marshal.loads(archive.extract(entry));assert code==compile((ROOT/'app'/(entry+'.py')).read_bytes(),code.co_filename,'exec')
        assert not any('numpy' in n.lower() for n in archive.toc)
    docs=sorted(p.name for p in (ROOT/'docs').glob('*.md'))
    (dist/'docs').mkdir(exist_ok=True)
    for name in docs:shutil.copyfile(ROOT/'docs'/name,dist/'docs'/name)
    for name in ('README.md','LICENSE','NOTICE','THIRD_PARTY.txt'):shutil.copyfile(ROOT/name,dist/name)
    manifest={'project':'SC2 Editor Toolkit','version':VERSION,'prerelease':False,'apiContractVersion':1,'nativeProtocol':15,
              'sourceCommit':commit,'platform':'Windows x64','supportedEditorBuild':'5.0.17.98310',
              'nativeSha256':hashes,'frozenToolkitSourceVerified':True,'mcpTools':31,'acceptance':'docs/V1_ACCEPTANCE.md'}
    (dist/'BUILD.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    allowed={'SC2NativeAPI.exe','SC2NativeMCP.exe','README.md','LICENSE','NOTICE','THIRD_PARTY.txt','BUILD.json','SHA256SUMS.txt'}
    allowed.update('docs/'+name for name in docs)
    allowed.update('LICENSE-'+name+'.txt' for name in ('DXVK','MinHook','Pillow','mpqcli','CLI11','StormLib'))
    actual={p.relative_to(dist).as_posix() for p in dist.rglob('*') if p.is_file()}
    if actual-allowed:raise RuntimeError('Unexpected files in public package: '+str(actual-allowed))
    files=sorted(p for p in dist.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
    (dist/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(dist).as_posix()+'\n' for p in files),encoding='utf8')
    assert {p.relative_to(dist).as_posix() for p in dist.rglob('*') if p.is_file()}==allowed
    output.mkdir(parents=True,exist_ok=True);target=output/('SC2EditorToolkit-v'+VERSION+'-win64.zip')
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(dist.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(dist).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for row in archive.read('SHA256SUMS.txt').decode().splitlines():
            expected,name=row.split('  ',1);assert hashlib.sha256(archive.read(name)).hexdigest()==expected
    digest=sha(target);(output/'SHA256SUMS.txt').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    print(json.dumps({'asset':str(target),'bytes':target.stat().st_size,'sha256':digest,'commit':commit,'files':len(allowed)},indent=2))

if __name__=='__main__':main()
