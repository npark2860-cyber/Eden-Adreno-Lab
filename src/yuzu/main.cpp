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

    const DWORD wait_result = WaitForSingleObject(parent_handle, INFINITE);
    DWORD exit_code = 0xFFFFFFFFul;
    const BOOL got_exit = GetExitCodeProcess(parent_handle, &exit_code);
    const DWORD error_code = got_exit != FALSE ? 0 : GetLastError();

    WriteWindowsNceV63Line("V63_WATCHDOG_EXIT", parent_pid, child_pid, wait_result, exit_code,
                           error_code);
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



LONG WINAPI WindowsNceV64UnhandledExceptionFilter(EXCEPTION_POINTERS* exception_pointers) noexcept {
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

void InstallWindowsNceV65IllegalInstructionVeh() noexcept {
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

void InstallWindowsNceV70BreakpointVeh() noexcept {
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
