#include <windows.h>
#include <commctrl.h>
#include <cassert>
#include <stdexcept>
#include <iostream>
#include "../src/owned_tree_traversal.h"
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"comctl32.lib")
int main(){
    INITCOMMONCONTROLSEX controls{sizeof(controls),ICC_TREEVIEW_CLASSES};assert(InitCommonControlsEx(&controls));
    HWND parent=CreateWindowExW(0,L"STATIC",L"Owned invisible test parent",WS_POPUP,0,0,100,100,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);assert(parent);
    for(bool visible:{false,true}){
        HWND tree=CreateWindowExW(0,WC_TREEVIEWW,L"",WS_CHILD|(visible?WS_VISIBLE:0),0,0,100,100,parent,nullptr,GetModuleHandleW(nullptr),nullptr);assert(tree);
        for(UINT value:{250u,0xffffffffu}){
            SendMessageW(tree,TVM_SETSCROLLTIME,value,0);
            auto original=SendMessageW(tree,TVM_GETSCROLLTIME,0,0);
            try{OwnedTreeTraversalScope guard(tree);assert(SendMessageW(tree,TVM_GETSCROLLTIME,0,0)==1);throw std::runtime_error("unwind");}catch(const std::runtime_error&){}
            assert(SendMessageW(tree,TVM_GETSCROLLTIME,0,0)==original);
            assert(bool(GetWindowLongPtrW(tree,GWL_STYLE)&WS_VISIBLE)==visible);
        }
        assert(!IsWindowVisible(parent));DestroyWindow(tree);
    }
    DestroyWindow(parent);std::cout<<"Owned tree traversal: local scroll and visibility restored on exception; no visible parent passed\n";
}
