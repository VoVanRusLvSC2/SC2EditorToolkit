// Executes only on the original GUI thread, on our private desktop.
static HWND SceneRoot(){HWND found=nullptr;for(HWND w:Roots())if(Text(w).rfind(L"Cutscenes - [",0)==0&&IsWindowVisible(w)){if(found)return nullptr;found=w;}return found;}
static void SceneTreeDump(Block* b,HWND tree,HTREEITEM item,int depth,int& count){
    while(item&&count++<100&&depth<16){wchar_t text[1024]{};TVITEMW row{};row.mask=TVIF_TEXT;row.hItem=item;row.pszText=text;row.cchTextMax=1024;SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row));
        Log(b,L"scene tree=%d depth=%d item=%p text=%s\n",GetDlgCtrlID(tree),depth,item,text);
        SceneTreeDump(b,tree,reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_CHILD,reinterpret_cast<LPARAM>(item))),depth+1,count);
        item=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(item)));
    }
}
static void SceneSnapshot(Block* b,HWND scene){
    if(!scene){Fail(b,51,L"Unique native Cutscenes window missing");return;}
    Log(b,L"scene title=%s\n",Text(scene).c_str());
    std::wstring status;
    for(HWND c:Children(scene)){
        auto cls=Class(c),text=Text(c);int id=GetDlgCtrlID(c);
        if(b->operation!=SceneAdvance&&IsWindowVisible(c))Log(b,L"scene control hwnd=%p class=%s id=%d text=%s\n",c,cls.c_str(),id,text.c_str());
        if(cls==L"Static"&&text.rfind(L"Scene Time:",0)==0)status+=text+L"; ";
        if(cls==L"Static"&&text.rfind(L"Camera:",0)==0)status+=text+L"; ";
        if(cls==L"GfxViewClass"&&id==22)b->viewport=reinterpret_cast<uint64_t>(c);
        if(b->operation!=SceneAdvance&&cls==L"SysTreeView32"&&(id==33||id==44)){int count=0;SceneTreeDump(b,c,reinterpret_cast<HTREEITEM>(SendMessageW(c,TVM_GETNEXTITEM,TVGN_ROOT,0)),0,count);}
    }
    wcsncpy_s(b->sceneStatus,status.c_str(),_TRUNCATE);
}
static UINT SceneCameraCommand(HWND scene,const std::wstring& wanted){
    HMENU root=GetMenu(scene);SendMessageW(scene,WM_INITMENU,reinterpret_cast<WPARAM>(root),0);
    UINT found=0;
    for(int i=0;i<GetMenuItemCount(root);i++){
        wchar_t label[512]{};GetMenuStringW(root,i,label,512,MF_BYPOSITION);if(Clean(label)!=L"View")continue;
        HMENU view=GetSubMenu(root,i);SendMessageW(scene,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(view),MAKELPARAM(i,FALSE));
        for(int j=0;j<GetMenuItemCount(view);j++){
            GetMenuStringW(view,j,label,512,MF_BYPOSITION);if(Clean(label)!=L"Camera")continue;
            HMENU cameras=GetSubMenu(view,j);SendMessageW(scene,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(cameras),MAKELPARAM(j,FALSE));
            for(int k=0;k<GetMenuItemCount(cameras);k++){
                GetMenuStringW(cameras,k,label,512,MF_BYPOSITION);auto text=Clean(label);
                if(text!=wanted&&text.rfind(wanted+L": ",0)!=0)continue;
                if(found||GetMenuState(cameras,k,MF_BYPOSITION)&(MF_DISABLED|MF_GRAYED))return 0;
                found=GetMenuItemID(cameras,k);
            }
        }
    }return found;
}
struct SceneSeekTask {Block* b;HWND scene;UINT_PTR timer;ULONGLONG deadline;int stage=0;double last=-1;bool waiting=false;ULONGLONG progress=GetTickCount64();};
static thread_local SceneSeekTask* sceneSeekTask;
static double SceneTime(HWND scene){for(HWND c:Children(scene))if(Class(c)==L"Static"){auto text=Text(c);if(text.rfind(L"Scene Time: ",0)==0)return wcstod(text.c_str()+12,nullptr);}return -1;}
static bool CheckedCommand(HMENU menu,UINT command){for(int i=0;i<GetMenuItemCount(menu);i++){if(GetMenuItemID(menu,i)==command)return (GetMenuState(menu,i,MF_BYPOSITION)&MF_CHECKED)!=0;auto sub=GetSubMenu(menu,i);if(sub&&CheckedCommand(sub,command))return true;}return false;}
static UINT SceneNestedCommand(HWND scene,const wchar_t* parent,const wchar_t* group,const wchar_t* wanted){
    HMENU root=GetMenu(scene);SendMessageW(scene,WM_INITMENU,reinterpret_cast<WPARAM>(root),0);
    for(int i=0;i<GetMenuItemCount(root);i++){
        wchar_t label[512]{};GetMenuStringW(root,i,label,512,MF_BYPOSITION);if(Clean(label)!=parent)continue;
        HMENU sub=GetSubMenu(root,i);SendMessageW(scene,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(sub),MAKELPARAM(i,FALSE));
        for(int j=0;j<GetMenuItemCount(sub);j++){
            GetMenuStringW(sub,j,label,512,MF_BYPOSITION);if(Clean(label)!=group)continue;
            HMENU items=GetSubMenu(sub,j);SendMessageW(scene,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(items),MAKELPARAM(j,FALSE));
            UINT found=0;for(int k=0;k<GetMenuItemCount(items);k++){GetMenuStringW(items,k,label,512,MF_BYPOSITION);if(Clean(label)==wanted){if(found||GetMenuState(items,k,MF_BYPOSITION)&(MF_DISABLED|MF_GRAYED))return 0;found=GetMenuItemID(items,k);}}return found;
        }
    }return 0;
}
static void FinishSceneSeek(SceneSeekTask* task){
    auto b=task->b;KillTimer(nullptr,task->timer);SceneSnapshot(b,task->scene);
    b->foregroundAfter=reinterpret_cast<uint64_t>(GetForegroundWindow());sceneSeekTask=nullptr;delete task;
    InterlockedExchange(&b->completed,1);UnmapViewOfFile(b);
}
static void CALLBACK SceneSeekTimer(HWND,UINT,UINT_PTR,DWORD){
    auto task=sceneSeekTask;if(!task)return;auto b=task->b;auto scene=task->scene;
    if(!IsWindow(scene)||GetTickCount64()>task->deadline){Fail(b,59,L"Native scene seek timed out");FinishSceneSeek(task);return;}
    if(task->stage==0){
        if(b->operation==SceneAdvance){
            UINT camera=SceneCameraCommand(scene,b->camera);
            if(!camera||!CheckedCommand(GetMenu(scene),camera)){Fail(b,62,L"Advance requires the same selected native camera");FinishSceneSeek(task);return;}
            if(SceneTime(scene)>b->timeMs/1000.0+0.021){Fail(b,63,L"Advance cannot seek backwards");FinishSceneSeek(task);return;}
            task->stage=2;return;
        }
        UINT size=SceneNestedCommand(scene,L"View",L"Viewport Size",L"1280x720");if(size){SendMessageW(scene,WM_COMMAND,size,0);++b->commandsDispatched;}
        UINT helpers=SceneNestedCommand(scene,L"Render",L"Show Helpers",L"Show All Helpers");
        if(helpers&&CheckedCommand(GetMenu(scene),helpers)){SendMessageW(scene,WM_COMMAND,helpers,0);++b->commandsDispatched;}
        UINT restart=FindCommand(scene,{L"Animation"},{L"Restart Scene"});
        if(!restart){Fail(b,58,L"Native Restart unavailable");FinishSceneSeek(task);return;}
        SendMessageW(scene,WM_COMMAND,restart,0);++b->commandsDispatched;task->stage=1;return;
    }
    if(task->stage==1){
        if(SceneTime(scene)>0.021)return;
        UINT camera=SceneCameraCommand(scene,b->camera);
        if(!camera){Fail(b,58,L"Camera absent or ambiguous");FinishSceneSeek(task);return;}
        SendMessageW(scene,WM_COMMAND,camera,0);++b->commandsDispatched;task->stage=2;return;
    }
    double now=SceneTime(scene),target=b->timeMs/1000.0;
    if(now<0)return;
    if(fabs(now-target)<=0.021){
        b->timeConfirmed=1;b->actualTimeMs=static_cast<int64_t>(llround(now*1000));UINT camera=SceneCameraCommand(scene,b->camera);b->cameraConfirmed=camera&&CheckedCommand(GetMenu(scene),camera);
        if(!b->cameraConfirmed)Fail(b,59,L"Requested native camera is not selected");
        FinishSceneSeek(task);return;
    }
    if(now>target+0.021){Fail(b,59,L"Native timeline passed the requested frame");FinishSceneSeek(task);return;}
    if(task->waiting&&now<=task->last+0.005){
        if(GetTickCount64()-task->progress>15000){Fail(b,64,L"Native timeline stopped advancing before the requested time");FinishSceneSeek(task);}return;
    }
    UINT next=FindCommand(scene,{L"Animation"},{L"Next Frame"});
    if(!next){Fail(b,58,L"Native Next Frame unavailable");FinishSceneSeek(task);return;}
    task->last=now;task->waiting=true;task->progress=GetTickCount64();SendMessageW(scene,WM_COMMAND,next,0);++b->commandsDispatched;
}
static void BeginSceneSeek(Block* b,HWND scene){
    if(sceneSeekTask){Fail(b,60,L"Another native scene seek owns this GUI thread");return;}
    // A timer callback outlives the hook invocation. Keep its code loaded until
    // this owned worker exits, including the few instructions after completion.
    HMODULE pinned=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&BeginSceneSeek),&pinned)){
        Fail(b,55,L"Cannot retain native scene callback module");return;
    }
    auto task=new SceneSeekTask{b,scene,0,GetTickCount64()+60000+static_cast<ULONGLONG>(b->timeMs)*3};
    task->timer=SetTimer(nullptr,0,40,SceneSeekTimer);
    if(!task->timer){delete task;Fail(b,55,L"Cannot schedule native scene seek");return;}
    sceneSeekTask=task;
}
struct SceneLoadTask {Block* b;HWND scene;ULONGLONG deadline;HWND dialog=nullptr;bool submitted=false;};
static thread_local SceneLoadTask* sceneLoadTask;
static void CALLBACK SceneLoadTimer(HWND,UINT,UINT_PTR,DWORD){
    auto task=sceneLoadTask;if(!task)return;
    for(HWND w:Roots())if(w!=task->scene&&Class(w)==L"#32770"&&IsWindowVisible(w)&&IsWindowEnabled(w)){
        for(HWND c:Children(w))if(Class(c)==L"Static"&&Text(c)==L"Do you want to add the new cutscene to your document?"){
            // Open as a loose file with the current dependency context. Do not
            // add it to (or dirty) even the worker's private map document.
            task->dialog=w;SendMessageW(w,WM_COMMAND,IDNO,0);return;
        }
        if(!task->dialog){task->dialog=w;Log(task->b,L"scene import dialog title=%s\n",Text(w).c_str());for(HWND c:Children(w))Log(task->b,L"scene dialog control class=%s id=%d text=%s\n",Class(c).c_str(),GetDlgCtrlID(c),Text(c).c_str());}
        HWND edit=GetDlgItem(w,1148);if(!edit)edit=GetDlgItem(w,1152);
        if(edit&&!task->submitted){SetWindowTextW(edit,task->b->mapPath);task->submitted=true;SendMessageW(w,WM_COMMAND,IDOK,0);return;}
    }
    if(GetTickCount64()>task->deadline){task->submitted=true;Fail(task->b,52,L"Native cutscene import dialog unsupported or timed out");if(task->dialog)CancelLoadDialog(task->dialog);}
}
static void SceneOperation(Block* b){
    if(!PrivateDesktop()){Fail(b,53,L"Cutscene operations require the owned private desktop");return;}
    HWND scene=SceneRoot();if(!scene){Fail(b,51,L"Open the Cutscenes module first");return;}
    if(!IsWindowEnabled(scene)){Fail(b,61,L"A modal dialog blocks the owned Cutscenes module");return;}
    SetActiveWindow(scene);SetFocus(scene);b->privateFocusUsed=1;
    if(b->operation==SceneLoad){
        UINT id=FindCommand(scene,{L"File"},{L"Import Cutscene File..."});
        if(!id||!std::filesystem::is_regular_file(b->mapPath)){Fail(b,54,L"Existing cutscene and original Import command required");return;}
        SceneLoadTask task{b,scene,GetTickCount64()+30000};sceneLoadTask=&task;
        UINT_PTR timer=SetTimer(nullptr,0,100,SceneLoadTimer);
        if(!timer){sceneLoadTask=nullptr;Fail(b,55,L"Cannot create scene import task timer");return;}
        ++b->commandsDispatched;SendMessageW(scene,WM_COMMAND,id,0);
        KillTimer(nullptr,timer);sceneLoadTask=nullptr;
        auto title=Text(scene);auto stem=std::filesystem::path(b->mapPath).stem().wstring();
        b->sceneLoaded=task.submitted&&title.find(stem)!=std::wstring::npos;
        if(!b->error&&!b->sceneLoaded)Fail(b,56,L"Import returned but requested scene identity not confirmed");
    }
    if(b->operation==SceneSeek||b->operation==SceneAdvance){
        if(b->timeMs<0||b->timeMs>600000||!b->camera[0]){Fail(b,57,L"Camera and time 0..600000 ms required");return;}
        BeginSceneSeek(b,scene);return;
    }
    SceneSnapshot(b,scene);
}
