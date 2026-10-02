"""Production NGX parameters/entrypoints with fake COM/GPU boundaries; no game."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
ngx = (root / 'dxmt/src/nvngx/nvngx.cpp').read_text()
def section(start, end):
    a = ngx.index(start)
    return ngx[a:ngx.index(end, a)]
create = section('NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_CreateFeature(', 'NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_Shutdown()')
extra = section('NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_GetScratchBufferSize(', 'inline static NVNGX_RESULT\nNVNGX_DLSS_GetOptimalSettingsCallback')
optimal = section('inline static NVNGX_RESULT\nNVNGX_DLSS_GetOptimalSettingsCallback', 'NVNGX_API NVNGX_RESULT\nNVSDK_NGX_D3D11_GetParameters(')
desc = (root / 'dxmt/src/d3d11/d3d11_interfaces.hpp').read_text()
desc = desc[desc.index('struct MTL_TEMPORAL_UPSCALE_D3D11_DESC'):desc.index('DEFINE_COM_INTERFACE')]
src = r'''
#include <cassert>
#include <cstring>
#include <cmath>
#include <memory>
#include <cstdio>
#include "nvngx.hpp"
#include "nvngx_parameter.hpp"
#include "nvngx_feature.hpp"
using UINT=unsigned;using BOOL=int;using FLOAT=float;
struct ID3D11Resource {};
using ID3D11Texture2D=ID3D11Resource;
'''+desc+r'''
struct IMTLD3D11ContextExt {
 unsigned refs=0,calls=0;MTL_TEMPORAL_UPSCALE_D3D11_DESC last{};
 void Release(){assert(refs);--refs;}
 void TemporalUpscale(const MTL_TEMPORAL_UPSCALE_D3D11_DESC *d){last=*d;++calls;}
};
struct IMTLD3D11ContextExt1:IMTLD3D11ContextExt {
 bool supported=true;
 int CheckFeatureSupport(int,BOOL *v,unsigned){*v=supported;return 0;}
};
struct IMTLD3D11ContextExt2:IMTLD3D11ContextExt1 {
 int result=0;
 int TryTemporalUpscale(const MTL_TEMPORAL_UPSCALE_D3D11_DESC *d){if(result<0)return result;TemporalUpscale(d);return 0;}
};
struct ID3D11DeviceContext {
 IMTLD3D11ContextExt2 ext;
 template<class T> int QueryInterface(T **out){*out=&ext;++ext.refs;return 0;}
};
#define IID_PPV_ARGS(x) (x)
#define E_INVALIDARG (-1)
#define FAILED(x) ((x)<0)
#define MTL_FEATURE_METALFX_TEMPORAL_SCALER 0
#define ERR(...) ((void)0)
template<class T> struct Com {
 T *ptr=nullptr;Com(std::nullptr_t){}
 ~Com(){if(ptr)ptr->Release();}
 T **operator&(){return &ptr;}T *operator->(){return ptr;}
};
namespace dxmt {
'''+create+extra+optimal+r'''
}
using namespace dxmt;
int main(){
 NVNGXParameter *p=nullptr;
 assert(NVSDK_NGX_D3D11_GetCapabilityParameters(&p)==NVNGX_RESULT_OK);
 unsigned available=0;p->Get("SuperSampling.Available",&available);assert(available==1);
 p->Set(NVNGX_Parameter_Width,1408u);p->Set(NVNGX_Parameter_Height,648u);
 p->Set(NVNGX_Parameter_PerfQualityValue,int(NVNGX_PERFQUALITY_MAXPERF));
 assert(NVNGX_DLSS_GetOptimalSettingsCallback(p)==NVNGX_RESULT_OK);
 unsigned w=0,h=0;p->Get(NVNGX_Parameter_OutWidth,&w);p->Get(NVNGX_Parameter_OutHeight,&h);
 // NGX chooses reduced INTERNAL targets, independently of the desktop.
 assert(w==704 && h==324);
 p->Set(NVNGX_Parameter_Width,w);p->Set(NVNGX_Parameter_Height,h);
 p->Set(NVNGX_Parameter_OutWidth,1408u);p->Set(NVNGX_Parameter_OutHeight,648u);
 p->Set(NVNGX_Parameter_DLSS_Feature_Create_Flags,int(NVNGX_DLSS_FLAG_DEPTH_INVERTED|NVNGX_DLSS_FLAG_MV_LOWRES|NVNGX_DLSS_FLAG_AUTO_EXPOSURE));
 ID3D11DeviceContext ctx;unsigned *handle=nullptr;
 ctx.ext.supported=false;
 assert(NVSDK_NGX_D3D11_CreateFeature(&ctx,1,p,&handle)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED && ctx.ext.refs==0);
 ctx.ext.supported=true;
 assert(NVSDK_NGX_D3D11_CreateFeature(&ctx,1,p,&handle)==NVNGX_RESULT_OK && ctx.ext.refs==0);
 p->Set(NVNGX_Parameter_Width,400u);unsigned *invalid=nullptr;
 assert(NVSDK_NGX_D3D11_CreateFeature(&ctx,1,p,&invalid)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED && !invalid);
 p->Set(NVNGX_Parameter_Width,w);
 ID3D11Resource color,depth,motion,output;
 p->Set(NVNGX_Parameter_Color,&color);p->Set(NVNGX_Parameter_Depth,&depth);
 p->Set(NVNGX_Parameter_MotionVectors,&motion);p->Set(NVNGX_Parameter_Output,&output);
 p->Set(NVNGX_Parameter_DLSS_Render_Subrect_Dimensions_Width,w);
 p->Set(NVNGX_Parameter_DLSS_Render_Subrect_Dimensions_Height,h);
 p->Set(NVNGX_Parameter_Jitter_Offset_X,0.25f);p->Set(NVNGX_Parameter_Jitter_Offset_Y,-0.5f);
 p->Set(NVNGX_Parameter_MV_Scale_X,704.f);p->Set(NVNGX_Parameter_MV_Scale_Y,324.f);
 p->Set(NVNGX_Parameter_Reset,1);p->Set(NVNGX_Parameter_DLSS_Pre_Exposure,1.f);
 assert(NVSDK_NGX_D3D11_EvaluateFeature(&ctx,handle,p,nullptr)==NVNGX_RESULT_OK);
 const auto &d=ctx.ext.last;
 assert(ctx.ext.calls==1 && ctx.ext.refs==0);
 assert(d.Color==&color && d.Depth==&depth && d.MotionVector==&motion && d.Output==&output);
 assert(d.InputContentWidth==704 && d.InputContentHeight==324 && d.DepthReversed && d.AutoExposure && !d.MotionVectorInDisplayRes);
 assert(d.JitterOffsetX==.25f && d.JitterOffsetY==-.5f && d.MotionVectorScaleX==704.f && d.InReset && d.PreExposure==1.f);
 p->Set(NVNGX_Parameter_DLSS_Render_Subrect_Dimensions_Width,500u);
 assert(NVSDK_NGX_D3D11_EvaluateFeature(&ctx,handle,p,nullptr)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED);
 p->Set(NVNGX_Parameter_DLSS_Render_Subrect_Dimensions_Width,w);
 p->Set(NVNGX_Parameter_Color,(ID3D11Resource *)nullptr);
 assert(NVSDK_NGX_D3D11_EvaluateFeature(&ctx,handle,p,nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 assert(ctx.ext.refs==0 && ctx.ext.calls==1);
 size_t scratch=99;
 assert(NVSDK_NGX_D3D11_GetScratchBufferSize(1,p,&scratch)==NVNGX_RESULT_OK && scratch==0);
 assert(NVSDK_NGX_D3D11_GetScratchBufferSize(1,p,nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 assert(NVSDK_NGX_D3D11_GetScratchBufferSize(99,p,&scratch)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED && scratch==0);
 p->Set(NVNGX_Parameter_Color,&color);ctx.ext.result=-2;
 assert(NVSDK_NGX_D3D11_EvaluateFeature(&ctx,handle,p,nullptr)==NVNGX_RESULT_FEATURE_NOT_SUPPORTED);
 assert(ctx.ext.calls==1 && ctx.ext.refs==0);
 ctx.ext.result=0;p->Set(NVNGX_Parameter_DLSS_Pre_Exposure,0.f);
 assert(NVSDK_NGX_D3D11_EvaluateFeature(&ctx,handle,p,nullptr)==NVNGX_RESULT_OK && ctx.ext.last.PreExposure==1);
 assert(NVSDK_NGX_D3D11_ReleaseFeature(nullptr)==NVNGX_RESULT_INVALID_PARAMETER);
 NVSDK_NGX_D3D11_ReleaseFeature(handle);delete static_cast<ParametersImpl *>(p);
 puts("PASS: production NGX capabilities, internal render sizes, hardware rejection and depth/motion/jitter/reset dispatch; fake COM, no GPU");
}
'''
policy = r'''
#include <assert.h>
#include <string.h>
#include "graphics_profile.h"
int main(){
 const char *base="other,nvapi64=n;msvcp140=n,b;nvngx=n";
 setenv("WINEDLLOVERRIDES",base,1);setenv("DXMT_CONFIG","untouched",1);
 madeira_apply_dlss_profile(1);
 assert(!strcmp(getenv("DXMT_ENABLE_NVEXT"),"1"));
 assert(strstr(getenv("WINEDLLOVERRIDES"),base)==getenv("WINEDLLOVERRIDES"));
 assert(strstr(getenv("WINEDLLOVERRIDES"),";nvapi64,nvngx=b"));
 assert(!strcmp(getenv("DXMT_METALFX_SPATIAL_SWAPCHAIN"),"0"));
 madeira_apply_dlss_profile(0);
 assert(!strcmp(getenv("WINEDLLOVERRIDES"),base));assert(!strcmp(getenv("DXMT_ENABLE_NVEXT"),"0"));
 assert(!strcmp(getenv("DXMT_CONFIG"),"untouched"));
 madeira_apply_dlss_profile(1);setenv("WINEDLLOVERRIDES","new-user-choice=n",1);
 madeira_apply_dlss_profile(0);assert(!strcmp(getenv("WINEDLLOVERRIDES"),"new-user-choice=n"));
 puts("PASS: per-game DLSS opt-in, unrelated overrides preserved, off restores baseline, no double upscaling");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-dlss-') as tmp:
    p = Path(tmp)
    for name, code, compiler, inc, extra in [('ngx.cpp', src, 'clang++', 'dxmt/src/nvngx', ['-std=c++20']), ('policy.c', policy, 'clang', 'build', [])]:
        (p / name).write_text(code)
        subprocess.run([compiler,*extra,'-fsanitize=address,undefined','-I',str(root/inc),str(p/name),'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test')],check=True)
view=(root/'app/Madeira/Library.swift').read_text()
assert 'bits != 32 && madeira_supports_temporal_upscaling()' in view
assert 'Toggle("DLSS via MetalFX (experimental)"' in view
bridge=(root/'app/Madeira/WineProcessBridge.m').read_text()
assert bridge.index('const int metalFXDLSS') < bridge.index('madeira.cfg env:') < bridge.index('madeira_apply_dlss_profile(metalFXDLSS)')
print('PASS: shared direct/Steam bridge applies per-game DLSS after global config; 32-bit/remote/unsupported opt-out')
