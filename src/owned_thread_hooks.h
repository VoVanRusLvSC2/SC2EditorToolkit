#pragma once
#include <windows.h>
#include <cwchar>

// Loaded by the owned startup bootstrap, then initialized on the Editor's own
// GUI thread. No external TID, DLL module registration or desktop-wide hook.
struct OwnedThreadHooks {
    HHOOK guard=nullptr,dispatch=nullptr,queued=nullptr;
    DWORD error=0;
    bool Start(HOOKPROC guardProc,HOOKPROC dispatchProc,HOOKPROC queuedProc=nullptr){
        if(guard&&dispatch&&(!queuedProc||queued))return true;
        wchar_t desktop[256]{};DWORD bytes=0;
        if(!GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,desktop,sizeof(desktop),&bytes)){
            error=GetLastError();return false;
        }
        if(wcsncmp(desktop,L"SC2Native-",10)!=0){error=ERROR_ACCESS_DENIED;return false;}
        guard=SetWindowsHookExW(WH_CBT,guardProc,nullptr,GetCurrentThreadId());
        if(!guard){error=GetLastError();return false;}
        dispatch=SetWindowsHookExW(WH_CALLWNDPROC,dispatchProc,nullptr,GetCurrentThreadId());
        if(!dispatch){error=GetLastError();UnhookWindowsHookEx(guard);guard=nullptr;return false;}
        if(queuedProc){
            queued=SetWindowsHookExW(WH_GETMESSAGE,queuedProc,nullptr,GetCurrentThreadId());
            if(!queued){error=GetLastError();UnhookWindowsHookEx(dispatch);dispatch=nullptr;UnhookWindowsHookEx(guard);guard=nullptr;return false;}
        }
        error=0;return true;
    }
    bool Stop(){
        bool c=!queued||UnhookWindowsHookEx(queued)!=0;
        bool a=!dispatch||UnhookWindowsHookEx(dispatch)!=0;
        bool b=!guard||UnhookWindowsHookEx(guard)!=0;
        if(a)dispatch=nullptr;if(b)guard=nullptr;if(c)queued=nullptr;return a&&b&&c;
    }
};
