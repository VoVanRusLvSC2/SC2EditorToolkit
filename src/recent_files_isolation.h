#pragma once
#include <windows.h>
#include <string>

namespace recent_files {
inline std::wstring WorkerKey(const std::wstring& instance){
    if(instance.size()!=38||instance.front()!=L'{'||instance.back()!=L'}')return {};
    for(size_t i=1;i<37;i++){
        bool dash=i==9||i==14||i==19||i==24;
        wchar_t c=instance[i];
        if(dash?c!=L'-':!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')||(c>=L'A'&&c<=L'F')))return {};
    }
    return L"Software\\SC2EditorToolkit\\Workers\\"+instance;
}
inline std::wstring Redirect(const std::wstring& path,const std::wstring& source,const std::wstring& target){
    if(source.empty()||path.size()<source.size()||
       CompareStringOrdinal(path.data(),int(source.size()),source.data(),int(source.size()),TRUE)!=CSTR_EQUAL||
       (path.size()>source.size()&&path[source.size()]!=L'\\'))return {};
    return target+path.substr(source.size());
}
}
DWORD StartRecentFilesIsolation(const wchar_t* instanceSuffix);
#ifdef SC2_RECENT_FILES_TESTING
DWORD StartRecentFilesIsolationForTest(const wchar_t* instance,const wchar_t* source);
void StopRecentFilesIsolationForTest();
std::wstring RecentFilesKeyNameForTest(HKEY key);
#endif
