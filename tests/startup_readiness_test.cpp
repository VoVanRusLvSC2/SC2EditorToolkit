#include "../src/startup_readiness.h"
#include <cstdlib>
#include <iostream>
static void Check(bool value){if(!value){std::cerr<<"Startup dispatch grace failed\n";std::exit(1);}}
int main(){
    DispatchStartupReadiness readiness;
    Check(!readiness.Failed(true,false,false,0));
    Check(!readiness.Failed(true,false,false,14999));
    Check(!readiness.Failed(true,false,true,15000));
    Check(!readiness.Failed(true,false,false,20000));
    Check(readiness.Failed(true,false,false,35000));
    Check(!readiness.Failed(true,true,false,40000));
    Check(!readiness.Failed(true,false,false,50000));
    Check(!readiness.Failed(false,false,false,64000));
    Check(!readiness.Failed(true,false,false,65000));
    Check(readiness.Failed(true,false,false,80000));
    std::cout<<"Asynchronous dispatch-marker grace, recovery and busy-window reset passed\n";
}
