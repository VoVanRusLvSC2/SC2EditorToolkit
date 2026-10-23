// Original Model field and Archive Browser on the owned private desktop.
// Resolve tokens natively, check the merged virtual file tree, cancel without saving.
struct DataAssetTask{Block* b;HWND data;std::vector<HWND> before;ULONGLONG start;std::string lookup="null";int stage=0;HWND values=nullptr,browser=nullptr;std::wstring pretty;};
static thread_local DataAssetTask* dataAsset;
static void DataAssetCancel(HWND dialog){
    if(!dialog||!IsWindowVisible(dialog))return;
    auto cancel=Control(dialog,L"Button",12);
    if(cancel&&IsWindowEnabled(cancel))PostMessageW(dialog,WM_COMMAND,MAKEWPARAM(12,BN_CLICKED),reinterpret_cast<LPARAM>(cancel));
}
static std::wstring DataTreeText(HWND tree,HTREEITEM node){wchar_t text[4096]{};TVITEMW item{};item.hItem=node;item.mask=TVIF_TEXT;item.pszText=text;item.cchTextMax=4096;return SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&item))?text:L"";}
static std::wstring DataPrettyModelPath(const std::wstring& text){
    size_t start=0;while(start<text.size()){
        auto end=text.find(L'\n',start);auto line=text.substr(start,end==text.npos?text.npos:end-start);if(!line.empty()&&line.back()==L'\r')line.pop_back();
        auto tab=line.find(L'\t');if(tab!=line.npos){auto key=line.substr(0,tab);if(key.rfind(L"(Basic) ",0)==0)key.erase(0,8);
            if(key==L"Model"||key==L"Art: Model")return line.substr(tab+1);
        }if(end==text.npos)break;start=end+1;
    }return {};
}
static std::string DataAssetTreeCheck(HWND browser,const std::wstring& requested){
    if(requested.empty()||requested.find(L"##")!=requested.npos)return "{\"confirmed\":false,\"reason\":\"Original resolved path unavailable\"}";
    HWND button=Control(browser,L"Button",19);if(button)SendMessageW(GetParent(button),WM_COMMAND,MAKEWPARAM(19,BN_CLICKED),reinterpret_cast<LPARAM>(button));DataPump(250);
    HWND tree=nullptr;for(HWND w:Children(browser))if(IsWindowVisible(w)&&Class(w)==L"SysTreeView32"){if(tree)return "{\"confirmed\":false,\"reason\":\"Ambiguous native file tree\"}";tree=w;}
    if(!tree)return "{\"confirmed\":false,\"reason\":\"Native file tree not visible\"}";
    std::vector<std::wstring> parts;size_t start=0;
    while(start<requested.size()){auto end=requested.find_first_of(L"\\/",start);auto part=requested.substr(start,end==requested.npos?requested.npos:end-start);if(!part.empty())parts.push_back(part);if(end==requested.npos)break;start=end+1;}
    HTREEITEM parent=nullptr;std::wstring found;
    for(size_t index=0;index<parts.size();index++){
        if(parts[index]==L"."||parts[index]==L"..")return "{\"confirmed\":false,\"reason\":\"Noncanonical native path\"}";
        if(parent)SendMessageW(tree,TVM_EXPAND,TVE_EXPAND,reinterpret_cast<LPARAM>(parent));
        auto node=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,parent?TVGN_CHILD:TVGN_ROOT,reinterpret_cast<LPARAM>(parent)));
        HTREEITEM match=nullptr;int entries=0;
        while(node&&entries++<100000){if(!_wcsicmp(DataTreeText(tree,node).c_str(),parts[index].c_str())){if(match)return "{\"confirmed\":false,\"reason\":\"Ambiguous native path component\"}";match=node;}node=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(node)));}
        if(node)return "{\"confirmed\":false,\"reason\":\"Native sibling bound exceeded\"}";
        if(!match){bool confirmed=index>0&&entries>0;return "{\"confirmed\":"+std::string(confirmed?"true":"false")+",\"exists\":false,\"requestedPath\":"+DiagQ(requested)+",\"missingComponent\":"+DiagQ(parts[index])+",\"nativeSiblingCount\":"+std::to_string(entries)+"}";}
        if(!found.empty())found+=L"\\";found+=DataTreeText(tree,match);parent=match;
    }
    SetFocus(tree);SendMessageW(tree,TVM_SELECTITEM,TVGN_CARET,reinterpret_cast<LPARAM>(parent));DataPump(250);
    auto selected=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_CARET,0));auto ok=Control(browser,L"Button",11);
    return "{\"confirmed\":"+std::string(selected==parent&&ok&&IsWindowEnabled(ok)?"true":"false")+",\"exists\":true,\"requestedPath\":"+DiagQ(requested)+",\"resolvedPath\":"+DiagQ(found)+",\"source\":\"original Archive Browser tree and selection readback\"}";
}
static void CALLBACK DataAssetTimer(HWND,UINT,UINT_PTR,DWORD){
    auto task=dataAsset;if(!task||task->stage==3||GetTickCount64()-task->start<1500)return;
    if(task->stage==2){if(task->browser&&IsWindowVisible(task->browser))DataAssetCancel(task->browser);else if(task->values&&IsWindowVisible(task->values))DataAssetCancel(task->values);return;}
    if(GetTickCount64()-task->start>180000){
        Fail(task->b,160,L"Original resource dialog deadline exceeded");
        if(task->browser)DataAssetCancel(task->browser);else if(task->values)DataAssetCancel(task->values);
        return;
    }
    for(HWND root:Roots())if(IsWindowVisible(root)&&std::find(task->before.begin(),task->before.end(),root)==task->before.end()){
        if(Text(root)==L"Object Values"&&task->stage==0){
            task->values=root;
            HWND browse=nullptr;int matches=0;
            for(HWND c:Children(root))if(IsWindowVisible(c)&&IsWindowEnabled(c)&&Class(c)==L"Button"&&Clean(Text(c))==L"Browse..."){browse=c;matches++;}
            if(matches!=1){task->lookup="{\"confirmed\":false,\"reason\":\"Unique original Model file Browse control unavailable\"}";task->stage=2;DataAssetCancel(root);return;}
            if(browse&&IsWindowEnabled(browse)){
                task->values=root;task->stage=1;task->start=GetTickCount64();
                SendMessageW(GetParent(browse),WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(browse),BN_CLICKED),reinterpret_cast<LPARAM>(browse));return;
            }
        }else if(Text(root)==L"Archive Browser"&&task->stage==1){
            Log(task->b,L"Original merged Archive Browser observed\n");
            task->stage=3;
            task->lookup=DataAssetTreeCheck(root,DataPrettyModelPath(task->pretty));
            task->browser=root;task->stage=2;
            DataAssetCancel(root);return;
        }
    }
}
static std::string DataAssetLookup(Block* b,HWND data,int row){
    HWND values=Control(data,L"SysListView32",2026),names=Control(data,L"SysListView32",2025);
    int count=values?int(SendMessageW(values,LVM_GETITEMCOUNT,0,0)):0;
    if(!values||!names||row<0||row>=count){Fail(b,155,L"Original resource field row unavailable");return "null";}
    SetActiveWindow(data);SetFocus(values);b->privateFocusUsed=1;
    for(HWND list:{values,names}){
        LVITEMW item{};item.stateMask=LVIS_SELECTED|LVIS_FOCUSED;item.state=0;SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&item));
        SendMessageW(list,LVM_SETSELECTIONMARK,0,row);item.state=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,row,reinterpret_cast<LPARAM>(&item));
    }
    SendMessageW(values,LVM_ENSUREVISIBLE,row,FALSE);RECT rectangle{};rectangle.left=LVIR_LABEL;SendMessageW(values,LVM_GETITEMRECT,row,reinterpret_cast<LPARAM>(&rectangle));
    NMITEMACTIVATE notification{};notification.hdr.hwndFrom=values;notification.hdr.idFrom=2026;notification.hdr.code=NM_CLICK;notification.iItem=row;notification.iSubItem=0;notification.ptAction={rectangle.left+2,(rectangle.top+rectangle.bottom)/2};
    SendMessageW(GetParent(values),WM_NOTIFY,2026,reinterpret_cast<LPARAM>(&notification));
    auto raw=FindCommand(data,{L"View"},{L"View Raw Data"});
    if(raw&&CheckedCommand(GetMenu(data),raw)){SendMessageW(data,WM_COMMAND,raw,0);DataPump(300);}
    UINT selectAll=FindCommand(data,{L"Edit"},{L"Select All"}),copy=FindCommand(data,{L"Edit"},{L"Copy As Text"});
    std::wstring pretty;
    if(copy&&EnsureDataClipboard()){
        SetFocus(values);if(selectAll)SendMessageW(data,WM_COMMAND,selectAll,0);DataClipEmpty();SendMessageW(data,WM_COMMAND,copy,0);pretty=DataCopiedText();DataClipOleFlush();
    }
    // Copy As Text selects every property. Restore ONLY the complete native
    // Model row in the now non-raw view; otherwise Modify Value opens a mixed
    // form with unrelated animation Browse buttons and unstable numeric IDs.
    int nativeRows=int(SendMessageW(values,LVM_GETITEMCOUNT,0,0)),modelRow=-1,rows=-1;size_t lineStart=0;
    while(lineStart<pretty.size()){
        auto end=pretty.find(L'\n',lineStart);auto line=pretty.substr(lineStart,end==pretty.npos?pretty.npos:end-lineStart);
        if(line.rfind(L"(Basic) Model\t",0)==0||line.rfind(L"Model\t",0)==0||line.rfind(L"Art: Model\t",0)==0){
            if(modelRow!=-1){Fail(b,162,L"Ambiguous original Model field");return "null";}modelRow=rows;
        }
        rows++;if(end==pretty.npos)break;lineStart=end+1;
    }
    if(modelRow<0||rows!=nativeRows||pretty.rfind(L"Field\t",0)!=0){Fail(b,162,L"Complete original non-raw Model row unavailable");return "null";}
    for(HWND list:{values,names}){
        LVITEMW item{};item.stateMask=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&item));
        SendMessageW(list,LVM_SETSELECTIONMARK,0,modelRow);item.state=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,modelRow,reinterpret_cast<LPARAM>(&item));
    }
    SendMessageW(values,LVM_ENSUREVISIBLE,modelRow,FALSE);SetFocus(values);
    rectangle={};rectangle.left=LVIR_LABEL;SendMessageW(values,LVM_GETITEMRECT,modelRow,reinterpret_cast<LPARAM>(&rectangle));
    notification.iItem=modelRow;notification.ptAction={rectangle.left+2,(rectangle.top+rectangle.bottom)/2};
    SendMessageW(GetParent(values),WM_NOTIFY,2026,reinterpret_cast<LPARAM>(&notification));
    auto modify=FindCommand(data,{L"Data"},{L"Modify Value"});if(!modify){Fail(b,156,L"Original Modify Value command unavailable");return "null";}
    auto visible=Roots();visible.erase(std::remove_if(visible.begin(),visible.end(),[](HWND w){return !IsWindowVisible(w);}),visible.end());
    DataAssetTask task{b,data,visible,GetTickCount64()};dataAsset=&task;
    task.pretty=pretty;
    auto timer=SetTimer(nullptr,0,100,DataAssetTimer);if(!timer){dataAsset=nullptr;Fail(b,157,L"Cannot guard original resource dialog");return "null";}
    SendMessageW(data,WM_COMMAND,modify,0);
    // Object Values can be modeless. Returning after a fixed delay leaves the
    // worker's Data window disabled; wait for lookup AND both cancellations.
    auto deadline=GetTickCount64()+185000;
    while(task.lookup=="null"||(task.values&&IsWindowVisible(task.values))||(task.browser&&IsWindowVisible(task.browser))){
        DataPump(50);
        if(GetTickCount64()>deadline){
            Fail(b,160,L"Original resource dialogs did not finish and close");
            DataAssetCancel(task.browser);DataAssetCancel(task.values);DataPump(250);break;
        }
    }
    KillTimer(nullptr,timer);dataAsset=nullptr;
    return task.lookup;
}
