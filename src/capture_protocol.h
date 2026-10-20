#pragma once
#include <windows.h>
#include <cstdint>
struct CaptureRequest {
    uint32_t size=sizeof(CaptureRequest),version=2;
    uint64_t targetWindow=0,sourceWindow=0;
    wchar_t output[32768]{};
    HRESULT result=E_PENDING;
    uint32_t width=0,height=0,format=0,sourceKind=0;
    uint32_t nonBlackPixels=0;
    uint32_t luminanceBins=0,luminanceMin=255,luminanceMax=0;
    uint64_t sequence=0;
};
