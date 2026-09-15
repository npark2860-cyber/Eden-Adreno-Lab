from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


# Windows HostMemory::Impl fallback allocator. Preserve all custom NCE reservation/direct-map code.
replace_once(
    """    ~Impl() {\n        Release();\n    }\n\n    void Map(size_t virtual_offset, size_t host_offset, size_t length, MemoryPermission perms) {\n""",
    """    ~Impl() {\n        Release();\n    }\n\n    void* Allocate(size_t size) {\n        auto* ptr = VirtualAlloc(nullptr, size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);\n        if (ptr == nullptr) {\n            LOG_CRITICAL(HW_Memory, \"Failed to allocate fallback buffer with size {:#x}, error {}\", size, GetLastError());\n        }\n        return ptr;\n    }\n\n    void Map(size_t virtual_offset, size_t host_offset, size_t length, MemoryPermission perms) {\n""",
    "windows Allocate",
)

# POSIX portions of PR4219 host_memory.cpp.
replace_once(
    """#else // ^^^ Windows ^^^ vvv POSIX vvv\n\n#ifdef ARCHITECTURE_arm64\n""",
    """#else // ^^^ Windows ^^^ vvv POSIX vvv\n\n#ifndef MAP_NOCORE\n#define MAP_NOCORE 0\n#endif\n\n#ifdef ARCHITECTURE_arm64\n""",
    "MAP_NOCORE define",
)

replacements = [
    (
        "MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);",
        "MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_NOCORE, -1, 0);",
        "arm64 ChooseVirtualBase MAP_NOCORE",
    ),
    (
        "MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_ALIGNED_SUPER, -1, 0);",
        "MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_ALIGNED_SUPER | MAP_NOCORE, -1, 0);",
        "aligned ChooseVirtualBase MAP_NOCORE",
    ),
    (
        "return mmap(nullptr, virtual_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);",
        "return mmap(nullptr, virtual_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_NOCORE, -1, 0);",
        "generic ChooseVirtualBase MAP_NOCORE",
    ),
    (
        "mmap(nullptr, backing_size, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, -1, 0)",
        "mmap(nullptr, backing_size, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE | MAP_NOCORE, -1, 0)",
        "private backing MAP_NOCORE",
    ),
    (
        "mmap(nullptr, backing_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)",
        "mmap(nullptr, backing_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_NOCORE, fd, 0)",
        "shared backing MAP_NOCORE",
    ),
]
for old, new, label in replacements:
    replace_once(old, new, label)

# After the Windows destructor was transformed, this plain destructor anchor is the POSIX Impl.
replace_once(
    """    ~Impl() {\n        Release();\n    }\n\n    void Map(size_t virtual_offset, size_t host_offset, size_t length, MemoryPermission perms) {\n""",
    """    ~Impl() {\n        Release();\n    }\n\n    void* Allocate(size_t size) {\n        auto* ptr = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);\n        if (ptr == MAP_FAILED) {\n            LOG_CRITICAL(HW_Memory, \"Failed to allocate fallback buffer with size {:#x}, {}\", size, strerror(errno));\n        }\n        return ptr;\n    }\n\n    void Map(size_t virtual_offset, size_t host_offset, size_t length, MemoryPermission perms) {\n""",
    "posix Allocate",
)

replace_once(
    """    LOG_WARNING(HW_Memory, \"Platform doesn't support fastmem\");\n    fallback_buffer.emplace(backing_size);\n    backing_base = fallback_buffer->data();\n    virtual_base = nullptr;\n""",
    """    LOG_WARNING(HW_Memory, \"Platform doesn't support fastmem\");\n    backing_base = static_cast<u8*>(mmap(nullptr, backing_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));\n    virtual_base = nullptr;\n""",
    "unsupported-platform fallback",
)

replace_once(
    """    } else {\n        impl.reset();\n        LOG_WARNING(HW_Memory, \"Platform can support fastmem, but can't create it\");\n        fallback_buffer.emplace(backing_size);\n        backing_base = fallback_buffer->data();\n        virtual_base = nullptr;\n    }\n#endif\n}\n\nHostMemory::~HostMemory() = default;\n""",
    """    } else {\n        LOG_WARNING(HW_Memory, \"Platform can support fastmem, but can't create it\");\n        fallback_buffer = true;\n        backing_base = static_cast<u8*>(impl->Allocate(backing_size));\n        virtual_base = nullptr;\n        impl.reset();\n    }\n#endif\n}\n\nHostMemory::~HostMemory() {\n#ifdef _WIN32\n    if (fallback_buffer) {\n        VirtualFree(backing_base, backing_size, MEM_RELEASE);\n    }\n#else\n    if (fallback_buffer) {\n        munmap(backing_base, backing_size);\n    }\n#endif\n}\n""",
    "fallback lifetime",
)

path.write_text(text, encoding="utf-8")
print("PR4219_HOST_MEMORY_TRANSFORM=PASS")
