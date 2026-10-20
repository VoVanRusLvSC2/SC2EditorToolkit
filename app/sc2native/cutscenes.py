"""Read-only scene validation and public time/camera arguments."""
import math
from pathlib import Path
import xml.etree.ElementTree as ET

def scene_file(value):
    path=Path(value).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in ('.sc2cutscene','.stormcutscene'):
        raise ValueError('scene must be an existing .SC2Cutscene/.StormCutscene file')
    if path.stat().st_size>32*1024**2:raise ValueError('Scene exceeds 32 MiB')
    root=ET.parse(path).getroot()
    if root.tag!='CutsceneState':raise ValueError('Expected native CutsceneState XML')
    cameras=[{'name':node.get('name',''),'guid':node.get('guid',''),'type':node.tag}
        for node in root.iter() if node.tag in ('CCutsceneNodeCamera','CCutsceneNodeTargetCamera')]
    return path,cameras

def seek_arguments(request):
    camera=request.get('camera','Director')
    if not isinstance(camera,str) or not camera.strip() or len(camera)>500:raise ValueError('camera must be a nonempty native camera name')
    value=request.get('time_ms',0)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=600000:
        raise ValueError('time_ms must be finite, 0..600000 milliseconds')
    # The original Next Frame command advances 33 ms. Report the actual time
    # read from the Editor; never pretend an arbitrary subframe was evaluated.
    return camera,round(value)

def scene_duration(path):
    """Authored native milliseconds; explicit end markers take precedence."""
    root=ET.parse(path).getroot();ends=[];extent=0
    def visit(node,offset=0,enabled=True):
        nonlocal extent
        enabled=enabled and node.get('enabled','1')!='0'
        if not enabled:return
        start=float(node.get('start','0'));duration=float(node.get('duration','0'))
        if not math.isfinite(start) or not math.isfinite(duration):raise ValueError('Non-finite scene timing')
        current=offset+start
        if node.tag=='CCutsceneElementEndScene' and current>0:ends.append(current)
        if node.tag.startswith('CCutsceneElement'):extent=max(extent,current+duration)
        for child in node:visit(child,current,enabled)
    visit(root)
    return {'durationMs':round(min(ends) if ends else extent) or None,'durationSource':'directorEndScene' if ends else 'authoredElements'}
