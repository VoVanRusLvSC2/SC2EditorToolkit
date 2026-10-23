#include "../src/editor_identity.h"
#include <iostream>
#include <cstdlib>
static void Check(bool value){if(!value){std::cerr<<"Editor identity check failed\n";std::exit(1);}}
int wmain(int argc,wchar_t** argv){
    wchar_t image[32768]{};GetModuleFileNameW(nullptr,image,_countof(image));
    auto directory=std::filesystem::path(image).parent_path()/(L"SC2EditorIdentity-"+std::to_wstring(GetCurrentProcessId()));std::filesystem::create_directory(directory);
    auto alias=directory/L"Editor with spaces.exe",other=directory/L"SC2Editor_x64.exe";
    Check(CreateHardLinkW(alias.c_str(),image,nullptr)!=FALSE);Check(CopyFileW(image,other.c_str(),TRUE)!=FALSE);
    Check(SameEditorFile(image,alias));Check(!SameEditorFile(image,other));Check(!SupportedEditorFile(image));Check(!SupportedEditorFile(other));
    Check(!SameEditorFile(image,directory/L"missing.exe"));
    if(argc==2)Check(SupportedEditorFile(argv[1]));
    std::filesystem::remove(alias);std::filesystem::remove(other);std::filesystem::remove(directory);
    std::cout<<"Editor file identity, alias handling and unsupported-executable rejection passed\n";
}
