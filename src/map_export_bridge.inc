// Original Map Image Export on the owned GUI thread. A private TGA is produced
// by CMapImageGenerator; the API losslessly encodes its pixels as PNG.
#include "map_export_paths.h"
#include "map_export_flags.h"
struct MapExportTask {
    Block* b;HWND terrain,dialog=nullptr,chooser=nullptr;ULONGLONG deadline;
    int stage=0;bool done=false,submitting=false,browseReturned=false;ULONGLONG chooserDeadline=0,submitAfter=0;HWND filename=nullptr;
    MapExportFlags flags;
};
static thread_local MapExportTask* mapExportTask;
static HWND MapButton(HWND dialog,int id,const wchar_t* label){
    HWND c=Control(dialog,L"Button",id);return c&&Clean(Text(c))==label?c:nullptr;
}
static bool MapClick(HWND dialog,int id,const wchar_t* label){
    HWND c=MapButton(dialog,id,label);if(!c||!IsWindowEnabled(c))return false;
    SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(id,BN_CLICKED),reinterpret_cast<LPARAM>(c));return true;
}
static bool MapCheck(HWND dialog,int id,const wchar_t* label,bool enabled){
    HWND c=MapButton(dialog,id,label);if(!c)return false;
    if((SendMessageW(c,BM_GETCHECK,0,0)==BST_CHECKED)!=enabled){
        if(!IsWindowEnabled(c))return false;
        SendMessageW(c,BM_SETCHECK,enabled?BST_CHECKED:BST_UNCHECKED,0);
        SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(id,BN_CLICKED),reinterpret_cast<LPARAM>(c));
    }
    return (SendMessageW(c,BM_GETCHECK,0,0)==BST_CHECKED)==enabled;
}
static bool MapRadio(HWND dialog,int first,int last,int selected,const wchar_t* label){
    HWND c=MapButton(dialog,selected,label);if(!c||!IsWindowEnabled(c))return false;
    CheckRadioButton(dialog,first,last,selected);
    SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(selected,BN_CLICKED),reinterpret_cast<LPARAM>(c));
    return SendMessageW(c,BM_GETCHECK,0,0)==BST_CHECKED;
}
static bool MapEdit(HWND dialog,int id,const std::wstring& text){
    HWND c=Control(dialog,L"Edit",id);if(!c||!IsWindowEnabled(c))return false;
    SetWindowTextW(c,text.c_str());
    SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(id,EN_KILLFOCUS),reinterpret_cast<LPARAM>(c));
    auto actual=Text(c);if(actual.empty())return false;
    return actual==text||wcstod(actual.c_str(),nullptr)==wcstod(text.c_str(),nullptr);
}
static bool MapCombo(HWND dialog,int id,const wchar_t* label){
    HWND c=Control(dialog,L"ComboBox",id);if(!c||!IsWindowEnabled(c))return false;
    int found=-1;auto count=SendMessageW(c,CB_GETCOUNT,0,0);if(count<0||count>256)return false;
    for(int i=0;i<count;i++){
        auto length=SendMessageW(c,CB_GETLBTEXTLEN,i,0);if(length<0||length>511)return false;
        wchar_t text[512]{};SendMessageW(c,CB_GETLBTEXT,i,reinterpret_cast<LPARAM>(text));
        if(text==std::wstring(label)){if(found!=-1)return false;found=i;}
    }
    if(found<0)return false;SendMessageW(c,CB_SETCURSEL,found,0);
    SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(id,CBN_SELCHANGE),reinterpret_cast<LPARAM>(c));
    return Text(c)==label;
}
static bool MapTreeFlag(MapExportTask* task,const wchar_t* label,bool wanted,bool apply=true,uint32_t* readback=nullptr){
    HWND dialog=task->dialog;auto b=task->b;
    HWND tree=Control(dialog,L"SysTreeView32",42);if(!tree||!IsWindowEnabled(tree))return false;
    HTREEITEM found=nullptr;std::vector<HTREEITEM> pending;
    pending.push_back(reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_ROOT,0)));
    int count=0;
    while(!pending.empty()&&count<256){
        auto item=pending.back();pending.pop_back();if(!item)continue;++count;
        wchar_t text[512]{};TVITEMW row{};row.mask=TVIF_TEXT;row.hItem=item;row.pszText=text;row.cchTextMax=512;
        SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row));
        if(text==std::wstring(label)){if(found)return false;found=item;}
        pending.push_back(reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(item))));
        pending.push_back(reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_CHILD,reinterpret_cast<LPARAM>(item))));
    }
    if(!found||!pending.empty()){Log(b,L"map-export missing/ambiguous option=%s\n",label);return false;}
    TVITEMW row{};row.mask=TVIF_STATE|TVIF_PARAM;row.stateMask=TVIS_STATEIMAGEMASK;row.hItem=found;
    if(!SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row)))return false;
    auto index=(row.state&TVIS_STATEIMAGEMASK)>>12;if(index!=1&&index!=2)return false;
    bool native=false;
    if(!task->flags.Value(found,apply,wanted,&native)){
        Log(b,L"map-export native flag not confirmed option=%s wanted=%d\n",label,wanted);return false;
    }
    if(readback)*readback=native?1u:0u;
    if((index==2)!=wanted){
        if(!apply)return false;
        row.mask=TVIF_STATE;row.state=INDEXTOSTATEIMAGEMASK(wanted?2:1);
        if(!SendMessageW(tree,TVM_SETITEMW,0,reinterpret_cast<LPARAM>(&row)))return false;
    }
    row.mask=TVIF_STATE;row.state=0;
    if(!SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row)))return false;
    bool actual=((row.state&TVIS_STATEIMAGEMASK)>>12)==2;
    Log(b,L"map-export option=%s checkbox=%d nativeFlag=%d apply=%d\n",label,actual,native,apply);return actual==wanted&&native==wanted;
}
static bool ConfigureMapExport(MapExportTask* task){
    HWND w=task->dialog;auto b=task->b;
    bool ok=MapRadio(w,14,15,14,L"Save To Disk:")&&MapCheck(w,18,L"Use As Minimap",false)
        &&MapRadio(w,25,27,26,L"Full")&&MapCheck(w,21,L"Based On Bounds",false)&&MapCheck(w,24,L"Based On Bounds",true)
        &&MapCombo(w,28,L"(All)")&&MapEdit(w,29,L"90.0")&&MapEdit(w,31,L"0.0")
        &&MapEdit(w,19,std::to_wstring(b->terrain.size))&&MapRadio(w,37,39,39,L"Custom:")&&MapClick(w,40,L"Copy Game");
    if(!ok)return false;
    if(!task->flags.Bind(Control(w,L"SysTreeView32",42))){Log(b,L"map-export flag-model adapter not verified reason=%u candidates=%u profile=%u rows=%u scanned=%llu row=%u id=%u alias=%d parameter=%lld visible=%u\n",task->flags.Reason(),task->flags.Hits(),task->flags.Profile(),task->flags.Count(),static_cast<unsigned long long>(task->flags.Scanned()),task->flags.Row(),task->flags.Id(),task->flags.Alias(),static_cast<long long>(task->flags.Parameter()),task->flags.Visible());return false;}
    for(auto flag:{L"Terrain",L"Water",L"Shadows"})if(!MapTreeFlag(task,flag,true))return false;
    if(!MapTreeFlag(task,L"Units",b->terrain.includeUnits!=0)||!MapTreeFlag(task,L"Doodads",b->terrain.includeDoodads!=0))return false;
    for(auto flag:{L"Fog Effects",L"Editor Helper Models",L"Editor-Only Models",L"Bounds",L"Base Height",L"Cameras",L"Points",L"Regions"})if(!MapTreeFlag(task,flag,false))return false;
    if(!MapCombo(w,43,L"None")||!MapCombo(w,44,L"Game")||!MapCombo(w,45,L"Standard")||!MapCombo(w,46,L"All")||!MapCombo(w,47,L"(All Players)"))return false;
    if(!MapRadio(w,37,39,39,L"Custom:"))return false;
    b->terrain.customOptions=SendMessageW(MapButton(w,39,L"Custom:"),BM_GETCHECK,0,0)==BST_CHECKED;
    b->terrain.filtersConfirmed=MapTreeFlag(task,L"Units",b->terrain.includeUnits!=0,false,&b->terrain.actualUnits)&&MapTreeFlag(task,L"Doodads",b->terrain.includeDoodads!=0,false,&b->terrain.actualDoodads)&&MapTreeFlag(task,L"Terrain",true,false)&&MapTreeFlag(task,L"Water",true,false);
    if(!b->terrain.filtersConfirmed||!b->terrain.customOptions)return false;
    auto height=wcstoul(Text(Control(w,L"Edit",22)).c_str(),nullptr,10);
    if(height<64||height>8192||uint64_t(height)*b->terrain.size>32*1024*1024){Log(b,L"map-export dimensions exceed the bounded image budget\n");return false;}
    b->terrain.fullMap=SendMessageW(MapButton(w,26,L"Full"),BM_GETCHECK,0,0)==BST_CHECKED&&Text(Control(w,L"ComboBox",28))==L"(All)";
    b->terrain.topDown=wcstod(Text(Control(w,L"Edit",29)).c_str(),nullptr)==90.0;
    b->terrain.optionsConfirmed=b->terrain.fullMap&&b->terrain.topDown&&b->terrain.filtersConfirmed&&b->terrain.customOptions&&wcstoul(Text(Control(w,L"Edit",19)).c_str(),nullptr,10)==b->terrain.size;
    Log(b,L"map-export native configuration width=%s height=%s angle=%s full=%u topDown=%u\n",Text(Control(w,L"Edit",19)).c_str(),Text(Control(w,L"Edit",22)).c_str(),Text(Control(w,L"Edit",29)).c_str(),b->terrain.fullMap,b->terrain.topDown);
    return b->terrain.optionsConfirmed!=0;
}
static void CALLBACK MapExportTimer(HWND,UINT,UINT_PTR,DWORD){
    auto task=mapExportTask;if(!task||task->done)return;auto b=task->b;
    if(GetTickCount64()>task->deadline){
        Fail(b,90,L"Original map image export timed out");
        if(task->chooser&&IsWindow(task->chooser))CancelLoadDialog(task->chooser);
        if(task->dialog&&IsWindow(task->dialog))CancelLoadDialog(task->dialog);
        task->done=true;return;
    }
    if(task->stage==0){
        HWND w=ExactRoot(L"Map Image Export");if(!w||!IsWindowEnabled(w))return;
        task->dialog=w;task->stage=1;
        if(!ConfigureMapExport(task)){Fail(b,91,L"Original map image export settings unavailable or readback mismatched");CancelLoadDialog(w);task->done=true;return;}
        task->stage=2;task->chooserDeadline=GetTickCount64()+30000;
        if(!MapClick(w,16,L"Browse...")){Fail(b,92,L"Original image output Browse command missing");CancelLoadDialog(w);task->done=true;return;}
        task->browseReturned=true;return;
    }
    if(task->stage==2){
        for(HWND w:Roots())if(w!=task->dialog&&Class(w)==L"#32770"&&IsWindowVisible(w)&&IsWindowEnabled(w)){
            HWND edit=GetDlgItem(w,1148);if(!edit)edit=GetDlgItem(w,1152);
            // Windows' modern IFileSaveDialog nests the file-name Edit (1001)
            // inside DirectUI. Resolve the unique control in this dialog only.
            if(!edit&&Text(w)==L"Choose File")edit=Control(w,L"Edit",1001);
            if(!edit)continue;
            bool owned=false;for(HWND owner=GetWindow(w,GW_OWNER);owner;owner=GetWindow(owner,GW_OWNER))if(owner==task->dialog)owned=true;
            // Some native Editor dialogs use the shared modal-parent HWND.
            // This exact chooser can only be accepted during our Browse call,
            // while the already verified export form is disabled, on this GUI
            // thread and private desktop; no pre-existing chooser is repurposed.
            if(!owned&&Text(w)==L"Choose File"&&!IsWindowEnabled(task->dialog))owned=true;
            if(!owned)continue;task->chooser=w;task->filename=edit;task->stage=20;task->submitAfter=GetTickCount64()+200;
            Log(b,L"map-export save dialog=%s path=%s\n",Text(w).c_str(),b->mapPath);
            SetWindowTextW(edit,b->mapPath);return;
        }
        if(GetTickCount64()>task->chooserDeadline){
            Fail(b,98,L"Unsupported or unavailable native image save dialog");
            for(HWND w:Roots())if(Text(w)==L"Choose File"&&IsWindowVisible(w)&&IsWindowEnabled(w))CancelLoadDialog(w);
            if(IsWindow(task->dialog))CancelLoadDialog(task->dialog);task->done=true;
        }
        return;
    }
    if(task->stage==20){
        if(GetTickCount64()<task->submitAfter)return;
        Log(b,L"map-export filename readback=%s\n",Text(task->filename).c_str());
        if(MapNormalizedPath(Text(task->filename))!=MapNormalizedPath(b->mapPath)){
            Fail(b,100,L"Native save filename did not accept this exact private path");CancelLoadDialog(task->chooser);CancelLoadDialog(task->dialog);task->done=true;return;
        }
        task->stage=3;task->chooserDeadline=GetTickCount64()+30000;
        HWND save=Control(task->chooser,L"Button",IDOK);
        SendMessageW(task->chooser,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),reinterpret_cast<LPARAM>(save));return;
    }
    if(task->stage==3){
        if(task->chooser&&IsWindow(task->chooser)&&IsWindowVisible(task->chooser)&&GetTickCount64()>task->chooserDeadline){Fail(b,101,L"Native file chooser did not accept the destination");CancelLoadDialog(task->chooser);CancelLoadDialog(task->dialog);task->done=true;return;}
        if(!task->browseReturned||!IsWindowEnabled(task->dialog))return;
        if(task->chooser&&IsWindow(task->chooser)&&IsWindowVisible(task->chooser))return;
        bool pathConfirmed=false;
        for(HWND c:Children(task->dialog))if(Class(c)==L"Static"){
            auto text=Text(c);if(!text.empty())Log(b,L"map-export destination label=%s\n",text.c_str());
            if(MapDisplayMatches(text,b->mapPath))pathConfirmed=true;
        }
        if(!pathConfirmed){Fail(b,93,L"Native export destination did not match this job's private output");CancelLoadDialog(task->dialog);task->done=true;return;}
        HWND ok=MapButton(task->dialog,11,L"OK");if(!ok||!IsWindowEnabled(ok)){Fail(b,94,L"Original map image export OK unavailable");task->done=true;return;}
        task->stage=4;task->submitting=true;
        ++b->commandsDispatched;SendMessageW(task->dialog,WM_COMMAND,MAKEWPARAM(11,BN_CLICKED),reinterpret_cast<LPARAM>(ok));
        task->submitting=false;return;
    }
    if(task->stage==4&&!task->submitting){
        if(IsWindow(task->dialog)&&IsWindowVisible(task->dialog))return;
        std::error_code error;auto size=std::filesystem::file_size(b->mapPath,error);
        if(error||size<18){Fail(b,95,L"Original map exporter returned without a complete image file");task->done=true;return;}
        b->terrain.exported=1;Log(b,L"map-export original exporter returned; native file bytes=%llu\n",static_cast<unsigned long long>(size));task->done=true;
    }
}
static void ExportWholeMap(Block* b,HWND terrain){
    std::filesystem::path output(b->mapPath);
    if(!output.is_absolute()||output.extension()!=L".tga"||std::filesystem::exists(output)||!std::filesystem::is_directory(output.parent_path())){Fail(b,86,L"Fresh absolute private .tga output path required");return;}
    if(b->terrain.size!=512&&b->terrain.size!=1024&&b->terrain.size!=2048&&b->terrain.size!=4096){Fail(b,87,L"Unsupported native map image size");return;}
    if(ExactRoot(L"Map Image Export")){Fail(b,88,L"An existing map image export dialog blocks this job");return;}
    UINT command=FindCommand(terrain,{L"Data"},{L"Export Map Image..."});if(!command){Fail(b,89,L"Original Export Map Image command unavailable");return;}
    HMODULE pinned=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&MapExportTimer),&pinned)||!pinned){Fail(b,102,L"Cannot retain native map export callback lifetime");return;}
    MapExportTask task{b,terrain,nullptr,nullptr,GetTickCount64()+600000};mapExportTask=&task;
    auto timer=SetTimer(nullptr,0,50,MapExportTimer);if(!timer){mapExportTask=nullptr;Fail(b,96,L"Cannot create native map image task timer");return;}
    ++b->commandsDispatched;SendMessageW(terrain,WM_COMMAND,command,0);
    while(!task.done){
        MSG message{};int count=0;
        while(count++<100&&PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
            if(message.message==WM_QUIT){PostQuitMessage(static_cast<int>(message.wParam));Fail(b,97,L"Editor exited during map export");task.done=true;break;}
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);
    }
    KillTimer(nullptr,timer);mapExportTask=nullptr;
}
