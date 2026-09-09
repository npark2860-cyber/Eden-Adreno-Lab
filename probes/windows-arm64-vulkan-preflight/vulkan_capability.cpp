// SPDX-FileCopyrightText: Copyright 2026 npark2860-cyber
// SPDX-License-Identifier: GPL-2.0-or-later

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define VK_NO_PROTOTYPES
#define VK_USE_PLATFORM_WIN32_KHR

#include <windows.h>
#include <vulkan/vulkan.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdio>
#include <string>
#include <string_view>
#include <vector>

namespace {

constexpr int EnvironmentInvalidExit = 72;

std::string VersionString(uint32_t version) {
    char buffer[64]{};
    std::snprintf(buffer, sizeof(buffer), "%u.%u.%u", VK_VERSION_MAJOR(version),
                  VK_VERSION_MINOR(version), VK_VERSION_PATCH(version));
    return buffer;
}

std::string SafeName(const char* value) {
    std::string result{value};
    for (char& character : result) {
        const unsigned char byte = static_cast<unsigned char>(character);
        if (byte < 0x20 || byte == 0x7f) {
            character = '?';
        }
    }
    return result;
}

const char* DeviceTypeName(VkPhysicalDeviceType type) {
    switch (type) {
    case VK_PHYSICAL_DEVICE_TYPE_OTHER:
        return "OTHER";
    case VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU:
        return "INTEGRATED_GPU";
    case VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU:
        return "DISCRETE_GPU";
    case VK_PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU:
        return "VIRTUAL_GPU";
    case VK_PHYSICAL_DEVICE_TYPE_CPU:
        return "CPU";
    default:
        return "UNKNOWN";
    }
}

bool HasExtension(const std::vector<VkExtensionProperties>& extensions, std::string_view name) {
    return std::ranges::any_of(extensions, [name](const VkExtensionProperties& extension) {
        return name == extension.extensionName;
    });
}

void PrintExtension(const char* scope, size_t device_index, std::string_view name, bool present) {
    if (device_index == static_cast<size_t>(-1)) {
        std::printf("IMP008E_VK_PREFLIGHT_%s_EXTENSION NAME=%.*s PRESENT=%u\n", scope,
                    static_cast<int>(name.size()), name.data(), present ? 1U : 0U);
    } else {
        std::printf("IMP008E_VK_PREFLIGHT_%s_EXTENSION DEVICE=%zu NAME=%.*s PRESENT=%u\n", scope,
                    device_index, static_cast<int>(name.size()), name.data(), present ? 1U : 0U);
    }
}

VkResult EnumerateInstanceExtensions(PFN_vkEnumerateInstanceExtensionProperties function,
                                     std::vector<VkExtensionProperties>& extensions) {
    uint32_t count = 0;
    VkResult result = function(nullptr, &count, nullptr);
    if (result != VK_SUCCESS) {
        return result;
    }

    for (unsigned int attempt = 0; attempt < 4; ++attempt) {
        extensions.resize(count);
        uint32_t written = count;
        result = function(nullptr, &written, extensions.empty() ? nullptr : extensions.data());
        if (result == VK_SUCCESS) {
            extensions.resize(written);
            return result;
        }
        if (result != VK_INCOMPLETE) {
            return result;
        }
        result = function(nullptr, &count, nullptr);
        if (result != VK_SUCCESS) {
            return result;
        }
    }
    return VK_INCOMPLETE;
}

VkResult EnumeratePhysicalDevices(PFN_vkEnumeratePhysicalDevices function, VkInstance instance,
                                  std::vector<VkPhysicalDevice>& devices) {
    uint32_t count = 0;
    VkResult result = function(instance, &count, nullptr);
    if (result != VK_SUCCESS) {
        return result;
    }

    for (unsigned int attempt = 0; attempt < 4; ++attempt) {
        devices.resize(count);
        uint32_t written = count;
        result = function(instance, &written, devices.empty() ? nullptr : devices.data());
        if (result == VK_SUCCESS) {
            devices.resize(written);
            return result;
        }
        if (result != VK_INCOMPLETE) {
            return result;
        }
        result = function(instance, &count, nullptr);
        if (result != VK_SUCCESS) {
            return result;
        }
    }
    return VK_INCOMPLETE;
}

VkResult EnumerateDeviceExtensions(PFN_vkEnumerateDeviceExtensionProperties function,
                                   VkPhysicalDevice device,
                                   std::vector<VkExtensionProperties>& extensions) {
    uint32_t count = 0;
    VkResult result = function(device, nullptr, &count, nullptr);
    if (result != VK_SUCCESS) {
        return result;
    }

    for (unsigned int attempt = 0; attempt < 4; ++attempt) {
        extensions.resize(count);
        uint32_t written = count;
        result = function(device, nullptr, &written,
                          extensions.empty() ? nullptr : extensions.data());
        if (result == VK_SUCCESS) {
            extensions.resize(written);
            return result;
        }
        if (result != VK_INCOMPLETE) {
            return result;
        }
        result = function(device, nullptr, &count, nullptr);
        if (result != VK_SUCCESS) {
            return result;
        }
    }
    return VK_INCOMPLETE;
}

int Inconclusive(const char* reason) {
    std::printf("IMP008E_VK_PREFLIGHT_REASON=%s\n", reason);
    std::printf("IMP008E_VK_PREFLIGHT_CLASSIFICATION=INCONCLUSIVE_ENVIRONMENT\n");
    return EnvironmentInvalidExit;
}

} // namespace

