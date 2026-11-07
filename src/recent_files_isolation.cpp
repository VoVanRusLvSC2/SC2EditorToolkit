#include "recent_files_isolation.h"
#include <winternl.h>
#include <vector>
#include "../vendor/minhook/include/MinHook.h"
#pragma comment(lib,"advapi32.lib")
#pragma comment(lib,"user32.lib")

namespace {
using OpenKey=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES);
using OpenKeyEx=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,ULONG);
using CreateKey=NTSTATUS(NTAPI*)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,ULONG,PUNICODE_STRING,ULONG,PULONG);
using QueryKey=NTSTATUS(NTAPI*)(HANDLE,int,PVOID,ULONG,PULONG);
OpenKey realOpen=nullptr;OpenKeyEx realOpenEx=nullptr;CreateKey realCreate=nullptr;QueryKey queryKey=nullptr;
void* targets[3]{};
std::wstring sourcePath,targetPath;

std::wstring KeyName(HANDLE key){
    ULONG bytes=0;queryKey(key,3,nullptr,0,&bytes);
    if(bytes<sizeof(ULONG)||bytes>131072)return {};
    std::vector<unsigned char> data(bytes);
    if(queryKey(key,3,data.data(),bytes,&bytes)<0)return {};
    auto length=*reinterpret_cast<ULONG*>(data.data());
    if(length%sizeof(wchar_t)||length>data.size()-sizeof(ULONG))return {};
    return std::wstring(reinterpret_cast<const wchar_t*>(data.data()+sizeof(ULONG)),length/sizeof(wchar_t));
}
struct Attributes {
    OBJECT_ATTRIBUTES copy{};UNICODE_STRING name{};std::wstring redirected;
    POBJECT_ATTRIBUTES value;
    explicit Attributes(POBJECT_ATTRIBUTES input):value(input){
        if(!input||!input->ObjectName||!input->ObjectName->Buffer||input->ObjectName->Length%sizeof(wchar_t))return;
        std::wstring path(input->ObjectName->Buffer,input->ObjectName->Length/sizeof(wchar_t));
        if(input->RootDirectory){
            auto root=KeyName(input->RootDirectory);if(root.empty())return;
            path=root+(path.empty()?L"":L"\\"+path);
        }
        redirected=recent_files::Redirect(path,sourcePath,targetPath);if(redirected.empty())return;
        if(redirected.size()>32766)throw std::bad_alloc();
        copy=*input;name.Length=USHORT(redirected.size()*sizeof(wchar_t));name.MaximumLength=name.Length;name.Buffer=redirected.data();
        copy.RootDirectory=nullptr;copy.ObjectName=&name;value=&copy;
    }
};
NTSTATUS NTAPI Open(PHANDLE key,ACCESS_MASK access,POBJECT_ATTRIBUTES input){
    try{Attributes a(input);return realOpen(key,access,a.value);}catch(...){return NTSTATUS(0xc0000017);}
}
NTSTATUS NTAPI OpenEx(PHANDLE key,ACCESS_MASK access,POBJECT_ATTRIBUTES input,ULONG options){
    try{Attributes a(input);return realOpenEx(key,access,a.value,options);}catch(...){return NTSTATUS(0xc0000017);}
}
NTSTATUS NTAPI Create(PHANDLE key,ACCESS_MASK access,POBJECT_ATTRIBUTES input,ULONG title,PUNICODE_STRING kind,ULONG options,PULONG disposition){
    try{Attributes a(input);return realCreate(key,access,a.value,title,kind,a.redirected.empty()?options:options|REG_OPTION_VOLATILE,disposition);}
    catch(...){return NTSTATUS(0xc0000017);}
}
void Remove(){for(auto target:targets)if(target){MH_DisableHook(target);MH_RemoveHook(target);}}
DWORD Start(const std::wstring& instance,const wchar_t* source){
    auto destination=recent_files::WorkerKey(instance);if(destination.empty())return ERROR_INVALID_PARAMETER;
    if(!sourcePath.empty())return ERROR_ALREADY_INITIALIZED;
    auto ntdll=GetModuleHandleW(L"ntdll.dll");
    queryKey=reinterpret_cast<QueryKey>(GetProcAddress(ntdll,"NtQueryKey"));
    if(!queryKey)return ERROR_PROC_NOT_FOUND;
    HKEY user=nullptr;auto error=RegOpenCurrentUser(KEY_READ,&user);if(error)return error;
    auto root=KeyName(user);RegCloseKey(user);if(root.empty())return ERROR_INVALID_HANDLE;
    sourcePath=root+L"\\"+source;targetPath=root+L"\\"+destination+L"\\Recent Files";
    HKEY privateKey=nullptr;
    error=RegCreateKeyExW(HKEY_CURRENT_USER,(destination+L"\\Recent Files").c_str(),0,nullptr,REG_OPTION_VOLATILE,KEY_ALL_ACCESS,nullptr,&privateKey,nullptr);
    if(error){sourcePath.clear();targetPath.clear();return error;}RegCloseKey(privateKey);
    auto initialized=MH_Initialize();
    if(initialized!=MH_OK&&initialized!=MH_ERROR_ALREADY_INITIALIZED){sourcePath.clear();targetPath.clear();return ERROR_DLL_INIT_FAILED;}
    const char* names[]={"NtOpenKey","NtOpenKeyEx","NtCreateKey"};
    void* callbacks[]={reinterpret_cast<void*>(Open),reinterpret_cast<void*>(OpenEx),reinterpret_cast<void*>(Create)};
    void** originals[]={reinterpret_cast<void**>(&realOpen),reinterpret_cast<void**>(&realOpenEx),reinterpret_cast<void**>(&realCreate)};
    for(int i=0;i<3;i++){
        auto address=reinterpret_cast<void*>(GetProcAddress(ntdll,names[i]));
        if(!address||MH_CreateHook(address,callbacks[i],originals[i])!=MH_OK){Remove();sourcePath.clear();targetPath.clear();return ERROR_INVALID_FUNCTION;}
        targets[i]=address;
    }
    for(auto target:targets)if(MH_EnableHook(target)!=MH_OK){Remove();sourcePath.clear();targetPath.clear();return ERROR_DLL_INIT_FAILED;}
    return ERROR_SUCCESS;
}
}
DWORD StartRecentFilesIsolation(const wchar_t* suffix){
    const std::wstring prefix=L".SC2Native-",text=suffix?suffix:L"";
    if(text.rfind(prefix,0)!=0)return ERROR_INVALID_PARAMETER;
    return Start(text.substr(prefix.size()),L"Software\\Blizzard Entertainment\\StarCraft II Editor\\Recent Files");
}
#ifdef SC2_RECENT_FILES_TESTING
DWORD StartRecentFilesIsolationForTest(const wchar_t* instance,const wchar_t* source){return Start(instance,source);}
void StopRecentFilesIsolationForTest(){Remove();sourcePath.clear();targetPath.clear();for(auto& target:targets)target=nullptr;}
std::wstring RecentFilesKeyNameForTest(HKEY key){return KeyName(key);}
#endif
