#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <span>
#include <string>
#include <vector>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/core.h"
#include "core/cpu_manager.h"
#include "core/file_sys/registered_cache.h"
#include "core/file_sys/vfs/vfs_real.h"
#include "core/frontend/emu_window.h"
#include "core/frontend/graphics_context.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/svc_types.h"
#include "core/hle/service/am/applet_manager.h"
#include "core/hle/service/filesystem/filesystem.h"
#include "core/memory.h"
#include "video_core/control/channel_state.h"
#include "video_core/engines/fermi_2d.h"
#include "video_core/gpu.h"
#include "video_core/host1x/host1x.h"
#include "video_core/memory_manager.h"
#include "video_core/pte_kind.h"
#include "video_core/rasterizer_interface.h"
#include "video_core/renderer_base.h"

#ifdef interface
#undef interface
#endif

namespace {

constexpr std::size_t PageSize = 0x1000;
constexpr std::size_t TextSize = PageSize;
constexpr std::size_t DataPages = 18;
constexpr std::size_t SyntheticNroSize = TextSize + DataPages * PageSize;
constexpr std::size_t GuestLoadOffset = 0x300;
constexpr std::size_t GuestSvcOffset = 0x304;
constexpr std::size_t GuestAfterSvcOffset = 0x308;
constexpr std::size_t TargetDataOffset = 0x1000;
constexpr std::size_t DestinationDataOffset = 0x2000;
constexpr u32 GuestLdrX3X2 = 0xF9400043U; // ldr x3, [x2]
constexpr u32 GuestSvc33 = 0xD4000661U;   // svc #0x33
constexpr u32 GuestBrk0 = 0xD4200000U;    // must never execute
constexpr u64 TargetSentinel = 0xE2E2A55A11223344ULL;
constexpr u64 X0Sentinel = 0x1122334455667788ULL;
constexpr u64 X1Sentinel = 0x8877665544332211ULL;
constexpr u64 X3BeforeSentinel = 0x0E2E0E2E0E2E0E2EULL;
constexpr u64 X18Sentinel = 0x123456789ABC0000ULL;
constexpr DAddr TargetDeviceAddress = 0x01000000;
constexpr DAddr DestinationDeviceAddress = TargetDeviceAddress + PageSize;
constexpr GPUVAddr TargetGpuAddress = 0x00100000;
constexpr GPUVAddr DestinationGpuAddress = TargetGpuAddress + PageSize;

std::atomic<u32> g_av_seen{};
std::atomic<u32> g_continue_seen{};
std::atomic<u32> g_continue_rw{};
std::atomic<u32> g_continue_pc_unchanged{};
std::atomic<u64> g_target_address{};
std::atomic<u64> g_guest_pc{};
std::atomic<u64> g_av_access_type{~0ULL};
std::atomic<u64> g_av_fault_address{};
std::atomic<u64> g_av_pc{};
std::atomic<u64> g_av_sp{};
std::atomic<u64> g_continue_pc{};
std::atomic<u64> g_continue_sp{};
std::atomic<u64> g_continue_protect{};

int Fail(const char* marker, int code = 1) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return code;
}

