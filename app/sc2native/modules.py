"""Explicit capabilities; future timeline methods stay unadvertised until implemented."""
MODULES=[
 {'id':'editor','version':2,'methods':['start','open','status','diagnostics','stop'],'startupModules':['Terrain','Triggers','Data','Import','AI','UI','Text','Overview']},
 {'id':'triggers','version':1,'methods':['convert_xml','compile_all','view_script']},
 {'id':'galaxy','version':1,'methods':['export','download'],'format':'exact native UTF-8 bytes'},
 {'id':'terrain','version':1,'methods':['capture_frame'],'captureSource':'original Terrain D3D9 viewport','view':'current native map view','requires':'.SC2Map','desktopScreenshot':False},
 {'id':'cutscene','version':4,'methods':['open_module','load','seek','capture_frame','export_mp4','export_status','export_cancel'],'timelineControl':True,'timeResolutionMs':33,
  'captureSource':'original D3D9 backbuffer; no desktop screenshots',
  'video':{'format':'mp4','codec':'h264','audioIncluded':True,'audioCodec':'aac','audioSource':'owned Editor output buffers','audioOptional':True,'defaultFps':30,'maxFps':60,'requires':['ffmpeg','ffprobe']}},
]

def capabilities():return {'version':'0.6.0','modules':MODULES,'background':True,'mouseKeyboardAutomation':False}
