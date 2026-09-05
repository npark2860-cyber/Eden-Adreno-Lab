#include <iostream>

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/core.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/kernel.h"

namespace {

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n";
    return 1;
}

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008B_E1_PLATFORM_CONTRACT");
#else
    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008B_E1_NCE_SETTING");
    }

    Core::System system;
    system.Initialize();
    auto& kernel = system.Kernel();
    kernel.Initialize();

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E1_PROCESS_CREATE");
    }

    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    const Result load_result =
        process->LoadFromMetadata(kernel, metadata, 0x1000, Kernel::KProcessAddress{0}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_PROCESS_LOAD");
    }
    std::cout << "IMP008B_E1_REAL_PROCESS=PASS\n";

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_THREAD_CREATE");
    }

    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_THREAD_OWNER");
    }
    std::cout << "IMP008B_E1_REAL_KTHREAD=PASS\n";

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_INTERFACE_NULL");
    }

    auto& native = thread->GetNativeExecutionParameters();
    if (native.lock.load(std::memory_order_acquire) != 1) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_LOCK_INITIAL");
    }

    interface->LockThread(thread);
    const bool locked_by_nce = native.lock.load(std::memory_order_acquire) == 0;
    interface->UnlockThread(thread);
    const bool unlocked_by_nce = native.lock.load(std::memory_order_acquire) == 1;
    if (!locked_by_nce || !unlocked_by_nce) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E1_NCE_LOCK_SIGNATURE");
    }
    std::cout << "IMP008B_E1_NCE_SELECTED=PASS\n";

    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    std::cout << "IMP008B_E1_PRODUCT_LINK_RUN=PASS\n";
    return 0;
#endif
}
