#include "../src/document_window.h"
#include <iostream>
#include <cstdlib>
static void Check(bool result){if(!result){std::cerr<<"Document readiness regression\n";std::exit(1);}}
int main(){
    std::wstring module;
    for(auto name:{L"Triggers",L"Terrain",L"Data",L"Import",L"AI",L"UI",L"Text",L"Overview"}){
        Check(DocumentWindow(std::wstring(name)+L" - [K:/.../Seed.SC2Map] - StarCraft II Editor",L"C:\\private\\SEED.sc2map",&module));
        Check(module==name);
    }
    Check(!DocumentWindow(L"Terrain - [K:/OtherSeed.SC2Map] - StarCraft II Editor",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Terrain - [K:/Seed.SC2Map.bak] - StarCraft II Editor",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Script Test - [Seed.SC2Map] - StarCraft II Editor",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Cutscenes - [Seed.SC2Map] - StarCraft II Editor",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Triggers - [Seed.SC2Map*] - StarCraft II Editor",L"Seed.SC2Map"));
    Check(DocumentWindow(L"Triggers - [Seed.SC2Map*] - StarCraft II Editor",L"Seed.SC2Map",nullptr,true));
    Check(DocumentWindow(L"Triggers - [K:/Seed]v2.SC2Map] - StarCraft II Editor",L"Seed]v2.SC2Map"));
    Check(!DocumentWindow(L"Triggers - [Seed.SC2Map",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Activity - StarCraft II Editor",L"Seed.SC2Map"));
    Check(!DocumentWindow(L"Triggers - [] - StarCraft II Editor",L""));
    std::cout<<"Document readiness captions: passed\n";
}
