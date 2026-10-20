// Tap only this owned editor process's render buffers, before silencing its
// speaker output. Windows SDK COM interfaces avoid game-internal ABI offsets.
#include "audio_protocol.h"
#include "graphics_bridge.h"
#include "../vendor/minhook/include/MinHook.h"
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <ksmedia.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <unordered_map>
#include <vector>
#pragma comment(lib,"ole32.lib")
#pragma comment(lib,"uuid.lib")
static SRWLOCK lock=SRWLOCK_INIT;
static AudioRequest state;static HANDLE wave=INVALID_HANDLE_VALUE;static bool recording=false;static uint32_t captureError;
struct Format{unsigned rate=0,channels=0,bits=0,align=0;bool floating=false,supported=false;};
using Init=HRESULT(STDMETHODCALLTYPE*)(IAudioClient*,AUDCLNT_SHAREMODE,DWORD,REFERENCE_TIME,REFERENCE_TIME,const WAVEFORMATEX*,LPCGUID);
using Service=HRESULT(STDMETHODCALLTYPE*)(IAudioClient*,REFIID,void**);
using Get=HRESULT(STDMETHODCALLTYPE*)(IAudioRenderClient*,UINT32,BYTE**);
using Drop=ULONG(STDMETHODCALLTYPE*)(IAudioRenderClient*);
using Release=HRESULT(STDMETHODCALLTYPE*)(IAudioRenderClient*,UINT32,DWORD);
static Init originalInit;static Service originalService;
struct Stream{Format format;Get get;Release release;Drop drop;IAudioClient* client;BYTE* buffer=nullptr;};
static std::unordered_map<void*,Format> clients;static std::unordered_map<void*,Stream> streams;
static std::vector<void**> tables;
static void Header(){
 unsigned char h[44]{};memcpy(h,"RIFF",4);uint32_t bytes=static_cast<uint32_t>(state.frames*state.channels*4),size=bytes+36;
 memcpy(h+4,&size,4);memcpy(h+8,"WAVEfmt ",8);uint32_t fmtSize=16;memcpy(h+16,&fmtSize,4);
 uint16_t tag=3,channels=static_cast<uint16_t>(state.channels),align=channels*4,bits=32;
 memcpy(h+20,&tag,2);memcpy(h+22,&channels,2);memcpy(h+24,&state.rate,4);uint32_t byteRate=state.rate*align;
 memcpy(h+28,&byteRate,4);memcpy(h+32,&align,2);memcpy(h+34,&bits,2);memcpy(h+36,"data",4);memcpy(h+40,&bytes,4);
 SetFilePointer(wave,0,nullptr,FILE_BEGIN);DWORD written=0;if(!WriteFile(wave,h,44,&written,nullptr)||written!=44)captureError=21;
}
static void IdleTo(uint64_t frames){
 if(frames<=state.frames)return;
 static const float zeros[16384]{};
 while(state.frames<frames){DWORD count=static_cast<DWORD>((std::min)(frames-state.frames,static_cast<uint64_t>(16384/state.channels)));DWORD bytes=count*state.channels*4,written=0;
  if(!WriteFile(wave,zeros,bytes,&written,nullptr)||written!=bytes){captureError=21;return;}state.frames+=count;state.idleFrames+=count;}
}
static HRESULT STDMETHODCALLTYPE Buffer(IAudioRenderClient* self,UINT32 frames,BYTE** data){
 AcquireSRWLockExclusive(&lock);++state.bufferCalls;auto original=streams.at(self).get;ReleaseSRWLockExclusive(&lock);
 auto hr=original(self,frames,data);if(SUCCEEDED(hr)){AcquireSRWLockExclusive(&lock);streams.at(self).buffer=*data;ReleaseSRWLockExclusive(&lock);}return hr;
}
static HRESULT STDMETHODCALLTYPE Submit(IAudioRenderClient* self,UINT32 frames,DWORD flags){
 AcquireSRWLockExclusive(&lock);++state.submitCalls;auto& s=streams.at(self);auto original=s.release;auto f=s.format;
 if(recording&&frames){
  if(f.rate!=state.rate||f.channels!=state.channels)captureError=20;
  else if(!s.buffer&&!(flags&AUDCLNT_BUFFERFLAGS_SILENT))captureError=28;
  else {
   LARGE_INTEGER q;QueryPerformanceCounter(&q);UINT32 padding=0;if(FAILED(s.client->GetCurrentPadding(&padding)))captureError=24;
   int64_t presentation=q.QuadPart+static_cast<int64_t>(static_cast<double>(padding)*state.frequency/f.rate);
   auto offset=static_cast<uint64_t>((std::max)(0.0,static_cast<double>(presentation-state.firstQpc)*state.rate/state.frequency));
   // Idle audio clients submit no buffers. Preserve these real timeline gaps
   // as silence instead of concatenating later sounds at the wrong timestamp.
   if(offset>state.frames+state.rate/100)IdleTo(offset);state.lastQpc=q.QuadPart;
   std::vector<float> samples(static_cast<size_t>(frames)*f.channels);
   for(size_t i=0;i<samples.size();i++){
    double v=0;auto p=s.buffer?s.buffer+i*(f.bits/8):nullptr;
    if(!(flags&AUDCLNT_BUFFERFLAGS_SILENT)){
     if(f.floating&&f.bits==32)v=*reinterpret_cast<float*>(p);
     else if(!f.floating&&f.bits==16)v=*reinterpret_cast<int16_t*>(p)/32768.0;
     else if(!f.floating&&f.bits==32)v=*reinterpret_cast<int32_t*>(p)/2147483648.0;
     else captureError=23;
    }
    if(!std::isfinite(v)){captureError=22;v=0;}samples[i]=static_cast<float>(v);state.nonzero+=v!=0;state.peak=(std::max)(state.peak,fabs(v));state.sumSquares+=v*v;
   }
   DWORD bytes=static_cast<DWORD>(samples.size()*4),written=0;
   if(!WriteFile(wave,samples.data(),bytes,&written,nullptr)||written!=bytes)captureError=21;else {state.frames+=frames;state.renderedFrames+=frames;}
  }
 }
 // The editor cannot be heard through the user's speakers. No system loopback,
 // microphone, other process or foreground input is involved.
 if(s.buffer)memset(s.buffer,0,static_cast<size_t>(frames)*f.align);s.buffer=nullptr;
 ReleaseSRWLockExclusive(&lock);return original(self,frames,flags|AUDCLNT_BUFFERFLAGS_SILENT);
}
static HRESULT STDMETHODCALLTYPE Initialize(IAudioClient* self,AUDCLNT_SHAREMODE mode,DWORD flags,REFERENCE_TIME duration,REFERENCE_TIME period,const WAVEFORMATEX* format,LPCGUID session){
 auto hr=originalInit(self,mode,flags,duration,period,format,session);
 if(SUCCEEDED(hr)){
  Format f{format->nSamplesPerSec,format->nChannels,format->wBitsPerSample,format->nBlockAlign,format->wFormatTag==WAVE_FORMAT_IEEE_FLOAT};
  f.supported=format->wFormatTag==WAVE_FORMAT_PCM||format->wFormatTag==WAVE_FORMAT_IEEE_FLOAT;
  if(format->wFormatTag==WAVE_FORMAT_EXTENSIBLE&&format->cbSize>=22){auto subtype=reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(format)->SubFormat;f.floating=subtype==KSDATAFORMAT_SUBTYPE_IEEE_FLOAT;f.supported=f.floating||subtype==KSDATAFORMAT_SUBTYPE_PCM;}
  AcquireSRWLockExclusive(&lock);clients[self]=f;ReleaseSRWLockExclusive(&lock);
 }return hr;
}
static ULONG STDMETHODCALLTYPE DropRender(IAudioRenderClient* self){
 AcquireSRWLockExclusive(&lock);auto original=streams.at(self).drop;ReleaseSRWLockExclusive(&lock);
 auto count=original(self);if(!count){AcquireSRWLockExclusive(&lock);streams.erase(self);if(streams.empty()){state.ready=0;if(recording)captureError=27;}ReleaseSRWLockExclusive(&lock);}return count;
}
static HRESULT STDMETHODCALLTYPE GetService(IAudioClient* self,REFIID iid,void** object){
 auto hr=originalService(self,iid,object);
 if(SUCCEEDED(hr)&&iid==__uuidof(IAudioRenderClient)){
  AcquireSRWLockExclusive(&lock);
  if(!streams.count(*object)&&clients.count(self)){
   auto f=clients.at(self);auto table=*reinterpret_cast<void***>(*object);auto clone=new void*[5];memcpy(clone,table,5*sizeof(void*));
   streams[*object]=Stream{f,reinterpret_cast<Get>(table[3]),reinterpret_cast<Release>(table[4]),reinterpret_cast<Drop>(table[2]),self};clone[2]=reinterpret_cast<void*>(DropRender);clone[3]=reinterpret_cast<void*>(Buffer);clone[4]=reinterpret_cast<void*>(Submit);
   *reinterpret_cast<void***>(*object)=clone;tables.push_back(clone);
   state.ready=f.supported&&f.rate>=8000&&f.rate<=192000&&f.channels>=1&&f.channels<=8&&f.align==f.channels*f.bits/8&&((f.floating&&f.bits==32)||(!f.floating&&(f.bits==16||f.bits==32)));state.error=state.ready?0:26;state.rate=f.rate;state.channels=f.channels;state.version=1;
  }ReleaseSRWLockExclusive(&lock);
 }return hr;
}
extern "C" __declspec(dllexport) DWORD WINAPI BootstrapAudioControl(AudioRequest* request){
 if(!request)return 1;AcquireSRWLockExclusive(&lock);auto op=request->operation;auto play=request->playQpc;
 if(op==1){
  if(recording||!state.ready||streams.size()!=1){request->error=30;ReleaseSRWLockExclusive(&lock);return 30;}
  wave=CreateFileW(request->path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
  if(wave==INVALID_HANDLE_VALUE){request->error=31;ReleaseSRWLockExclusive(&lock);return 31;}
  state.error=0;state.frames=state.nonzero=state.renderedFrames=state.idleFrames=0;LARGE_INTEGER begin;QueryPerformanceCounter(&begin);state.firstQpc=begin.QuadPart;state.lastQpc=0;state.peak=state.sumSquares=0;captureError=0;
  LARGE_INTEGER freq;QueryPerformanceFrequency(&freq);state.frequency=freq.QuadPart;state.playQpc=play;Header();recording=true;SetAudioRenderFast(true);
 }else if(op==2){SetAudioRenderFast(false);recording=false;if(wave!=INVALID_HANDLE_VALUE){LARGE_INTEGER end;QueryPerformanceCounter(&end);IdleTo(static_cast<uint64_t>(static_cast<double>(end.QuadPart-state.firstQpc)*state.rate/state.frequency));Header();CloseHandle(wave);wave=INVALID_HANDLE_VALUE;}state.error=captureError;}
 *request=state;ReleaseSRWLockExclusive(&lock);return request->error;
}
DWORD StartHiddenAudio(){
 auto hr=CoInitializeEx(nullptr,COINIT_MULTITHREADED);if(FAILED(hr)){state.error=1;return 1;}
 IMMDeviceEnumerator* enumerator=nullptr;IMMDevice* endpoint=nullptr;IAudioClient* client=nullptr;DWORD error=0;
 if(FAILED(CoCreateInstance(__uuidof(MMDeviceEnumerator),nullptr,CLSCTX_INPROC_SERVER,__uuidof(IMMDeviceEnumerator),reinterpret_cast<void**>(&enumerator)))||FAILED(enumerator->GetDefaultAudioEndpoint(eRender,eConsole,&endpoint))||FAILED(endpoint->Activate(__uuidof(IAudioClient),CLSCTX_INPROC_SERVER,nullptr,reinterpret_cast<void**>(&client))))error=2;
 if(!error){auto table=*reinterpret_cast<void***>(client);HMODULE pinned=nullptr;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(table[3]),&pinned))error=4;
 if(!error&&(MH_CreateHook(table[3],reinterpret_cast<void*>(Initialize),reinterpret_cast<void**>(&originalInit))!=MH_OK||MH_CreateHook(table[14],reinterpret_cast<void*>(GetService),reinterpret_cast<void**>(&originalService))!=MH_OK||MH_EnableHook(table[3])!=MH_OK||MH_EnableHook(table[14])!=MH_OK))error=3;}
 if(client)client->Release();if(endpoint)endpoint->Release();if(enumerator)enumerator->Release();CoUninitialize();state.error=error;return error;
}
