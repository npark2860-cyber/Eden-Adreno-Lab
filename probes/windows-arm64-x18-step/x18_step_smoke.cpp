// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <array>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <optional>

#include "common/logging.h"
#include "dynarmic/interface/A64/a64.h"

void AssertFailSoftImpl() {}
[[noreturn]] void AssertFatalImpl() {
    std::abort();
}

namespace Common::Log {
void FmtLogMessageImpl(Class, Level, const char*, unsigned int, const char*, fmt::string_view,
                       const fmt::format_args&) {}
} // namespace Common::Log

namespace {

constexpr std::uint64_t Pc = 0x1000;
constexpr std::uint64_t BranchTarget = 0x2000;
constexpr std::uint64_t DataAddress = 0x3000;
constexpr std::uint32_t NzcvMask = 0xF0000000u;

constexpr std::uint32_t AddReadX18 = 0x8B010240u;       // ADD X0, X18, X1
constexpr std::uint32_t AddWriteX18 = 0x8B010012u;      // ADD X18, X0, X1
constexpr std::uint32_t AddsReadX18 = 0xAB010240u;      // ADDS X0, X18, X1
constexpr std::uint32_t BrX18 = 0xD61F0240u;            // BR X18
constexpr std::uint32_t MrsX18Tpidr = 0xD53BD052u;      // MRS X18, TPIDR_EL0
constexpr std::uint32_t MrsX18Tpidrro = 0xD53BD072u;    // MRS X18, TPIDRRO_EL0
constexpr std::uint32_t LdrX0FromX18 = 0xF9400240u;     // LDR X0, [X18]
constexpr std::uint32_t LdrX18FromX0 = 0xF9400012u;     // LDR X18, [X0]
constexpr std::uint32_t StrX18ToX0 = 0xF9000012u;       // STR X18, [X0]
constexpr std::uint32_t LdarX0FromX18 = 0xC8DFFE40u;    // LDAR X0, [X18]

class Callbacks final : public Dynarmic::A64::UserCallbacks {
public:
    std::optional<std::uint32_t> MemoryReadCode(std::uint64_t vaddr) override {
        const auto it = code.find(vaddr);
        if (it == code.end()) {
            return std::nullopt;
        }
        return it->second;
    }

    std::uint8_t MemoryRead8(std::uint64_t vaddr) override {
        return Read<std::uint8_t>(vaddr);
    }
    std::uint16_t MemoryRead16(std::uint64_t vaddr) override {
        return Read<std::uint16_t>(vaddr);
    }
    std::uint32_t MemoryRead32(std::uint64_t vaddr) override {
        return Read<std::uint32_t>(vaddr);
    }
    std::uint64_t MemoryRead64(std::uint64_t vaddr) override {
        return Read<std::uint64_t>(vaddr);
    }
    Dynarmic::A64::Vector MemoryRead128(std::uint64_t vaddr) override {
        return {Read<std::uint64_t>(vaddr), Read<std::uint64_t>(vaddr + 8)};
    }

    void MemoryWrite8(std::uint64_t vaddr, std::uint8_t value) override {
        Write(vaddr, value);
    }
    void MemoryWrite16(std::uint64_t vaddr, std::uint16_t value) override {
        Write(vaddr, value);
    }
    void MemoryWrite32(std::uint64_t vaddr, std::uint32_t value) override {
        Write(vaddr, value);
    }
    void MemoryWrite64(std::uint64_t vaddr, std::uint64_t value) override {
        Write(vaddr, value);
    }
    void MemoryWrite128(std::uint64_t vaddr, Dynarmic::A64::Vector value) override {
        Write(vaddr, value[0]);
        Write(vaddr + 8, value[1]);
    }

    void CallSVC(std::uint32_t) override {
        svc_seen = true;
    }
    void ExceptionRaised(std::uint64_t, Dynarmic::A64::Exception) override {
        exception_seen = true;
    }
    void AddTicks(std::uint64_t ticks) override {
        elapsed_ticks += ticks;
    }
    std::uint64_t GetTicksRemaining() override {
        return 100000;
    }
    std::uint64_t GetCNTPCT() override {
        return elapsed_ticks;
    }

    template <typename T>
    T Read(std::uint64_t vaddr) const {
        T value{};
        const auto it = data.find(vaddr);
        if (it != data.end()) {
            std::memcpy(&value, it->second.data(), sizeof(T));
        }
        return value;
    }

    template <typename T>
    void Write(std::uint64_t vaddr, T value) {
        std::array<std::uint8_t, 16> bytes{};
        std::memcpy(bytes.data(), &value, sizeof(T));
        data.insert_or_assign(vaddr, bytes);
    }

