#pragma once
#include <string>
// Verified original Editor channels. Console 13 is INPUT; Console 15 is OUTPUT.
// Messages uses output 13. An absent channel must stay unreadable, never fall
// back to the Console command field.
inline int DiagnosticOutputId(const std::wstring& title){
    if(title.rfind(L"Console - ",0)==0||title.rfind(L"Консоль - ",0)==0)return 15;
    if(title.rfind(L"Messages - ",0)==0||title.rfind(L"Сообщения - ",0)==0)return 13;
    return -1;
}
