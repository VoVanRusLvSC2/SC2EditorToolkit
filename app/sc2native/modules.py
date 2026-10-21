"""Explicit capabilities; future timeline methods stay unadvertised until implemented."""
MODULES=[
 {'id':'editor','version':3,'methods':['start','open','status','diagnostics','validate_document','save_reopen','stop'],'operationDiagnostics':{'source':'original Messages/Console output; operation snapshots and native append observations','unknownIsZero':False},'saveReopen':{'nativeSerialization':True,'nativeCloseBeforeReopen':True,'componentHashesByLocale':True,'textDiffsOptional':True,'sourcePreserved':True},'startupModules':['Terrain','Triggers','Data','Import','AI','UI','Text','Overview']},
 {'id':'triggers','version':1,'methods':['convert_xml','compile_all','view_script']},
 {'id':'galaxy','version':1,'methods':['export','download'],'format':'exact native UTF-8 bytes'},
 {'id':'objects','version':1,'methods':['search'],'editorRequired':False,'readOnly':True,'source':'saved map Objects XML','coordinates':'saved XYZ; Z may be terrain-relative placement offset','filters':['query','kinds','owner','bounds','offset','limit'],'maxPageSize':500},
 {'id':'terrain','version':4,'methods':['capture_frame','export_map_image','capture_region','list_map_cameras'],'savedCameras':{'selector':'map_camera_id','originalPalette':True,'nativeCameraReadback':True,'triggerExecution':False},'region':{'experimental':True,'source':'crop of original full-map pixels','coordinateMappingValidated':False,'requires':'bounds left/bottom/right/top; standard untransformed terrain','resampling':False},'captureSource':'original Terrain viewport or native Export Map Image','fullMap':{'experimental':True,'validation':'native settings confirmed; final rendered-map acceptance pending','bounds':'Full','quadrant':'All','cameraAngle':90,'defaultSize':2048,'sizeAxis':'horizontal','units':True,'doodads':True,'encoding':'PNG from native TGA pixels'},'requires':'.SC2Map','desktopScreenshot':False},
 {'id':'cutscene','version':4,'methods':['open_module','load','seek','capture_frame','export_mp4','export_status','export_cancel'],'timelineControl':True,'timeResolutionMs':33,
  'captureSource':'original D3D9 backbuffer; no desktop screenshots',
  'video':{'format':'mp4','codec':'h264','audioIncluded':True,'audioCodec':'aac','audioSource':'owned Editor output buffers','audioOptional':True,'defaultFps':30,'maxFps':60,'requires':['ffmpeg','ffprobe']}},
]

def capabilities():return {'version':'0.9.1-rc.1','modules':MODULES,'background':True,'mouseKeyboardAutomation':False}
