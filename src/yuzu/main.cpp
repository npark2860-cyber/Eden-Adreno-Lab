// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <cstring>

#include <QApplication>
#include "startup_checks.h"

#if YUZU_ROOM
#include <cstring>
#include "dedicated_room/yuzu_room.h"
#endif
#ifdef __unix__
#include "qt_common/gui_settings.h"
#endif

#ifndef _WIN32
#include <sys/resource.h>
#endif

#if defined(__APPLE__)
#include <climits>
#include <cstdlib>
#include <cstring>
#endif

#include "main_window.h"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cwchar>

#include <QScreen>

namespace {

constexpr const char* V63WatchdogArgument = "--nce-v63-watchdog";

HANDLE OpenWindowsNceV63Log() noexcept {
    char temp_path[MAX_PATH + 1]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH) {
        return INVALID_HANDLE_VALUE;
    }

    char path[MAX_PATH + 64]{};
    const int path_length =
        std::snprintf(path, sizeof(path), "%s%s", temp_path, "eden_nce_v63_exit_watchdog.log");
    if (path_length <= 0 || static_cast<size_t>(path_length) >= sizeof(path)) {
        return INVALID_HANDLE_VALUE;
    }

    return CreateFileA(path, FILE_APPEND_DATA,
                       FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                       OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
}

void WriteWindowsNceV63Line(const char* tag, unsigned long parent_pid, unsigned long child_pid,
                            unsigned long wait_result, unsigned long exit_code,
                            unsigned long error_code) noexcept {
    HANDLE file = OpenWindowsNceV63Log();
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    char line[512]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "%s tick=%llu parent_pid=%lu child_pid=%lu wait=0x%08lX exit=0x%08lX "
        "error=%lu base=fb3d278617f69dd00671fbf3e5d56bdc1366ec73\r\n",
        tag, static_cast<unsigned long long>(GetTickCount64()), parent_pid, child_pid, wait_result,
        exit_code, error_code);
    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
}

constexpr DWORD D2FastFailExceptionCode = 0xC0000409ul;

struct D2FastFailModuleInfo {
    u64 base{};
    u64 size{};
    u64 resolved_address{};
    bool pac_stripped{};
    u64 query_base{};
    u64 query_allocation_base{};
    u64 query_region_size{};
    DWORD query_state{};
    DWORD query_protect{};
    DWORD query_type{};
    DWORD query_error{};
    char name[MAX_PATH]{"<unknown>"};
};

D2FastFailModuleInfo ResolveD2FastFailModule(DWORD process_id, u64 address) noexcept {
    D2FastFailModuleInfo result{};
    if (address == 0) {
        return result;
    }

    // Windows ARM64 may store PAC-signed return addresses in stack frame records.
    // Try the raw address first, then a canonical user-mode candidate with the
    // upper 16 PAC bits removed. This is diagnostic-only and does not alter state.
    const u64 candidates[2] = {address, address & 0x0000FFFFFFFFFFFFULL};

    HANDLE snapshot =
        CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, process_id);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return result;
    }

    for (size_t candidate_index = 0; candidate_index < 2 && result.base == 0;
         ++candidate_index) {
        const u64 candidate = candidates[candidate_index];
        if (candidate == 0 || (candidate_index == 1 && candidate == candidates[0])) {
            continue;
        }

        MODULEENTRY32W module{};
        module.dwSize = sizeof(module);
        if (Module32FirstW(snapshot, &module) != FALSE) {
            do {
                const u64 base = reinterpret_cast<u64>(module.modBaseAddr);
                const u64 end = base + static_cast<u64>(module.modBaseSize);
                if (candidate >= base && candidate < end) {
                    result.base = base;
                    result.size = static_cast<u64>(module.modBaseSize);
                    result.resolved_address = candidate;
                    result.pac_stripped = candidate_index == 1;
                    const int converted =
                        WideCharToMultiByte(CP_UTF8, 0, module.szModule, -1, result.name,
                                            static_cast<int>(sizeof(result.name)), nullptr, nullptr);
                    if (converted <= 0) {
                        std::snprintf(result.name, sizeof(result.name), "<module-name-error>");
                    }
                    break;
                }
            } while (Module32NextW(snapshot, &module) != FALSE);
        }
    }

    CloseHandle(snapshot);

    // If Toolhelp cannot associate a PAC-stripped return address with a loaded module,
    // classify the remote virtual-memory region directly. This distinguishes PE image
    // code from MEM_PRIVATE/JIT/generated code without executing anything in the target.
    const u64 query_address =
        result.resolved_address != 0 ? result.resolved_address : candidates[1];
    if (query_address != 0) {
        HANDLE process =
            OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, process_id);
        if (process != nullptr) {
            MEMORY_BASIC_INFORMATION mbi{};
            if (VirtualQueryEx(process,
                               reinterpret_cast<const void*>(
                                   static_cast<std::uintptr_t>(query_address)),
                               &mbi, sizeof(mbi)) != 0) {
                result.query_base = reinterpret_cast<u64>(mbi.BaseAddress);
                result.query_allocation_base = reinterpret_cast<u64>(mbi.AllocationBase);
                result.query_region_size = static_cast<u64>(mbi.RegionSize);
                result.query_state = mbi.State;
                result.query_protect = mbi.Protect;
                result.query_type = mbi.Type;
                if (result.resolved_address == 0) {
                    result.resolved_address = query_address;
                    result.pac_stripped = query_address != address;
                }
            } else {
                result.query_error = GetLastError();
            }
            CloseHandle(process);
        } else {
            result.query_error = GetLastError();
        }
    }

    return result;
}

