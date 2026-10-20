"""Create a private terrain fixture with two native-format saved cameras."""
import argparse,hashlib,json,math,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from make_terrain_fixture import make_fixture

def make_camera_fixture(base,output):
    base=Path(base).resolve();before=hashlib.sha256(base.read_bytes()).hexdigest()
    result=make_fixture(base,output);output=Path(output).resolve()
    tool=Path(__file__).resolve().parents[1]/'tools/mpqcli/mpqcli.exe'
    def read(name):return subprocess.check_output([str(tool),'read',name,str(output)],creationflags=subprocess.CREATE_NO_WINDOW)
    objects=ET.fromstring(read('Objects'));width,height=result['dimensions'];cameras=[]
    for ident,name,x,y,distance,pitch,yaw in [
        ('2001','SouthwestCamera',width/4,height/4,34,56,180),
        ('2002','NortheastCamera',width*3/4,height*3/4,25,50,90)]:
        xy=f'{x:g},{y:g}'
        camera=ET.SubElement(objects,'ObjectCamera',Id=ident,Name=name,Position=xy+',0',CameraTarget=xy,
                             Rotation=str(math.radians(yaw)),Scale='1,1,1',Color='0,0,0,0')
        for key,value in [('FieldOfView',27.8),('NearClip',.1),('FarClip',600),('ShadowClip',75),
                          ('Distance',distance),('Pitch',pitch),('Yaw',yaw),('FocalDepth',8),('FalloffEnd',8)]:
            ET.SubElement(camera,'CameraValue',Index=key,Value=str(value))
        cameras.append({'cameraId':ident,'name':name,'target':{'x':x,'y':y},'distance':distance,'pitch':pitch,'yaw':yaw})
    payload=output.parent/(output.stem+'-components')/'Objects'
    payload.write_bytes(ET.tostring(objects,encoding='utf-8',xml_declaration=True))
    subprocess.run([str(tool),'add','-w','-p','Objects',str(output),str(payload)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    assert hashlib.sha256(base.read_bytes()).hexdigest()==before
    result['cameras']=cameras;output.with_suffix('.fixture.json').write_text(json.dumps(result,indent=2),encoding='utf8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(make_camera_fixture(a.base,a.output)))
