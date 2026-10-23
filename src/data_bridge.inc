// Read original Data controls on the owned GUI thread. No user clipboard or physical input.
static UINT DataMenuLeaf(HWND window,HMENU menu,const std::wstring& wanted,int depth=0){
    if(depth>12)return 0;int count=GetMenuItemCount(menu);if(count<0||count>256)return 0;UINT found=0;
    for(int i=0;i<count;i++){
        wchar_t text[256]{};GetMenuStringW(menu,i,text,256,MF_BYPOSITION);HMENU sub=GetSubMenu(menu,i);
        if(sub){SendMessageW(window,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(sub),MAKELPARAM(i,FALSE));auto id=DataMenuLeaf(window,sub,wanted,depth+1);if(id){if(found)return 0;found=id;}}
        else if(Clean(text)==wanted&&!(GetMenuState(menu,i,MF_BYPOSITION)&(MF_DISABLED|MF_GRAYED))){if(found)return 0;found=GetMenuItemID(menu,i);}
    }return found;
}
static UINT DataCatalogCommand(HWND data,const wchar_t* wanted,const wchar_t* group){
    HMENU menu=GetMenu(data);SendMessageW(data,WM_INITMENU,reinterpret_cast<WPARAM>(menu),0);
    for(int i=0;i<GetMenuItemCount(menu);i++){wchar_t text[128]{};GetMenuStringW(menu,i,text,128,MF_BYPOSITION);if(Clean(text)!=L"Data")continue;
        auto sub=GetSubMenu(menu,i);SendMessageW(data,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(sub),MAKELPARAM(i,FALSE));
        for(int j=0;j<GetMenuItemCount(sub);j++){wchar_t label[256]{};GetMenuStringW(sub,j,label,256,MF_BYPOSITION);if(Clean(label)!=group)continue;
            auto category=GetSubMenu(sub,j);SendMessageW(data,WM_INITMENUPOPUP,reinterpret_cast<WPARAM>(category),MAKELPARAM(j,FALSE));return DataMenuLeaf(data,category,wanted);
        }return 0;
    }return 0;
}
static void DataPump(DWORD milliseconds){
    ULONGLONG end=GetTickCount64()+milliseconds;MSG msg{};
    do{while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);}while(GetTickCount64()<end);
}
static std::wstring DataCell(HWND list,int row,int column){
    wchar_t text[16384]{};LVITEMW item{};item.iSubItem=column;item.pszText=text;item.cchTextMax=_countof(text);
    auto got=SendMessageW(list,LVM_GETITEMTEXTW,row,reinterpret_cast<LPARAM>(&item));
    if(got>=_countof(text)-1)return L"<TRUNCATED>";return text;
}
static std::string DataList(HWND list,int limit=512){
    int rows=int(SendMessageW(list,LVM_GETITEMCOUNT,0,0));auto header=reinterpret_cast<HWND>(SendMessageW(list,LVM_GETHEADER,0,0));
    int columns=int(SendMessageW(header,HDM_GETITEMCOUNT,0,0));
    if(rows<0||rows>200000||columns<0||columns>128)return "{\"complete\":false,\"error\":\"Unsupported native table\"}";
    std::string json="{\"count\":"+std::to_string(rows)+",\"complete\":"+(rows<=limit?"true":"false")+",\"columns\":[";
    for(int c=0;c<columns;c++){if(c)json+=",";wchar_t text[1024]{};HDITEMW item{};item.mask=HDI_TEXT;item.pszText=text;item.cchTextMax=1024;SendMessageW(header,HDM_GETITEMW,c,reinterpret_cast<LPARAM>(&item));json+=DiagQ(text);}json+="],\"rows\":[";
    for(int row=0;row<(std::min)(rows,limit);row++){
        if(row)json+=",";json+="[";
        for(int c=0;c<columns;c++){if(c)json+=",";json+=DiagQ(DataCell(list,row,c));}json+="]";
    }return json+"]}";
}
static void DataTreeJson(HWND tree,HTREEITEM item,std::string& json,int& count,int depth){
    while(item&&count<2048&&depth<32){
        wchar_t text[4096]{};TVITEMW value{};value.hItem=item;value.mask=TVIF_TEXT|TVIF_PARAM;value.pszText=text;value.cchTextMax=4096;
        if(!SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&value)))return;
        if(count++)json+=",";json+="{\"text\":"+DiagQ(text)+",\"depth\":"+std::to_string(depth)+"}";
        DataTreeJson(tree,reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_CHILD,reinterpret_cast<LPARAM>(item))),json,count,depth+1);
        item=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(item)));
    }
}
#include "data_asset_bridge.inc"
static void DataOperation(Block* b,HWND target){
    if(!PrivateDesktop()){Fail(b,140,L"Data access requires owned private desktop");return;}
    LoadNativeDataModule(b,target);if(b->error)return;
    HWND data=nullptr;for(HWND w:Roots())if(IsWindowVisible(w)&&IsWindowEnabled(w)&&Text(w).rfind(L"Data - [",0)==0&&DocumentWindow(Text(w),b->expectedDocument,nullptr,true)){if(data){Fail(b,141,L"Ambiguous Data workspace");return;}data=w;}
    if(!data){Fail(b,142,L"Original Data workspace absent");return;}
    SetActiveWindow(data);b->privateFocusUsed=1;
    for(auto label:{L"Toggle Easy Mode",L"Display Object List As Tree",L"Display All Object Sources"}){
        auto command=FindCommand(data,{L"View"},{label});
        if(command&&CheckedCommand(GetMenu(data),command))SendMessageW(data,WM_COMMAND,command,0);
    }
    if(auto fieldSearch=Control(data,L"Edit",2020);fieldSearch&&!Text(fieldSearch).empty()){
        SendMessageW(fieldSearch,WM_SETTEXT,0,reinterpret_cast<LPARAM>(L""));SendMessageW(GetParent(fieldSearch),WM_COMMAND,MAKEWPARAM(2020,EN_CHANGE),reinterpret_cast<LPARAM>(fieldSearch));
    }
    auto sourceFilter=Control(data,L"ComboBox",19);
    if(!sourceFilter){Fail(b,154,L"Original Data source filter unavailable");return;}
    if(Text(sourceFilter)!=L"All Data"){
        auto index=SendMessageW(sourceFilter,CB_FINDSTRINGEXACT,WPARAM(-1),reinterpret_cast<LPARAM>(L"All Data"));
        if(index==CB_ERR){Fail(b,154,L"Original All Data source scope unavailable");return;}
        SendMessageW(sourceFilter,CB_SETCURSEL,index,0);SendMessageW(GetParent(sourceFilter),WM_COMMAND,MAKEWPARAM(19,CBN_SELCHANGE),reinterpret_cast<LPARAM>(sourceFilter));DataPump(250);
    }
    auto explorer=FindCommand(data,{L"View"},{L"Show Object Explorer"});
    if(explorer&&!(GetMenuState(GetMenu(data),explorer,MF_BYCOMMAND)&MF_CHECKED))SendMessageW(data,WM_COMMAND,explorer,0);
    std::string selection="null",preview="null",copies="[]";std::wstring copied;
    if(b->camera[0]){
        struct Catalog{const wchar_t* name;const wchar_t* label;};
        const Catalog catalogs[]={{L"Unit",L"Units"},{L"Model",L"Models"},{L"Actor",L"Actors"},{L"Abil",L"Abilities"},{L"Behavior",L"Behaviors"},{L"Effect",L"Effects"},{L"Sound",L"Sounds"},{L"Texture",L"Textures"},{L"Weapon",L"Weapons"},{L"Validator",L"Validators"},{L"Upgrade",L"Upgrades"},{L"Requirement",L"Requirements"}};
        const Catalog* selected=nullptr;for(auto& entry:catalogs)if(!_wcsicmp(entry.name,b->camera))selected=&entry;
        if(!selected){Fail(b,144,L"Unsupported native catalog");return;}
        const wchar_t* group=wcscmp(selected->name,L"Actor")==0?L"Edit Actor Data":
            (wcscmp(selected->name,L"Model")==0||wcscmp(selected->name,L"Sound")==0||wcscmp(selected->name,L"Texture")==0)?L"Edit Art and Sound Data":L"Edit Game Data";
        UINT catalogCommand=DataCatalogCommand(data,selected->label,group);
        if(!catalogCommand){Fail(b,145,L"Unique original catalog menu command unavailable");return;}
        auto type=Control(data,L"ComboBox",21);
        const wchar_t* typeName=wcscmp(selected->name,L"Abil")==0?L"Ability":selected->name;
        if(!type||Text(type)!=typeName){SendMessageW(data,WM_COMMAND,catalogCommand,0);DataPump(250);}
        if(b->timeMs!=1&&b->timeMs!=4)for(auto label:{L"Table View",L"View Raw Data"}){
            auto command=FindCommand(data,{L"View"},{label});if(!command){Fail(b,152,L"Original Data view command unavailable");return;}
            if(!CheckedCommand(GetMenu(data),command))SendMessageW(data,WM_COMMAND,command,0);
        }
        auto search=Control(data,L"Edit",18);auto list=Control(data,L"SysListView32",1025);
        if(!search||!list){Fail(b,146,L"Native object search controls absent");return;}
        if(Text(search)!=b->contextLabel){
            SendMessageW(search,WM_SETTEXT,0,reinterpret_cast<LPARAM>(b->contextLabel));
            SendMessageW(GetParent(search),WM_COMMAND,MAKEWPARAM(18,EN_CHANGE),reinterpret_cast<LPARAM>(search));DataPump(1500);
        }
        if(b->timeMs==5){
            std::string prepared="{\"prepared\":true,\"requestedCatalog\":"+DiagQ(selected->name)+",\"requestedId\":"+DiagQ(b->contextLabel)+"}";
            memcpy(b->source,prepared.data(),prepared.size());b->sourceBytes=uint32_t(prepared.size());b->codePage=CP_UTF8;return;
        }
        auto header=reinterpret_cast<HWND>(SendMessageW(list,LVM_GETHEADER,0,0));wchar_t firstColumn[256]{};
        HDITEMW heading{};heading.mask=HDI_TEXT;heading.pszText=firstColumn;heading.cchTextMax=256;SendMessageW(header,HDM_GETITEMW,0,reinterpret_cast<LPARAM>(&heading));
        if(std::wstring(firstColumn)!=std::wstring(typeName)+L" Name"){Fail(b,159,L"Original catalog object list is still refreshing");return;}
        int count=int(SendMessageW(list,LVM_GETITEMCOUNT,0,0));
        Log(b,L"Data catalog=%s search=%s candidates=%d\n",b->camera,b->contextLabel,count);
        int match=-1;std::wstring wanted=b->contextLabel;
        if(count<0||count>200000){Fail(b,147,L"Unsupported Data object count");return;}
        for(int i=0;i<count;i++){
            auto name=DataCell(list,i,0);
            if(name==wanted||name.rfind(wanted+L" (",0)==0){if(match!=-1){Fail(b,148,L"Ambiguous exact native object ID");return;}match=i;}
        }
        if(match>=0){
            int selectedIndex=int(SendMessageW(list,LVM_GETNEXTITEM,WPARAM(-1),LVNI_SELECTED));
            if(selectedIndex!=match||SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0)!=1){
            LVITEMW item{};item.stateMask=LVIS_SELECTED|LVIS_FOCUSED;item.state=0;
            SendMessageW(list,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&item));
            SendMessageW(list,LVM_SETSELECTIONMARK,0,match);
            SetFocus(list);b->privateFocusUsed=1;
            item.state=LVIS_SELECTED|LVIS_FOCUSED;SendMessageW(list,LVM_SETITEMSTATE,match,reinterpret_cast<LPARAM>(&item));DataPump(500);
            LVITEMW identity{};identity.mask=LVIF_PARAM;identity.iItem=match;SendMessageW(list,LVM_GETITEMW,0,reinterpret_cast<LPARAM>(&identity));
            SendMessageW(list,LVM_ENSUREVISIBLE,match,FALSE);
            NMITEMACTIVATE notification{};notification.hdr.hwndFrom=list;notification.hdr.idFrom=1025;notification.hdr.code=NM_CLICK;notification.iItem=match;notification.iSubItem=0;
            notification.lParam=identity.lParam;
            RECT label{};label.left=LVIR_LABEL;
            if(SendMessageW(list,LVM_GETITEMRECT,match,reinterpret_cast<LPARAM>(&label))){notification.ptAction.x=label.left+2;notification.ptAction.y=(label.top+label.bottom)/2;}
            SendMessageW(GetParent(list),WM_NOTIFY,1025,reinterpret_cast<LPARAM>(&notification));DataPump(500);
            Log(b,L"Data selection mark=%lld selected=%lld fields=%lld focus=%d param=%lld\n",SendMessageW(list,LVM_GETSELECTIONMARK,0,0),SendMessageW(list,LVM_GETSELECTEDCOUNT,0,0),SendMessageW(Control(data,L"SysListView32",2025),LVM_GETITEMCOUNT,0,0),GetFocus()==list,identity.lParam);
            }
            selection="{\"catalog\":"+DiagQ(selected->name)+",\"requestedId\":"+DiagQ(wanted)+",\"nativeRow\":"+DiagQ(DataCell(list,match,0))+",\"source\":"+DiagQ(DataCell(list,match,1))+",\"row\":"+std::to_string(match)+"}";
        }else if(b->operation!=DataInspect){Fail(b,149,L"Exact object ID not found in original Data catalog");return;}
        if(b->timeMs==1){auto xml=FindCommand(data,{L"View"},{L"XML View"});if(!xml){Fail(b,153,L"Original XML View command unavailable");return;}SendMessageW(data,WM_COMMAND,xml,0);DataPump(250);}
    }
    if(b->camera[0]&&b->timeMs!=1&&b->timeMs!=4){
        HWND fields=Control(data,L"SysListView32",2025);
        if(fields&&SendMessageW(fields,LVM_GETITEMCOUNT,0,0)>0){
            if(!EnsureDataClipboard()){Fail(b,151,L"Private clipboard isolation unavailable; original Copy was not invoked");return;}
            copies="[";bool comma=false;
            for(int control:{2026,2025})if(HWND source=Control(data,L"SysListView32",control)){
                SetActiveWindow(data);SetFocus(source);b->privateFocusUsed=1;
                if(control!=1025){auto select=FindCommand(data,{L"Edit",L"Правка"},{L"Select All",L"Выделить все"});
                    if(select)SendMessageW(data,WM_COMMAND,select,0);
                    else{LVITEMW row{};row.stateMask=LVIS_SELECTED;row.state=LVIS_SELECTED;SendMessageW(source,LVM_SETITEMSTATE,WPARAM(-1),reinterpret_cast<LPARAM>(&row));}
                    SendMessageW(source,LVM_SETSELECTIONMARK,0,0);
                }
                for(auto label:{L"Copy As Text"}){
                    DataClipEmpty();auto copy=FindCommand(data,{L"Edit",L"Правка"},{label});
                    if(copy){SendMessageW(data,WM_COMMAND,copy,0);auto text=DataCopiedText();DataClipOleFlush();
                        if(comma)copies+=",";comma=true;
                        copies+="{\"controlId\":"+std::to_string(control)+",\"command\":"+DiagQ(label)+",\"text\":"+DiagQ(text)+"}";
                        if(text.rfind(L"Field\t",0)==0)copied=text;
                        Log(b,L"Original private copy control=%d command=%s chars=%zu\n",control,label,text.size());
                    }else Log(b,L"Original private copy unavailable control=%d command=%s\n",control,label);
                }
                if(!copied.empty())break;
            }copies+="]";
        }
    }
    std::string asset="null";
    if(b->operation==DataAsset||b->operation==DataResources){
        if(wcscmp(b->camera,L"Model")!=0){Fail(b,161,L"Native resource file lookup currently supports Model only");return;}
        // Complete original serialization identifies the exact main Model field;
        // clipped on-screen strings or a guessed row are never used.
        size_t start=0;int row=-1,index=-1;
        while(start<copied.size()){
            auto end=copied.find(L'\n',start);auto line=copied.substr(start,end==copied.npos?copied.npos:end-start);
            if(line.rfind(L"(Basic) CModel_Model\t",0)==0||line.rfind(L"CModel_Model\t",0)==0){if(row!=-1){Fail(b,162,L"Ambiguous Model field");return;}row=index;}
            index++;if(end==copied.npos)break;start=end+1;
        }
        if(row<0){Fail(b,162,L"Complete original Model field identity unavailable");return;}
        asset=DataAssetLookup(b,data,row);if(b->error)return;
    }
    std::string json="{\"source\":\"original Editor Data controls\",\"dataSpace\":"+DiagQ(Text(Control(data,L"Button",20)))+",\"dataSource\":"+DiagQ(Text(sourceFilter))+",\"selection\":"+selection+",\"preview\":"+preview+",\"privateClipboard\":"+std::string(dataClipReady?"true":"false")+",\"copyText\":"+DiagQ(copied)+",\"copies\":"+copies+",\"controls\":[";bool comma=false;
    for(HWND c:Children(data))if(IsWindowVisible(c)){
        auto cls=Class(c);int id=GetDlgCtrlID(c);
        if(cls!=L"SysListView32"&&cls!=L"SysTreeView32"&&cls!=L"ComboBox"&&cls!=L"Static"&&cls!=L"Scintilla")continue;
        if(comma)json+=",";comma=true;
        json+="{\"id\":"+std::to_string(id)+",\"class\":"+DiagQ(cls)+",\"text\":"+DiagQ(cls==L"Scintilla"?L"":Text(c));
        if(cls==L"SysListView32")json+=",\"table\":"+DataList(c,id==1025?8:2048);
        if(cls==L"Scintilla"){
            auto n=SendMessageW(c,2183,0,0);if(n>=0&&n<8*1024*1024){std::vector<char> text(size_t(n)+1);SendMessageW(c,2182,text.size(),reinterpret_cast<LPARAM>(text.data()));
            int length=MultiByteToWideChar(CP_UTF8,0,text.data(),int(n),nullptr,0);std::wstring value(length,0);MultiByteToWideChar(CP_UTF8,0,text.data(),int(n),value.data(),length);json+=",\"xml\":"+DiagQ(value);}
        }
        if(cls==L"ComboBox"){
            json+=",\"options\":[";int n=int(SendMessageW(c,CB_GETCOUNT,0,0));
            for(int i=0;i<n&&i<256;i++){if(i)json+=",";wchar_t text[1024]{};if(SendMessageW(c,CB_GETLBTEXTLEN,i,0)<1024)SendMessageW(c,CB_GETLBTEXT,i,reinterpret_cast<LPARAM>(text));json+=DiagQ(text);}json+="]";
        }
        if(cls==L"SysTreeView32"){json+=",\"tree\":[";int count=0;DataTreeJson(c,reinterpret_cast<HTREEITEM>(SendMessageW(c,TVM_GETNEXTITEM,TVGN_ROOT,0)),json,count,0);json+="],\"complete\":"+std::string(count<2048?"true":"false");}
        json+="}";
    }json+="],\"assetLookup\":"+asset+"}";
    if(json.size()>=kSourceCapacity){Fail(b,143,L"Native Data response exceeded bound");return;}
    memcpy(b->source,json.data(),json.size());b->sourceBytes=uint32_t(json.size());b->codePage=CP_UTF8;
}
