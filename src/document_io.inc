// Original File/Save As and File/Close -> File/Open, only on owned private UI.
struct NativeSaveTask {Block* b;HWND target,dialog=nullptr,edit=nullptr;ULONGLONG deadline,acceptAfter=0;int stage=0;bool done=false,submitting=false,commandReturned=false;};
static thread_local NativeSaveTask* nativeSaveTask;
static bool SaveDialogTitle(const std::wstring& title){return title==L"Save As"||title==L"Save Document"||title==L"Save Document As"||title==L"Сохранить как"||title==L"Сохранить документ";}
static HWND SaveNameControl(HWND dialog,Block* b){
    for(int id:{1001,1148,1152}){HWND c=Control(dialog,L"Edit",id);if(c&&IsWindowEnabled(c))return c;}
    HWND found=nullptr;for(HWND c:Children(dialog))if(Class(c)==L"Edit"&&IsWindowEnabled(c)&&DocumentName(Text(c))==DocumentName(b->expectedDocument)){
        if(found)return nullptr;found=c;
    }return found;
}
static bool RecordFailureDialog(Block* b){
    if(b->error==118)return false; // Do not repeatedly journal an unsupported modal dialog.
    for(HWND w:Roots()){
        auto text=NativeFailureText(w);if(text.empty())continue;
        auto& watch=diagnosticWatch;
        if(watch.count<1024&&watch.events.size()<kDiagnosticCapacity-262144){
            if(watch.count++)watch.events+=",";
            watch.events+="{\"sequence\":"+std::to_string(watch.count)+",\"channel\":\"nativeDialog\",\"kind\":\"dialog\",\"text\":"+DiagQ(text)+"}";
        }else watch.complete=false;
        Log(b,L"native operation failure dialog=%s text=%s\n",Text(w).c_str(),text.c_str());
        Fail(b,118,L"Original Editor reported a failure dialog; see operation diagnostics");
        // Persist a bounded checkpoint before acknowledging the failure. A
        // native loader can abort its process while declining bad dependencies.
        CaptureDiagnosticJson(b,false);
        auto& capture=b->diagnosticCapture;capture.eventCount=watch.count;capture.eventsComplete=0;
        CopyDiagnosticJson(capture.events,capture.eventBytes,"{\"complete\":false,\"failureCheckpoint\":true,\"events\":["+watch.events+"]}");
        HWND button=Control(w,L"Button",IDOK);
        if(button&&(Clean(Text(button))==L"OK"||Clean(Text(button))==L"ОК"))PostMessageW(w,WM_COMMAND,MAKEWPARAM(IDOK,BN_CLICKED),reinterpret_cast<LPARAM>(button));
        else {
            // Missing dependencies use a Yes/No "Continue anyway?" dialog.
            // Decline the failed load rather than accepting incomplete data.
            button=Control(w,L"Button",IDNO);
            if(button&&(Clean(Text(button))==L"No"||Clean(Text(button))==L"Нет"))PostMessageW(w,WM_COMMAND,MAKEWPARAM(IDNO,BN_CLICKED),reinterpret_cast<LPARAM>(button));
            else CancelLoadDialog(w);
        }
        return true;
    }return false;
}
static void CALLBACK NativeSaveTimer(HWND,UINT,UINT_PTR,DWORD){
    auto t=nativeSaveTask;if(!t||t->done)return;auto b=t->b;
    if(RecordFailureDialog(b)){if(t->dialog&&IsWindow(t->dialog))CancelLoadDialog(t->dialog);t->done=true;return;}
    if(GetTickCount64()>t->deadline){
        if(t->dialog&&IsWindow(t->dialog))CancelLoadDialog(t->dialog);
        Fail(b,110,L"Original Save As timed out or displayed an unsupported dialog");t->done=true;return;
    }
    if(t->stage==0){
        for(HWND w:Roots())if(IsWindowVisible(w)&&IsWindowEnabled(w)&&SaveDialogTitle(Text(w))){
            if(t->dialog&&t->dialog!=w){Fail(b,111,L"Ambiguous native Save As dialogs");t->done=true;return;}
            t->dialog=w;
        }
        if(!t->dialog)return;t->edit=SaveNameControl(t->dialog,b);
        if(!t->edit){
            Log(b,L"save unsupported dialog title=%s\n",Text(t->dialog).c_str());
            for(HWND c:Children(t->dialog))Log(b,L"save control class=%s id=%d text=%s\n",Class(c).c_str(),GetDlgCtrlID(c),Text(c).c_str());
            CancelLoadDialog(t->dialog);Fail(b,112,L"Unique native Save As filename control unavailable");t->done=true;return;
        }
        t->stage=1;t->acceptAfter=GetTickCount64()+200;SetWindowTextW(t->edit,b->mapPath);
        Log(b,L"save original dialog=%s filename control=%d\n",Text(t->dialog).c_str(),GetDlgCtrlID(t->edit));return;
    }
    if(t->stage==1&&GetTickCount64()>=t->acceptAfter){
        if(MapNormalizedPath(Text(t->edit))!=MapNormalizedPath(b->mapPath)){
            CancelLoadDialog(t->dialog);Fail(b,113,L"Native Save As did not accept this exact private filename");t->done=true;return;
        }
        HWND ok=Control(t->dialog,L"Button",IDOK);if(!ok)ok=Control(t->dialog,L"Button",11);
        if(!ok||!IsWindowEnabled(ok)){CancelLoadDialog(t->dialog);Fail(b,114,L"Native Save As confirmation unavailable");t->done=true;return;}
        auto label=Clean(Text(ok));if(label!=L"Save"&&label!=L"OK"&&label!=L"Сохранить"&&label!=L"ОК"){
            CancelLoadDialog(t->dialog);Fail(b,114,L"Native Save As confirmation label mismatched");t->done=true;return;
        }
        t->stage=2;t->submitting=true;++b->commandsDispatched;
        SendMessageW(t->dialog,WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(ok),BN_CLICKED),reinterpret_cast<LPARAM>(ok));t->submitting=false;return;
    }
    if(t->stage==2&&!t->submitting&&t->commandReturned){
        if(t->dialog&&IsWindow(t->dialog)&&IsWindowVisible(t->dialog))return;
        auto title=Text(t->target);std::error_code error;auto bytes=std::filesystem::file_size(b->mapPath,error);
        if(!error&&bytes&&IsWindowEnabled(t->target)&&DocumentWindow(title,std::filesystem::path(b->mapPath).filename().wstring(),nullptr,false)){
            b->documentIo.saved=1;b->documentIo.savedBytes=bytes;wcsncpy_s(b->loadedTitle,title.c_str(),_TRUNCATE);t->done=true;
            Log(b,L"save original serializer returned; bytes=%llu title=%s\n",static_cast<unsigned long long>(bytes),title.c_str());
        }
    }
}
static void SaveNativeDocument(Block* b,HWND target){
    if(!PrivateDesktop()){Fail(b,105,L"Native document Save As requires an owned private desktop");return;}
    std::filesystem::path path(b->mapPath);auto ext=DocumentName(path.extension().wstring());auto expectedExt=DocumentName(std::filesystem::path(b->expectedDocument).extension().wstring());
    if(!path.is_absolute()||std::filesystem::exists(path)||!std::filesystem::is_directory(path.parent_path())||(ext!=L".sc2map"&&ext!=L".sc2mod")||ext!=expectedExt){Fail(b,106,L"Native save requires a fresh absolute private archive with the same document type");return;}
    for(HWND w:Roots())if(IsWindowVisible(w)&&SaveDialogTitle(Text(w))){Fail(b,107,L"A pre-existing native save dialog blocks this operation");return;}
    SetActiveWindow(target);b->privateFocusUsed=1;
    UINT command=FindCommand(target,{L"File",L"Файл"},{L"Save As...",L"Save As",L"Сохранить как..."});
    if(!command){Fail(b,108,L"Original File/Save As command unavailable");return;}
    HMODULE pinned=nullptr;if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&NativeSaveTimer),&pinned)){Fail(b,109,L"Cannot retain original save callback lifetime");return;}
    NativeSaveTask task{b,target,nullptr,nullptr,GetTickCount64()+600000};nativeSaveTask=&task;
    auto timer=SetTimer(nullptr,0,50,NativeSaveTimer);if(!timer){nativeSaveTask=nullptr;Fail(b,109,L"Cannot create original save timer");return;}
    b->documentIo.saveCommand=command;++b->commandsDispatched;Log(b,L"save original File/Save As id=%u path=%s\n",command,b->mapPath);
    SendMessageW(target,WM_COMMAND,command,0);task.commandReturned=true;
    while(!task.done){
        MSG message{};int count=0;while(count++<100&&PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
            if(message.message==WM_QUIT){PostQuitMessage(int(message.wParam));Fail(b,115,L"Editor exited while saving");task.done=true;break;}TranslateMessage(&message);DispatchMessageW(&message);
        }MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);
    }KillTimer(nullptr,timer);nativeSaveTask=nullptr;
}
static void ReopenNativeDocument(Block* b,HWND target){
    if(!PrivateDesktop()){Fail(b,120,L"Native close/reopen requires an owned private desktop");return;}
    std::filesystem::path path(b->mapPath);
    if(!path.is_absolute()||!std::filesystem::is_regular_file(path)||DocumentName(path.filename().wstring())!=DocumentName(b->expectedDocument)){
        Fail(b,121,L"Reopen must target the exact current saved private archive");return;
    }
    SetActiveWindow(target);b->privateFocusUsed=1;
    auto close=FindCommand(target,{L"File",L"Файл"},{L"Close",L"Close Document",L"Закрыть"});
    if(!close){Fail(b,122,L"Original File/Close command unavailable");return;}
    b->documentIo.closeCommand=close;++b->commandsDispatched;SendMessageW(target,WM_COMMAND,close,0);
    // File/Close can expose another already open private document (the startup
    // seed). Use its unique clean Triggers shell only after proving that every
    // window for the saved document has gone; File/Open then reads from disk.
    HWND carrier=nullptr;bool stillOpen=false;
    auto deadline=GetTickCount64()+5000;
    do {
        MSG message{};int count=0;while(count++<100&&PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
            if(message.message==WM_QUIT){PostQuitMessage(int(message.wParam));Fail(b,125,L"Editor exited after native close");return;}
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        carrier=nullptr;stillOpen=false;std::vector<HWND> candidates;
        for(HWND w:Roots()){
            auto title=Text(w);if(DocumentWindow(title,b->expectedDocument,nullptr,true))stillOpen=true;
            bool empty=title==L"Triggers - StarCraft II Editor"||title==L"Data - StarCraft II Editor"||title==L"Terrain - StarCraft II Editor"||title==L"StarCraft II Editor";
            bool cleanTriggers=title.rfind(L"Triggers - [",0)==0&&title.find(L"*")==title.npos&&!DocumentWindow(title,b->expectedDocument,nullptr,true);
            if((empty||cleanTriggers)&&IsWindowEnabled(w)&&FindCommand(w,{L"File",L"Файл"},{L"Open...",L"Открыть..."}))candidates.push_back(w);
        }
        for(HWND w:candidates)if(Text(w)==L"Triggers - StarCraft II Editor"){
            if(carrier){Fail(b,123,L"Ambiguous empty Triggers workspace after close");return;}carrier=w;
        }
        if(!carrier&&candidates.size()==1)carrier=candidates[0];
        if(carrier&&!stillOpen)break;
        MsgWaitForMultipleObjects(0,nullptr,FALSE,25,QS_ALLINPUT);
    }while(GetTickCount64()<deadline);
    if(stillOpen){Fail(b,124,L"Original document remained open; disk reopen is not proven");return;}
    b->documentIo.closed=1;
    for(HWND w:Roots())if(GetMenu(w))Log(b,L"reopen empty shell title=%s enabled=%d visible=%d\n",Text(w).c_str(),IsWindowEnabled(w),IsWindowVisible(w));
    if(!carrier){Fail(b,125,L"No empty owned workspace available after native close");return;}
    Log(b,L"reopen: original File/Close completed; original loader will read saved archive\n");
    Load(b,carrier);if(b->mapLoaded)b->documentIo.reopened=1;
}
static void LoadNativeDataModule(Block* b,HWND target){
    if(!PrivateDesktop()){Fail(b,126,L"Native Data loading requires an owned private desktop");return;}
    auto command=FindCommand(target,{L"Modules",L"Модули"},{L"Data",L"Данные"});
    if(!command){Fail(b,127,L"Original Data module command unavailable");return;}
    b->moduleCommand=command;++b->commandsDispatched;SendMessageW(target,WM_COMMAND,command,0);
    HWND found=nullptr;for(HWND w:Roots())if(IsWindowEnabled(w)&&IsWindowVisible(w)&&Text(w).rfind(L"Data - [",0)==0&&DocumentWindow(Text(w),b->expectedDocument,nullptr,true)){
        if(found){Fail(b,128,L"Ambiguous native Data workspace");return;}found=w;
    }
    if(!found){Fail(b,129,L"Original Data module did not finish opening the requested document");return;}
    b->documentIo.dataLoaded=1;wcsncpy_s(b->loadedTitle,Text(found).c_str(),_TRUNCATE);
}