void WriteWindowsNceD2FastFailLine(
    DWORD parent_pid, DWORD child_pid, DWORD thread_id, const EXCEPTION_DEBUG_INFO& info,
    const CONTEXT* context, u64 stack_base, u64 stack_limit, u32 instruction,
    bool instruction_ok, u32 instruction_minus4, bool instruction_minus4_ok,
    u32 instruction_plus4, bool instruction_plus4_ok, u64 frame_prev, u64 frame_lr,
    u64 frame2_prev, u64 frame2_lr, u32 frame_lr_instruction_minus4,
    bool frame_lr_instruction_minus4_ok, u32 frame_lr_instruction,
    bool frame_lr_instruction_ok, u32 frame_lr_instruction_plus4,
    bool frame_lr_instruction_plus4_ok, const D2FastFailModuleInfo& pc_module,
    const D2FastFailModuleInfo& lr_module, const D2FastFailModuleInfo& frame_lr_module,
    const D2FastFailModuleInfo& frame2_lr_module, DWORD context_error,
    DWORD memory_error) noexcept {
    HANDLE file = OpenWindowsNceV63Log();
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    const auto& record = info.ExceptionRecord;
    const u64 info0 =
        record.NumberParameters > 0 ? static_cast<u64>(record.ExceptionInformation[0]) : 0;
    const u64 info1 =
        record.NumberParameters > 1 ? static_cast<u64>(record.ExceptionInformation[1]) : 0;
    const u64 info2 =
        record.NumberParameters > 2 ? static_cast<u64>(record.ExceptionInformation[2]) : 0;
    const u64 info3 =
        record.NumberParameters > 3 ? static_cast<u64>(record.ExceptionInformation[3]) : 0;

    const u64 pc = context != nullptr ? static_cast<u64>(context->Pc) : 0;
    const u64 sp = context != nullptr ? static_cast<u64>(context->Sp) : 0;
    const u64 lr = context != nullptr ? static_cast<u64>(context->X[30]) : 0;
    const u64 fp = context != nullptr ? static_cast<u64>(context->X[29]) : 0;
    const u64 x18 = context != nullptr ? static_cast<u64>(context->X[18]) : 0;
    const u64 x0 = context != nullptr ? static_cast<u64>(context->X[0]) : 0;
    const u64 x1 = context != nullptr ? static_cast<u64>(context->X[1]) : 0;
    const u64 x2 = context != nullptr ? static_cast<u64>(context->X[2]) : 0;
    const u64 x3 = context != nullptr ? static_cast<u64>(context->X[3]) : 0;
    const u64 x4 = context != nullptr ? static_cast<u64>(context->X[4]) : 0;
    const u64 x5 = context != nullptr ? static_cast<u64>(context->X[5]) : 0;
    const u64 x6 = context != nullptr ? static_cast<u64>(context->X[6]) : 0;
    const u64 x7 = context != nullptr ? static_cast<u64>(context->X[7]) : 0;
    const u64 context_flags =
        context != nullptr ? static_cast<u64>(context->ContextFlags) : 0;
    const u64 cpsr = context != nullptr ? static_cast<u64>(context->Cpsr) : 0;

    const u64 pc_rva =
        pc_module.base != 0 && pc_module.resolved_address >= pc_module.base
            ? pc_module.resolved_address - pc_module.base
            : 0;
    const u64 lr_rva =
        lr_module.base != 0 && lr_module.resolved_address >= lr_module.base
            ? lr_module.resolved_address - lr_module.base
            : 0;
    const u64 frame_lr_rva =
        frame_lr_module.base != 0 && frame_lr_module.resolved_address >= frame_lr_module.base
            ? frame_lr_module.resolved_address - frame_lr_module.base
            : 0;
    const u64 frame_lr_vq_rva =
        frame_lr_module.query_allocation_base != 0 &&
                frame_lr_module.resolved_address >= frame_lr_module.query_allocation_base
            ? frame_lr_module.resolved_address - frame_lr_module.query_allocation_base
            : 0;
    const u64 frame2_lr_rva =
        frame2_lr_module.base != 0 &&
                frame2_lr_module.resolved_address >= frame2_lr_module.base
            ? frame2_lr_module.resolved_address - frame2_lr_module.base
            : 0;
    const u64 frame2_lr_vq_rva =
        frame2_lr_module.query_allocation_base != 0 &&
                frame2_lr_module.resolved_address >= frame2_lr_module.query_allocation_base
            ? frame2_lr_module.resolved_address - frame2_lr_module.query_allocation_base
            : 0;

    char line[8192]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "NCE_D2_FASTFAIL_DEBUG tick=%llu parent_pid=%lu child_pid=%lu thread_id=%lu "
        "first_chance=%lu code=0x%08lX flags=0x%08lX address=0x%016llX params=%lu "
        "info0=0x%016llX info1=0x%016llX info2=0x%016llX info3=0x%016llX "
        "pc=0x%016llX sp=0x%016llX lr=0x%016llX fp=0x%016llX x18=0x%016llX "
        "x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX "
        "x4=0x%016llX x5=0x%016llX x6=0x%016llX x7=0x%016llX "
        "stack_base=0x%016llX stack_limit=0x%016llX "
        "instruction_minus4=0x%08X instruction_minus4_ok=%u "
        "instruction=0x%08X instruction_ok=%u "
        "instruction_plus4=0x%08X instruction_plus4_ok=%u "
        "frame_prev=0x%016llX frame_lr=0x%016llX "
        "frame2_prev=0x%016llX frame2_lr=0x%016llX "
        "frame_lr_instruction_minus4=0x%08X frame_lr_instruction_minus4_ok=%u "
        "frame_lr_instruction=0x%08X frame_lr_instruction_ok=%u "
        "frame_lr_instruction_plus4=0x%08X frame_lr_instruction_plus4_ok=%u "
        "pc_module=%s pc_module_base=0x%016llX pc_resolved=0x%016llX pc_pac_stripped=%u pc_rva=0x%llX "
        "lr_module=%s lr_module_base=0x%016llX lr_resolved=0x%016llX lr_pac_stripped=%u lr_rva=0x%llX "
        "frame_lr_module=%s frame_lr_module_base=0x%016llX frame_lr_resolved=0x%016llX frame_lr_pac_stripped=%u frame_lr_rva=0x%llX "
        "frame_lr_vq_base=0x%016llX frame_lr_vq_alloc=0x%016llX frame_lr_vq_size=0x%llX "
        "frame_lr_vq_state=0x%08lX frame_lr_vq_protect=0x%08lX frame_lr_vq_type=0x%08lX frame_lr_vq_error=%lu frame_lr_vq_rva=0x%llX "
        "frame2_lr_module=%s frame2_lr_module_base=0x%016llX frame2_lr_resolved=0x%016llX frame2_lr_pac_stripped=%u frame2_lr_rva=0x%llX "
        "frame2_lr_vq_base=0x%016llX frame2_lr_vq_alloc=0x%016llX frame2_lr_vq_size=0x%llX "
        "frame2_lr_vq_state=0x%08lX frame2_lr_vq_protect=0x%08lX frame2_lr_vq_type=0x%08lX frame2_lr_vq_error=%lu frame2_lr_vq_rva=0x%llX "
        "context_flags=0x%016llX cpsr=0x%016llX context_error=%lu memory_error=%lu "
        "base=811afc84ac0bc00285b24ef786c8ad92b074009d\r\n",
        static_cast<unsigned long long>(GetTickCount64()), parent_pid, child_pid, thread_id,
        info.dwFirstChance, record.ExceptionCode, record.ExceptionFlags,
        static_cast<unsigned long long>(
            reinterpret_cast<std::uintptr_t>(record.ExceptionAddress)),
        record.NumberParameters, static_cast<unsigned long long>(info0),
        static_cast<unsigned long long>(info1), static_cast<unsigned long long>(info2),
        static_cast<unsigned long long>(info3), static_cast<unsigned long long>(pc),
        static_cast<unsigned long long>(sp), static_cast<unsigned long long>(lr),
        static_cast<unsigned long long>(fp), static_cast<unsigned long long>(x18),
        static_cast<unsigned long long>(x0), static_cast<unsigned long long>(x1),
        static_cast<unsigned long long>(x2), static_cast<unsigned long long>(x3),
        static_cast<unsigned long long>(x4), static_cast<unsigned long long>(x5),
        static_cast<unsigned long long>(x6), static_cast<unsigned long long>(x7),
        static_cast<unsigned long long>(stack_base),
        static_cast<unsigned long long>(stack_limit), instruction_minus4,
        instruction_minus4_ok ? 1u : 0u, instruction, instruction_ok ? 1u : 0u,
        instruction_plus4, instruction_plus4_ok ? 1u : 0u,
        static_cast<unsigned long long>(frame_prev),
        static_cast<unsigned long long>(frame_lr),
        static_cast<unsigned long long>(frame2_prev),
        static_cast<unsigned long long>(frame2_lr),
        frame_lr_instruction_minus4, frame_lr_instruction_minus4_ok ? 1u : 0u,
        frame_lr_instruction, frame_lr_instruction_ok ? 1u : 0u,
        frame_lr_instruction_plus4, frame_lr_instruction_plus4_ok ? 1u : 0u,
        pc_module.name,
        static_cast<unsigned long long>(pc_module.base),
        static_cast<unsigned long long>(pc_module.resolved_address),
        pc_module.pac_stripped ? 1u : 0u,
        static_cast<unsigned long long>(pc_rva), lr_module.name,
        static_cast<unsigned long long>(lr_module.base),
        static_cast<unsigned long long>(lr_module.resolved_address),
        lr_module.pac_stripped ? 1u : 0u,
        static_cast<unsigned long long>(lr_rva), frame_lr_module.name,
        static_cast<unsigned long long>(frame_lr_module.base),
        static_cast<unsigned long long>(frame_lr_module.resolved_address),
        frame_lr_module.pac_stripped ? 1u : 0u,
        static_cast<unsigned long long>(frame_lr_rva),
        static_cast<unsigned long long>(frame_lr_module.query_base),
        static_cast<unsigned long long>(frame_lr_module.query_allocation_base),
        static_cast<unsigned long long>(frame_lr_module.query_region_size),
        frame_lr_module.query_state, frame_lr_module.query_protect,
        frame_lr_module.query_type, frame_lr_module.query_error,
        static_cast<unsigned long long>(frame_lr_vq_rva),
        frame2_lr_module.name,
        static_cast<unsigned long long>(frame2_lr_module.base),
        static_cast<unsigned long long>(frame2_lr_module.resolved_address),
        frame2_lr_module.pac_stripped ? 1u : 0u,
        static_cast<unsigned long long>(frame2_lr_rva),
        static_cast<unsigned long long>(frame2_lr_module.query_base),
        static_cast<unsigned long long>(frame2_lr_module.query_allocation_base),
        static_cast<unsigned long long>(frame2_lr_module.query_region_size),
        frame2_lr_module.query_state, frame2_lr_module.query_protect,
        frame2_lr_module.query_type, frame2_lr_module.query_error,
        static_cast<unsigned long long>(frame2_lr_vq_rva),
        static_cast<unsigned long long>(context_flags),
        static_cast<unsigned long long>(cpsr), context_error, memory_error);

    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
}


