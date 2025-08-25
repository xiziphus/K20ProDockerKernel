# Docker-Enabled Kernel Build Guide for Redmi K20 Pro

This guide walks you through building a Docker-enabled Android kernel for the Redmi K20 Pro (raphael) from start to finish.

## 📋 Prerequisites

### System Requirements
- **Linux or macOS** (recommended: Ubuntu 20.04+ or macOS 10.15+)
- **Python 3.6+**
- **Git**
- **Build tools** (gcc, make, etc.)
- **50GB+ free disk space**
- **8GB+ RAM** (16GB recommended)

### Android Development Tools
- **Android NDK** (for cross-compilation)
- **AOSP build tools** (optional but recommended)
- **fastboot/adb** (for deployment)

## 🚀 Step-by-Step Build Process

### Step 1: Environment Setup

First, let's set up the build environment:

```bash
# Run automated setup
./setup.sh

# Or run manually with dependency installation
python3 kernel_build/scripts/install_setup.py --install-deps --verbose
```

This will:
- ✅ Check system compatibility
- ✅ Validate Python environment
- ✅ Check build dependencies
- ✅ Set up project structure
- ✅ Create environment configuration

### Step 1.5: Install Cross-Compilation Tools

For macOS:
```bash
# Install essential build tools including binutils
brew install binutils aarch64-elf-binutils

# Install Android NDK
brew install android-ndk

# Set environment variable
export ANDROID_NDK_ROOT=/opt/homebrew/share/android-ndk

# Or install cross-compiler directly
brew install aarch64-elf-gcc

# Verify binutils installation
objdump --version
aarch64-elf-objdump --version
```

For Linux:
```bash
# Ubuntu/Debian
sudo apt-get install gcc-aarch64-linux-gnu

# Or download Android NDK
wget https://dl.google.com/android/repository/android-ndk-r25c-linux.zip
unzip android-ndk-r25c-linux.zip
export ANDROID_NDK_ROOT=$PWD/android-ndk-r25c
```

### Step 2: Get Kernel Source

Use our automated kernel source setup:

```bash
# List available kernel sources
python3 kernel_build/scripts/setup_kernel_source.py list

# Download LineageOS 18.1 kernel (recommended)
python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1

# Check kernel source info
python3 kernel_build/scripts/setup_kernel_source.py info
```

Available options:
- **lineage-18.1**: LineageOS 18.1 (Android 11) - Stable ✅
- **lineage-19.1**: LineageOS 19.1 (Android 12) - Stable ✅  
- **lineage-20**: LineageOS 20 (Android 13) - Beta 🧪

The script will:
- ✅ Download kernel source to `kernel_source/`
- ✅ Verify kernel integrity
- ✅ Set up build environment
- ✅ Create environment setup script

### Step 3: Apply Docker Patches

Apply Docker-enabling configurations and patches:

```bash
# Apply Docker kernel configuration
python3 kernel_build/scripts/config_tool.py apply --defconfig kernel_source/arch/arm64/configs/raphael_defconfig --backup

# Apply cpuset modifications for Docker compatibility
python3 kernel_build/scripts/cpuset_tool.py --kernel-source kernel_source modify

# Check status
python3 kernel_build/scripts/patch_integration.py --kernel-source kernel_source status
```

This will:
- ✅ Apply 50+ Docker-required kernel configurations
- ✅ Modify cpuset.c with 14 Docker control files
- ✅ Create backups for rollback
- ✅ Validate Docker compatibility

### Step 4: Set Up Build Environment

Set up the cross-compilation environment:

```bash
# Set up toolchain (if not using AOSP build system)
python3 kernel_build/scripts/toolchain_setup.py

# Set environment variables
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=aarch64-linux-android-

# If using Android NDK:
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-
```

### Step 5: Configure Kernel

Apply the Docker-enabled configuration:

```bash
# Navigate to kernel source
cd kernel_source

# Apply the Docker-enabled defconfig
make docker_raphael_defconfig

# Or copy our generated config:
cp ../kernel_build/output/docker_raphael_defconfig .config

# Verify configuration
python3 ../kernel_build/scripts/config_tool.py validate
```

### Step 6: Build Kernel

Build the Docker-enabled kernel using our automated build script:

```bash
# Build Docker-enabled kernel
./build_docker_kernel.sh
```

Or manually:
```bash
# Set up environment
source setup_env.sh

# Navigate to kernel source
cd kernel_source

# Configure kernel
make raphael_defconfig

# Build kernel
make clean
make -j$(nproc) Image Image.gz dtbs
```

Expected build time: 15-45 minutes depending on your system.

**Note**: You need a cross-compiler for ARM64. The build script will detect and use:
1. Android NDK (if `ANDROID_NDK_ROOT` is set)
2. System cross-compiler (`aarch64-linux-gnu-gcc`)
3. Native build (will likely fail on x86/x64 systems)

### Step 7: Create Boot Image

Create a flashable boot image:

