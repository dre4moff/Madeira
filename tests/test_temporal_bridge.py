"""Production iOS temporal descriptor branch, fake MetalFX descriptor/device."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
s=(root/'dxmt/src/winemetal/unix/winemetal_unix.c').read_text()
start=s.index('static NTSTATUS\n_MTLDevice_newTemporalScaler(')
block=s[start:s.index('static NTSTATUS\n_MTLDevice_newSpatialScaler(',start)]
# iOS preprocessing removes the macOS-only temporary signal-handler workaround.
assert '#if !TARGET_OS_IOS\n  struct sigaction' in block
assert '#if !TARGET_OS_IOS\n  if (@available(macOS 16' in block
h=(root/'dxmt/src/winemetal/winemetal.h').read_text()
start=h.index('struct WMTFXTemporalScalerInfo {')
info=h[start:h.index('};',start)+2]
properties={
 'MTLPixelFormat':['colorTextureFormat','outputTextureFormat','depthTextureFormat','motionTextureFormat'],
 'NSUInteger':['inputWidth','inputHeight','outputWidth','outputHeight'],
 'float':['inputContentMinScale','inputContentMaxScale'],
 'BOOL':['inputContentPropertiesEnabled','requiresSynchronousInitialization','autoExposureEnabled']}
props='\n'.join('@property(nonatomic) '+t+' '+n+';' for t,names in properties.items() for n in names)
src=r'''
#import <Foundation/Foundation.h>
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#undef TARGET_OS_IOS
#define TARGET_OS_IOS 1
typedef int NTSTATUS;
#define STATUS_SUCCESS 0
typedef uintptr_t obj_handle_t;
typedef enum WMTPixelFormat { FormatInvalid=0,FormatColor=1,FormatOutput=2,FormatDepth=3,FormatMotion=4 } WMTPixelFormat;
typedef unsigned MTLPixelFormat;
static unsigned conversions,creations;
static bool supported=true;
static MTLPixelFormat to_metal_pixel_format(WMTPixelFormat f){conversions++;return f;}
@protocol MTLDevice @end
@interface FakeDevice:NSObject<MTLDevice> @end
@implementation FakeDevice @end
'''+info+r'''
struct unixcall_mtldevice_newfxtemporalscaler {
 obj_handle_t device;struct {const struct WMTFXTemporalScalerInfo *ptr;} info;obj_handle_t ret;
};
@interface MTLFXTemporalScalerDescriptor:NSObject
'''+props+r'''
+(BOOL)supportsDevice:(id<MTLDevice>)device;
+(float)supportedInputContentMinScaleForDevice:(id<MTLDevice>)device;
+(float)supportedInputContentMaxScaleForDevice:(id<MTLDevice>)device;
-(id)newTemporalScalerWithDevice:(id<MTLDevice>)device;
@end
@implementation MTLFXTemporalScalerDescriptor
+(BOOL)supportsDevice:(id<MTLDevice>)device{return supported && device!=nil;}
+(float)supportedInputContentMinScaleForDevice:(id<MTLDevice>)device{return 1;}
+(float)supportedInputContentMaxScaleForDevice:(id<MTLDevice>)device{return 2;}
-(id)newTemporalScalerWithDevice:(id<MTLDevice>)device{
 assert(device);creations++;
 assert(self.inputWidth==704 && self.inputHeight==324);
 assert(self.outputWidth==1408 && self.outputHeight==648);
 assert(self.colorTextureFormat==1 && self.outputTextureFormat==2 && self.depthTextureFormat==3 && self.motionTextureFormat==4);
 assert(self.inputContentMinScale==1 && self.inputContentMaxScale==2);
 assert(self.inputContentPropertiesEnabled && self.requiresSynchronousInitialization && self.autoExposureEnabled);
 return [NSObject new];
}
@end
'''+block+r'''
int main(){@autoreleasepool {
 FakeDevice *device=[FakeDevice new];
 struct WMTFXTemporalScalerInfo info={0};
 info.input_width=704;info.input_height=324;info.output_width=1408;info.output_height=648;
 info.color_format=1;info.output_format=2;info.depth_format=3;info.motion_format=4;
 info.input_content_min_scale=1;info.input_content_max_scale=3;
 info.input_content_properties_enabled=true;info.requires_synchronous_initialization=true;info.auto_exposure=true;
 struct unixcall_mtldevice_newfxtemporalscaler p={.device=(obj_handle_t)device,.info={&info},.ret=999};
 supported=false;assert(_MTLDevice_newTemporalScaler(&p)==0 && p.ret==0 && creations==0 && conversions==0);
 supported=true;assert(_MTLDevice_newTemporalScaler(&p)==0 && p.ret!=0 && creations==1 && conversions==4);
 [(id)p.ret release];[device release];
 puts("PASS: actual temporal descriptor respects mobile scale range, keeps internal/output sizes, synchronous initialization and unsupported-device rejection; fake Metal only");
}}
'''
with tempfile.TemporaryDirectory(prefix='madeira-temporal-') as tmp:
    p=Path(tmp);(p/'test.m').write_text(src)
    subprocess.run(['clang','-fsanitize=address,undefined','-framework','Foundation',str(p/'test.m'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
