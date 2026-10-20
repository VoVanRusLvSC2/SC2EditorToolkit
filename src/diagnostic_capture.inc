// Structured native log snapshots and mutations on the owned Editor GUI thread.
// No keyboard/mouse hooks. Only Console/Messages output control 13 is watched.
static std::string DiagUtf8(const std::wstring& s){
    if(s.empty())return {};int n=WideCharToMultiByte(CP_UTF8,0,s.data(),int(s.size()),nullptr,0,nullptr,nullptr);
    std::string out(n,0);WideCharToMultiByte(CP_UTF8,0,s.data(),int(s.size()),out.data(),n,nullptr,nullptr);return out;
}
static std::string DiagQ(const std::wstring& s){
    std::string out="\"";for(unsigned char c:DiagUtf8(s)){
        if(c=='"'||c=='\\'){out+='\\';out+=char(c);}else if(c=='\n')out+="\\n";else if(c=='\r')out+="\\r";else if(c=='\t')out+="\\t";
        else if(c<32){char value[8]{};sprintf_s(value,"\\u%04x",c);out+=value;}else out+=char(c);
    }return out+'"';
}
static bool DiagnosticRoot(HWND w){auto s=Text(w);return s.rfind(L"Console - ",0)==0||s.rfind(L"Messages - ",0)==0||s.rfind(L"Консоль - ",0)==0||s.rfind(L"Сообщения - ",0)==0;}
static std::wstring DiagnosticKey(HWND w){auto root=GetAncestor(w,GA_ROOT);return Text(root)+L"|"+Class(w)+L"|"+std::to_wstring(GetDlgCtrlID(w));}
static std::wstring FullDiagnosticText(HWND w,bool& complete){
    constexpr int bound=262144;int length=GetWindowTextLengthW(w);
    if(length<0||length>=bound){complete=false;length=(std::min)((std::max)(length,0),bound-1);}
    std::vector<wchar_t> text(size_t(length)+1);int got=GetWindowTextW(w,text.data(),int(text.size()));
    if(got!=length)complete=false;return std::wstring(text.data(),size_t((std::max)(got,0)));
}
static void CopyDiagnosticJson(char* target,uint32_t& bytes,const std::string& json){
    const std::string failure="{\"version\":1,\"complete\":false,\"channels\":[],\"error\":\"Native diagnostic capture exceeded its bound\"}";
    const auto& value=json.size()<kDiagnosticCapacity?json:failure;bytes=uint32_t(value.size());memcpy(target,value.data(),value.size());target[value.size()]=0;
}
static std::wstring NativeFailureText(HWND root){
    if(Class(root)!=L"#32770"||!IsWindowVisible(root))return {};
    std::wstring all=Text(root);for(HWND c:Children(root))if(Class(c)==L"Static")all+=L"\n"+Text(c);
    auto lower=all;std::transform(lower.begin(),lower.end(),lower.begin(),towlower);
    bool failure=false;for(auto needle:{L"could not",L"cannot ",L"unable to",L"failed to",L"missing depend",L"not found",L"ошибка",L"не удалось",L"отсутствует завис"})if(lower.find(needle)!=lower.npos)failure=true;
    return failure?all:std::wstring();
}
static void CaptureDiagnosticJson(Block* b,bool before){
    bool complete=true;size_t channels=0,roots=0;std::string values="[";std::string dialogs="[";bool firstDialog=true;
    for(HWND root:Roots()){
        auto failure=NativeFailureText(root);if(!failure.empty()){
            if(!firstDialog)dialogs+=",";firstDialog=false;dialogs+="{\"window\":"+DiagQ(Text(root))+",\"text\":"+DiagQ(failure)+"}";
        }
        if(!DiagnosticRoot(root))continue;++roots;bool rootRead=false;
        for(HWND c:Children(root)){
            auto cls=Class(c);int id=GetDlgCtrlID(c);
            bool rich=cls==L"Edit"||cls.rfind(L"RichEdit",0)==0||cls.rfind(L"RICHEDIT",0)==0;
            // Console's other edit is the command input, never a log channel.
            if(rich&&id!=13)continue;
            if(!rich&&cls!=L"SysListView32"&&cls!=L"ListBox")continue;
            rootRead=true;bool channelComplete=true;std::string entries="[";bool comma=false;
            auto add=[&](int index,const std::vector<std::wstring>& columns){
                if(comma)entries+=",";comma=true;std::wstring joined;entries+="{\"row\":"+std::to_string(index)+",\"columns\":[";
                for(size_t k=0;k<columns.size();k++){if(k)entries+=",";entries+=DiagQ(columns[k]);if(!columns[k].empty()){if(!joined.empty())joined+=L" | ";joined+=columns[k];}}
                entries+="],\"text\":"+DiagQ(joined)+"}";
            };
            if(rich){
                auto content=FullDiagnosticText(c,channelComplete);std::wistringstream lines(content);std::wstring line;int index=0;
                while(std::getline(lines,line)){if(!line.empty()&&line.back()==L'\r')line.pop_back();if(!line.empty())add(index,{line});++index;}
            }else{
                int count=int(SendMessageW(c,rich?WM_GETTEXTLENGTH:cls==L"ListBox"?LB_GETCOUNT:LVM_GETITEMCOUNT,0,0));
                if(count<0||count>512)channelComplete=false;
                for(int row=0;row<(std::min)((std::max)(count,0),512);row++){
                    std::vector<std::wstring> cols;
                    if(cls==L"ListBox"){
                        auto n=SendMessageW(c,LB_GETTEXTLEN,row,0);if(n<0||n>65535){channelComplete=false;continue;}
                        std::vector<wchar_t> text(size_t(n)+1);SendMessageW(c,LB_GETTEXT,row,reinterpret_cast<LPARAM>(text.data()));cols.push_back(text.data());
                    }else for(int column=0;column<8;column++){
                        wchar_t text[4096]{};LVITEMW item{};item.iSubItem=column;item.pszText=text;item.cchTextMax=4096;
                        auto n=SendMessageW(c,LVM_GETITEMTEXTW,row,reinterpret_cast<LPARAM>(&item));if(n>=4095)channelComplete=false;cols.push_back(text);
                    }add(row,cols);
                }
            }
            entries+="]";if(channels++)values+=",";
            values+="{\"key\":"+DiagQ(DiagnosticKey(c))+",\"window\":"+DiagQ(Text(root))+",\"controlId\":"+std::to_string(id)+",\"kind\":"+DiagQ(cls)+",\"complete\":"+(channelComplete?"true":"false")+",\"entries\":"+entries+"}";
            if(!channelComplete)complete=false;
        }if(!rootRead)complete=false;
    }
    values+="]";dialogs+="]";if(!roots||!channels)complete=false;
    auto json="{\"version\":1,\"complete\":"+std::string(complete?"true":"false")+",\"channels\":"+values+",\"dialogs\":"+dialogs+"}";
    auto& d=b->diagnosticCapture;if(before)CopyDiagnosticJson(d.before,d.beforeBytes,json);else CopyDiagnosticJson(d.after,d.afterBytes,json);
}
struct DiagnosticWatch {bool active=false,reading=false,complete=true;uint32_t count=0;std::string events;};
static thread_local DiagnosticWatch diagnosticWatch;
static void ObserveDiagnosticMutationUnsafe(const CWPSTRUCT* m){
    auto& watch=diagnosticWatch;if(!m||!watch.active||watch.reading||!PrivateDesktop())return;
    if(m->message!=WM_SETTEXT&&m->message!=EM_REPLACESEL&&m->message!=WM_CLEAR&&m->message!=WM_USER+73&&m->message!=WM_USER+97)return;
    HWND w=m->hwnd;if(GetDlgCtrlID(w)!=13||!DiagnosticRoot(GetAncestor(w,GA_ROOT)))return;
    auto cls=Class(w);if(cls.rfind(L"RichEdit",0)!=0&&cls.rfind(L"RICHEDIT",0)!=0&&cls!=L"Edit")return;
    watch.reading=true;
    if(watch.count>=1024||watch.events.size()>kDiagnosticCapacity-262144){watch.complete=false;watch.reading=false;return;}
    std::wstring text;std::string kind="unknown";bool append=false;
    if(m->message==WM_SETTEXT||m->message==EM_REPLACESEL){
        kind=m->message==WM_SETTEXT?"set":"replace";
        if(m->lParam){
            if(IsWindowUnicode(w)){
                auto p=reinterpret_cast<const wchar_t*>(m->lParam);auto n=wcsnlen_s(p,65536);if(n==65536)watch.complete=false;text.assign(p,n);
            }else{
                auto p=reinterpret_cast<const char*>(m->lParam);auto n=strnlen_s(p,65536);if(n==65536)watch.complete=false;
                int size=MultiByteToWideChar(CP_ACP,0,p,int(n),nullptr,0);text.resize(size);MultiByteToWideChar(CP_ACP,0,p,int(n),text.data(),size);
            }
        }
        if(m->message==EM_REPLACESEL){DWORD start=0,end=0;SendMessageW(w,EM_GETSEL,reinterpret_cast<WPARAM>(&start),reinterpret_cast<LPARAM>(&end));int length=GetWindowTextLengthW(w);append=start==end&&end==DWORD(length);if(append)kind="append";}
    }else if(m->message==WM_CLEAR)kind="clear";
    if(watch.count++)watch.events+=",";
    watch.events+="{\"sequence\":"+std::to_string(watch.count)+",\"channel\":"+DiagQ(DiagnosticKey(w))+",\"kind\":\""+kind+"\",\"text\":"+DiagQ(text)+"}";
    watch.reading=false;
}
static void ObserveDiagnosticMutation(const CWPSTRUCT* m){
    __try{ObserveDiagnosticMutationUnsafe(m);}__except(EXCEPTION_EXECUTE_HANDLER){diagnosticWatch.complete=false;diagnosticWatch.reading=false;}
}
static void BeginDiagnosticCapture(Block* b){CaptureDiagnosticJson(b,true);diagnosticWatch=DiagnosticWatch{};diagnosticWatch.active=PrivateDesktop();}
static void EndDiagnosticCapture(Block* b){
    // A short GUI pump captures posted logger updates after synchronous native
    // commands; document readiness is still checked by the operation itself.
    auto until=GetTickCount64()+300;
    while(GetTickCount64()<until){MSG message{};int count=0;while(count++<100&&PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
        if(message.message==WM_QUIT){PostQuitMessage(int(message.wParam));break;}TranslateMessage(&message);DispatchMessageW(&message);
    }MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);}
    diagnosticWatch.active=false;CaptureDiagnosticJson(b,false);
    auto& d=b->diagnosticCapture;d.eventCount=diagnosticWatch.count;d.eventsComplete=diagnosticWatch.complete?1:0;
    auto json="{\"complete\":"+std::string(diagnosticWatch.complete?"true":"false")+",\"events\":["+diagnosticWatch.events+"]}";
    CopyDiagnosticJson(d.events,d.eventBytes,json);
}