void WriteWindowsNceD2BreakpointDebugLine(
    DWORD parent_pid, DWORD child_pid, DWORD thread_id, u64 sequence, bool consumed_as_attach,
    const EXCEPTION_DEBUG_INFO& info, const CONTEXT* context, HANDLE read_handle,
    DWORD context_error) noexcept {
    HANDLE file = OpenWindowsNceV63Log();
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    const auto& record = info.ExceptionRecord;
    const u64 info0 =
        record.NumberParameters > 0 ? static_cast<u64>(record.ExceptionInformation[0]) : 0;
    const u64 info1 =
        record.NumberParameters > 1 ? static_cast<u64>(record.ExceptionInformation[1]) : 0;

    const u64 pc = context != nullptr ? static_cast<u64>(context->Pc) : 0;
    const u64 sp = context != nullptr ? static_cast<u64>(context->Sp) : 0;
    const u64 lr = context != nullptr ? static_cast<u64>(context->X[30]) : 0;
    const u64 x18 = context != nullptr ? static_cast<u64>(context->X[18]) : 0;
    const u64 context_flags =
        context != nullptr ? static_cast<u64>(context->ContextFlags) : 0;
    const u64 cpsr = context != nullptr ? static_cast<u64>(context->Cpsr) : 0;
    const u64 exception_address =
        reinterpret_cast<u64>(record.ExceptionAddress);

    u32 instruction_minus4 = 0;
    u32 instruction = 0;
    u32 instruction_exception = 0;
    bool instruction_minus4_ok = false;
    bool instruction_ok = false;
    bool instruction_exception_ok = false;
    DWORD memory_error = 0;

    if (read_handle != nullptr && context != nullptr) {
        auto read_instruction = [&](u64 address, u32& value) {
            SIZE_T bytes{};
            if (address == 0) {
                return false;
            }
            if (ReadProcessMemory(
                    read_handle,
                    reinterpret_cast<const void*>(static_cast<std::uintptr_t>(address)),
                    &value, sizeof(value), &bytes) != FALSE &&
                bytes == sizeof(value)) {
                return true;
            }
            if (memory_error == 0) {
                memory_error = GetLastError();
            }
            return false;
        };

        instruction_ok = read_instruction(pc, instruction);
        instruction_minus4_ok =
            pc >= sizeof(u32) && read_instruction(pc - sizeof(u32), instruction_minus4);
        instruction_exception_ok =
            read_instruction(exception_address, instruction_exception);
    }

    const auto pc_module = ResolveD2FastFailModule(parent_pid, pc);
    const auto lr_module = ResolveD2FastFailModule(parent_pid, lr);
    const auto exception_module = ResolveD2FastFailModule(parent_pid, exception_address);

    const u64 pc_rva =
        pc_module.base != 0 && pc_module.resolved_address >= pc_module.base
            ? pc_module.resolved_address - pc_module.base
            : 0;
    const u64 lr_rva =
        lr_module.base != 0 && lr_module.resolved_address >= lr_module.base
            ? lr_module.resolved_address - lr_module.base
            : 0;
    const u64 exception_rva =
        exception_module.base != 0 && exception_module.resolved_address >= exception_module.base
            ? exception_module.resolved_address - exception_module.base
            : 0;

    char line[4096]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "NCE_D2_BREAKPOINT_DEBUG_EVENT seq=%llu consumed_as_attach=%u "
        "parent_pid=%lu child_pid=%lu thread_id=%lu first_chance=%lu "
        "flags=0x%08lX address=0x%016llX params=%lu info0=0x%016llX info1=0x%016llX "
        "pc=0x%016llX sp=0x%016llX lr=0x%016llX x18=0x%016llX "
        "instruction_minus4=0x%08X instruction_minus4_ok=%u "
        "instruction=0x%08X instruction_ok=%u "
        "instruction_exception=0x%08X instruction_exception_ok=%u "
        "pc_module=%s pc_module_base=0x%016llX pc_rva=0x%llX "
        "lr_module=%s lr_module_base=0x%016llX lr_rva=0x%llX "
        "exception_module=%s exception_module_base=0x%016llX exception_rva=0x%llX "
        "context_flags=0x%016llX cpsr=0x%016llX "
        "bcr0=0x%08llX bvr0=0x%016llX bcr1=0x%08llX bvr1=0x%016llX "
        "bcr2=0x%08llX bvr2=0x%016llX bcr3=0x%08llX bvr3=0x%016llX "
        "bcr4=0x%08llX bvr4=0x%016llX bcr5=0x%08llX bvr5=0x%016llX "
        "bcr6=0x%08llX bvr6=0x%016llX bcr7=0x%08llX bvr7=0x%016llX "
        "context_error=%lu memory_error=%lu base=2f0d41b173b4f9ae0d4e0b96cb61402c9ea5cd0e\r\n",
        static_cast<unsigned long long>(sequence), consumed_as_attach ? 1u : 0u,
        parent_pid, child_pid, thread_id, info.dwFirstChance, record.ExceptionFlags,
        static_cast<unsigned long long>(exception_address), record.NumberParameters,
        static_cast<unsigned long long>(info0), static_cast<unsigned long long>(info1),
        static_cast<unsigned long long>(pc), static_cast<unsigned long long>(sp),
        static_cast<unsigned long long>(lr), static_cast<unsigned long long>(x18),
        instruction_minus4, instruction_minus4_ok ? 1u : 0u, instruction,
        instruction_ok ? 1u : 0u, instruction_exception,
        instruction_exception_ok ? 1u : 0u, pc_module.name,
        static_cast<unsigned long long>(pc_module.base),
        static_cast<unsigned long long>(pc_rva), lr_module.name,
        static_cast<unsigned long long>(lr_module.base),
        static_cast<unsigned long long>(lr_rva), exception_module.name,
        static_cast<unsigned long long>(exception_module.base),
        static_cast<unsigned long long>(exception_rva),
        static_cast<unsigned long long>(context_flags),
        static_cast<unsigned long long>(cpsr),
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[0]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[0]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[1]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[1]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[2]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[2]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[3]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[3]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[4]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[4]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[5]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[5]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[6]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[6]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bcr[7]) : 0ULL,
        context != nullptr ? static_cast<unsigned long long>(context->Bvr[7]) : 0ULL,
        context_error, memory_error);

    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
}

