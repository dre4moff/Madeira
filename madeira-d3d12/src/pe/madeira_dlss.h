/* SPDX-License-Identifier: GPL-3.0-or-later
 * NGX temporal reconstruction for the existing Madeira D3D12 backend.
 * Included after the device/list/resource vtables are declared. */
#include "dxmt_command.h" /* existing iOS Metal kernels, including motion downsampling */
#define MAD_DLSS_MAGIC 0x4d465831u
struct mad_dlss_feature {
    UINT magic, width, height, output_width, output_height, flags;
    struct mad_device *device;
    struct { struct WMTFXTemporalScalerInfo info; obj_handle_t scaler, motion; } cache[2];
    unsigned replacement;
    obj_handle_t motion_pipeline, last_scaler;
};

HRESULT MadeiraD3D12TemporalSupported(void *device) {
    struct mad_device *d = device;
    if (!d || d->vtbl != &g_device_vtbl || !d->mtl_device) return E_INVALIDARG;
    return MTLDevice_supportsFXTemporalScaler(d->mtl_device) ? S_OK : E_NOTIMPL;
}

HRESULT MadeiraD3D12TemporalCreate(void *list, UINT width, UINT height,
                                  UINT output_width, UINT output_height, UINT flags, UINT64 *out) {
    struct mad_list *l = list;
    struct mad_dlss_feature *f;
    if (!out) return E_INVALIDARG;
    *out = 0;
    if (!l || l->vtbl != &g_list_vtbl || l->closed ||
        (l->type != D3D12_COMMAND_LIST_TYPE_DIRECT && l->type != D3D12_COMMAND_LIST_TYPE_COMPUTE) ||
        !width || !height || width > output_width || height > output_height ||
        output_width > 16384 || output_height > 16384) return E_INVALIDARG;
    if (width * 2 < output_width || height * 2 < output_height) return E_NOTIMPL;
    if (FAILED(MadeiraD3D12TemporalSupported(l->device))) return E_NOTIMPL;
    /* iOS 26 MetalFX consumes unjittered, render-resolution motion. Never
     * downsample display-resolution vectors first; reject jittered vectors. */
    if (flags & 4) {
        d3d12_log("[dlss-metalfx] D3D12: unsupported motion-vector mode flags=0x%x (needs unjittered vectors)\n", flags);
        return E_NOTIMPL;
    }
    f = calloc(1, sizeof *f);
    if (!f) return E_OUTOFMEMORY;
    f->magic = MAD_DLSS_MAGIC; f->device = l->device;
    f->width = width; f->height = height;
    f->output_width = output_width; f->output_height = output_height; f->flags = flags;
    ID3D12Device_AddRef((ID3D12Device *)f->device);
    *out = (UINT64)(uintptr_t)f;
    d3d12_log("[dlss-metalfx] D3D12 feature created input=%ux%u output=%ux%u flags=0x%x\n",
              width, height, output_width, output_height, flags);
    return S_OK;
}

void MadeiraD3D12TemporalRelease(UINT64 handle) {
    struct mad_dlss_feature *f = (void *)(uintptr_t)handle;
    if (!f || f->magic != MAD_DLSS_MAGIC) return;
    f->magic = 0;
    for (unsigned i = 0; i < 2; ++i) {
        if (f->cache[i].scaler) NSObject_release(f->cache[i].scaler);
        if (f->cache[i].motion) NSObject_release(f->cache[i].motion);
    }
    if (f->motion_pipeline) NSObject_release(f->motion_pipeline);
    ID3D12Device_Release((ID3D12Device *)f->device);
    free(f);
}

