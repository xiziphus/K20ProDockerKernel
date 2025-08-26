# Android Container - Docker-Enabled Kernel for K20 Pro
**English** | [中文](README_CN.md)

This project enables running Linux containers (Docker, Podman, etc.) natively on Android devices by building a Docker-enabled kernel. It supports cross-architecture container migration from x86 to ARM64 and provides a complete containerization solution for Android.

## 🎯 Project Scope & Deliverables

### What This Project Provides:
- **Docker-enabled Android kernel** for Redmi K20 Pro (raphael)
- **Automated kernel build system** with patch management
- **Container runtime support** built into the kernel
- **Cross-architecture migration capabilities** using CRIU
- **Comprehensive tooling** for kernel configuration and patching

### What This Project Does NOT Include:
- Complete Android ROM/firmware
- Android system apps or framework modifications
- Bootloader or recovery modifications

## 📱 ROM Compatibility

### ✅ Primary Target ROM:
- **PixelExperience (PE)** - Official target ROM (CONFIG_LOCALVERSION="-F1xy-0.19-pe")

### ✅ Compatible ROMs (AOSP-based):
- **LineageOS** - High compatibility
- **crDroid** - AOSP-based, should work
- **Resurrection Remix** - AOSP-based
- **Havoc OS** - AOSP-based
- **Pure AOSP** - Maximum compatibility

### ⚠️ May Need Modifications:
- **MIUI** - Heavily modified, may require significant changes
- Other heavily customized ROMs

### 📋 ROM Requirements:
- Support for custom kernels
- Standard Android kernel interfaces
- Built for Redmi K20 Pro (raphael) device
- Android 10/11 era compatibility

-----

**Target Device:** Redmi K20 Pro (raphael) - Android 10/11 era

<img src="picture/5.png" width = "475" height = "289"  />

## 🚀 Quick Start

### Ubuntu/Debian Users (Recommended)
```bash
# Complete automated setup and build
./setup_and_build_ubuntu.sh

# Or if dependencies are already installed
./build_kernel_ubuntu.sh
```

### Other Linux Distributions
```bash
# Manual build (install dependencies first)
./build_docker_kernel.sh
```

### macOS Users
```bash
# Install dependencies first
brew install binutils aarch64-elf-binutils android-ndk

# Then build
./build_docker_kernel.sh
```

📖 **Detailed guides**: [Ubuntu Build Guide](UBUNTU_BUILD_GUIDE.md) | [macOS Guide](INTEL_MAC_KERNEL_BUILD.md)

## Project Directory

```
├── CoClient # Android client, used to manage containers in Android
│
├── README.md
├── README_CN.md
├── backend # Cross-architecture migration backend service program
│ ├── README.md
│ ├── README_EN.md
│ ├── backend.py
│ ├── container_migrate.py
│ ├── docker-popcorn-notify
│ ├── image_migrate.py
│ ├── mnt.py
│ └── recode.sh
├── criu # Use criu module in Android
│
├── docker # Run Docker container in Android
│ ├── README.md
│ ├── README_CN.md
│ ├── containerd
│ ├── containerd-shim
│ ├── ctr
│ ├── docker
│ ├── docker-init
│ ├── docker-proxy
│ ├── dockerd
│ └── runc
├── files  # Android total cgroup configuration file and docker startup script, diff files.
│   ├── aosp.diff
│   ├── cgroups.json
│   ├── dockerd.sh
│   ├── kernel.diff
│   └── raphael_defconfig
├── migration # Cross-architecture migration related
│   ├── README.md
│   ├── README_CN.md
│   ├── build-tar-static.sh
│   └── tar
├── picture # effect picture
│   ├── 1.png
│   └── 2.png
├── kernel_build/              # 🆕 Automated kernel build system
│   ├── config/               # Kernel configuration management
│   ├── patch/                # Patch application system
│   ├── scripts/              # Command-line tools
│   ├── tests/                # Test suites
│   └── utils/                # Utility functions
└── pixel-OS/                 # PixelExperience build instructions
    ├── README.md
    └── README_CN.md
```

## 🚀 Quick Start Guide

### 1. Automated Kernel Build (Recommended)

```bash
# Apply all patches and modifications in one command
python kernel_build/scripts/patch_integration.py apply-all

# Check comprehensive status
python kernel_build/scripts/patch_integration.py status

# Rollback everything if needed
python kernel_build/scripts/patch_integration.py rollback-all
```

### 2. Manual Kernel Configuration

