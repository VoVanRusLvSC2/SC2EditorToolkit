#include "../src/owned_thread_hooks.h"
#include <iostream>
#include <string>
#pragma comment(lib,"user32.lib")
static constexpr UINT probe=WM_APP+41,finish=WM_APP+42;
static thread_local OwnedThreadHooks hooks;
static thread_local bool initialized=false;
static volatile LONG calls=0,wrongThread=0,postedOutsideSend=0;
static DWORD owner=0;
static HWND target=nullptr;
static HANDLE ready=nullptr;
static LRESULT CALLBACK Guard(int n,WPARAM w,LPARAM l){return CallNextHookEx(nullptr,n,w,l);}
static LRESULT CALLBACK Dispatch(int n,WPARAM w,LPARAM l){
    if(n>=0){auto m=reinterpret_cast<CWPSTRUCT*>(l);if(m&&m->message==probe){
        InterlockedIncrement(&calls);if(GetCurrentThreadId()!=owner)InterlockedIncrement(&wrongThread);
        if(m->wParam==1&&!InSendMessageEx(nullptr))InterlockedIncrement(&postedOutsideSend);
    }}return CallNextHookEx(nullptr,n,w,l);
}
static LRESULT CALLBACK Queued(int n,WPARAM w,LPARAM l){
    if(n>=0&&w==PM_REMOVE){auto m=reinterpret_cast<MSG*>(l);if(m&&m->message==probe){
        InterlockedIncrement(&calls);if(GetCurrentThreadId()!=owner)InterlockedIncrement(&wrongThread);
        if(!InSendMessageEx(nullptr))InterlockedIncrement(&postedOutsideSend);
        m->message=WM_NULL;
    }}return CallNextHookEx(nullptr,n,w,l);
}
static void CALLBACK Attach(ULONG_PTR){initialized=hooks.Start(Guard,Dispatch,Queued);}
static DWORD WINAPI TargetThread(void*){
    owner=GetCurrentThreadId();if(!initialized)return 2;
    target=CreateWindowExW(0,L"STATIC",L"Owned native dispatch test",WS_POPUP,0,0,10,10,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    SetEvent(ready);if(!target)return 3;
    MSG m{};while(GetMessageW(&m,nullptr,0,0)>0){if(m.message==finish)break;TranslateMessage(&m);DispatchMessageW(&m);}
    bool removed=hooks.Stop();DestroyWindow(target);return removed?0:4;
}
int wmain(){
    // Refuse the input desktop, even though these hooks never inject input.
    OwnedThreadHooks refused;if(refused.Start(Guard,Dispatch)||refused.error!=ERROR_ACCESS_DENIED)return 1;
    HDESK original=GetThreadDesktop(GetCurrentThreadId());
    std::wstring name=L"SC2Native-DispatchTest-"+std::to_wstring(GetCurrentProcessId());
    HDESK desktop=CreateDesktopW(name.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);
    if(!desktop||!SetThreadDesktop(desktop))return 2;
    ready=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    DWORD tid=0;HANDLE thread=CreateThread(nullptr,0,TargetThread,nullptr,CREATE_SUSPENDED,&tid);
    if(!thread)return 3;
    bool queued=QueueUserAPC(Attach,thread,0)!=0;ResumeThread(thread);
    bool started=queued&&WaitForSingleObject(ready,10000)==WAIT_OBJECT_0&&target;
    bool received=false,scoped=false,posted=false;
    if(started){
        SendMessageW(target,probe,0,0);received=calls==1&&wrongThread==0;
        HWND other=CreateWindowExW(0,L"STATIC",L"Unhooked thread",WS_POPUP,0,0,10,10,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
        if(other){SendMessageW(other,probe,0,0);scoped=calls==1;DestroyWindow(other);}
        PostMessageW(target,probe,1,0);
        auto deadline=GetTickCount64()+5000;while(calls<2&&GetTickCount64()<deadline)Sleep(10);
        posted=calls==2&&postedOutsideSend==1&&wrongThread==0;
    }
    PostThreadMessageW(tid,finish,0,0);bool ended=WaitForSingleObject(thread,10000)==WAIT_OBJECT_0;
    DWORD code=1;GetExitCodeThread(thread,&code);CloseHandle(thread);CloseHandle(ready);
    SetThreadDesktop(original);CloseDesktop(desktop);
    if(!started||!received||!scoped||!posted||!ended||code)return 4;
    std::cout<<"Owned GUI thread startup, sent/posted dispatch, no InSendMessage for posted requests, scope and cleanup passed\n";return 0;
}
