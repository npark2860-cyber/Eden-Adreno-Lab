#!/usr/bin/env python3
'''Add observation-only frame-cadence attribution hooks to exact dc95.

Expected order:
  - recreate the existing payload/uniform-cache A/B diagnostic chain
  - this pass

This pass does NOT change timing, waits, swap intervals, fences, queue policy, render-pass behavior,
or renderer behavior. It only logs host steady-clock timestamps at three points already traversed by
the existing frame path:

  1. guest BufferQueueProducer::QueueBuffer completion
  2. Nvnflinger HardwareComposer buffer acquisition
  3. each active HardwareComposer composition tick plus WaitForComposite duration

The intent is to distinguish:
  - producer cadence (new guest buffers already arrive every ~50 ms), from
  - compositor cadence (guest queues faster but acquisition/presentation becomes every third 60 Hz tick), from
  - a blocking composite hand-off (WaitForComposite itself consumes the missing interval).

Logging is gated by the already-existing x1_present_frame_log diagnostic setting.
'''

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_frame_cadence_attribution.py <eden-root>")

    root = Path(sys.argv[1])

    settings = (root / "src/common/settings.h").read_text(encoding="utf-8")
    for marker in ("x1_present_frame_log", "x1_ab_disable_adaptive_uniform_fast_stream"):
        if marker not in settings:
            raise RuntimeError(f"required parent diagnostic marker missing: {marker}")

    producer = root / "src/core/hle/service/nvnflinger/buffer_queue_producer.cpp"
    text = producer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "common/assert.h"\n',
        '#include <chrono>\n#include <cstdint>\n\n#include "common/assert.h"\n',
        "producer cadence includes",
    )

    notify_anchor = '''    item.graphic_buffer.reset();\n    item.slot = BufferItem::INVALID_BUFFER_SLOT;\n\n    if (listener_available) {\n'''
    notify_replacement = '''    if (Settings::values.x1_present_frame_log.GetValue()) {\n        const auto x1_queue_host_us = std::chrono::duration_cast<std::chrono::microseconds>(\n            std::chrono::steady_clock::now().time_since_epoch()).count();\n        LOG_INFO(Service_Nvnflinger,\n                 "[X1-CADENCE][QUEUE] hostUs={} core=0x{:x} frame={} slot={} swap={}",\n                 x1_queue_host_us, reinterpret_cast<std::uintptr_t>(core.get()), item.frame_number,\n                 slot, item.swap_interval);\n    }\n\n    item.graphic_buffer.reset();\n    item.slot = BufferItem::INVALID_BUFFER_SLOT;\n\n    if (listener_available) {\n'''
    text = replace_once(text, notify_anchor, notify_replacement, "producer QueueBuffer cadence log")
    producer.write_text(text, encoding="utf-8")

    composer = root / "src/core/hle/service/nvnflinger/hardware_composer.cpp"
    text = composer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include <optional>\n\n#include <boost/container/small_vector.hpp>\n',
        '#include <chrono>\n#include <optional>\n\n#include <boost/container/small_vector.hpp>\n\n#include "common/logging.h"\n#include "common/settings.h"\n',
        "composer cadence includes",
    )

    wait_anchor = '''    // Set default speed limit to 100%.\n    *out_speed_scale = 1.0f;\n\n    nvdisp.WaitForComposite();\n    this->ReleaseFramebuffersLocked(display);\n'''
    wait_replacement = '''    // Set default speed limit to 100%.\n    *out_speed_scale = 1.0f;\n\n    const auto x1_tick_start = std::chrono::steady_clock::now();\n    nvdisp.WaitForComposite();\n    const auto x1_after_wait = std::chrono::steady_clock::now();\n    const auto x1_wait_us = std::chrono::duration_cast<std::chrono::microseconds>(\n        x1_after_wait - x1_tick_start).count();\n    u32 x1_main_acquired = 0;\n    u32 x1_overlay_acquired = 0;\n\n    this->ReleaseFramebuffersLocked(display);\n'''
    text = replace_once(text, wait_anchor, wait_replacement, "WaitForComposite timing")

    item_anchor = '''        const auto& buffer = m_framebuffers[consumer_id];\n        const auto& item = buffer.item;\n        const auto& igbp_buffer = *item.graphic_buffer;\n\n        if (layer->visible) {\n'''
    item_replacement = '''        const auto& buffer = m_framebuffers[consumer_id];\n        const auto& item = buffer.item;\n        const auto& igbp_buffer = *item.graphic_buffer;\n\n        if (result == CacheStatus::BufferAcquired) {\n            if (layer->is_overlay) {\n                ++x1_overlay_acquired;\n            } else {\n                ++x1_main_acquired;\n            }\n            if (Settings::values.x1_present_frame_log.GetValue()) {\n                const auto x1_acquire_host_us =\n                    std::chrono::duration_cast<std::chrono::microseconds>(\n                        std::chrono::steady_clock::now().time_since_epoch()).count();\n                LOG_INFO(Service_Nvnflinger,\n                         "[X1-CADENCE][ACQUIRE] hostUs={} tick={} consumer={} overlay={} frame={} swap={}",\n                         x1_acquire_host_us, m_frame_number, consumer_id, layer->is_overlay,\n                         item.frame_number, item.swap_interval);\n            }\n        }\n\n        if (layer->visible) {\n'''
    text = replace_once(text, item_anchor, item_replacement, "composer acquire cadence log")

    end_anchor = '''    // Advance by 1 frame (60 FPS compositing)\n    m_frame_number += 1;\n\n    return 1;\n'''
    end_replacement = '''    if (Settings::values.x1_present_frame_log.GetValue()) {\n        const auto x1_tick_end = std::chrono::steady_clock::now();\n        const auto x1_tick_host_us = std::chrono::duration_cast<std::chrono::microseconds>(\n            x1_tick_end.time_since_epoch()).count();\n        const auto x1_tick_us = std::chrono::duration_cast<std::chrono::microseconds>(\n            x1_tick_end - x1_tick_start).count();\n        LOG_INFO(Service_Nvnflinger,\n                 "[X1-CADENCE][VI] hostUs={} tick={} mainNew={} overlayNew={} waitUs={} workUs={}",\n                 x1_tick_host_us, m_frame_number, x1_main_acquired, x1_overlay_acquired,\n                 x1_wait_us, x1_tick_us);\n    }\n\n    // Advance by 1 frame (60 FPS compositing)\n    m_frame_number += 1;\n\n    return 1;\n'''
    text = replace_once(text, end_anchor, end_replacement, "composer tick cadence log")
    composer.write_text(text, encoding="utf-8")

    producer_final = producer.read_text(encoding="utf-8")
    composer_final = composer.read_text(encoding="utf-8")
    for required in ("[X1-CADENCE][QUEUE]", "listener_available->OnFrameAvailable(item)", "return Status::NoError;"):
        if required not in producer_final:
            raise RuntimeError(f"producer cadence invariant missing: {required}")
    for required in (
        "[X1-CADENCE][ACQUIRE]",
        "[X1-CADENCE][VI]",
        "nvdisp.WaitForComposite();",
        "nvdisp.Composite(composition_stack);",
        "m_frame_number += 1;",
        "return 1;",
    ):
        if required not in composer_final:
            raise RuntimeError(f"composer cadence invariant missing: {required}")

    print("Applied X1 exact-dc95 observation-only frame cadence attribution hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
