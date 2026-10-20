#pragma once
#include <string>
#include <cwctype>
inline std::wstring MapNormalizedPath(std::wstring path){for(auto& c:path){if(c==L'/')c=L'\\';c=static_cast<wchar_t>(towlower(c));}return path;}
// The native static caption abbreviates long paths as K:/.../parent/file.tga.
// This is checked ONLY after the save chooser accepted the exact full filename;
// both visible ends must match that same destination, including its basename.
inline bool MapDisplayMatches(const std::wstring& display,const std::wstring& expected){
    auto shown=MapNormalizedPath(display),full=MapNormalizedPath(expected);
    if(shown==full)return true;
    auto gap=shown.find(L"\\...\\");
    if(gap==shown.npos||gap<2||shown.find(L"\\...\\",gap+1)!=shown.npos)return false;
    auto prefix=shown.substr(0,gap+1),suffix=shown.substr(gap+4);
    if(suffix.size()<5||full.size()<prefix.size()+suffix.size())return false;
    return full.compare(0,prefix.size(),prefix)==0&&full.compare(full.size()-suffix.size(),suffix.size(),suffix)==0;
}
