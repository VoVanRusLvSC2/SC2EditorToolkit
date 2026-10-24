#pragma once
#include <windows.h>
#include <commctrl.h>

// Caller must own this control on its private Editor desktop. Never changes
// global animation settings. Restore original scroll/visibility on exceptions.
class OwnedTreeTraversalScope {
    HWND window_;
    UINT scroll_;
    bool visible_;
public:
    explicit OwnedTreeTraversalScope(HWND window):window_(window),
        scroll_(UINT(SendMessageW(window,TVM_GETSCROLLTIME,0,0))),
        visible_((GetWindowLongPtrW(window,GWL_STYLE)&WS_VISIBLE)!=0) {
        SendMessageW(window_,TVM_SETSCROLLTIME,1,0);
        if(visible_)SendMessageW(window_,WM_SETREDRAW,FALSE,0);
    }
    OwnedTreeTraversalScope(const OwnedTreeTraversalScope&)=delete;
    OwnedTreeTraversalScope& operator=(const OwnedTreeTraversalScope&)=delete;
    ~OwnedTreeTraversalScope() noexcept {
        if(IsWindow(window_)) {
            SendMessageW(window_,TVM_SETSCROLLTIME,scroll_,0);
            if(visible_){SendMessageW(window_,WM_SETREDRAW,TRUE,0);InvalidateRect(window_,nullptr,FALSE);}
        }
    }
};