int RunWindowsNceV63Watchdog(int argc, char* argv[]) noexcept {
    if (argc != 4) {
        return 201;
    }

    char* handle_end{};
    const auto inherited_handle_value = _strtoui64(argv[2], &handle_end, 10);
    if (handle_end == argv[2] || inherited_handle_value == 0) {
        return 202;
    }

    char* pid_end{};
    const unsigned long parent_pid = std::strtoul(argv[3], &pid_end, 10);
    if (pid_end == argv[3] || parent_pid == 0) {
        return 203;
    }

    HANDLE parent_handle =
        reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(inherited_handle_value));
    const unsigned long child_pid = static_cast<unsigned long>(GetCurrentProcessId());
    WriteWindowsNceV63Line("V63_WATCHDOG_READY", parent_pid, child_pid, 0xFFFFFFFFul,
                           STILL_ACTIVE, 0);

    if (DebugActiveProcess(parent_pid) == FALSE) {
        const DWORD attach_error = GetLastError();
        WriteWindowsNceV63Line("NCE_D2_FASTFAIL_DEBUG_ATTACH_FAIL", parent_pid, child_pid,
                               0xFFFFFFFFul, STILL_ACTIVE, attach_error);

        const DWORD wait_result = WaitForSingleObject(parent_handle, INFINITE);
        DWORD exit_code = 0xFFFFFFFFul;
        const BOOL got_exit = GetExitCodeProcess(parent_handle, &exit_code);
        const DWORD error_code = got_exit != FALSE ? 0 : GetLastError();
        WriteWindowsNceV63Line("V63_WATCHDOG_EXIT", parent_pid, child_pid, wait_result, exit_code,
                               error_code);
        CloseHandle(parent_handle);
        return 0;
    }

    (void)DebugSetProcessKillOnExit(FALSE);
    WriteWindowsNceV63Line("NCE_D2_FASTFAIL_DEBUG_ATTACHED", parent_pid, child_pid,
                           0xFFFFFFFFul, STILL_ACTIVE, 0);

    HANDLE read_handle =
        OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, parent_pid);
    bool consumed_attach_breakpoint = false;
    u64 breakpoint_sequence = 0;
    u64 known_guest_brk_skipped = 0;
    u64 breakpoint_candidates = 0;
    bool saw_exit = false;
    DWORD debug_exit_code = 0xFFFFFFFFul;

    while (!saw_exit) {
        DEBUG_EVENT event{};
        if (WaitForDebugEvent(&event, INFINITE) == FALSE) {
            WriteWindowsNceV63Line("NCE_D2_FASTFAIL_DEBUG_WAIT_FAIL", parent_pid, child_pid,
                                   0xFFFFFFFFul, STILL_ACTIVE, GetLastError());
            break;
        }

        DWORD continue_status = DBG_CONTINUE;

        if (event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT) {
            const auto& exception = event.u.Exception;
            const auto& record = exception.ExceptionRecord;

            if (record.ExceptionCode == EXCEPTION_BREAKPOINT) {
                const bool consume_as_attach = !consumed_attach_breakpoint;
                ++breakpoint_sequence;

                // Low-perturbation D2 observer: the normal Windows NCE x18 fallback path generates
                // very large numbers of deliberate BRK #0xF000 exceptions. Capturing full thread
                // context, resolving modules, and flushing a log line for every one materially
                // perturbs scheduling and can hide the rare unmatched HostStackBridge breakpoint.
                //
                // The target occurrence previously reported ExceptionAddress at a non-BRK host
                // instruction (STR X1,[X18,#8]). Therefore, after the debugger-attach breakpoint,
                // read only the 4-byte instruction at ExceptionAddress. Known generated guest BRK
                // sites are passed directly to VEH with no thread-context capture or per-event I/O.
                // Any non-BRK (or unreadable) breakpoint remains a candidate and gets the complete
                // pre-VEH diagnostic record.
                constexpr u32 D2KnownGuestBreakpointInstruction = 0xD43E0000;
                u32 exception_instruction = 0;
                SIZE_T exception_instruction_bytes = 0;
                const u64 exception_address =
                    reinterpret_cast<u64>(record.ExceptionAddress);
                const bool known_guest_brk =
                    !consume_as_attach && read_handle != nullptr && exception_address != 0 &&
                    ReadProcessMemory(
                        read_handle,
                        reinterpret_cast<const void*>(
                            static_cast<std::uintptr_t>(exception_address)),
                        &exception_instruction, sizeof(exception_instruction),
                        &exception_instruction_bytes) != FALSE &&
                    exception_instruction_bytes == sizeof(exception_instruction) &&
                    exception_instruction == D2KnownGuestBreakpointInstruction;

                if (known_guest_brk) {
                    ++known_guest_brk_skipped;
                    continue_status = DBG_EXCEPTION_NOT_HANDLED;
                } else {
                    ++breakpoint_candidates;

                    CONTEXT context{};
                    context.ContextFlags = CONTEXT_ALL;
                    DWORD context_error = 0;
                    HANDLE thread =
                        OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE,
                                   event.dwThreadId);
                    const CONTEXT* context_ptr = nullptr;
                    if (thread != nullptr) {
                        if (GetThreadContext(thread, &context) != FALSE) {
                            context_ptr = &context;
                        } else {
                            context_error = GetLastError();
                        }
                        CloseHandle(thread);
                    } else {
                        context_error = GetLastError();
                    }

                    WriteWindowsNceD2BreakpointDebugLine(
                        parent_pid, child_pid, event.dwThreadId, breakpoint_sequence,
                        consume_as_attach, exception, context_ptr, read_handle, context_error);

                    if (consume_as_attach) {
                        consumed_attach_breakpoint = true;
                        continue_status = DBG_CONTINUE;
                    } else {
                        continue_status = DBG_EXCEPTION_NOT_HANDLED;
                    }
                }
            } else if (record.ExceptionCode == D2FastFailExceptionCode) {
                CONTEXT context{};
                context.ContextFlags = CONTEXT_ALL;

                DWORD context_error = 0;
                HANDLE thread =
                    OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE,
                               event.dwThreadId);
                const CONTEXT* context_ptr = nullptr;
                if (thread != nullptr) {
                    if (GetThreadContext(thread, &context) != FALSE) {
                        context_ptr = &context;
                    } else {
                        context_error = GetLastError();
                    }
                    CloseHandle(thread);
                } else {
                    context_error = GetLastError();
                }

                u64 stack_base = 0;
                u64 stack_limit = 0;
                u64 frame_prev = 0;
                u64 frame_lr = 0;
                u64 frame2_prev = 0;
                u64 frame2_lr = 0;
                u32 frame_lr_instruction_minus4 = 0;
                u32 frame_lr_instruction = 0;
                u32 frame_lr_instruction_plus4 = 0;
                bool frame_lr_instruction_minus4_ok = false;
                bool frame_lr_instruction_ok = false;
                bool frame_lr_instruction_plus4_ok = false;
                u32 instruction = 0;
                u32 instruction_minus4 = 0;
                u32 instruction_plus4 = 0;
                bool instruction_ok = false;
                bool instruction_minus4_ok = false;
                bool instruction_plus4_ok = false;
                DWORD memory_error = 0;

                if (read_handle != nullptr && context_ptr != nullptr) {
                    SIZE_T bytes{};
                    const u64 x18 = static_cast<u64>(context.X[18]);
                    if (x18 != 0) {
                        if (ReadProcessMemory(read_handle,
                                              reinterpret_cast<const void*>(x18 + 8),
                                              &stack_base, sizeof(stack_base), &bytes) == FALSE ||
                            bytes != sizeof(stack_base)) {
                            memory_error = GetLastError();
                            stack_base = 0;
                        }
                        bytes = 0;
                        if (ReadProcessMemory(read_handle,
                                              reinterpret_cast<const void*>(x18 + 16),
                                              &stack_limit, sizeof(stack_limit), &bytes) == FALSE ||
                            bytes != sizeof(stack_limit)) {
                            if (memory_error == 0) {
                                memory_error = GetLastError();
                            }
                            stack_limit = 0;
                        }
                    }

                    auto read_instruction = [&](u64 address, u32& value) {
                        SIZE_T instruction_bytes{};
                        return address != 0 &&
                               ReadProcessMemory(
                                   read_handle,
                                   reinterpret_cast<const void*>(
                                       static_cast<std::uintptr_t>(address)),
                                   &value, sizeof(value), &instruction_bytes) != FALSE &&
                               instruction_bytes == sizeof(value);
                    };

                    instruction_ok = read_instruction(static_cast<u64>(context.Pc), instruction);
                    instruction_minus4_ok =
                        context.Pc >= sizeof(u32) &&
                        read_instruction(static_cast<u64>(context.Pc) - sizeof(u32),
                                         instruction_minus4);
                    instruction_plus4_ok =
                        read_instruction(static_cast<u64>(context.Pc) + sizeof(u32),
                                         instruction_plus4);

                    const u64 fp = static_cast<u64>(context.X[29]);
                    if (fp != 0) {
                        u64 frame_record[2]{};
                        SIZE_T frame_bytes{};
                        if (ReadProcessMemory(read_handle,
                                              reinterpret_cast<const void*>(
                                                  static_cast<std::uintptr_t>(fp)),
                                              frame_record, sizeof(frame_record),
                                              &frame_bytes) != FALSE &&
                            frame_bytes == sizeof(frame_record)) {
                            frame_prev = frame_record[0];
                            frame_lr = frame_record[1];

                            const u64 canonical_frame_lr =
                                frame_lr & 0x0000FFFFFFFFFFFFULL;
                            frame_lr_instruction_ok =
                                read_instruction(canonical_frame_lr, frame_lr_instruction);
                            frame_lr_instruction_minus4_ok =
                                canonical_frame_lr >= sizeof(u32) &&
                                read_instruction(canonical_frame_lr - sizeof(u32),
                                                 frame_lr_instruction_minus4);
                            frame_lr_instruction_plus4_ok =
                                read_instruction(canonical_frame_lr + sizeof(u32),
                                                 frame_lr_instruction_plus4);

                            if (frame_prev > fp && frame_prev - fp < 0x01000000ULL) {
                                u64 frame2_record[2]{};
                                SIZE_T frame2_bytes{};
                                if (ReadProcessMemory(
                                        read_handle,
                                        reinterpret_cast<const void*>(
                                            static_cast<std::uintptr_t>(frame_prev)),
                                        frame2_record, sizeof(frame2_record),
                                        &frame2_bytes) != FALSE &&
                                    frame2_bytes == sizeof(frame2_record)) {
                                    frame2_prev = frame2_record[0];
                                    frame2_lr = frame2_record[1];
                                }
                            }
                        } else if (memory_error == 0) {
                            memory_error = GetLastError();
                        }
                    }
                }

                const u64 pc_value = context_ptr != nullptr ? static_cast<u64>(context.Pc) : 0;
                const u64 lr_value =
                    context_ptr != nullptr ? static_cast<u64>(context.X[30]) : 0;
                const auto pc_module = ResolveD2FastFailModule(parent_pid, pc_value);
                const auto lr_module = ResolveD2FastFailModule(parent_pid, lr_value);
                const auto frame_lr_module = ResolveD2FastFailModule(parent_pid, frame_lr);
                const auto frame2_lr_module = ResolveD2FastFailModule(parent_pid, frame2_lr);

                WriteWindowsNceD2FastFailLine(
                    parent_pid, child_pid, event.dwThreadId, exception, context_ptr, stack_base,
                    stack_limit, instruction, instruction_ok, instruction_minus4,
                    instruction_minus4_ok, instruction_plus4, instruction_plus4_ok, frame_prev,
                    frame_lr, frame2_prev, frame2_lr, frame_lr_instruction_minus4,
                    frame_lr_instruction_minus4_ok, frame_lr_instruction,
                    frame_lr_instruction_ok, frame_lr_instruction_plus4,
                    frame_lr_instruction_plus4_ok, pc_module, lr_module, frame_lr_module,
                    frame2_lr_module, context_error, memory_error);
                continue_status = DBG_EXCEPTION_NOT_HANDLED;
            } else {
                continue_status = DBG_EXCEPTION_NOT_HANDLED;
            }
        } else if (event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
            if (event.u.CreateProcessInfo.hFile != nullptr) {
                CloseHandle(event.u.CreateProcessInfo.hFile);
            }
        } else if (event.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT) {
            if (event.u.LoadDll.hFile != nullptr) {
                CloseHandle(event.u.LoadDll.hFile);
            }
        } else if (event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) {
            debug_exit_code = event.u.ExitProcess.dwExitCode;
            saw_exit = true;
        }

        (void)ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continue_status);
    }

    if (read_handle != nullptr) {
        CloseHandle(read_handle);
    }

    {
        HANDLE file = OpenWindowsNceV63Log();
        if (file != INVALID_HANDLE_VALUE) {
            char line[512]{};
            const int line_length = std::snprintf(
                line, sizeof(line),
                "NCE_D2_BREAKPOINT_FILTER_SUMMARY parent_pid=%lu child_pid=%lu "
                "breakpoints=%llu known_guest_brk_skipped=%llu candidates=%llu "
                "base=2f0d41b173b4f9ae0d4e0b96cb61402c9ea5cd0e\r\n",
                parent_pid, child_pid,
                static_cast<unsigned long long>(breakpoint_sequence),
                static_cast<unsigned long long>(known_guest_brk_skipped),
                static_cast<unsigned long long>(breakpoint_candidates));
            if (line_length > 0) {
                DWORD written{};
                const DWORD size = static_cast<DWORD>(
                    line_length < static_cast<int>(sizeof(line)) ? line_length
                                                                 : sizeof(line) - 1);
                (void)WriteFile(file, line, size, &written, nullptr);
                (void)FlushFileBuffers(file);
            }
            CloseHandle(file);
        }
    }

    if (!saw_exit) {
        (void)DebugActiveProcessStop(parent_pid);
        const DWORD wait_result = WaitForSingleObject(parent_handle, INFINITE);
        DWORD exit_code = 0xFFFFFFFFul;
        const BOOL got_exit = GetExitCodeProcess(parent_handle, &exit_code);
        const DWORD error_code = got_exit != FALSE ? 0 : GetLastError();
        WriteWindowsNceV63Line("V63_WATCHDOG_EXIT", parent_pid, child_pid, wait_result, exit_code,
                               error_code);
    } else {
        WriteWindowsNceV63Line("V63_WATCHDOG_EXIT", parent_pid, child_pid, WAIT_OBJECT_0,
                               debug_exit_code, 0);
    }

    CloseHandle(parent_handle);
    return 0;
}

