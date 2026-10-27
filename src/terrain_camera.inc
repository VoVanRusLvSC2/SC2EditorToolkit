// Original saved-camera preview and camera-editor readback, owned GUI thread only.
static UINT TerrainCameraCommand(HWND terrain,const wchar_t* wanted,bool* checked=nullptr){
    HMENU root=GetMenu(terrain);SendMessageW(terrain,WM_INITMENU,reinterpret_cast<WPARAM>(root),0);UINT found=0;
    for(int i=0;i<GetMenuItemCount(root);i++){
        wchar_t label[512]{};GetMenuStringW(root,i,label,512,MF_BYPOSITION);if(Clean(label)!=L"View")continue;
        HMENU view=GetSubMenu(root,i);SendMessageW(terrain,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(view),MAKELPARAM(i,FALSE));
        for(int j=0;j<GetMenuItemCount(view);j++){
            GetMenuStringW(view,j,label,512,MF_BYPOSITION);if(Clean(label)!=L"Camera")continue;
            HMENU menu=GetSubMenu(view,j);SendMessageW(terrain,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(menu),MAKELPARAM(j,FALSE));
            for(int k=0;k<GetMenuItemCount(menu);k++){
                GetMenuStringW(menu,k,label,512,MF_BYPOSITION);if(Clean(label)!=wanted)continue;
                auto state=GetMenuState(menu,k,MF_BYPOSITION);if(found||state&(MF_DISABLED|MF_GRAYED))return 0;
                found=GetMenuItemID(menu,k);if(checked)*checked=(state&MF_CHECKED)!=0;
            }
        }
    }return found;
}
static HWND CameraScalarControl(HWND dialog,int id,const wchar_t* followingClass=nullptr){
    HWND found=nullptr;for(HWND c:Children(dialog))if(Class(c)==L"Edit"&&GetDlgCtrlID(c)==id){
        if(followingClass){HWND next=GetWindow(c,GW_HWNDNEXT);if(!next||Class(next)!=L"msctls_updown32")continue;
            next=GetWindow(next,GW_HWNDNEXT);if(!next||Class(next)!=followingClass)continue;}
        if(found)return nullptr;found=c;
    }return found;
}
static bool CameraNumber(HWND dialog,int id,double& value,const wchar_t* followingClass=nullptr){
    HWND edit=CameraScalarControl(dialog,id,followingClass);if(!edit)return false;
    auto text=Text(edit);if(text.empty()||text.size()>64)return false;wchar_t* end=nullptr;value=wcstod(text.c_str(),&end);
    return end&&end!=text.c_str()&&!*end&&std::isfinite(value);
}
struct TerrainCameraTask {Block* b;bool done=false;ULONGLONG deadline;int stage=0;};
static thread_local TerrainCameraTask* terrainCameraTask;
static void CALLBACK TerrainCameraTimer(HWND,UINT,UINT_PTR,DWORD){
    auto t=terrainCameraTask;if(!t||t->done)return;auto b=t->b;HWND dialog=ExactRoot(L"Camera Editor");
    if(!dialog){if(GetTickCount64()>t->deadline){Fail(b,140,L"Original Camera Editor dialog not found");t->done=true;}return;}
    if(t->stage==0&&b->terrainCamera.enabled){
        auto& r=b->terrainCamera;
        struct Input{int id;double value;const wchar_t* following;};
        const Input inputs[]={{50,r.x,nullptr},{52,r.y,nullptr},{54,r.z,nullptr},{45,r.pitch,nullptr},{46,r.roll,nullptr},
                              {47,r.yaw,L"StaticImageClass"},{47,r.distance,L"Static"},{41,r.fov,nullptr}};
        HWND set=Control(dialog,L"Button",58);
        if(!set||Clean(Text(set))!=L"Set Game Camera"){Fail(b,157,L"Original Set Game Camera unavailable");t->stage=2;}
        else{
            bool valid=true;
            for(auto& input:inputs){
                HWND edit=CameraScalarControl(dialog,input.id,input.following);
                if(!edit){valid=false;break;}
                wchar_t text[64]{};swprintf_s(text,L"%.9f",input.value);
                SendMessageW(edit,WM_SETTEXT,0,reinterpret_cast<LPARAM>(text));
                SendMessageW(GetParent(edit),WM_COMMAND,MAKEWPARAM(input.id,EN_CHANGE),reinterpret_cast<LPARAM>(edit));
                SendMessageW(GetParent(edit),WM_COMMAND,MAKEWPARAM(input.id,EN_KILLFOCUS),reinterpret_cast<LPARAM>(edit));
            }
            if(!valid){Fail(b,157,L"Original camera input controls are ambiguous");t->stage=2;}
            else {t->stage=3;++b->commandsDispatched;SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(58,BN_CLICKED),reinterpret_cast<LPARAM>(set));return;}
        }
    }
    if(t->stage==3)t->stage=0;
    if(t->stage==0){
        HWND get=Control(dialog,L"Button",57);
        if(!get||Clean(Text(get))!=L"Get Game Camera"){Fail(b,144,L"Original current-camera readback command missing");t->stage=2;}
        else {t->stage=1;++b->commandsDispatched;SendMessageW(dialog,WM_COMMAND,MAKEWPARAM(57,BN_CLICKED),reinterpret_cast<LPARAM>(get));return;}
    }
    if(t->stage==1){
        auto& m=b->mapCamera;
        bool valid=CameraNumber(dialog,50,m.x)&&CameraNumber(dialog,52,m.y)&&CameraNumber(dialog,54,m.z)
            &&CameraNumber(dialog,45,m.pitch)&&CameraNumber(dialog,46,m.roll)
            &&CameraNumber(dialog,47,m.yaw,L"StaticImageClass")&&CameraNumber(dialog,47,m.distance,L"Static")&&CameraNumber(dialog,41,m.fov);
        if(valid&&m.distance>0&&m.fov>0&&m.fov<180)m.valuesRead=1;else Fail(b,145,L"Original camera parameters could not be read uniquely");
        Log(b,L"map camera name=%s target=%.6f,%.6f,%.6f pitch=%.6f yaw=%.6f roll=%.6f distance=%.6f fov=%.6f read=%u\n",m.name,m.x,m.y,m.z,m.pitch,m.yaw,m.roll,m.distance,m.fov,m.valuesRead);
    }
    // Cancel restores the pre-dialog camera, including a Set Game Camera
    // preview. Commit a successful explicit view change with the original OK.
    bool commit=b->terrainCamera.enabled&&!b->error;
    int closeId=commit?11:12;HWND cancel=Control(dialog,L"Button",closeId);
    if(!cancel||Clean(Text(cancel))!=(commit?L"OK":L"Cancel")){
        Fail(b,146,L"Original camera dialog cancellation unavailable");t->done=true;PostMessageW(dialog,WM_CLOSE,0,0);return;
    }
    t->done=true;PostMessageW(dialog,WM_COMMAND,MAKEWPARAM(closeId,BN_CLICKED),reinterpret_cast<LPARAM>(cancel));
}
static void RunTerrainCameraDialog(Block* b,HWND terrain);
static void TerrainCameraOperation(Block* b,HWND terrain){
    if(!b->camera[0]&&!b->terrainCamera.enabled&&b->operation!=TerrainCameraRead){Fail(b,147,L"Explicit saved camera or custom parameters required");return;}
    if(ExactRoot(L"Camera Editor")){Fail(b,148,L"A pre-existing camera dialog blocks selection");return;}
    if(b->terrainCamera.enabled||b->operation==TerrainCameraRead){
        b->mapCamera.selected=1;wcsncpy_s(b->mapCamera.name,L"Current Terrain Camera",_TRUNCATE);
        RunTerrainCameraDialog(b,terrain);return;
    }
    if(b->operation==TerrainCameraLayer){
        auto layer=FindCommand(terrain,{L"Layer"},{L"Cameras"});if(!layer){Fail(b,143,L"Original Cameras layer missing");return;}
        ++b->commandsDispatched;SendMessageW(terrain,WM_COMMAND,layer,0);
        // Return to the Editor's outer loop before resolving its new palette.
        return;
    }
    HWND list=Control(terrain,L"SysListView32",927);if(!list||!IsWindowVisible(list)){Fail(b,149,L"Original saved-camera palette unavailable");return;}
    // The Editor's selection binding belongs to the focused palette. Focus is
    // logical and confined to this owned private desktop.
    SetFocus(list);b->privateFocusUsed=1;
    int count=int(SendMessageW(list,LVM_GETITEMCOUNT,0,0)),match=-1;if(count<1||count>4096){Fail(b,150,L"Saved-camera palette is empty or exceeds the supported bound");return;}
    for(int row=0;row<count;row++){
        wchar_t text[1024]{};LVITEMW item{};item.pszText=text;item.cchTextMax=1024;SendMessageW(list,LVM_GETITEMTEXTW,row,reinterpret_cast<LPARAM>(&item));
        if(text==std::wstring(b->camera)){if(match!=-1){Fail(b,151,L"Ambiguous native camera name; selection refused");return;}match=row;}
    }
    if(match<0){Fail(b,152,L"Exact saved camera was not found in original palette");return;}
    LVITEMW selected{};selected.stateMask=LVIS_SELECTED|LVIS_FOCUSED;
    LVITEMW data{};data.mask=LVIF_PARAM;data.iItem=match;SendMessageW(list,LVM_GETITEMW,0,reinterpret_cast<LPARAM>(&data));
    if(b->operation==TerrainCameraSelect){
    bool autoPreview=false;auto previewCommand=TerrainCameraCommand(terrain,L"Auto Preview Cameras",&autoPreview);
    if(previewCommand&&autoPreview){++b->commandsDispatched;SendMessageW(terrain,WM_COMMAND,previewCommand,0);}
    SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&selected));
    SendMessageW(list,LVM_SETSELECTIONMARK,0,match);selected.state=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,match,reinterpret_cast<LPARAM>(&selected));
    if(SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0)!=1){Fail(b,155,L"Native camera palette selection was not confirmed");return;}
    // Native list selection notifications are emitted by the control. Commit
    // its active item with a control activation notification, without input.
    SendMessageW(list,LVM_ENSUREVISIBLE,match,FALSE);
    RECT label{};label.left=LVIR_LABEL;SendMessageW(list,LVM_GETITEMRECT,match,reinterpret_cast<LPARAM>(&label));
    NMITEMACTIVATE activate{};activate.hdr.hwndFrom=list;activate.hdr.idFrom=927;activate.hdr.code=LVN_ITEMACTIVATE;
    activate.iItem=match;activate.iSubItem=0;activate.lParam=data.lParam;
    activate.ptAction={(label.left+label.right)/2,(label.top+label.bottom)/2};
    SendMessageW(GetParent(list),WM_NOTIFY,927,reinterpret_cast<LPARAM>(&activate));
    // The command enablement/document binding is updated by the outer loop.
    return;
    }
    if(SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0)!=1||!(SendMessageW(list,LVM_GETITEMSTATE,match,LVIS_SELECTED)&LVIS_SELECTED)){
        Fail(b,155,L"Saved camera selection changed before native view command");return;
    }
    b->mapCamera.selected=1;wcsncpy_s(b->mapCamera.name,b->camera,_TRUNCATE);
    HWND view=nullptr;for(HWND c:Children(terrain))if(Class(c)==L"Button"&&GetDlgCtrlID(c)==922&&IsWindowVisible(c)){
        if(view){Fail(b,153,L"Ambiguous visible View Selected Camera controls");return;}view=c;
    }
    Log(b,L"camera binding list=%p parent=%p row=%d data=%p selected=%lld view=%p enabled=%d text=%s\n",list,GetParent(list),match,reinterpret_cast<void*>(data.lParam),SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0),view,view?IsWindowEnabled(view):0,view?Text(view).c_str():L"");
    for(HWND c:Children(terrain))if(Class(c)==L"Static"&&Text(c).rfind(L"Selection:",0)==0)Log(b,L"camera document %s\n",Text(c).c_str());
    if(!view||Clean(Text(view))!=L"View Selected Camera"){Fail(b,153,L"Original View Selected Camera command unavailable");return;}
    // Enablement reflects the viewport selection, which can lag the palette.
    // The exact selected row is checked above; the original command resolves
    // that row. Its result must also pass independent numeric readback.
    ++b->commandsDispatched;SendMessageW(GetParent(view),WM_COMMAND,MAKEWPARAM(922,BN_CLICKED),reinterpret_cast<LPARAM>(view));
    // Clear only editor selection after applying the camera, removing its
    // manipulator from the shot. This does not edit the saved camera record.
    selected.state=0;SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&selected));
    SendMessageW(list,LVM_SETSELECTIONMARK,0,-1);
    RunTerrainCameraDialog(b,terrain);
}
static void RunTerrainCameraDialog(Block* b,HWND terrain){
    UINT command=TerrainCameraCommand(terrain,L"Camera Editor");if(!command){Fail(b,141,L"Original Terrain Camera Editor command missing");return;}
    HMODULE pinned=nullptr;if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&TerrainCameraTimer),&pinned)){Fail(b,142,L"Cannot retain camera callback lifetime");return;}
    TerrainCameraTask task{b,false,GetTickCount64()+10000};terrainCameraTask=&task;auto timer=SetTimer(nullptr,0,100,TerrainCameraTimer);
    if(!timer){terrainCameraTask=nullptr;Fail(b,142,L"Camera task timer unavailable");return;}
    ++b->commandsDispatched;SendMessageW(terrain,WM_COMMAND,command,0);
    while(!task.done){MSG m{};int pumped=0;while(pumped++<100&&PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){
        if(m.message==WM_QUIT){PostQuitMessage(int(m.wParam));Fail(b,156,L"Editor exited during camera selection");task.done=true;break;}TranslateMessage(&m);DispatchMessageW(&m);
    }MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);}
    KillTimer(nullptr,timer);terrainCameraTask=nullptr;
}
