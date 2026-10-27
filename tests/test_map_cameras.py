import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.map_cameras import camera_records,choose_camera,verify_readback,terrain_camera_options,verify_custom_readback

class MapCameras(unittest.TestCase):
    def test_custom_camera_requires_all_explicit_finite_parameters(self):
        value=dict(x=20,y=30,z=8,pitch=50,yaw=180,roll=0,distance=35,fov=28)
        self.assertEqual(terrain_camera_options(value),value)
        for key,bad in [('x',True),('y',float('nan')),('pitch',91),('distance',0),('fov',180),('yaw',720)]:
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):terrain_camera_options({**value,key:bad})
        with self.assertRaises(ValueError):terrain_camera_options({**value,'unknown':4})
        with self.assertRaises(ValueError):terrain_camera_options({'x':20})
    def test_id_localization_and_original_values(self):
        rows=camera_records(b'<PlacedObjects><ObjectCamera Id="9" Name="Camera/Name/A" Position="10,20,3" CameraTarget="12,23"><CameraValue Index="Distance" Value="22.5"/></ObjectCamera></PlacedObjects>',{'Camera/Name/A':'Opening'})
        self.assertEqual(choose_camera(rows,'9')['name'],'Opening')
        self.assertEqual(rows[0]['position'],{'x':10,'y':20,'z':3});self.assertEqual(rows[0]['values'],{'Distance':'22.5'})
        self.assertEqual(rows[0]['target'],{'x':12,'y':23})
    def test_duplicate_names_do_not_choose_first(self):
        rows=camera_records(b'<PlacedObjects><ObjectCamera Id="1" Name="A"/><ObjectCamera Id="2" Name="A"/></PlacedObjects>')
        with self.assertRaises(ValueError):choose_camera(rows,'2')
    def test_missing_and_duplicate_ids_rejected(self):
        for xml in [b'<PlacedObjects><ObjectCamera/></PlacedObjects>',b'<PlacedObjects><ObjectCamera Id="1"/><ObjectCamera Id="1"/></PlacedObjects>']:
            with self.assertRaises(ValueError):camera_records(xml)
        for ident in [1,True,'',None,'999']:
            with self.assertRaises(ValueError):choose_camera([],ident)
    def test_readback_checks_angles_not_only_target(self):
        camera={'name':'A','target':{'x':1,'y':2},'values':{'Yaw':'359.999','Distance':'34'}}
        actual={'name':'A','selected':1,'valuesRead':1,'target':{'x':1,'y':2},'yaw':0,'distance':34}
        self.assertIn('yaw',verify_readback(camera,actual)['checked'])
        with self.assertRaises(RuntimeError):verify_readback(camera,dict(actual,yaw=90))
        with self.assertRaises(RuntimeError):verify_readback(camera,dict(actual,distance=20))
    def test_custom_camera_verifies_every_coordinate_and_rejects_clamping(self):
        requested=dict(x=20,y=30,z=8,pitch=50,yaw=180,roll=0,distance=35,fov=28)
        actual={**requested,'target':{k:requested[k] for k in ('x','y','z')},'name':'Current Terrain Camera','selected':1,'valuesRead':1}
        self.assertEqual(len(verify_custom_readback(requested,actual)['checked']),8)
        for key in ('pitch','yaw','roll','distance','fov'):
            with self.assertRaises(RuntimeError):verify_custom_readback(requested,{**actual,key:requested[key]+1})
        with self.assertRaises(RuntimeError):verify_custom_readback(requested,{**actual,'target':dict(x=20,y=30,z=9)})

if __name__=='__main__':unittest.main()
