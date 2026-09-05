// SPDX-FileCopyrightText: Copyright 2023 yuzu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <memory>
#include <mutex>

#include "core/arm/arm_interface.h"
#include "core/arm/nce/guest_context.h"

namespace Core::Memory {
class Memory;
}

namespace Core::NCE {
#if defined(_WIN32)
class WindowsCrossThreadBreak;
class WindowsX18FallbackRunner;
#endif
} // namespace Core::NCE

namespace Core {

class System;

class ArmNce final : public ArmInterface {
public:
    ArmNce(System& system, bool uses_wall_clock, std::size_t core_index);
    ~ArmNce() override;

    void Initialize() override;

    Architecture GetArchitecture() const override {
        return Architecture::AArch64;
    }

    HaltReason RunThread(Kernel::KThread* thread) override;
    HaltReason StepThread(Kernel::KThread* thread) override;

    void GetContext(Kernel::Svc::ThreadContext& ctx) const override;
    void SetContext(const Kernel::Svc::ThreadContext& ctx) override;
    void SetTpidrroEl0(u64 value) override;

    void GetSvcArguments(std::span<uint64_t, 8> args) const override;
    void SetSvcArguments(std::span<const uint64_t, 8> args) override;
    u32 GetSvcNumber() const override;

    void SignalInterrupt(Kernel::KThread* thread) override;
    void ClearInstructionCache() override;
    void InvalidateCacheRange(u64 addr, std::size_t size) override;

    void LockThread(Kernel::KThread* thread) override;
    void UnlockThread(Kernel::KThread* thread) override;

protected:
    const Kernel::DebugWatchpoint* HaltedWatchpoint() const override {
        return nullptr;
    }

    void RewindBreakpointInstruction() override {}

private:
#if !defined(_WIN32)
    // Linux/Android assembly and signal definitions.
    static HaltReason ReturnToRunCodeByTrampoline(void* tpidr, GuestContext* ctx,
                                                  u64 trampoline_addr);
    static HaltReason ReturnToRunCodeByExceptionLevelChange(int tid, void* tpidr);

    static void ReturnToRunCodeByExceptionLevelChangeSignalHandler(int sig, void* info,
                                                                   void* raw_context);
    static void BreakFromRunCodeSignalHandler(int sig, void* info, void* raw_context);
    static void GuestAlignmentFaultSignalHandler(int sig, void* info, void* raw_context);
    static void GuestAccessFaultSignalHandler(int sig, void* info, void* raw_context);

    // C++ implementation functions for Linux/Android assembly definitions.
    static void* RestoreGuestContext(void* raw_context);
    static void SaveGuestContext(GuestContext* ctx, void* raw_context);
    static bool HandleFailedGuestFault(GuestContext* ctx, void* info, void* raw_context);
    static bool HandleGuestAlignmentFault(GuestContext* ctx, void* info, void* raw_context);
    static bool HandleGuestAccessFault(GuestContext* ctx, void* info, void* raw_context);
    static void HandleHostAlignmentFault(int sig, void* info, void* raw_context);
    static void HandleHostAccessFault(int sig, void* info, void* raw_context);
#endif

    // NativeExecutionParameters synchronization exists on both host platforms. Linux/Android use
    // the existing AArch64 assembly implementation; Windows provides the equivalent C++ atomic
    // implementation in arm_nce_windows.cpp.
    static void LockThreadParameters(void* tpidr);
    static void UnlockThreadParameters(void* tpidr);

public:
    Core::System& m_system;

    // Members set on initialization.
    std::size_t m_core_index{};
#if defined(_WIN32)
    std::unique_ptr<NCE::WindowsCrossThreadBreak> m_windows_break{};
    std::unique_ptr<NCE::WindowsX18FallbackRunner> m_windows_x18_runner{};
#else
    pid_t m_thread_id{-1};
#endif

    // Core context.
    GuestContext m_guest_ctx{};
    Kernel::KThread* m_running_thread{};

#if !defined(_WIN32)
    // Stack for POSIX signal processing.
    std::unique_ptr<u8[]> m_stack{};
#endif
};

} // namespace Core
