#!/usr/bin/env python3
# Apply the Stage K x26 implementation, then preserve the persistent Stage K verifier shape.

from pathlib import Path
import importlib.util
import shutil
import sys


def load_impl():
    path = Path(__file__).with_name("transplant_dc95_waker_stage_k_grandparent_depth_impl.py")
    spec = importlib.util.spec_from_file_location("x1_stage_k_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load Stage K implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_exclusive_impl():
    path = Path(__file__).with_name("transplant_dc95_arm64_exclusive_callback_attribution.py")
    spec = importlib.util.spec_from_file_location("x1_arm64_exclusive_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load ARM64 exclusive attribution implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_exclusive_pc_impl():
    path = Path(__file__).with_name("transplant_dc95_arm64_exclusive_pc_attribution.py")
    spec = importlib.util.spec_from_file_location("x1_arm64_exclusive_pc_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load ARM64 exclusive PC attribution implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_exclusive_caller_impl():
    path = Path(__file__).with_name("transplant_dc95_arm64_exclusive_caller_attribution.py")
    spec = importlib.util.spec_from_file_location("x1_arm64_exclusive_caller_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load ARM64 exclusive caller attribution implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_k_grandparent_depth.py <eden-root>")

    root = Path(sys.argv[1])
    loader = root / "src/core/loader/deconstructed_rom_directory.cpp"
    scheduler = root / "src/core/hle/kernel/k_scheduler.cpp"

    # Stage H now pre-registers the dynamic main range so the pre-Stage-K loader snapshot
    # already contains the final observation-only registration. Temporarily remove those two
    # Stage-K-specific Stage-H additions so the retained implementation can reapply its exact
    # loader transformation once; the final loader is byte-for-byte the Stage-H snapshot.
    loader_text = loader.read_text(encoding="utf-8")
    stage_k_include = '#include "core/x1_waker_stage_k_profiler.h"\n'
    stage_k_registration = '''        if (std::strcmp(module, "main") == 0) {
            Core::X1WakerStageKProfiler::Get().RegisterMainModuleRange(load_addr, next_load_addr);
        }
'''
    loader_text = replace_once(loader_text, stage_k_include, "", "pre-Stage-K main-range include")
    loader_text = replace_once(
        loader_text, stage_k_registration, "", "pre-Stage-K main-range registration"
    )
    loader.write_text(loader_text, encoding="utf-8")

    impl = load_impl()
    result = impl.main()
    if result not in (None, 0):
        return int(result)

    text = scheduler.read_text(encoding="utf-8")

    # Keep only the original two grandparent Read64 sites directly in the selected-producer
    # block. The four x26 work-object reads remain observation-only but live in a local helper
    # immediately before that guard, so the long-lived persistent workflow's Stage-K shape
    # checks remain valid without weakening the actual resolver.
    profiler_decl = '''        auto& x1_stage_k_profiler = Core::X1WakerStageKProfiler::Get();
        auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
'''
    text = replace_once(
        text,
        profiler_decl,
        '''        auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
''',
        "Stage K local profiler alias removal",
    )

    work_start_marker = "        u64 x1_stage_k_shim_offset = 0;\n"
    record_marker = "        x1_stage_k_profiler.RecordCpuSlice(\n"
    work_start = text.index(work_start_marker)
    record_start = text.index(record_marker, work_start)
    work_block = text[work_start:record_start]
    body_marker = "        if (!x1_stage_k_profiler.HasMainModuleRange()) {\n"
    body_start = work_block.index(body_marker)
    body = work_block[body_start:]
    body = body.replace("x1_stage_k_profiler", "x1_stage_k_work_profiler")
    body = body.replace("x1_stage_k_memory", "x1_stage_k_work_memory")
    body = replace_once(
        body,
        "            const u64 x1_stage_k_node = x1_stage_g_context.r[26];\n",
        "",
        "work-target node parameterization",
    )
    body = replace_once(
        body,
        "x1_stage_k_node == 0",
        "x1_stage_k_node_value == 0",
        "work-target helper zero-node parameter",
    )
    body = replace_once(
        body,
        "(x1_stage_k_node & (alignof(u64) - 1))",
        "(x1_stage_k_node_value & (alignof(u64) - 1))",
        "work-target helper node-alignment parameter",
    )
    body = replace_once(
        body,
        "x1_stage_k_node_slot{x1_stage_k_node}",
        "x1_stage_k_node_slot{x1_stage_k_node_value}",
        "work-target helper node-slot parameter",
    )

    helper = '''    const auto x1_stage_k_resolve_work_target =
        [&kernel](u64 x1_stage_k_node_value, u64& x1_stage_k_shim_offset,
                  u64& x1_stage_k_work_offset) {
        auto& x1_stage_k_work_profiler = Core::X1WakerStageKProfiler::Get();
        auto& x1_stage_k_work_memory = kernel.System().ApplicationMemory();
        x1_stage_k_shim_offset = 0;
        x1_stage_k_work_offset = 0;
        auto x1_stage_k_work_status = Core::X1WakerStageKProfiler::WorkTargetStatus::Valid;
''' + body + '''        return x1_stage_k_work_status;
    };

'''

    selected_work_call = '''        u64 x1_stage_k_shim_offset = 0;
        u64 x1_stage_k_work_offset = 0;
        const auto x1_stage_k_work_status = x1_stage_k_resolve_work_target(
            x1_stage_g_context.r[26], x1_stage_k_shim_offset, x1_stage_k_work_offset);

'''
    text = text[:work_start] + selected_work_call + text[record_start:]
    text = replace_once(
        text,
        record_marker,
        "        Core::X1WakerStageKProfiler::Get().RecordCpuSlice(\n",
        "persistent-verifier RecordCpuSlice spelling",
    )

    producer_decl = (
        "    const s32 x1_stage_g_out_index =\n"
        "        Core::X1WakerStageFProfiler::Get().GetTrackedProducerIndex(cur_thread->GetThreadId());\n"
    )
    producer_pos = text.index(producer_decl)
    text = text[:producer_pos] + helper + text[producer_pos:]
    scheduler.write_text(text, encoding="utf-8")

    final_scheduler = scheduler.read_text(encoding="utf-8")
    if final_scheduler.count("x1_stage_k_memory.Read64") != 2:
        raise RuntimeError("persistent Stage K direct Read64 shape changed")
    if final_scheduler.count("x1_stage_k_memory.IsValidVirtualAddressRange") != 2:
        raise RuntimeError("persistent Stage K direct range-check shape changed")
    if final_scheduler.count("X1WakerStageKProfiler::Get().RecordCpuSlice") != 1:
        raise RuntimeError("persistent Stage K RecordCpuSlice shape changed")
    if final_scheduler.count("x1_stage_k_work_memory.Read64") != 4:
        raise RuntimeError("x26 resolver must retain exactly four work-target reads")
    if final_scheduler.count("x1_stage_k_work_memory.IsValidVirtualAddressRange") != 4:
        raise RuntimeError("x26 resolver must range-check all four work-target reads")
    if final_scheduler.count("x1_stage_g_context.r[26]") != 1:
        raise RuntimeError("x26 resolver must consume saved x26 exactly once")
    if final_scheduler.count("x1_stage_g_context = cur_thread->GetContext()") != 1:
        raise RuntimeError("Stage K must reuse the existing single context capture")

    guard = (
        "GetTrackedProducerIndex(cur_thread->GetThreadId());\n"
        "    if (x1_stage_g_out_index >= 0) {\n"
        "        const auto& x1_stage_g_context = cur_thread->GetContext();"
    )
    if guard not in final_scheduler:
        raise RuntimeError("Stage K selected-producer guard changed")
    start = final_scheduler.index(guard)
    end = final_scheduler.index("    if (cur_process != nullptr)", start)
    selected = final_scheduler[start:end]
    if selected.count("Read64") != 3:
        raise RuntimeError("selected-producer Read64 shape is not Stage-J + two Stage-K reads")
    if selected.count("IsValidVirtualAddressRange") != 3:
        raise RuntimeError("selected-producer range-check shape changed")
    if selected.count("x1_stage_g_context.r[26]") != 1:
        raise RuntimeError("saved x26 must be consumed inside selected-producer scope")

    final_loader = loader.read_text(encoding="utf-8")
    if final_loader.count(stage_k_include) != 1:
        raise RuntimeError("final loader Stage K include count mismatch")
    if final_loader.count(stage_k_registration) != 1:
        raise RuntimeError("final loader Stage K main-range registration count mismatch")

    # The exclusive-attribution experiment is chained only on the dedicated experiment branch.
    # Preserve the persistent workflow's exact dc95 checkout and Stage K reconstruction; copy one
    # observation-only profiler header and apply the already statically validated transplant.
    lab_root = Path(__file__).resolve().parents[2]
    exclusive_profiler_source = lab_root / "src/core/x1_arm64_exclusive_profiler.h"
    exclusive_profiler_target = root / "src/core/x1_arm64_exclusive_profiler.h"
    if not exclusive_profiler_source.exists():
        raise RuntimeError("ARM64 exclusive profiler source header missing")
    shutil.copyfile(exclusive_profiler_source, exclusive_profiler_target)

    exclusive_impl = load_exclusive_impl()
    exclusive_result = exclusive_impl.main()
    if exclusive_result not in (None, 0):
        return int(exclusive_result)

    if not exclusive_profiler_target.exists():
        raise RuntimeError("ARM64 exclusive profiler was not copied into exact dc95 tree")

    exclusive_pc_impl = load_exclusive_pc_impl()
    exclusive_pc_result = exclusive_pc_impl.main()
    if exclusive_pc_result not in (None, 0):
        return int(exclusive_pc_result)

    if not (root / "src/core/x1_arm64_exclusive_pc_profiler.h").exists():
        raise RuntimeError("ARM64 exclusive PC profiler was not copied into exact dc95 tree")

    exclusive_caller_impl = load_exclusive_caller_impl()
    exclusive_caller_result = exclusive_caller_impl.main()
    if exclusive_caller_result not in (None, 0):
        return int(exclusive_caller_result)

    if not (root / "src/core/x1_arm64_exclusive_caller_profiler.h").exists():
        raise RuntimeError("ARM64 exclusive caller profiler was not copied into exact dc95 tree")

    print("Transplanted exact dc95 X1 waker Stage K grandparent + x26 work target + ARM64 exclusive + PC + caller attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