void LaunchWindowsNceV63Watchdog() noexcept {
    const DWORD parent_pid = GetCurrentProcessId();
    HANDLE parent_handle =
        OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, TRUE, parent_pid);
    if (parent_handle == nullptr) {
        WriteWindowsNceV63Line("V63_WATCHDOG_OPEN_FAIL", parent_pid, 0, 0xFFFFFFFFul,
                               STILL_ACTIVE, GetLastError());
        return;
    }

    wchar_t executable[32768]{};
    const DWORD executable_length =
        GetModuleFileNameW(nullptr, executable,
                           static_cast<DWORD>(sizeof(executable) / sizeof(executable[0])));
    if (executable_length == 0 ||
        executable_length >= static_cast<DWORD>(sizeof(executable) / sizeof(executable[0]))) {
        WriteWindowsNceV63Line("V63_WATCHDOG_PATH_FAIL", parent_pid, 0, 0xFFFFFFFFul,
                               STILL_ACTIVE, GetLastError());
        CloseHandle(parent_handle);
        return;
    }

    wchar_t command_line[32768]{};
    const auto handle_value =
        static_cast<unsigned long long>(reinterpret_cast<std::uintptr_t>(parent_handle));
    const int command_length =
        std::swprintf(command_line, sizeof(command_line) / sizeof(command_line[0]),
                      L"\"%ls\" --nce-v63-watchdog %llu %lu", executable, handle_value,
                      static_cast<unsigned long>(parent_pid));
    if (command_length <= 0 ||
        command_length >= static_cast<int>(sizeof(command_line) / sizeof(command_line[0]))) {
        WriteWindowsNceV63Line("V63_WATCHDOG_COMMAND_FAIL", parent_pid, 0, 0xFFFFFFFFul,
                               STILL_ACTIVE, 0);
        CloseHandle(parent_handle);
        return;
    }

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION child{};
    const BOOL created =
        CreateProcessW(executable, command_line, nullptr, nullptr, TRUE,
                       CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT, nullptr, nullptr, &startup,
                       &child);
    if (created == FALSE) {
        WriteWindowsNceV63Line("V63_WATCHDOG_LAUNCH_FAIL", parent_pid, 0, 0xFFFFFFFFul,
                               STILL_ACTIVE, GetLastError());
        CloseHandle(parent_handle);
        return;
    }

    WriteWindowsNceV63Line("V63_WATCHDOG_LAUNCHED", parent_pid,
                           static_cast<unsigned long>(child.dwProcessId), 0xFFFFFFFFul,
                           STILL_ACTIVE, 0);
    CloseHandle(child.hThread);
    CloseHandle(child.hProcess);
    CloseHandle(parent_handle);
}



