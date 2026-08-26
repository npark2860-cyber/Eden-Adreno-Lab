#!/usr/bin/env python3
'''Split the texture alias-copy bucket into generic routes and Vulkan direct-copy subreasons.

Expected order:
  - transplant_dc95_texture_fill_reasons.py
  - this pass

Instrumentation-only. No copy, barrier, render-pass, or synchronization behavior is changed.
The existing alias-copy parent scope remains active; child scopes temporarily override the
current BufferCategory and restore it afterwards.
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

    # Self-heal the dependency chain when this pass is invoked directly.
    header = vulkan / "vk_adreno_profiler.h"
    if "OtherTextureRtScale" not in header.read_text(encoding="utf-8"):
        parent = Path(__file__).with_name("transplant_dc95_texture_fill_reasons.py")
        subprocess.run([sys.executable, str(parent), str(root)], check=True)

    text = header.read_text(encoding="utf-8")
    old = '''        OtherTextureRtFindColor,\n        OtherTextureRtFindDepth,\n        OtherTextureRtScale,\n        Count,\n'''
    new = '''        OtherTextureRtFindColor,\n        OtherTextureRtFindDepth,\n        OtherTextureRtScale,\n        OtherTextureAliasDirectRoute,\n        OtherTextureAliasReinterpretRoute,\n        OtherTextureAliasConvertRoute,\n        OtherTextureAliasDirectResolveInvalidate,\n        OtherTextureAliasDirectBpbReinterpret,\n        OtherTextureAliasDirectVkCopy,\n        Count,\n'''
    text = replace_once(text, old, new, "alias-copy profiler categories")
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")
    old = '''    case AdrenoProfiler::BufferCategory::OtherTextureRtScale:\n        return "other/texture/rt-scale";\n    default:\n'''
    new = '''    case AdrenoProfiler::BufferCategory::OtherTextureRtScale:\n        return "other/texture/rt-scale";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectRoute:\n        return "other/texture/alias-copy/direct-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasReinterpretRoute:\n        return "other/texture/alias-copy/reinterpret-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasConvertRoute:\n        return "other/texture/alias-copy/convert-route";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectResolveInvalidate:\n        return "other/texture/alias-copy/direct-resolve-invalidate";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectBpbReinterpret:\n        return "other/texture/alias-copy/direct-bpb-reinterpret";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasDirectVkCopy:\n        return "other/texture/alias-copy/direct-vk-copy";\n    default:\n'''
    text = replace_once(text, old, new, "alias-copy profiler names")
    cpp.write_text(text, encoding="utf-8")

    # Generic TextureCache CopyImage routing. The texture-fill pass added the optional
    # BeginX1TextureSubcategory/EndX1TextureSubcategory bridge. Numeric values below are
    # deliberately appended after the existing 25..34 texture subcategories.
    cache = root / "src/video_core/texture_cache/texture_cache.h"
    text = cache.read_text(encoding="utf-8")

    old = '''    if (src_format_type == dst_format_type) {\n        if constexpr (HAS_EMULATED_COPIES) {\n            if (!runtime.CanImageBeCopied(dst, src)) {\n                return runtime.EmulateCopyImage(dst, src, copies);\n            }\n        }\n        return runtime.CopyImage(dst, src, copies);\n    }\n'''
    new = '''    if (src_format_type == dst_format_type) {\n        if constexpr (HAS_EMULATED_COPIES) {\n            if (!runtime.CanImageBeCopied(dst, src)) {\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::BeginX1TextureSubcategory(35);\n                }\n                runtime.EmulateCopyImage(dst, src, copies);\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::EndX1TextureSubcategory();\n                }\n                return;\n            }\n        }\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(35);\n        }\n        runtime.CopyImage(dst, src, copies);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n        return;\n    }\n'''
    text = replace_once(text, old, new, "alias-copy direct generic route")

    old = '''    if (runtime.ShouldReinterpret(dst, src)) {\n        return runtime.ReinterpretImage(dst, src, copies);\n    }\n    for (const ImageCopy& copy : copies) {\n'''
    new = '''    if (runtime.ShouldReinterpret(dst, src)) {\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(36);\n        }\n        runtime.ReinterpretImage(dst, src, copies);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n        return;\n    }\n    if constexpr (requires {\n                      P::BeginX1TextureSubcategory(u32{});\n                      P::EndX1TextureSubcategory();\n                  }) {\n        P::BeginX1TextureSubcategory(37);\n    }\n    for (const ImageCopy& copy : copies) {\n'''
    text = replace_once(text, old, new, "alias-copy reinterpret and convert route start")

    old = '''        runtime.ConvertImage(dst_framebuffer, dst_view, src_view);\n    }\n}\n\ntemplate <class P>\nvoid TextureCache<P>::BindRenderTarget'''
    new = '''        runtime.ConvertImage(dst_framebuffer, dst_view, src_view);\n    }\n    if constexpr (requires {\n                      P::BeginX1TextureSubcategory(u32{});\n                      P::EndX1TextureSubcategory();\n                  }) {\n        P::EndX1TextureSubcategory();\n    }\n}\n\ntemplate <class P>\nvoid TextureCache<P>::BindRenderTarget'''
    text = replace_once(text, old, new, "alias-copy convert route end")
    cache.write_text(text, encoding="utf-8")

    # Vulkan direct CopyImage has a second decision layer. Split the resolve-shadow
    # invalidation, bytes-per-block reinterpret fallback, and actual vkCmdCopyImage path.
    vk_cache = vulkan / "vk_texture_cache.cpp"
    text = vk_cache.read_text(encoding="utf-8")

    old = '''void TextureCacheRuntime::CopyImage(Image& dst, Image& src,\n                                    std::span<const VideoCommon::ImageCopy> copies) {\n    if (ENABLE_MSAA_RESOLVE_CONSUME) {\n        InvalidateResolveShadow(dst.Handle());\n    }\n'''
    new = '''void TextureCacheRuntime::CopyImage(Image& dst, Image& src,\n                                    std::span<const VideoCommon::ImageCopy> copies) {\n    if (ENABLE_MSAA_RESOLVE_CONSUME) {\n        AdrenoProfiler::Get().PushBufferCategoryOverride(\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectResolveInvalidate);\n        InvalidateResolveShadow(dst.Handle());\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n    }\n'''
    text = replace_once(text, old, new, "alias-copy direct resolve invalidation")

    old = '''        return ReinterpretImage(dst, src, std::span{&oneCopy, 1});\n'''
    new = '''        AdrenoProfiler::Get().PushBufferCategoryOverride(\n            AdrenoProfiler::BufferCategory::OtherTextureAliasDirectBpbReinterpret);\n        ReinterpretImage(dst, src, std::span{&oneCopy, 1});\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n        return;\n'''
    text = replace_once(text, old, new, "alias-copy direct bytes-per-block reinterpret fallback")

    old = '''    const VkImage dst_image = dst.Handle();\n    const VkImage src_image = src.Handle();\n    scheduler.RequestOutsideRenderPassOperationContext();\n    scheduler.Record([dst_image, src_image, aspect_mask, vk_copies](vk::CommandBuffer cmdbuf) {\n'''
    new = '''    const VkImage dst_image = dst.Handle();\n    const VkImage src_image = src.Handle();\n    AdrenoProfiler::Get().PushBufferCategoryOverride(\n        AdrenoProfiler::BufferCategory::OtherTextureAliasDirectVkCopy);\n    scheduler.RequestOutsideRenderPassOperationContext();\n    AdrenoProfiler::Get().PopBufferCategoryOverride();\n    scheduler.Record([dst_image, src_image, aspect_mask, vk_copies](vk::CommandBuffer cmdbuf) {\n'''
    text = replace_once(text, old, new, "alias-copy direct vk copy outside-RP")

    vk_cache.write_text(text, encoding="utf-8")

    print("Applied alias CopyImage generic/Vulkan subreason attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
