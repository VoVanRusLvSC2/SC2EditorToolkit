"""Opt-in private map fixture with hills, native units and doodads.

Never modifies the supplied base map. No user assets or resulting maps are tracked.
"""
import argparse,hashlib,json,math,shutil,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path

def make_fixture(base,output):
    root=Path(__file__).resolve().parents[1];tool=root/'tools/mpqcli/mpqcli.exe'
    base=Path(base).resolve(strict=True);output=Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    digest=hashlib.sha256(base.read_bytes()).hexdigest()
    def read(name):return subprocess.check_output([str(tool),'read',name,str(base)],creationflags=subprocess.CREATE_NO_WINDOW)
    descriptor=ET.fromstring(read('t3Terrain.xml'));height=descriptor.find('heightMap');vert=height.find('vertData')
    if height.get('offset')!='0 0 0' or height.get('scale')!='1 1 1':raise ValueError('Fixture requires an untransformed base terrain')
    width,height_vertices=map(int,height.get('dim').split());xmax,ymax=width-1,height_vertices-1
    bias=float(vert.get('quantizeBias'));scale=float(vert.get('quantizeScale'));standard=float(vert.get('standardHeight'))
    heights=bytearray(read('t3HeightMap'));sync=bytearray(read('t3SyncHeightMap'))
    if heights[:4]!=b'HMAP' or len(heights)!=32+width*height_vertices*6:raise ValueError('Unsupported HMAP fixture layout')
    if sync[:4]!=b'SMAP' or len(sync)!=64+width*height_vertices*4:raise ValueError('Unsupported SMAP fixture layout')
    values=[]
    for y in range(height_vertices):
        for x in range(width):
            z=standard+5*math.exp(-((x/xmax-.3)**2+(y/ymax-.45)**2)/.012)+3*math.exp(-((x/xmax-.72)**2+(y/ymax-.7)**2)/.02)
            total=round((z+2*bias)/scale);adjust=max(32767,total-65535);native_base=total-adjust
            if not 0<=native_base<=65535 or not 0<=adjust<=65535:raise ValueError('Fixture height cannot be quantized')
            i=y*width+x;struct.pack_into('<HH',heights,32+6*i,native_base,adjust)
            struct.pack_into('<h',sync,64+4*i,round(z*256));values.append(z)
    objects=ET.Element('PlacedObjects',Version='27');ident=1000
    def add(tag,fx,fy,**attributes):
        nonlocal ident
        z=standard+5*math.exp(-((fx-.3)**2+(fy-.45)**2)/.012)+3*math.exp(-((fx-.72)**2+(fy-.7)**2)/.02) if tag=='ObjectDoodad' else 0
        ident+=1;ET.SubElement(objects,tag,Id=str(ident),Position=f'{fx*xmax:.4f},{fy*ymax:.4f},{z:.4f}',Rotation='0',Scale='1,1,1',**attributes)
    # Different built-in landmarks in each corner make cropping obvious.
    for fx,fy,unit in ((.12,.14,'CommandCenter'),(.86,.14,'Nexus'),(.12,.85,'Hatchery'),(.86,.85,'PlanetaryFortress')):
        add('ObjectUnit',fx,fy,UnitType=unit,Player='1')
    for fx,fy in ((.44,.3),(.47,.3),(.5,.3),(.53,.3),(.56,.3),(.44,.35),(.47,.35),(.5,.35),(.53,.35),(.56,.35)):
        add('ObjectUnit',fx,fy,UnitType='Marine',Player='1')
    for fx,fy in ((.18,.45),(.45,.65),(.65,.5),(.8,.38)):
        add('ObjectDoodad',fx,fy,Type='ZergCarcasses',Variation='5')
    components=output.parent/(output.stem+'-components');components.mkdir(parents=True,exist_ok=False)
    manifest=ET.fromstring(read('ComponentList.SC2Components'))
    if not any(n.get('Type')=='plob' for n in manifest):ET.SubElement(manifest,'DataComponent',Type='plob').text='Objects'
    preload=ET.fromstring(read('Preload.xml'))
    required=[('Actor','SYSTEM_ActorConfig'),('Terrain',height.get('tileSet'))]
    required += [('Unit',n.get('UnitType')) for n in objects if n.tag=='ObjectUnit']
    required += [('Actor',n.get('Type')) for n in objects if n.tag=='ObjectDoodad']
    for tag,ident in sorted(set(required)):
        if not any(n.tag==tag and n.get('id')==ident for n in preload):ET.SubElement(preload,tag,id=ident)
    # Retain the original native build/timestamp profile; change only the
    # component tag in this fresh private fixture, not the source map.
    version=bytearray(read('MapInfo.version'))
    if len(version)!=44 or version[:8]!=b'cdesipam':raise ValueError('Unsupported native fixture version marker')
    version[4:8]=b'bolp';struct.pack_into('<I',version,32,1)
    (components/'Objects.version').write_bytes(version)
    for name,node in [('ComponentList.SC2Components',manifest),('Preload.xml',preload)]:
        (components/name).write_bytes(ET.tostring(node,encoding='utf-8',xml_declaration=True))
    (components/'Objects').write_bytes(ET.tostring(objects,encoding='utf-8',xml_declaration=True))
    (components/'t3HeightMap').write_bytes(heights);(components/'t3SyncHeightMap').write_bytes(sync)
    output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(base,output)
    for name in ('Objects','Objects.version','Preload.xml','ComponentList.SC2Components','t3HeightMap','t3SyncHeightMap'):
        subprocess.run([str(tool),'add','-w','-p',name,str(output),str(components/name)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    assert hashlib.sha256(base.read_bytes()).hexdigest()==digest
    result={'fixture':str(output),'dimensions':[xmax,ymax],'units':14,'doodads':4,'heightMin':min(values),'heightMax':max(values),
        'cornerLandmarks':['CommandCenter','Nexus','Hatchery','PlanetaryFortress'],'baseUnchanged':True}
    output.with_suffix('.fixture.json').write_text(json.dumps(result,indent=2),encoding='utf8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(make_fixture(a.base,a.output)))
