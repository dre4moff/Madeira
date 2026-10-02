// A D3D pipeline may omit its pixel shader for depth/stencil-only rendering.
// Metal mesh pipelines require a fragment function while rasterization is on.
// No color, depth override, discard, resources or side effects: retain the
// rasterizer's interpolated depth and its normal depth/stencil tests.
#include <metal_stdlib>
using namespace metal;
fragment void madeira_mesh_null_fragment() {}
