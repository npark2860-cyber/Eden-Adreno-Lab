from pathlib import Path
import sys

arm_path = Path(sys.argv[1])
header_path = Path(sys.argv[2])
asm_path = Path(sys.argv[3])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


arm = arm_path.read_text(encoding="utf-8")
arm = replace_once(
    arm,
    "teb-bounds-guest-limit",
    """struct WindowsTebStackBounds {\n    NT_TIB* tib{};\n    void* host_stack_base{};\n    void* host_stack_limit{};\n};\n""",
    """struct WindowsTebStackBounds {\n    NT_TIB* tib{};\n    void* host_stack_base{};\n    void* host_stack_limit{};\n    std::uint64_t guest_stack_limit{};\n};\n""",
)
arm = replace_once(
    arm,
    "capture-guest-stack-limit",
    """    bounds.host_stack_base = tib->StackBase;\n    bounds.host_stack_limit = tib->StackLimit;\n    // Keep the host StackLimit through the host-side NtContinue transition. Publishing the guest\n""",
    """    bounds.host_stack_base = tib->StackBase;\n    bounds.host_stack_limit = tib->StackLimit;\n    bounds.guest_stack_limit = static_cast<std::uint64_t>(allocation_base);\n    // Keep the host StackLimit through the host-side NtContinue transition. Publishing the guest\n""",
)
arm = replace_once(
    arm,
    "post-entry-third-arg",
    """            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n""",
    """            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second),\n                teb_stack_bounds.guest_stack_limit));\n""",
)
arm_path.write_text(arm, encoding="utf-8", newline="\n")

header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    "enter-guest-signature",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline) noexcept;\n""",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline,\n                                               std::uint64_t guest_stack_limit) noexcept;\n""",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

asm = asm_path.read_text(encoding="utf-8")
asm = replace_once(
    asm,
    "enter-guest-comment-signature",
    "; uint64_t WindowsNceEnterGuest(GuestContext* guest, const void* entry_trampoline)\n",
    "; uint64_t WindowsNceEnterGuest(GuestContext* guest, const void* entry_trampoline, uint64_t guest_stack_limit)\n",
)
asm = replace_once(
    asm,
    "preserve-limit-scratch",
    """        ; Keep only the two values needed after all ordinary guest registers are restored.\n        mov     x17, x0\n        mov     x16, x1\n""",
    """        ; Keep entry metadata in registers excluded from the ordinary guest restore.\n        ; x30 carries the guest StackLimit until SP has switched; x29 carries guest SP.\n        mov     x17, x0\n        mov     x16, x1\n        mov     x30, x2\n""",
)
asm = replace_once(
    asm,
    "guest-sp-scratch",
    """        ; x30 temporarily carries guest SP until the final stack switch.\n        ldr     x30, [x17, #GuestContextSp]\n\n        ; Restore guest GPRs except x16/x17 (entry-trampoline scratch), physical x18 (Windows TEB),\n        ; and x30 (temporarily guest SP).\n""",
    """        ; x29 temporarily carries guest SP until the final stack switch.\n        ldr     x29, [x17, #GuestContextSp]\n\n        ; Restore guest GPRs except x16/x17 (entry-trampoline scratch), physical x18 (Windows TEB),\n        ; x29 (temporarily guest SP), and x30 (temporarily guest StackLimit).\n""",
)
asm = replace_once(
    asm,
    "defer-x29-and-publish-limit",
    """        ldp     x25, x26, [x17, #0x0C8]\n        ldp     x27, x28, [x17, #0x0D8]\n        ldr     x29,      [x17, #0x0E8]\n\n        mov     sp, x30\n        ldr     x30, [x17, #0x0F0]\n\n        ; entry_trampoline restores guest x16/x17 and uses a direct relative branch to guest PC.\n""",
    """        ldp     x25, x26, [x17, #0x0C8]\n        ldp     x27, x28, [x17, #0x0D8]\n\n        ; Match the NtContinue path ordering: guest SP becomes active first, then the guest\n        ; StackLimit is published while x18 still points at the Windows TEB.\n        mov     sp, x29\n        str     x30, [x18, #16]\n        ldr     x29, [x17, #0x0E8]\n        ldr     x30, [x17, #0x0F0]\n\n        ; entry_trampoline restores guest x16/x17 and uses a direct relative branch to guest PC.\n""",
)
asm_path.write_text(asm, encoding="utf-8", newline="\n")

print("REALGAME_V8_POST_STACKLIMIT=PASS")