int main() {
    std::printf("IMP008E_VK_PREFLIGHT_MAIN_ENTER=PASS\n");
    std::printf("IMP008E_VK_PREFLIGHT_PROCESS_ARCH=%s\n",
#if defined(_M_ARM64) || defined(__aarch64__)
                "ARM64"
#else
                "NOT_ARM64"
#endif
    );

    HMODULE library = LoadLibraryW(L"vulkan-1.dll");
    if (library == nullptr) {
        std::printf("IMP008E_VK_PREFLIGHT_LOADER_LOAD=FAIL ERROR=%lu\n", GetLastError());
        return Inconclusive("VULKAN_LOADER_UNAVAILABLE");
    }

    char library_path[MAX_PATH]{};
    const DWORD path_length = GetModuleFileNameA(library, library_path, MAX_PATH);
    std::printf("IMP008E_VK_PREFLIGHT_LOADER_LOAD=PASS PATH=%s PATH_LENGTH=%lu\n",
                path_length == 0 ? "<unavailable>" : library_path, path_length);

    const auto get_instance_proc_addr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
        GetProcAddress(library, "vkGetInstanceProcAddr"));
    if (get_instance_proc_addr == nullptr) {
        std::printf("IMP008E_VK_PREFLIGHT_GET_INSTANCE_PROC_ADDR=FAIL\n");
        FreeLibrary(library);
        return Inconclusive("VK_GET_INSTANCE_PROC_ADDR_UNAVAILABLE");
    }
    std::printf("IMP008E_VK_PREFLIGHT_GET_INSTANCE_PROC_ADDR=PASS\n");

    const auto enumerate_instance_version = reinterpret_cast<PFN_vkEnumerateInstanceVersion>(
        get_instance_proc_addr(VK_NULL_HANDLE, "vkEnumerateInstanceVersion"));
    uint32_t loader_api_version = VK_API_VERSION_1_0;
    VkResult version_result = VK_SUCCESS;
    if (enumerate_instance_version != nullptr) {
        version_result = enumerate_instance_version(&loader_api_version);
    }
    std::printf("IMP008E_VK_PREFLIGHT_LOADER_API_RESULT=%d VERSION=%s RAW=0x%08X\n",
                version_result, VersionString(loader_api_version).c_str(), loader_api_version);
    if (version_result != VK_SUCCESS || loader_api_version < VK_API_VERSION_1_1) {
        FreeLibrary(library);
        return Inconclusive("VULKAN_1_1_LOADER_UNAVAILABLE");
    }

    const auto enumerate_instance_extensions =
        reinterpret_cast<PFN_vkEnumerateInstanceExtensionProperties>(
            get_instance_proc_addr(VK_NULL_HANDLE, "vkEnumerateInstanceExtensionProperties"));
    const auto create_instance = reinterpret_cast<PFN_vkCreateInstance>(
        get_instance_proc_addr(VK_NULL_HANDLE, "vkCreateInstance"));
    if (enumerate_instance_extensions == nullptr || create_instance == nullptr) {
        std::printf("IMP008E_VK_PREFLIGHT_GLOBAL_FUNCTIONS=FAIL\n");
        FreeLibrary(library);
        return Inconclusive("VULKAN_GLOBAL_FUNCTIONS_UNAVAILABLE");
    }
    std::printf("IMP008E_VK_PREFLIGHT_GLOBAL_FUNCTIONS=PASS\n");

    std::vector<VkExtensionProperties> instance_extensions;
    const VkResult instance_extension_result =
        EnumerateInstanceExtensions(enumerate_instance_extensions, instance_extensions);
    std::printf("IMP008E_VK_PREFLIGHT_INSTANCE_EXTENSION_ENUM_RESULT=%d COUNT=%zu\n",
                instance_extension_result, instance_extensions.size());
    if (instance_extension_result != VK_SUCCESS) {
        FreeLibrary(library);
        return Inconclusive("INSTANCE_EXTENSION_ENUMERATION_FAILED");
    }

    std::ranges::sort(instance_extensions,
                      [](const VkExtensionProperties& left,
                         const VkExtensionProperties& right) {
                          return std::string_view{left.extensionName} <
                                 std::string_view{right.extensionName};
                      });
    for (const VkExtensionProperties& extension : instance_extensions) {
        std::printf("IMP008E_VK_PREFLIGHT_INSTANCE_EXTENSION_AVAILABLE NAME=%s SPEC=%u\n",
                    extension.extensionName, extension.specVersion);
    }

    constexpr std::array RequiredInstanceExtensions{
        std::string_view{"VK_KHR_surface"},
        std::string_view{"VK_KHR_win32_surface"},
    };
    constexpr std::array RelevantOptionalInstanceExtensions{
        std::string_view{"VK_KHR_get_physical_device_properties2"},
        std::string_view{"VK_KHR_get_surface_capabilities2"},
    };

    bool win32_instance_boundary = true;
    for (const std::string_view extension : RequiredInstanceExtensions) {
        const bool present = HasExtension(instance_extensions, extension);
        PrintExtension("INSTANCE_REQUIRED", static_cast<size_t>(-1), extension, present);
        win32_instance_boundary &= present;
    }
    for (const std::string_view extension : RelevantOptionalInstanceExtensions) {
        PrintExtension("INSTANCE_OPTIONAL", static_cast<size_t>(-1), extension,
                       HasExtension(instance_extensions, extension));
    }

    std::array<const char*, RequiredInstanceExtensions.size()> enabled_extension_names{};
    uint32_t enabled_extension_count = 0;
    if (win32_instance_boundary) {
        for (size_t index = 0; index < RequiredInstanceExtensions.size(); ++index) {
            enabled_extension_names[index] = RequiredInstanceExtensions[index].data();
        }
        enabled_extension_count = static_cast<uint32_t>(enabled_extension_names.size());
    }

    const VkApplicationInfo application_info{
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pNext = nullptr,
        .pApplicationName = "IMP-008E Vulkan Preflight",
        .applicationVersion = VK_MAKE_API_VERSION(0, 1, 0, 0),
        .pEngineName = "Eden WinARM64 NCE preflight",
        .engineVersion = VK_MAKE_API_VERSION(0, 1, 0, 0),
        .apiVersion = VK_API_VERSION_1_1,
    };
    const VkInstanceCreateInfo instance_create_info{
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = nullptr,
        .flags = 0,
        .pApplicationInfo = &application_info,
        .enabledLayerCount = 0,
        .ppEnabledLayerNames = nullptr,
        .enabledExtensionCount = enabled_extension_count,
        .ppEnabledExtensionNames =
            enabled_extension_count == 0 ? nullptr : enabled_extension_names.data(),
    };

    VkInstance instance = VK_NULL_HANDLE;
    const VkResult create_result = create_instance(&instance_create_info, nullptr, &instance);
    std::printf("IMP008E_VK_PREFLIGHT_CREATE_INSTANCE_RESULT=%d MODE=%s\n", create_result,
                win32_instance_boundary ? "WIN32_REQUIRED_EXTENSIONS" : "ENUMERATION_ONLY");
    if (create_result != VK_SUCCESS || instance == VK_NULL_HANDLE) {
        FreeLibrary(library);
        return Inconclusive("VK_CREATE_INSTANCE_FAILED");
    }
    std::printf("IMP008E_VK_PREFLIGHT_CREATE_INSTANCE=PASS\n");

    const auto destroy_instance = reinterpret_cast<PFN_vkDestroyInstance>(
        get_instance_proc_addr(instance, "vkDestroyInstance"));
    const auto enumerate_physical_devices = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(
        get_instance_proc_addr(instance, "vkEnumeratePhysicalDevices"));
    const auto get_physical_device_properties =
        reinterpret_cast<PFN_vkGetPhysicalDeviceProperties>(
            get_instance_proc_addr(instance, "vkGetPhysicalDeviceProperties"));
    const auto enumerate_device_extensions =
        reinterpret_cast<PFN_vkEnumerateDeviceExtensionProperties>(
            get_instance_proc_addr(instance, "vkEnumerateDeviceExtensionProperties"));
    if (destroy_instance == nullptr || enumerate_physical_devices == nullptr ||
        get_physical_device_properties == nullptr || enumerate_device_extensions == nullptr) {
        std::printf("IMP008E_VK_PREFLIGHT_INSTANCE_FUNCTIONS=FAIL\n");
        if (destroy_instance != nullptr) {
            destroy_instance(instance, nullptr);
        }
        FreeLibrary(library);
        return Inconclusive("VULKAN_INSTANCE_FUNCTIONS_UNAVAILABLE");
    }
    std::printf("IMP008E_VK_PREFLIGHT_INSTANCE_FUNCTIONS=PASS\n");

    std::vector<VkPhysicalDevice> devices;
    const VkResult device_result =
        EnumeratePhysicalDevices(enumerate_physical_devices, instance, devices);
    std::printf("IMP008E_VK_PREFLIGHT_PHYSICAL_DEVICE_ENUM_RESULT=%d COUNT=%zu\n", device_result,
                devices.size());
    if (device_result != VK_SUCCESS || devices.empty()) {
        destroy_instance(instance, nullptr);
        FreeLibrary(library);
        return Inconclusive(device_result == VK_SUCCESS ? "ZERO_PHYSICAL_DEVICES"
                                                       : "PHYSICAL_DEVICE_ENUMERATION_FAILED");
    }

    constexpr std::array AlwaysRequiredDeviceExtensions{
        std::string_view{"VK_EXT_vertex_attribute_divisor"},
        std::string_view{"VK_KHR_driver_properties"},
        std::string_view{"VK_KHR_sampler_mirror_clamp_to_edge"},
        std::string_view{"VK_KHR_shader_float_controls"},
        std::string_view{"VK_KHR_swapchain"},
    };
    constexpr std::string_view DescriptorIndexingExtension = "VK_EXT_descriptor_indexing";

    bool usable_device_extension_boundary = false;
    for (size_t index = 0; index < devices.size(); ++index) {
        VkPhysicalDeviceProperties properties{};
        get_physical_device_properties(devices[index], &properties);
        const std::string device_name = SafeName(properties.deviceName);
        std::printf(
            "IMP008E_VK_PREFLIGHT_DEVICE INDEX=%zu NAME=%s TYPE=%s VENDOR=0x%04X DEVICE=0x%04X "
            "DRIVER_RAW=0x%08X API=%s API_RAW=0x%08X\n",
            index, device_name.c_str(), DeviceTypeName(properties.deviceType), properties.vendorID,
            properties.deviceID, properties.driverVersion,
            VersionString(properties.apiVersion).c_str(), properties.apiVersion);

        std::vector<VkExtensionProperties> device_extensions;
        const VkResult extension_result = EnumerateDeviceExtensions(
            enumerate_device_extensions, devices[index], device_extensions);
        std::printf(
            "IMP008E_VK_PREFLIGHT_DEVICE_EXTENSION_ENUM_RESULT DEVICE=%zu RESULT=%d COUNT=%zu\n",
            index, extension_result, device_extensions.size());
        if (extension_result != VK_SUCCESS) {
            continue;
        }

        std::ranges::sort(device_extensions,
                          [](const VkExtensionProperties& left,
                             const VkExtensionProperties& right) {
                              return std::string_view{left.extensionName} <
                                     std::string_view{right.extensionName};
                          });
        for (const VkExtensionProperties& extension : device_extensions) {
            std::printf(
                "IMP008E_VK_PREFLIGHT_DEVICE_EXTENSION_AVAILABLE DEVICE=%zu NAME=%s SPEC=%u\n",
                index, extension.extensionName, extension.specVersion);
        }

        bool required_extensions_present = properties.apiVersion >= VK_API_VERSION_1_1;
        for (const std::string_view extension : AlwaysRequiredDeviceExtensions) {
            const bool present = HasExtension(device_extensions, extension);
            PrintExtension("DEVICE_REQUIRED", index, extension, present);
            required_extensions_present &= present;
        }
        const bool descriptor_indexing_required = properties.apiVersion < VK_API_VERSION_1_2;
        const bool descriptor_indexing_present =
            HasExtension(device_extensions, DescriptorIndexingExtension);
        PrintExtension(descriptor_indexing_required ? "DEVICE_REQUIRED" : "DEVICE_CORE_OR_EXTENSION",
                       index, DescriptorIndexingExtension, descriptor_indexing_present);
        if (descriptor_indexing_required) {
            required_extensions_present &= descriptor_indexing_present;
        }

        std::printf("IMP008E_VK_PREFLIGHT_DEVICE_EXTENSION_BOUNDARY DEVICE=%zu RESULT=%s\n", index,
                    required_extensions_present ? "PASS" : "FAIL");
        usable_device_extension_boundary |= required_extensions_present;
    }

    destroy_instance(instance, nullptr);
    FreeLibrary(library);

    std::printf("IMP008E_VK_PREFLIGHT_WIN32_INSTANCE_BOUNDARY=%s\n",
                win32_instance_boundary ? "PASS" : "FAIL");
    std::printf("IMP008E_VK_PREFLIGHT_USABLE_DEVICE_EXTENSION_BOUNDARY=%s\n",
                usable_device_extension_boundary ? "PASS" : "FAIL");
    if (!win32_instance_boundary) {
        return Inconclusive("WIN32_INSTANCE_EXTENSIONS_UNAVAILABLE");
    }
    if (!usable_device_extension_boundary) {
        return Inconclusive("NO_DEVICE_MEETS_EDEN_EXTENSION_BOUNDARY");
    }

    std::printf("IMP008E_VK_PREFLIGHT_GATE=PASS\n");
    std::printf("IMP008E_VK_PREFLIGHT_CLASSIFICATION=PREFLIGHT_PASS\n");
    return 0;
}
