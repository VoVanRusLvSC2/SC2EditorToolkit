// Read-only reflection adapter for the exact supported original Editor build.
// All calls run on the owned document's GUI thread. No global/game VM is used.
#include <map>
#include <set>
#include <stdexcept>
#include <fstream>
namespace data_audit {
static bool Copy(uintptr_t p,void* out,size_t bytes){
    __try{if(!p)return false;memcpy(out,reinterpret_cast<void*>(p),bytes);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
template<class T> static T At(uintptr_t p){T value{};if(!Copy(p,&value,sizeof(value)))throw std::runtime_error("Unreadable original Data metadata");return value;}
static std::string String(uintptr_t p){
    auto length=At<uint32_t>(p)>>2;if(length>1048576)throw std::runtime_error("Original Data string bound exceeded");
    auto first=(At<uint32_t>(p+4)&2)?At<uintptr_t>(p+8):p+8;
    std::string value(length,0);if(length&&!Copy(first,value.data(),length))throw std::runtime_error("Unreadable original Data string");return value;
}
static std::string Range(uintptr_t p){auto a=At<uintptr_t>(p),z=At<uintptr_t>(p+8);if(z<a||z-a>1048576)throw std::runtime_error("Original Data range bound exceeded");std::string v(z-a,0);if(z>a&&!Copy(a,v.data(),v.size()))throw std::runtime_error("Unreadable original Data range");return v;}
static std::string Q(const std::string& value){std::string out="\"";for(unsigned char c:value){if(c=='"'||c=='\\'){out+='\\';out+=char(c);}else if(c<32){char b[7];sprintf_s(b,"\\u%04x",c);out+=b;}else out+=char(c);}return out+'"';}
struct Ref{uintptr_t pointer=0;uint64_t extra=0;};
using Getter=uint32_t(__fastcall*)(uintptr_t,const Ref*,Ref*,uint32_t*,uint8_t*,uint32_t*);
static uint32_t Get(uintptr_t method,uintptr_t field,const Ref* object,Ref* value,uint32_t* index,uint8_t* selector,uint32_t* aux){
    __try{return reinterpret_cast<Getter>(method)(field,object,value,index,selector,aux);}
    __except(EXCEPTION_EXECUTE_HANDLER){return 0xffffffff;}
}
struct Catalog{uint32_t index;uintptr_t pointer;std::string name;std::vector<uintptr_t> entries;std::map<std::string,uintptr_t> valid;std::map<uint32_t,std::string> names;};
struct Context{
    uintptr_t base;std::vector<Catalog> catalogs;std::map<std::string,size_t> byName;
    std::string activePath,activeType;
    uint64_t fields=0,leaves=0,getterErrors=0,opaque=0;std::vector<std::string> references,resources,unknown;
    explicit Context():base(reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr))){
        const uint8_t signature[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x40};
        if(memcmp(reinterpret_cast<void*>(base+0x21c9e40),signature,sizeof(signature))||memcmp(reinterpret_cast<void*>(base+0x21c77e0),signature,sizeof(signature)))throw std::runtime_error("Original Data reflection signature mismatch");
        auto manager=At<uintptr_t>(base+0x65108a8);
        for(uint32_t i=0;i<109;i++){
            auto p=At<uintptr_t>(manager+8+i*8);if(!p)throw std::runtime_error("Missing original Data catalog");
            Catalog c{i,p,Range(p+8),{},{},{}};auto slots=At<uint32_t>(p+0x90),count=At<uint32_t>(p+0x68);
            if(slots>1000000||count>1000000)throw std::runtime_error("Original Data catalog bound exceeded");
            auto names=At<uintptr_t>(p+0xa0),entries=At<uintptr_t>(p+0x48);
            for(uint32_t j=0;j<slots;j++){auto n=At<uintptr_t>(names+j*8);if(n)c.names[j]=Range(n+8);}
            for(uint32_t j=0;j<slots;j++){
                auto e=At<uintptr_t>(entries+j*8);if(!e)continue;auto index=At<uint32_t>(e+8)>>16;
                if(index!=j||!c.names.count(index))throw std::runtime_error("Original Data entry identity mismatch");
                c.entries.push_back(e);if(!c.valid.emplace(c.names.at(index),e).second)throw std::runtime_error("Duplicate original Data entry ID");
            }byName[c.name]=catalogs.size();catalogs.push_back(std::move(c));
        }
    }
    void Unknown(const std::string& path,const std::string& type,const char* reason){opaque++;if(unknown.size()<100)unknown.push_back("{\"field\":"+Q(path)+",\"type\":"+Q(type)+",\"reason\":"+Q(reason)+"}");}
    void Link(uintptr_t value,const std::string& path,const std::string& typeName,const std::string& catalog){
        auto link=At<uintptr_t>(value);if(!link)return;
        auto record=At<uintptr_t>(link+0x30);auto target=record?String(record+0x18):std::string();
        auto found=byName.find(catalog);std::string status=found==byName.end()||target.empty()||target.find("##")!=target.npos?"unknown":catalogs[found->second].valid.count(target)?"present":"missing";
        references.push_back("{\"field\":"+Q(path)+",\"type\":"+Q(typeName)+",\"catalog\":"+Q(catalog)+",\"target\":"+Q(target)+",\"status\":"+Q(status)+"}");
    }
    void Walk(uintptr_t scope,Ref object,uint8_t selector,const std::string& prefix,int depth=0){
        if(depth>32)throw std::runtime_error("Original Data struct depth exceeded");
        auto count=At<uint32_t>(scope+0x80);auto array=At<uintptr_t>(scope+0x90);if(count>4096)throw std::runtime_error("Original Data field count exceeded");
        for(uint32_t f=0;f<count;f++){
            auto field=At<uintptr_t>(array+f*8),type=At<uintptr_t>(field+0x28),nested=At<uintptr_t>(field+0x98),method=At<uintptr_t>(field+0xb8);
            auto name=String(field),typeName=String(type);auto category=At<int32_t>(type+0x24);auto size=At<uint32_t>(field+0x30);
            if(method<base||method>=base+0x3700000)throw std::runtime_error("Original Data getter is outside the verified module");
            auto stem=prefix.empty()?name:prefix+'.'+name;activePath=stem;activeType=typeName;bool ended=false;
            for(uint32_t index=0;index<(size?size:65536);index++){
                if(index>=65536)throw std::runtime_error("Original Data array bound exceeded");
                Ref value{};uint32_t aux=0,actual=index;uint8_t selected=selector;
                auto code=Get(method,field,&object,&value,&actual,&selected,&aux);
                if(code){if(code!=0x2001002b){getterErrors++;Unknown(stem,typeName,"Original getter rejected a value");}ended=true;break;}
                if(actual<index||actual>=65536)throw std::runtime_error("Original Data getter returned an invalid array index");index=actual;
                fields++;auto path=stem+((size!=1)?'['+std::to_string(actual)+']':"");
                if(!value.pointer){Unknown(path,typeName,"Original getter returned no value");continue;}
                if(nested){Walk(nested,value,selected,path,depth+1);continue;}
                leaves++;
                if(category==9){
                    std::string catalog=typeName.size()>5&&typeName.front()=='C'&&typeName.substr(typeName.size()-4)=="Link"?typeName.substr(1,typeName.size()-5):"";
                    Link(value.pointer,path,typeName,catalog);
                }else if(typeName=="CAbilCommand"&&At<uintptr_t>(type+0x80)==base+0xc4b160){
                    Link(value.pointer,path+".Ability",typeName,"Abil");
                    if(At<uintptr_t>(value.pointer))Unknown(path,typeName,"Ability target checked; command argument semantics require separate validation");
                }else if(typeName=="CBehaviorLinkArray"&&At<uintptr_t>(type+0x80)==base+0xc4b1a0){
                    auto n=At<uint32_t>(value.pointer);auto links=At<uintptr_t>(value.pointer+0x10);
                    if(n>65536)throw std::runtime_error("Original behavior link array bound exceeded");
                    for(uint32_t j=0;j<n;j++)Link(links+j*8,path+'['+std::to_string(j)+']',typeName,"Behavior");
                }else if(category==1&&At<uintptr_t>(type+0x80)==base+0xc4b180){
                    auto record=At<uintptr_t>(value.pointer);if(record){auto pathValue=String(record);if(!pathValue.empty())resources.push_back("{\"field\":"+Q(path)+",\"type\":"+Q(typeName)+",\"path\":"+Q(pathValue)+"}");}
                }else if(category<0||category==0)Unknown(path,typeName,"Opaque original native type; no verified reference visitor");
                if(fields>10000000)throw std::runtime_error("Original Data field traversal bound exceeded");
            }
            if(!size&&!ended)throw std::runtime_error("Original Data dynamic array did not terminate");
        }
    }
};
static std::string Join(const std::vector<std::string>& values){std::string out="[";for(auto& v:values){if(out.size()>1)out+=',';out+=v;}return out+']';}
static std::string Counts(const Context& c){return "\"fieldsVisited\":"+std::to_string(c.fields)+",\"leafValuesVisited\":"+std::to_string(c.leaves)+",\"getterErrors\":"+std::to_string(c.getterErrors)+",\"unclassifiedValues\":"+std::to_string(c.opaque);}
static void Page(Block* b,HWND data){
    try{
        auto& request=b->dataAudit;
        if(request.catalog>=109||!request.limit||request.limit>256)throw std::runtime_error("Invalid native Data audit page");
        Context c;auto& catalog=c.catalogs.at(request.catalog);if(request.offset>catalog.entries.size())throw std::runtime_error("Data audit offset exceeds catalog");
        std::string out="{\"schemaVersion\":1,\"source\":\"original Editor effective catalog reflection\",\"catalogIndex\":"+std::to_string(catalog.index)+",\"catalog\":"+Q(catalog.name)+",\"totalEntries\":"+std::to_string(catalog.entries.size())+",\"offset\":"+std::to_string(request.offset)+",\"objects\":[";
        auto requestedEnd=(std::min)(catalog.entries.size(),size_t(request.offset)+request.limit);size_t end=request.offset;
        for(size_t i=request.offset;i<requestedEnd;i++){
            auto entry=catalog.entries[i];auto identifier=catalog.names.at(At<uint32_t>(entry+8)>>16);auto scope=At<uintptr_t>(entry+0x30);
            c.fields=c.leaves=c.getterErrors=c.opaque=0;c.references.clear();c.resources.clear();c.unknown.clear();
            try{c.Walk(scope,Ref{entry,0},0,"");}catch(const std::exception&){Log(b,L"Data audit object=%S/%S field=%S type=%S\n",catalog.name.c_str(),identifier.c_str(),c.activePath.c_str(),c.activeType.c_str());throw;}
            auto encoded="{\"id\":"+Q(identifier)+",\"nativeClass\":"+Q(String(scope))+",\"defaultTemplate\":"+std::string((At<uint32_t>(entry+8)&1)?"true":"false")+","+Counts(c)+",\"references\":"+Join(c.references)+",\"resources\":"+Join(c.resources)+",\"unclassifiedSamples\":"+Join(c.unknown)+"}";
            if(out.size()+encoded.size()>kSourceCapacity-1048576){if(i==request.offset)throw std::runtime_error("One original Data object exceeds the complete transport bound");break;}
            if(i>request.offset)out+=',';out+=encoded;end=i+1;
        }
        out+="],\"nextOffset\":"+(end<catalog.entries.size()?std::to_string(end):"null")+",\"dataSources\":[";
        auto filter=Control(data,L"ComboBox",19);auto n=SendMessageW(filter,CB_GETCOUNT,0,0);
        if(n<1||n>4096)throw std::runtime_error("Original Data source enumeration unavailable");
        for(int i=0;i<n;i++){auto length=SendMessageW(filter,CB_GETLBTEXTLEN,i,0);if(length<0||length>32767)throw std::runtime_error("Original Data source name bound exceeded");std::vector<wchar_t> name(size_t(length)+1);if(SendMessageW(filter,CB_GETLBTEXT,i,reinterpret_cast<LPARAM>(name.data()))!=length)throw std::runtime_error("Original Data source readback failed");if(i)out+=',';out+=DiagQ(name.data());}
        out+="],\"traversalComplete\":true,\"variant\":0}";
        if(out.size()>=kSourceCapacity)throw std::runtime_error("Data audit page transport capacity exceeded");
        memcpy(b->source,out.data(),out.size());b->sourceBytes=uint32_t(out.size());b->codePage=CP_UTF8;
    }catch(const std::exception& e){Log(b,L"Data audit: %S\n",e.what());Fail(b,170,L"Original Data audit page could not be read completely");}
}
static std::wstring Wide(const std::string& s){if(s.empty())return {};int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0);if(!n)throw std::runtime_error("Native resource path is not UTF-8");std::wstring out(n,0);MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),out.data(),n);return out;}
static std::wstring Fold(std::wstring s){if(!s.empty())CharLowerBuffW(s.data(),DWORD(s.size()));return s;}
struct BrowserTask{Block* b;ULONGLONG start;bool done=false;std::vector<std::string> paths;std::string result,error;};
static thread_local BrowserTask* browserTask;
static void CALLBACK BrowserTimer(HWND,UINT,UINT_PTR,DWORD){
    auto task=browserTask;if(!task||task->done)return;
    HWND browser=nullptr;for(auto root:Roots())if(IsWindowVisible(root)&&Text(root)==L"Archive Browser"){if(browser){task->done=true;task->error="Ambiguous original Archive Browser";return;}browser=root;}
    if(!browser)return;task->done=true;
    try{
        auto preview=FindCommand(browser,{L"View"},{L"Show Preview"});
        if(!preview)throw std::runtime_error("Original file preview toggle unavailable");
        if(CheckedCommand(GetMenu(browser),preview))SendMessageW(browser,WM_COMMAND,preview,0);
        auto search=Control(browser,L"Edit",16);if(!search||!Text(search).empty())throw std::runtime_error("Original Archive Browser search is not empty");
        auto treeButton=Control(browser,L"Button",19);if(!treeButton)throw std::runtime_error("Original archive tree view unavailable");
        SendMessageW(GetParent(treeButton),WM_COMMAND,MAKEWPARAM(19,BN_CLICKED),reinterpret_cast<LPARAM>(treeButton));
        auto tree=Control(browser,L"SysTreeView32",17);if(!tree||!IsWindowVisible(tree))throw std::runtime_error("Original archive file tree unavailable");
        std::map<HTREEITEM,std::map<std::wstring,HTREEITEM>> children;size_t nodes=0;
        auto enumerate=[&](HTREEITEM parent)->const std::map<std::wstring,HTREEITEM>&{
            auto existing=children.find(parent);if(existing!=children.end())return existing->second;
            if(parent)SendMessageW(tree,TVM_EXPAND,TVE_EXPAND,reinterpret_cast<LPARAM>(parent));
            std::map<std::wstring,HTREEITEM> list;
            auto node=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,parent?TVGN_CHILD:TVGN_ROOT,reinterpret_cast<LPARAM>(parent)));
            while(node){
                if(++nodes>1000000||GetTickCount64()-task->start>300000)throw std::runtime_error("Original virtual file traversal bound exceeded");
                auto name=DataTreeText(tree,node);if(name.empty()||name.size()>=4095||name.find_first_of(L"\\/")!=name.npos)throw std::runtime_error("Unsupported original virtual file tree node");
                if(!list.emplace(Fold(name),node).second)throw std::runtime_error("Ambiguous original virtual file name");
                node=reinterpret_cast<HTREEITEM>(SendMessageW(tree,TVM_GETNEXTITEM,TVGN_NEXT,reinterpret_cast<LPARAM>(node)));
            }
            return children.emplace(parent,std::move(list)).first->second;
        };
        if(enumerate(nullptr).empty())throw std::runtime_error("Original merged file index is empty");
        std::vector<std::string> results;
        for(auto& requested:task->paths){
            auto path=Wide(requested);HTREEITEM parent=nullptr;bool present=true;size_t start=0,depth=0;
            while(start<path.size()){
                if(++depth>64)throw std::runtime_error("Original resource path depth exceeded");
                auto end=path.find(L'\\',start);auto name=path.substr(start,end==path.npos?path.npos:end-start);
                if(name.empty()||name==L"."||name==L".."||name.find(L':')!=name.npos)throw std::runtime_error("Noncanonical native resource path");
                auto& siblings=enumerate(parent);auto found=siblings.find(Fold(name));
                if(found==siblings.end()){present=false;break;}parent=found->second;
                if(end==path.npos)break;start=end+1;
            }
            if(present){TVITEMW item{};item.mask=TVIF_CHILDREN;item.hItem=parent;if(!SendMessageW(tree,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&item)))throw std::runtime_error("Original resource file identity unreadable");if(item.cChildren)present=false;}
            results.push_back("{\"path\":"+Q(requested)+",\"status\":"+Q(present?"present":"missing")+"}");
        }
        task->result="{\"source\":\"original merged Archive Browser\",\"complete\":true,\"nodesEnumerated\":"+std::to_string(nodes)+",\"foldersEnumerated\":"+std::to_string(children.size())+",\"resources\":"+Join(results)+"}";
    }catch(const std::exception& e){task->error=e.what();}
    DataAssetCancel(browser);
}
static void Files(Block* b,HWND data){
    try{
        auto size=std::filesystem::file_size(b->mapPath);if(size>kSourceCapacity)throw std::runtime_error("Native resource input exceeds bound");
        BrowserTask task{b,GetTickCount64()};
        std::ifstream input(std::filesystem::path(b->mapPath),std::ios::binary);if(!input)throw std::runtime_error("Cannot open private resource request");
        std::string line;std::set<std::wstring> unique;
        while(std::getline(input,line)){
            if(!line.empty()&&line.back()=='\r')line.pop_back();
            if(line.empty()||line.size()>32767||line.find_first_of("\0\r\n",0,3)!=line.npos||task.paths.size()>=200000)throw std::runtime_error("Invalid native resource input line");
            if(!unique.insert(Fold(Wide(line))).second)throw std::runtime_error("Duplicate native resource input");task.paths.push_back(line);
        }
        if(!input.eof())throw std::runtime_error("Native resource input was not fully read");
        if(task.paths.empty()){task.result="{\"source\":\"original merged Archive Browser\",\"complete\":true,\"resources\":[]}";}
        else{
            for(auto root:Roots())if(IsWindowVisible(root)&&Text(root)==L"Archive Browser")throw std::runtime_error("An existing owned Archive Browser blocks a fresh resource check");
            HWND console=nullptr;for(auto root:Roots())if(Text(root)==L"Console - StarCraft II Editor"){if(console)throw std::runtime_error("Ambiguous original Console");console=root;}
            if(!console||!IsWindowVisible(console)){auto command=FindCommand(data,{L"Window"},{L"Console"});if(!command)throw std::runtime_error("Original Console command unavailable");SendMessageW(data,WM_COMMAND,command,0);DataPump(100);}
            console=nullptr;for(auto root:Roots())if(Text(root)==L"Console - StarCraft II Editor")console=root;
            auto edit=Control(console,L"RichEdit20W",13),enter=Control(console,L"Button",14);
            if(!edit||!enter)throw std::runtime_error("Original Console command controls unavailable");
            browserTask=&task;auto timer=SetTimer(nullptr,0,250,BrowserTimer);if(!timer){browserTask=nullptr;throw std::runtime_error("Cannot observe original Archive Browser");}
            SendMessageW(edit,WM_SETTEXT,0,reinterpret_cast<LPARAM>(L"browse"));
            SendMessageW(GetParent(enter),WM_COMMAND,MAKEWPARAM(14,BN_CLICKED),reinterpret_cast<LPARAM>(enter));
            while(!task.done&&GetTickCount64()-task.start<300000)DataPump(100);
            KillTimer(nullptr,timer);browserTask=nullptr;
            if(!task.done)throw std::runtime_error("Original Archive Browser did not become ready");
            if(!task.error.empty())throw std::runtime_error(task.error);
        }
        if(task.result.size()>=kSourceCapacity)throw std::runtime_error("Native resource result exceeds complete transport bound");
        memcpy(b->source,task.result.data(),task.result.size());b->sourceBytes=uint32_t(task.result.size());b->codePage=CP_UTF8;
    }catch(const std::exception& e){Log(b,L"Data resource audit: %S\n",e.what());Fail(b,171,L"Original merged resource audit could not be confirmed completely");}
}
}
