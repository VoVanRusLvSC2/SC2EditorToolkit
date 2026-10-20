#include "bootstrap.h"
#include <winternl.h>
#include <string>
#include <cstring>
#include "graphics_bridge.h"
#include "audio_protocol.h"
#pragma comment(lib,"user32.lib")
static std::wstring suffix,logPath;
static SRWLOCK logLock=SRWLOCK_INIT;
static const wchar_t* names[]={L"StarCraft II Editor Application (Global)",L"StarCraft II Editor Application",L"StarCraft II Editor Shared Memory",L"StarCraft II Editor File",L"StarCraft II Game Shared Memory"};
static void Log(const char* api,const std::wstring& name,const std::wstring& renamed,NTSTATUS status){
    if(name.empty())return;wchar_t line[4096]{};swprintf_s(line,L"%S status=%08lx name=%s -> %s\r\n",api,static_cast<ULONG>(status),name.c_str(),renamed.c_str());
    char utf8[16384]{};int n=WideCharToMultiByte(CP_UTF8,0,line,-1,utf8,sizeof(utf8),nullptr,nullptr);if(n<=1)return;
    AcquireSRWLockExclusive(&logLock);HANDLE file=CreateFileW(logPath.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file!=INVALID_HANDLE_VALUE){DWORD count;WriteFile(file,utf8,n-1,&count,nullptr);CloseHandle(file);}ReleaseSRWLockExclusive(&logLock);
}
struct ObjectName {
    OBJECT_ATTRIBUTES attr{};UNICODE_STRING value{};std::wstring original,changed;POBJECT_ATTRIBUTES ptr=nullptr;
    explicit ObjectName(POBJECT_ATTRIBUTES p):ptr(p){
        if(!p||!p->ObjectName||!p->ObjectName->Buffer)return;
        original.assign(p->ObjectName->Buffer,p->ObjectName->Length/sizeof(wchar_t));auto pos=original.find_last_of(L'\\');auto leaf=original.substr(pos==original.npos?0:pos+1);
        for(auto allowed:names)if(leaf==allowed){changed=original+suffix;break;}
        if(changed.empty())return;attr=*p;value.Length=static_cast<USHORT>(changed.size()*sizeof(wchar_t));value.MaximumLength=value.Length;value.Buffer=changed.data();attr.ObjectName=&value;ptr=&attr;
    }
};
using FnCreateEvent=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,int,BOOLEAN);
using FnCreateMutant=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,BOOLEAN);
using FnCreateSection=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,PLARGE_INTEGER,ULONG,ULONG,HANDLE);
using FnCreateSemaphore=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,LONG,LONG);
using FnOpenObject=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES);
static FnCreateEvent realEvent;static FnCreateMutant realMutant;static FnCreateSection realSection;static FnCreateSemaphore realSemaphore;
static FnOpenObject openEvent,openMutant,openSection,openSemaphore;
static NTSTATUS NTAPI Event(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p,int type,BOOLEAN state){ObjectName o(p);auto s=realEvent(h,a,o.ptr,type,state);Log("NtCreateEvent",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI Mutant(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p,BOOLEAN owner){ObjectName o(p);auto s=realMutant(h,a,o.ptr,owner);Log("NtCreateMutant",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI Section(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p,PLARGE_INTEGER size,ULONG protect,ULONG allocation,HANDLE file){ObjectName o(p);auto s=realSection(h,a,o.ptr,size,protect,allocation,file);Log("NtCreateSection",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI Semaphore(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p,LONG count,LONG maximum){ObjectName o(p);auto s=realSemaphore(h,a,o.ptr,count,maximum);Log("NtCreateSemaphore",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI OpenE(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p){ObjectName o(p);auto s=openEvent(h,a,o.ptr);Log("NtOpenEvent",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI OpenM(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p){ObjectName o(p);auto s=openMutant(h,a,o.ptr);Log("NtOpenMutant",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI OpenS(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p){ObjectName o(p);auto s=openSection(h,a,o.ptr);Log("NtOpenSection",o.original,o.changed,s);return s;}
static NTSTATUS NTAPI HookSemaphoreOpen(PHANDLE h,ACCESS_MASK a,POBJECT_ATTRIBUTES p){ObjectName o(p);auto s=openSemaphore(h,a,o.ptr);Log("NtOpenSemaphore",o.original,o.changed,s);return s;}
struct Patch {const char* name;void* hook;};
static DWORD PatchImports(HMODULE module,Patch* patches,size_t count){
    if(!module)return 0;auto base=reinterpret_cast<unsigned char*>(module);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);auto nt=reinterpret_cast<IMAGE_NT_HEADERS*>(base+dos->e_lfanew);
    auto dir=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];if(!dir.VirtualAddress)return 0;auto descriptor=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base+dir.VirtualAddress);DWORD done=0;
    for(int d=0;d<256&&descriptor[d].Name;d++){
        if(_stricmp(reinterpret_cast<const char*>(base+descriptor[d].Name),"ntdll.dll")||!descriptor[d].OriginalFirstThunk)continue;
        auto lookup=reinterpret_cast<IMAGE_THUNK_DATA*>(base+descriptor[d].OriginalFirstThunk);auto bound=reinterpret_cast<IMAGE_THUNK_DATA*>(base+descriptor[d].FirstThunk);
        for(int i=0;i<8192&&lookup[i].u1.AddressOfData;i++){
            if(IMAGE_SNAP_BY_ORDINAL(lookup[i].u1.Ordinal))continue;auto entry=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base+lookup[i].u1.AddressOfData);
            for(size_t p=0;p<count;p++)if(!strcmp(entry->Name,patches[p].name)){
                DWORD old=0;if(!VirtualProtect(&bound[i].u1.Function,sizeof(ULONG_PTR),PAGE_READWRITE,&old))continue;
                InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&bound[i].u1.Function),patches[p].hook);DWORD ignored;VirtualProtect(&bound[i].u1.Function,sizeof(ULONG_PTR),old,&ignored);++done;
            }
        }
    }return done;
}
extern "C" __declspec(dllexport) DWORD WINAPI BootstrapInit(void* raw){
    auto config=static_cast<BootstrapConfig*>(raw);if(!config)return 1;suffix=config->suffix;logPath=config->logPath;
    auto n=GetModuleHandleW(L"ntdll.dll");realEvent=reinterpret_cast<FnCreateEvent>(GetProcAddress(n,"NtCreateEvent"));realMutant=reinterpret_cast<FnCreateMutant>(GetProcAddress(n,"NtCreateMutant"));
    realSection=reinterpret_cast<FnCreateSection>(GetProcAddress(n,"NtCreateSection"));realSemaphore=reinterpret_cast<FnCreateSemaphore>(GetProcAddress(n,"NtCreateSemaphore"));
    openEvent=reinterpret_cast<FnOpenObject>(GetProcAddress(n,"NtOpenEvent"));openMutant=reinterpret_cast<FnOpenObject>(GetProcAddress(n,"NtOpenMutant"));openSection=reinterpret_cast<FnOpenObject>(GetProcAddress(n,"NtOpenSection"));openSemaphore=reinterpret_cast<FnOpenObject>(GetProcAddress(n,"NtOpenSemaphore"));
    if(!realEvent||!realMutant||!realSection||!realSemaphore||!openEvent||!openMutant||!openSection||!openSemaphore){config->error=2;return 2;}
    Patch patches[]={{"NtCreateEvent",reinterpret_cast<void*>(Event)},{"NtCreateMutant",reinterpret_cast<void*>(Mutant)},{"NtCreateSection",reinterpret_cast<void*>(Section)},{"NtCreateSemaphore",reinterpret_cast<void*>(Semaphore)},
                     {"NtOpenEvent",reinterpret_cast<void*>(OpenE)},{"NtOpenMutant",reinterpret_cast<void*>(OpenM)},{"NtOpenSection",reinterpret_cast<void*>(OpenS)},{"NtOpenSemaphore",reinterpret_cast<void*>(HookSemaphoreOpen)}};
    config->patches=PatchImports(GetModuleHandleW(L"kernelbase.dll"),patches,_countof(patches))+PatchImports(GetModuleHandleW(L"kernel32.dll"),patches,_countof(patches));
    std::wstring graphicsPath=logPath+L".graphics.log";DWORD graphicsError=StartHiddenGraphics(graphicsPath.c_str());if(graphicsError){config->error=100+graphicsError;return config->error;}
    DWORD audioError=StartHiddenAudio();if(audioError)Log("audio-bootstrap",L"owned audio tap",L"unavailable; non-audio operations remain usable",audioError);
    return config->patches?0:3;
}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID){return TRUE;}
