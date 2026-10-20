#pragma once
#include <windows.h>
#include <cstdint>
#include "audio_protocol.h"
constexpr uint32_t kMagic = 0x53433247;
constexpr size_t kSourceCapacity = 16 * 1024 * 1024;
constexpr wchar_t kMessageName[] = L"SC2.NativeGalaxyBridge.20261020.modules.v7";
enum Operation : uint32_t { Inspect = 0, Generate = 1, Compile = 2, ReadSource = 3, FreshnessProbe = 4, LoadDocument = 5, CancelLoad = 6, Diagnostics=7, OpenCutscene=8, SceneInspect=9, SceneLoad=10, SceneSeek=11, SceneAdvance=12, SceneAudio=13 };
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
    AudioRequest audio;
    uint32_t sceneLoaded,cameraConfirmed,timeConfirmed;
    volatile LONG loadStage;
    uint32_t loadCommand, mapLoaded, resumeDialog;
    uint32_t contextSelected;
    volatile LONG started, completed;
    uint32_t error, exceptionCode, dllPid, dllTid;
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
};
