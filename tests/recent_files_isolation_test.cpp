#include "../src/recent_files_isolation.h"
#include <iostream>
#include <cstdlib>
#pragma comment(lib,"ole32.lib")
#pragma comment(lib,"advapi32.lib")
static void Check(bool value){if(!value){std::cerr<<"Recent Files isolation failed: "<<GetLastError()<<"\n";std::exit(1);}}
int wmain(){
    Check(recent_files::Redirect(L"Source",L"Source",L"Target")==L"Target");
    Check(recent_files::Redirect(L"source\\child",L"SOURCE",L"Target")==L"Target\\child");
    Check(recent_files::Redirect(L"Source Backup",L"Source",L"Target").empty());
    Check(recent_files::WorkerKey(L"..\\user").empty());
    GUID id{};Check(SUCCEEDED(CoCreateGuid(&id)));wchar_t text[64]{};StringFromGUID2(id,text,64);
    auto worker=recent_files::WorkerKey(text),fixture=L"Software\\SC2EditorToolkit\\Tests\\"+std::wstring(text);
    auto source=fixture+L"\\Recent Files";
    HKEY parent=nullptr,original=nullptr;DWORD sentinel=17;
    Check(RegCreateKeyExW(HKEY_CURRENT_USER,source.c_str(),0,nullptr,REG_OPTION_VOLATILE,KEY_ALL_ACCESS,nullptr,&original,nullptr)==ERROR_SUCCESS);
    Check(RegSetValueExW(original,L"sentinel",0,REG_DWORD,reinterpret_cast<BYTE*>(&sentinel),sizeof(sentinel))==ERROR_SUCCESS);
    Check(RegOpenKeyExW(HKEY_CURRENT_USER,fixture.c_str(),0,KEY_READ|KEY_WRITE,&parent)==ERROR_SUCCESS);
    Check(StartRecentFilesIsolationForTest(text,source.c_str())==ERROR_SUCCESS);
    HKEY redirected=nullptr;
    Check(RegOpenKeyExW(parent,L"Recent Files",0,KEY_READ|KEY_WRITE,&redirected)==ERROR_SUCCESS);
    auto actual=RecentFilesKeyNameForTest(redirected);
    Check(actual.find(worker+L"\\Recent Files")!=actual.npos);
    DWORD kind=0,bytes=sizeof(sentinel),value=0;
    Check(RegQueryValueExW(redirected,L"sentinel",nullptr,&kind,reinterpret_cast<BYTE*>(&value),&bytes)==ERROR_FILE_NOT_FOUND);
    value=73;Check(RegSetValueExW(redirected,L"sentinel",0,REG_DWORD,reinterpret_cast<BYTE*>(&value),sizeof(value))==ERROR_SUCCESS);
    RegCloseKey(redirected);
    HKEY nested=nullptr;
    Check(RegCreateKeyExW(parent,L"Recent Files\\Nested",0,nullptr,0,KEY_ALL_ACCESS,nullptr,&nested,nullptr)==ERROR_SUCCESS);
    Check(RecentFilesKeyNameForTest(nested).find(worker+L"\\Recent Files\\Nested")!=std::wstring::npos);RegCloseKey(nested);
    Check(RegOpenKeyExA(HKEY_CURRENT_USER,std::string(source.begin(),source.end()).c_str(),0,KEY_READ,&redirected)==ERROR_SUCCESS);
    bytes=sizeof(value);Check(RegQueryValueExW(redirected,L"sentinel",nullptr,&kind,reinterpret_cast<BYTE*>(&value),&bytes)==ERROR_SUCCESS&&value==73);RegCloseKey(redirected);
    bytes=sizeof(value);Check(RegQueryValueExW(original,L"sentinel",nullptr,&kind,reinterpret_cast<BYTE*>(&value),&bytes)==ERROR_SUCCESS&&value==17);
    StopRecentFilesIsolationForTest();
    Check(RegOpenKeyExW(parent,L"Recent Files\\Nested",0,KEY_READ,&nested)==ERROR_FILE_NOT_FOUND);
    RegCloseKey(original);RegCloseKey(parent);
    RegDeleteTreeW(HKEY_CURRENT_USER,fixture.c_str());RegDeleteTreeW(HKEY_CURRENT_USER,worker.c_str());
    std::cout<<"Recent Files exact/relative/ANSI opens, nested creates and original-key preservation passed\n";
}
