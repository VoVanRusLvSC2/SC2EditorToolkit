"""Explicit capabilities; future timeline methods stay unadvertised until implemented."""
MODULES=[
 {'id':'jobs','version':1,'methods':['submit','status','wait','cancel'],'perServerEditors':1,'pendingCapacity':32,'history':256,
  'executionDeadlineSeconds':{'default':1800,'videoDefault':14400,'maximum':14400},'automaticRetry':False,'restartReplay':False,'restartIncompleteStatus':'INTERRUPTED'},
 {'id':'data','version':2,'methods':['read','links','resources','audit'],'source':'original Data editor; process-private Copy As Text, native Object Explorer and Archive Browser',
  'catalogs':['Unit','Model','Actor','Abil','Behavior','Effect','Sound','Texture','Weapon','Validator','Upgrade','Requirement'],
  'fullFieldValues':'original Copy As Text with header/row-count confirmation; clipped cells are incomplete',
  'audit':{'nativeCatalogs':109,'scope':'merged effective map/mod and loaded dependencies','typedCatalogTargets':True,'typedFilePaths':'original merged Archive Browser','opaqueTypes':'explicit coverage gaps','fullArtifacts':'JSONL objects/findings and JSON summary','runtimeSemanticValidation':False},
  'userClipboardAccessUsed':False,'relationships':'native Explorer associations; edge direction/transitivity not inferred',
  'resources':'main Model file presence in original merged Archive Browser and native diagnostics; binary integrity, nested assets and other catalogs remain incomplete'},
 {'id':'editor','version':4,'methods':['start','open','status','diagnostics','validate_document','save_reopen','check_map','stop'],'report':{'sourceRevision':'SHA-256','downloadable':True,'nativeCompilerSeparateFromMessages':True},'operationDiagnostics':{'source':'original Messages/Console output; operation snapshots and native append observations','unknownIsZero':False},'saveReopen':{'nativeSerialization':True,'nativeCloseBeforeReopen':True,'componentHashesByLocale':True,'textDiffsOptional':True,'sourcePreserved':True},'startupModules':['Terrain','Triggers','Data','Import','AI','UI','Text','Overview']},
 {'id':'triggers','version':1,'methods':['convert_xml','compile_all','view_script']},
 {'id':'galaxy','version':1,'methods':['export','download'],'format':'exact native UTF-8 bytes'},
 {'id':'objects','version':1,'methods':['search'],'editorRequired':False,'readOnly':True,'source':'saved map Objects XML','coordinates':'saved XYZ; Z may be terrain-relative placement offset','filters':['query','kinds','owner','bounds','offset','limit'],'maxPageSize':500},
 {'id':'terrain','version':5,'methods':['capture_frame','export_map_image','capture_region','list_map_cameras'],'savedCameras':{'selector':'map_camera_id','originalPalette':True,'nativeCameraReadback':True,'triggerExecution':False},'region':{'experimental':True,'source':'crop of original full-map pixels','coordinateMappingValidated':False,'requires':'bounds left/bottom/right/top; standard untransformed terrain','resampling':False},'captureSource':'original Terrain viewport or native Export Map Image','fullMap':{'experimental':False,'validation':'original flag-model readback and native full-map settings confirmed','independentObjectFilters':True,'filterSource':'original Editor model getter/setter','bounds':'Full','quadrant':'All','cameraAngle':90,'defaultSize':2048,'sizeAxis':'horizontal','units':True,'doodads':True,'encoding':'PNG from native TGA pixels'},'requires':'.SC2Map','desktopScreenshot':False},
 {'id':'cutscene','version':4,'methods':['open_module','load','seek','capture_frame','export_mp4','export_status','export_cancel'],'timelineControl':True,'timeResolutionMs':33,
  'captureSource':'original D3D9 backbuffer; no desktop screenshots',
  'video':{'format':'mp4','codec':'h264','audioIncluded':True,'audioCodec':'aac','audioSource':'owned Editor output buffers','audioOptional':True,'defaultFps':30,'maxFps':60,'requires':['ffmpeg','ffprobe']}},
]

def capabilities():return {'version':'0.14.0-rc.1','modules':MODULES,'background':True,'mouseKeyboardAutomation':False,
 'editorSelection':{'requestArgument':'editor_path','environmentVariable':'SC2_EDITOR_PATH','cliArgument':'--editor',
 'discovery':['Windows registry','Program Files environment locations','PATH'],'ambiguousInstallation':'explicit selection required',
 'supportedBuilds':['5.0.17.98310 x64'],'binarySha256Verified':True,'pathTiedToOneMachine':False},
 'ownedWorkerRendering':{'selection':['auto','legacy','vulkan'],'startupArgument':'render_backend','dependency':'DXVK 3.1.1 x64, SHA-256 pinned',
 'scope':'owned hidden Editor only','offscreenVulkan':True,'backendChangeRequiresRestart':True,'normalEditorAttachment':False}}
