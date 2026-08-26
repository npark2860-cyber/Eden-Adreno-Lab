#!/usr/bin/env python3
'''Split the texture alias-copy bucket into generic routes and Vulkan direct-copy subreasons.

Expected order:
  - transplant_dc95_texture_fill_reasons.py
  - this pass

Instrumentation-only. No copy, barrier, render-pass, or synchronization behavior is changed.
Child scopes are activated only while the current parent category is alias-copy, preventing
CopyImage calls from JoinImages or other texture paths from contaminating this experiment.
'''

from pathlib import Path
import subprocess
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_alias_copy_reasons.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    header = vulkan / "vk_adreno_profiler.h"
    if "OtherTextureRtScale" not in header.read_text(encoding="utf-8"):
        parent = Path(__file__).with_name("transplant_dc95_texture_fill_reasons.py")
        subprocess.run([sys.executable, str(parent), str(root)], check=True)

    text = header.read_text(encoding="utf-8")
    old = '''        OtherTextureRtFindColor,\n        OtherTextureRtFindDepth,\n        OtherTextureRtScale,\n        Count,\n'''
    new = '''        OtherTextureRtFindColor,\n        OtherTextureRtFindDepth,\n        OtherTextureRtScale,\n        OtherTextureAliasDirectRoute,\n        OtherTextureAliasReinterpretRoute,\n        OtherTextureAliasConvertRoute,\n        OtherTextureAliasDirectResolveInvalidate,\n        OtherTextureAliasDirectBpbReinterpret,\n        OtherTextureAliasDirectVkCopy,\n        Count,\n'''
    text = replace_once(text, old, new, "alias-copy profiler categories")

    old = '''    void PushBufferCategoryOverride(BufferCategory category) noexcept;\n    void PopBufferCategoryOverride() noexcept;\n'''
    new = '''    void PushBufferCategoryOverride(BufferCategory category) noexcept;\n    void PopBufferCategoryOverride() noexcept;\n    bool PushBufferCategoryOverrideIf(BufferCategory expected, BufferCategory category) noexcept;\n'''
    text = replace_once(text, old, new, "conditional alias override API")
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")
    old = '''    case AdrenoProfiler::BufferCategory::OtherTextureRtScale:\n        return "other/texture/rt-scale";\n    default:\n'''
    new = '''    case AdrenoProfiler::BufferCategory::OtherTextureRtScale:\n        return "other/texture/rt-scale";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectRoute:\n        return "other/texture/alias-copy/direct-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasReinterpretRoute:\n        return "other/texture/alias-copy/reinterpret-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasConvertRoute:\n        return "other/texture/alias-copy/convert-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectResolveInvalidate:\n        return "other/texture/alias-copy/direct-resolve-invalidate";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectBpbReinterpret:\n        return "other/texture/alias-copy/direct-bpb-reinterpret";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectVkCopy:\n        return "other/texture/alias-copy/direct-vk-copy";\n    default:\n'''
    text = replace_once(text, old, new, "alias-copy profiler names")

    old = '''void AdrenoProfiler::PopBufferCategoryOverride() noexcept {\n    if (buffer_category_state.override_depth == 0) {\n        return;\n    }\n    buffer_category_state.category =\n        buffer_category_state.override_stack[--buffer_category_state.override_depth];\n}\n\nvoid AdrenoProfiler::EndWork()'''
    new = '''void AdrenoProfiler::PopBufferCategoryOverride() noexcept {\n    if (buffer_category_state.override_depth == 0) {\n        return;\n    }\n    buffer_category_state.category =\n        buffer_category_state.override_stack[--buffer_category_state.override_depth];\n}\n\nbool AdrenoProfiler::PushBufferCategoryOverrideIf(BufferCategory expected,\n                                                   BufferCategory category) noexcept {\n    if (!CorrelationEnabled() || work_correlation.origin == WorkOrigin::None ||\n        category == BufferCategory::None || buffer_category_state.category != expected) {\n        return false;\n    }\n    if (buffer_category_state.override_depth >= buffer_category_state.override_stack.size()) {\n        return false;\n    }\n    buffer_category_state.override_stack[buffer_category_state.override_depth++] =\n        buffer_category_state.category;\n    buffer_category_state.category = category;\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->scopes.fetch_add(1, std::memory_order_relaxed);\n    }\n    return true;\n}\n\nvoid AdrenoProfiler::EndWork()'''
    text = replace_once(text, old, new, "conditional alias override implementation")
    cpp.write_text(text, encoding="utf-8")

    vk_header = vulkan / "vk_texture_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    old = '''    static void EndX1TextureSubcategory() {\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n    }\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    new = '''    static void EndX1TextureSubcategory() {\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n    }\n\n    static bool BeginX1TextureSubcategoryIf(u32 expected, u32 category) {\n        return AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n            static_cast<AdrenoProfiler::BufferCategory>(expected),\n            static_cast<AdrenoProfiler::BufferCategory>(category));\n    }\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    text = replace_once(text, old, new, "conditional Vulkan TextureCacheParams bridge")
    vk_header.write_text(text, encoding="utf-8")

    # Generic TextureCache is instantiated for OpenGL too. Give that backend a no-op bridge so
    # the shared route code remains compile-safe while still activating only on Vulkan.
    gl_header = root / "src/video_core/renderer_opengl/gl_texture_cache.h"
    text = gl_header.read_text(encoding="utf-8")
    old = '''struct TextureCacheParams {\n    static constexpr bool ENABLE_VALIDATION = true;\n    static constexpr bool FRAMEBUFFER_BLITS = true;\n    static constexpr bool HAS_EMULATED_COPIES = true;\n    static constexpr bool HAS_DEVICE_MEMORY_INFO = true;\n    static constexpr bool IMPLEMENTS_ASYNC_DOWNLOADS = true;\n\n    using Runtime = OpenGL::TextureCacheRuntime;\n'''
    new = '''struct TextureCacheParams {\n    static constexpr bool ENABLE_VALIDATION = true;\n    static constexpr bool FRAMEBUFFER_BLITS = true;\n    static constexpr bool HAS_EMULATED_COPIES = true;\n    static constexpr bool HAS_DEVICE_MEMORY_INFO = true;\n    static constexpr bool IMPLEMENTS_ASYNC_DOWNLOADS = true;\n\n    static bool BeginX1TextureSubcategoryIf(u32, u32) {\n        return false;\n    }\n\n    static void EndX1TextureSubcategory() {}\n\n    using Runtime = OpenGL::TextureCacheRuntime;\n'''
    text = replace_once(text, old, new, "OpenGL no-op alias bridge")
    gl_header.write_text(text, encoding="utf-8")

    # Category 29 is the existing OtherTextureAliasCopy parent from the texture-fill pass.
    # New appended categories are 35 direct, 36 reinterpret, 37 convert.
    cache = root / "src/video_core/texture_cache/texture_cache.h"
    text = cache.read_text(encoding="utf-8")

    old = '''    if (src_format_type == dst_format_type) {\n        if constexpr (HAS_EMULATED_COPIES) {\n            if (!runtime.CanImageBeCopied(dst, src)) {\n                return runtime.EmulateCopyImage(dst, src, copies);\n            }\n        }\n        return runtime.CopyImage(dst, src, copies);\n    }\n'''
    new = '''    if (src_format_type == dst_format_type) {\n        if constexpr (HAS_EMULATED_COPIES) {\n            if (!runtime.CanImageBeCopied(dst, src)) {\n                bool x1_alias_route = false;\n                if constexpr (requires { P::BeginX1TextureSubcategoryIf(u32{}, u32{}); }) {\n                    x1_alias_route = P::BeginX1TextureSubcategoryIf(29, 35);\n                }\n                runtime.EmulateCopyImage(dst, src, copies);\n                if (x1_alias_route) {\n                    P::EndX1TextureSubcategory();\n                }\n                return;\n            }\n        }\n        bool x1_alias_route = false;\n        if constexpr (requires { P::BeginX1TextureSubcategoryIf(u32{}, u32{}); }) {\n            x1_alias_route = P::BeginX1TextureSubcategoryIf(29, 35);\n        }\n        runtime.CopyImage(dst, src, copies);\n        if (x1_alias_route) {\n            P::EndX1TextureSubcategory();\n        }\n        return;\n    }\n'''
    text = replace_once(text, old, new, "alias-copy direct generic route")

    old = '''    if (runtime.ShouldReinterpret(dst, src)) {\n        return runtime.ReinterpretImage(dst, src, copies);\n    }\n    for (const ImageCopy& copy : copies) {\n'''
    new = '''    if (runtime.ShouldReinterpret(dst, src)) {\n        bool x1_alias_route = false;\n        if constexpr (requires { P::BeginX1TextureSubcategoryIf(u32{}, u32{}); }) {\n            x1_alias_route = P::BeginX1TextureSubcategoryIf(29, 36);\n        }\n        runtime.ReinterpretImage(dst, src, copies);\n        if (x1_alias_route) {\n            P::EndX1TextureSubcategory();\n        }\n        return;\n    }\n    bool x1_alias_convert_route = false;\n    if constexpr (requires { P::BeginX1TextureSubcategoryIf(u32{}, u32{}); }) {\n        x1_alias_convert_route = P::BeginX1TextureSubcategoryIf(29, 37);\n    }\n    for (const ImageCopy& copy : copies) {\n'''
    text = replace_once(text, old, new, "alias-copy reinterpret and convert route start")

    old = '''        runtime.ConvertImage(dst_framebuffer, dst_view, src_view);\n    }\n}\n\ntemplate <class P>\nvoid TextureCache<P>::BindRenderTarget'''
    new = '''        runtime.ConvertImage(dst_framebuffer, dst_view, src_view);\n    }\n    if (x1_alias_convert_route) {\n        P::EndX1TextureSubcategory();\n    }\n}\n\ntemplate <class P>\nvoid TextureCache<P>::BindRenderTarget'''
    text = replace_once(text, old, new, "alias-copy convert route end")
    cache.write_text(text, encoding="utf-8")

    # Vulkan runtime direct-route children are also parent-gated. This prevents direct
    # runtime.CopyImage calls from JoinImages/overlap maintenance from entering alias buckets.
    vk_cache = vulkan / "vk_texture_cache.cpp"
    text = vk_cache.read_text(encoding="utf-8")

    old = '''void TextureCacheRuntime::CopyImage(Image& dst, Image& src,\n                                    std::span<const VideoCommon::ImageCopy> copies) {\n    if (ENABLE_MSAA_RESOLVE_CONSUME) {\n        InvalidateResolveShadow(dst.Handle());\n    }\n'''
    new = '''void TextureCacheRuntime::CopyImage(Image& dst, Image& src,\n                                    std::span<const VideoCommon::ImageCopy> copies) {\n    if (ENABLE_MSAA_RESOLVE_CONSUME) {\n        const bool x1_alias_resolve = AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectRoute,\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectResolveInvalidate);\n        InvalidateResolveShadow(dst.Handle());\n        if (x1_alias_resolve) {\n            AdrenoProfiler::Get().PopBufferCategoryOverride();\n        }\n    }\n'''
    text = replace_once(text, old, new, "alias-copy direct resolve invalidation")

    old = '''        return ReinterpretImage(dst, src, std::span{&oneCopy, 1});\n'''
    new = '''        const bool x1_alias_bpb = AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectRoute,\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectBpbReinterpret);\n        ReinterpretImage(dst, src, std::span{&oneCopy, 1});\n        if (x1_alias_bpb) {\n            AdrenoProfiler::Get().PopBufferCategoryOverride();\n        }\n        return;\n'''
    text = replace_once(text, old, new, "alias-copy direct bytes-per-block reinterpret fallback")

    old = '''    const VkImage dst_image = dst.Handle();\n    const VkImage src_image = src.Handle();\n    scheduler.RequestOutsideRenderPassOperationContext();\n    scheduler.Record([dst_image, src_image, aspect_mask, vk_copies](vk::CommandBuffer cmdbuf) {\n'''
    new = '''    const VkImage dst_image = dst.Handle();\n    const VkImage src_image = src.Handle();\n    const bool x1_alias_vk_copy = AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n        AdrenoProfiler::BufferCategory::OtherTextureAliasDirectRoute,\n        AdrenoProfiler::BufferCategory::OtherTextureAliasDirectVkCopy);\n    scheduler.RequestOutsideRenderPassOperationContext();\n    if (x1_alias_vk_copy) {\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n    }\n    scheduler.Record([dst_image, src_image, aspect_mask, vk_copies](vk::CommandBuffer cmdbuf) {\n'''
    text = replace_once(text, old, new, "alias-copy direct vk copy outside-RP")

    vk_cache.write_text(text, encoding="utf-8")

    print("Applied parent-gated alias CopyImage generic/Vulkan subreason attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
