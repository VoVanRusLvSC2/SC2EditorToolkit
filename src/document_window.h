#pragma once
#include <string>
#include <cwctype>

// Document captions can abbreviate the directory, but retain the full archive
// name. Do not match substrings (Seed.SC2Map.bak is a different document).
inline std::wstring DocumentName(std::wstring path){
    auto slash=path.find_last_of(L"/\\");
    if(slash!=path.npos)path.erase(0,slash+1);
    for(auto& c:path)c=static_cast<wchar_t>(towlower(c));
    return path;
}
inline bool DocumentWindow(const std::wstring& title,const std::wstring& expected,std::wstring* module=nullptr,bool allowDirty=false){
    const std::wstring ending=L"] - StarCraft II Editor";
    auto open=title.find(L" - [");
    if(open==title.npos||title.size()<ending.size()||title.compare(title.size()-ending.size(),ending.size(),ending)!=0)return false;
    auto label=title.substr(0,open);
    // Script Test, dialogs, previews and Cutscenes' scene-file captions do not
    // establish that a map/mod has finished loading.
    bool known=false;
    for(auto name:{L"Terrain",L"Triggers",L"Data",L"Import",L"AI",L"UI",L"Text",L"Overview"})if(label==name)known=true;
    if(!known)return false;
    auto document=title.substr(open+4,title.size()-ending.size()-(open+4));
    if(allowDirty&&!document.empty()&&document.back()==L'*')document.pop_back();
    if(expected.empty()||DocumentName(document)!=DocumentName(expected))return false;
    if(module)*module=label;
    return true;
}
