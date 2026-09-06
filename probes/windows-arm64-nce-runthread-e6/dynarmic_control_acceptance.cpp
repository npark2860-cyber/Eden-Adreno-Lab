#include <cstddef>
#include <iostream>

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/nce/arm_nce.h"
#include "core/core.h"
#include "core/device_memory.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/kernel.h"

namespace {

constexpr std::size_t PageSize = 0x1000;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008B_E6_PLATFORM_CONTRACT");
#else
    Trace("IMP008B_E6_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Dynarmic);
    Settings::SetNceEnabled(true);
    if (Settings::values.cpu_backend.GetValue() != Settings::CpuBackend::Dynarmic) {
        return Fail("IMP008B_E6_DYNARMIC_SETTING");
    }
    if (Settings::IsNceEnabled()) {
        return Fail("IMP008B_E6_NCE_DISABLED");
    }
    Trace("IMP008B_E6_DYNARMIC_SELECTED");
    Trace("IMP008B_E6_NCE_DISABLED");

    Core::System system;
    Trace("IMP008B_E6_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008B_E6_SYSTEM_INIT_DONE");

    auto& kernel = system.Kernel();
    Trace("IMP008B_E6_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008B_E6_KERNEL_INIT_DONE");

    auto& direct_buffer = system.DeviceMemory().buffer;
    Trace("IMP008B_E6_DIRECT_MAP_BEGIN");
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    if (fastmem_base == 0) {
        kernel.Shutdown();
        return Fail("IMP008B_E6_DIRECT_MAP");
    }
    Trace("IMP008B_E6_DIRECT_MAP_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E6_PROCESS_CREATE");
    }
    Trace("IMP008B_E6_PROCESS_CREATED");

    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008B_E6_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, PageSize, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_PROCESS_LOAD");
    }
    Trace("IMP008B_E6_PROCESS_LOAD_DONE");

    if (!process->IsApplication()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_APPLICATION_PROCESS");
    }
    if (!process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_64BIT_PROCESS");
    }
    Trace("IMP008B_E6_REAL_APPLICATION_PROCESS");
    Trace("IMP008B_E6_64BIT_PROCESS");

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_INTERFACE_NULL");
    }
    Trace("IMP008B_E6_PROCESS_OWNED_INTERFACE");

    auto* const dynarmic64 = dynamic_cast<Core::ArmDynarmic64*>(interface);
    auto* const nce = dynamic_cast<Core::ArmNce*>(interface);
    if (dynarmic64 == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_DYNARMIC64_BACKEND");
    }
    if (nce != nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_NOT_NCE_BACKEND");
    }
    if (dynarmic64->GetArchitecture() != Core::Architecture::AArch64) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E6_AARCH64_BACKEND");
    }

    Trace("IMP008B_E6_DYNARMIC64_BACKEND");
    Trace("IMP008B_E6_NOT_NCE_BACKEND");
    Trace("IMP008B_E6_AARCH64_BACKEND");

    process->Close(kernel);
    kernel.Shutdown();

    Trace("IMP008B_E6_GATE");
    return 0;
#endif
}