[[maybe_unused]] LONG WINAPI WindowsNceV64UnhandledExceptionFilter(EXCEPTION_POINTERS* exception_pointers) noexcept {
    if (exception_pointers == nullptr || exception_pointers->ExceptionRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const EXCEPTION_RECORD* record = exception_pointers->ExceptionRecord;
    const CONTEXT* context = exception_pointers->ContextRecord;

    char temp_path[MAX_PATH + 1]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    char path[MAX_PATH + 64]{};
    const int path_length =
        std::snprintf(path, sizeof(path), "%s%s", temp_path, "eden_nce_v64_unhandled.log");
    if (path_length <= 0 || static_cast<size_t>(path_length) >= sizeof(path)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    HANDLE file = CreateFileA(path, FILE_APPEND_DATA,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const ULONG_PTR access_type =
        record->NumberParameters >= 1 ? record->ExceptionInformation[0] : ~ULONG_PTR{0};
    const ULONG_PTR fault_address =
        record->NumberParameters >= 2 ? record->ExceptionInformation[1] : 0;

#if defined(_M_ARM64)
    const unsigned long long pc =
        context != nullptr ? static_cast<unsigned long long>(context->Pc) : 0;
    const unsigned long long sp =
        context != nullptr ? static_cast<unsigned long long>(context->Sp) : 0;
    const unsigned long long x18 =
        context != nullptr ? static_cast<unsigned long long>(context->X[18]) : 0;
#else
    const unsigned long long pc = 0;
    const unsigned long long sp = 0;
    const unsigned long long x18 = 0;
#endif

    char line[1024]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "V64_UNHANDLED tick=%llu pid=%lu tid=%lu code=0x%08lX flags=0x%08lX "
        "exception_address=0x%016llX parameters=%lu access_type=0x%016llX "
        "fault_address=0x%016llX pc=0x%016llX sp=0x%016llX x18=0x%016llX "
        "base=ef5a51e01159f7d7aff90e8df760ade7dd2bbe19\r\n",
        static_cast<unsigned long long>(GetTickCount64()),
        static_cast<unsigned long>(GetCurrentProcessId()),
        static_cast<unsigned long>(GetCurrentThreadId()),
        static_cast<unsigned long>(record->ExceptionCode),
        static_cast<unsigned long>(record->ExceptionFlags),
        static_cast<unsigned long long>(
            reinterpret_cast<std::uintptr_t>(record->ExceptionAddress)),
        static_cast<unsigned long>(record->NumberParameters),
        static_cast<unsigned long long>(access_type),
        static_cast<unsigned long long>(fault_address), pc, sp, x18);
    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);

    return EXCEPTION_CONTINUE_SEARCH;
}

PVOID g_windows_nce_v65_illegal_instruction_veh{};

void WriteWindowsNceV65IllegalInstruction(const char* tag,
                                          EXCEPTION_POINTERS* exception_pointers) noexcept {
    char temp_path[MAX_PATH + 1]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH) {
        return;
    }

    char path[MAX_PATH + 80]{};
    const int path_length = std::snprintf(
        path, sizeof(path), "%s%s", temp_path, "eden_nce_v65_illegal_instruction.log");
    if (path_length <= 0 || static_cast<size_t>(path_length) >= sizeof(path)) {
        return;
    }

    HANDLE file = CreateFileA(path, FILE_APPEND_DATA,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    const EXCEPTION_RECORD* record =
        exception_pointers != nullptr ? exception_pointers->ExceptionRecord : nullptr;
    const CONTEXT* context =
        exception_pointers != nullptr ? exception_pointers->ContextRecord : nullptr;

    unsigned long exception_code = 0;
    unsigned long exception_flags = 0;
    unsigned long parameter_count = 0;
    unsigned long long exception_address = 0;
    unsigned long long pc = 0;
    unsigned long long sp = 0;
    unsigned long long x18 = 0;
    unsigned long long lr = 0;
    unsigned long cpsr = 0;
    unsigned long instruction = 0;
    size_t instruction_bytes = 0;

    if (record != nullptr) {
        exception_code = static_cast<unsigned long>(record->ExceptionCode);
        exception_flags = static_cast<unsigned long>(record->ExceptionFlags);
        parameter_count = static_cast<unsigned long>(record->NumberParameters);
        exception_address = static_cast<unsigned long long>(
            reinterpret_cast<std::uintptr_t>(record->ExceptionAddress));

        SIZE_T bytes_read{};
        if (record->ExceptionAddress != nullptr &&
            ReadProcessMemory(GetCurrentProcess(), record->ExceptionAddress, &instruction,
                              sizeof(instruction), &bytes_read) != FALSE) {
            instruction_bytes = static_cast<size_t>(bytes_read);
        }
    }

#if defined(_M_ARM64)
    if (context != nullptr) {
        pc = static_cast<unsigned long long>(context->Pc);
        sp = static_cast<unsigned long long>(context->Sp);
        x18 = static_cast<unsigned long long>(context->X[18]);
        lr = static_cast<unsigned long long>(context->X[30]);
        cpsr = static_cast<unsigned long>(context->Cpsr);
    }
#endif

    char line[1200]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "%s tick=%llu pid=%lu tid=%lu code=0x%08lX flags=0x%08lX "
        "exception_address=0x%016llX parameters=%lu pc=0x%016llX sp=0x%016llX "
        "x18=0x%016llX lr=0x%016llX cpsr=0x%08lX instruction=0x%08lX "
        "instruction_bytes=%zu base=893afde63dd5e9be74fb91e18aa3e6fa634eb7bb\r\n",
        tag, static_cast<unsigned long long>(GetTickCount64()),
        static_cast<unsigned long>(GetCurrentProcessId()),
        static_cast<unsigned long>(GetCurrentThreadId()), exception_code, exception_flags,
        exception_address, parameter_count, pc, sp, x18, lr, cpsr, instruction,
        instruction_bytes);
    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
}

LONG CALLBACK WindowsNceV65IllegalInstructionVeh(EXCEPTION_POINTERS* exception_pointers) noexcept {
    if (exception_pointers == nullptr || exception_pointers->ExceptionRecord == nullptr ||
        exception_pointers->ExceptionRecord->ExceptionCode != EXCEPTION_ILLEGAL_INSTRUCTION) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    WriteWindowsNceV65IllegalInstruction("V65_ILLEGAL_INSTRUCTION", exception_pointers);
    return EXCEPTION_CONTINUE_SEARCH;
}

