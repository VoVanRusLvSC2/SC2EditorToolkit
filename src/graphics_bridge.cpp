#include "graphics_bridge.h"
#include <d3d9.h>
#include <deque>
#include <mutex>
#include <unordered_map>
#include <functional>
#include <string>
#include <vector>
#include <wincodec.h>
#include "capture_protocol.h"
#include "../vendor/minhook/include/MinHook.h"
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"windowscodecs.lib")
#pragma comment(lib,"ole32.lib")
static void BeforePresent(IDirect3DDevice9* device,IDirect3DSwapChain9* chain=nullptr,HWND window=nullptr);
static HANDLE workEvent,readyEvent;
static DWORD renderTid;
static HWND renderWindow;
static std::wstring graphicsLog;
static std::mutex queueLock,objectLock;
struct Task {std::function<void()> fn;HANDLE done;};
static std::deque<Task*> queue;
struct Object {void** original;void** clone;HWND originalFocus;bool ex;};
static std::unordered_map<void*,Object> objects;
static void Log(const wchar_t* line,HRESULT status=0){
    wchar_t out[512]{};swprintf_s(out,L"%s status=%08lx thread=%lu\r\n",line,static_cast<ULONG>(status),GetCurrentThreadId());
    char bytes[2048]{};int n=WideCharToMultiByte(CP_UTF8,0,out,-1,bytes,sizeof(bytes),nullptr,nullptr);HANDLE f=CreateFileW(graphicsLog.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(f!=INVALID_HANDLE_VALUE){DWORD written;WriteFile(f,bytes,n-1,&written,nullptr);CloseHandle(f);}
}
static void Trace(const wchar_t* line){static volatile LONG count=0;if(InterlockedIncrement(&count)<1000)Log(line);}
static void Invoke(const std::function<void()>& fn){
    if(GetCurrentThreadId()==renderTid){fn();return;}
    Task task{fn,CreateEventW(nullptr,FALSE,FALSE,nullptr)};
    {std::lock_guard<std::mutex> lock(queueLock);queue.push_back(&task);}SetEvent(workEvent);
    WaitForSingleObject(task.done,INFINITE);CloseHandle(task.done);
}
static LRESULT CALLBACK Guard(int n,WPARAM w,LPARAM l){
    if(n==HCBT_ACTIVATE||n==HCBT_SETFOCUS||n==HCBT_MINMAX)return 1;
    if(n==HCBT_CREATEWND){auto c=reinterpret_cast<CBT_CREATEWNDW*>(l);c->lpcs->style&=~WS_VISIBLE;c->lpcs->dwExStyle|=WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW;}
    return CallNextHookEx(nullptr,n,w,l);
}
static DWORD WINAPI RenderThread(void*){
    HDESK input=OpenInputDesktop(0,FALSE,DESKTOP_CREATEWINDOW|DESKTOP_READOBJECTS|DESKTOP_WRITEOBJECTS);if(!input||!SetThreadDesktop(input)){SetEvent(readyEvent);return 1;}
    renderTid=GetCurrentThreadId();CoInitializeEx(nullptr,COINIT_MULTITHREADED);HHOOK guard=SetWindowsHookExW(WH_CBT,Guard,nullptr,renderTid);
    WNDCLASSW c{};c.lpfnWndProc=DefWindowProcW;c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"SC2NativeHiddenRenderWindow";RegisterClassW(&c);
    renderWindow=CreateWindowExW(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,c.lpszClassName,L"",WS_POPUP,0,0,1024,768,nullptr,nullptr,c.hInstance,nullptr);
    Log(renderWindow?L"hidden render window ready":L"hidden render window failed",renderWindow?S_OK:E_FAIL);SetEvent(readyEvent);
    for(;;){
        MsgWaitForMultipleObjects(1,&workEvent,FALSE,INFINITE,QS_ALLINPUT);
        MSG m{};while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}
        for(;;){Task* task=nullptr;{std::lock_guard<std::mutex> lock(queueLock);if(!queue.empty()){task=queue.front();queue.pop_front();}}
            if(!task)break;task->fn();SetEvent(task->done);
        }
    }
    UnhookWindowsHookEx(guard);return 0;
}
template<class T> static T Original(void* self,int slot){std::lock_guard<std::mutex> lock(objectLock);return reinterpret_cast<T>(objects.at(self).original[slot]);}
static Object Metadata(void* self){std::lock_guard<std::mutex> lock(objectLock);return objects.at(self);}
static void Forget(void* self){std::lock_guard<std::mutex> lock(objectLock);auto it=objects.find(self);if(it!=objects.end()){HeapFree(GetProcessHeap(),0,it->second.clone);objects.erase(it);}}
static HRESULT STDMETHODCALLTYPE QI(void* self,REFIID id,void** result){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,REFIID,void**)>(self,0);HRESULT h=E_FAIL;Invoke([&]{h=fn(self,id,result);});return h;}
static ULONG STDMETHODCALLTYPE AddRef(void* self){auto fn=Original<ULONG(STDMETHODCALLTYPE*)(void*)>(self,1);ULONG n=0;Invoke([&]{n=fn(self);});return n;}
static ULONG STDMETHODCALLTYPE Release(void* self){ULONG n=0;Invoke([&]{
    auto meta=Metadata(self);auto fn=reinterpret_cast<ULONG(STDMETHODCALLTYPE*)(void*)>(meta.original[2]);
    // Some D3D9 objects retain internal references after their public COM count
    // becomes zero. Let destruction/internal callbacks see the real vtable.
    InterlockedExchangePointer(reinterpret_cast<void* volatile*>(self),meta.original);
    n=fn(self);if(n)InterlockedExchangePointer(reinterpret_cast<void* volatile*>(self),meta.clone);else Forget(self);
});return n;}
static HRESULT STDMETHODCALLTYPE Cooperative(void* self){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*)>(self,3);HRESULT h;Invoke([&]{h=fn(self);});return h;}
static D3DPRESENT_PARAMETERS Parameters(const D3DPRESENT_PARAMETERS* input){
    auto p=*input;RECT viewport{};
    // Preserve D3D's original zero-size semantics before replacing the HWND.
    if(p.hDeviceWindow&&GetClientRect(p.hDeviceWindow,&viewport)){
        if(!p.BackBufferWidth&&viewport.right>0)p.BackBufferWidth=static_cast<UINT>(viewport.right);
        if(!p.BackBufferHeight&&viewport.bottom>0)p.BackBufferHeight=static_cast<UINT>(viewport.bottom);
    }
    p.Windowed=TRUE;p.FullScreen_RefreshRateInHz=0;p.hDeviceWindow=renderWindow;return p;
}
static HRESULT STDMETHODCALLTYPE Reset(void* self,D3DPRESENT_PARAMETERS* p){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,D3DPRESENT_PARAMETERS*)>(self,16);auto copy=Parameters(p);HRESULT h;Invoke([&]{h=fn(self,&copy);});return h;}
static HRESULT STDMETHODCALLTYPE Present(void* self,const RECT* source,const RECT* target,HWND window,const RGNDATA* dirty){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,const RECT*,const RECT*,HWND,const RGNDATA*)>(self,17);HRESULT h;Invoke([&]{BeforePresent(static_cast<IDirect3DDevice9*>(self),nullptr,window?window:Metadata(self).originalFocus);h=fn(self,source,target,renderWindow,dirty);});return h;}
static HRESULT STDMETHODCALLTYPE ResetEx(void* self,D3DPRESENT_PARAMETERS* p,D3DDISPLAYMODEEX*){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,D3DPRESENT_PARAMETERS*,D3DDISPLAYMODEEX*)>(self,132);auto copy=Parameters(p);HRESULT h;Invoke([&]{h=fn(self,&copy,nullptr);});return h;}
static HRESULT STDMETHODCALLTYPE PresentEx(void* self,const RECT* source,const RECT* target,HWND window,const RGNDATA* dirty,DWORD flags){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,const RECT*,const RECT*,HWND,const RGNDATA*,DWORD)>(self,121);HRESULT h;Invoke([&]{BeforePresent(static_cast<IDirect3DDevice9*>(self),nullptr,window?window:Metadata(self).originalFocus);h=fn(self,source,target,renderWindow,dirty,flags);});return h;}
static HRESULT STDMETHODCALLTYPE CreationParameters(void* self,D3DDEVICE_CREATION_PARAMETERS* p){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,D3DDEVICE_CREATION_PARAMETERS*)>(self,9);HRESULT h;Invoke([&]{h=fn(self,p);});if(SUCCEEDED(h))p->hFocusWindow=Metadata(self).originalFocus;return h;}
static void** Clone(void* self,size_t slots,HWND focus,bool ex){
    std::lock_guard<std::mutex> lock(objectLock);if(objects.count(self))return nullptr;auto original=*reinterpret_cast<void***>(self);
    // D3D9's implementation also uses private virtual methods after its public
    // COM ABI. Preserve the readable tail, changing public slots only.
    MEMORY_BASIC_INFORMATION region{};VirtualQuery(original,&region,sizeof(region));
    size_t readable=(reinterpret_cast<uintptr_t>(region.BaseAddress)+region.RegionSize-reinterpret_cast<uintptr_t>(original))/sizeof(void*);
    size_t copied=(std::min)(readable,(std::max)(slots,size_t(512)));
    auto clone=static_cast<void**>(HeapAlloc(GetProcessHeap(),0,copied*sizeof(void*)));memcpy(clone,original,copied*sizeof(void*));
    clone[0]=reinterpret_cast<void*>(QI);clone[1]=reinterpret_cast<void*>(AddRef);clone[2]=reinterpret_cast<void*>(Release);objects.emplace(self,Object{original,clone,focus,ex});return clone;
}
static HRESULT STDMETHODCALLTYPE SwapPresent(void* self,const RECT* source,const RECT* target,HWND window,const RGNDATA* dirty,DWORD flags){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,const RECT*,const RECT*,HWND,const RGNDATA*,DWORD)>(self,3);HRESULT h;Invoke([&]{auto chain=static_cast<IDirect3DSwapChain9*>(self);IDirect3DDevice9* device=nullptr;if(SUCCEEDED(chain->GetDevice(&device))&&device){BeforePresent(device,chain,window?window:Metadata(self).originalFocus);device->Release();}h=fn(self,source,target,renderWindow,dirty,flags);});return h;}
#include "d3d_proxies.inc"
static void Wrap_IDirect3DBaseTexture9(IDirect3DBaseTexture9* value){
    if(!value)return;D3DRESOURCETYPE type;Invoke([&]{type=value->GetType();});
    if(type==D3DRTYPE_TEXTURE)Wrap_IDirect3DTexture9(static_cast<IDirect3DTexture9*>(value));
    else if(type==D3DRTYPE_CUBETEXTURE)Wrap_IDirect3DCubeTexture9(static_cast<IDirect3DCubeTexture9*>(value));
    else if(type==D3DRTYPE_VOLUMETEXTURE)Wrap_IDirect3DVolumeTexture9(static_cast<IDirect3DVolumeTexture9*>(value));
}
static void Wrap_IDirect3DResource9(IDirect3DResource9* value){
    D3DRESOURCETYPE type;Invoke([&]{type=value->GetType();});
    if(type==D3DRTYPE_SURFACE)Wrap_IDirect3DSurface9(static_cast<IDirect3DSurface9*>(value));
    else if(type==D3DRTYPE_VERTEXBUFFER)Wrap_IDirect3DVertexBuffer9(static_cast<IDirect3DVertexBuffer9*>(value));
    else if(type==D3DRTYPE_INDEXBUFFER)Wrap_IDirect3DIndexBuffer9(static_cast<IDirect3DIndexBuffer9*>(value));
    else Wrap_IDirect3DBaseTexture9(static_cast<IDirect3DBaseTexture9*>(value));
}
static HRESULT STDMETHODCALLTYPE AdditionalSwapChain(void* self,D3DPRESENT_PARAMETERS* p,IDirect3DSwapChain9** chain){auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,D3DPRESENT_PARAMETERS*,IDirect3DSwapChain9**)>(self,13);auto copy=Parameters(p);HRESULT h;Invoke([&]{h=fn(self,&copy,chain);});if(SUCCEEDED(h)&&*chain){Wrap_IDirect3DSwapChain9(*chain);std::lock_guard<std::mutex> lock(objectLock);objects.at(*chain).originalFocus=p->hDeviceWindow;}return h;}
static void WrapDevice(IDirect3DDevice9* device,HWND focus,bool ex){
    auto table=Clone(device,ex?134:119,focus,ex);if(!table)return;
    if(ex)Fill_IDirect3DDevice9Ex(table);else Fill_IDirect3DDevice9(table);
    table[3]=reinterpret_cast<void*>(Cooperative);table[9]=reinterpret_cast<void*>(CreationParameters);table[13]=reinterpret_cast<void*>(AdditionalSwapChain);table[16]=reinterpret_cast<void*>(Reset);table[17]=reinterpret_cast<void*>(Present);
    if(ex){table[121]=reinterpret_cast<void*>(PresentEx);table[132]=reinterpret_cast<void*>(ResetEx);}
    InterlockedExchangePointer(reinterpret_cast<void* volatile*>(device),table);
}
static void Wrap_IDirect3DDevice9(IDirect3DDevice9* value){WrapDevice(value,nullptr,false);}
static void Wrap_IDirect3DDevice9Ex(IDirect3DDevice9Ex* value){WrapDevice(value,nullptr,true);}
static HRESULT STDMETHODCALLTYPE CreateDevice(void* self,UINT adapter,D3DDEVTYPE type,HWND focus,DWORD flags,D3DPRESENT_PARAMETERS* p,IDirect3DDevice9** device){
    auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,UINT,D3DDEVTYPE,HWND,DWORD,D3DPRESENT_PARAMETERS*,IDirect3DDevice9**)>(self,16);auto copy=Parameters(p);HRESULT h;
    Invoke([&]{h=fn(self,adapter,type,renderWindow,flags|D3DCREATE_MULTITHREADED,&copy,device);});Log(L"redirected CreateDevice",h);
    if(SUCCEEDED(h)&&*device)WrapDevice(*device,focus,false);return h;
}
static HRESULT STDMETHODCALLTYPE CreateDeviceEx(void* self,UINT adapter,D3DDEVTYPE type,HWND focus,DWORD flags,D3DPRESENT_PARAMETERS* p,D3DDISPLAYMODEEX*,IDirect3DDevice9Ex** device){
    auto fn=Original<HRESULT(STDMETHODCALLTYPE*)(void*,UINT,D3DDEVTYPE,HWND,DWORD,D3DPRESENT_PARAMETERS*,D3DDISPLAYMODEEX*,IDirect3DDevice9Ex**)>(self,20);auto copy=Parameters(p);HRESULT h;
    Invoke([&]{h=fn(self,adapter,type,renderWindow,flags|D3DCREATE_MULTITHREADED,&copy,nullptr,device);});Log(L"redirected CreateDeviceEx",h);
    if(SUCCEEDED(h)&&*device)WrapDevice(*device,focus,true);return h;
}
static void WrapFactory(IDirect3D9* api,bool ex){auto table=Clone(api,ex?22:17,nullptr,ex);if(!table)return;if(ex)Fill_IDirect3D9Ex(table);else Fill_IDirect3D9(table);table[16]=reinterpret_cast<void*>(CreateDevice);if(ex)table[20]=reinterpret_cast<void*>(CreateDeviceEx);InterlockedExchangePointer(reinterpret_cast<void* volatile*>(api),table);}
static void Wrap_IDirect3D9(IDirect3D9* value){WrapFactory(value,false);}
static void Wrap_IDirect3D9Ex(IDirect3D9Ex* value){WrapFactory(value,true);}
struct CaptureState {CaptureRequest* request;HANDLE done;};
static CaptureState* pendingCapture;
static uint64_t frameSequence;
static HRESULT SavePng(const wchar_t* path,UINT width,UINT height,std::vector<BYTE>& pixels){
    IWICImagingFactory* factory=nullptr;IWICStream* stream=nullptr;IWICBitmapEncoder* encoder=nullptr;IWICBitmapFrameEncode* frame=nullptr;
    HRESULT h=CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&factory));
    if(SUCCEEDED(h))h=factory->CreateStream(&stream);
    if(SUCCEEDED(h))h=stream->InitializeFromFilename(path,GENERIC_WRITE);
    if(SUCCEEDED(h))h=factory->CreateEncoder(GUID_ContainerFormatPng,nullptr,&encoder);
    if(SUCCEEDED(h))h=encoder->Initialize(stream,WICBitmapEncoderNoCache);
    if(SUCCEEDED(h))h=encoder->CreateNewFrame(&frame,nullptr);
    if(SUCCEEDED(h))h=frame->Initialize(nullptr);
    if(SUCCEEDED(h))h=frame->SetSize(width,height);
    WICPixelFormatGUID format=GUID_WICPixelFormat32bppBGRA;
    if(SUCCEEDED(h))h=frame->SetPixelFormat(&format);
    if(SUCCEEDED(h)&&format!=GUID_WICPixelFormat32bppBGRA)h=WINCODEC_ERR_UNSUPPORTEDPIXELFORMAT;
    if(SUCCEEDED(h))h=frame->WritePixels(height,width*4,static_cast<UINT>(pixels.size()),pixels.data());
    if(SUCCEEDED(h))h=frame->Commit();if(SUCCEEDED(h))h=encoder->Commit();
    if(frame)frame->Release();if(encoder)encoder->Release();if(stream)stream->Release();if(factory)factory->Release();return h;
}
static HRESULT CaptureSurface(IDirect3DDevice9* device,IDirect3DSwapChain9* chain,CaptureRequest& request){
    IDirect3DSurface9* back=nullptr;IDirect3DSurface9* resolved=nullptr;IDirect3DSurface9* staging=nullptr;
    HRESULT h=chain?chain->GetBackBuffer(0,D3DBACKBUFFER_TYPE_MONO,&back):device->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back);
    D3DSURFACE_DESC desc{};D3DLOCKED_RECT locked{};std::vector<BYTE> pixels;
    do{
        if(FAILED(h))break;h=back->GetDesc(&desc);if(FAILED(h))break;
        if(!desc.Width||!desc.Height||desc.Width>8192||desc.Height>8192){h=E_INVALIDARG;break;}
        if(desc.Format!=D3DFMT_X8R8G8B8&&desc.Format!=D3DFMT_A8R8G8B8){h=WINCODEC_ERR_UNSUPPORTEDPIXELFORMAT;break;}
        IDirect3DSurface9* source=back;
        if(desc.MultiSampleType!=D3DMULTISAMPLE_NONE){
            h=device->CreateRenderTarget(desc.Width,desc.Height,desc.Format,D3DMULTISAMPLE_NONE,0,FALSE,&resolved,nullptr);if(FAILED(h))break;
            h=device->StretchRect(back,nullptr,resolved,nullptr,D3DTEXF_NONE);if(FAILED(h))break;source=resolved;
        }
        h=device->CreateOffscreenPlainSurface(desc.Width,desc.Height,desc.Format,D3DPOOL_SYSTEMMEM,&staging,nullptr);if(FAILED(h))break;
        h=device->GetRenderTargetData(source,staging);if(FAILED(h))break;
        h=staging->LockRect(&locked,nullptr,D3DLOCK_READONLY);if(FAILED(h))break;
        pixels.resize(size_t(desc.Width)*desc.Height*4);
        for(UINT y=0;y<desc.Height;y++)memcpy(pixels.data()+size_t(y)*desc.Width*4,static_cast<BYTE*>(locked.pBits)+size_t(y)*locked.Pitch,size_t(desc.Width)*4);
        staging->UnlockRect();
        bool bins[256]{};
        for(size_t i=0;i<pixels.size();i+=4){
            if(pixels[i]||pixels[i+1]||pixels[i+2])++request.nonBlackPixels;
            UINT luma=(29*pixels[i]+150*pixels[i+1]+77*pixels[i+2])>>8;
            if(!bins[luma]){bins[luma]=true;++request.luminanceBins;}
            request.luminanceMin=(std::min)(request.luminanceMin,luma);request.luminanceMax=(std::max)(request.luminanceMax,luma);pixels[i+3]=255;
        }
        h=SavePng(request.output,desc.Width,desc.Height,pixels);
        if(SUCCEEDED(h)){request.width=desc.Width;request.height=desc.Height;request.format=desc.Format;request.sequence=frameSequence;request.sourceKind=chain?2:1;}
    }while(false);
    if(staging)staging->Release();if(resolved)resolved->Release();if(back)back->Release();return h;
}
static void BeforePresent(IDirect3DDevice9* device,IDirect3DSwapChain9* chain,HWND window){
    ++frameSequence;if(!pendingCapture)return;
    auto state=pendingCapture;if(state->request->targetWindow&&state->request->targetWindow!=reinterpret_cast<uint64_t>(window))return;pendingCapture=nullptr;state->request->sourceWindow=reinterpret_cast<uint64_t>(window);
    state->request->result=CaptureSurface(device,chain,*state->request);SetEvent(state->done);
}
extern "C" __declspec(dllexport) DWORD WINAPI BootstrapCapture(CaptureRequest* request){
    if(!request||request->size!=sizeof(CaptureRequest)||request->version!=2||!request->output[0])return ERROR_INVALID_PARAMETER;
    HANDLE done=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(!done)return GetLastError();
    CaptureState state{request,done};bool busy=false;
    Invoke([&]{busy=pendingCapture!=nullptr;if(!busy)pendingCapture=&state;});
    if(busy){CloseHandle(done);request->result=HRESULT_FROM_WIN32(ERROR_BUSY);return ERROR_BUSY;}
    DWORD waited=WaitForSingleObject(done,30000);
    Invoke([&]{if(pendingCapture==&state)pendingCapture=nullptr;});
    if(waited!=WAIT_OBJECT_0&&request->result==E_PENDING)request->result=HRESULT_FROM_WIN32(WAIT_TIMEOUT);
    CloseHandle(done);return SUCCEEDED(request->result)?0:1;
}
using Create9Fn=IDirect3D9*(WINAPI*)(UINT);using Create9ExFn=HRESULT(WINAPI*)(UINT,IDirect3D9Ex**);
static Create9Fn realCreate9;static Create9ExFn realCreate9Ex;
static IDirect3D9* WINAPI Create9(UINT version){IDirect3D9* api=nullptr;Invoke([&]{api=realCreate9(version);});Log(L"redirected Direct3DCreate9",api?S_OK:E_FAIL);if(api)WrapFactory(api,false);return api;}
static HRESULT WINAPI Create9Ex(UINT version,IDirect3D9Ex** api){HRESULT h;Invoke([&]{h=realCreate9Ex(version,api);});Log(L"redirected Direct3DCreate9Ex",h);if(SUCCEEDED(h)&&*api)WrapFactory(*api,true);return h;}
DWORD StartHiddenGraphics(const wchar_t* log){
    graphicsLog=log;workEvent=CreateEventW(nullptr,FALSE,FALSE,nullptr);readyEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    HANDLE thread=CreateThread(nullptr,0,RenderThread,nullptr,0,nullptr);if(!thread||WaitForSingleObject(readyEvent,15000)!=WAIT_OBJECT_0||!renderWindow)return 1;CloseHandle(thread);
    HMODULE d3d=LoadLibraryW(L"d3d9.dll");if(!d3d)return 2;auto create=GetProcAddress(d3d,"Direct3DCreate9");auto createEx=GetProcAddress(d3d,"Direct3DCreate9Ex");
    if(MH_Initialize()!=MH_OK)return 3;
    if(MH_CreateHook(reinterpret_cast<void*>(create),reinterpret_cast<void*>(Create9),reinterpret_cast<void**>(&realCreate9))!=MH_OK)return 4;
    if(createEx&&MH_CreateHook(reinterpret_cast<void*>(createEx),reinterpret_cast<void*>(Create9Ex),reinterpret_cast<void**>(&realCreate9Ex))!=MH_OK)return 5;
    if(MH_EnableHook(MH_ALL_HOOKS)!=MH_OK)return 6;Log(L"hidden graphics hooks installed");return 0;
}