```bash
# Apply Docker-required kernel configurations
python kernel_build/scripts/config_tool.py apply files/raphael_defconfig

# Validate configuration
python kernel_build/scripts/config_tool.py validate

# Export final configuration
python kernel_build/scripts/config_tool.py export
```

### 3. Patch Management

```bash
# Apply kernel patches
python kernel_build/scripts/patch_tool.py apply files/kernel.diff files/aosp.diff

# Modify cpuset.c for Docker compatibility
python kernel_build/scripts/cpuset_tool.py modify

# Verify patches
python kernel_build/scripts/patch_tool.py verify files/kernel.diff
```

## 🔧 Kernel Build System Features

### ✅ Automated Patch Application
- **Docker-required kernel patches** from `files/kernel.diff`
- **AOSP integration patches** from `files/aosp.diff`
- **Cpuset.c modifications** for Docker compatibility
- **Conflict detection and resolution**
- **Automatic backup and rollback**

### ✅ Configuration Management
- **Kernel config validation** and merging
- **Docker-required options** verification
- **Configuration export** and reporting
- **Custom configuration support**

### ✅ Comprehensive Testing
- **Patch verification** and integrity checks
- **Configuration validation** tests
- **Build system integration** tests
- **Rollback functionality** tests

### ✅ Debugging and Troubleshooting Tools
- **Comprehensive log analysis** for kernel and Docker issues
- **Network debugging utilities** for container connectivity
- **Storage debugging tools** for overlay filesystem issues
- **System health monitoring** and diagnostics
- **Automated issue detection** and recommendations

## 📋 Build Process Steps

### Traditional Manual Process:
1. Enter the pixel-OS directory and compile the PixelExperience source code
2. Enter the docker directory, modify the Android kernel source code, and port docker to the Android operating system
3. Enter the criu directory, modify the Android kernel source code, and port criu to the Android operating system
4. Enter the migration directory and modify the Android kernel source code so that Android supports cross-architecture migration
5. Enter the backend directory and use the ubuntu back-end service program to conduct cross-architecture migration experiments
6. Enter the CoClient directory and use the Android application to manage the Android container

### 🆕 Automated Process:
1. **Run automated kernel build**: `python kernel_build/scripts/patch_integration.py apply-all`
2. **Compile kernel** with your preferred AOSP build system
3. **Flash kernel** to your K20 Pro device
4. **Install Docker binaries** from the `docker/` directory
5. **Configure runtime environment** using `files/dockerd.sh`
6. **Test container functionality**

## 🔍 Debugging and Troubleshooting

### Comprehensive Diagnostics
```bash
# Run complete system diagnostics
python kernel_build/scripts/debug_toolkit.py

# Analyze system logs for issues
python kernel_build/scripts/log_analyzer.py --hours 24

# Debug network connectivity
python kernel_build/scripts/network_debugger.py

# Check storage and overlay filesystem
python kernel_build/scripts/storage_debugger.py
```

### Quick Health Check
```bash
# System monitoring and health check
python kernel_build/scripts/system_monitor.py --health-check

# Docker daemon status and diagnostics
python kernel_build/scripts/docker_health_monitor.py

# Container runtime diagnostics
python kernel_build/scripts/container_diagnostics.py
```

### Log Analysis Features
- **Automated error pattern detection** in system logs
- **Kernel panic and error analysis**
- **Docker daemon issue identification**
- **Network connectivity problem diagnosis**
- **Storage and filesystem error detection**
- **Comprehensive reporting** with recommendations

## ⚠️ Important Notes

- **Kernel Only**: This project builds a Docker-enabled kernel, not a complete ROM
- **ROM Compatibility**: Designed for PixelExperience, compatible with most AOSP-based ROMs
- **Device Specific**: Only for Redmi K20 Pro (raphael) device
- **Manual Kernel Modification**: If you prefer manual modification, refer to the diff files in the `files/` directory

### Effect

**1. The rendering of the container running in Android.**

<table>
  <tr>
    <td>Docker info</td>
     <td>hello-world container and criu</td>
  </tr>
  <tr>
    <td><img src="picture/1.png" width="460" height="995" alt="图片1"/></td>
    <td><img src="picture/2.png" width="460" height="995" alt="图片2"/></td>
  </tr>
 </table>

**2. The rendering of the criu on android platform, simple looper experiment**

<img src="picture/3.png" alt="图片3"/>

**3. The rendering of the cross-architecture container migration**

On the left is the container in the ubuntu operating system, and on the right is the container in Android. It can be seen that the container in Android continues to run after the container state in ubuntu, achieving the purpose of cross-architecture migration.

<img src="picture/4.png" alt="图片4"/>