#include <windows.h>
#include <string>
#include <vector>
#include <cstring>
#include <iostream>
#include <stdexcept>
static bool PrivateDesktop(){wchar_t name[128]{};DWORD size=0;return GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,name,sizeof(name),&size)&&wcsncmp(name,L"SC2Native-",10)==0;}
#include "../src/data_clipboard.inc"
static void Require(bool value,const char* why){if(!value)throw std::runtime_error(why);}
static HGLOBAL TextHandle(const wchar_t* value){auto bytes=(wcslen(value)+1)*sizeof(wchar_t);auto data=GlobalAlloc(GMEM_MOVEABLE,bytes);auto p=GlobalLock(data);memcpy(p,value,bytes);GlobalUnlock(data);return data;}
class TextObject:public IDataObject{
    LONG refs=1;
public:
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out)override{if(!out)return E_POINTER;*out=nullptr;if(id==IID_IUnknown||id==IID_IDataObject){*out=this;AddRef();return S_OK;}return E_NOINTERFACE;}
    ULONG STDMETHODCALLTYPE AddRef()override{return InterlockedIncrement(&refs);}
    ULONG STDMETHODCALLTYPE Release()override{auto count=InterlockedDecrement(&refs);if(!count)delete this;return count;}
    HRESULT STDMETHODCALLTYPE GetData(FORMATETC* f,STGMEDIUM* m)override{if(f->cfFormat!=CF_UNICODETEXT)return DV_E_FORMATETC;m->tymed=TYMED_HGLOBAL;m->hGlobal=TextHandle(L"original OLE Data text");m->pUnkForRelease=nullptr;return S_OK;}
    HRESULT STDMETHODCALLTYPE GetDataHere(FORMATETC*,STGMEDIUM*)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE QueryGetData(FORMATETC* f)override{return f->cfFormat==CF_UNICODETEXT?S_OK:DV_E_FORMATETC;}
    HRESULT STDMETHODCALLTYPE GetCanonicalFormatEtc(FORMATETC*,FORMATETC*)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE SetData(FORMATETC*,STGMEDIUM*,BOOL)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE EnumFormatEtc(DWORD,IEnumFORMATETC**)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE DAdvise(FORMATETC*,DWORD,IAdviseSink*,DWORD*)override{return OLE_E_ADVISENOTSUPPORTED;}
    HRESULT STDMETHODCALLTYPE DUnadvise(DWORD)override{return OLE_E_ADVISENOTSUPPORTED;}
    HRESULT STDMETHODCALLTYPE EnumDAdvise(IEnumSTATDATA**)override{return OLE_E_ADVISENOTSUPPORTED;}
};
int main(){
    try{
        Require(!PrivateDesktop(),"Test must start on its normal desktop");Require(!EnsureDataClipboard(),"Refuse clipboard hooks outside an owned private desktop");
        auto before=GetClipboardSequenceNumber();auto original=GetThreadDesktop(GetCurrentThreadId());
        wchar_t name[128]{};swprintf_s(name,L"SC2Native-ClipboardTest-%lu",GetCurrentProcessId());
        auto desktop=CreateDesktopW(name,nullptr,nullptr,0,GENERIC_ALL,nullptr);Require(desktop&&SetThreadDesktop(desktop),"Cannot create private test desktop");
        Require(EnsureDataClipboard(),"Cannot install private process clipboard");
        Require(OpenClipboard(nullptr)&&EmptyClipboard(),"Virtual open/empty failed");
        Require(SetClipboardData(CF_UNICODETEXT,TextHandle(L"native table\t73\r\n"))!=nullptr,"Virtual Win32 set failed");
        Require(DataCopiedText()==L"native table\t73\r\n","Win32 exact text capture failed");
        Require(CountClipboardFormats()==1,"Format count leaked system clipboard state");
        UINT formats[4]{};UINT count=0;Require(GetUpdatedClipboardFormats(formats,4,&count)&&count==1&&formats[0]==CF_UNICODETEXT,"Updated formats leaked system state");
        SetLastError(ERROR_INVALID_PARAMETER);Require(EnumClipboardFormats(CF_UNICODETEXT)==0&&GetLastError()==ERROR_SUCCESS,"End of private enumeration retained a false error");
        Require(IsClipboardFormatAvailable(CF_UNICODETEXT)&&EnumClipboardFormats(0)==CF_UNICODETEXT,"Private format discovery failed");Require(CloseClipboard(),"Virtual close failed");
        IDataObject* snapshot=nullptr;Require(OleGetClipboard(&snapshot)==S_OK&&snapshot,"Win32-to-OLE snapshot unavailable");
        FORMATETC format{CF_UNICODETEXT,nullptr,DVASPECT_CONTENT,-1,TYMED_HGLOBAL};STGMEDIUM data{};
        Require(snapshot->GetData(&format,&data)==S_OK,"Win32-to-OLE text unavailable");
        auto text=static_cast<wchar_t*>(GlobalLock(data.hGlobal));Require(text&&std::wstring(text)==L"native table\t73\r\n","Snapshot changed exact text");GlobalUnlock(data.hGlobal);ReleaseStgMedium(&data);snapshot->Release();
        auto object=new TextObject;Require(OleSetClipboard(object)==S_OK,"Virtual OLE set failed");object->Release();
        Require(DataCopiedText()==L"original OLE Data text","OLE exact text capture failed");
        IDataObject* read=nullptr;Require(OleGetClipboard(&read)==S_OK&&read&&OleIsCurrentClipboard(read)==S_OK,"Private OLE identity failed");read->Release();Require(OleFlushClipboard()==S_OK,"Private OLE flush failed");
        auto actual=reinterpret_cast<DWORD(WINAPI*)()>(dataClipSystemSequence)();
        Require(actual==before,"System clipboard changed during the test (may also indicate an external user copy)");
        DataClipEmpty();snapshot=nullptr;Require(OleGetClipboard(&snapshot)==S_OK&&snapshot,"Empty OLE clipboard falsely reported lock error");
        Require(snapshot->QueryGetData(&format)==DV_E_FORMATETC,"Empty OLE clipboard fabricated text");
        IEnumFORMATETC* enumeration=nullptr;Require(snapshot->EnumFormatEtc(DATADIR_GET,&enumeration)==S_OK&&enumeration,"Empty format enumeration unavailable");
        FORMATETC empty{};ULONG fetched=99;Require(enumeration->Next(1,&empty,&fetched)==S_FALSE&&fetched==0,"Empty enumeration exposed a format");enumeration->Release();
        snapshot->Release();SetThreadDesktop(original);CloseDesktop(desktop);
        std::cout<<"Private clipboard: Win32/OLE exact text, formats, ownership and unchanged system sequence passed\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
