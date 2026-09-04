cmake_minimum_required(VERSION 3.31)
project(imp006_x18_step LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

get_filename_component(EDEN_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(ARCHITECTURE arm64)
set(ARCHITECTURE_arm64 ON)
add_compile_definitions(ARCHITECTURE_arm64)
set(YUZU_DISABLE_LLVM ON)
set(DYNARMIC_TESTS OFF CACHE BOOL "" FORCE)
set(DYNARMIC_USE_LLVM OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)

list(APPEND CMAKE_MODULE_PATH "${EDEN_ROOT}/src/dynarmic/CMakeModules")
include(CMakeDependentOption)

find_package(Boost 1.57 REQUIRED)
find_package(fmt 8 CONFIG REQUIRED)
find_package(unordered_dense REQUIRED)

include(FetchContent)
FetchContent_Declare(
    oaknut
    URL https://github.com/eden-emulator/oaknut/archive/refs/tags/v2.0.3.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(oaknut)
# The exact Oaknut target is already available above. Dynarmic's non-required find_package(oaknut)
# must not try to consume the FetchContent build-tree package config, which has no installed
# oaknutTargets.cmake file.
set(CMAKE_DISABLE_FIND_PACKAGE_oaknut TRUE)

add_library(common INTERFACE)
target_include_directories(common INTERFACE "${EDEN_ROOT}/src")

add_subdirectory("${EDEN_ROOT}/src/dynarmic" "${CMAKE_BINARY_DIR}/dynarmic")

add_executable(imp006_x18_step x18_step_smoke.cpp)
target_include_directories(imp006_x18_step PRIVATE "${EDEN_ROOT}/src")
target_link_libraries(imp006_x18_step PRIVATE dynarmic)