HRESULT MadeiraD3D12TemporalRecord(void *list, UINT64 handle, const struct madeira_dlss_desc *desc) {
    struct mad_list *l = list;
    struct mad_dlss_feature *f = (void *)(uintptr_t)handle;
    struct mad_resource *r[5];
    struct WMTFXTemporalScalerInfo info = {0};
    obj_handle_t scaler = 0, downsampled = 0;
    int highres = f && !(f->flags & 2);
    struct mad_cmd *cmd;
    struct mad_dlss_command *record;
    int fresh = 0;
    if (!l || l->vtbl != &g_list_vtbl || l->closed || !f || f->magic != MAD_DLSS_MAGIC ||
        l->device != f->device || !desc || desc->size != sizeof *desc ||
        desc->version != MADEIRA_DLSS_ABI_VERSION || desc->flags != f->flags ||
        !desc->input_width || !desc->input_height ||
        desc->output_width != f->output_width || desc->output_height != f->output_height ||
        !isfinite(desc->motion_scale_x) || !isfinite(desc->motion_scale_y) ||
        !isfinite(desc->jitter_x) || !isfinite(desc->jitter_y) ||
        !isfinite(desc->pre_exposure) || desc->pre_exposure <= 0) return E_INVALIDARG;
    r[0] = (void *)(uintptr_t)desc->color; r[1] = (void *)(uintptr_t)desc->output;
    r[2] = (void *)(uintptr_t)desc->depth; r[3] = (void *)(uintptr_t)desc->motion;
    r[4] = (void *)(uintptr_t)desc->exposure;
    for (unsigned i = 0; i < 5; ++i) {
        if (i == 4 && !r[i]) continue;
        if (!r[i] || r[i]->vtbl != &g_res_vtbl || r[i]->owner != f->device || !r[i]->texture ||
            r[i]->samples != 1 || r[i]->tex_type != WMTTextureType2D ||
            r[i]->desc.DepthOrArraySize != 1) return E_INVALIDARG;
    }
    if (r[0] == r[1] || r[0]->width > f->output_width || r[0]->height > f->output_height ||
        desc->input_width > r[0]->width || desc->input_height > r[0]->height ||
        r[1]->width != f->output_width || r[1]->height != f->output_height ||
        r[2]->width != r[0]->width || r[2]->height != r[0]->height ||
        r[3]->width != (highres ? f->output_width : r[0]->width) ||
        r[3]->height != (highres ? f->output_height : r[0]->height) ||
        (r[4] && (r[4]->width != 1 || r[4]->height != 1)) ||
        !(r[1]->desc.Flags & D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS)) return E_INVALIDARG;
    if (desc->input_width * 2 < f->output_width || desc->input_height * 2 < f->output_height)
        return E_NOTIMPL;
    /* The existing downsampling kernel maps full texture extents. Reject an
     * active subrect here rather than reconstructing with cropped motion. */
    if (highres && (desc->input_width != r[0]->width || desc->input_height != r[0]->height))
        return E_NOTIMPL;
    /* Float RG views are the supported native motion-vector representation. */
    if (r[3]->tex_pf != WMTPixelFormatRG16Float && r[3]->tex_pf != WMTPixelFormatRG32Float) return E_NOTIMPL;
    info.color_format = r[0]->tex_pf; info.output_format = r[1]->tex_pf;
    info.depth_format = r[2]->tex_pf; info.motion_format = highres ? WMTPixelFormatRG32Float : r[3]->tex_pf;
    info.input_width = r[0]->width; info.input_height = r[0]->height;
    info.output_width = f->output_width; info.output_height = f->output_height;
    info.input_content_min_scale = 1.0f; info.input_content_max_scale = 3.0f;
    info.auto_exposure = !!(f->flags & 64);
    info.input_content_properties_enabled = true;
    info.requires_synchronous_initialization = true;
    for (unsigned i = 0; i < 2; ++i)
        if (f->cache[i].scaler && !memcmp(&info, &f->cache[i].info, sizeof info)) { scaler = f->cache[i].scaler; downsampled = f->cache[i].motion; }
    if (!scaler) {
        unsigned i = f->replacement++ & 1;
        scaler = MTLDevice_newTemporalScaler(f->device->mtl_device, &info);
        if (!scaler) {
            d3d12_log("[dlss-metalfx] D3D12: temporal scaler rejected formats or dimensions\n");
            return E_NOTIMPL;
        }
        if (highres) {
            struct WMTTextureInfo tex = {0};
            tex.width = info.input_width; tex.height = info.input_height; tex.depth = 1;
            tex.array_length = tex.mipmap_level_count = tex.sample_count = 1;
            tex.type = WMTTextureType2D; tex.pixel_format = WMTPixelFormatRG32Float;
            tex.usage = WMTTextureUsageShaderRead | WMTTextureUsageShaderWrite;
            tex.options = WMTResourceStorageModePrivate;
            downsampled = MTLDevice_newTexture(f->device->mtl_device, &tex);
            if (!f->motion_pipeline) {
                obj_handle_t data = DispatchData_alloc_init((uint64_t)(uintptr_t)dxmt_command, dxmt_command_len);
                obj_handle_t error = 0, library = MTLDevice_newLibrary(f->device->mtl_device, data, &error);
                if (data) NSObject_release(data);
                if (library) {
                    obj_handle_t fn = MTLLibrary_newFunction(library, "cs_downscale_dilated_mv");
                    struct WMTComputePipelineInfo pipeline = {0}; pipeline.compute_function = fn;
                    if (fn) f->motion_pipeline = MTLDevice_newComputePipelineState(f->device->mtl_device, &pipeline, &error);
                    if (fn) NSObject_release(fn);
                    NSObject_release(library);
                }
            }
            if (!downsampled || !f->motion_pipeline) {
                if (downsampled) NSObject_release(downsampled);
                NSObject_release(scaler); return E_NOTIMPL;
            }
        }
        if (f->cache[i].scaler) NSObject_release(f->cache[i].scaler);
        if (f->cache[i].motion) NSObject_release(f->cache[i].motion);
        f->cache[i].motion = downsampled;
        f->cache[i].scaler = scaler; f->cache[i].info = info; fresh = 1;
        d3d12_log("[dlss-metalfx] D3D12 temporal scaler active input=%ux%u output=%ux%u\n",
                  info.input_width, info.input_height, info.output_width, info.output_height);
    }
    record = calloc(1, sizeof *record);
    if (!record) return E_OUTOFMEMORY;
    cmd = mad_list_push(l, MC_TEMPORAL);
    if (!cmd) { free(record); return E_OUTOFMEMORY; }
    record->scaler = scaler; NSObject_retain(scaler);
    if (downsampled) {
        record->motion = downsampled; record->pipeline = f->motion_pipeline;
        NSObject_retain(downsampled); NSObject_retain(record->pipeline);
    }
    for (unsigned i = 0; i < 5; ++i) if ((record->resources[i] = r[i])) {
        ID3D12Resource_AddRef((ID3D12Resource *)r[i]); mad_list_note_used(l, r[i]);
    }
    record->props = (struct WMTFXTemporalScalerProps){desc->input_width, desc->input_height,
        fresh || scaler != f->last_scaler || desc->reset, !!(f->flags & 8), desc->motion_scale_x, desc->motion_scale_y,
        desc->jitter_x, desc->jitter_y, desc->pre_exposure};
    cmd->u.temporal = record;
    f->last_scaler = scaler;
    return S_OK;
}
