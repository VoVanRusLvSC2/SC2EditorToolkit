#include "editor_identity.h"
#include <windows.h>
#include <filesystem>
#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <sstream>
#include <tlhelp32.h>
#include "bootstrap.h"
#include "document_window.h"
#include "protocol.h"
#include "startup_readiness.h"
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"ole32.lib")
namespace fs=std::filesystem;
static std::string U(const std::wstring& w){int n=WideCharToMultiByte(CP_UTF8,0,w.data(),int(w.size()),nullptr,0,nullptr,nullptr);std::string s(n,0);WideCharToMultiByte(CP_UTF8,0,w.data(),int(w.size()),s.data(),n,nullptr,nullptr);return s;}
static std::string Q(const std::wstring& w){std::string s="\"";for(unsigned char c:U(w)){if(c=='"'||c=='\\'){s+='\\';s+=char(c);}else if(c=='\n')s+="\\n";else if(c=='\r')s+="\\r";else if(c=='\t')s+="\\t";else if(c>=32)s+=char(c);}return s+'"';}
static std::wstring Text(HWND w){wchar_t s[2048]{};if(!(GetWindowLongPtrW(w,GWL_STYLE)&WS_CHILD)){GetWindowTextW(w,s,2048);return s;}DWORD_PTR r=0;SendMessageTimeoutW(w,WM_GETTEXT,2048,reinterpret_cast<LPARAM>(s),SMTO_ABORTIFHUNG|SMTO_BLOCK,200,&r);return s;}
static std::wstring Class(HWND w){wchar_t s[256]{};GetClassNameW(w,s,256);return s;}
static std::wstring DesktopName(HDESK d){wchar_t s[256]{};DWORD n=0;GetUserObjectInformationW(d,UOI_NAME,s,sizeof(s),&n);return s;}
static DWORD childPid;
static std::vector<HWND> windows;
static BOOL CALLBACK Enum(HWND w,LPARAM){DWORD pid=0;GetWindowThreadProcessId(w,&pid);if(pid==childPid)windows.push_back(w);return TRUE;}
static BOOL CALLBACK Children(HWND w,LPARAM p){auto v=reinterpret_cast<std::vector<HWND>*>(p);v->push_back(w);return TRUE;}
static int E(const char* message){std::cerr<<message<<" Win32="<<GetLastError()<<"\n";return 2;}
struct BootstrapFailure {
    std::wstring phase;DWORD win32Error=0,remoteExitCode=0,bootstrapError=0;
    bool Set(const wchar_t* stage,DWORD error,DWORD remote=0,DWORD native=0){phase=stage;win32Error=error;remoteExitCode=remote;bootstrapError=native;return false;}
    std::string Json()const{return "{\"phase\":"+Q(phase)+",\"win32Error\":"+std::to_string(win32Error)+",\"remoteExitCode\":"+std::to_string(remoteExitCode)+",\"bootstrapError\":"+std::to_string(bootstrapError)+"}";}
};
static bool InjectBootstrap(PROCESS_INFORMATION& process,const fs::path& dllPath,const fs::path& logPath,DWORD& patches,const std::wstring& instanceId,BootstrapFailure& failure){
    HMODULE local=LoadLibraryExW(dllPath.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!local)return failure.Set(L"load-local-bootstrap",GetLastError());
    auto exported=GetProcAddress(local,"BootstrapInit");
    if(!exported){auto error=GetLastError();FreeLibrary(local);return failure.Set(L"resolve-bootstrap-export",error);}
    uintptr_t rva=reinterpret_cast<uintptr_t>(exported)-reinterpret_cast<uintptr_t>(local);FreeLibrary(local);
    auto text=dllPath.wstring();SIZE_T bytes=(text.size()+1)*sizeof(wchar_t),written=0;
    void* remote=VirtualAllocEx(process.hProcess,nullptr,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!remote)return failure.Set(L"allocate-bootstrap-path",GetLastError());
    if(!WriteProcessMemory(process.hProcess,remote,text.c_str(),bytes,&written)||written!=bytes)return failure.Set(L"write-bootstrap-path",GetLastError());
    auto load=reinterpret_cast<LPTHREAD_START_ROUTINE>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW"));
    HANDLE thread=CreateRemoteThread(process.hProcess,nullptr,0,load,remote,0,nullptr);if(!thread)return failure.Set(L"start-bootstrap-loader",GetLastError());
    DWORD wait=WaitForSingleObject(thread,30000),result=0;
    if(wait!=WAIT_OBJECT_0){auto error=wait==WAIT_TIMEOUT?ERROR_TIMEOUT:GetLastError();CloseHandle(thread);return failure.Set(L"wait-bootstrap-loader",error);}
    if(!GetExitCodeThread(thread,&result)){auto error=GetLastError();CloseHandle(thread);return failure.Set(L"read-loader-result",error);}CloseHandle(thread);
    VirtualFreeEx(process.hProcess,remote,0,MEM_RELEASE);
    uintptr_t base=0;
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,process.dwProcessId);
    if(snapshot==INVALID_HANDLE_VALUE)return failure.Set(L"enumerate-bootstrap-module",GetLastError());MODULEENTRY32W module{};module.dwSize=sizeof(module);
    if(Module32FirstW(snapshot,&module))do{if(!_wcsicmp(module.szExePath,dllPath.c_str())){base=reinterpret_cast<uintptr_t>(module.modBaseAddr);break;}}while(Module32NextW(snapshot,&module));CloseHandle(snapshot);
    if(!base)return failure.Set(L"find-loaded-bootstrap",ERROR_DLL_INIT_FAILED,result);
    BootstrapConfig config{};config.primaryThreadId=process.dwThreadId;wcsncpy_s(config.suffix,(L".SC2Native-"+instanceId).c_str(),_TRUNCATE);wcsncpy_s(config.logPath,logPath.c_str(),_TRUNCATE);
    remote=VirtualAllocEx(process.hProcess,nullptr,sizeof(config),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!remote)return failure.Set(L"allocate-bootstrap-config",GetLastError());
    if(!WriteProcessMemory(process.hProcess,remote,&config,sizeof(config),&written)||written!=sizeof(config))return failure.Set(L"write-bootstrap-config",GetLastError());
    thread=CreateRemoteThread(process.hProcess,nullptr,0,reinterpret_cast<LPTHREAD_START_ROUTINE>(base+rva),remote,0,nullptr);if(!thread)return failure.Set(L"start-bootstrap-init",GetLastError());
    wait=WaitForSingleObject(thread,30000);
    if(wait!=WAIT_OBJECT_0){auto error=wait==WAIT_TIMEOUT?ERROR_TIMEOUT:GetLastError();CloseHandle(thread);return failure.Set(L"wait-bootstrap-init",error);}
    if(!GetExitCodeThread(thread,&result)){auto error=GetLastError();CloseHandle(thread);return failure.Set(L"read-bootstrap-result",error);}CloseHandle(thread);
    if(!ReadProcessMemory(process.hProcess,remote,&config,sizeof(config),&written)||written!=sizeof(config))return failure.Set(L"read-bootstrap-config",GetLastError());
    VirtualFreeEx(process.hProcess,remote,0,MEM_RELEASE);patches=config.patches;
    if(result||config.error||!patches)return failure.Set(L"initialize-bootstrap",ERROR_DLL_INIT_FAILED,result,config.error);
    return true;
}
int wmain(int argc,wchar_t** argv){
    fs::path out,document;std::wstring editor,jobName,startupModule=L"default",renderBackend=L"legacy";int timeout=90;
    for(int i=1;i<argc;i++){if(i+1>=argc)return E("Missing argument");std::wstring k=argv[i],v=argv[++i];if(k==L"--out")out=v;else if(k==L"--editor")editor=v;else if(k==L"--document")document=v;else if(k==L"--timeout")timeout=std::stoi(v);else if(k==L"--job-name")jobName=v;else if(k==L"--module")startupModule=v;else if(k==L"--render-backend")renderBackend=v;else return E("Unknown argument");}
    if(startupModule!=L"default"&&startupModule!=L"triggers"&&startupModule!=L"terrain")return E("Unsupported startup module");
    if(renderBackend!=L"legacy"&&renderBackend!=L"vulkan")return E("Render backend must be legacy or vulkan");
    if(!SetEnvironmentVariableW(L"SC2EDITOR_RENDER_BACKEND",renderBackend.c_str()))return E("Cannot configure owned render backend");
    if(!jobName.empty()){
        if(jobName.rfind(L"Local\\SC2NativeApi-",0)!=0)return E("Invalid API job name");
        HANDLE job=OpenJobObjectW(JOB_OBJECT_ASSIGN_PROCESS,FALSE,jobName.c_str());
        if(!job||!AssignProcessToJobObject(job,GetCurrentProcess()))return E("Cannot bind hidden host to API lifetime");
        CloseHandle(job);
    }
    if(out.empty()||fs::exists(out))return E("Fresh --out required");fs::create_directories(out);
    if(editor.empty()||!SupportedEditorFile(editor))return E("Explicit supported original --editor required (5.0.17.98310 x64)");
    if(!SetEnvironmentVariableW(L"SC2EDITOR_EXPECTED_EXE",editor.c_str()))return E("Cannot bind selected Editor identity");
    SetEnvironmentVariableW(L"SC2EDITOR_ATTACH_LOG",(out/L"dispatch.log").c_str());
    HDESK input=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);if(!input)return E("Cannot identify input desktop");auto inputBefore=DesktopName(input);CloseDesktop(input);
    HDESK original=GetThreadDesktop(GetCurrentThreadId());GUID id{};CoCreateGuid(&id);wchar_t guid[64]{};StringFromGUID2(id,guid,64);
    std::wstring desktop=L"SC2Native-"+std::wstring(guid),fullDesktop=L"WinSta0\\"+desktop;
    HDESK isolated=CreateDesktopW(desktop.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);if(!isolated)return E("Cannot create private desktop");
    if(!SetThreadDesktop(isolated))return E("Cannot associate host with private desktop");
    fs::path temp=out/L"private-temp";fs::create_directories(temp);SetEnvironmentVariableW(L"TEMP",temp.c_str());SetEnvironmentVariableW(L"TMP",temp.c_str());
    std::wstring command=L"\""+editor+L"\" -product SC2";if(!document.empty())command+=L" -loadfile \""+document.wstring()+L"\"";
    if(startupModule==L"triggers")command+=L" -modtrigger";
    if(startupModule==L"terrain")command+=L" -modterrain";
    STARTUPINFOW si{};si.cb=sizeof(si);si.lpDesktop=fullDesktop.data();si.dwFlags=STARTF_USESHOWWINDOW;si.wShowWindow=SW_SHOWNOACTIVATE;
    PROCESS_INFORMATION process{};
    if(!CreateProcessW(editor.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_UNICODE_ENVIRONMENT|CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,fs::path(editor).parent_path().c_str(),&si,&process))return E("Original Editor creation failed");
    childPid=process.dwProcessId;
    FILETIME creation{},exit{},kernel{},user{};GetProcessTimes(process.hProcess,&creation,&exit,&kernel,&user);
    auto identity="\"pid\":"+std::to_string(childPid)+",\"createTimeFiletime\":"+std::to_string((uint64_t(creation.dwHighDateTime)<<32)|creation.dwLowDateTime)+",\"instanceId\":"+Q(guid);
    {std::ofstream initial(out/"state.json");initial<<"{\"status\":\"BOOTSTRAPPING\","<<identity<<"}";}
    wchar_t self[32768]{};GetModuleFileNameW(nullptr,self,32768);auto bootstrap=fs::path(self).parent_path()/L"SC2StartupBootstrap.dll";DWORD patches=0;
    BootstrapFailure bootstrapFailure;
    if(!InjectBootstrap(process,bootstrap,out/L"bootstrap.log",patches,guid,bootstrapFailure)){
        {std::ofstream report(out/"state.json");report<<"{\"status\":\"HIDDEN_BOOTSTRAP_FAILED\","<<identity<<",\"bootstrapFailure\":"<<bootstrapFailure.Json()<<"}";}
        TerminateProcess(process.hProcess,42);WaitForSingleObject(process.hProcess,10000);CloseHandle(process.hThread);CloseHandle(process.hProcess);
        SetThreadDesktop(original);CloseDesktop(isolated);
        std::cerr<<"Private worker bootstrap failed phase="<<U(bootstrapFailure.phase)<<" Win32="<<bootstrapFailure.win32Error<<" remote="<<bootstrapFailure.remoteExitCode<<" bootstrap="<<bootstrapFailure.bootstrapError<<"\n";return 2;
    }
    ResumeThread(process.hThread);CloseHandle(process.hThread);
    std::string state;std::wstring currentDocument,readyModule;DWORD exitCode=STILL_ACTIVE;ULONGLONG deadline=GetTickCount64()+ULONGLONG(timeout)*1000;
    bool ready=false,singleton=false,graphics=false,busy=false,dispatchReady=false;
    DispatchStartupReadiness dispatchStartup;
    while(GetTickCount64()<deadline){
        windows.clear();EnumWindows(Enum,0);ready=false;singleton=false;graphics=false;busy=false;dispatchReady=false;
        std::ostringstream snapshots;snapshots<<"[";bool comma=false;
        for(HWND w:windows){
            auto title=Text(w);if(title.empty())continue;
            if(title==L"Activity - StarCraft II Editor"&&IsWindowVisible(w))busy=true;if(comma)snapshots<<",";comma=true;
            snapshots<<"{\"hwnd\":"<<reinterpret_cast<uint64_t>(w)<<",\"title\":"<<Q(title)<<",\"enabled\":"<<(IsWindowEnabled(w)?"true":"false")<<",\"texts\":[";
            std::vector<HWND> children;EnumChildWindows(w,Children,reinterpret_cast<LPARAM>(&children));bool sep=false;
            for(HWND c:children)if(Class(c)==L"Static"||Class(c)==L"Button"){
                auto s=Text(c);if(s.empty())continue;if(sep)snapshots<<",";sep=true;snapshots<<Q(s);
                if(s.find(L"Another instance of the editor")!=s.npos)singleton=true;
                if(s.find(L"Graphics device is not available")!=s.npos||s.find(L"0x88760868")!=s.npos)graphics=true;
            }snapshots<<"]}";
            if(IsWindowVisible(w)&&IsWindowEnabled(w)&&DocumentWindow(title,document.wstring(),&readyModule)){
                ready=true;currentDocument=document.filename().wstring();
                dispatchReady=reinterpret_cast<uintptr_t>(GetPropW(w,kDispatchProperty))==kProtocolVersion;
            }
        }snapshots<<"]";
        GetExitCodeProcess(process.hProcess,&exitCode);
        bool dispatcherFailed=dispatchStartup.Failed(ready,busy,dispatchReady,GetTickCount64());
        ready=ready&&dispatchReady&&!busy&&!singleton&&!graphics&&exitCode==STILL_ACTIVE;
        auto status=ready?L"HIDDEN_EDITOR_READY":dispatcherFailed?L"NATIVE_DISPATCH_STARTUP_FAILED":singleton?L"BLOCKED_BY_EDITOR_SINGLETON":graphics?L"GRAPHICS_STARTUP_FAILED":exitCode!=STILL_ACTIVE?L"EDITOR_EXITED":L"STARTING";
        std::ostringstream r;r<<"{\"status\":"<<Q(status)<<",\"pid\":"<<childPid<<",\"createTimeFiletime\":"<<((uint64_t(creation.dwHighDateTime)<<32)|creation.dwLowDateTime)<<",\"desktop\":"<<Q(desktop)<<",\"inputDesktopBefore\":"<<Q(inputBefore)<<",\"currentDocument\":"<<Q(currentDocument)<<",\"exitCode\":"<<exitCode<<",\"desktopSwitched\":false,\"inputInjectionUsed\":false,\"windows\":"<<snapshots.str()<<"}";
        state=r.str();state.insert(state.size()-1,",\"instanceId\":"+Q(guid)+",\"renderBackend\":"+Q(renderBackend)+",\"readyModule\":"+Q(ready?readyModule:L"")+",\"dispatchReady\":"+std::string(dispatchReady?"true":"false")+",\"nativeProtocolVersion\":"+std::to_string(kProtocolVersion));std::ofstream file(out/"state.json",std::ios::binary);file<<state;file.close();
        if(ready||dispatcherFailed||singleton||graphics||exitCode!=STILL_ACTIVE)break;
        WaitForSingleObject(process.hProcess,500);
    }
    input=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);auto inputAfter=DesktopName(input);if(input)CloseDesktop(input);
    // Lock/unlock/screensavers are external observations. This host never
    // switches the input desktop; a ready private Editor remains ready.
    state.insert(state.size()-1,",\"inputDesktopAfter\":"+Q(inputAfter)+",\"inputDesktopChangedDuringStartup\":"+std::string(inputBefore!=inputAfter?"true":"false"));
    {std::ofstream file(out/"state.json",std::ios::binary);file<<state;}
    if(!ready&&exitCode==STILL_ACTIVE){TerminateProcess(process.hProcess,41);WaitForSingleObject(process.hProcess,10000);}
    std::cout<<state<<"\n";CloseHandle(process.hProcess);SetThreadDesktop(original);CloseDesktop(isolated);
    return ready?0:2;
}