[[maybe_unused]] void InstallWindowsNceV65IllegalInstructionVeh() noexcept {
    g_windows_nce_v65_illegal_instruction_veh =
        AddVectoredExceptionHandler(1, &WindowsNceV65IllegalInstructionVeh);
    WriteWindowsNceV65IllegalInstruction(
        g_windows_nce_v65_illegal_instruction_veh != nullptr ? "V65_VEH_READY"
                                                             : "V65_VEH_INSTALL_FAIL",
        nullptr);
}


PVOID g_windows_nce_v70_breakpoint_veh{};

void WriteWindowsNceV70Breakpoint(const char* tag,
                                  EXCEPTION_POINTERS* exception_pointers) noexcept {
    char temp_path[MAX_PATH + 1]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH) {
        return;
    }

    char path[MAX_PATH + 96]{};
    const int path_length =
        std::snprintf(path, sizeof(path), "%s%s", temp_path,
                      "eden_nce_v70_host_bridge_origin.log");
    if (path_length <= 0 || static_cast<size_t>(path_length) >= sizeof(path)) {
        return;
    }

    HANDLE file = CreateFileA(path, FILE_APPEND_DATA,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    const EXCEPTION_RECORD* record =
        exception_pointers != nullptr ? exception_pointers->ExceptionRecord : nullptr;
    const CONTEXT* context =
        exception_pointers != nullptr ? exception_pointers->ContextRecord : nullptr;

    unsigned long exception_code = 0;
    unsigned long exception_flags = 0;
    unsigned long parameter_count = 0;
    unsigned long long exception_address = 0;
    unsigned long long exception_info0 = 0;
    unsigned long context_flags = 0;
    unsigned long long pc = 0;
    unsigned long long sp = 0;
    unsigned long long x0 = 0;
    unsigned long long x1 = 0;
    unsigned long long x2 = 0;
    unsigned long long x3 = 0;
    unsigned long long x16 = 0;
    unsigned long long x18 = 0;
    unsigned long long lr = 0;
    unsigned long cpsr = 0;
    unsigned long inst_minus4 = 0;
    unsigned long inst_pc = 0;
    unsigned long inst_plus4 = 0;
    unsigned long inst_plus8 = 0;
    unsigned long inst_plus12 = 0;
    size_t minus4_bytes = 0;
    size_t pc_bytes = 0;
    size_t plus4_bytes = 0;
    size_t plus8_bytes = 0;
    size_t plus12_bytes = 0;

    if (record != nullptr) {
        exception_code = static_cast<unsigned long>(record->ExceptionCode);
        exception_flags = static_cast<unsigned long>(record->ExceptionFlags);
        parameter_count = static_cast<unsigned long>(record->NumberParameters);
        exception_address = static_cast<unsigned long long>(
            reinterpret_cast<std::uintptr_t>(record->ExceptionAddress));
        if (record->NumberParameters >= 1) {
            exception_info0 = static_cast<unsigned long long>(record->ExceptionInformation[0]);
        }
    }

#if defined(_M_ARM64)
    if (context != nullptr) {
        context_flags = static_cast<unsigned long>(context->ContextFlags);
        pc = static_cast<unsigned long long>(context->Pc);
        sp = static_cast<unsigned long long>(context->Sp);
        x0 = static_cast<unsigned long long>(context->X[0]);
        x1 = static_cast<unsigned long long>(context->X[1]);
        x2 = static_cast<unsigned long long>(context->X[2]);
        x3 = static_cast<unsigned long long>(context->X[3]);
        x16 = static_cast<unsigned long long>(context->X[16]);
        x18 = static_cast<unsigned long long>(context->X[18]);
        lr = static_cast<unsigned long long>(context->X[30]);
        cpsr = static_cast<unsigned long>(context->Cpsr);

        const auto read_word = [&](std::uint64_t address, unsigned long& value,
                                   size_t& bytes) noexcept {
            SIZE_T bytes_read{};
            if (address != 0 &&
                ReadProcessMemory(GetCurrentProcess(),
                                  reinterpret_cast<const void*>(
                                      static_cast<std::uintptr_t>(address)),
                                  &value, sizeof(value), &bytes_read) != FALSE) {
                bytes = static_cast<size_t>(bytes_read);
            }
        };

        if (context->Pc >= sizeof(u32)) {
            read_word(context->Pc - sizeof(u32), inst_minus4, minus4_bytes);
        }
        read_word(context->Pc, inst_pc, pc_bytes);
        read_word(context->Pc + sizeof(u32), inst_plus4, plus4_bytes);
        read_word(context->Pc + sizeof(u32) * 2, inst_plus8, plus8_bytes);
        read_word(context->Pc + sizeof(u32) * 3, inst_plus12, plus12_bytes);
    }
#endif

    char line[2200]{};
    const int line_length = std::snprintf(
        line, sizeof(line),
        "%s tick=%llu pid=%lu tid=%lu code=0x%08lX flags=0x%08lX "
        "exception_address=0x%016llX parameters=%lu info0=0x%016llX "
        "context_flags=0x%08lX pc=0x%016llX sp=0x%016llX "
        "x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX "
        "x16=0x%016llX x18=0x%016llX lr=0x%016llX cpsr=0x%08lX "
        "inst_m4=0x%08lX/%zu inst_pc=0x%08lX/%zu "
        "inst_p4=0x%08lX/%zu inst_p8=0x%08lX/%zu inst_p12=0x%08lX/%zu "
        "xf18_return=0x5846313846414C4C breakloop=0x02000000 prefetch=0x20000000 "
        "base=05d51f33fdd04f639f798bd244ba1a60e08a6d0a\r\n",
        tag, static_cast<unsigned long long>(GetTickCount64()),
        static_cast<unsigned long>(GetCurrentProcessId()),
        static_cast<unsigned long>(GetCurrentThreadId()), exception_code, exception_flags,
        exception_address, parameter_count, exception_info0, context_flags, pc, sp,
        x0, x1, x2, x3, x16, x18, lr, cpsr,
        inst_minus4, minus4_bytes, inst_pc, pc_bytes,
        inst_plus4, plus4_bytes, inst_plus8, plus8_bytes, inst_plus12, plus12_bytes);

    if (line_length > 0) {
        DWORD written{};
        const DWORD size = static_cast<DWORD>(
            line_length < static_cast<int>(sizeof(line)) ? line_length : sizeof(line) - 1);
        (void)WriteFile(file, line, size, &written, nullptr);
        (void)FlushFileBuffers(file);
    }
    CloseHandle(file);
}

LONG CALLBACK WindowsNceV70BreakpointVeh(EXCEPTION_POINTERS* exception_pointers) noexcept {
    if (exception_pointers == nullptr || exception_pointers->ExceptionRecord == nullptr ||
        exception_pointers->ExceptionRecord->ExceptionCode != EXCEPTION_BREAKPOINT) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    WriteWindowsNceV70Breakpoint("V70_BREAKPOINT", exception_pointers);
    return EXCEPTION_CONTINUE_SEARCH;
}

[[maybe_unused]] void InstallWindowsNceV70BreakpointVeh() noexcept {
    // Tail observer: NCE still gets first chance. V70 only expands the escaping breakpoint
    // context so the host/guest bridge and RedirectToHost return-value origin can be classified.
    g_windows_nce_v70_breakpoint_veh =
        AddVectoredExceptionHandler(0, &WindowsNceV70BreakpointVeh);
    WriteWindowsNceV70Breakpoint(
        g_windows_nce_v70_breakpoint_veh != nullptr ? "V70_VEH_READY"
                                                    : "V70_VEH_INSTALL_FAIL",
        nullptr);
}

} // namespace

