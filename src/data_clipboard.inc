// Process-private clipboard for the owned hidden Editor. Original Copy As Text
// can serialize complete cells without reading/writing the user's clipboard.
#include <ole2.h>
#include <map>
#include <mutex>
#include "../vendor/minhook/include/MinHook.h"
#pragma comment(lib,"ole32.lib")
static std::recursive_mutex dataClipMutex;
static std::map<UINT,HANDLE> dataClipHandles;
static IDataObject* dataClipObject;
static HWND dataClipOwner;
static bool dataClipOpened;
static bool dataClipReady;
static DWORD dataClipSequence=1;
static void* dataClipSystemSequence;
static BOOL WINAPI DataClipOpen(HWND owner){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);dataClipOwner=owner;dataClipOpened=true;SetLastError(ERROR_SUCCESS);return TRUE;}
static BOOL WINAPI DataClipClose(){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);dataClipOpened=false;SetLastError(ERROR_SUCCESS);return TRUE;}
static BOOL WINAPI DataClipEmpty(){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);
    for(auto entry:dataClipHandles)if(entry.first==CF_UNICODETEXT||entry.first==CF_TEXT||entry.first>=0xc000)GlobalFree(entry.second);
    dataClipHandles.clear();if(dataClipObject){auto old=dataClipObject;dataClipObject=nullptr;old->Release();}++dataClipSequence;SetLastError(ERROR_SUCCESS);return TRUE;
}
static HANDLE WINAPI DataClipSet(UINT format,HANDLE handle){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);dataClipHandles[format]=handle;++dataClipSequence;SetLastError(ERROR_SUCCESS);return handle;
}
static HANDLE WINAPI DataClipGet(UINT format){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);SetLastError(ERROR_SUCCESS);
    auto found=dataClipHandles.find(format);if(found!=dataClipHandles.end())return found->second;
    if(dataClipObject){
        FORMATETC request{CLIPFORMAT(format),nullptr,DVASPECT_CONTENT,-1,TYMED_HGLOBAL};STGMEDIUM medium{};
        if(SUCCEEDED(dataClipObject->GetData(&request,&medium))&&medium.tymed==TYMED_HGLOBAL){
            SIZE_T bytes=GlobalSize(medium.hGlobal);HGLOBAL copy=nullptr;
            if(bytes&&bytes<=32*1024*1024){void* source=GlobalLock(medium.hGlobal);copy=GlobalAlloc(GMEM_MOVEABLE,bytes);void* destination=copy?GlobalLock(copy):nullptr;
                if(source&&destination)memcpy(destination,source,bytes);else{if(copy)GlobalFree(copy);copy=nullptr;}
                if(source)GlobalUnlock(medium.hGlobal);if(destination)GlobalUnlock(copy);
            }ReleaseStgMedium(&medium);if(copy)dataClipHandles[format]=copy;return copy;
        }
    }SetLastError(ERROR_SUCCESS);return nullptr;
}
static BOOL WINAPI DataClipAvailable(UINT format){return DataClipGet(format)!=nullptr;}
static UINT WINAPI DataClipEnum(UINT after){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);auto item=dataClipHandles.upper_bound(after);SetLastError(ERROR_SUCCESS);return item==dataClipHandles.end()?0:item->first;}
static int WINAPI DataClipCount(){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);SetLastError(ERROR_SUCCESS);return int(dataClipHandles.size());}
static HWND WINAPI DataClipOpenWindow(){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);SetLastError(ERROR_SUCCESS);return dataClipOpened?dataClipOwner:nullptr;}
static BOOL WINAPI DataClipUpdated(PUINT formats,UINT capacity,PUINT written){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);
    if(!written){SetLastError(ERROR_INVALID_PARAMETER);return FALSE;}
    *written=UINT(dataClipHandles.size());if(capacity<*written){SetLastError(ERROR_INSUFFICIENT_BUFFER);return FALSE;}
    if(*written&&!formats){SetLastError(ERROR_INVALID_PARAMETER);return FALSE;}
    UINT index=0;for(auto entry:dataClipHandles)formats[index++]=entry.first;SetLastError(ERROR_SUCCESS);return TRUE;
}
static int WINAPI DataClipPriority(UINT* formats,int count){
    if(count<0||(count&&!formats)){SetLastError(ERROR_INVALID_PARAMETER);return -1;}
    for(int i=0;i<count;i++)if(DataClipAvailable(formats[i]))return int(formats[i]);return DataClipCount()? -1:0;
}
static HWND WINAPI DataClipOwner(){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);return dataClipOwner;}
static DWORD WINAPI DataClipSequence(){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);return dataClipSequence;}
static HRESULT WINAPI DataClipOleSet(IDataObject* object){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);if(object)object->AddRef();DataClipEmpty();dataClipObject=object;return S_OK;
}
#include "data_clipboard_object.inc"
static HRESULT WINAPI DataClipOleGet(IDataObject** object){
    if(!object)return E_POINTER;std::lock_guard<std::recursive_mutex> lock(dataClipMutex);
    if(dataClipObject){*object=dataClipObject;(*object)->AddRef();return S_OK;}
    *object=new(std::nothrow) DataMemoryObject(dataClipHandles);return *object?S_OK:E_OUTOFMEMORY;
}
static HRESULT WINAPI DataClipOleCurrent(IDataObject* object){std::lock_guard<std::recursive_mutex> lock(dataClipMutex);return object&&object==dataClipObject?S_OK:S_FALSE;}
static HRESULT WINAPI DataClipOleFlush(){
    std::lock_guard<std::recursive_mutex> lock(dataClipMutex);
    // Materialize supported text before releasing delayed rendering objects;
    // they must not keep a closed map's live Data model referenced.
    if(dataClipObject){DataClipGet(CF_UNICODETEXT);DataClipGet(CF_TEXT);auto old=dataClipObject;dataClipObject=nullptr;old->Release();}
    return S_OK;
}
static bool EnsureDataClipboard(){
    if(dataClipReady)return true;if(!PrivateDesktop())return false;
    auto status=MH_Initialize();if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED)return false;
    struct Hook{const wchar_t* module;const char* name;void* replacement;};
    Hook hooks[]={{L"user32.dll","OpenClipboard",reinterpret_cast<void*>(DataClipOpen)},
        {L"user32.dll","CloseClipboard",reinterpret_cast<void*>(DataClipClose)},
        {L"user32.dll","EmptyClipboard",reinterpret_cast<void*>(DataClipEmpty)},
        {L"user32.dll","SetClipboardData",reinterpret_cast<void*>(DataClipSet)},
        {L"user32.dll","GetClipboardData",reinterpret_cast<void*>(DataClipGet)},
        {L"user32.dll","IsClipboardFormatAvailable",reinterpret_cast<void*>(DataClipAvailable)},
        {L"user32.dll","EnumClipboardFormats",reinterpret_cast<void*>(DataClipEnum)},
        {L"user32.dll","CountClipboardFormats",reinterpret_cast<void*>(DataClipCount)},
        {L"user32.dll","GetOpenClipboardWindow",reinterpret_cast<void*>(DataClipOpenWindow)},
        {L"user32.dll","GetUpdatedClipboardFormats",reinterpret_cast<void*>(DataClipUpdated)},
        {L"user32.dll","GetPriorityClipboardFormat",reinterpret_cast<void*>(DataClipPriority)},
        {L"user32.dll","GetClipboardOwner",reinterpret_cast<void*>(DataClipOwner)},
        {L"user32.dll","GetClipboardSequenceNumber",reinterpret_cast<void*>(DataClipSequence)},
        {L"ole32.dll","OleSetClipboard",reinterpret_cast<void*>(DataClipOleSet)},
        {L"ole32.dll","OleGetClipboard",reinterpret_cast<void*>(DataClipOleGet)},
        {L"ole32.dll","OleIsCurrentClipboard",reinterpret_cast<void*>(DataClipOleCurrent)},
        {L"ole32.dll","OleFlushClipboard",reinterpret_cast<void*>(DataClipOleFlush)}};
    std::vector<void*> addresses;
    for(auto& hook:hooks){
        auto module=GetModuleHandleW(hook.module);if(!module)module=LoadLibraryW(hook.module);
        void* address=module?reinterpret_cast<void*>(GetProcAddress(module,hook.name)):nullptr;
        void** original=strcmp(hook.name,"GetClipboardSequenceNumber")==0?&dataClipSystemSequence:nullptr;
        if(!address||MH_CreateHook(address,hook.replacement,original)!=MH_OK){for(auto value:addresses)MH_RemoveHook(value);return false;}
        addresses.push_back(address);
    }
    for(auto address:addresses)if(MH_EnableHook(address)!=MH_OK){for(auto value:addresses){MH_DisableHook(value);MH_RemoveHook(value);}return false;}
    // Remain isolated for this owned process's lifetime, including delayed OLE
    // rendering. No clipboard function above forwards to the system clipboard.
    dataClipReady=true;return true;
}
static std::wstring DataCopiedText(){
    auto handle=DataClipGet(CF_UNICODETEXT);SIZE_T bytes=handle?GlobalSize(handle):0;
    if(bytes&&bytes<=32*1024*1024){auto text=static_cast<const wchar_t*>(GlobalLock(handle));if(text){std::wstring value(text,wcsnlen_s(text,bytes/sizeof(wchar_t)));GlobalUnlock(handle);return value;}}
    handle=DataClipGet(CF_TEXT);bytes=handle?GlobalSize(handle):0;
    if(bytes&&bytes<=32*1024*1024){auto text=static_cast<const char*>(GlobalLock(handle));if(text){int length=int(strnlen_s(text,bytes));int n=MultiByteToWideChar(CP_ACP,0,text,length,nullptr,0);std::wstring value(n,0);MultiByteToWideChar(CP_ACP,0,text,length,value.data(),n);GlobalUnlock(handle);return value;}}
    return {};
}
