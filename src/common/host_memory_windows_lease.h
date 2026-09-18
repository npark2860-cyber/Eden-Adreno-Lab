// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error host_memory_windows_lease.h is only available on Windows.
#endif

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <utility>

#include "common/host_memory.h"
#include "common/logging.h"

#ifndef MEM_REPLACE_PLACEHOLDER
#define MEM_REPLACE_PLACEHOLDER 0x00004000
#endif
#ifndef MEM_PRESERVE_PLACEHOLDER
#define MEM_PRESERVE_PLACEHOLDER 0x00000002
#endif

namespace Common {

inline HostMemory::PrivateMappingLease::PrivateMappingLease(HostMemory* owner_,
                                                            u8* virtual_address_,
                                                            size_t host_offset_, size_t length_,
                                                            MemoryPermission perms_) noexcept
    : owner{owner_}, virtual_address{virtual_address_}, host_offset{host_offset_}, length{length_},
      perms{perms_}, active{true} {}

inline HostMemory::PrivateMappingLease::~PrivateMappingLease() {
    if (active) {
        (void)Restore();
    }
}

inline HostMemory::PrivateMappingLease::PrivateMappingLease(PrivateMappingLease&& other) noexcept
    : owner{std::exchange(other.owner, nullptr)},
      virtual_address{std::exchange(other.virtual_address, nullptr)},
      host_offset{std::exchange(other.host_offset, 0)}, length{std::exchange(other.length, 0)},
      perms{other.perms}, active{std::exchange(other.active, false)} {}

inline HostMemory::PrivateMappingLease& HostMemory::PrivateMappingLease::operator=(
    PrivateMappingLease&& other) noexcept {
    if (this == &other) {
        return *this;
    }
    if (active && !Restore()) {
        return *this;
    }
    owner = std::exchange(other.owner, nullptr);
    virtual_address = std::exchange(other.virtual_address, nullptr);
    host_offset = std::exchange(other.host_offset, 0);
    length = std::exchange(other.length, 0);
    perms = other.perms;
    active = std::exchange(other.active, false);
    return *this;
}

inline bool HostMemory::PrivateMappingLease::ContainsAddress(u64 address) const noexcept {
    if (!active || virtual_address == nullptr || length == 0) {
        return false;
    }
    const auto begin = reinterpret_cast<std::uintptr_t>(virtual_address);
    const auto end = begin + length;
    return end >= begin && address >= begin && address < end;
}

inline bool HostMemory::PrivateMappingLease::SyncToBacking() noexcept {
    if (!active || owner == nullptr || virtual_address == nullptr || length == 0) {
        return false;
    }
    std::memcpy(owner->BackingBasePointer() + host_offset, virtual_address, length);
    std::atomic_thread_fence(std::memory_order_release);
    return true;
}

inline bool HostMemory::PrivateMappingLease::SyncFromBacking() noexcept {
    if (!active || owner == nullptr || virtual_address == nullptr || length == 0) {
        return false;
    }
    std::atomic_thread_fence(std::memory_order_acquire);
    std::memcpy(virtual_address, owner->BackingBasePointer() + host_offset, length);
    return true;
}

inline bool HostMemory::PrivateMappingLease::Restore() noexcept {
    if (!active) {
        return true;
    }
    if (owner == nullptr || virtual_address == nullptr || length == 0) {
        active = false;
        return false;
    }

    std::memcpy(owner->BackingBasePointer() + host_offset, virtual_address, length);

    if (!VirtualFreeEx(GetCurrentProcess(), virtual_address, length,
                       MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
        LOG_ERROR(HW_Memory, "Failed to return private HostMemory lease to placeholder: {}",
                  GetLastError());
        return false;
    }

    active = false;
    owner->Map(reinterpret_cast<size_t>(virtual_address), host_offset, length, perms, false);

    MEMORY_BASIC_INFORMATION restored{};
    const bool restored_mapped =
        VirtualQuery(virtual_address, &restored, sizeof(restored)) != 0 &&
        restored.Type == MEM_MAPPED;
    if (!restored_mapped) {
        LOG_ERROR(HW_Memory, "Failed to restore section-backed HostMemory lease mapping");
    }

    owner = nullptr;
    virtual_address = nullptr;
    host_offset = 0;
    length = 0;
    return restored_mapped;
}

inline std::optional<HostMemory::PrivateMappingLease> HostMemory::AcquireDirectMappedPrivateLease(
    void* virtual_address_, size_t host_offset_, size_t length_, MemoryPermission perms_) {
    constexpr size_t WindowsPageSize = 0x1000;

    auto log_failure = [&](const char* stage, const void* query_address,
                           const MEMORY_BASIC_INFORMATION* region, SIZE_T queried,
                           const void* replacement_address, DWORD query_error, DWORD operation_error,
                           DWORD cleanup_error = ERROR_SUCCESS) {
        const auto ptr_value = [](const void* ptr) -> u64 {
            return static_cast<u64>(reinterpret_cast<std::uintptr_t>(ptr));
        };
        LOG_ERROR(
            HW_Memory,
            "NCE_V54_LEASE_FAIL stage={} va=0x{:016X} host=0x{:X} len=0x{:X} "
            "query=0x{:016X} queried=0x{:X} state=0x{:X} type=0x{:X} "
            "alloc=0x{:016X} base=0x{:016X} region=0x{:X} repl=0x{:016X} "
            "query_err={} op_err={} cleanup_err={}",
            stage, ptr_value(virtual_address_), static_cast<u64>(host_offset_),
            static_cast<u64>(length_), ptr_value(query_address), static_cast<u64>(queried),
            static_cast<u64>(region != nullptr ? region->State : 0),
            static_cast<u64>(region != nullptr ? region->Type : 0),
            ptr_value(region != nullptr ? region->AllocationBase : nullptr),
            ptr_value(region != nullptr ? region->BaseAddress : nullptr),
            static_cast<u64>(region != nullptr ? region->RegionSize : 0),
            ptr_value(replacement_address), static_cast<u64>(query_error),
            static_cast<u64>(operation_error), static_cast<u64>(cleanup_error));
    };

    if (virtual_address_ == nullptr || length_ == 0 ||
        (reinterpret_cast<std::uintptr_t>(virtual_address_) & (WindowsPageSize - 1)) != 0 ||
        (length_ & (WindowsPageSize - 1)) != 0 || host_offset_ > backing_size ||
        length_ > backing_size - host_offset_) {
        log_failure("S01_INPUT", virtual_address_, nullptr, 0, nullptr, ERROR_SUCCESS,
                    ERROR_SUCCESS);
        return std::nullopt;
    }

    MEMORY_BASIC_INFORMATION initial{};
    const SIZE_T initial_queried = VirtualQuery(virtual_address_, &initial, sizeof(initial));
    const DWORD initial_query_error = initial_queried == 0 ? GetLastError() : ERROR_SUCCESS;
    if (initial_queried == 0 || initial.State != MEM_COMMIT || initial.Type != MEM_MAPPED ||
        initial.AllocationBase != virtual_address_) {
        log_failure("S02_INITIAL_QUERY", virtual_address_, &initial, initial_queried, nullptr,
                    initial_query_error, ERROR_SUCCESS);
        return std::nullopt;
    }

    const auto begin = reinterpret_cast<std::uintptr_t>(virtual_address_);
    const auto end = begin + length_;
    if (end < begin) {
        log_failure("S03_RANGE_OVERFLOW", virtual_address_, &initial, initial_queried, nullptr,
                    initial_query_error, ERROR_SUCCESS);
        return std::nullopt;
    }
    for (auto cursor = begin; cursor < end;) {
        MEMORY_BASIC_INFORMATION region{};
        const void* const query_address = reinterpret_cast<const void*>(cursor);
        const SIZE_T region_queried = VirtualQuery(query_address, &region, sizeof(region));
        const DWORD region_query_error = region_queried == 0 ? GetLastError() : ERROR_SUCCESS;
        if (region_queried == 0 || region.State != MEM_COMMIT || region.Type != MEM_MAPPED ||
            region.AllocationBase != initial.AllocationBase) {
            log_failure("S04_REGION_QUERY", query_address, &region, region_queried, nullptr,
                        region_query_error, ERROR_SUCCESS);
            return std::nullopt;
        }
        const auto region_end = reinterpret_cast<std::uintptr_t>(region.BaseAddress) +
                                static_cast<std::uintptr_t>(region.RegionSize);
        if (region_end <= cursor) {
            log_failure("S05_REGION_NONADVANCE", query_address, &region, region_queried, nullptr,
                        region_query_error, ERROR_SUCCESS);
            return std::nullopt;
        }
        cursor = (std::min)(region_end, end);
    }

    using PfnVirtualAlloc2 = PVOID(WINAPI*)(HANDLE, PVOID, SIZE_T, ULONG, ULONG,
                                            MEM_EXTENDED_PARAMETER*, ULONG);
    auto* const kernelbase = GetModuleHandleW(L"KernelBase.dll");
    if (kernelbase == nullptr) {
        const DWORD operation_error = GetLastError();
        log_failure("S06_KERNELBASE", virtual_address_, &initial, initial_queried, nullptr,
                    initial_query_error, operation_error);
        return std::nullopt;
    }
    auto* const virtual_alloc2 = reinterpret_cast<PfnVirtualAlloc2>(
        GetProcAddress(kernelbase, "VirtualAlloc2"));
    if (virtual_alloc2 == nullptr) {
        const DWORD operation_error = GetLastError();
        log_failure("S07_VIRTUALALLOC2_RESOLVE", virtual_address_, &initial, initial_queried,
                    nullptr, initial_query_error, operation_error);
        return std::nullopt;
    }

    Unmap(reinterpret_cast<size_t>(virtual_address_), length_, false);

    auto restore_mapped_view = [&] {
        Map(reinterpret_cast<size_t>(virtual_address_), host_offset_, length_, perms_, false);
    };

    void* replacement = virtual_alloc2(
        GetCurrentProcess(), virtual_address_, length_,
        MEM_RESERVE | MEM_COMMIT | MEM_REPLACE_PLACEHOLDER, PAGE_READWRITE, nullptr, 0);
    const DWORD first_alloc_error = replacement == nullptr ? GetLastError() : ERROR_SUCCESS;
    if (replacement != virtual_address_) {
        DWORD first_cleanup_error = ERROR_SUCCESS;
        if (replacement != nullptr &&
            !VirtualFreeEx(GetCurrentProcess(), replacement, length_,
                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
            first_cleanup_error = GetLastError();
            MEMORY_BASIC_INFORMATION failure_region{};
            const SIZE_T failure_queried =
                VirtualQuery(virtual_address_, &failure_region, sizeof(failure_region));
            const DWORD failure_query_error =
                failure_queried == 0 ? GetLastError() : ERROR_SUCCESS;
            log_failure("S08_FIRST_REPLACEMENT_CLEANUP", virtual_address_, &failure_region,
                        failure_queried, replacement, failure_query_error, first_alloc_error,
                        first_cleanup_error);
        }

        if (!VirtualFreeEx(GetCurrentProcess(), virtual_address_, length_,
                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
            const DWORD preserve_error = GetLastError();
            MEMORY_BASIC_INFORMATION failure_region{};
            const SIZE_T failure_queried =
                VirtualQuery(virtual_address_, &failure_region, sizeof(failure_region));
            const DWORD failure_query_error =
                failure_queried == 0 ? GetLastError() : ERROR_SUCCESS;
            log_failure("S09_PRESERVE_PLACEHOLDER", virtual_address_, &failure_region,
                        failure_queried, replacement, failure_query_error, preserve_error,
                        first_cleanup_error);
            restore_mapped_view();
            return std::nullopt;
        }

        replacement = virtual_alloc2(
            GetCurrentProcess(), virtual_address_, length_,
            MEM_RESERVE | MEM_COMMIT | MEM_REPLACE_PLACEHOLDER, PAGE_READWRITE, nullptr, 0);
        const DWORD second_alloc_error = replacement == nullptr ? GetLastError() : ERROR_SUCCESS;
        if (replacement != virtual_address_) {
            MEMORY_BASIC_INFORMATION failure_region{};
            const SIZE_T failure_queried =
                VirtualQuery(virtual_address_, &failure_region, sizeof(failure_region));
            const DWORD failure_query_error =
                failure_queried == 0 ? GetLastError() : ERROR_SUCCESS;

            DWORD second_cleanup_error = ERROR_SUCCESS;
            if (replacement != nullptr &&
                !VirtualFreeEx(GetCurrentProcess(), replacement, length_,
                               MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
                second_cleanup_error = GetLastError();
                log_failure("S10_SECOND_REPLACEMENT_CLEANUP", virtual_address_, &failure_region,
                            failure_queried, replacement, failure_query_error, second_alloc_error,
                            second_cleanup_error);
            }

            log_failure("S11_SECOND_REPLACEMENT", virtual_address_, &failure_region,
                        failure_queried, replacement, failure_query_error, second_alloc_error,
                        second_cleanup_error);
            restore_mapped_view();
            return std::nullopt;
        }
    }

    std::memcpy(virtual_address_, backing_base + host_offset_, length_);

    MEMORY_BASIC_INFORMATION private_region{};
    const SIZE_T private_queried =
        VirtualQuery(virtual_address_, &private_region, sizeof(private_region));
    const DWORD private_query_error = private_queried == 0 ? GetLastError() : ERROR_SUCCESS;
    if (private_queried == 0 || private_region.State != MEM_COMMIT ||
        private_region.Type != MEM_PRIVATE) {
        DWORD cleanup_error = ERROR_SUCCESS;
        if (!VirtualFreeEx(GetCurrentProcess(), virtual_address_, length_,
                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
            cleanup_error = GetLastError();
        }
        log_failure("S12_FINAL_PRIVATE", virtual_address_, &private_region, private_queried,
                    replacement, private_query_error, ERROR_SUCCESS, cleanup_error);
        restore_mapped_view();
        return std::nullopt;
    }

    return PrivateMappingLease{this, static_cast<u8*>(virtual_address_), host_offset_, length_,
                               perms_};
}
}

} // namespace Common
