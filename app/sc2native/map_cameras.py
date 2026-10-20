"""Saved map cameras: exact IDs and original properties, never runtime motion."""
import re
import math
import subprocess
from .map_objects import xml_root,vector


def camera_records(objects,strings=None):
    strings=strings or {};result=[];ids=set()
    for element in xml_root(objects,'PlacedObjects').findall('ObjectCamera'):
        ident=element.get('Id')
        if not ident or ident in ids:raise ValueError('Missing or duplicate saved map camera ID')
        ids.add(ident);reference=element.get('Name','');name=strings.get(reference,reference)
        values={}
        for value in element.findall('CameraValue'):
            index=value.get('Index')
            if index is None or index in values:raise ValueError('Ambiguous saved camera parameter')
            values[index]=value.get('Value')
        position=vector(element.get('Position'),3)
        target=vector(element.get('CameraTarget'),2)
        result.append({'cameraId':ident,'name':name,'nameReference':reference,'nameResolved':reference in strings,
                       'position':dict(zip(('x','y','z'),position)) if position else None,
                       'target':dict(zip(('x','y'),target)) if target else None,
                       'values':values,'attributes':dict(element.attrib)})
    return result


def choose_camera(cameras,ident):
    if not isinstance(ident,str) or not ident.strip() or len(ident)>128:raise ValueError('map_camera_id must be a nonempty saved camera ID string')
    matches=[camera for camera in cameras if camera['cameraId']==ident]
    if len(matches)!=1:raise ValueError('Saved map camera ID was not found uniquely')
    camera=matches[0]
    if not camera['name'] or len(camera['name'])>511:raise ValueError('Saved camera has no supported native display name')
    if sum(other['name']==camera['name'] for other in cameras)!=1:raise ValueError('Camera name is ambiguous in the original Editor; selection refused')
    return camera


FIELDS={'Pitch':'pitch','Yaw':'yaw','Roll':'roll','Distance':'distance','FieldOfView':'fov'}


def verify_readback(camera,actual):
    if not actual.get('selected') or not actual.get('valuesRead') or actual.get('name')!=camera['name']:
        raise RuntimeError('Original map camera selection/readback was not confirmed')
    if camera['target'] is None or any(abs(actual['target'][key]-camera['target'][key])>.02 for key in ('x','y')):
        raise RuntimeError('Original Terrain target does not match saved CameraTarget')
    checked=['target.x','target.y']
    for source,key in FIELDS.items():
        if source not in camera['values']:continue
        try:expected=float(camera['values'][source])
        except (TypeError,ValueError):raise ValueError('Saved camera has a nonnumeric '+source)
        if not math.isfinite(expected):raise ValueError('Saved camera has a nonfinite '+source)
        delta=actual[key]-expected
        if key in ('pitch','yaw','roll'):delta=(delta+180)%360-180
        if abs(delta)>.11:raise RuntimeError('Original camera '+source+' does not match the saved value')
        checked.append(key)
    return {'checked':checked,'unverifiedSavedParameters':[key for key in camera['values'] if key not in FIELDS],
            'numericTolerance':.11,'targetTolerance':.02,'source':'original Get Game Camera controls; bounded native UI precision'}


def read_camera_records(archive,tool,locale='enUS'):
    if not isinstance(locale,str) or not re.fullmatch(r'[a-z]{2}[A-Z]{2}',locale):raise ValueError('locale must be an SC2 locale such as enUS')
    def read(*args):
        run=subprocess.run([str(tool),*map(str,args)],capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode:raise RuntimeError('Cannot read saved cameras: '+run.stderr.decode('utf8',errors='replace')[-1000:])
        return run.stdout
    names=read('list',archive).decode('utf-8-sig').splitlines()
    target=locale+'.SC2Data/LocalizedData/GameStrings.txt'
    matches=[name for name in names if name.replace('\\','/').casefold()==target.casefold()]
    if len(matches)>1:raise ValueError('Ambiguous camera localization component')
    strings={}
    if matches:
        for line in read('read',matches[0],archive).decode('utf-8-sig').splitlines():
            if '=' in line:
                key,value=line.split('=',1)
                if key in strings and strings[key]!=value:raise ValueError('Conflicting camera localization key')
                strings[key]=value
    return camera_records(read('read','Objects',archive),strings)
