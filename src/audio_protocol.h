#pragma once
#include <windows.h>
#include <cstdint>
struct AudioRequest {
    uint32_t operation=0,error=0,ready=0,version=0,rate=0,channels=0;
    uint64_t frames=0,nonzero=0,bufferCalls=0,submitCalls=0,renderedFrames=0,idleFrames=0;
    int64_t firstQpc=0,lastQpc=0,frequency=0,playQpc=0,sceneStartQpc=0;
    double peak=0,sumSquares=0;
    wchar_t path[32768]{};
};
DWORD StartHiddenAudio();
