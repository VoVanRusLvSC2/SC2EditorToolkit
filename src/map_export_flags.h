#pragma once
#include <windows.h>
#include <commctrl.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>

// Build-specific adapter for the SHA-pinned 5.0.17.98310 Editor. Its flag tree
// has a separate model: TVM_SETITEM only paints a checkbox and does not change
// the flags read by CMapImageGenerator. Use the original model setter/getter.
// Resolve only the live model bound to this request's owned GUI-thread HWND;
// never retain model pointers after the export dialog has closed.
class MapExportFlags {
    uintptr_t base_=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr)),model_=0;
    HWND tree_=nullptr;
    uint32_t reason_=0,hits_=0,best_=0,count_=0;uint64_t scanned_=0;
    uint32_t row_=0,id_=0,visible_=0;int32_t alias_=0;LPARAM parameter_=-1;
    static bool Read(uintptr_t address,void* value,SIZE_T size){
        SIZE_T got=0;return address&&ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),value,size,&got)&&got==size;
    }
    template<class T> static bool Field(uintptr_t address,T& value){return Read(address,&value,sizeof(value));}
    bool Model(uintptr_t address){
        uintptr_t table=0,wrapper=0,window=0,callback=0,context=0,rows=0;uint32_t count=0;
        if(!Field(address,table)||table!=base_+0x35be1b0||!Field(address+0x20,wrapper))return false;
        best_=(std::max)(best_,1u);
        if(!Field(wrapper+0x98,window)||window!=reinterpret_cast<uintptr_t>(tree_))return false;
        best_=(std::max)(best_,2u);
        if(!Field(wrapper+0xd8,callback)||callback!=base_+0x8b5130)return false;
        best_=(std::max)(best_,3u);
        if(!Field(wrapper+0xe0,context)||context!=address)return false;
        best_=(std::max)(best_,4u);
        if(!Field(address+0x70,count))return false;count_=count;
        if(count!=54||!Field(address+0x80,rows))return false;
        best_=(std::max)(best_,5u);
        // Some build-profile rows are intentionally hidden (null item). Check
        // all IDs/aliases and validate every materialized item against this
        // live Win32 tree; an unrelated or stale model cannot satisfy this.
        uint32_t visible=0;uint64_t ids=0;
        for(uint32_t i=0;i<count;++i){
            uint32_t id=0;int32_t alias=0;uintptr_t item=0;
            row_=i;parameter_=-1;
            if(!Field(rows+i*0xc8,id))return false;id_=id;
            if(id>=54||(ids&(uint64_t(1)<<id))||!Field(rows+i*0xc8+4,alias))return false;alias_=alias;
            if(alias < -1||alias>255||!Field(rows+i*0xc8+8,item))return false;
            ids|=uint64_t(1)<<id;
            if(item){
                TVITEMW row{};row.mask=TVIF_PARAM;row.hItem=reinterpret_cast<HTREEITEM>(item);
                if(!SendMessageW(tree_,TVM_GETITEMW,0,reinterpret_cast<LPARAM>(&row)))return false;
                // lParam is Win32 control metadata, not the authoritative
                // native flag ID. The original callback resolves by HTREEITEM.
                parameter_=row.lParam;
                ++visible;visible_=visible;
            }
        }
        return visible>=13;
    }
    static bool Call(uintptr_t base,uintptr_t model,uint32_t id,bool set,bool wanted,bool* actual){
        __try{
            if(set)reinterpret_cast<void(*)(void*,uint32_t,bool)>(base+0x8b4c40)(reinterpret_cast<void*>(model),id,wanted);
            *actual=reinterpret_cast<bool(*)(void*,uint32_t)>(base+0x8b3f10)(reinterpret_cast<void*>(model),id);return true;
        }__except(EXCEPTION_EXECUTE_HANDLER){return false;}
    }
