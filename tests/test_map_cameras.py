import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.map_cameras import camera_records,choose_camera,verify_readback

class MapCameras(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
