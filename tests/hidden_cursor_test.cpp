#include "../src/hidden_cursor.h"
#include <iostream>
#include <cstdlib>
static void Check(bool value){if(!value){std::cerr<<"Hidden cursor isolation failed\n";std::exit(1);}}
int main(){
    for(size_t slots:{size_t(119),size_t(134)}){
        void* table[134]{};
        auto sentinel=reinterpret_cast<void*>(uintptr_t(1));
        for(size_t i=0;i<slots;++i)table[i]=sentinel;
        HiddenCursor::Apply(table);
        for(size_t i=0;i<slots;++i)if(i<10||i>12)Check(table[i]==sentinel);
        // No real device/driver is needed or called, even for extreme values.
        // A dereference or forwarding attempt would fail on this null device.
        auto properties=reinterpret_cast<HRESULT(STDMETHODCALLTYPE*)(void*,UINT,UINT,IDirect3DSurface9*)>(table[10]);
        auto position=reinterpret_cast<void(STDMETHODCALLTYPE*)(void*,int,int,DWORD)>(table[11]);
        auto show=reinterpret_cast<BOOL(STDMETHODCALLTYPE*)(void*,BOOL)>(table[12]);
        Check(properties(nullptr,UINT_MAX,UINT_MAX,nullptr)==D3D_OK);
        position(nullptr,INT_MIN,INT_MAX,D3DCURSOR_IMMEDIATE_UPDATE);
        Check(show(nullptr,TRUE)==FALSE);Check(show(nullptr,FALSE)==FALSE);
    }
    std::cout<<"D3D9 and D3D9Ex cursor commands suppressed without driver or input calls\n";
}
