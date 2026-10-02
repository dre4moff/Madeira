// Synthetic host GPU test, no Wine, Steam, game or physical iPhone.
// Loads the same precompiled macOS no-output fragment embedded by build-pe.sh.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <initializer_list>

int main(int argc, const char **argv) {
    @autoreleasepool {
        assert(argc == 2);
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        assert(device && [device supportsFamily:MTLGPUFamilyApple7]);
        NSError *error = nil;
        id<MTLLibrary> fallback = [device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
        assert(fallback && !error);
        id<MTLFunction> fragment = [fallback newFunctionWithName:@"madeira_mesh_null_fragment"];
        assert(fragment && fragment.functionType == MTLFunctionTypeFragment);
        NSString *fixture = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct V { float4 position [[position]]; };\nstruct P { uint unused; };\n"
            "[[mesh,max_total_threads_per_threadgroup(1)]] void mesh_main(mesh<V,P,3,1,topology::triangle> out) {\n"
            "out.set_vertex(0,V{float4(-1,-1,0.25,1)});out.set_vertex(1,V{float4(3,-1,0.25,1)});"
            "out.set_vertex(2,V{float4(-1,3,0.25,1)});out.set_primitive(0,P{0});"
            "out.set_index(0,0);out.set_index(1,1);out.set_index(2,2);out.set_primitive_count(1);}\n";
        id<MTLLibrary> lib = [device newLibraryWithSource:fixture options:nil error:&error];
        if (!lib) fprintf(stderr, "%s\n", error.localizedDescription.UTF8String);
        assert(lib);
        id<MTLFunction> mesh = [lib newFunctionWithName:@"mesh_main"];
        assert(mesh);
        for (NSUInteger samples : {1u, 4u}) {
            for (bool withColor : {false, true}) {
                MTLMeshRenderPipelineDescriptor *p = [MTLMeshRenderPipelineDescriptor new];
                p.meshFunction = mesh;
                p.fragmentFunction = fragment;
                p.rasterizationEnabled = YES;
                p.alphaToCoverageEnabled = NO;
                p.rasterSampleCount = samples;
                p.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
                if (withColor) {
                    p.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
                    p.colorAttachments[0].writeMask = MTLColorWriteMaskNone;
                }
                error = nil;
                id<MTLRenderPipelineState> pipeline = [device newRenderPipelineStateWithMeshDescriptor:p
                    options:MTLPipelineOptionNone reflection:nil error:&error];
                if (!pipeline) fprintf(stderr, "%s\n", error.localizedDescription.UTF8String);
                assert(pipeline);
                if (samples != 1) continue; // MSAA descriptor creation; read back single-sample depth below.
                MTLTextureDescriptor *t = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:4 height:4 mipmapped:NO];
                t.usage = MTLTextureUsageRenderTarget;
                t.storageMode = MTLStorageModePrivate;
                id<MTLTexture> depth = [device newTextureWithDescriptor:t];
                id<MTLTexture> color = nil;
                if (withColor) {
                    t.pixelFormat = MTLPixelFormatRGBA8Unorm;
                    color = [device newTextureWithDescriptor:t];
                }
                MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
                pass.depthAttachment.texture = depth;
                pass.depthAttachment.loadAction = MTLLoadActionClear;
                pass.depthAttachment.storeAction = MTLStoreActionStore;
                pass.depthAttachment.clearDepth = 1;
                if (withColor) {
                    pass.colorAttachments[0].texture = color;
                    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
                    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
                    pass.colorAttachments[0].clearColor = MTLClearColorMake(1, 0, 0, 1);
                }
                MTLDepthStencilDescriptor *ds = [MTLDepthStencilDescriptor new];
                ds.depthCompareFunction = MTLCompareFunctionAlways;
                ds.depthWriteEnabled = YES;
                id<MTLCommandQueue> queue = [device newCommandQueue];
                id<MTLCommandBuffer> cb = [queue commandBuffer];
                id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass];
                [enc setRenderPipelineState:pipeline];
                [enc setDepthStencilState:[device newDepthStencilStateWithDescriptor:ds]];
                [enc drawMeshThreadgroups:MTLSizeMake(1,1,1) threadsPerObjectThreadgroup:MTLSizeMake(1,1,1) threadsPerMeshThreadgroup:MTLSizeMake(1,1,1)];
                [enc endEncoding];
                id<MTLBuffer> bytes = [device newBufferWithLength:2048 options:MTLResourceStorageModeShared];
                id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
                [blit copyFromTexture:depth sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                    sourceSize:MTLSizeMake(4,4,1) toBuffer:bytes destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024];
                if (withColor) {
                    [blit copyFromTexture:color sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                        sourceSize:MTLSizeMake(4,4,1) toBuffer:bytes destinationOffset:1024 destinationBytesPerRow:256 destinationBytesPerImage:1024];
                }
                [blit endEncoding];
                [cb commit]; [cb waitUntilCompleted];
                if (cb.error) fprintf(stderr, "%s\n", cb.error.localizedDescription.UTF8String);
                assert(cb.status == MTLCommandBufferStatusCompleted);
                for (unsigned y=0;y<4;y++) for (unsigned x=0;x<4;x++) {
                    float value = *(float *)((char *)bytes.contents+y*256+x*4);
                    assert(std::fabs(value-0.25f) < 0.0001f);
                    if (withColor) {
                        unsigned char *rgba=(unsigned char *)bytes.contents+1024+y*256+x*4;
                        assert(rgba[0]==255 && rgba[1]==0 && rgba[2]==0 && rgba[3]==255);
                    }
                }
            }
        }
        puts("PASS: real host Metal mesh pipeline; embedded no-output fragment, 1x/4x MSAA creation, rasterized depth=0.25 and color clear unchanged");
    }
}