[[noreturn]] void Fatal(const char* marker, unsigned code = 1) {
    std::fprintf(stderr, "%s=FAIL\n", marker);
    std::fflush(stderr);
#if defined(_WIN32)
    ExitProcess(code);
#else
    std::_Exit(static_cast<int>(code));
#endif
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

void WriteU32(std::vector<u8>& bytes, std::size_t offset, u32 value) {
    std::memcpy(bytes.data() + offset, &value, sizeof(value));
}

bool WriteSyntheticNro(const std::filesystem::path& path) {
    std::vector<u8> bytes(SyntheticNroSize, 0);

    // NRO header layout from the production loader. Keep file size page-aligned so the loader's
    // PageAlignSize(file_size) copy remains entirely inside this synthetic file.
    WriteU32(bytes, 0x04, 0x200);      // module_header_offset; zeroed bytes there => no MOD0
    WriteU32(bytes, 0x08, 0x454D4F48); // "HOME"
    WriteU32(bytes, 0x0C, 0x57455242); // "BREW"
    WriteU32(bytes, 0x10, 0x304F524E); // "NRO0"
    WriteU32(bytes, 0x18, static_cast<u32>(SyntheticNroSize));

    WriteU32(bytes, 0x20, 0x0000); // text offset
    WriteU32(bytes, 0x24, static_cast<u32>(TextSize));
    WriteU32(bytes, 0x28, static_cast<u32>(TextSize)); // ro offset
    WriteU32(bytes, 0x2C, 0);                           // ro size
    WriteU32(bytes, 0x30, static_cast<u32>(TextSize)); // data offset
    WriteU32(bytes, 0x34, static_cast<u32>(SyntheticNroSize - TextSize));
    WriteU32(bytes, 0x38, 0); // bss size

    WriteU32(bytes, GuestLoadOffset, GuestLdrX3X2);
    WriteU32(bytes, GuestSvcOffset, GuestSvc33);
    WriteU32(bytes, GuestAfterSvcOffset, GuestBrk0);

    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) {
        return false;
    }
    out.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    out.flush();
    return static_cast<bool>(out);
}

#if defined(_WIN32)
class ProbeWindow final : public Core::Frontend::EmuWindow {
public:
    ProbeWindow() {
        instance = GetModuleHandleW(nullptr);
        class_name = L"IMP008E_E2_HIDDEN_WINDOW";

        WNDCLASSW wc{};
        wc.lpfnWndProc = DefWindowProcW;
        wc.hInstance = instance;
        wc.lpszClassName = class_name.c_str();
        class_atom = RegisterClassW(&wc);
        if (class_atom == 0 && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
            return;
        }

        hwnd = CreateWindowExW(0, class_name.c_str(), L"IMP-008E E2", WS_OVERLAPPED,
                               CW_USEDEFAULT, CW_USEDEFAULT, 64, 64, nullptr, nullptr, instance,
                               nullptr);
        if (hwnd == nullptr) {
            return;
        }

        window_info.type = Core::Frontend::WindowSystemType::Windows;
        window_info.render_surface = hwnd;
        window_info.render_surface_scale = 1.0f;
        NotifyClientAreaSizeChanged({64, 64});
        UpdateCurrentFramebufferLayout(64, 64);
        ready = true;
    }

    ~ProbeWindow() override {
        if (hwnd != nullptr) {
            DestroyWindow(hwnd);
        }
        if (class_atom != 0 && instance != nullptr) {
            UnregisterClassW(class_name.c_str(), instance);
        }
    }

    std::unique_ptr<Core::Frontend::GraphicsContext> CreateSharedContext() const override {
        return std::make_unique<Core::Frontend::GraphicsContext>();
    }

    bool IsShown() const override {
        return true;
    }

    bool IsReady() const {
        return ready;
    }

private:
    HINSTANCE instance{};
    ATOM class_atom{};
    HWND hwnd{};
    std::wstring class_name;
    bool ready{};
};

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

