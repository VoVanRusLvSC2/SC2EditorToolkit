#include "../src/map_export_paths.h"
#include <iostream>
int main(){
    const auto path=L"K:\\private\\map-images\\abcd1234\\NativeMap-abcd.tga";
    if(!MapDisplayMatches(L"K:/private/map-images/abcd1234/NativeMap-abcd.tga",path)||
       !MapDisplayMatches(L"K:/.../map-images/abcd1234/NativeMap-abcd.tga",path)||
       MapDisplayMatches(L"C:/.../abcd1234/NativeMap-abcd.tga",path)||
       MapDisplayMatches(L"K:/.../other/NativeMap-abcd.tga",path)||
       MapDisplayMatches(L"K:/.../abcd1234/NativeMap-other.tga",path)||
       MapDisplayMatches(L"K:/.../abcd1234/NativeMap-abcd.tga.bak",path)||
       MapDisplayMatches(L"K:/.../NativeMap-abcd.tga",L"K:\\NativeMap-abcd.tga")||
       MapDisplayMatches(L"K:/.../.../NativeMap-abcd.tga",path))return 1;
    std::cout<<"Native export destination captions: passed\n";
}
