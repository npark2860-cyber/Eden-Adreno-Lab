#!/usr/bin/env python3
# Add observation-only Stage H guest module range reporting and pre-register Stage K main range.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_h_module_mapping.py <eden-root>")

    root = Path(sys.argv[1])
    loader = root / "src/core/loader/deconstructed_rom_directory.cpp"
    if not loader.exists():
        raise RuntimeError("exact dc95 deconstructed_rom_directory.cpp not found")

    text = loader.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_waker_stage_k_profiler.h"\n',
        "Stage K main-range profiler include",
    )
    anchor = '''        next_load_addr = *tentative_next_load_addr;
        modules.insert_or_assign(load_addr, module);
        LOG_DEBUG(Loader, "loaded module {} @ {:#x}", module, load_addr);
'''
    replacement = '''        next_load_addr = *tentative_next_load_addr;
        modules.insert_or_assign(load_addr, module);
        LOG_DEBUG(Loader, "loaded module {} @ {:#x}", module, load_addr);
        if (Settings::values.x1_address_arbiter_attribution_log.GetValue()) {
            LOG_INFO(Loader,
                     "[X1-WAKERH] module={} base={:#x} end={:#x} size={:#x}",
                     module, load_addr, next_load_addr, next_load_addr - load_addr);
        }
        if (std::strcmp(module, "main") == 0) {
            Core::X1WakerStageKProfiler::Get().RegisterMainModuleRange(load_addr, next_load_addr);
        }
'''
    text = replace_once(text, anchor, replacement, "Stage H bounded module range report")
    loader.write_text(text, encoding="utf-8")

    final = loader.read_text(encoding="utf-8")
    required = (
        "[X1-WAKERH]",
        "module={} base={:#x} end={:#x} size={:#x}",
        "Settings::values.x1_address_arbiter_attribution_log.GetValue()",
        "modules.insert_or_assign(load_addr, module)",
        "next_load_addr - load_addr",
        "X1WakerStageKProfiler::Get().RegisterMainModuleRange",
        'std::strcmp(module, "main") == 0',
    )
    for marker in required:
        if marker not in final:
            raise RuntimeError(f"Stage H required marker missing: {marker}")

    if final.count("[X1-WAKERH]") != 1:
        raise RuntimeError("Stage H must add exactly one bounded module-range log site")
    if final.count("X1WakerStageKProfiler::Get().RegisterMainModuleRange") != 1:
        raise RuntimeError("Stage H must pre-register the Stage K main range exactly once")

    lowered = final.lower()
    for forbidden_value in ("0x85f12528", "0x85f12420", "0x85edea8c", "0x85edeb40", "0x80", "0x81"):
        if forbidden_value in lowered:
            raise RuntimeError(f"Stage H must not hardcode runtime observation {forbidden_value}")

    added = replacement[len(anchor):]
    forbidden = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "Yield", "QueueBuffer(", "swap_interval", "gpu_fence_behavior", "WaitForAddress(",
        "SignalToAddress(",
    )
    if any(token in added for token in forbidden):
        raise RuntimeError("behavior-changing token found in Stage H loader instrumentation")

    print("Transplanted exact dc95 X1 waker Stage H module-range mapping + Stage K main range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