static void OverrideWindowsFont() {
    // Qt5 chooses these fonts on Windows and they have fairly ugly alphanumeric/cyrillic characters
    // Asking to use "MS Shell Dlg 2" gives better other chars while leaving the Chinese Characters.
    const QString startup_font = QApplication::font().family();
    const QStringList ugly_fonts = {QStringLiteral("SimSun"), QStringLiteral("PMingLiU")};
    if (ugly_fonts.contains(startup_font)) {
        QApplication::setFont(QFont(QStringLiteral("MS Shell Dlg 2"), 9, QFont::Normal));
    }
}
#endif

static Qt::HighDpiScaleFactorRoundingPolicy GetHighDpiRoundingPolicy() {
#ifdef _WIN32
    // For Windows, we want to avoid scaling artifacts on fractional scaling ratios.
    // This is done by setting the optimal scaling policy for the primary screen.

    // Create a temporary QApplication.
    int temp_argc = 0;
    char** temp_argv = nullptr;
    QApplication temp{temp_argc, temp_argv};

    // Get the current screen geometry.
    const QScreen* primary_screen = QGuiApplication::primaryScreen();
    if (primary_screen == nullptr) {
        return Qt::HighDpiScaleFactorRoundingPolicy::PassThrough;
    }

    const QRect screen_rect = primary_screen->geometry();
    const qreal real_ratio = primary_screen->devicePixelRatio();
    const qreal real_width = std::trunc(screen_rect.width() * real_ratio);
    const qreal real_height = std::trunc(screen_rect.height() * real_ratio);

    // Recommended minimum width and height for proper window fit.
    // Any screen with a lower resolution than this will still have a scale of 1.
    constexpr qreal minimum_width = 1350.0;
    constexpr qreal minimum_height = 900.0;

    const qreal width_ratio = std::max(1.0, real_width / minimum_width);
    const qreal height_ratio = std::max(1.0, real_height / minimum_height);

    // Get the lower of the 2 ratios and truncate, this is the maximum integer scale.
    const qreal max_ratio = std::trunc(std::min(width_ratio, height_ratio));
    return max_ratio > real_ratio ? Qt::HighDpiScaleFactorRoundingPolicy::Round
                                  : Qt::HighDpiScaleFactorRoundingPolicy::Floor;
#else
    // Other OSes should be better than Windows at fractional scaling.
    return Qt::HighDpiScaleFactorRoundingPolicy::PassThrough;
#endif
}

int main(int argc, char* argv[]) {
#ifdef _WIN32
    if (argc >= 2 && std::strcmp(argv[1], V63WatchdogArgument) == 0) {
        return RunWindowsNceV63Watchdog(argc, argv);
    }
    LaunchWindowsNceV63Watchdog();
#endif

#if YUZU_ROOM
    bool launch_room = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--room") == 0) {
            launch_room = true;
        }
    }

    if (launch_room) {
        LaunchRoom(argc, argv, true);
        return 0;
    }
#endif

    bool has_broken_vulkan = false;
    bool is_child = false;
    if (CheckEnvVars(&is_child)) {
        return 0;
    }

    if (StartupChecks(argv[0], &has_broken_vulkan,
                      Settings::values.perform_vulkan_check.GetValue())) {
        return 0;
    }

#ifdef YUZU_CRASH_DUMPS
    Breakpad::InstallCrashHandler();
#endif

    // Init settings params
    QCoreApplication::setOrganizationName(QStringLiteral("eden"));
    QCoreApplication::setApplicationName(QStringLiteral("eden"));

    // Increases the maximum open file limit.
    // TODO: This should be common to all frontends.
#ifdef _WIN32
    // MSVCRT limits this to 2048 for some inexplicable (and likely arcane) reason,
    // so we have to account for that as well.
#ifdef __MSVCRT__
    _setmaxstdio(2048);
#else
    _setmaxstdio(8192);
#endif // __MSVCRT__
#elif defined(__unix__) || defined(__APPLE__)
    // Set the max open file limit to 8192, or the hard limit.
    // Most sane systems should not hit the hard limit here.
    struct rlimit rl;
    if (getrlimit(RLIMIT_NOFILE, &rl) == 0) {
        rl.rlim_cur = std::min<rlim_t>(8192, rl.rlim_max);
        setrlimit(RLIMIT_NOFILE, &rl);
    }
#endif // _WIN32

#if defined(__APPLE__)
    // Convert the relative path to an absolute path before the chdir
    char resolved[PATH_MAX];
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "-u") == 0 || strcmp(argv[i], "-input-profile") == 0) {
            ++i;
        } else if (argv[i][0] != '-' && argv[i][0] != '/' && realpath(argv[i], resolved)) {
            argv[i] = strdup(resolved);
        }
    }

    // If you start a bundle (binary) on OSX without the Terminal, the working directory is "/".
    // But since we require the working directory to be the executable path for the location of
    // the user folder in the Qt Frontend, we need to cd into that working directory
    const auto bin_path = Common::FS::GetBundleDirectory() / "..";
    chdir(Common::FS::PathToUTF8String(bin_path).c_str());
#endif

#ifdef __unix__
    // Set the DISPLAY variable in order to open web browsers
    // TODO (lat9nq): Find a better solution for AppImages to start external applications
    if (QString::fromLocal8Bit(qgetenv("DISPLAY")).isEmpty()) {
        qputenv("DISPLAY", ":0");
    }

    if (GraphicsBackend::GetForceX11() && qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM"))
        qputenv("QT_QPA_PLATFORM", "xcb");

    // Fix the Wayland appId. This needs to match the name of the .desktop file without the .desktop
    // suffix.
    QGuiApplication::setDesktopFileName(QStringLiteral("dev.eden_emu.eden"));
#endif

    auto rounding_policy = GetHighDpiRoundingPolicy();
    QApplication::setHighDpiScaleFactorRoundingPolicy(rounding_policy);

#if QT_VERSION < QT_VERSION_CHECK(6, 0, 0)
    // Disables the "?" button on all dialogs. Disabled by default on Qt6.
    QCoreApplication::setAttribute(Qt::AA_DisableWindowContextHelpButton);
#endif

    // Enables the core to make the qt created contexts current on std::threads
    QCoreApplication::setAttribute(Qt::AA_DontCheckOpenGLContextThreadAffinity);

#ifdef _WIN32
    QApplication::setStyle(QStringLiteral("windowsvista"));
#endif

    QApplication app(argc, argv);

#ifdef _WIN32
    // V75 diagnostic: keep natural Windows WER terminal handling uncontaminated by the historical
    // in-process V64/V65/V70 exception observers. Run 2 proved that their logging path can consume
    // enough of a small guest/TEB stack to fault inside GetTempPathA. V63 remains out-of-process,
    // and the V74 NCE provenance instrumentation is unchanged.
    OverrideWindowsFont();
#endif

    // Workaround for QTBUG-85409, for Suzhou numerals the number 1 is actually \u3021
    // so we can see if we get \u3008 instead
    // TL;DR all other number formats are consecutive in unicode code points
    // This bug is fixed in Qt6, specifically 6.0.0-alpha1
#if QT_VERSION < QT_VERSION_CHECK(6, 0, 0)
    const QLocale locale = QLocale::system();
    if (QStringLiteral("\u3008") == locale.toString(1)) {
        QLocale::setDefault(QLocale::system().name());
    }
#endif

    // Qt changes the locale and causes issues in float conversion using std::to_string() when
    // generating shaders
    setlocale(LC_ALL, "C");

    MainWindow main_window{has_broken_vulkan};
    // After settings have been loaded by GMainWindow, apply the filter
    main_window.show();

    app.connect(&app, &QGuiApplication::applicationStateChanged, &main_window, &MainWindow::OnAppFocusStateChanged);
    return app.exec();
}
