#!/usr/bin/env python3
'''Split Draw texture-related reason buckets below FillImageViews/UpdateRenderTargets.

Expected order:
  - transplant_dc95_draw_other_reasons.py
  - this pass

Instrumentation-only. Existing outer Draw reason scopes remain intact. This pass adds
override subcategories that temporarily replace the current BufferCategory and restore
the parent afterwards, so texture work can be split without losing parent attribution.
'''

from pathlib import Path
import subprocess
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, got {count}")
    return text.replace(old, new)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_texture_fill_reasons.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    header = vulkan / "vk_adreno_profiler.h"
    if "OtherTextureFillImageViews" not in header.read_text(encoding="utf-8"):
        parent_transplant = Path(__file__).with_name("transplant_dc95_draw_other_reasons.py")
        subprocess.run([sys.executable, str(parent_transplant), str(root)], check=True)

    text = header.read_text(encoding="utf-8")
    old = '''        OtherTransformFeedback,\n        OtherQueryCounter,\n        OtherDrawCommand,\n        Count,\n'''
    new = '''        OtherTransformFeedback,\n        OtherQueryCounter,\n        OtherDrawCommand,\n        OtherTextureCreateView,\n        OtherTextureRefreshStandard,\n        OtherTextureRefreshConverted,\n        OtherTextureRefreshAccelerated,\n        OtherTextureAliasCopy,\n        OtherTextureAliasScale,\n        OtherTextureBlacklistScale,\n        OtherTextureRtFindColor,\n        OtherTextureRtFindDepth,\n        OtherTextureRtScale,\n        Count,\n'''
    text = replace_once(text, old, new, "texture subreason categories")

    old = '''    void BeginBufferCategory(BufferCategory category) noexcept;\n    void EndBufferCategory() noexcept;\n'''
    new = '''    void BeginBufferCategory(BufferCategory category) noexcept;\n    void EndBufferCategory() noexcept;\n    void PushBufferCategoryOverride(BufferCategory category) noexcept;\n    void PopBufferCategoryOverride() noexcept;\n'''
    text = replace_once(text, old, new, "texture override API")
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")

    old = '''struct BufferCategoryState {\n    AdrenoProfiler::BufferCategory category{AdrenoProfiler::BufferCategory::None};\n    u32 depth{};\n};\n'''
    new = '''struct BufferCategoryState {\n    AdrenoProfiler::BufferCategory category{AdrenoProfiler::BufferCategory::None};\n    u32 depth{};\n    std::array<AdrenoProfiler::BufferCategory, 16> override_stack{};\n    u32 override_depth{};\n};\n'''
    text = replace_once(text, old, new, "texture override state")

    old = '''    case AdrenoProfiler::BufferCategory::OtherDrawCommand:\n        return "other/draw-command";\n    default:\n'''
    new = '''    case AdrenoProfiler::BufferCategory::OtherDrawCommand:\n        return "other/draw-command";\n    case AdrenoProfiler::BufferCategory::OtherTextureCreateView:\n        return "other/texture/create-view";\n    case AdrenoProfiler::BufferCategory::OtherTextureRefreshStandard:\n        return "other/texture/refresh-standard";\n    case AdrenoProfiler::BufferCategory::OtherTextureRefreshConverted:\n        return "other/texture/refresh-converted";\n    case AdrenoProfiler::BufferCategory::OtherTextureRefreshAccelerated:\n        return "other/texture/refresh-accelerated";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasCopy:\n        return "other/texture/alias-copy";\n    case AdrenoProfiler::BufferCategory::OtherTextureAliasScale:\n        return "other/texture/alias-scale";\n    case AdrenoProfiler::BufferCategory::OtherTextureBlacklistScale:\n        return "other/texture/blacklist-scale";\n    case AdrenoProfiler::BufferCategory::OtherTextureRtFindColor:\n        return "other/texture/rt-find-color";\n    case AdrenoProfiler::BufferCategory::OtherTextureRtFindDepth:\n        return "other/texture/rt-find-depth";\n    case AdrenoProfiler::BufferCategory::OtherTextureRtScale:\n        return "other/texture/rt-scale";\n    default:\n'''
    text = replace_once(text, old, new, "texture subreason names")

    old = '''void AdrenoProfiler::EndBufferCategory() noexcept {\n    if (buffer_category_state.depth == 0) {\n        return;\n    }\n    if (--buffer_category_state.depth == 0) {\n        buffer_category_state.category = BufferCategory::None;\n    }\n}\n\nvoid AdrenoProfiler::EndWork()'''
    new = '''void AdrenoProfiler::EndBufferCategory() noexcept {\n    if (buffer_category_state.depth == 0) {\n        return;\n    }\n    if (--buffer_category_state.depth == 0) {\n        buffer_category_state.category = BufferCategory::None;\n    }\n}\n\nvoid AdrenoProfiler::PushBufferCategoryOverride(BufferCategory category) noexcept {\n    if (!CorrelationEnabled() || work_correlation.origin == WorkOrigin::None ||\n        category == BufferCategory::None) {\n        return;\n    }\n    if (buffer_category_state.override_depth >= buffer_category_state.override_stack.size()) {\n        return;\n    }\n    buffer_category_state.override_stack[buffer_category_state.override_depth++] =\n        buffer_category_state.category;\n    buffer_category_state.category = category;\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->scopes.fetch_add(1, std::memory_order_relaxed);\n    }\n}\n\nvoid AdrenoProfiler::PopBufferCategoryOverride() noexcept {\n    if (buffer_category_state.override_depth == 0) {\n        return;\n    }\n    buffer_category_state.category =\n        buffer_category_state.override_stack[--buffer_category_state.override_depth];\n}\n\nvoid AdrenoProfiler::EndWork()'''
    text = replace_once(text, old, new, "texture override lifecycle")
    cpp.write_text(text, encoding="utf-8")

    vk_header = vulkan / "vk_texture_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
        "vk texture profiler include",
    )
    old = '''struct TextureCacheParams {\n    static constexpr bool ENABLE_VALIDATION = true;\n    static constexpr bool FRAMEBUFFER_BLITS = false;\n    static constexpr bool HAS_EMULATED_COPIES = false;\n    static constexpr bool HAS_DEVICE_MEMORY_INFO = true;\n    static constexpr bool IMPLEMENTS_ASYNC_DOWNLOADS = true;\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    new = '''struct TextureCacheParams {\n    static constexpr bool ENABLE_VALIDATION = true;\n    static constexpr bool FRAMEBUFFER_BLITS = false;\n    static constexpr bool HAS_EMULATED_COPIES = false;\n    static constexpr bool HAS_DEVICE_MEMORY_INFO = true;\n    static constexpr bool IMPLEMENTS_ASYNC_DOWNLOADS = true;\n\n    static void BeginX1TextureSubcategory(u32 category) {\n        AdrenoProfiler::Get().PushBufferCategoryOverride(\n            static_cast<AdrenoProfiler::BufferCategory>(category));\n    }\n\n    static void EndX1TextureSubcategory() {\n        AdrenoProfiler::Get().PopBufferCategoryOverride();\n    }\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    text = replace_once(text, old, new, "vk TextureCacheParams bridge")
    vk_header.write_text(text, encoding="utf-8")

    cache = root / "src/video_core/texture_cache/texture_cache.h"
    text = cache.read_text(encoding="utf-8")

    old = '''                    has_blacklisted |= ScaleDown(image);\n                    image.scale_rating = 0;\n'''
    new = '''                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::BeginX1TextureSubcategory(31);\n                    }\n                    has_blacklisted |= ScaleDown(image);\n                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::EndX1TextureSubcategory();\n                    }\n                    image.scale_rating = 0;\n'''
    text = replace_once(text, old, new, "fill blacklist scale")

    old = '''            const auto [pair, is_new_tc] = channel_state->image_views.try_emplace(descriptor);\n            if (is_new_tc)\n                pair->second = CreateImageView(descriptor);\n            PrepareImageView(pair->second, false, false);\n'''
    new = '''            const auto [pair, is_new_tc] = channel_state->image_views.try_emplace(descriptor);\n            if (is_new_tc) {\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::BeginX1TextureSubcategory(25);\n                }\n                pair->second = CreateImageView(descriptor);\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::EndX1TextureSubcategory();\n                }\n            }\n            PrepareImageView(pair->second, false, false);\n'''
    text = replace_once(text, old, new, "visit create view")

    old = '''    auto staging = runtime.UploadStagingBuffer(MapSizeBytes(image));\n    UploadImageContents(image, staging);\n    runtime.InsertUploadMemoryBarrier();\n'''
    new = '''    u32 x1_texture_refresh_category = 26;\n    if (True(image.flags & ImageFlagBits::AcceleratedUpload)) {\n        x1_texture_refresh_category = 28;\n    } else if (True(image.flags & ImageFlagBits::Converted)) {\n        x1_texture_refresh_category = 27;\n    }\n    if constexpr (requires {\n                      P::BeginX1TextureSubcategory(u32{});\n                      P::EndX1TextureSubcategory();\n                  }) {\n        P::BeginX1TextureSubcategory(x1_texture_refresh_category);\n    }\n    auto staging = runtime.UploadStagingBuffer(MapSizeBytes(image));\n    UploadImageContents(image, staging);\n    runtime.InsertUploadMemoryBarrier();\n    if constexpr (requires {\n                      P::BeginX1TextureSubcategory(u32{});\n                      P::EndX1TextureSubcategory();\n                  }) {\n        P::EndX1TextureSubcategory();\n    }\n'''
    text = replace_once(text, old, new, "refresh upload path")

    old = '''    Image& image = slot_images[image_id];\n    bool any_rescaled = True(image.flags & ImageFlagBits::Rescaled);\n'''
    new = '''    Image& image = slot_images[image_id];\n    const auto x1_alias_scale_up = [this](Image& target) {\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(30);\n        }\n        ScaleUp(target);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n    };\n    const auto x1_alias_scale_down = [this](Image& target) {\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(30);\n        }\n        ScaleDown(target);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n    };\n    const auto x1_alias_copy = [this](ImageId dst_id, ImageId src_id, const auto& copies) {\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(29);\n        }\n        CopyImage(dst_id, src_id, copies);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n    };\n    bool any_rescaled = True(image.flags & ImageFlagBits::Rescaled);\n'''
    text = replace_once(text, old, new, "alias helpers")
    text = replace_once(
        text,
        '''        if (can_rescale) {\n            ScaleUp(image);\n        } else {\n            ScaleDown(image);\n        }\n''',
        '''        if (can_rescale) {\n            x1_alias_scale_up(image);\n        } else {\n            x1_alias_scale_down(image);\n        }\n''',
        "alias root scale",
    )
    text = replace_count(
        text,
        '            CopyImage(image_id, aliased->id, aliased->copies);\n',
        '            x1_alias_copy(image_id, aliased->id, aliased->copies);\n',
        2,
        "nested alias copy calls",
    )
    text = replace_once(
        text,
        '        CopyImage(image_id, aliased->id, aliased->copies);\n',
        '        x1_alias_copy(image_id, aliased->id, aliased->copies);\n',
        "final alias copy call",
    )
    text = replace_once(
        text,
        '''            ScaleDown(aliased_image);\n            x1_alias_copy(image_id, aliased->id, aliased->copies);\n''',
        '''            x1_alias_scale_down(aliased_image);\n            x1_alias_copy(image_id, aliased->id, aliased->copies);\n''',
        "alias child scale down",
    )
    text = replace_once(
        text,
        '''        ScaleUp(aliased_image);\n        x1_alias_copy(image_id, aliased->id, aliased->copies);\n''',
        '''        x1_alias_scale_up(aliased_image);\n        x1_alias_copy(image_id, aliased->id, aliased->copies);\n''',
        "alias child scale up",
    )

    old = '''                BindRenderTarget(&color_buffer_id, FindColorBuffer(index));\n'''
    new = '''                ImageViewId x1_new_color_buffer{};\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::BeginX1TextureSubcategory(32);\n                }\n                x1_new_color_buffer = FindColorBuffer(index);\n                if constexpr (requires {\n                                  P::BeginX1TextureSubcategory(u32{});\n                                  P::EndX1TextureSubcategory();\n                              }) {\n                    P::EndX1TextureSubcategory();\n                }\n                BindRenderTarget(&color_buffer_id, x1_new_color_buffer);\n'''
    text = replace_once(text, old, new, "rt find color")

    old = '''            BindRenderTarget(&render_targets.depth_buffer_id, FindDepthBuffer());\n'''
    new = '''            ImageViewId x1_new_depth_buffer{};\n            if constexpr (requires {\n                              P::BeginX1TextureSubcategory(u32{});\n                              P::EndX1TextureSubcategory();\n                          }) {\n                P::BeginX1TextureSubcategory(33);\n            }\n            x1_new_depth_buffer = FindDepthBuffer();\n            if constexpr (requires {\n                              P::BeginX1TextureSubcategory(u32{});\n                              P::EndX1TextureSubcategory();\n                          }) {\n                P::EndX1TextureSubcategory();\n            }\n            BindRenderTarget(&render_targets.depth_buffer_id, x1_new_depth_buffer);\n'''
    text = replace_once(text, old, new, "rt find depth")

    old = '''                    Image& image = slot_images[image_id];\n                    ScaleUp(image);\n'''
    new = '''                    Image& image = slot_images[image_id];\n                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::BeginX1TextureSubcategory(34);\n                    }\n                    ScaleUp(image);\n                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::EndX1TextureSubcategory();\n                    }\n'''
    text = replace_once(text, old, new, "rt scale up")

    old = '''                    Image& image = slot_images[image_id];\n                    ScaleDown(image);\n'''
    new = '''                    Image& image = slot_images[image_id];\n                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::BeginX1TextureSubcategory(34);\n                    }\n                    ScaleDown(image);\n                    if constexpr (requires {\n                                      P::BeginX1TextureSubcategory(u32{});\n                                      P::EndX1TextureSubcategory();\n                                  }) {\n                        P::EndX1TextureSubcategory();\n                    }\n'''
    text = replace_once(text, old, new, "rt scale down")

    cache.write_text(text, encoding="utf-8")

    print("Applied texture FillImageViews/UpdateRenderTargets subreason attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
