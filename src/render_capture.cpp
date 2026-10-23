#include "editor_identity.h"
#include <windows.h>
#include <tlhelp32.h>
#include <filesystem>
#include <iostream>
#include <string>
#include "capture_protocol.h"
namespace fs=std::filesystem;
int wmain(int argc,wchar_t** argv){
    DWORD pid=0;uint64_t targetWindow=0;fs::path out,editor;
    for(int i=1;i<argc;i++){if(i+1>=argc)return 2;std::wstring key=argv[i],value=argv[++i];if(key==L"--pid")pid=std::stoul(value);else if(key==L"--out")out=value;else if(key==L"--editor")editor=value;else if(key==L"--viewport")targetWindow=std::stoull(value);else return 2;}
    if(!pid||out.empty()||!out.is_absolute()||fs::exists(out))return 2;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_CREATE_THREAD|PROCESS_VM_READ|PROCESS_VM_WRITE|PROCESS_VM_OPERATION,FALSE,pid);
    if(!process)return 2;wchar_t image[32768]{};DWORD length=32768;
    if(editor.empty())editor=OwnedEditorPath();
    if(!QueryFullProcessImageNameW(process,0,image,&length)||editor.empty()||!SupportedEditorFile(editor)||!SameEditorFile(image,editor)){CloseHandle(process);return 2;}
    uintptr_t base=0;fs::path dll;
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);
    MODULEENTRY32W module{};module.dwSize=sizeof(module);
    if(snapshot!=INVALID_HANDLE_VALUE){if(Module32FirstW(snapshot,&module))do{if(!_wcsicmp(module.szModule,L"SC2StartupBootstrap.dll")){base=reinterpret_cast<uintptr_t>(module.modBaseAddr);dll=module.szExePath;break;}}while(Module32NextW(snapshot,&module));CloseHandle(snapshot);}
    if(!base){std::cerr<<"Owned worker bootstrap missing; no injection attempted\n";CloseHandle(process);return 2;}
    HMODULE local=LoadLibraryW(dll.c_str());if(!local){CloseHandle(process);return 2;}
    auto entry=GetProcAddress(local,"BootstrapCapture");if(!entry){FreeLibrary(local);CloseHandle(process);return 2;}
    auto rva=reinterpret_cast<uintptr_t>(entry)-reinterpret_cast<uintptr_t>(local);FreeLibrary(local);
    CaptureRequest request;request.targetWindow=targetWindow;wcsncpy_s(request.output,out.c_str(),_TRUNCATE);
    void* memory=VirtualAllocEx(process,nullptr,sizeof(request),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);SIZE_T transferred=0;
    if(!memory||!WriteProcessMemory(process,memory,&request,sizeof(request),&transferred)){CloseHandle(process);return 2;}
    HANDLE thread=CreateRemoteThread(process,nullptr,0,reinterpret_cast<LPTHREAD_START_ROUTINE>(base+rva),memory,0,nullptr);
    if(!thread){VirtualFreeEx(process,memory,0,MEM_RELEASE);CloseHandle(process);return 2;}
    // Never free the POD while its owner may still be using it.
    WaitForSingleObject(thread,INFINITE);DWORD code=1;GetExitCodeThread(thread,&code);
    bool read=ReadProcessMemory(process,memory,&request,sizeof(request),&transferred)!=0;
    VirtualFreeEx(process,memory,0,MEM_RELEASE);CloseHandle(thread);CloseHandle(process);
    std::cout<<"{\"status\":\""<<(!code&&read?"NATIVE_FRAME_CAPTURED":"CAPTURE_FAILED")<<"\",\"hresult\":"<<static_cast<unsigned long>(request.result)<<",\"width\":"<<request.width<<",\"height\":"<<request.height<<",\"sequence\":"<<request.sequence<<",\"sourceWindow\":"<<request.sourceWindow<<",\"sourceKind\":"<<request.sourceKind<<",\"nonBlackPixels\":"<<request.nonBlackPixels<<",\"luminanceBins\":"<<request.luminanceBins<<",\"luminanceMin\":"<<request.luminanceMin<<",\"luminanceMax\":"<<request.luminanceMax<<",\"emptyFrame\":"<<(request.nonBlackPixels?"false":"true")<<",\"desktopPixelsRead\":false}\n";
    return !code&&read&&SUCCEEDED(request.result)?0:2;
}
