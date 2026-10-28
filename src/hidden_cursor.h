#pragma once
#include <d3d9.h>

// The render thread lives on the input desktop. Never forward cursor commands
// from the private Editor to the driver: they could move or replace the user's
// cursor even though the Editor window itself is invisible. This policy is
// applied only to devices created and wrapped inside this owned process.
namespace HiddenCursor {
inline HRESULT STDMETHODCALLTYPE SetProperties(void*,UINT,UINT,IDirect3DSurface9*){
    return D3D_OK;
}
inline void STDMETHODCALLTYPE SetPosition(void*,int,int,DWORD){}
inline BOOL STDMETHODCALLTYPE Show(void*,BOOL){return FALSE;}
inline void Apply(void** table){
    // IDirect3DDevice9 and IDirect3DDevice9Ex share these three ABI slots.
    table[10]=reinterpret_cast<void*>(SetProperties);
    table[11]=reinterpret_cast<void*>(SetPosition);
    table[12]=reinterpret_cast<void*>(Show);
}
}
