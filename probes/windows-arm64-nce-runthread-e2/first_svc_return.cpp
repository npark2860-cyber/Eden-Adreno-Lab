#include <cstddef>
#include <cstdint>
#include <iostream>
#include <utility>

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/arm/nce/patcher.h"
#include "core/core.h"
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
constexpr std::size_t InitialImageSize = PageSize * 2;
constexpr std::size_t GuestCodeOffset = 0x24;
constexpr std::size_t GuestSvcOffset = 0x28;
constexpr std::size_t GuestAfterSvcOffset = 0x2c;
constexpr u32 GuestAddX0One = 0x91000400; // add x0, x0, #1
constexpr u32 GuestSvc33 = 0xD4000661;    // svc #0x33
constexpr u32 GuestBrk0 = 0xD4200000;     // must never execute in E2

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cerr << marker << "=PASS\n" << std::flush;
}

std::size_t PageAlign(std::size_t value) {
    return (value + PageSize - 1) & ~(PageSize - 1);
}

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008B_E2_PLATFORM_CONTRACT");
#else
    Trace("IMP008B_E2_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008B_E2_NCE_SETTING");
    }
    Trace("IMP008B_E2_SETTINGS_READY");

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

    auto* const words = reinterpret_cast<u32*>(code_set.memory.data());
    words[GuestCodeOffset / sizeof(u32)] = GuestAddX0One;
    words[GuestSvcOffset / sizeof(u32)] = GuestSvc33;
    words[GuestAfterSvcOffset / sizeof(u32)] = GuestBrk0;
    Trace("IMP008B_E2_CODESET_READY");

    Core::NCE::Patcher patcher;
    Trace("IMP008B_E2_PATCH_BEGIN");
    if (!patcher.PatchText(code_set.memory, code)) {
        return Fail("IMP008B_E2_PATCH_TEXT");
    }
    if (patcher.GetPatchMode() != Core::NCE::PatchMode::PostData) {
        return Fail("IMP008B_E2_PATCH_MODE");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    if (patch_size == 0) {
        return Fail("IMP008B_E2_PATCH_SIZE");
    }
    Trace("IMP008B_E2_PATCH_READY");

    Core::System system;
    Trace("IMP008B_E2_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008B_E2_SYSTEM_INIT_DONE");
    auto& kernel = system.Kernel();
    Trace("IMP008B_E2_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008B_E2_KERNEL_INIT_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E2_PROCESS_CREATE");
    }
    Trace("IMP008B_E2_PROCESS_CREATED");

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008B_E2_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{0}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_PROCESS_LOAD");
    }
    Trace("IMP008B_E2_PROCESS_LOAD_DONE");
    std::cout << "IMP008B_E2_REAL_PROCESS=PASS\n" << std::flush;

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();
    Trace("IMP008B_E2_RELOCATE_BEGIN");
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_RELOCATE");
    }
    Trace("IMP008B_E2_RELOCATE_DONE");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);

    Trace("IMP008B_E2_LOAD_MODULE_BEGIN");
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008B_E2_LOAD_MODULE_DONE");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_THREAD_CREATE");
    }
    Trace("IMP008B_E2_THREAD_CREATED");
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_THREAD_OWNER");
    }
    Trace("IMP008B_E2_THREAD_INIT_DONE");
    std::cout << "IMP008B_E2_REAL_KTHREAD=PASS\n" << std::flush;

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_INTERFACE_NULL");
    }

    const u64 guest_pc = load_base_u64 + GuestCodeOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;

    Kernel::Svc::ThreadContext context{};
    context.r[0] = 0x41;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    Trace("IMP008B_E2_CONTEXT_SET_BEGIN");
    interface->SetContext(context);
    interface->SetTpidrroEl0(0);
    interface->Initialize();
    interface->ClearInstructionCache();
    Trace("IMP008B_E2_CONTEXT_SET_DONE");

    std::cout << "IMP008B_E2_PRE_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008B_E2_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    if (!True(halt_reason & Core::HaltReason::SupervisorCall)) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_HALT_REASON");
    }
    if (interface->GetSvcNumber() != 0x33) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext returned{};
    interface->GetContext(returned);
    if (returned.r[0] != 0x42) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_GUEST_EXECUTED");
    }
    if (returned.pc != load_base_u64 + GuestAfterSvcOffset) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_RETURN_PC");
    }
    if (returned.sp != guest_sp) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E2_RETURN_SP");
    }

    std::cout << "IMP008B_E2_GUEST_ENTERED=PASS\n";
    std::cout << "IMP008B_E2_FIRST_SVC_RETURN=PASS\n";
    std::cout << "IMP008B_E2_CONTEXT_COHERENT=PASS\n" << std::flush;

    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    std::cout << "IMP008B_E2_GATE=PASS\n" << std::flush;
    return 0;
#endif
}
