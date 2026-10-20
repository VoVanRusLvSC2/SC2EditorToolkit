"""Opt-in native private save/reopen and operation-diagnostic regression.

Requires a healthy installed map/mod and its actual dependencies. User inputs
are hashed and copied, never modified. No device input or desktop switching.
"""
import argparse,hashlib,json,shutil,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--work',required=True)
p.add_argument('--package',action='store_true');p.add_argument('--scope',default=None)
p.add_argument('--roundtrip-only',action='store_true',help='Check save/reopen, compiler and exports without injecting Data faults')
p.add_argument('--missing-dependency',action='store_true',help='Also exercise an intentionally missing private dependency')
args=p.parse_args();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False)
source=Path(args.template).resolve(strict=True);sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
original=sha(source);tool=ROOT/'tools/mpqcli/mpqcli.exe'
fault=work/('MalformedData'+source.suffix);shutil.copyfile(source,fault)
payload=work/'MalformedData.xml';payload.write_bytes(b'<?xml version="1.0" encoding="utf-8"?><Catalog><CUnit id="NativeBadXml">')
run=subprocess.run([str(tool),'add','-w','-p','Base.SC2Data/GameData/UnitData.xml',str(fault),str(payload)],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
fault_sha=sha(fault)
command=[str(ROOT/'dist/SC2NativeAPI.exe')] if args.package else [sys.executable,str(ROOT/'app/hidden_api.py')]
command+=['serve','--port','0','--work',str(work/'runtime')]
process=subprocess.Popen(command,stdout=(work/'stdout.log').open('wb'),stderr=(work/'stderr.log').open('wb'),creationflags=subprocess.CREATE_NO_WINDOW)
info=None;records=[]
def call(route,data):
    request=urllib.request.Request(info['url']+route,json.dumps(data).encode('utf8'),{'Content-Type':'application/json','X-SC2-Token':info['token']})
    started=time.monotonic()
    try:
        with urllib.request.urlopen(request,timeout=1800) as response:result=json.load(response)
    except urllib.error.HTTPError as error:result=json.load(error)
    records.append({'route':route,'result':result})
    (work/('response-%02d.json'%len(records))).write_text(json.dumps(records[-1],indent=2),encoding='utf8')
    print(route,result.get('status'),result.get('error'),round(time.monotonic()-started,1),flush=True)
    if result.get('desktopObservation'):
        observed=result['desktopObservation']
        assert observed['visibleWindowsOnUserDesktopPeak']==observed['editorForegroundSamples']==0,observed
        assert not observed['inputInjectionUsed'] and not observed['desktopSwitchApiUsed'],observed
    return result
def download(artifact):
    request=urllib.request.Request(info['url']+artifact['download'],headers={'X-SC2-Token':info['token']})
    with urllib.request.urlopen(request,timeout=30) as response:data=response.read()
    assert hashlib.sha256(data).hexdigest()==artifact['sha256']
    return data
try:
    deadline=time.monotonic()+45
    while not (work/'runtime/api-info.json').exists():
        assert process.poll() is None and time.monotonic()<deadline,'API startup failed'
        time.sleep(.1)
    info=json.loads((work/'runtime/api-info.json').read_text())
    output=work/('Saved'+source.suffix)
    saved=call('/editor/save-reopen',{'map':str(source),'include_diffs':True,'output':str(output)})
    assert saved['nativeLoadVerified'] and saved['nativeSaveVerified'] and saved['nativeReopenVerified'],saved.get('error')
    assert saved['componentComparisonVerified'] and saved['componentComparison']['savedToReopenedEqual']
    assert saved['sourceUnchanged'] and sha(source)==original
    comparison=json.loads(download(saved['componentDiffArtifact']))
    assert comparison['savedToReopened']['equal'] and comparison['savedToReopened']['complete']
    if saved['status']=='NATIVE_SAVE_REOPEN_VERIFIED':assert sha(output)==hashlib.sha256(download(saved['savedArchive'])).hexdigest()
    else:assert saved['status']=='NATIVE_DOCUMENT_CHECK_INCOMPLETE' and saved['nativeValidationPassed'] is None
    compiled=call('/triggers/compile',{'scope':args.scope} if args.scope else {})
    assert compiled['nativeCompilePassed'],compiled.get('error')
    galaxy=call('/galaxy/export',{'output':str(work/'Native.galaxy')})
    assert sha(work/'Native.galaxy')==compiled['sourceSha256']==hashlib.sha256(download(galaxy['artifact'])).hexdigest()
    errors=None
    if not args.roundtrip_only:
        bad=call('/editor/validate',{'map':str(fault),'baseline_template':str(source)})
        errors=bad['diagnostics']['newErrors']
        assert bad['status']=='FAILED' and bad['diagnostics']['newErrorsClear'] is False and errors, bad.get('error')
        assert any('XML' in entry['message'] and 'UnitData.xml' in entry['message'] for entry in errors),errors
        again=call('/editor/diagnostics',{})['operationDiagnostics']
        assert again['newErrorCount']==0 and again['newErrorsClear'] is True and again['baselineMessages'],again
        good=call('/editor/validate',{'map':str(source)})
        assert not good['diagnostics']['newErrors'] and good['nativeLoadVerified'] and good['nativeDataModuleLoaded']
    assert sha(source)==original and sha(fault)==fault_sha
    if args.missing_dependency:
        import xml.etree.ElementTree as ET
        missing=work/('MissingDependency'+source.suffix);shutil.copyfile(source,missing)
        read=lambda member:subprocess.check_output([str(tool),'read',member,str(source)],creationflags=subprocess.CREATE_NO_WINDOW)
        doc=ET.fromstring(read('DocumentInfo'));values=doc.findall('./Dependencies/Value');assert values,'Template has no replaceable dependency'
        old=values[-1].text;replacement='file:Mods/SC2NativeIntentionallyMissingDependency.SC2Mod';values[-1].text=replacement
        header=read('DocumentHeader');assert header.count(old.encode('utf8')+b'\0')==1,'Unsupported native dependency header'
        for name,data in [('DocumentInfo',ET.tostring(doc,encoding='utf-8',xml_declaration=True)),('DocumentHeader',header.replace(old.encode('utf8')+b'\0',replacement.encode('utf8')+b'\0'))]:
            payload.write_bytes(data)
            subprocess.run([str(tool),'add','-w','-p',name,str(missing),str(payload)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        missing_sha=sha(missing)
        failed=call('/editor/validate',{'map':str(missing),'baseline_template':str(source)})
        assert failed['status']=='FAILED' and not failed['nativeValidationPassed'],failed
        assert any(e['type']=='missingDependency' and 'SC2NativeIntentionallyMissingDependency.SC2Mod' in e['message'] for e in failed['diagnostics']['newErrors']),failed['diagnostics']
        assert sha(missing)==missing_sha and sha(source)==original
        recovered=call('/editor/validate',{'map':str(source)})
        assert recovered['status']=='NATIVE_DOCUMENT_VALIDATED' and recovered['sourceUnchanged'],recovered.get('error')
    observations=[record['result']['desktopObservation'] for record in records if record['result'].get('desktopObservation')]
    summary={'status':'NATIVE_DOCUMENT_CHECKS_PASSED','package':args.package,'sourceUnchanged':sha(source)==original,
             'saveReopenVerified':True,'componentComparisonVerified':True,'roundtripValidationStatus':saved['status'],
             'nativeCompilePassed':True,'galaxyBytes':(work/'Native.galaxy').stat().st_size,
             'malformedDataErrors':len(errors) if errors is not None else None,'oldMessagesNotRecounted':not args.roundtrip_only,
             'desktopObservation':observations[-1] if observations else None,'desktopObservations':observations}
    (work/'VERIFICATION.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary),flush=True)
finally:
    if info:call('/shutdown',{})
    process.wait(timeout=30)
