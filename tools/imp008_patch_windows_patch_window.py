#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


patcher = Path("src/core/arm/nce/patcher.cpp")
replace_once(
    patcher,
    '''#include "core/arm/nce/windows_generated_context.h"\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_x18_exclusive.h"''',
    '''#include "core/arm/nce/windows_generated_context.h"\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_patch_code_metadata.h"\n#include "core/arm/nce/windows_x18_exclusive.h"''',
)
replace_once(
    patcher,
    '''    if (mode != PatchMode::Split) {\n        for (const Trampoline& rel : patch.m_trampolines) {\n            out_trampolines->insert({RebasePc(rel.module_offset), RebasePatch(rel.patch_offset)});\n        }\n    }\n\n    // Cortex-A57 seems to treat all exclusives as ordered, but newer processors do not.''',
    '''    if (mode != PatchMode::Split) {\n        for (const Trampoline& rel : patch.m_trampolines) {\n            out_trampolines->insert({RebasePc(rel.module_offset), RebasePatch(rel.patch_offset)});\n        }\n    }\n\n#if defined(_WIN32)\n    // Cross-thread breaks may arrive while generated patch helpers temporarily own guest-stack\n    // scratch frames/registers. Record the complete generated-code regions as tagged process\n    // metadata so the Windows host can defer architectural capture until execution returns to a\n    // real guest instruction. Tagged keys cannot collide with ordinary post-handler lookups.\n    if (mode == PatchMode::Split) {\n        WindowsPatchCodeMetadata::RegisterRange(*out_trampolines, GetInteger(load_base),\n                                                pre_patch_size);\n        WindowsPatchCodeMetadata::RegisterRange(\n            *out_trampolines, GetInteger(load_base) + pre_patch_size + image_size, patch_size);\n    } else {\n        WindowsPatchCodeMetadata::RegisterRange(*out_trampolines, RebasePatch(0), patch_size);\n    }\n#endif\n\n    // Cortex-A57 seems to treat all exclusives as ordered, but newer processors do not.''',
)

armnce = Path("src/core/arm/nce/arm_nce_windows.cpp")
replace_once(
    armnce,
    '''#include "core/arm/nce/windows_exception_context.h"\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_x18_fallback_runner.h"''',
    '''#include "core/arm/nce/windows_exception_context.h"\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_patch_code_metadata.h"\n#include "core/arm/nce/windows_x18_fallback_runner.h"''',
)
replace_once(
    armnce,
    '''struct BreakTransformState {\n    ArmNce* nce{};\n    bool transformed{};\n    bool host_window{};\n};''',
    '''struct BreakTransformState {\n    ArmNce* nce{};\n    bool transformed{};\n    bool host_window{};\n    bool patch_window{};\n};''',
)
replace_once(
    armnce,
    '''    if (state->nce->m_windows_break->IsHostStackPointer(context.Sp)) {\n        state->host_window = true;\n        return false;\n    }\n\n    state->host_window = false;\n    auto& guest = state->nce->m_guest_ctx;''',
    '''    if (state->nce->m_windows_break->IsHostStackPointer(context.Sp)) {\n        state->host_window = true;\n        return false;\n    }\n\n    state->host_window = false;\n    auto* const thread = state->nce->m_running_thread;\n    auto* const process = thread != nullptr ? thread->GetOwnerProcess() : nullptr;\n    if (process != nullptr && NCE::WindowsPatchCodeMetadata::Contains(\n                                  context.Pc, process->GetPostHandlers())) {\n        state->patch_window = true;\n        return false;\n    }\n\n    state->patch_window = false;\n    auto& guest = state->nce->m_guest_ctx;''',
)
replace_once(
    armnce,
    '''        if (state.transformed) {\n            // The target returns through RunThread and PhysicalCore::ExitContext owns the matching\n            // UnlockThread call, exactly as on the existing Linux NCE break path.\n            return;\n        }\n        if (!state.host_window) {\n            UnlockThreadParameters(params);\n            return;\n        }\n        std::this_thread::yield();''',
    '''        if (state.transformed) {\n            // The target returns through RunThread and PhysicalCore::ExitContext owns the matching\n            // UnlockThread call, exactly as on the existing Linux NCE break path.\n            return;\n        }\n        if (state.patch_window) {\n            // Unlike the host-stack RtlRestoreContext window, generated patch code may itself need\n            // to acquire NativeExecutionParameters::lock (notably the SVC lock prelude). Retaining\n            // the sender-owned lock here can deadlock the target. Resume unchanged, release the\n            // lock long enough for the generated helper to retire, then reacquire and retry.\n            UnlockThreadParameters(params);\n            std::this_thread::yield();\n            LockThreadParameters(params);\n            std::atomic_thread_fence(std::memory_order_acquire);\n            if (!params->is_running) {\n                UnlockThreadParameters(params);\n                return;\n            }\n            continue;\n        }\n        if (!state.host_window) {\n            UnlockThreadParameters(params);\n            return;\n        }\n        std::this_thread::yield();''',
)

cmake = Path("src/core/CMakeLists.txt")
replace_once(
    cmake,
    '''            arm/nce/windows_nce_transition.cpp\n            arm/nce/windows_nce_transition.h\n            arm/nce/windows_x18_exclusive.h''',
    '''            arm/nce/windows_nce_transition.cpp\n            arm/nce/windows_nce_transition.h\n            arm/nce/windows_patch_code_metadata.h\n            arm/nce/windows_x18_exclusive.h''',
)

print("IMP008A_WINDOWS_PATCH_WINDOW_FIX=PASS")
