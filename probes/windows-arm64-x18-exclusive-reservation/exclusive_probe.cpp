#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>

#include <cstdint>
#include <cstdio>

#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_nce_transition.h"
#include "core/arm/nce/windows_x18_exclusive.h"

using Core::NCE::BuildWindowsX18ExclusivePlan;
using Core::NCE::CurrentNceContext;
using Core::NCE::Exclusive;

extern "C" std::uint32_t Imp007ExclusiveGetterProbe(std::uint64_t* target, void** observed);
extern "C" std::uint32_t Imp007ExclusiveFullSaveProbe(std::uint64_t* target, void** observed);
extern "C" std::uint32_t Imp007ExclusiveAcquireReleaseProbe(std::uint64_t* target,
                                                              void** observed);
extern "C" std::uint32_t Imp007ExclusiveClrexProbe(std::uint64_t* target);
extern "C" std::uint32_t Imp007ExclusiveMismatchProbe(std::uint64_t* reserved,
                                                        std::uint64_t* other);

namespace {

constexpr std::uint64_t InitialValue = 0x1122334455667788ull;
constexpr unsigned Attempts = 4096;

alignas(64) std::uint64_t target{};
alignas(64) std::uint64_t other{};
std::uint64_t context_sentinel{};
void* observed{};

bool RunUntilSuccess(std::uint32_t (*probe)(std::uint64_t*, void**)) {
    for (unsigned i = 0; i < Attempts; ++i) {
        observed = nullptr;
        if (probe(&target, &observed) == 0) {
            return true;
        }
    }
    return false;
}

void Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
}

} // namespace

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    const bool x18_before = __getReg(18) == teb;

    const auto x18_base_plan = BuildWindowsX18ExclusivePlan(Exclusive{0xC85F7E40});
    const auto x18_result_plan = BuildWindowsX18ExclusivePlan(Exclusive{0xC85F7C12});
    const bool plan_base_ok = x18_base_plan && x18_base_plan->reads_x18 &&
                              !x18_base_plan->writes_x18 &&
                              x18_base_plan->rewritten_instruction == 0xC85FFE60;
    const bool plan_result_ok = x18_result_plan && !x18_result_plan->reads_x18 &&
                                x18_result_plan->writes_x18 &&
                                x18_result_plan->value_scratch != x18_result_plan->context_scratch;

    auto* expected_context =
        reinterpret_cast<CurrentNceContext::Parameters*>(&context_sentinel);
    CurrentNceContext::Install(expected_context);

    target = InitialValue;
    const bool relaxed_success = RunUntilSuccess(&Imp007ExclusiveGetterProbe);
    const bool getter_ok = observed == expected_context;
    const bool relaxed_value_ok = target == InitialValue + 1;

    target = InitialValue;
    const bool full_save_success = RunUntilSuccess(&Imp007ExclusiveFullSaveProbe);
    const bool full_save_getter_ok = observed == expected_context;
    const bool full_save_value_ok = target == InitialValue + 1;

    target = InitialValue;
    const bool acq_rel_success = RunUntilSuccess(&Imp007ExclusiveAcquireReleaseProbe);
    const bool acq_rel_getter_ok = observed == expected_context;
    const bool acq_rel_value_ok = target == InitialValue + 1;

    target = InitialValue;
    const std::uint32_t clrex_status = Imp007ExclusiveClrexProbe(&target);
    const bool clrex_failed = clrex_status != 0 && target == InitialValue;

    target = InitialValue;
    other = 0x8877665544332211ull;
    const std::uint64_t other_before = other;
    const std::uint32_t mismatch_status = Imp007ExclusiveMismatchProbe(&target, &other);
    const bool mismatch_failed = mismatch_status != 0 && target == InitialValue &&
                                 other == other_before;

    CurrentNceContext::Clear();
    const bool x18_after = __getReg(18) == teb;

    Report("X18_TEB_BEFORE", x18_before);
    Report("X18_EXCLUSIVE_BASE_PLAN", plan_base_ok);
    Report("X18_EXCLUSIVE_RESULT_PLAN", plan_result_ok);
    Report("TLS_GETTER_RESERVATION_SURVIVES", relaxed_success);
    Report("TLS_GETTER_CONTEXT_OK", getter_ok);
    Report("RELAXED_EXCLUSIVE_VALUE_OK", relaxed_value_ok);
    Report("FULL_SAVE_GETTER_RESERVATION_SURVIVES", full_save_success);
    Report("FULL_SAVE_GETTER_CONTEXT_OK", full_save_getter_ok);
    Report("FULL_SAVE_EXCLUSIVE_VALUE_OK", full_save_value_ok);
    Report("ACQ_REL_TLS_GETTER_RESERVATION_SURVIVES", acq_rel_success);
    Report("ACQ_REL_TLS_GETTER_CONTEXT_OK", acq_rel_getter_ok);
    Report("ACQ_REL_EXCLUSIVE_VALUE_OK", acq_rel_value_ok);
    Report("CLREX_FORCES_STXR_FAILURE", clrex_failed);
    Report("ADDRESS_MISMATCH_STXR_FAILURE", mismatch_failed);
    Report("X18_TEB_AFTER", x18_after);

    const bool pass = x18_before && plan_base_ok && plan_result_ok && relaxed_success && getter_ok &&
                      relaxed_value_ok && full_save_success && full_save_getter_ok &&
                      full_save_value_ok && acq_rel_success && acq_rel_getter_ok &&
                      acq_rel_value_ok && clrex_failed && mismatch_failed && x18_after;
    std::printf("IMP007_NATIVE_EXCLUSIVE_RESERVATION_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
