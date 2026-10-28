#pragma once
#include <windows.h>
#include <filesystem>
#include <string>
#include <vector>
#pragma comment(lib,"version.lib")
#pragma comment(lib,"user32.lib")

inline bool SameEditorFile(const std::filesystem::path& first,const std::filesystem::path& second){
    auto open=[](const std::filesystem::path& path){return CreateFileW(path.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,0,nullptr);};
    HANDLE a=open(first),b=open(second);BY_HANDLE_FILE_INFORMATION x{},y{};
    bool same=a!=INVALID_HANDLE_VALUE&&b!=INVALID_HANDLE_VALUE&&GetFileInformationByHandle(a,&x)&&GetFileInformationByHandle(b,&y)&&
        x.dwVolumeSerialNumber==y.dwVolumeSerialNumber&&x.nFileIndexHigh==y.nFileIndexHigh&&x.nFileIndexLow==y.nFileIndexLow;
    if(a!=INVALID_HANDLE_VALUE)CloseHandle(a);if(b!=INVALID_HANDLE_VALUE)CloseHandle(b);return same;
}
inline bool SupportedEditorFile(const std::filesystem::path& path){
    if(_wcsicmp(path.filename().c_str(),L"SC2Editor_x64.exe"))return false;
    DWORD kind=0;if(!GetBinaryTypeW(path.c_str(),&kind)||kind!=SCS_64BIT_BINARY)return false;
    DWORD unused=0,size=GetFileVersionInfoSizeW(path.c_str(),&unused);if(!size||size>1024*1024)return false;
    std::vector<unsigned char> data(size);if(!GetFileVersionInfoW(path.c_str(),0,size,data.data()))return false;
    VS_FIXEDFILEINFO* info=nullptr;UINT bytes=0;
    // The fixed Windows version resource stores the build modulo 65536.
    // The API additionally verifies the complete original executable SHA-256.
    return VerQueryValueW(data.data(),L"\\",reinterpret_cast<void**>(&info),&bytes)&&bytes>=sizeof(*info)&&info->dwSignature==0xfeef04bd&&
        info->dwFileVersionMS==MAKELONG(0,5)&&info->dwFileVersionLS==MAKELONG(98310,17);
}
inline std::wstring OwnedEditorPath(){
    DWORD size=GetEnvironmentVariableW(L"SC2EDITOR_EXPECTED_EXE",nullptr,0);if(!size||size>32768)return {};
    std::wstring path(size,L'\0');if(!GetEnvironmentVariableW(L"SC2EDITOR_EXPECTED_EXE",path.data(),size))return {};path.resize(size-1);return path;
}

// A startup export must fail closed if loaded into a game or an ordinary
// visible Editor. Check before installing any hooks or starting render threads.
inline bool CurrentOwnedEditorProcess(){
    wchar_t exe[32768]{},desktop[256]{};DWORD bytes=0;
    if(!GetModuleFileNameW(nullptr,exe,_countof(exe))||
       !GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,desktop,sizeof(desktop),&bytes)||
       wcsncmp(desktop,L"SC2Native-",10)!=0)return false;
    auto expected=OwnedEditorPath();
    return !expected.empty()&&
        !_wcsicmp(std::filesystem::path(exe).filename().c_str(),L"SC2Editor_x64.exe")&&
        !_wcsicmp(std::filesystem::path(expected).filename().c_str(),L"SC2Editor_x64.exe")&&
        SameEditorFile(exe,expected);
}