    std::map<std::uint64_t, std::uint32_t> code;
    std::map<std::uint64_t, std::array<std::uint8_t, 16>> data;
    std::uint64_t tpidr{};
    std::uint64_t tpidrro{};
    std::uint64_t elapsed_ticks{};
    bool svc_seen{};
    bool exception_seen{};
};

struct Probe {
    Callbacks callbacks;
    Dynarmic::A64::Jit jit;

    Probe()
        : jit([this] {
              Dynarmic::A64::UserConfig config{};
              config.callbacks = &callbacks;
              config.tpidr_el0 = &callbacks.tpidr;
              config.tpidrro_el0 = &callbacks.tpidrro;
              config.code_cache_size = 8 * 1024 * 1024;
              config.enable_cycle_counting = false;
              return config;
          }()) {}

    bool Step(std::uint32_t instruction, std::uint64_t pc = Pc) {
        callbacks.code.insert_or_assign(pc, instruction);
        jit.InvalidateCacheRange(pc, sizeof(instruction));
        jit.SetPC(pc);
        callbacks.exception_seen = false;
        jit.Step();
        return !callbacks.exception_seen;
    }
};

bool Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
    return pass;
}

} // namespace

int main() {
    Probe probe;
    bool pass = true;

    probe.jit.SetRegister(18, 5);
    probe.jit.SetRegister(1, 7);
    pass &= Report("STEP_ADD_READ_X18",
                   probe.Step(AddReadX18) && probe.jit.GetRegister(0) == 12 &&
                       probe.jit.GetPC() == Pc + 4);

    probe.jit.SetRegister(0, 20);
    probe.jit.SetRegister(1, 22);
    pass &= Report("STEP_ADD_WRITE_X18",
                   probe.Step(AddWriteX18) && probe.jit.GetRegister(18) == 42);

    probe.jit.SetRegister(18, BranchTarget);
    pass &= Report("STEP_BR_X18", probe.Step(BrX18) && probe.jit.GetPC() == BranchTarget);

    probe.callbacks.tpidr = 0x1122334455667788ull;
    probe.jit.SetRegister(18, 0);
    pass &= Report("STEP_MRS_X18_TPIDR",
                   probe.Step(MrsX18Tpidr) &&
                       probe.jit.GetRegister(18) == probe.callbacks.tpidr);

    probe.callbacks.tpidrro = 0x8877665544332211ull;
    probe.jit.SetRegister(18, 0);
    pass &= Report("STEP_MRS_X18_TPIDRRO",
                   probe.Step(MrsX18Tpidrro) &&
                       probe.jit.GetRegister(18) == probe.callbacks.tpidrro);

    probe.jit.SetRegister(18, ~std::uint64_t{0});
    probe.jit.SetRegister(1, 1);
    probe.jit.SetPstate(0);
    pass &= Report("STEP_ADDS_X18_NZCV",
                   probe.Step(AddsReadX18) && probe.jit.GetRegister(0) == 0 &&
                       (probe.jit.GetPstate() & NzcvMask) == 0x60000000u);

    constexpr std::uint64_t LoadValue = 0xA1B2C3D4E5F60718ull;
    probe.callbacks.Write(DataAddress, LoadValue);
    probe.jit.SetRegister(18, DataAddress);
    probe.jit.SetRegister(0, 0);
    pass &= Report("STEP_LDR_X18_BASE",
                   probe.Step(LdrX0FromX18) && probe.jit.GetRegister(0) == LoadValue);

    probe.jit.SetRegister(0, DataAddress);
    probe.jit.SetRegister(18, 0);
    pass &= Report("STEP_LDR_RESULT_X18",
                   probe.Step(LdrX18FromX0) && probe.jit.GetRegister(18) == LoadValue);

    constexpr std::uint64_t StoreAddress = DataAddress + 0x20;
    constexpr std::uint64_t StoreValue = 0x0102030405060718ull;
    probe.jit.SetRegister(0, StoreAddress);
    probe.jit.SetRegister(18, StoreValue);
    pass &= Report("STEP_STR_DATA_X18",
                   probe.Step(StrX18ToX0) &&
                       probe.callbacks.Read<std::uint64_t>(StoreAddress) == StoreValue);

    probe.jit.SetRegister(18, DataAddress);
    probe.jit.SetRegister(0, 0);
    pass &= Report("STEP_LDAR_X18_BASE",
                   probe.Step(LdarX0FromX18) && probe.jit.GetRegister(0) == LoadValue);

    std::printf("X18_DYNARMIC_STEP_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
