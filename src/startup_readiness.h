#pragma once
#include <cstdint>

// A document window can precede the bridge's dispatch marker. Require a
// continuous grace interval before declaring that asynchronous startup failed.
struct DispatchStartupReadiness {
    bool pending=false;
    uint64_t since=0;
    bool Failed(bool documentReady,bool busy,bool dispatchReady,uint64_t now){
        if(!documentReady||busy||dispatchReady){pending=false;return false;}
        if(!pending){pending=true;since=now;}
        return now-since>=15000;
    }
};
