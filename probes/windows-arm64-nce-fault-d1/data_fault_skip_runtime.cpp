#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <utility>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/arm/nce/patcher.h"
#if defined(_WIN32)
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_nce_transition.h"
#endif
#include "core/core.h"
#include "core/device_memory.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/code_set.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/kernel.h"
#include "core/hle/kernel/svc_types.h"

#ifdef interface
#undef interface
#endif

namespace {

constexpr std::size_t PageSize = 0x1000;
constexpr std::size_t StackPages = 16;
constexpr std::size_t InitialImageSize = PageSize * (1 + StackPages);
constexpr u64 FaultSearchOffset = 0x100000;
constexpr u64 FaultSearchLimit = 0x2000000;
constexpr std::size_t GuestLoadOffset = 0x24;
constexpr std::size_t GuestSvcOffset = 0x28;
constexpr std::size_t GuestAfterSvcOffset = 0x2c;
constexpr u32 GuestLdrX3X2 = 0xF9400043U; // ldr x3, [x2]
constexpr u32 GuestSvc33 = 0xD4000661U;   // svc #0x33
constexpr u32 GuestBrk0 = 0xD4200000U;    // must never execute
constexpr u64 X0Sentinel = 0x1122334455667788ULL;
constexpr u64 X1Sentinel = 0x8877665544332211ULL;
constexpr u64 X3Sentinel = 0x0D1D0D1D0D1D0D1DULL;
constexpr u64 X18Sentinel = 0x123456789ABC0000ULL;

std::atomic<u32> g_read_preflight_seen{};
std::atomic<u64> g_read_preflight_page{};
std::atomic<u32> g_observation_seen{};
std::atomic<u32> g_fault_seen{};
std::atomic<u64> g_fault_access_type{};
std::atomic<u64> g_fault_address{};
std::atomic<u64> g_exception_pc{};
std::atomic<u64> g_exception_sp{};

#if defined(_WIN32)
constexpr u64 D1ObservationMagic = 0x31444F4257415231ULL; // "1RAWBOD1", endian-stable marker only
constexpr u32 D1ObservationVersion = 1;

struct D1FirstExceptionRecord {
    u64 magic;
    u32 version;
    u32 exception_code;
    u32 parameter_count;
    u32 reserved;
    u64 exception_address;
    u64 pc;
    u64 sp;
    u64 info0;
    u64 info1;
};
static_assert(sizeof(D1FirstExceptionRecord) == 64);

HANDLE g_observation_file = INVALID_HANDLE_VALUE;
D1FirstExceptionRecord g_first_exception_record{};
#endif

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

std::size_t PageAlign(std::size_t value) {
    return (value + PageSize - 1) & ~(PageSize - 1);
}

#if defined(_WIN32)
constexpr u32 D1ContinueRegistersVersionLow = 4;
constexpr u32 D1ContinueRegistersVersionHigh = 5;
constexpr u32 D1ContinuePhysicalX18Version = 6;
constexpr u32 D1GeneratedSaveGetterEnterVersion = 7;
constexpr u32 D1GeneratedSaveGetterReturnVersion = 8;

struct D1ContinueRegisterRecord {
    u64 magic;
    u32 version;
    u32 sequence;
    u32 exception_code;
    u32 parameter_count;
    u64 value0;
    u64 value1;
    u64 value2;
    u64 value3;
    u64 value4;
};
static_assert(sizeof(D1ContinueRegisterRecord) == 64);

std::atomic<u32> g_register_continue_seen{};

LONG CALLBACK D1ContinueRegisterObservation(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr || g_observation_file == INVALID_HANDLE_VALUE) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    u32 expected = 0;
    if (!g_register_continue_seen.compare_exchange_strong(expected, 1,
                                                          std::memory_order_acq_rel)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& exception_record = *exception->ExceptionRecord;
    const auto& context = *reinterpret_cast<const ARM64_NT_CONTEXT*>(exception->ContextRecord);

    D1ContinueRegisterRecord low{};
    low.magic = D1ObservationMagic;
    low.version = D1ContinueRegistersVersionLow;
    low.sequence = 2;
    low.exception_code = static_cast<u32>(exception_record.ExceptionCode);
    low.parameter_count = 0;
    low.value0 = context.X[0];
    low.value1 = context.X[1];
    low.value2 = context.X[2];
    low.value3 = context.X[3];
    low.value4 = context.X[30];

    D1ContinueRegisterRecord high{};
    high.magic = D1ObservationMagic;
    high.version = D1ContinueRegistersVersionHigh;
    high.sequence = 3;
    high.exception_code = static_cast<u32>(exception_record.ExceptionCode);
    high.parameter_count = 0;
    high.value0 = context.X[16];
    high.value1 = context.X[17];
    high.value2 = context.X[18];
    high.value3 = context.X[29];
    high.value4 = static_cast<u64>(context.Cpsr);

    // Windows ARM64 exception CONTEXT does not necessarily expose the live platform-owned x18.
    // Capture the actual physical x18 in the same VCH callback so the CONTEXT slot can be
    // distinguished from real TEB ownership without changing any guest/runtime behavior.
    u64 physical_x18{};
    asm volatile("mov %0, x18" : "=r"(physical_x18));

    D1ContinueRegisterRecord physical{};
    physical.magic = D1ObservationMagic;
    physical.version = D1ContinuePhysicalX18Version;
    physical.sequence = 4;
    physical.exception_code = static_cast<u32>(exception_record.ExceptionCode);
    physical.parameter_count = 0;
    physical.value0 = physical_x18;
    physical.value1 = context.X[18];

    DWORD bytes_written{};
    WriteFile(g_observation_file, &low, static_cast<DWORD>(sizeof(low)), &bytes_written, nullptr);
    bytes_written = 0;
    WriteFile(g_observation_file, &high, static_cast<DWORD>(sizeof(high)), &bytes_written, nullptr);
    bytes_written = 0;
    WriteFile(g_observation_file, &physical, static_cast<DWORD>(sizeof(physical)), &bytes_written,
              nullptr);
    return EXCEPTION_CONTINUE_SEARCH;
}

u64 ReadPhysicalX18() {
    u64 value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

void WriteGeneratedSaveGetterRecord(u32 version, u32 sequence, u64 value0, u64 value1,
                                    u64 value2) noexcept {
    if (g_observation_file == INVALID_HANDLE_VALUE) {
        return;
    }

    D1ContinueRegisterRecord observed{};
    observed.magic = D1ObservationMagic;
    observed.version = version;
    observed.sequence = sequence;
    observed.exception_code = 0;
    observed.parameter_count = 0;
    observed.value0 = value0;
    observed.value1 = value1;
    observed.value2 = value2;

    DWORD bytes_written{};
    WriteFile(g_observation_file, &observed, static_cast<DWORD>(sizeof(observed)), &bytes_written,
              nullptr);
}

#if defined(ARCHITECTURE_arm64)
extern "C" __attribute__((noinline)) void* D1GeneratedSaveGetterProbe() {
    u64 physical_x18_entry{};
    u64 physical_sp_entry{};
    asm volatile("mov %0, x18" : "=r"(physical_x18_entry));
    asm volatile("mov %0, sp" : "=r"(physical_sp_entry));
    WriteGeneratedSaveGetterRecord(D1GeneratedSaveGetterEnterVersion, 5, physical_x18_entry,
                                   physical_sp_entry, 0);

    void* const result = Core::NCE::GetCurrentNceContextForGeneratedCode();

    u64 physical_x18_return{};
    u64 physical_sp_return{};
    asm volatile("mov %0, x18" : "=r"(physical_x18_return));
    asm volatile("mov %0, sp" : "=r"(physical_sp_return));
    WriteGeneratedSaveGetterRecord(D1GeneratedSaveGetterReturnVersion, 6,
                                   static_cast<u64>(reinterpret_cast<uintptr_t>(result)),
                                   physical_x18_return, physical_sp_return);
    return result;
}

__attribute__((noinline)) void* CallCurrentNceGetterOnGuestStack(u64 guest_stack_pointer) {
    void* result{};
    const auto getter = &Core::NCE::GetCurrentNceContextForGeneratedCode;
    asm volatile("mov x19, sp\n"
                 "mov sp, %1\n"
                 "blr %2\n"
                 "mov %0, x0\n"
                 "mov sp, x19\n"
                 : "=r"(result)
                 : "r"(guest_stack_pointer), "r"(getter)
                 : "x0", "x19", "x30", "memory", "cc");
    return result;
}
#endif

bool IsReservedPage(u64 address, MEMORY_BASIC_INFORMATION& mbi) {
    if (VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) == 0) {
        return false;
    }
    return mbi.State == MEM_RESERVE;
}

LONG CALLBACK D1ReadPreflightVeh(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& record = *exception->ExceptionRecord;
    if (record.ExceptionCode != EXCEPTION_ACCESS_VIOLATION || record.NumberParameters < 2) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const u64 expected_page = g_read_preflight_page.load(std::memory_order_acquire);
    const u64 access_type = static_cast<u64>(record.ExceptionInformation[0]);
    const u64 fault_address = static_cast<u64>(record.ExceptionInformation[1]);
    if (expected_page == 0 || access_type != 0 || fault_address != expected_page) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    DWORD old_protect{};
    if (!VirtualProtect(reinterpret_cast<void*>(expected_page), PageSize, PAGE_READWRITE,
                        &old_protect)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    g_read_preflight_seen.store(1, std::memory_order_release);
    std::fprintf(stderr, "IMP008D_D1_PREFLIGHT_EXCEPTION_CODE=0x%08lX\n",
                 static_cast<unsigned long>(record.ExceptionCode));
    std::fprintf(stderr, "IMP008D_D1_PREFLIGHT_EXCEPTION_ACCESS=%llu\n",
                 static_cast<unsigned long long>(access_type));
    std::fprintf(stderr, "IMP008D_D1_PREFLIGHT_EXCEPTION_FAULT=0x%llX\n",
                 static_cast<unsigned long long>(fault_address));
    std::fprintf(stderr, "IMP008D_D1_PREFLIGHT_EXCEPTION_PC=0x%llX\n",
                 static_cast<unsigned long long>(exception->ContextRecord->Pc));
    std::fflush(stderr);
    return EXCEPTION_CONTINUE_EXECUTION;
}

bool RunSameAddressReadPreflight(u64 page) {
    if (page == 0) {
        return false;
    }

    DWORD old_protect{};
    if (!VirtualProtect(reinterpret_cast<void*>(page), PageSize, PAGE_NOACCESS, &old_protect)) {
        return false;
    }

    g_read_preflight_seen.store(0, std::memory_order_release);
    g_read_preflight_page.store(page, std::memory_order_release);
    PVOID const veh = AddVectoredExceptionHandler(1, &D1ReadPreflightVeh);
    if (veh == nullptr) {
        g_read_preflight_page.store(0, std::memory_order_release);
        return false;
    }

    volatile const u8* const probe = reinterpret_cast<volatile const u8*>(page);
    const volatile u8 value = *probe;
    (void)value;

    RemoveVectoredExceptionHandler(veh);
    g_read_preflight_page.store(0, std::memory_order_release);

    DWORD restore_old{};
    if (!VirtualProtect(reinterpret_cast<void*>(page), PageSize, PAGE_NOACCESS, &restore_old)) {
        return false;
    }

    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(page), &mbi, sizeof(mbi)) == 0 ||
        mbi.State != MEM_COMMIT || (mbi.Protect & 0xFF) != PAGE_NOACCESS) {
        return false;
    }

