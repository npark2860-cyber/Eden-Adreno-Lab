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
#include "core/core.h"
#include "core/device_memory.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/code_set.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/kernel.h"
#include "core/memory.h"
#include "video_core/host1x/gpu_device_memory_manager.h"

namespace {

constexpr std::size_t PageSize = 0x1000;
constexpr std::size_t ImagePages = 2;
constexpr std::size_t InitialImageSize = PageSize * ImagePages;
constexpr DAddr DeviceAddress = 0x1000;
constexpr u64 InitialSentinel = 0x1122334455667788ULL;
constexpr u64 WriteSentinel = 0x8877665544332211ULL;
constexpr u32 GuestNop = 0xD503201FU;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
bool QueryProtection(u64 address, DWORD expected, MEMORY_BASIC_INFORMATION* observed = nullptr) {
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) == 0) {
        return false;
    }
    if (observed != nullptr) {
        *observed = mbi;
    }
    return mbi.State == MEM_COMMIT && (mbi.Protect & 0xFFU) == expected;
}

void PrintProtection(const char* marker, u64 address) {
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) == 0) {
        std::fprintf(stderr, "%s ADDRESS=0x%llX QUERY=FAIL ERROR=%lu\n", marker,
                     static_cast<unsigned long long>(address),
                     static_cast<unsigned long>(GetLastError()));
        std::fflush(stderr);
        return;
    }
    std::fprintf(stderr,
                 "%s ADDRESS=0x%llX STATE=0x%lX PROTECT=0x%lX TYPE=0x%lX BASE=%p ALLOC=%p\n",
                 marker, static_cast<unsigned long long>(address),
                 static_cast<unsigned long>(mbi.State),
                 static_cast<unsigned long>(mbi.Protect),
                 static_cast<unsigned long>(mbi.Type), mbi.BaseAddress, mbi.AllocationBase);
    std::fflush(stderr);
}
#endif

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008E_E1_PLATFORM_CONTRACT");
#else
    Trace("IMP008E_E1_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    Settings::values.use_reactive_flushing.SetValue(true);
    if (!Settings::IsNceEnabled() || !Settings::values.use_reactive_flushing.GetValue()) {
        return Fail("IMP008E_E1_SETTINGS");
    }
    Trace("IMP008E_E1_SETTINGS_READY");

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
    data.size = static_cast<u32>(PageSize);
    *reinterpret_cast<u32*>(code_set.memory.data()) = GuestNop;

    Core::System system;
    system.Initialize();
    auto& kernel = system.Kernel();
    kernel.Initialize();

    auto& direct_buffer = system.DeviceMemory().buffer;
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    if (fastmem_base == 0) {
        kernel.Shutdown();
        return Fail("IMP008E_E1_DIRECT_MAP");
    }
    Trace("IMP008E_E1_DIRECT_MAP");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008E_E1_PROCESS_CREATE");
    }

    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, InitialImageSize, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_PROCESS_LOAD");
    }
    Trace("IMP008E_E1_REAL_APPLICATION_PROCESS");

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    process->LoadModule(kernel, std::move(code_set), load_base);

    const u64 target = load_base_u64 + PageSize;
    auto& process_memory = process->GetMemory();
    u8* const backing_ptr = process_memory.GetPointerSilent(Common::ProcessAddress{target});
    if (backing_ptr == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_TARGET_BACKING");
    }

    auto* const fastmem_ptr = reinterpret_cast<volatile u64*>(target);
    *fastmem_ptr = InitialSentinel;
    if (*fastmem_ptr != InitialSentinel) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_INITIAL_SENTINEL");
    }

    PrintProtection("IMP008E_E1_INITIAL_PROTECTION", target);
    if (!QueryProtection(target, PAGE_READWRITE)) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_INITIAL_RW");
    }
    Trace("IMP008E_E1_INITIAL_RW");

    Tegra::MaxwellDeviceMemoryManager device_memory(system.DeviceMemory());
    const Core::Asid asid = device_memory.RegisterProcess(&process_memory);
    Trace("IMP008E_E1_DEVICE_PROCESS_REGISTERED");

    device_memory.AllocateFixed(DeviceAddress, PageSize);
    device_memory.Map(DeviceAddress, target, PageSize, asid, false);
    u8* const device_ptr = device_memory.GetPointer<u8>(DeviceAddress);
    if (device_ptr == nullptr || device_ptr != backing_ptr) {
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_DEVICE_MAPPING");
    }
    Trace("IMP008E_E1_DEVICE_MAPPING");

    device_memory.UpdatePagesCachedCount(DeviceAddress, PageSize, +1);
    Trace("IMP008E_E1_CACHE_APPLIED");

    PrintProtection("IMP008E_E1_CACHED_PROTECTION", target);
    if (!QueryProtection(target, PAGE_NOACCESS)) {
        device_memory.UpdatePagesCachedCount(DeviceAddress, PageSize, -1);
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_CACHED_NOACCESS");
    }
    Trace("IMP008E_E1_CACHED_NOACCESS");

    // The backing alias must remain valid while the guest fastmem view is protected.
    u64 backing_value{};
    std::memcpy(&backing_value, backing_ptr, sizeof(backing_value));
    if (backing_value != InitialSentinel) {
        device_memory.UpdatePagesCachedCount(DeviceAddress, PageSize, -1);
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_CACHED_BACKING");
    }
    Trace("IMP008E_E1_CACHED_BACKING");

    device_memory.UpdatePagesCachedCount(DeviceAddress, PageSize, -1);
    Trace("IMP008E_E1_UNCACHE_APPLIED");

    PrintProtection("IMP008E_E1_RECOVERED_PROTECTION", target);
    if (!QueryProtection(target, PAGE_READWRITE)) {
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_RECOVERED_RW");
    }
    Trace("IMP008E_E1_RECOVERED_RW");

    if (*fastmem_ptr != InitialSentinel) {
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_READ_SENTINEL");
    }
    Trace("IMP008E_E1_READ_SENTINEL");

    *fastmem_ptr = WriteSentinel;
    if (*fastmem_ptr != WriteSentinel) {
        device_memory.UnregisterProcess(asid);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008E_E1_WRITE_READBACK");
    }
    Trace("IMP008E_E1_WRITE_READBACK");

    device_memory.UnregisterProcess(asid);
    process->Close(kernel);
    kernel.Shutdown();

    Trace("IMP008E_E1_GATE");
    return 0;
#endif
}
