#pragma once
#include <windows.h>
#include <cstdint>
#include "audio_protocol.h"
constexpr uint32_t kMagic = 0x53433247;
constexpr size_t kSourceCapacity = 16 * 1024 * 1024;
constexpr uint32_t kProtocolVersion=15;
constexpr wchar_t kMessageName[] = L"SC2.NativeGalaxyBridge.20261020.modules.v15";
constexpr wchar_t kDispatchProperty[] = L"SC2NativeBridge.OwnedThread.v15";
enum Operation : uint32_t { Inspect = 0, Generate = 1, Compile = 2, ReadSource = 3, FreshnessProbe = 4, LoadDocument = 5, CancelLoad = 6, Diagnostics=7, OpenCutscene=8, SceneInspect=9, SceneLoad=10, SceneSeek=11, SceneAdvance=12, SceneAudio=13, TerrainView=14, TerrainExport=15, SaveDocument=16, ReopenDocument=17, LoadDataModule=18, TerrainCamera=19, TerrainCameraLayer=20, TerrainCameraSelect=21, DataRead=22,DataLinks=23,DataResources=24,DataInspect=25,DataAsset=26,DataAudit=27,DataAuditFiles=28 };
constexpr size_t kDiagnosticCapacity=2*1024*1024;
struct DiagnosticCapture {uint32_t beforeBytes,afterBytes,eventBytes,eventCount,eventsComplete;char before[kDiagnosticCapacity],after[kDiagnosticCapacity],events[kDiagnosticCapacity];};
struct DocumentIo {uint32_t saveCommand,closeCommand,saved,closed,reopened,dataLoaded;uint64_t savedBytes;};
struct TerrainRequest {uint32_t size,includeUnits,includeDoodads,exported,fullMap,topDown,optionsConfirmed,filtersConfirmed,actualUnits,actualDoodads,customOptions;};
struct MapCameraReadback {uint32_t selected,valuesRead;double x,y,z,pitch,yaw,roll,distance,fov;wchar_t name[512];};
struct DataAuditRequest {uint32_t catalog,offset,limit;};
struct Block {
    uint32_t magic, version, operation, pid, tid;
    uint64_t target;
    wchar_t expectedDocument[256];
    wchar_t expectedMarker[256];
    wchar_t contextLabel[512];
    wchar_t scope[64];
    wchar_t mapPath[32768];
    wchar_t loadedTitle[2048];
    wchar_t camera[512],sceneStatus[2048];
    int64_t timeMs;
    int64_t actualTimeMs;
    uint64_t viewport;
    TerrainRequest terrain;
    AudioRequest audio;
    uint32_t sceneLoaded,cameraConfirmed,timeConfirmed;
    volatile LONG loadStage;
    uint32_t loadCommand, mapLoaded, resumeDialog;
    uint32_t contextSelected;
    volatile LONG started, completed;
    uint32_t error, exceptionCode, dllPid, dllTid, requestGuardRemoved;
    uint32_t generatorCommand, compilerCommand, commandsDispatched;
    uint32_t compileCommandReturned,diagnosticWindows,diagnosticsTruncated,moduleCommand,privateFocusUsed;
    uint32_t activationVetoes, focusVetoes, sourceBytes, codePage;
    uint32_t poisonApplied, poisonReplaced, sourceReadOnly;
    int32_t compilerErrors;
    uint64_t foregroundBefore, foregroundAfter, scriptWindow;
    uint64_t beforeTextFingerprint, afterTextFingerprint;
    wchar_t statusBefore[1024], statusAfter[1024];
    wchar_t failure[1024];
    wchar_t log[32768];
    char source[kSourceCapacity];
    DocumentIo documentIo;
    DiagnosticCapture diagnosticCapture;
    MapCameraReadback mapCamera;
    DataAuditRequest dataAudit;
};
