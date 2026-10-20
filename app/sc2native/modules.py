"""Explicit capabilities; future timeline methods stay unadvertised until implemented."""
MODULES=[
 {'id':'editor','version':1,'methods':['start','open','status','diagnostics','stop']},
 {'id':'triggers','version':1,'methods':['convert_xml','compile_all','view_script']},
 {'id':'galaxy','version':1,'methods':['export','download'],'format':'exact native UTF-8 bytes'},
 {'id':'cutscene','version':1,'methods':['open_module','capture_frame'],'timelineControl':False,
  'captureSource':'original D3D9 backbuffer; no desktop screenshots'},
]

def capabilities():return {'version':'0.2.0','modules':MODULES,'background':True,'mouseKeyboardAutomation':False}
