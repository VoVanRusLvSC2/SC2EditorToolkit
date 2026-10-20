#include "protocol.h"
#include <commctrl.h>
#include <string>
#include <vector>
#include <algorithm>
#include <cwctype>
#include <cstdarg>
#include <filesystem>
#include <shlobj.h>
#include <sstream>
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"comctl32.lib")
static HMODULE module;
static thread_local Block* current;
static thread_local bool processing;
static bool PrivateDesktop(){
    wchar_t name[256]{};DWORD size=0;
    return GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,name,sizeof(name),&size)&&wcsncmp(name,L"SC2Native-",10)==0;
}
static std::wstring Text(HWND w) {
    wchar_t s[2048]{}; GetWindowTextW(w,s,2048); return s;
}
static std::wstring Class(HWND w) {
    wchar_t s[256]{}; GetClassNameW(w,s,256); return s;
}
static void Log(Block* b,const wchar_t* format,...) {
    size_t used=wcsnlen_s(b->log,_countof(b->log));
    if(used+2>=_countof(b->log)){b->diagnosticsTruncated=1;return;}
    va_list a;va_start(a,format);
    _vsnwprintf_s(b->log+used,_countof(b->log)-used,_TRUNCATE,format,a);va_end(a);
}
static void Fail(Block* b,uint32_t code,const wchar_t* reason) {
    b->error=code;wcsncpy_s(b->failure,reason,_TRUNCATE);
}
static LRESULT CALLBACK FocusGuard(int n,WPARAM wp,LPARAM lp) {
    if(PrivateDesktop())return CallNextHookEx(nullptr,n,wp,lp);
    if(current && n>=0) {
        if(n==HCBT_ACTIVATE){InterlockedIncrement(reinterpret_cast<volatile LONG*>(&current->activationVetoes));return 1;}
        if(n==HCBT_SETFOCUS){InterlockedIncrement(reinterpret_cast<volatile LONG*>(&current->focusVetoes));return 1;}
    }
    return CallNextHookEx(nullptr,n,wp,lp);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK BridgeFocusGuard(int n,WPARAM wp,LPARAM lp) {
    if(PrivateDesktop())return CallNextHookEx(nullptr,n,wp,lp);
    if(n==HCBT_ACTIVATE||n==HCBT_SETFOCUS){
        if(current){if(n==HCBT_ACTIVATE)++current->activationVetoes;else ++current->focusVetoes;}
        return 1;
    }
    return CallNextHookEx(nullptr,n,wp,lp);
}
static BOOL CALLBACK EnumChildren(HWND w,LPARAM p){reinterpret_cast<std::vector<HWND>*>(p)->push_back(w);return TRUE;}
static std::vector<HWND> Children(HWND w){std::vector<HWND> v;EnumChildWindows(w,EnumChildren,reinterpret_cast<LPARAM>(&v));return v;}
static BOOL CALLBACK EnumRoots(HWND w,LPARAM p){reinterpret_cast<std::vector<HWND>*>(p)->push_back(w);return TRUE;}
static std::vector<HWND> Roots(){std::vector<HWND> v;EnumThreadWindows(GetCurrentThreadId(),EnumRoots,reinterpret_cast<LPARAM>(&v));return v;}
static std::wstring Clean(std::wstring s){s.erase(std::remove(s.begin(),s.end(),L'&'),s.end());auto i=s.find(L'\t');if(i!=s.npos)s.resize(i);return s;}
static UINT FindCommand(HWND w,std::initializer_list<const wchar_t*> parents,std::initializer_list<const wchar_t*> labels) {
    HMENU m=GetMenu(w);int count=GetMenuItemCount(m);if(count<0||count>64)return 0;
    SendMessageW(w,WM_INITMENU,reinterpret_cast<WPARAM>(m),0);
    UINT found=0;
    for(int i=0;i<count;i++){
        wchar_t s[512]{};GetMenuStringW(m,i,s,512,MF_BYPOSITION);
        bool match=false;for(auto p:parents)if(Clean(s)==p)match=true;
        if(!match)continue;
        HMENU sub=GetSubMenu(m,i);
        SendMessageW(w,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(sub),MAKELPARAM(i,FALSE));
        int n=GetMenuItemCount(sub);if(n<0||n>256)return 0;
        for(int j=0;j<n;j++){
            GetMenuStringW(sub,j,s,512,MF_BYPOSITION);match=false;for(auto p:labels)if(Clean(s)==p)match=true;
            if(!match)continue;
            if(GetMenuState(sub,j,MF_BYPOSITION)&(MF_DISABLED|MF_GRAYED))return 0;
            UINT id=GetMenuItemID(sub,j);if(found||id==UINT(-1))return 0;found=id;
        }
    }return found;
}
struct LoadState {
    Block* b;
    std::filesystem::path path;
    ULONGLONG deadline;
    HWND chooser=nullptr, folder=nullptr;
};
static thread_local LoadState* loading;
static HWND ExactRoot(const wchar_t* label){HWND found=nullptr;for(HWND w:Roots())if(Text(w)==label&&IsWindowVisible(w)){if(found)return nullptr;found=w;}return found;}
static HWND Control(HWND w,const wchar_t* type,int id){HWND found=nullptr;for(HWND c:Children(w))if(Class(c)==type&&GetDlgCtrlID(c)==id){if(found)return nullptr;found=c;}return found;}
static void CancelLoadDialog(HWND w){
    if(!w||!IsWindow(w))return;
    for(HWND c:Children(w))if(Class(c)==L"Button"&&(Clean(Text(c))==L"Cancel"||Clean(Text(c))==L"Отмена")){
        SendMessageW(w,WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(c),BN_CLICKED),reinterpret_cast<LPARAM>(c));return;
    }
}
static void CALLBACK LoadTimer(HWND,UINT,UINT_PTR,DWORD){
    auto state=loading;if(!state)return;auto b=state->b;
    if(GetTickCount64()>state->deadline){
        if(!b->error)Fail(b,35,L"Native document load timed out; cancelling only dialogs opened for this job");
        b->loadStage=90;
        if(state->folder&&IsWindow(state->folder))CancelLoadDialog(state->folder);
        else if(state->chooser&&IsWindow(state->chooser))CancelLoadDialog(state->chooser);
        return;
    }
    if(b->loadStage==1){
        HWND chooser=ExactRoot(L"Open Document");if(!chooser)chooser=ExactRoot(L"Открыть документ");
        if(!chooser||!IsWindowEnabled(chooser))return;
        HWND button=Control(chooser,L"Button",15);if(!button)return;
        state->chooser=chooser;b->loadStage=2;Log(b,L"load: invoking native Browse folder button\n");
        SendMessageW(chooser,WM_COMMAND,MAKEWPARAM(15,BN_CLICKED),reinterpret_cast<LPARAM>(button));return;
    }
    if(b->loadStage==2){
        HWND folder=ExactRoot(L"Browse For Folder");if(!folder)folder=ExactRoot(L"Обзор папок");
        if(!folder||!IsWindowEnabled(folder))return;
        state->folder=folder;b->loadStage=3;auto directory=state->path.parent_path().wstring();
        Log(b,L"load: shell BFFM_SETSELECTIONW directory=%s\n",directory.c_str());
        SendMessageW(folder,BFFM_SETSELECTIONW,TRUE,reinterpret_cast<LPARAM>(directory.c_str()));
        HWND ok=Control(folder,L"Button",IDOK);
        if(!ok){Fail(b,36,L"Native folder OK control missing");state->deadline=0;return;}
        SendMessageW(folder,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),reinterpret_cast<LPARAM>(ok));return;
    }
    if(b->loadStage==3){
        if(state->folder&&IsWindow(state->folder)&&IsWindowVisible(state->folder))return;
        HWND chooser=state->chooser;if(!chooser||!IsWindow(chooser)||!IsWindowEnabled(chooser))return;
        HWND list=Control(chooser,L"SysListView32",19);if(!list)return;
        int count=static_cast<int>(SendMessageW(list,LVM_GETITEMCOUNT,0,0));if(count<1||count>64)return;
        int match=-1;auto filename=state->path.filename().wstring();
        for(int i=0;i<count;i++){
            wchar_t text[2048]{};LVITEMW item{};item.iSubItem=0;item.pszText=text;item.cchTextMax=2048;
            SendMessageW(list,LVM_GETITEMTEXTW,i,reinterpret_cast<LPARAM>(&item));
            if(!_wcsicmp(text,filename.c_str())){if(match!=-1){Fail(b,37,L"Ambiguous native document filename");state->deadline=0;return;}match=i;}
        }
        if(match==-1)return;
        LVITEMW item{};item.stateMask=LVIS_SELECTED|LVIS_FOCUSED;item.state=0;SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&item));
        item.state=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,match,reinterpret_cast<LPARAM>(&item));
        if(SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0)!=1){Fail(b,38,L"Native file selection not confirmed");state->deadline=0;return;}
        HWND ok=Control(chooser,L"Button",11);if(!ok){Fail(b,39,L"Native document OK control missing");state->deadline=0;return;}
        b->loadStage=4;Log(b,L"load: native filename selected=%s\n",filename.c_str());
        SendMessageW(chooser,WM_COMMAND,MAKEWPARAM(11,BN_CLICKED),reinterpret_cast<LPARAM>(ok));return;
    }
}
static void Load(Block* b,HWND target){
    std::filesystem::path path(b->mapPath);
    if(!path.is_absolute()||!std::filesystem::is_regular_file(path)) {Fail(b,30,L"Prepared document path must be an existing absolute archive path");return;}
    auto extension=path.extension().wstring();std::transform(extension.begin(),extension.end(),extension.begin(),towlower);
    if(extension!=L".sc2map"&&extension!=L".sc2mod"){Fail(b,30,L"Only prepared SC2Map/SC2Mod archives accepted");return;}
    // Refuse pre-existing dialogs instead of repurposing a user interaction.
    bool resume=ExactRoot(L"Open Document")&&b->resumeDialog;
    if(!resume&&(ExactRoot(L"Open Document")||ExactRoot(L"Browse For Folder"))){Fail(b,31,L"An unrelated document chooser is already open");return;}
    UINT command=FindCommand(target,{L"File",L"Файл"},{L"Open...",L"Открыть..."});
    if(!command){Fail(b,32,L"Unique enabled original File/Open command missing");return;}
    LoadState state{b,path,GetTickCount64()+600000};loading=&state;
    UINT_PTR timer=SetTimer(nullptr,0,50,LoadTimer);if(!timer){loading=nullptr;Fail(b,33,L"Cannot create native dialog task timer");return;}
    b->loadStage=1;b->loadCommand=command;++b->commandsDispatched;
    Log(b,L"load: native File/Open id=%u input=%s\n",command,path.c_str());
    if(!resume)SendMessageW(target,WM_COMMAND,MAKEWPARAM(command,0),0);
    // This Editor's Open Document is modeless. Keep the owner thread's regular
    // message pump running under the activation veto until the native loader
    // has switched to the exact new document and enabled its workspace.
    ULONGLONG readySince=0;
    while(IsWindow(target)&&!b->error){
        auto caption=Text(target);
        if(b->loadStage==4&&IsWindowEnabled(target)&&caption.find(path.filename().wstring())!=caption.npos){
            if(!readySince)readySince=GetTickCount64();
            if(GetTickCount64()-readySince>=500)break;
        }else readySince=0;
        MSG message{};int bounded=0;while(bounded++<100&&PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
            if(message.message==WM_QUIT){PostQuitMessage(static_cast<int>(message.wParam));Fail(b,40,L"Editor is exiting");break;}
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);
        if(GetTickCount64()>state.deadline)LoadTimer(nullptr,0,0,0);
    }
    KillTimer(nullptr,timer);loading=nullptr;
    auto title=Text(target);wcsncpy_s(b->loadedTitle,title.c_str(),_TRUNCATE);
    if(!b->error&&b->loadStage==4&&IsWindowEnabled(target)&&title.find(path.filename().wstring())!=title.npos){
        b->mapLoaded=1;b->loadStage=5;Log(b,L"load: new document is active and enabled\n");
    }else if(!b->error)Fail(b,34,L"Native document opening returned without the expected active document");
}
static HWND Script(){HWND found=nullptr;for(HWND w:Roots())if(Text(w)==L"Script Test - StarCraft II Editor"||Text(w)==L"Проверка скрипта - Редактор StarCraft II"){if(found)return nullptr;found=w;}return found;}
static bool SelectContext(Block* b,HWND target){
    if(!b->contextLabel[0])return true;
    // Authored libraries are roots of tree 28; tree 18 contains dependency
    // libraries. This distinction was observed on the actual Nydus document.
    HWND tree=Control(target,L"SysTreeView32",28);if(!tree){Fail(b,43,L"Native authored context tree not found");return false;}
    HTREEITEM matched=nullptr;int count=0;
    auto root=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_ROOT,0));
    std::wstring label(b->contextLabel);
    while(root&&count++<256){
        wchar_t text[2048]{};TVITEMW item{};item.mask=TVIF_TEXT;item.hItem=root;item.pszText=text;item.cchTextMax=2048;SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&item));
        std::wstring name(text);
        if(name==label||name.rfind(label+L" = ",0)==0||name.rfind(label+L" <",0)==0){if(matched){Fail(b,44,L"Ambiguous authored root label");return false;}matched=root;}
        root=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(root)));
    }
    if(root||!matched){Fail(b,45,L"Expected authored map root label not found in bounded native tree");return false;}
    if(!(SendMessageW(tree,TVM_GETITEMSTATE,reinterpret_cast<WPARAM>(matched),TVIS_SELECTED)&TVIS_SELECTED))
        SendMessageW(tree,TVM_SELECTITEM,TVGN_CARET,reinterpret_cast<LPARAM>(matched));
    if(!(SendMessageW(tree,TVM_GETITEMSTATE,reinterpret_cast<WPARAM>(matched),TVIS_SELECTED)&TVIS_SELECTED)){Fail(b,46,L"Native map context selection not accepted; no generation sent");return false;}
    // The native View Script command uses the active pane, not merely the
    // selected item. Logical focus is permitted only on our isolated desktop.
    if(PrivateDesktop()){SetFocus(tree);b->privateFocusUsed=1;}
    b->contextSelected=1;Log(b,L"context: exact unique authored root selected=%s scope=%s treeId=%d\n",b->contextLabel,b->scope,GetDlgCtrlID(tree));return true;
}
static HWND EditorControl(HWND script) {
    HWND found=nullptr;LONG64 area=-1;
    for(HWND c:Children(script))if(Class(c)==L"Scintilla"&&IsWindowVisible(c)){
        RECT r{};GetClientRect(c,&r);LONG64 a=LONG64(r.right)*r.bottom;
        if(a>area){found=c;area=a;}
    }return found;
}
static uint64_t Fingerprint(HWND editor) {
    if(!editor)return 0;
    LRESULT length=SendMessageW(editor,2183,0,0);
    if(length<0||length>=kSourceCapacity)return 0;
    std::vector<char> text(static_cast<size_t>(length)+1);
    SendMessageW(editor,2182,text.size(),reinterpret_cast<LPARAM>(text.data()));
    uint64_t hash=14695981039346656037ull;for(size_t i=0;i<size_t(length);i++){hash^=static_cast<unsigned char>(text[i]);hash*=1099511628211ull;}return hash;
}
static std::wstring CompileStatus(HWND script) {
    std::wstring result;
    if(!script)return result;
    for(HWND c:Children(script))if(Class(c)==L"Static"){
        auto s=Text(c);if(s.find(L"Memory Usage - Code:")!=s.npos||s.find(L"Использование памяти - код:")!=s.npos){if(!result.empty())return L"AMBIGUOUS_COMPILE_STATUS";result=s;}
    }return result;
}
static void Snapshot(Block* b) {
    HWND script=Script();b->scriptWindow=reinterpret_cast<uint64_t>(script);
    b->compilerErrors=-1;
    if(!script){Fail(b,20,L"Script Test not found on the document owner thread");return;}
    auto status=CompileStatus(script);wcsncpy_s(b->statusAfter,status.c_str(),_TRUNCATE);
    for(HWND c:Children(script))if(Class(c)==L"SysListView32"&&GetDlgCtrlID(c)==19){
        b->compilerErrors=static_cast<int32_t>(SendMessageW(c,LVM_GETITEMCOUNT,0,0));
        for(int i=0;i<(std::min)(b->compilerErrors,64);i++)for(int column=0;column<4;column++){
            wchar_t text[2048]{};LVITEMW item{};item.iSubItem=column;item.pszText=text;item.cchTextMax=2048;
            SendMessageW(c,LVM_GETITEMTEXTW,i,reinterpret_cast<LPARAM>(&item));Log(b,L"compiler row=%d column=%d text=%s\n",i,column,text);
        }
    }
    HWND editor=EditorControl(script);if(!editor){Fail(b,21,L"No visible Scintilla source control");return;}
    b->sourceReadOnly=static_cast<uint32_t>(SendMessageW(editor,2140,0,0));
    LRESULT length=SendMessageW(editor,2183,0,0);
    if(length<=0||length>=kSourceCapacity){Fail(b,22,L"Source empty or above 16 MiB bound");return;}
    b->codePage=static_cast<uint32_t>(SendMessageW(editor,2137,0,0));
    SendMessageW(editor,2182,static_cast<WPARAM>(length+1),reinterpret_cast<LPARAM>(b->source));
    b->sourceBytes=static_cast<uint32_t>(length);b->afterTextFingerprint=Fingerprint(editor);
    if(b->expectedMarker[0]){
        char marker[1024]{};WideCharToMultiByte(CP_UTF8,0,b->expectedMarker,-1,marker,1024,nullptr,nullptr);
        if(std::string(b->source,b->sourceBytes).find(marker)==std::string::npos)Fail(b,23,L"Expected test marker absent from native source");
    }
    if(wcsncmp(b->scope,L"library:",8)==0){
        char libraryId[64]{};WideCharToMultiByte(CP_UTF8,0,b->scope+8,-1,libraryId,64,nullptr,nullptr);
        std::string required="void lib"+std::string(libraryId)+"_InitLib (";
        if(std::string(b->source,b->sourceBytes).find(required)==std::string::npos)Fail(b,47,L"Selected native source does not define the requested library initializer");
    }
}
static void DiagnosticsSnapshot(Block* b){
    for(HWND root:Roots()){
        auto title=Text(root);
        if(title.find(L"Console")==title.npos&&title.find(L"Messages")==title.npos&&title.find(L"Консоль")==title.npos&&title.find(L"Сообщения")==title.npos)continue;
        ++b->diagnosticWindows;Log(b,L"diagnostics window=%s\n",title.c_str());
        for(HWND c:Children(root)){
            auto cls=Class(c);int id=GetDlgCtrlID(c);
            Log(b,L"diagnostics control=%d class=%s\n",id,cls.c_str());
            if(cls==L"SysListView32"){
                int count=static_cast<int>(SendMessageW(c,LVM_GETITEMCOUNT,0,0));
                Log(b,L"diagnostics readable=listview count=%d\n",count);
                if(count>256)b->diagnosticsTruncated=1;
                for(int r=0;r<(std::min)(count,256);r++){
                    std::wstring row;for(int col=0;col<8;col++){
                        wchar_t text[2048]{};LVITEMW item{};item.iSubItem=col;item.pszText=text;item.cchTextMax=2048;
                        SendMessageW(c,LVM_GETITEMTEXTW,r,reinterpret_cast<LPARAM>(&item));if(text[0]){if(!row.empty())row+=L" | ";row+=text;}
                    }Log(b,L"diagnostics row=%d control=%d text=%s\n",r,id,row.c_str());
                }
            }else if(cls==L"ListBox"){
                int count=static_cast<int>(SendMessageW(c,LB_GETCOUNT,0,0));if(count>256)b->diagnosticsTruncated=1;
                Log(b,L"diagnostics readable=listbox count=%d\n",count);
                for(int r=0;r<(std::min)(count,256);r++){
                    auto length=SendMessageW(c,LB_GETTEXTLEN,r,0);if(length<0||length>32768){b->diagnosticsTruncated=1;continue;}
                    std::vector<wchar_t> value(size_t(length)+1);SendMessageW(c,LB_GETTEXT,r,reinterpret_cast<LPARAM>(value.data()));Log(b,L"diagnostics row=%d control=%d text=%s\n",r,id,value.data());
                }
            }else if(cls==L"Edit"||cls.rfind(L"RichEdit",0)==0||cls.rfind(L"RICHEDIT",0)==0||cls==L"Scintilla"){
                Log(b,L"diagnostics readable=text\n");
                if(GetWindowTextLengthW(c)>2047)b->diagnosticsTruncated=1;
                std::wistringstream lines(Text(c));std::wstring line;
                while(std::getline(lines,line))if(!line.empty())Log(b,L"diagnostics text=%s\n",line.c_str());
            }
        }
    }
}
static void Process(Block* b) {
    b->dllPid=GetCurrentProcessId();b->dllTid=GetCurrentThreadId();b->foregroundBefore=reinterpret_cast<uint64_t>(GetForegroundWindow());
    HWND target=reinterpret_cast<HWND>(b->target);DWORD pid=0;DWORD tid=GetWindowThreadProcessId(target,&pid);
    if(pid!=b->pid||tid!=b->tid||pid!=GetCurrentProcessId()||tid!=GetCurrentThreadId()){Fail(b,10,L"PID/thread/HWND identity mismatch");return;}
    auto title=Text(target);
    if(b->expectedDocument[0]==0||title.find(b->expectedDocument)==title.npos||title.find(L'*')!=title.npos){Fail(b,11,L"Expected saved test document is not active");return;}
    for(HWND w:Roots()){
        Log(b,L"root hwnd=%p enabled=%d class=%s title=%s\n",w,IsWindowEnabled(w),Class(w).c_str(),Text(w).c_str());
        if(w==target)for(HWND c:Children(w))if(Class(c)==L"SysTreeView32"){
            HTREEITEM selected=reinterpret_cast<HTREEITEM>(SendMessageW(c,TVM_GETNEXTITEM,TVGN_CARET,0));
            wchar_t s[1024]{};TVITEMW item{};item.mask=TVIF_TEXT;item.hItem=selected;item.pszText=s;item.cchTextMax=1024;
            if(selected)SendMessageW(c,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&item));
            Log(b,L"tree id=%d selected=%s\n",GetDlgCtrlID(c),s);
            if(b->operation==Inspect){
                int roots=0;auto entry=reinterpret_cast<HTREEITEM>(SendMessageW(c,TVM_GETNEXTITEM,TVGN_ROOT,0));
                while(entry&&roots++<64){
                    wchar_t name[1024]{};TVITEMW row{};row.mask=TVIF_TEXT;row.hItem=entry;row.pszText=name;row.cchTextMax=1024;SendMessageW(c,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row));
                    Log(b,L"tree id=%d root=%s\n",GetDlgCtrlID(c),name);entry=reinterpret_cast<HTREEITEM>(SendMessageW(c,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(entry)));
                }
            }
        }
    }
    if(b->operation==Diagnostics){DiagnosticsSnapshot(b);return;}
    if(b->operation==OpenCutscene){
        UINT command=FindCommand(target,{L"Modules",L"Модули"},{L"Cutscene Editor",L"Cutscenes",L"Редактор сцен",L"Редактор кат-сцен"});
        if(!command){Fail(b,50,L"Original Cutscene module command not found");return;}
        b->moduleCommand=command;++b->commandsDispatched;SendMessageW(target,WM_COMMAND,command,0);return;
    }
    if(b->operation==Inspect){
        for(HWND w:Roots())if(IsWindowVisible(w))for(HWND c:Children(w))if(IsWindowVisible(c)&&(Class(c)==L"Static"||Class(c)==L"Button")){
            auto text=Text(c);if(!text.empty())Log(b,L"visible root=%s class=%s id=%d text=%s\n",Text(w).c_str(),Class(c).c_str(),GetDlgCtrlID(c),text.c_str());
        }
        return;
    }
    if(b->operation==CancelLoad){
        HWND activity=ExactRoot(L"Activity - StarCraft II Editor");
        bool own=false;if(activity&&b->mapPath[0])for(HWND c:Children(activity))if(Class(c)==L"Static"&&Text(c).find(b->mapPath)!=std::wstring::npos)own=true;
        if(!own){Fail(b,41,L"No activity matching this exact prepared map; cancel not sent");return;}
        SendMessageW(activity,WM_COMMAND,IDCANCEL,0);Log(b,L"Requested native cancel for this job's Activity dialog\n");return;
    }
    if(!IsWindowEnabled(target)&&!(b->operation==LoadDocument&&b->resumeDialog)){Fail(b,12,L"A modal dialog blocks the target; no generator command sent");return;}
    if(b->operation==LoadDocument){Load(b,target);return;}
    HWND oldScript=Script();b->beforeTextFingerprint=Fingerprint(EditorControl(oldScript));
    auto before=CompileStatus(oldScript);wcsncpy_s(b->statusBefore,before.c_str(),_TRUNCATE);
    if(b->operation==Generate||b->operation==FreshnessProbe){
        if(!SelectContext(b,target))return;
        UINT id=FindCommand(target,{L"Data",L"Данные"},{L"View Script",L"Просмотреть скрипт",L"Просмотр скрипта"});
        if(!id){Fail(b,13,L"Unique enabled native View Script command not found");return;}
        if(b->operation==FreshnessProbe){
            // The probe is restricted to our disposable marker document. It edits only
            // Script Test's generated text, never the map's XML/model or saved file.
            if(title.find(L"NativeEmitterProbe.SC2Map")==title.npos||wcscmp(b->expectedMarker,L"NativeOracleMarker20261020")){
                Fail(b,24,L"Freshness probe is restricted to the disposable marker fixture");return;
            }
            HWND source=EditorControl(oldScript);
            if(!source||SendMessageW(source,2140,0,0)){Fail(b,25,L"Generated viewer is read-only; scratch probe not applied");return;}
            LRESULT n=SendMessageW(source,2183,0,0);
            if(n<=0||n>=kSourceCapacity){Fail(b,22,L"Cannot back up scratch source");return;}
            std::vector<char> backup(size_t(n)+1);SendMessageW(source,2182,backup.size(),reinterpret_cast<LPARAM>(backup.data()));
            constexpr char poison[]="// SC2_NATIVE_BRIDGE_STALE_TEXT_PROBE_20261020\r\n";
            SendMessageW(source,2181,0,reinterpret_cast<LPARAM>(poison));
            b->poisonApplied=Fingerprint(source)!=b->beforeTextFingerprint;
            b->generatorCommand=id;++b->commandsDispatched;SendMessageW(target,WM_COMMAND,MAKEWPARAM(id,0),0);
            Snapshot(b);
            b->poisonReplaced=b->poisonApplied&&b->sourceBytes==uint32_t(n)&&std::equal(backup.begin(),backup.end()-1,b->source);
            if(!b->poisonReplaced){
                // Restore the disposable source buffer if regeneration did not restore it.
                HWND restore=EditorControl(Script());if(restore&&!SendMessageW(restore,2140,0,0))SendMessageW(restore,2181,0,reinterpret_cast<LPARAM>(backup.data()));
                Fail(b,26,L"Fresh source replacement not proven; previous scratch source restored where possible");
            }
            b->foregroundAfter=reinterpret_cast<uint64_t>(GetForegroundWindow());return;
        }
        b->generatorCommand=id;++b->commandsDispatched;SendMessageW(target,WM_COMMAND,MAKEWPARAM(id,0),0);
    }else if(b->operation==Compile){
        HWND script=Script();if(!script){Fail(b,20,L"Script Test not found");return;}
        if(PrivateDesktop()){
            SetActiveWindow(script);HWND source=EditorControl(script);if(source)SetFocus(source);b->privateFocusUsed=1;
        }
        UINT id=FindCommand(script,{L"Data",L"Данные"},{L"Compile All",L"Компилировать все",L"Преобразовать все"});
        if(!id){
            HMENU menu=GetMenu(script);
            for(int i=0;i<GetMenuItemCount(menu);i++){
                wchar_t text[512]{};GetMenuStringW(menu,i,text,512,MF_BYPOSITION);Log(b,L"menu root=%s\n",text);
                HMENU child=GetSubMenu(menu,i);if(!child)continue;
                for(int j=0;j<GetMenuItemCount(child);j++){GetMenuStringW(child,j,text,512,MF_BYPOSITION);Log(b,L"menu item=%s id=%u state=%u\n",text,GetMenuItemID(child,j),GetMenuState(child,j,MF_BYPOSITION));}
            }
            Fail(b,14,L"Unique enabled native Compile All command not found");return;
        }
        b->compilerCommand=id;++b->commandsDispatched;SendMessageW(script,WM_COMMAND,MAKEWPARAM(id,0),0);
        b->compileCommandReturned=1;
    }else if(b->operation!=ReadSource){Fail(b,15,L"Unknown operation");return;}
    Snapshot(b);
    DiagnosticsSnapshot(b);
    b->foregroundAfter=reinterpret_cast<uint64_t>(GetForegroundWindow());
}
static void GuardedProcess(Block* b) {
    __try{Process(b);}__except(EXCEPTION_EXECUTE_HANDLER){b->exceptionCode=GetExceptionCode();Fail(b,99,L"SEH exception during native bridge request; no automatic retry");}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK BridgeHook(int n,WPARAM wp,LPARAM lp) {
    if(n>=0&&!processing){
        auto message=reinterpret_cast<CWPSTRUCT*>(lp);
        static UINT request=RegisterWindowMessageW(kMessageName);
        if(message&&message->message==request){
            wchar_t name[256]{};
            if(GlobalGetAtomNameW(static_cast<ATOM>(message->wParam),name,256)&&wcsncmp(name,L"Local\\SC2NativeBridge-",21)==0){
                HANDLE mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);
                if(mapping){
                    auto b=static_cast<Block*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Block)));
                    if(b&&b->magic==kMagic&&b->version==4&&b->target==reinterpret_cast<uint64_t>(message->hwnd)&&!b->started){
                        processing=true;current=b;InterlockedExchange(&b->started,1);
                        HHOOK guard=SetWindowsHookExW(WH_CBT,FocusGuard,module,GetCurrentThreadId());
                        if(!guard)Fail(b,16,L"Cannot install thread-local focus/activation guard");else GuardedProcess(b);
                        if(guard)UnhookWindowsHookEx(guard);
                        b->foregroundAfter=reinterpret_cast<uint64_t>(GetForegroundWindow());
                        current=nullptr;processing=false;InterlockedExchange(&b->completed,1);
                    }
                    if(b)UnmapViewOfFile(b);CloseHandle(mapping);
                }
            }
        }
    }return CallNextHookEx(nullptr,n,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)module=h;return TRUE;}
