"""Opt-in native XYZ camera round trip and full-map PNG, on private copies."""
import argparse,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from sc2native.session import Worker


def main():
    p=argparse.ArgumentParser();p.add_argument('--map',required=True);p.add_argument('--work',required=True);a=p.parse_args()
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=False);source=Path(a.map).resolve(strict=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest();w=Worker(work/'runtime');checks=[]
    try:
        w.ensure(source,startup_module='terrain');print('OWNED_TERRAIN_READY',flush=True)
        for name,camera in [('Southwest',dict(x=18,y=18,z=8.5,pitch=56,yaw=180,roll=0,distance=34,fov=27.8)),
                            ('Northeast',dict(x=45,y=45,z=10,pitch=65,yaw=90,roll=8,distance=45,fov=45))]:
            result=w.capture_terrain({'terrain_camera':camera,'output':str(work/(name+'.png'))})
            (work/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            assert result['status']=='TERRAIN_FRAME_CAPTURED' and result['requestedTerrainFrameVerified'],result
            assert len(result['terrainCamera']['verification']['checked'])==8
            assert result['imageHasDetail'] and not result['emptyFrame'] and result['sourceUnchanged']
            checks.append(result['terrainCamera']);print(name,'PASSED',flush=True)
        assert hashlib.sha256((work/'Southwest.png').read_bytes()).digest()!=hashlib.sha256((work/'Northeast.png').read_bytes()).digest()
        full=w.export_map_image({'size':512,'include_units':True,'include_doodads':True,'output':str(work/'FullMap.png')})
        assert full['wholeMapVerified'] and full['objectFiltersVerified'] and full['sourceUnchanged']
        observed=w.monitor.snapshot();assert not observed['visibleWindowsOnUserDesktopPeak'] and not observed['editorForegroundSamples']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        (work/'VERIFICATION.json').write_text(json.dumps({'status':'NATIVE_CUSTOM_CAMERA_AND_COMPLETE_MAP_PASSED','cameras':checks,
            'fullMap':full['image'],'sourceUnchanged':True,'observation':observed},indent=2),encoding='utf8')
    finally:
        observed=w.monitor.snapshot() if w.monitor else None;w.close()
        (work/'closed.json').write_text(json.dumps({'ownedClosed':not w.alive(),'observation':observed}),encoding='utf8')


if __name__=='__main__':main()
