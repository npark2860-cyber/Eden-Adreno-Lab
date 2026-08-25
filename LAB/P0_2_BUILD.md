# P0.2 Windows ARM64 Test Package

This branch exists only to build a runnable Windows ARM64 package from the validated P0.2 source head.

Source head:
`lab/p0-2-transfer-rp-reasons @ ffac24ffaebdd0cf4c0c7d4249f8ad28f7284808`

Build environment:

- native GitHub `windows-11-arm` runner,
- clang-cl 22.1.4,
- ARM64 Vulkan SDK 1.4.341.1,
- Release + Ninja,
- Qt enabled with Eden's bundled Qt path,
- OpenGL disabled because Windows ARM64 does not support Eden's OpenGL backend,
- LTO disabled.

Expected artifact name:
`Eden-P0.2-Windows-ARM64-ffac24ff`

The package includes `RUN_P0_2.ps1`, the log analyzer and the P0/P0.2 capture documentation.