```bash
# Create output directory
mkdir -p ../kernel_output

# Copy kernel artifacts
cp arch/arm64/boot/Image ../kernel_output/
cp arch/arm64/boot/Image.gz ../kernel_output/
cp arch/arm64/boot/dts/qcom/*.dtb ../kernel_output/

# If you have mkbootimg tool:
mkbootimg \
    --kernel arch/arm64/boot/Image.gz \
    --ramdisk ../files/ramdisk.img \
    --dtb arch/arm64/boot/dts/qcom/sm8150-mtp.dtb \
    --cmdline "console=ttyMSM0,115200n8 androidboot.hardware=qcom androidboot.console=ttyMSM0" \
    --base 0x00000000 \
    --pagesize 4096 \
    --os_version 11.0.0 \
    --os_patch_level 2023-01 \
    --output ../kernel_output/boot.img
```

### Step 8: Validate Build

Verify the kernel was built correctly:

```bash
# Return to project root
cd ..

# Validate build artifacts
python3 kernel_build/scripts/build_kernel.py --validate-only

# Check kernel size and format
ls -lh kernel_output/
file kernel_output/Image.gz
```

### Step 9: Deploy to Device

Deploy the kernel to your K20 Pro:

```bash
# Check device connection
./deploy.sh check

# Deploy kernel (device must be in fastboot mode)
./deploy.sh deploy kernel_output/boot.img

# Or use the Python script directly:
python3 kernel_build/scripts/deploy_kernel.py deploy kernel_output/boot.img
```

### Step 10: Validate Deployment

After the device boots, validate the Docker-enabled kernel:

```bash
# Validate deployment
./deploy.sh validate

# Or run detailed validation:
python3 kernel_build/scripts/validate_deployment.py --verbose
```

## 📊 Expected Outputs

### Build Artifacts
```
kernel_output/
├── Image              # Raw kernel image
├── Image.gz           # Compressed kernel
├── boot.img           # Flashable boot image
├── sm8150-mtp.dtb     # Device tree blob
└── build_report.json  # Build information
```

### Validation Results
- ✅ Docker kernel features available
- ✅ Cgroup subsystems working
- ✅ Namespace support enabled
- ✅ Overlay filesystem available
- ✅ Container creation possible

## 🔧 Build Configuration

### Docker-Enabled Features
The kernel includes these Docker-required features:

#### Container Support
- `CONFIG_NAMESPACES=y` - Namespace isolation
- `CONFIG_PID_NS=y` - Process namespaces
- `CONFIG_NET_NS=y` - Network namespaces
- `CONFIG_USER_NS=y` - User namespaces

#### Cgroup Support
- `CONFIG_CGROUPS=y` - Control groups
- `CONFIG_MEMCG=y` - Memory control
- `CONFIG_CPUSETS=y` - CPU affinity
- `CONFIG_CGROUP_DEVICE=y` - Device control

#### Storage Support
- `CONFIG_OVERLAY_FS=y` - Overlay filesystem
- `CONFIG_DM_THIN_PROVISIONING=y` - Thin provisioning

#### Network Support
- `CONFIG_BRIDGE_NETFILTER=y` - Bridge networking
- `CONFIG_VETH=y` - Virtual ethernet
- `CONFIG_MACVLAN=y` - MAC VLANs

## 🚨 Troubleshooting

### Common Build Issues

#### Missing Dependencies
```bash
# Ubuntu/Debian
sudo apt-get install build-essential git python3 python3-pip
sudo apt-get install gcc-aarch64-linux-gnu
sudo apt-get install binutils binutils-dev binutils-aarch64-linux-gnu

# macOS
brew install git python3 make
brew install binutils aarch64-elf-binutils
```

#### Cross-Compiler Issues
```bash
# Check cross-compiler
which $CROSS_COMPILE-gcc
$CROSS_COMPILE-gcc --version

# Set correct path
export PATH=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH
```

#### Build Failures
```bash
# Clean and retry
make clean
make mrproper

# Check configuration
make menuconfig

# Verbose build
make V=1 -j1 Image
```

### Deployment Issues

#### Device Not Detected
```bash
# Check fastboot
fastboot devices

# Reboot to fastboot
adb reboot bootloader
```

#### Boot Loop
```bash
# Flash stock kernel
fastboot flash boot stock_boot.img

# Or use backup
./deploy.sh rollback kernel_build/backups/kernels/boot_backup_TIMESTAMP.img
```

## 📚 Additional Resources

### Kernel Source Repositories
- **LineageOS**: https://github.com/LineageOS/android_kernel_xiaomi_sm8150
- **PixelExperience**: Check device-specific repos
- **AOSP**: https://android.googlesource.com/kernel/

### Build Tools
- **Android NDK**: https://developer.android.com/ndk/downloads
- **AOSP Build**: https://source.android.com/setup/build
- **mkbootimg**: Part of Android build tools

### Documentation
- **Kernel Config**: `kernel_build/config/README.md`
- **Patch System**: `kernel_build/patch/README.md`
- **Deployment**: `kernel_build/deployment/README.md`

## ⚠️ Important Notes

### Device Compatibility
- **Only for Redmi K20 Pro (raphael/raphaelin)**
- **Requires unlocked bootloader**
- **Test with PixelExperience ROM first**

### Safety Precautions
- **Always backup original kernel**
- **Test on non-daily driver device first**
- **Have fastboot recovery ready**
- **Keep stock ROM/kernel for recovery**

### Performance Considerations
- **Docker overhead on mobile hardware**
- **Battery impact from container workloads**
- **Storage space for container images**

---

**This guide provides a complete workflow for building and deploying a Docker-enabled kernel for the Redmi K20 Pro. Follow each step carefully and ensure you have proper backups before flashing.**