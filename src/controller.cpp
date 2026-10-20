#include "protocol.h"
#include "document_window.h"
#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <sstream>
#include <filesystem>
#include <thread>
#include <atomic>
#include <commctrl.h>
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"ole32.lib")
namespace fs=std::filesystem;
static std::string Utf8(const std::wstring& w){if(w.empty())return {};int n=WideCharToMultiByte(CP_UTF8,0,w.data(),int(w.size()),nullptr,0,nullptr,nullptr);std::string r(n,0);WideCharToMultiByte(CP_UTF8,0,w.data(),int(w.size()),r.data(),n,nullptr,nullptr);return r;}
static std::string Q(const std::wstring& s){std::string r="\"";for(unsigned char c:Utf8(s)){if(c=='"'||c=='\\'){r+='\\';r+=char(c);}else if(c=='\n')r+="\\n";else if(c=='\r')r+="\\r";else if(c=='\t')r+="\\t";else if(c<32){char a[8];sprintf_s(a,"\\u%04x",c);r+=a;}else r+=char(c);}return r+'"';}
static std::wstring Text(HWND w){
    wchar_t s[2048]{};
    // Cross-process top-level captions live in Windows' caption cache. Asking
    // every helper/IME thread to process WM_GETTEXT can stall each video frame.
    if(!(GetWindowLongPtrW(w,GWL_STYLE)&WS_CHILD)){GetWindowTextW(w,s,2048);return s;}
    DWORD_PTR result=0;SendMessageTimeoutW(w,WM_GETTEXT,2048,reinterpret_cast<LPARAM>(s),SMTO_ABORTIFHUNG|SMTO_BLOCK,300,&result);return s;
}
static DWORD wantedPid;
static std::vector<HWND> windows;
static std::atomic<uint32_t> editorForegroundEvents{0};
static std::atomic<uint32_t> privateForegroundEvents{0};
static void CALLBACK ForegroundEvent(HWINEVENTHOOK,DWORD,HWND w,LONG,LONG,DWORD,DWORD){
    DWORD pid=0;DWORD tid=GetWindowThreadProcessId(w,&pid);if(pid!=wantedPid)return;
    wchar_t eventDesktop[256]{},inputDesktop[256]{};DWORD bytes=0;
    HDESK input=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);
    bool read=input&&GetUserObjectInformationW(GetThreadDesktop(tid),UOI_NAME,eventDesktop,sizeof(eventDesktop),&bytes)&&GetUserObjectInformationW(input,UOI_NAME,inputDesktop,sizeof(inputDesktop),&bytes);
    if(input)CloseDesktop(input);
    if(read&&wcscmp(eventDesktop,inputDesktop)!=0)++privateForegroundEvents;else ++editorForegroundEvents;
}
static BOOL CALLBACK Root(HWND w,LPARAM){DWORD pid=0;GetWindowThreadProcessId(w,&pid);if(pid==wantedPid)windows.push_back(w);return TRUE;}
static void Pump(){MSG m;while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}}
static int Error(const std::string& text){std::cerr<<text<<" (Win32="<<GetLastError()<<")\n";return 2;}
static UINT MenuCommand(HMENU menu,const std::wstring& wanted){
    for(int i=0;i<GetMenuItemCount(menu);i++){
        wchar_t text[512]{};GetMenuStringW(menu,i,text,512,MF_BYPOSITION);std::wstring label;
        for(wchar_t c:std::wstring(text)){if(c==L'\t')break;if(c!=L'&')label+=c;}
        if(label==wanted){UINT id=GetMenuItemID(menu,i);if(id&&id!=UINT(-1))return id;}
        auto sub=GetSubMenu(menu,i);if(sub){UINT id=MenuCommand(sub,wanted);if(id)return id;}
    }return 0;
}
static void DumpMenu(std::ostream& out,HMENU menu){
    out<<"[";for(int i=0;i<GetMenuItemCount(menu);i++){
        if(i)out<<",";wchar_t text[512]{};GetMenuStringW(menu,i,text,512,MF_BYPOSITION);
        out<<"{\"text\":"<<Q(text)<<",\"id\":"<<GetMenuItemID(menu,i)<<",\"state\":"<<GetMenuState(menu,i,MF_BYPOSITION)<<",\"children\":";
        DumpMenu(out,GetSubMenu(menu,i));out<<"}";
    }out<<"]";
}
int wmain(int argc,wchar_t** argv){
    if(argc<3){std::cout<<"SC2NativeBridge.exe inspect|generate|compile|read|freshness-probe --pid PID --expect-document NativeEmitterProbe.SC2Map --marker MARKER --out NEW_DIRECTORY\n";return 2;}
    std::wstring op=argv[1],expected,marker,context,scope=L"mapRoot",desktop,camera;uint32_t imageSize=2048;bool includeUnits=true,includeDoodads=true;int64_t timeMs=0;fs::path out,map;bool resumeDialog=false;
    for(int i=2;i<argc;i++){std::wstring arg=argv[i];if(i+1>=argc)return Error("Missing option value");std::wstring value=argv[++i];if(arg==L"--pid")wantedPid=std::stoul(value);else if(arg==L"--expect-document")expected=value;else if(arg==L"--marker")marker=value;else if(arg==L"--out")out=value;else if(arg==L"--map")map=value;else if(arg==L"--resume-dialog")resumeDialog=value==L"yes";else if(arg==L"--context-label")context=value;else if(arg==L"--scope")scope=value;else if(arg==L"--desktop")desktop=value;else if(arg==L"--camera")camera=value;else if(arg==L"--time-ms")timeMs=std::stoll(value);else if(arg==L"--image-size")imageSize=std::stoul(value);else if(arg==L"--include-units"||arg==L"--include-doodads"){if(value!=L"yes"&&value!=L"no")return Error("Boolean options require yes/no");if(arg==L"--include-units")includeUnits=value==L"yes";else includeDoodads=value==L"yes";}else return Error("Unknown option");}
    if(!desktop.empty()){
        if(desktop.rfind(L"SC2Native-",0)!=0)return Error("Only a private SC2Native desktop is allowed");
        HDESK isolated=OpenDesktopW(desktop.c_str(),0,FALSE,GENERIC_ALL);
        if(!isolated||!SetThreadDesktop(isolated))return Error("Cannot join private worker desktop");
    }
    if(scope!=L"mapRoot"){
        if(scope.rfind(L"library:",0)!=0||scope.size()!=16)return Error("Scope must be mapRoot or library:<8 hex ID>");
        for(size_t i=8;i<scope.size();i++){if(!iswxdigit(scope[i]))return Error("Invalid library ID");scope[i]=towupper(scope[i]);}
    }
    if(!wantedPid||expected.empty()||out.empty())return Error("Explicit PID, expected document, and fresh output directory required");
    if(fs::exists(out))return Error("Output directory must be new");
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,wantedPid);if(!process)return Error("Cannot query Editor PID");
    wchar_t exe[32768]{};DWORD size=32768;bool queried=QueryFullProcessImageNameW(process,0,exe,&size)!=0;
    if(!queried||_wcsicmp(exe,L"C:\\Program Files (x86)\\StarCraft II\\Support64\\SC2Editor_x64.exe"))return Error("PID is not the expected installed original Editor");
    EnumWindows(Root,0);HWND target=nullptr;
    if(op==L"inventory"){
        fs::create_directories(out);std::ofstream dump(out/"inventory.json");dump<<"[";bool sep=false;
        for(HWND w:windows){if(sep)dump<<",";sep=true;dump<<"{\"hwnd\":"<<reinterpret_cast<uint64_t>(w)<<",\"title\":"<<Q(Text(w))<<",\"enabled\":"<<(IsWindowEnabled(w)?"true":"false")<<",\"menu\":";DumpMenu(dump,GetMenu(w));dump<<",\"controls\":[";
            struct Context{std::ofstream* stream;bool comma;};Context context{&dump,false};
            EnumChildWindows(w,[](HWND child,LPARAM param)->BOOL{auto c=reinterpret_cast<Context*>(param);wchar_t cls[256]{};GetClassNameW(child,cls,256);
                RECT r{};GetWindowRect(child,&r);if(c->comma)*c->stream<<",";c->comma=true;
                *c->stream<<"{\"hwnd\":"<<reinterpret_cast<uint64_t>(child)<<",\"parent\":"<<reinterpret_cast<uint64_t>(GetParent(child))<<",\"id\":"<<GetDlgCtrlID(child)<<",\"class\":"<<Q(cls)<<",\"text\":"<<Q(Text(child))<<",\"visible\":"<<(IsWindowVisible(child)?"true":"false")<<",\"rect\":["<<r.left<<","<<r.top<<","<<r.right<<","<<r.bottom<<"]}";
                return TRUE;},reinterpret_cast<LPARAM>(&context));dump<<"]}";
        }dump<<"]";return 0;
    }
    for(HWND w:windows){auto title=Text(w);if(title.rfind(L"Triggers - [",0)==0&&DocumentWindow(title,expected,nullptr,true)){if(target)return Error("Ambiguous Triggers workspace");target=w;}}
    if(!target&&!desktop.empty()){
        for(HWND w:windows){auto title=Text(w);if(IsWindowEnabled(w)&&DocumentWindow(title,expected,nullptr,true)){
            UINT command=MenuCommand(GetMenu(w),L"Triggers");if(!command)return Error("Native Triggers module command absent");
            PostMessageW(w,WM_COMMAND,command,0);break;
        }}
        ULONGLONG until=GetTickCount64()+30000;
        while(!target&&GetTickCount64()<until){windows.clear();EnumWindows(Root,0);for(HWND w:windows){auto title=Text(w);if(title.rfind(L"Triggers - [",0)==0&&DocumentWindow(title,expected,nullptr,true)&&IsWindowEnabled(w)){if(target)return Error("Ambiguous Triggers workspace");target=w;}}if(!target)Sleep(200);}
    }
    if(!target)return Error("Expected Triggers test-document workspace not found");
    DWORD tid=GetWindowThreadProcessId(target,nullptr);if(!tid)return Error("No owner thread");
    if(op!=L"inspect"&&op!=L"generate"&&op!=L"compile"&&op!=L"read"&&op!=L"freshness-probe"&&op!=L"load"&&op!=L"cancel-load"&&op!=L"diagnostics"&&op!=L"cutscene"&&op!=L"scene-inspect"&&op!=L"scene-load"&&op!=L"scene-seek"&&op!=L"scene-advance"&&op!=L"scene-audio"&&op!=L"terrain"&&op!=L"terrain-export"&&op!=L"save-document"&&op!=L"reopen-document"&&op!=L"load-data"&&op!=L"terrain-camera"&&op!=L"terrain-camera-layer"&&op!=L"terrain-camera-select")return Error("Unsupported operation");
    if(op==L"load"&&(map.empty()||!map.is_absolute()||!fs::is_regular_file(map)))return Error("Existing absolute --map archive required");
    fs::create_directories(out);
    std::ofstream inventory(out/"windows-before.json",std::ios::binary);inventory<<"[";
    for(size_t i=0;i<windows.size();i++){if(i)inventory<<",";inventory<<"{\"hwnd\":"<<reinterpret_cast<uint64_t>(windows[i])<<",\"enabled\":"<<(IsWindowEnabled(windows[i])?"true":"false")<<",\"title\":"<<Q(Text(windows[i]))<<"}";}inventory<<"]";inventory.close();
    GUID id{};if(FAILED(CoCreateGuid(&id)))return Error("Cannot create request ID");wchar_t guid[64]{};StringFromGUID2(id,guid,64);
    std::wstring mappingName=L"Local\\SC2NativeBridge-"+std::to_wstring(wantedPid)+L"-"+guid;
    HANDLE mapping=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(Block),mappingName.c_str());if(!mapping||GetLastError()==ERROR_ALREADY_EXISTS)return Error("Cannot create unique IPC mapping");
    auto b=static_cast<Block*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Block)));if(!b)return Error("Cannot map IPC");
    ZeroMemory(b,sizeof(Block));b->compilerErrors=-1;b->magic=kMagic;b->version=10;b->pid=wantedPid;b->tid=tid;b->target=reinterpret_cast<uint64_t>(target);
    b->operation=op==L"generate"?Generate:op==L"compile"?Compile:op==L"read"?ReadSource:op==L"freshness-probe"?FreshnessProbe:op==L"load"?LoadDocument:op==L"cancel-load"?CancelLoad:op==L"diagnostics"?Diagnostics:op==L"cutscene"?OpenCutscene:op==L"scene-inspect"?SceneInspect:op==L"scene-load"?SceneLoad:op==L"scene-seek"?SceneSeek:op==L"scene-advance"?SceneAdvance:op==L"scene-audio"?SceneAudio:op==L"terrain"?TerrainView:op==L"terrain-export"?TerrainExport:op==L"save-document"?SaveDocument:op==L"reopen-document"?ReopenDocument:op==L"load-data"?LoadDataModule:op==L"terrain-camera"?TerrainCamera:op==L"terrain-camera-layer"?TerrainCameraLayer:op==L"terrain-camera-select"?TerrainCameraSelect:Inspect;
    wcsncpy_s(b->expectedDocument,expected.c_str(),_TRUNCATE);wcsncpy_s(b->expectedMarker,marker.c_str(),_TRUNCATE);
    wcsncpy_s(b->mapPath,map.c_str(),_TRUNCATE);
    wcsncpy_s(b->contextLabel,context.c_str(),_TRUNCATE);
    wcsncpy_s(b->scope,scope.c_str(),_TRUNCATE);
    b->terrain.size=imageSize;b->terrain.includeUnits=includeUnits;b->terrain.includeDoodads=includeDoodads;
    b->resumeDialog=resumeDialog;b->timeMs=timeMs;wcsncpy_s(b->camera,camera.c_str(),_TRUNCATE);
    wchar_t self[32768]{};GetModuleFileNameW(nullptr,self,32768);auto dllPath=fs::path(self).parent_path()/L"SC2NativeBridge.dll";
    HMODULE dll=LoadLibraryW(dllPath.c_str());if(!dll)return Error("Cannot load bridge DLL locally");
    auto hookProc=reinterpret_cast<HOOKPROC>(GetProcAddress(dll,"BridgeHook"));auto guardProc=reinterpret_cast<HOOKPROC>(GetProcAddress(dll,"BridgeFocusGuard"));
    if(!hookProc||!guardProc)return Error("Missing bridge exports");
    HHOOK guard=SetWindowsHookExW(WH_CBT,guardProc,dll,tid);if(!guard)return Error("Cannot install Editor-thread focus veto");
    HHOOK hook=SetWindowsHookExW(WH_CALLWNDPROC,hookProc,dll,tid);if(!hook){UnhookWindowsHookEx(guard);return Error("Cannot install Editor-thread DLL hook");}
    HWINEVENTHOOK events=SetWinEventHook(EVENT_SYSTEM_FOREGROUND,EVENT_SYSTEM_FOREGROUND,nullptr,ForegroundEvent,0,0,WINEVENT_OUTOFCONTEXT);
    if(!events){UnhookWindowsHookEx(hook);UnhookWindowsHookEx(guard);return Error("Cannot monitor foreground changes");}
    ATOM atom=GlobalAddAtomW(mappingName.c_str());UINT msg=RegisterWindowMessageW(kMessageName);if(!atom||!msg)return Error("Cannot initialize IPC name/message");
    uint64_t before=reinterpret_cast<uint64_t>(GetForegroundWindow());std::atomic<bool> finished{false};DWORD sendError=0;BOOL sent=FALSE;DWORD_PTR value=0;
    std::thread sender([&]{sent=static_cast<BOOL>(SendMessageTimeoutW(target,msg,atom,0,SMTO_ABORTIFHUNG|SMTO_BLOCK,30000,&value));if(!sent)sendError=GetLastError();finished=true;});
    LONG previousStage=-1;
    while(!finished){
        if(b->loadStage!=previousStage){previousStage=b->loadStage;std::cerr<<"loadStage="<<previousStage<<"\n";std::ofstream progress(out/"progress.json");progress<<"{\"loadStage\":"<<previousStage<<",\"error\":"<<b->error<<"}";}
        Pump();MsgWaitForMultipleObjects(0,nullptr,FALSE,5,QS_ALLINPUT);
    }sender.join();
    ULONGLONG until=GetTickCount64()+500;while(GetTickCount64()<until){Pump();MsgWaitForMultipleObjects(0,nullptr,FALSE,5,QS_ALLINPUT);}Pump();
    uint64_t after=reinterpret_cast<uint64_t>(GetForegroundWindow());
    // A timeout does not cancel a native handler. Keep its activation guard alive
    // until it completes instead of permitting a delayed focus-stealing action.
    if(b->started&&!b->completed){
        std::cerr<<"Native handler pending; keeping worker hooks installed until completion.\n";
        while(!b->completed&&WaitForSingleObject(process,0)==WAIT_TIMEOUT){
            if(b->loadStage!=previousStage){previousStage=b->loadStage;std::cerr<<"loadStage="<<previousStage<<"\n";std::ofstream progress(out/"progress.json");progress<<"{\"loadStage\":"<<previousStage<<",\"error\":"<<b->error<<"}";}
            Pump();MsgWaitForMultipleObjects(0,nullptr,FALSE,25,QS_ALLINPUT);
        }
    }
    UnhookWinEvent(events);bool removedHook=UnhookWindowsHookEx(hook)!=0;bool removedGuard=UnhookWindowsHookEx(guard)!=0;GlobalDeleteAtom(atom);
    std::ofstream nativeLog(out/"native-log.txt",std::ios::binary);nativeLog<<Utf8(b->log);nativeLog.close();
    if(b->completed&&b->sourceBytes&&b->sourceBytes<kSourceCapacity){std::ofstream source(out/"Native.galaxy",std::ios::binary);source.write(b->source,b->sourceBytes);}
    std::ostringstream r;
    bool success=b->started&&b->completed&&b->error==0&&editorForegroundEvents==0&&removedHook&&removedGuard;
    bool compilePassed=b->compilerCommand&&b->compileCommandReturned&&b->compilerErrors==0&&wcsstr(b->statusAfter,L"Compiled:");
    r<<"{\n\"status\":\""<<(success?"NATIVE_DLL_REQUEST_COMPLETED":"NOT_CONFIRMED")<<"\",\n\"operation\":"<<Q(op)<<",\n\"pid\":"<<wantedPid<<",\"ownerThread\":"<<tid<<",\"dllPid\":"<<b->dllPid<<",\"dllThread\":"<<b->dllTid<<",\n\"started\":"<<b->started<<",\"completed\":"<<b->completed<<",\"error\":"<<b->error<<",\"sendError\":"<<sendError<<",\"exceptionCode\":"<<b->exceptionCode<<",\"failure\":"<<Q(b->failure)<<",\n\"loadCommandId\":"<<b->loadCommand<<",\"loadStage\":"<<b->loadStage<<",\"mapLoaded\":"<<b->mapLoaded<<",\"loadedTitle\":"<<Q(b->loadedTitle)<<",\n\"generatorCommandId\":"<<b->generatorCommand<<",\"compilerCommandId\":"<<b->compilerCommand<<",\"commandsDispatched\":"<<b->commandsDispatched<<",\n\"sourceBytes\":"<<b->sourceBytes<<",\"codePage\":"<<b->codePage<<",\"compilerErrors\":"<<b->compilerErrors<<",\"nativeCompilePassed\":"<<(compilePassed?"true":"false")<<",\n\"compileStatusBefore\":"<<Q(b->statusBefore)<<",\"compileStatusAfter\":"<<Q(b->statusAfter)<<",\n\"activationVetoes\":"<<b->activationVetoes<<",\"focusVetoes\":"<<b->focusVetoes<<",\"editorForegroundEvents\":"<<editorForegroundEvents<<",\"foregroundBefore\":"<<before<<",\"foregroundAfter\":"<<after<<",\"sameForegroundAtEndpoints\":"<<(before==after?"true":"false")<<",\n\"beforeTextFingerprint\":"<<b->beforeTextFingerprint<<",\"afterTextFingerprint\":"<<b->afterTextFingerprint<<",\n\"sourceReadOnly\":"<<b->sourceReadOnly<<",\"poisonApplied\":"<<b->poisonApplied<<",\"poisonReplaced\":"<<b->poisonReplaced<<",\n\"inputInjectionUsed\":false,\"activationApiUsed\":false,\"hooksRemoved\":"<<(removedHook&&removedGuard?"true":"false")<<",\"editorTerminated\":false,\"automaticMapOpeningImplemented\":true,\"byteEqualityToManualExportProven\":false\n}\n";
    auto json=r.str();
    const std::string activationFlag="\"activationApiUsed\":false";
    if(b->privateFocusUsed){auto flag=json.find(activationFlag);if(flag!=json.npos)json.replace(flag,activationFlag.size(),"\"activationApiUsed\":true");}
    auto ending=json.rfind("\n}");json.insert(ending,",\n\"sceneLoaded\":"+std::to_string(b->sceneLoaded)+",\n\"cameraConfirmed\":"+std::to_string(b->cameraConfirmed)+",\n\"timeConfirmed\":"+std::to_string(b->timeConfirmed)+",\n\"viewport\":"+std::to_string(b->viewport)+",\n\"sceneStatus\":"+Q(b->sceneStatus)+",\n\"actualTimeMs\":"+std::to_string(b->actualTimeMs));
    json.insert(ending,",\n\"privateDesktopFocusUsed\":"+std::string(b->privateFocusUsed?"true":"false")+",\n\"diagnosticWindows\":"+std::to_string(b->diagnosticWindows)+",\n\"diagnosticsTruncated\":"+std::to_string(b->diagnosticsTruncated)+",\n\"moduleCommandId\":"+std::to_string(b->moduleCommand));
    ending=json.rfind("\n}");json.insert(ending,",\n\"privateDesktopActivationEvents\":"+std::to_string(privateForegroundEvents.load())+",\n\"userDesktopActivationApiUsed\":false");
    ending=json.rfind("\n}");auto& a=b->audio;json.insert(ending,",\n\"audio\":{\"error\":"+std::to_string(a.error)+",\"ready\":"+std::to_string(a.ready)+",\"version\":"+std::to_string(a.version)+",\"rate\":"+std::to_string(a.rate)+",\"channels\":"+std::to_string(a.channels)+",\"frames\":"+std::to_string(a.frames)+",\"nonzero\":"+std::to_string(a.nonzero)+",\"peak\":"+std::to_string(a.peak)+",\"sumSquares\":"+std::to_string(a.sumSquares)+",\"firstQpc\":"+std::to_string(a.firstQpc)+",\"lastQpc\":"+std::to_string(a.lastQpc)+",\"playQpc\":"+std::to_string(a.playQpc)+",\"frequency\":"+std::to_string(a.frequency)+",\"sceneStartQpc\":"+std::to_string(a.sceneStartQpc)+",\"bufferCalls\":"+std::to_string(a.bufferCalls)+",\"submitCalls\":"+std::to_string(a.submitCalls)+",\"renderedFrames\":"+std::to_string(a.renderedFrames)+",\"idleFrames\":"+std::to_string(a.idleFrames)+"}");
    ending=json.rfind("\n}");auto& t=b->terrain;json.insert(ending,",\n\"terrainExport\":{\"size\":"+std::to_string(t.size)+",\"includeUnits\":"+std::to_string(t.includeUnits)+",\"includeDoodads\":"+std::to_string(t.includeDoodads)+",\"exported\":"+std::to_string(t.exported)+",\"fullMap\":"+std::to_string(t.fullMap)+",\"topDown\":"+std::to_string(t.topDown)+",\"optionsConfirmed\":"+std::to_string(t.optionsConfirmed)+"}");
    auto& io=b->documentIo;ending=json.rfind("\n}");json.insert(ending,",\n\"documentIo\":{\"saveCommandId\":"+std::to_string(io.saveCommand)+",\"closeCommandId\":"+std::to_string(io.closeCommand)+",\"saved\":"+std::to_string(io.saved)+",\"closed\":"+std::to_string(io.closed)+",\"reopened\":"+std::to_string(io.reopened)+",\"dataLoaded\":"+std::to_string(io.dataLoaded)+",\"savedBytes\":"+std::to_string(io.savedBytes)+"}");
    auto& d=b->diagnosticCapture;
    auto& mc=b->mapCamera;ending=json.rfind("\n}");
    std::ostringstream cameraJson;cameraJson<<",\n\"mapCamera\":{\"selected\":"<<mc.selected<<",\"valuesRead\":"<<mc.valuesRead<<",\"name\":"<<Q(mc.name)<<",\"target\":{\"x\":"<<mc.x<<",\"y\":"<<mc.y<<",\"z\":"<<mc.z<<"},\"pitch\":"<<mc.pitch<<",\"yaw\":"<<mc.yaw<<",\"roll\":"<<mc.roll<<",\"distance\":"<<mc.distance<<",\"fov\":"<<mc.fov<<"}";
    json.insert(ending,cameraJson.str());
    for(auto part:{std::make_pair(L"diagnostics-before.json",std::make_pair(d.before,d.beforeBytes)),std::make_pair(L"diagnostics-after.json",std::make_pair(d.after,d.afterBytes)),std::make_pair(L"diagnostics-events.json",std::make_pair(d.events,d.eventBytes))}){
        if(part.second.second&&part.second.second<kDiagnosticCapacity){std::ofstream stream(out/part.first,std::ios::binary);stream.write(part.second.first,part.second.second);}
    }
    ending=json.rfind("\n}");json.insert(ending,",\n\"diagnosticCapture\":{\"version\":1,\"eventCount\":"+std::to_string(d.eventCount)+",\"eventsComplete\":"+std::string(d.eventsComplete?"true":"false")+"}");
    std::ofstream result(out/"result.json",std::ios::binary);result<<json;result.close();std::cout<<json;
    UnmapViewOfFile(b);CloseHandle(mapping);CloseHandle(process);FreeLibrary(dll);return !success?2:op==L"compile"&&!compilePassed?1:0;
}
