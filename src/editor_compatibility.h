#pragma once
#include <windows.h>
#include <wintrust.h>
#include <softpub.h>
#include <bcrypt.h>
#include <wincrypt.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <cstring>
#include "editor_profiles.generated.h"
#pragma comment(lib,"version.lib")
#pragma comment(lib,"wintrust.lib")
#pragma comment(lib,"crypt32.lib")
#pragma comment(lib,"bcrypt.lib")

inline const EditorBuildProfile* FindEditorBuildProfile(const std::string& digest){
    for(auto& profile:kEditorBuildProfiles)if(digest==profile.sha256)return &profile;
    return nullptr;
}
inline std::string EditorFileSha256(const std::filesystem::path& path){
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;unsigned char bytes[32]{};
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return {};
    bool ok=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0;
    std::ifstream stream(path,std::ios::binary);std::vector<char> buffer(1024*1024);
    if(!stream)ok=false;
    while(ok&&stream){stream.read(buffer.data(),buffer.size());auto n=stream.gcount();if(n&&BCryptHashData(hash,reinterpret_cast<PUCHAR>(buffer.data()),ULONG(n),0)<0)ok=false;}
    if(stream.bad())ok=false;
    if(ok)ok=BCryptFinishHash(hash,bytes,sizeof(bytes),0)>=0;
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);
    if(!ok)return {};const char* alphabet="0123456789abcdef";std::string result;
    for(auto byte:bytes){result+=alphabet[byte>>4];result+=alphabet[byte&15];}return result;
}
struct EditorResourceIdentity {
    bool editor=false;std::wstring version;
};
inline EditorResourceIdentity ReadEditorResourceIdentity(const std::filesystem::path& path){
    if(_wcsicmp(path.filename().c_str(),L"SC2Editor_x64.exe"))return {};
    DWORD kind=0;if(!GetBinaryTypeW(path.c_str(),&kind)||kind!=SCS_64BIT_BINARY)return {};
    DWORD unused=0,size=GetFileVersionInfoSizeW(path.c_str(),&unused);if(!size||size>1024*1024)return {};
    std::vector<unsigned char> data(size);if(!GetFileVersionInfoW(path.c_str(),0,size,data.data()))return {};
    struct Translation {WORD language,codepage;};Translation* translations=nullptr;UINT bytes=0;
    if(!VerQueryValueW(data.data(),L"\\VarFileInfo\\Translation",reinterpret_cast<void**>(&translations),&bytes))return {};
    for(UINT i=0;i<bytes/sizeof(Translation);i++){
        auto text=[&](const wchar_t* name){wchar_t query[256]{};swprintf_s(query,L"\\StringFileInfo\\%04x%04x\\%s",translations[i].language,translations[i].codepage,name);
            wchar_t* value=nullptr;UINT count=0;if(!VerQueryValueW(data.data(),query,reinterpret_cast<void**>(&value),&count)||!count||count>4096)return std::wstring();return std::wstring(value,count-1);};
        auto original=text(L"OriginalFilename"),description=text(L"FileDescription"),company=text(L"CompanyName");
        bool role=!_wcsicmp(original.c_str(),L"SC2Edit.exe")||!_wcsicmp(original.c_str(),L"SC2Editor_x64.exe")||!_wcsicmp(description.c_str(),L"SC2Edit");
        if(role&&company.find(L"Blizzard Entertainment")!=company.npos)return {true,text(L"FileVersion")};
    }return {};
}
inline bool TrustedBlizzardEditorSignature(const std::filesystem::path& path){
    WINTRUST_FILE_INFO file{};file.cbStruct=sizeof(file);file.pcwszFilePath=path.c_str();
    WINTRUST_DATA trust{};trust.cbStruct=sizeof(trust);trust.dwUIChoice=WTD_UI_NONE;trust.fdwRevocationChecks=WTD_REVOKE_NONE;
    trust.dwUnionChoice=WTD_CHOICE_FILE;trust.pFile=&file;trust.dwStateAction=WTD_STATEACTION_VERIFY;
    trust.dwProvFlags=WTD_CACHE_ONLY_URL_RETRIEVAL|WTD_REVOCATION_CHECK_NONE;
    GUID action=WINTRUST_ACTION_GENERIC_VERIFY_V2;
    bool accepted=false;
    if(WinVerifyTrust(nullptr,&action,&trust)==ERROR_SUCCESS){
        auto provider=WTHelperProvDataFromStateData(trust.hWVTStateData);
        auto signer=provider?WTHelperGetProvSignerFromChain(provider,0,FALSE,0):nullptr;
        if(signer&&signer->csCertChain&&signer->pasCertChain&&signer->pasCertChain[0].pCert){
            wchar_t publisher[512]{};
            CertGetNameStringW(signer->pasCertChain[0].pCert,CERT_NAME_SIMPLE_DISPLAY_TYPE,0,nullptr,publisher,_countof(publisher));
            accepted=!_wcsicmp(publisher,L"Blizzard Entertainment, Inc.")||!_wcsicmp(publisher,L"Blizzard Entertainment");
        }
    }
    trust.dwStateAction=WTD_STATEACTION_CLOSE;WinVerifyTrust(nullptr,&action,&trust);return accepted;
}
struct EditorCompatibilityIdentity {
    std::string sha256;const EditorBuildProfile* profile=nullptr;std::wstring version;
    bool trusted=false;
};
inline EditorCompatibilityIdentity InspectCompatibleEditor(const std::filesystem::path& path,bool portableOnly=false){
    auto resource=ReadEditorResourceIdentity(path);if(!resource.editor)return {};
    auto sha=EditorFileSha256(path);auto profile=portableOnly?nullptr:FindEditorBuildProfile(sha);
    bool trusted=!sha.empty()&&(profile||TrustedBlizzardEditorSignature(path));
    return {sha,profile,resource.version,trusted};
}
inline bool CurrentEditorHasVerifiedOffsets(){
    static const bool allowed=[](){wchar_t image[32768]{};if(!GetModuleFileNameW(nullptr,image,_countof(image)))return false;
        auto profile=FindEditorBuildProfile(EditorFileSha256(image));return profile&&profile->nativeOffsets;}();
    return allowed;
}
