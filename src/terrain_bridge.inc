// Select the document's own original Terrain renderer, never an arbitrary
// swapchain or a Cutscenes preview. All commands run on the owned GUI thread.
static void TerrainOperation(Block* b,HWND target){
    if(!PrivateDesktop()){Fail(b,80,L"Terrain capture requires an owned private desktop");return;}
    UINT command=FindCommand(target,{L"Modules",L"Модули"},{L"Terrain",L"Ландшафт"});
    if(!command){Fail(b,81,L"Original Terrain module is unavailable for this document (a terrain map is required)");return;}
    b->moduleCommand=command;++b->commandsDispatched;
    SendMessageW(target,WM_COMMAND,command,0);
    HWND terrain=nullptr;
    for(HWND w:Roots())if(IsWindowVisible(w)&&IsWindowEnabled(w)&&Text(w).rfind(L"Terrain - [",0)==0&&DocumentWindow(Text(w),b->expectedDocument,nullptr,true)){
        if(terrain){Fail(b,82,L"Ambiguous native Terrain document window");return;}terrain=w;
    }
    if(!terrain){Fail(b,83,L"Native Terrain window for the expected document is not ready");return;}
    for(HWND c:Children(terrain)){
        Log(b,L"terrain control hwnd=%p class=%s id=%d visible=%d text=%s\n",c,Class(c).c_str(),GetDlgCtrlID(c),IsWindowVisible(c),Text(c).c_str());
        RECT rect{};GetClientRect(c,&rect);
        if(Class(c)==L"GfxViewClass"&&IsWindowVisible(c)&&rect.right>64&&rect.bottom>64){
            if(b->viewport){Fail(b,84,L"Ambiguous native Terrain viewport");return;}b->viewport=reinterpret_cast<uint64_t>(c);
        }
    }
    if(!b->viewport){Fail(b,85,L"Original Terrain render viewport not found");return;}
    SetActiveWindow(terrain);SetFocus(reinterpret_cast<HWND>(b->viewport));b->privateFocusUsed=1;
    wcsncpy_s(b->loadedTitle,Text(terrain).c_str(),_TRUNCATE);
    if(b->operation==TerrainExport){ExportWholeMap(b,terrain);return;}
    if((b->operation==TerrainCamera||b->operation==TerrainCameraLayer||b->operation==TerrainCameraSelect||b->operation==TerrainCameraRead)){TerrainCameraOperation(b,terrain);return;}
    RedrawWindow(terrain,nullptr,nullptr,RDW_INVALIDATE|RDW_ALLCHILDREN);
}