    return g_read_preflight_seen.load(std::memory_order_acquire) == 1;
}

LONG CALLBACK D1ObservationVeh(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& record = *exception->ExceptionRecord;

    u32 observation_expected = 0;
    if (g_observation_seen.compare_exchange_strong(observation_expected, 1,
                                                   std::memory_order_acq_rel)) {
        g_first_exception_record.magic = D1ObservationMagic;
        g_first_exception_record.version = D1ObservationVersion;
        g_first_exception_record.exception_code = static_cast<u32>(record.ExceptionCode);
        g_first_exception_record.parameter_count = static_cast<u32>(record.NumberParameters);
        g_first_exception_record.reserved = 0;
        g_first_exception_record.exception_address = reinterpret_cast<u64>(record.ExceptionAddress);
        g_first_exception_record.pc = static_cast<u64>(exception->ContextRecord->Pc);
        g_first_exception_record.sp = static_cast<u64>(exception->ContextRecord->Sp);
        g_first_exception_record.info0 =
            record.NumberParameters >= 1 ? static_cast<u64>(record.ExceptionInformation[0]) : 0;
        g_first_exception_record.info1 =
            record.NumberParameters >= 2 ? static_cast<u64>(record.ExceptionInformation[1]) : 0;

        DWORD bytes_written{};
        WriteFile(g_observation_file, &g_first_exception_record,
                  static_cast<DWORD>(sizeof(g_first_exception_record)), &bytes_written, nullptr);
    }

    if (record.ExceptionCode != EXCEPTION_ACCESS_VIOLATION || record.NumberParameters < 2) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    u32 expected = 0;
    if (g_fault_seen.compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) {
        const u64 access_type = static_cast<u64>(record.ExceptionInformation[0]);
        const u64 fault_address = static_cast<u64>(record.ExceptionInformation[1]);
        const u64 exception_pc = static_cast<u64>(exception->ContextRecord->Pc);
        const u64 exception_sp = static_cast<u64>(exception->ContextRecord->Sp);
        g_fault_access_type.store(access_type, std::memory_order_release);
        g_fault_address.store(fault_address, std::memory_order_release);
        g_exception_pc.store(exception_pc, std::memory_order_release);
        g_exception_sp.store(exception_sp, std::memory_order_release);
    }

    // Observation only. The production NCE VEH owns the fault decision and PC skip.
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008D_D1_PLATFORM_CONTRACT");
#else
    Trace("IMP008D_D1_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008D_D1_NCE_SETTING");
    }
    Trace("IMP008D_D1_NCE_ENABLED");

    Kernel::CodeSet code_set;
    code_set.memory.resize(InitialImageSize);
    auto& code = code_set.CodeSegment();
    code.offset = 0;
    code.addr = Kernel::KProcessAddress{0};
    code.size = static_cast<u32>(PageSize);
    auto& ro = code_set.RODataSegment();
    ro.offset = PageSize;
    ro.addr = Kernel::KProcessAddress{PageSize};
    ro.size = 0;
    auto& data = code_set.DataSegment();
    data.offset = PageSize;
    data.addr = Kernel::KProcessAddress{PageSize};
    data.size = static_cast<u32>(PageSize * StackPages);

    auto* const words = reinterpret_cast<u32*>(code_set.memory.data());
    words[GuestLoadOffset / sizeof(u32)] = GuestLdrX3X2;
    words[GuestSvcOffset / sizeof(u32)] = GuestSvc33;
    words[GuestAfterSvcOffset / sizeof(u32)] = GuestBrk0;
    Trace("IMP008D_D1_CODESET_READY");

    Core::NCE::Patcher patcher;
    if (!patcher.PatchText(code_set.memory, code) ||
        patcher.GetPatchMode() != Core::NCE::PatchMode::PostData || patcher.GetSectionSize() == 0) {
        return Fail("IMP008D_D1_PATCHER");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    Trace("IMP008D_D1_PATCHER_READY");

    Core::System system;
    system.Initialize();
    auto& kernel = system.Kernel();
    kernel.Initialize();

    auto& direct_buffer = system.DeviceMemory().buffer;
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    if (fastmem_base == 0) {
        kernel.Shutdown();
        return Fail("IMP008D_D1_DIRECT_MAP");
    }
    Trace("IMP008D_D1_DIRECT_MAP");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008D_D1_PROCESS_CREATE");
    }

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_PROCESS_LOAD");
    }
    Trace("IMP008D_D1_REAL_APPLICATION_PROCESS");

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_RELOCATE");
    }

    if (code_set.memory.size() < image_size_before_relocate + patch_size) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_PATCH_IMAGE_SIZE");
    }

    const u64 production_getter = static_cast<u64>(reinterpret_cast<uintptr_t>(
        &Core::NCE::GetCurrentNceContextForGeneratedCode));
    const u64 probe_getter =
        static_cast<u64>(reinterpret_cast<uintptr_t>(&D1GeneratedSaveGetterProbe));
    std::size_t getter_literal_matches = 0;
    std::size_t getter_literal_first_offset = 0;
    const std::size_t patch_end = image_size_before_relocate + patch_size;
    for (std::size_t offset = image_size_before_relocate; offset + sizeof(u64) <= patch_end;
         ++offset) {
        u64 candidate{};
        std::memcpy(&candidate, code_set.memory.data() + offset, sizeof(candidate));
        if (candidate != production_getter) {
            continue;
        }
        if (getter_literal_matches == 0) {
            getter_literal_first_offset = offset - image_size_before_relocate;
            std::memcpy(code_set.memory.data() + offset, &probe_getter, sizeof(probe_getter));
        }
        ++getter_literal_matches;
    }
    std::fprintf(stderr,
                 "IMP008D_D1_GENERATED_GETTER_LITERAL_MATCHES=%zu FIRST_OFFSET=0x%zX\n",
                 getter_literal_matches, getter_literal_first_offset);
    std::fflush(stderr);
    if (getter_literal_matches == 0) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_GENERATED_GETTER_REDIRECT");
    }
    // Patcher emits the shared save-context helper before load-context and module trampolines.
    // Redirect only the first getter literal, leaving every later generated helper untouched.
    Trace("IMP008D_D1_GENERATED_SAVE_GETTER_REDIRECT");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008D_D1_MODULE_LOADED");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_THREAD_CREATE");
    }
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_THREAD_OWNER");
    }
    Trace("IMP008D_D1_REAL_KTHREAD");

    Core::ArmInterface* const arm = process->GetArmInterface(0);
    if (arm == nullptr) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_INTERFACE_NULL");
    }

    // Reuse the E1 no-RTTI signature: ArmNce LockThread toggles the native execution lock.
    auto& native = thread->GetNativeExecutionParameters();
    if (native.lock.load(std::memory_order_acquire) != 1) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_LOCK_INITIAL");
    }
    arm->LockThread(thread);
    const bool locked_by_nce = native.lock.load(std::memory_order_acquire) == 0;
    arm->UnlockThread(thread);
    const bool unlocked_by_nce = native.lock.load(std::memory_order_acquire) == 1;
    if (!locked_by_nce || !unlocked_by_nce) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_NCE_SELECTION");
    }
    Trace("IMP008D_D1_NCE_SELECTED");

    const u64 guest_pc = load_base_u64 + GuestLoadOffset;
    const u64 expected_resume_pc = load_base_u64 + GuestSvcOffset;
    const u64 expected_return_pc = load_base_u64 + GuestAfterSvcOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;

    u64 fault_target = 0;
    MEMORY_BASIC_INFORMATION reserved_mbi{};
    for (u64 offset = FaultSearchOffset; offset < FaultSearchLimit; offset += PageSize) {
        const u64 candidate = load_base_u64 + offset;
        MEMORY_BASIC_INFORMATION candidate_mbi{};
        if (IsReservedPage(candidate, candidate_mbi)) {
            fault_target = candidate;
            reserved_mbi = candidate_mbi;
            break;
        }
    }
    if (fault_target == 0) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_FAULT_TARGET_DISCOVERY");
    }

    std::fprintf(stderr,
                 "IMP008D_D1_RESERVED_TARGET=0x%llX STATE=0x%lX PROTECT=0x%lX BASE=%p ALLOC=%p\n",
                 static_cast<unsigned long long>(fault_target),
                 static_cast<unsigned long>(reserved_mbi.State),
                 static_cast<unsigned long>(reserved_mbi.Protect), reserved_mbi.BaseAddress,
                 reserved_mbi.AllocationBase);

    // Commit host backing only. Do not add this page to the guest page table.
    direct_buffer.Map(fault_target, 0, PageSize, Common::MemoryPermission::ReadWrite, false);
    DWORD old_protect{};
    if (!VirtualProtect(reinterpret_cast<void*>(fault_target), PageSize, PAGE_NOACCESS,
                        &old_protect)) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_TARGET_NOACCESS");
    }

    MEMORY_BASIC_INFORMATION target_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(fault_target), &target_mbi,
                     sizeof(target_mbi)) == 0 ||
        target_mbi.State != MEM_COMMIT || (target_mbi.Protect & 0xFF) != PAGE_NOACCESS) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_TARGET_HOST_STATE");
    }

    std::fprintf(stderr,
                 "IMP008D_D1_DATA_TARGET=0x%llX STATE=0x%lX PROTECT=0x%lX BASE=%p ALLOC=%p\n",
                 static_cast<unsigned long long>(fault_target),
                 static_cast<unsigned long>(target_mbi.State),
                 static_cast<unsigned long>(target_mbi.Protect), target_mbi.BaseAddress,
                 target_mbi.AllocationBase);
    std::fprintf(stderr, "IMP008D_D1_ENTRY_PC=0x%llX EXPECTED_RESUME_PC=0x%llX EXPECTED_RETURN_PC=0x%llX\n",
                 static_cast<unsigned long long>(guest_pc),
                 static_cast<unsigned long long>(expected_resume_pc),
                 static_cast<unsigned long long>(expected_return_pc));
    std::fprintf(stderr, "IMP008D_D1_GUEST_SP=0x%llX\n",
                 static_cast<unsigned long long>(guest_sp));
    std::fflush(stderr);
    Trace("IMP008D_D1_GUEST_UNMAPPED_TARGET");

    if (!RunSameAddressReadPreflight(fault_target)) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_READ_AV_PREFLIGHT");
    }
    Trace("IMP008D_D1_READ_AV_PREFLIGHT");

    Kernel::Svc::ThreadContext context{};
    context.r[0] = X0Sentinel;
    context.r[1] = X1Sentinel;
    context.r[2] = fault_target;
    context.r[3] = X3Sentinel;
    context.r[18] = X18Sentinel;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    arm->SetContext(context);
    arm->SetTpidrroEl0(0);
    arm->Initialize();
    arm->ClearInstructionCache();

    const u64 teb = reinterpret_cast<u64>(NtCurrentTeb());
    const u64 physical_x18_before = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008D_D1_TEB=0x%llX\n", static_cast<unsigned long long>(teb));
    std::fprintf(stderr, "IMP008D_D1_PHYSICAL_X18_BEFORE=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_before));
    std::fflush(stderr);
    if (physical_x18_before != teb) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_PHYSICAL_X18_TEB_BEFORE");
    }
    Trace("IMP008D_D1_PHYSICAL_X18_TEB_BEFORE");

    Trace("IMP008D_D1_GUEST_STACK_GETTER_BEFORE");
    Core::NCE::CurrentNceContext::Install(&native);
    void* const guest_stack_getter_result = CallCurrentNceGetterOnGuestStack(guest_sp);
    Core::NCE::CurrentNceContext::Clear();
    const u64 physical_x18_after_getter = ReadPhysicalX18();
    std::fprintf(stderr,
                 "IMP008D_D1_GUEST_STACK_GETTER_RESULT=%p EXPECTED=%p X18=0x%llX TEB=0x%llX\n",
                 guest_stack_getter_result, static_cast<void*>(&native),
                 static_cast<unsigned long long>(physical_x18_after_getter),
                 static_cast<unsigned long long>(teb));
    std::fflush(stderr);
    if (guest_stack_getter_result != static_cast<void*>(&native) ||
        physical_x18_after_getter != teb) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_GUEST_STACK_GETTER_PREFLIGHT");
    }
    Trace("IMP008D_D1_GUEST_STACK_GETTER_PREFLIGHT");

    g_observation_seen.store(0, std::memory_order_release);
    g_fault_seen.store(0, std::memory_order_release);
    g_fault_access_type.store(~0ULL, std::memory_order_release);
    g_fault_address.store(0, std::memory_order_release);
    g_exception_pc.store(0, std::memory_order_release);
    g_exception_sp.store(0, std::memory_order_release);
    g_first_exception_record = {};
    g_register_continue_seen.store(0, std::memory_order_release);

    g_observation_file = CreateFileW(L"imp008d-d1-first-exception.bin", GENERIC_WRITE,
                                     FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, CREATE_ALWAYS,
                                     FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);
    if (g_observation_file == INVALID_HANDLE_VALUE) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_OBSERVATION_FILE_OPEN");
    }
    Trace("IMP008D_D1_OBSERVATION_FILE_READY");

    PVOID const observation_veh = AddVectoredExceptionHandler(1, &D1ObservationVeh);
    if (observation_veh == nullptr) {
        CloseHandle(g_observation_file);
        g_observation_file = INVALID_HANDLE_VALUE;
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_OBSERVATION_VEH");
    }

    PVOID const register_continue_handler =
        AddVectoredContinueHandler(0, &D1ContinueRegisterObservation);
    if (register_continue_handler == nullptr) {
        RemoveVectoredExceptionHandler(observation_veh);
        CloseHandle(g_observation_file);
        g_observation_file = INVALID_HANDLE_VALUE;
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_REGISTER_CONTINUE_HANDLER");
    }
    Trace("IMP008D_D1_REGISTER_CONTINUE_HANDLER_READY");

    Trace("IMP008D_D1_PRE_RUNTHREAD");
    arm->LockThread(thread);
    const Core::HaltReason halt_reason = arm->RunThread(thread);
    arm->UnlockThread(thread);
    RemoveVectoredExceptionHandler(observation_veh);
    RemoveVectoredContinueHandler(register_continue_handler);
    FlushFileBuffers(g_observation_file);
    CloseHandle(g_observation_file);
    g_observation_file = INVALID_HANDLE_VALUE;
    Trace("IMP008D_D1_RUNTHREAD_RETURNED");

    const u64 physical_x18_after = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008D_D1_PHYSICAL_X18_AFTER=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_after));
    std::fflush(stderr);

    if (g_observation_seen.load(std::memory_order_acquire) != 1 ||
        g_fault_seen.load(std::memory_order_acquire) != 1 ||
        g_fault_access_type.load(std::memory_order_acquire) != 0 ||
        g_fault_address.load(std::memory_order_acquire) != fault_target ||
        g_exception_pc.load(std::memory_order_acquire) != guest_pc ||
        g_exception_sp.load(std::memory_order_acquire) != guest_sp) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_DATA_AV");
    }
    Trace("IMP008D_D1_DATA_AV");

    if (guest_pc == fault_target) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_PC_NE_FAULT");
    }
    Trace("IMP008D_D1_PC_NE_FAULT");

    if (!True(halt_reason & Core::HaltReason::SupervisorCall)) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_SUPERVISOR_CALL_RETURN");
    }
    Trace("IMP008D_D1_SUPERVISOR_CALL_RETURN");

    const u32 svc_number = arm->GetSvcNumber();
    std::fprintf(stderr, "IMP008D_D1_SVC_NUMBER=0x%X\n", svc_number);
    std::fflush(stderr);
    if (svc_number != 0x33) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext returned{};
    arm->GetContext(returned);
    std::fprintf(stderr,
                 "IMP008D_D1_RETURNED PC=0x%llX SP=0x%llX X0=0x%llX X1=0x%llX X2=0x%llX X3=0x%llX X18=0x%llX\n",
                 static_cast<unsigned long long>(returned.pc),
                 static_cast<unsigned long long>(returned.sp),
                 static_cast<unsigned long long>(returned.r[0]),
                 static_cast<unsigned long long>(returned.r[1]),
                 static_cast<unsigned long long>(returned.r[2]),
                 static_cast<unsigned long long>(returned.r[3]),
                 static_cast<unsigned long long>(returned.r[18]));
    std::fflush(stderr);

    if (returned.pc != expected_return_pc) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_SKIP_PC_EXACT");
    }
    Trace("IMP008D_D1_SKIP_PC_EXACT");

    if (returned.r[3] != X3Sentinel) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_X3_SENTINEL");
    }
    Trace("IMP008D_D1_X3_SENTINEL");

    if (returned.sp != guest_sp || returned.r[0] != X0Sentinel ||
        returned.r[1] != X1Sentinel || returned.r[2] != fault_target ||
        returned.r[18] != X18Sentinel) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_CONTEXT_COHERENT");
    }
    Trace("IMP008D_D1_CONTEXT_COHERENT");

    if (physical_x18_after != teb) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008D_D1_PHYSICAL_X18_TEB_AFTER");
    }
    Trace("IMP008D_D1_PHYSICAL_X18_TEB_AFTER");

    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    Trace("IMP008D_D1_GATE");
    return 0;
#endif
}
