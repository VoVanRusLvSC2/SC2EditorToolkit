// Immutable private Win32 clipboard snapshot exposed through the OLE contract.
// An empty clipboard is readable; it is not CLIPBRD_E_CANT_OPEN (a lock error).
#include <shlobj.h>
#pragma comment(lib,"shell32.lib")
class DataMemoryObject final:public IDataObject{
    LONG refs=1;
    std::map<CLIPFORMAT,std::vector<unsigned char>> values;
public:
    explicit DataMemoryObject(const std::map<UINT,HANDLE>& handles){
        size_t total=0;
        for(auto entry:handles){
            auto bytes=GlobalSize(entry.second);
            if(!bytes||bytes>32*1024*1024||total+bytes>32*1024*1024)continue;
            auto source=static_cast<unsigned char*>(GlobalLock(entry.second));if(!source)continue;
            values[CLIPFORMAT(entry.first)]={source,source+bytes};total+=bytes;GlobalUnlock(entry.second);
        }
    }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out)override{
        if(!out)return E_POINTER;*out=nullptr;
        if(id==__uuidof(IUnknown)||id==__uuidof(IDataObject)){*out=this;AddRef();return S_OK;}return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef()override{return InterlockedIncrement(&refs);}
    ULONG STDMETHODCALLTYPE Release()override{auto left=InterlockedDecrement(&refs);if(!left)delete this;return left;}
    HRESULT STDMETHODCALLTYPE QueryGetData(FORMATETC* format)override{
        if(!format)return E_POINTER;
        if(!(format->tymed&TYMED_HGLOBAL))return DV_E_TYMED;
        if(format->dwAspect!=DVASPECT_CONTENT)return DV_E_DVASPECT;
        if(format->lindex!=-1)return DV_E_LINDEX;
        return values.count(format->cfFormat)?S_OK:DV_E_FORMATETC;
    }
    HRESULT STDMETHODCALLTYPE GetData(FORMATETC* format,STGMEDIUM* medium)override{
        if(!medium)return E_POINTER;*medium={};auto status=QueryGetData(format);if(FAILED(status))return status;
        auto& bytes=values.at(format->cfFormat);auto copy=GlobalAlloc(GMEM_MOVEABLE,bytes.size());if(!copy)return E_OUTOFMEMORY;
        auto target=GlobalLock(copy);if(!target){GlobalFree(copy);return E_OUTOFMEMORY;}
        memcpy(target,bytes.data(),bytes.size());GlobalUnlock(copy);medium->tymed=TYMED_HGLOBAL;medium->hGlobal=copy;return S_OK;
    }
    HRESULT STDMETHODCALLTYPE GetDataHere(FORMATETC*,STGMEDIUM*)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE GetCanonicalFormatEtc(FORMATETC*,FORMATETC* out)override{if(!out)return E_POINTER;out->ptd=nullptr;return DATA_S_SAMEFORMATETC;}
    HRESULT STDMETHODCALLTYPE SetData(FORMATETC*,STGMEDIUM*,BOOL)override{return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE EnumFormatEtc(DWORD direction,IEnumFORMATETC** out)override{
        if(!out)return E_POINTER;*out=nullptr;if(direction!=DATADIR_GET)return E_NOTIMPL;
        std::vector<FORMATETC> formats;for(auto& entry:values)formats.push_back({entry.first,nullptr,DVASPECT_CONTENT,-1,TYMED_HGLOBAL});
        return SHCreateStdEnumFmtEtc(UINT(formats.size()),formats.data(),out);
    }
    HRESULT STDMETHODCALLTYPE DAdvise(FORMATETC*,DWORD,IAdviseSink*,DWORD*)override{return OLE_E_ADVISENOTSUPPORTED;}
    HRESULT STDMETHODCALLTYPE DUnadvise(DWORD)override{return OLE_E_ADVISENOTSUPPORTED;}
    HRESULT STDMETHODCALLTYPE EnumDAdvise(IEnumSTATDATA**)override{return OLE_E_ADVISENOTSUPPORTED;}
};
