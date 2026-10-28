#include "../src/editor_identity.h"
#include "../src/bootstrap.h"
#include <iostream>
#include <cstdlib>
static void Check(bool value){if(!value){std::cerr<<"Editor identity check failed\n";std::exit(1);}}
int wmain(int argc,wchar_t** argv){
    Check(!CurrentOwnedEditorProcess());
    wchar_t image[32768]{};GetModuleFileNameW(nullptr,image,_countof(image));
    auto directory=std::filesystem::path(image).parent_path()/(L"SC2EditorIdentity-"+std::to_wstring(GetCurrentProcessId()));std::filesystem::create_directory(directory);
    auto alias=directory/L"Editor with spaces.exe",other=directory/L"SC2Editor_x64.exe";
    Check(CreateHardLinkW(alias.c_str(),image,nullptr)!=FALSE);Check(CopyFileW(image,other.c_str(),TRUE)!=FALSE);
    Check(SameEditorFile(image,alias));Check(!SameEditorFile(image,other));Check(!SupportedEditorFile(image));Check(!SupportedEditorFile(other));
    Check(!SameEditorFile(image,directory/L"missing.exe"));
    // A forged environment variable and private desktop cannot turn a foreign
    // executable into an owned Editor (including a running game process).
    Check(SetEnvironmentVariableW(L"SC2EDITOR_EXPECTED_EXE",image)!=FALSE);
    HDESK original=GetThreadDesktop(GetCurrentThreadId());
    auto name=L"SC2Native-IdentityTest-"+std::to_wstring(GetCurrentProcessId());
    HDESK isolated=CreateDesktopW(name.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);
    Check(isolated&&SetThreadDesktop(isolated));Check(!CurrentOwnedEditorProcess());
    if(argc>=3){
        auto library=LoadLibraryExW(argv[2],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        Check(library!=nullptr);
        auto initialize=reinterpret_cast<DWORD(WINAPI*)(void*)>(GetProcAddress(library,"BootstrapInit"));
        Check(initialize!=nullptr);BootstrapConfig config{};
        Check(initialize(&config)==ERROR_ACCESS_DENIED&&config.error==ERROR_ACCESS_DENIED&&config.patches==0);
        Check(FreeLibrary(library)!=FALSE);
    }
    Check(SetThreadDesktop(original)!=FALSE);Check(CloseDesktop(isolated)!=FALSE);
    Check(SetEnvironmentVariableW(L"SC2EDITOR_EXPECTED_EXE",nullptr)!=FALSE);
    if(argc>=2)Check(SupportedEditorFile(argv[1]));
    std::filesystem::remove(alias);std::filesystem::remove(other);std::filesystem::remove(directory);
    std::cout<<"Editor file identity, alias handling and unsupported-executable rejection passed\n";
}
