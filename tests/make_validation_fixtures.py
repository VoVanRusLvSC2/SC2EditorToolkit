"""Opt-in private positive/negative maps; never track or modify Blizzard/user maps."""
import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def make_fixtures(base,output,*,water_map=None):
    root=Path(__file__).resolve().parents[1];tool=root/'tools/mpqcli/mpqcli.exe'
    base=Path(base).resolve(strict=True);output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    original=digest(base);payload=output/'payload.xml';cases=[]
    def read(path,member):return subprocess.check_output([str(tool),'read',member.replace('/','\\'),str(path)],creationflags=subprocess.CREATE_NO_WINDOW)
    def copy(name):
        target=output/(name+base.suffix);shutil.copyfile(base,target);return target
    def add(target,member,data):
        payload.write_bytes(data)
        subprocess.run([str(tool),'add','-w','-p',member.replace('/','\\'),str(target),str(payload)],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    healthy=copy('Healthy');cases.append({'name':'healthy','map':str(healthy),'expected':'native-compile-and-clean-load'})
    localized=copy('Localized')
    for locale,name in (('enUS','Toolkit localization test'),('ruRU','Проверка локализации — ёжик')):
        member=locale+'.SC2Data/LocalizedData/GameStrings.txt'
        try:lines=read(base,member).decode('utf-8-sig').splitlines()
        except subprocess.CalledProcessError:lines=[]
        lines=[line for line in lines if not line.startswith(('DocInfo/Name=','SC2NativeToolkit/LocalizationProbe='))]
        lines+=['DocInfo/Name='+name,'SC2NativeToolkit/LocalizationProbe='+name]
        add(localized,member,('\r\n'.join(lines)+'\r\n').encode('utf8'))
    components=ET.fromstring(read(base,'ComponentList.SC2Components'))
    for locale in ('enUS','ruRU'):
        if not any(n.get('Type')=='text' and n.get('Locale')==locale for n in components):ET.SubElement(components,'DataComponent',Type='text',Locale=locale).text='GameText'
    add(localized,'ComponentList.SC2Components',ET.tostring(components,encoding='utf-8',xml_declaration=True))
    cases.append({'name':'localized','map':str(localized),'expected':'native save/reopen preserves English/Cyrillic localized map text; original compilation remains valid'})
    model=copy('DataOverrides')
    add(model,'Base.SC2Data/GameData/UnitData.xml',b'<Catalog><CUnit id="Marine"><LifeMax value="73"/></CUnit></Catalog>')
    add(model,'Base.SC2Data/GameData/ModelData.xml',b'<Catalog><CModel id="NativeToolkitMissingModel" parent="Marine"><Model value="Assets\\SC2EditorToolkit\\IntentionallyMissing.m3"/></CModel></Catalog>')
    cases.append({'name':'data-overrides','map':str(model),'expected':'Marine LifeMax=73 in original effective fields; missing main Model file fails original Archive Browser lookup'})
    bad=copy('MalformedData');add(bad,'Base.SC2Data/GameData/UnitData.xml',b'<Catalog><CUnit id="NativeToolkitMalformed">')
    cases.append({'name':'malformed-data','map':str(bad),'expected':'new original XML/Data error'})
    missing=copy('MissingDependency');document=ET.fromstring(read(base,'DocumentInfo'));values=document.findall('./Dependencies/Value')
    if not values:raise ValueError('Base map must have at least one native dependency')
    old=values[-1].text;new='file:Mods/SC2NativeIntentionallyMissingDependency.SC2Mod';values[-1].text=new
    header=read(base,'DocumentHeader')
    if header.count(old.encode('utf8')+b'\0')!=1:raise ValueError('Unsupported dependency header; no guessed binary modification')
    add(missing,'DocumentInfo',ET.tostring(document,encoding='utf-8',xml_declaration=True))
    add(missing,'DocumentHeader',header.replace(old.encode('utf8')+b'\0',new.encode('utf8')+b'\0'))
    cases.append({'name':'missing-dependency','map':str(missing),'expected':'new original missing-dependency error and worker recovery'})
    if water_map:
        source=Path(water_map).resolve(strict=True);water_hash=digest(source);data=read(source,'t3Water')
        if data[:4]!=b'WATR' or len(data)<=32:raise ValueError('Water source has no nonempty original water component')
        target=output/('WaterSource'+source.suffix);shutil.copyfile(source,target)
        cases.append({'name':'water','map':str(target),'expected':'native overhead water rendering; visual review required','originalSha256':water_hash})
        if digest(source)!=water_hash:raise RuntimeError('Water source changed')
    if digest(base)!=original:raise RuntimeError('Base source changed')
    for case in cases:case['sha256']=digest(case['map'])
    manifest={'schemaVersion':1,'sourceSha256':original,'sourceUnchanged':True,'cases':cases}
    (output/'matrix.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');payload.unlink(missing_ok=True)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True);parser.add_argument('--output',required=True);parser.add_argument('--water-map')
    args=parser.parse_args();print(json.dumps(make_fixtures(args.base,args.output,water_map=args.water_map),indent=2))