u64 ReadPhysicalX18() {
    u64 value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

LONG CALLBACK E2ObservationVeh(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& record = *exception->ExceptionRecord;
    if (record.ExceptionCode != EXCEPTION_ACCESS_VIOLATION || record.NumberParameters < 2) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const u64 target = g_target_address.load(std::memory_order_acquire);
    const u64 guest_pc = g_guest_pc.load(std::memory_order_acquire);
    const u64 access_type = static_cast<u64>(record.ExceptionInformation[0]);
    const u64 fault_address = static_cast<u64>(record.ExceptionInformation[1]);
    const u64 pc = static_cast<u64>(exception->ContextRecord->Pc);
    if (target == 0 || guest_pc == 0 || access_type != 0 || fault_address != target ||
        pc != guest_pc) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    u32 expected = 0;
    if (g_av_seen.compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) {
        g_av_access_type.store(access_type, std::memory_order_release);
        g_av_fault_address.store(fault_address, std::memory_order_release);
        g_av_pc.store(pc, std::memory_order_release);
        g_av_sp.store(static_cast<u64>(exception->ContextRecord->Sp), std::memory_order_release);
        std::fprintf(stderr,
                     "IMP008E_E2_DATA_AV CODE=0x%08lX ACCESS=%llu FAULT=0x%llX PC=0x%llX SP=0x%llX\n",
                     static_cast<unsigned long>(record.ExceptionCode),
                     static_cast<unsigned long long>(access_type),
                     static_cast<unsigned long long>(fault_address),
                     static_cast<unsigned long long>(pc),
                     static_cast<unsigned long long>(exception->ContextRecord->Sp));
        std::fflush(stderr);
    }

    // Observation only. The production NCE VEH owns cache invalidation and continuation.
    return EXCEPTION_CONTINUE_SEARCH;
}

LONG CALLBACK E2ContinueObservation(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& record = *exception->ExceptionRecord;
    if (record.ExceptionCode != EXCEPTION_ACCESS_VIOLATION || record.NumberParameters < 2) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const u64 target = g_target_address.load(std::memory_order_acquire);
    const u64 guest_pc = g_guest_pc.load(std::memory_order_acquire);
    const u64 access_type = static_cast<u64>(record.ExceptionInformation[0]);
    const u64 fault_address = static_cast<u64>(record.ExceptionInformation[1]);
    if (target == 0 || guest_pc == 0 || access_type != 0 || fault_address != target) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    u32 expected = 0;
    if (!g_continue_seen.compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    MEMORY_BASIC_INFORMATION mbi{};
    DWORD protect = 0;
    bool rw = false;
    if (VirtualQuery(reinterpret_cast<const void*>(target), &mbi, sizeof(mbi)) != 0) {
        protect = mbi.Protect & 0xFFU;
        rw = mbi.State == MEM_COMMIT && protect == PAGE_READWRITE;
    }

    const u64 pc = static_cast<u64>(exception->ContextRecord->Pc);
    const bool pc_unchanged = pc == guest_pc;
    g_continue_rw.store(rw ? 1U : 0U, std::memory_order_release);
    g_continue_pc_unchanged.store(pc_unchanged ? 1U : 0U, std::memory_order_release);
    g_continue_pc.store(pc, std::memory_order_release);
    g_continue_sp.store(static_cast<u64>(exception->ContextRecord->Sp), std::memory_order_release);
    g_continue_protect.store(protect, std::memory_order_release);

    std::fprintf(stderr,
                 "IMP008E_E2_CONTINUE_STATE PC=0x%llX EXPECTED_PC=0x%llX SP=0x%llX PROTECT=0x%lX RW=%u PC_UNCHANGED=%u\n",
                 static_cast<unsigned long long>(pc),
                 static_cast<unsigned long long>(guest_pc),
                 static_cast<unsigned long long>(exception->ContextRecord->Sp),
                 static_cast<unsigned long>(protect), rw ? 1U : 0U, pc_unchanged ? 1U : 0U);
    std::fflush(stderr);

    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008E_E2_PLATFORM_CONTRACT");
#else
    Trace("IMP008E_E2_MAIN_ENTER");

    const std::filesystem::path nro_path =
        std::filesystem::current_path() / "imp008e-e2-synthetic.nro";
    if (!WriteSyntheticNro(nro_path)) {
        return Fail("IMP008E_E2_SYNTHETIC_NRO_WRITE", 70);
    }
    Trace("IMP008E_E2_SYNTHETIC_NRO_READY");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::values.renderer_backend.SetValue(Settings::RendererBackend::Vulkan);
    Settings::values.use_reactive_flushing.SetValue(true);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled() || !Settings::values.use_reactive_flushing.GetValue() ||
        Settings::values.renderer_backend.GetValue() != Settings::RendererBackend::Vulkan) {
        return Fail("IMP008E_E2_SETTINGS", 71);
    }
    Trace("IMP008E_E2_SETTINGS_READY");

    Core::System system;
    system.Initialize();
    system.ApplySettings();

    ProbeWindow window;
    if (!window.IsReady()) {
        return Fail("IMP008E_E2_WIN32_WINDOW", 74);
    }
    Trace("IMP008E_E2_WIN32_WINDOW_READY");

    system.SetContentProvider(std::make_unique<FileSys::ContentProviderUnion>());
    system.SetFilesystem(std::make_shared<FileSys::RealVfsFilesystem>());
    system.GetFileSystemController().CreateFactories(*system.GetFilesystem());
    system.GetUserChannel().clear();

    Service::AM::FrontendAppletParameters load_parameters{
        .applet_id = Service::AM::AppletId::Application,
    };
    const Core::SystemResultStatus load_result =
        system.Load(window, nro_path.string(), load_parameters);
    std::fprintf(stderr, "IMP008E_E2_LOAD_RESULT=%u\n", static_cast<unsigned>(load_result));
    std::fflush(stderr);
    if (load_result == Core::SystemResultStatus::ErrorVideoCore) {
        Trace("IMP008E_E2_RENDERER_ENVIRONMENT_INVALID");
        std::filesystem::remove(nro_path);
        return 72;
    }
    if (load_result != Core::SystemResultStatus::Success || !system.IsPoweredOn()) {
        std::filesystem::remove(nro_path);
        return Fail("IMP008E_E2_SYSTEM_LOAD", 73);
    }
    Trace("IMP008E_E2_REAL_SYSTEM_LOAD");
    Trace("IMP008E_E2_REAL_HOST1X_GPU");

    system.GPU().Start();
    system.GetCpuManager().OnGpuReady();
    Trace("IMP008E_E2_GPU_STARTED_NO_SYSTEM_RUN");

    auto* const process = system.ApplicationProcess();
    if (process == nullptr || !process->IsApplication() || !process->Is64Bit()) {
        Fatal("IMP008E_E2_APPLICATION_PROCESS", 75);
    }
    Trace("IMP008E_E2_REAL_APPLICATION_PROCESS");

    auto* const rasterizer = system.Renderer().ReadRasterizer();
    if (rasterizer == nullptr) {
        Fatal("IMP008E_E2_RASTERIZER", 76);
    }
    std::fprintf(stderr, "IMP008E_E2_RENDERER_VENDOR=%s\n",
                 system.Renderer().GetDeviceVendor().c_str());
    std::fflush(stderr);
    Trace("IMP008E_E2_REAL_RASTERIZER");

    const u64 load_base = GetInteger(process->GetEntryPoint());
    const u64 target = load_base + TargetDataOffset;
    const u64 destination = load_base + DestinationDataOffset;
    const u64 guest_pc = load_base + GuestLoadOffset;
    const u64 expected_return_pc = load_base + GuestAfterSvcOffset;
    const u64 guest_sp = load_base + SyntheticNroSize - 0x20;

    auto& process_memory = process->GetMemory();
    u8* const target_backing =
        process_memory.GetPointerSilent(Common::ProcessAddress{target});
    u8* const destination_backing =
        process_memory.GetPointerSilent(Common::ProcessAddress{destination});
    if (target_backing == nullptr || destination_backing == nullptr) {
        Fatal("IMP008E_E2_DATA_BACKING", 77);
    }
    std::memcpy(target_backing, &TargetSentinel, sizeof(TargetSentinel));
    std::memset(destination_backing, 0, sizeof(TargetSentinel));

    PrintProtection("IMP008E_E2_INITIAL_PROTECTION", target);
    if (!QueryProtection(target, PAGE_READWRITE)) {
        Fatal("IMP008E_E2_INITIAL_RW", 78);
    }
    Trace("IMP008E_E2_INITIAL_RW");

    auto& device_memory = system.Host1x().MemoryManager();
    const Core::Asid asid = device_memory.RegisterProcess(&process_memory);
    Trace("IMP008E_E2_DEVICE_PROCESS_REGISTERED");

    device_memory.AllocateFixed(TargetDeviceAddress, PageSize * 2);
    device_memory.Map(TargetDeviceAddress, target, PageSize, asid, false);
    device_memory.Map(DestinationDeviceAddress, destination, PageSize, asid, false);
    if (device_memory.GetPointer<u8>(TargetDeviceAddress) != target_backing ||
        device_memory.GetPointer<u8>(DestinationDeviceAddress) != destination_backing) {
        Fatal("IMP008E_E2_DEVICE_MAPPING", 79);
    }
    Trace("IMP008E_E2_DEVICE_MAPPING");

    auto gpu_memory = std::make_unique<Tegra::MemoryManager>(system, device_memory);
    system.GPU().InitAddressSpace(*gpu_memory);

    auto channel = system.GPU().AllocateChannel();
    if (!channel) {
        Fatal("IMP008E_E2_CHANNEL_ALLOCATE", 80);
    }
    channel->memory_manager = gpu_memory.get();
    system.GPU().InitChannel(*channel, process->GetProgramId());
    if (!channel->initialized) {
        Fatal("IMP008E_E2_CHANNEL_INIT", 81);
    }
    system.GPU().BindChannel(channel->bind_id);
    Trace("IMP008E_E2_REAL_GPU_CHANNEL");

    gpu_memory->Map(TargetGpuAddress, TargetDeviceAddress, PageSize, Tegra::PTEKind::PITCH, false);
    gpu_memory->Map(DestinationGpuAddress, DestinationDeviceAddress, PageSize,
                    Tegra::PTEKind::PITCH, false);
    if (gpu_memory->GpuToCpuAddress(TargetGpuAddress) != TargetDeviceAddress ||
        gpu_memory->GpuToCpuAddress(DestinationGpuAddress) != DestinationDeviceAddress) {
        Fatal("IMP008E_E2_GPU_MAPPING", 82);
    }
    Trace("IMP008E_E2_GPU_MAPPING");

    Tegra::Engines::Fermi2D::Surface src{};
    src.format = Tegra::RenderTargetFormat::A8B8G8R8_UNORM;
    src.linear = Tegra::Engines::Fermi2D::MemoryLayout::Pitch;
    src.depth = 1;
    src.layer = 0;
    src.pitch = 4;
    src.width = 1;
    src.height = 1;
    src.addr_upper = static_cast<u32>(TargetGpuAddress >> 32);
    src.addr_lower = static_cast<u32>(TargetGpuAddress);

    Tegra::Engines::Fermi2D::Surface dst = src;
    dst.addr_upper = static_cast<u32>(DestinationGpuAddress >> 32);
    dst.addr_lower = static_cast<u32>(DestinationGpuAddress);

    Tegra::Engines::Fermi2D::Config copy{};
    copy.operation = Tegra::Engines::Fermi2D::Operation::SrcCopy;
    copy.filter = Tegra::Engines::Fermi2D::Filter::Point;
    copy.must_accelerate = true;
    copy.dst_x0 = 0;
    copy.dst_y0 = 0;
    copy.dst_x1 = 1;
    copy.dst_y1 = 1;
    copy.src_x0 = 0;
    copy.src_y0 = 0;
    copy.src_x1 = 1;
    copy.src_y1 = 1;

    if (!rasterizer->AccelerateSurfaceCopy(src, dst, copy)) {
        Fatal("IMP008E_E2_REAL_CACHE_CREATE", 83);
    }
    Trace("IMP008E_E2_REAL_CACHE_CREATE");

    PrintProtection("IMP008E_E2_CACHED_PROTECTION", target);
    if (!QueryProtection(target, PAGE_NOACCESS)) {
        Fatal("IMP008E_E2_REAL_CACHE_NOACCESS", 84);
    }
    Trace("IMP008E_E2_REAL_CACHE_NOACCESS");

    u64 backing_value{};
    std::memcpy(&backing_value, target_backing, sizeof(backing_value));
    if (backing_value != TargetSentinel) {
        Fatal("IMP008E_E2_CACHED_BACKING", 85);
    }
    Trace("IMP008E_E2_CACHED_BACKING");

    auto* thread = Kernel::KThread::Create(system.Kernel());
    if (thread == nullptr) {
        Fatal("IMP008E_E2_THREAD_CREATE", 86);
    }
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        Fatal("IMP008E_E2_THREAD_OWNER", 87);
    }
    Trace("IMP008E_E2_REAL_KTHREAD");

    Core::ArmInterface* const arm = process->GetArmInterface(0);
    if (arm == nullptr) {
        Fatal("IMP008E_E2_ARM_INTERFACE", 88);
    }

    auto& native = thread->GetNativeExecutionParameters();
    if (native.lock.load(std::memory_order_acquire) != 1) {
        Fatal("IMP008E_E2_LOCK_INITIAL", 89);
    }
    arm->LockThread(thread);
    const bool locked_by_nce = native.lock.load(std::memory_order_acquire) == 0;
    arm->UnlockThread(thread);
    const bool unlocked_by_nce = native.lock.load(std::memory_order_acquire) == 1;
    if (!locked_by_nce || !unlocked_by_nce) {
        Fatal("IMP008E_E2_NCE_SELECTION", 90);
    }
    Trace("IMP008E_E2_NCE_SELECTED");

    Kernel::Svc::ThreadContext context{};
    context.r[0] = X0Sentinel;
    context.r[1] = X1Sentinel;
    context.r[2] = target;
    context.r[3] = X3BeforeSentinel;
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
    std::fprintf(stderr,
                 "IMP008E_E2_PRE_RUN PC=0x%llX TARGET=0x%llX SP=0x%llX TEB=0x%llX X18=0x%llX\n",
                 static_cast<unsigned long long>(guest_pc),
                 static_cast<unsigned long long>(target),
                 static_cast<unsigned long long>(guest_sp),
                 static_cast<unsigned long long>(teb),
                 static_cast<unsigned long long>(physical_x18_before));
    std::fflush(stderr);
    if (physical_x18_before != teb) {
        Fatal("IMP008E_E2_PHYSICAL_X18_TEB_BEFORE", 91);
    }
    Trace("IMP008E_E2_PHYSICAL_X18_TEB_BEFORE");

    g_target_address.store(target, std::memory_order_release);
    g_guest_pc.store(guest_pc, std::memory_order_release);
    g_av_seen.store(0, std::memory_order_release);
    g_continue_seen.store(0, std::memory_order_release);
    g_continue_rw.store(0, std::memory_order_release);
    g_continue_pc_unchanged.store(0, std::memory_order_release);

    PVOID const observation_veh = AddVectoredExceptionHandler(1, &E2ObservationVeh);
    if (observation_veh == nullptr) {
        Fatal("IMP008E_E2_OBSERVATION_VEH", 92);
    }
    PVOID const continue_handler = AddVectoredContinueHandler(0, &E2ContinueObservation);
    if (continue_handler == nullptr) {
        RemoveVectoredExceptionHandler(observation_veh);
        Fatal("IMP008E_E2_CONTINUE_HANDLER", 93);
    }
    Trace("IMP008E_E2_EXCEPTION_OBSERVERS_READY");

    Trace("IMP008E_E2_PRE_RUNTHREAD");
    arm->LockThread(thread);
    const Core::HaltReason halt_reason = arm->RunThread(thread);
    arm->UnlockThread(thread);
    RemoveVectoredContinueHandler(continue_handler);
    RemoveVectoredExceptionHandler(observation_veh);
    Trace("IMP008E_E2_RUNTHREAD_RETURNED");

    const u64 physical_x18_after = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008E_E2_PHYSICAL_X18_AFTER=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_after));
    std::fflush(stderr);

    if (g_av_seen.load(std::memory_order_acquire) != 1 ||
        g_av_access_type.load(std::memory_order_acquire) != 0 ||
        g_av_fault_address.load(std::memory_order_acquire) != target ||
        g_av_pc.load(std::memory_order_acquire) != guest_pc ||
        g_av_sp.load(std::memory_order_acquire) != guest_sp) {
        Fatal("IMP008E_E2_DATA_AV_EXACT", 94);
    }
    Trace("IMP008E_E2_DATA_AV_EXACT");

    if (g_continue_seen.load(std::memory_order_acquire) != 1 ||
        g_continue_rw.load(std::memory_order_acquire) != 1 ||
        g_continue_pc_unchanged.load(std::memory_order_acquire) != 1 ||
        g_continue_pc.load(std::memory_order_acquire) != guest_pc ||
        g_continue_sp.load(std::memory_order_acquire) != guest_sp ||
        g_continue_protect.load(std::memory_order_acquire) != PAGE_READWRITE) {
        Fatal("IMP008E_E2_PRODUCTION_RETRY_STATE", 95);
    }
    Trace("IMP008E_E2_PRODUCTION_RETRY_STATE");
    Trace("IMP008E_E2_FAILED_DATA_SKIP_NOT_USED");

    PrintProtection("IMP008E_E2_POST_RETURN_PROTECTION", target);
    if (!QueryProtection(target, PAGE_READWRITE)) {
        Fatal("IMP008E_E2_POST_RETURN_RW", 96);
    }
    Trace("IMP008E_E2_POST_RETURN_RW");

    if (!True(halt_reason & Core::HaltReason::SupervisorCall)) {
        Fatal("IMP008E_E2_SUPERVISOR_CALL_RETURN", 97);
    }
    Trace("IMP008E_E2_SUPERVISOR_CALL_RETURN");

    const u32 svc_number = arm->GetSvcNumber();
    std::fprintf(stderr, "IMP008E_E2_SVC_NUMBER=0x%X\n", svc_number);
    std::fflush(stderr);
    if (svc_number != 0x33) {
        Fatal("IMP008E_E2_SVC_NUMBER", 98);
    }
    Trace("IMP008E_E2_SVC_NUMBER");

    Kernel::Svc::ThreadContext returned{};
    arm->GetContext(returned);
    std::fprintf(stderr,
                 "IMP008E_E2_RETURNED PC=0x%llX SP=0x%llX X0=0x%llX X1=0x%llX X2=0x%llX X3=0x%llX X18=0x%llX\n",
                 static_cast<unsigned long long>(returned.pc),
                 static_cast<unsigned long long>(returned.sp),
                 static_cast<unsigned long long>(returned.r[0]),
                 static_cast<unsigned long long>(returned.r[1]),
                 static_cast<unsigned long long>(returned.r[2]),
                 static_cast<unsigned long long>(returned.r[3]),
                 static_cast<unsigned long long>(returned.r[18]));
    std::fflush(stderr);

    if (returned.pc != expected_return_pc || returned.sp != guest_sp ||
        returned.r[0] != X0Sentinel || returned.r[1] != X1Sentinel ||
        returned.r[2] != target || returned.r[3] != TargetSentinel ||
        returned.r[18] != X18Sentinel) {
        Fatal("IMP008E_E2_RETURN_CONTEXT", 99);
    }
    Trace("IMP008E_E2_REEXECUTED_VALUE_EXACT");
    Trace("IMP008E_E2_POST_SVC_PC_EXACT");
    Trace("IMP008E_E2_CONTEXT_COHERENT");

    if (physical_x18_after != teb) {
        Fatal("IMP008E_E2_PHYSICAL_X18_TEB_AFTER", 100);
    }
    Trace("IMP008E_E2_PHYSICAL_X18_TEB_AFTER");

    // Best-effort successful-path cleanup. Keep the manually constructed address space alive until
    // all real rasterizer ownership has been invalidated/unmapped.
    rasterizer->OnCacheInvalidation(TargetDeviceAddress, PageSize);
    rasterizer->OnCacheInvalidation(DestinationDeviceAddress, PageSize);
    gpu_memory->Unmap(TargetGpuAddress, PageSize);
    gpu_memory->Unmap(DestinationGpuAddress, PageSize);
    gpu_memory.reset();
    channel.reset();

    device_memory.Unmap(TargetDeviceAddress, PageSize);
    device_memory.Unmap(DestinationDeviceAddress, PageSize);
    device_memory.Free(TargetDeviceAddress, PageSize * 2);
    device_memory.UnregisterProcess(asid);

    thread->Close(system.Kernel());
    system.ShutdownMainProcess();
    std::filesystem::remove(nro_path);

    Trace("IMP008E_E2_GATE");
    return 0;
#endif
}
