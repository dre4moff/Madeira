"""NGX D3D12 entry points and the fixed-width DLL boundary, without Wine/GPU."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
ngx=(root/'dxmt/src/nvngx/nvngx.cpp').read_text()
def section(a,b):
 start=ngx.index(a);return ngx[start:ngx.index(b,start)]
extra=section('NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_GetScratchBufferSize(', 'inline static NVNGX_RESULT\nNVNGX_DLSS_GetOptimalSettingsCallback')
params=section('inline static NVNGX_RESULT\nNVNGX_DLSS_GetOptimalSettingsCallback','NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_GetFeatureRequirements(')
source=r'''
#include <cassert>
#include <cmath>
#include <cstring>
#include <memory>
#include <string>
#include <cstdio>
#include "nvngx.hpp"
#include "nvngx_parameter.hpp"
#include "nvngx_feature.hpp"
#include "madeira_dlss_abi.h"
struct ID3D12Device{};struct ID3D12GraphicsCommandList{};struct ID3D12Resource{};struct IDXGIAdapter{};
using HMODULE=void *;using FARPROC=void(*)();
static bool loaded=true,hardware=true;static int32_t failure;
static unsigned creates,records,releases;static madeira_dlss_desc last;
static int32_t supported(void *d){return d && hardware?0:int32_t(0x80004001);}
static int32_t create(void *l,uint32_t w,uint32_t h,uint32_t ow,uint32_t oh,uint32_t flags,uint64_t *out){
 assert(l && w==640 && h==360 && ow==1280 && oh==720 && flags==2);++creates;*out=44;return failure;
}
static int32_t record(void *l,uint64_t feature,const madeira_dlss_desc *d){assert(l && feature==44 && d->size==96);last=*d;++records;return failure;}
static void release(uint64_t feature){assert(feature==44);++releases;}
static HMODULE GetModuleHandleW(const wchar_t *name){assert(!wcscmp(name,L"d3d12.dll"));return loaded?(void *)1:nullptr;}
static FARPROC GetProcAddress(HMODULE module,const char *name){assert(module);
 if(!strcmp(name,"MadeiraD3D12TemporalSupported"))return reinterpret_cast<FARPROC>(supported);
 if(!strcmp(name,"MadeiraD3D12TemporalCreate"))return reinterpret_cast<FARPROC>(create);
 if(!strcmp(name,"MadeiraD3D12TemporalRecord"))return reinterpret_cast<FARPROC>(record);
 if(!strcmp(name,"MadeiraD3D12TemporalRelease"))return reinterpret_cast<FARPROC>(release);
 assert(false);return nullptr;
}
namespace dxmt {
struct Logger{template<class T>static void warn(T){}template<class T>static void info(T){}};
namespace str{template<class... T>std::string format(T...){return {};}}
'''+extra+params+r'''
NVNGX_RESULT NVSDK_NGX_D3D11_GetFeatureRequirements(IDXGIAdapter *,const NVNGX_FeatureDiscoveryInfo *info,NVNGX_FeatureRequirement *out){
 if(!info||!out)return NVNGX_RESULT_INVALID_PARAMETER;
 out->FeatureSupported=NVNGX_FEATURE_SUPPORT_RESULT_SUPPORTED;return NVNGX_RESULT_OK;
}
}
'''+f'#include "{root}/dxmt/src/nvngx/nvngx_d3d12.hpp"\n'+r'''
using namespace dxmt;
int main(){
 ID3D12Device device;ID3D12GraphicsCommandList list;NVNGXParameter *p=nullptr;
 loaded=false;assert(NVSDK_NGX_D3D12_Init(0,L"",&device,nullptr,0)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED);
 assert(NVSDK_NGX_D3D12_GetCapabilityParameters(&p)==NVNGX_RESULT_OK);unsigned avail=99;p->Get("SuperSampling.Available",&avail);assert(!avail);NVSDK_NGX_D3D12_DestroyParameters(p);
 loaded=true;hardware=false;assert(NVSDK_NGX_D3D12_Init_Ext(0,L"",&device,0,nullptr)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED);
 hardware=true;assert(NVSDK_NGX_D3D12_Init_ProjectID("p",0,"v",L"",&device,0,nullptr)==NVNGX_RESULT_OK);
 assert(NVSDK_NGX_D3D12_GetCapabilityParameters(&p)==NVNGX_RESULT_OK);p->Get("SuperSampling.Available",&avail);assert(avail==1);
 size_t scratch=99;assert(NVSDK_NGX_D3D12_GetScratchBufferSize(1,p,&scratch)==NVNGX_RESULT_OK && scratch==0);
 assert(NVSDK_NGX_D3D12_AllocateParameters(nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 p->Set(NVNGX_Parameter_Width,640u);p->Set(NVNGX_Parameter_Height,360u);p->Set(NVNGX_Parameter_OutWidth,1280u);p->Set(NVNGX_Parameter_OutHeight,720u);p->Set(NVNGX_Parameter_DLSS_Feature_Create_Flags,2);
 unsigned *handle=(unsigned *)1;failure=int32_t(0x80070057);
 assert(NVSDK_NGX_D3D12_CreateFeature(&list,1,p,&handle)==NVNGX_RESULT_INVALID_PARAMETER && !handle);
 failure=0;assert(NVSDK_NGX_D3D12_CreateFeature(&list,1,p,&handle)==NVNGX_RESULT_OK);
 ID3D12Resource color,output,depth,motion;
 p->Set(NVNGX_Parameter_Color,&color);p->Set(NVNGX_Parameter_Output,&output);p->Set(NVNGX_Parameter_Depth,&depth);p->Set(NVNGX_Parameter_MotionVectors,&motion);
 p->Set(NVNGX_Parameter_Jitter_Offset_X,.25f);p->Set(NVNGX_Parameter_MV_Scale_X,640.f);p->Set(NVNGX_Parameter_DLSS_Pre_Exposure,0.f);
 assert(NVSDK_NGX_D3D12_EvaluateFeature(&list,handle,p,nullptr)==NVNGX_RESULT_OK);
 assert(last.color==uint64_t(&color) && last.output==uint64_t(&output) && last.depth==uint64_t(&depth) && last.motion==uint64_t(&motion) && last.input_width==640 && last.output_width==1280 && last.pre_exposure==1 && last.jitter_x==.25f && last.motion_scale_x==640);
 failure=int32_t(0x80004001);assert(NVSDK_NGX_D3D12_EvaluateFeature(&list,handle,p,nullptr)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED);
 failure=int32_t(0x80070057);assert(NVSDK_NGX_D3D12_EvaluateFeature(&list,handle,p,nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 assert(NVSDK_NGX_D3D12_ReleaseFeature(handle)==NVNGX_RESULT_OK && releases==1);
 assert(NVSDK_NGX_D3D12_ReleaseFeature(nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 NVSDK_NGX_D3D12_DestroyParameters(p);NVSDK_NGX_D3D12_Shutdown();
 puts("PASS: production NGX D3D12 init/capabilities/scratch/create/evaluate/release, exact resource-pointer ABI and accurate unsupported/invalid errors");
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder);(p/'test.cpp').write_text(source)
 subprocess.run(['xcrun','clang++','-std=c++20','-fsanitize=address,undefined','-I'+str(root/'dxmt/include'),'-I'+str(root/'dxmt/src/nvngx'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