public:
    uint32_t Reason()const{return reason_;}uint32_t Hits()const{return hits_;}
    uint32_t Profile()const{return best_;}uint32_t Count()const{return count_;}uint64_t Scanned()const{return scanned_;}
    uint32_t Row()const{return row_;}uint32_t Id()const{return id_;}int32_t Alias()const{return alias_;}
    uint32_t Visible()const{return visible_;}LPARAM Parameter()const{return parameter_;}
    bool Bind(HWND tree){
        DWORD pid=0;auto tid=GetWindowThreadProcessId(tree,&pid);
        reason_=1;if(pid!=GetCurrentProcessId()||tid!=GetCurrentThreadId())return false;
        tree_=tree;model_=0;
        // ASLR-relative RVAs are permitted only when both original function
        // signatures match. No guessed call or fallback checkbox-only export.
        constexpr unsigned char setter[]={0x40,0x53,0x45,0x33,0xc9,0x44,0x8b,0xda,0x8b,0x51,0x70,0x48,0x8b,0xd9};
        constexpr unsigned char getter[]={0x48,0x89,0x5c,0x24,0x08,0x44,0x8b,0x49,0x70,0x33,0xdb,0x4c,0x8b,0xd9};
        unsigned char a[sizeof(setter)]{},b[sizeof(getter)]{};
        reason_=2;if(!Read(base_+0x8b4c40,a,sizeof(a))||memcmp(a,setter,sizeof(a))||
            !Read(base_+0x8b3f10,b,sizeof(b))||memcmp(b,getter,sizeof(b)))return false;
        // The native wrapper exposes no public HWND->model accessor. Search
        // committed writable private memory for its exact vtable, then require
        // the reciprocal HWND/callback/context and all 54 rows. Snapshots are
        // bounded, read-only and discarded; no raw snapshots are logged/saved.
        std::vector<uintptr_t> chunk(1024*1024/sizeof(uintptr_t));
        MEMORY_BASIC_INFORMATION region{};uintptr_t address=0;
        const auto deadline=GetTickCount64()+5000;
        while(VirtualQuery(reinterpret_cast<void*>(address),&region,sizeof(region))){
            auto next=reinterpret_cast<uintptr_t>(region.BaseAddress)+region.RegionSize;
            reason_=3;if(next<=address)return false;address=next;
            reason_=4;if(GetTickCount64()>deadline||scanned_>uint64_t(2)*1024*1024*1024)return false;
            if(region.State!=MEM_COMMIT||region.Type!=MEM_PRIVATE||
                (region.Protect&0xff)!=PAGE_READWRITE||(region.Protect&(PAGE_GUARD|PAGE_NOACCESS)))continue;
            for(SIZE_T offset=0;offset<region.RegionSize;){
                reason_=4;if(GetTickCount64()>deadline||scanned_>=uint64_t(2)*1024*1024*1024)return false;
                SIZE_T size=(std::min)(region.RegionSize-offset,chunk.size()*sizeof(uintptr_t));
                auto start=reinterpret_cast<uintptr_t>(region.BaseAddress)+offset;
                if(Read(start,chunk.data(),size))for(SIZE_T i=0;i<size/sizeof(uintptr_t);++i){
                    if(chunk[i]!=base_+0x35be1b0)continue;
                    ++hits_;
                    auto candidate=start+i*sizeof(uintptr_t);
                    if(Model(candidate)){model_=candidate;reason_=0;return true;}
                }
                offset+=size;scanned_+=size;
            }
        }
        reason_=5;return false;
    }
    bool Value(HTREEITEM item,bool apply,bool wanted,bool* actual){
        if(!model_||!Model(model_))return false;
        uintptr_t rows=0,nativeItem=0;uint32_t matches=0,selected=0;
        if(!Field(model_+0x80,rows))return false;
        // Match the original tree callback: resolve the unique HTREEITEM to
        // its stable model ID; neither array position nor TVITEM.lParam is an ID.
        for(uint32_t i=0;i<54;++i){
            uint32_t id=0;if(!Field(rows+i*0xc8,id)||!Field(rows+i*0xc8+8,nativeItem))return false;
            if(nativeItem==reinterpret_cast<uintptr_t>(item)){++matches;selected=id;}
        }
        if(matches!=1)return false;
        return Call(base_,model_,selected,apply,wanted,actual)&&*actual==wanted;
    }
};
