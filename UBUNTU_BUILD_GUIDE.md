# Ubuntu Kernel Build Guide

This guide explains how to build the Docker-enabled kernel for Redmi K20 Pro on Ubuntu/Debian systems.

## Quick Start (Recommended)

For a complete automated setup and build:

```bash
./setup_and_build_ubuntu.sh
```

This script will:
- Install all required dependencies
- Download kernel source (if needed)
- Configure the build environment
- Build the Docker-enabled kernel
- Validate the build artifacts
- Create deployment packages

## Manual Build (If Dependencies Already Installed)

If you already have the build dependencies installed:

```bash
./build_kernel_ubuntu.sh
```

## Step-by-Step Manual Process

### 1. Install Dependencies

```bash
# Update package list
sudo apt-get update

# Install essential build tools
sudo apt-get install -y \
    build-essential \
    git \
    python3 \
    python3-pip \
    curl \
    wget \
    unzip \
    bc \
    bison \
    flex \
    libssl-dev \
    libelf-dev \
    libncurses5-dev \
    libncursesw5-dev \
    rsync \
    dwarves

# Install ARM64 cross-compilation toolchain
sudo apt-get install -y \
    gcc-aarch64-linux-gnu \
    binutils-aarch64-linux-gnu \
    libc6-dev-arm64-cross

# Install additional binutils
sudo apt-get install -y \
    binutils \
    binutils-dev \
    binutils-multiarch

# Install Android tools (optional)
sudo apt-get install -y \
    android-tools-adb \
    android-tools-fastboot

# Create python symlink (kernel build system needs 'python')
sudo ln -sf /usr/bin/python3 /usr/bin/python
```

### 2. Download Kernel Source

```bash
python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1
```

### 3. Build Kernel

```bash
./build_docker_kernel.sh
```

### 4. Validate Build

```bash
python3 kernel_build/scripts/validate_kernel_artifacts.py --skip-boot-test
```

## Build Requirements

### System Requirements
- Ubuntu 18.04+ or Debian 10+ (recommended)
- At least 8GB RAM (16GB recommended)
- At least 50GB free disk space
- Internet connection for downloading dependencies

### Required Packages
- **Build essentials**: `build-essential`, `git`, `python3`
- **Kernel build tools**: `bc`, `bison`, `flex`, `libssl-dev`, `libelf-dev`
- **Cross-compiler**: `gcc-aarch64-linux-gnu`, `binutils-aarch64-linux-gnu`
- **Additional tools**: `rsync`, `dwarves`, `libncurses5-dev`

### Optional but Recommended
- **Android tools**: `android-tools-adb`, `android-tools-fastboot`
- **Boot image tools**: `mkbootimg`

## Troubleshooting

### Common Issues

#### 1. "No cross-compiler found"
```bash
# Install ARM64 cross-compiler
sudo apt-get install gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu
```

#### 2. "python: command not found"
```bash
# Create python symlink
sudo ln -sf /usr/bin/python3 /usr/bin/python
```

#### 3. "libssl-dev not found"
```bash
# Install development libraries
sudo apt-get install libssl-dev libelf-dev libncurses5-dev
```

#### 4. "make: *** No rule to make target"
```bash
# Clean and reconfigure
cd kernel_source
make clean
make mrproper
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- raphael_defconfig
```

#### 5. Build fails with "No space left on device"
```bash
# Check disk space
df -h
# Clean temporary files
sudo apt-get clean
sudo apt-get autoremove
```

### Verification Commands

Check if dependencies are properly installed:

```bash
# Check cross-compiler
aarch64-linux-gnu-gcc --version

# Check binutils
aarch64-linux-gnu-objcopy --version
aarch64-linux-gnu-objdump --version

# Check build tools
make --version
python3 --version
bc --version

# Run comprehensive check
./check_binutils.sh
```

## Build Outputs

After successful build, you'll find:

```
kernel_output/
├── Image              # Raw kernel image
├── Image.gz           # Compressed kernel image
├── dtbs/              # Device tree blobs
│   └── *.dtb         # Device-specific DTB files
├── boot.img           # Flashable boot image (if mkbootimg available)
└── build_info.txt     # Build information

kernel_build/deployment/
└── docker_kernel_raphael_YYYYMMDD_HHMMSS.zip  # Complete deployment package
```

## Deployment

### Option 1: Use Deployment Script
```bash
./deploy.sh deploy kernel_output/Image.gz
```

### Option 2: Manual Fastboot
```bash
# Boot device into fastboot mode
adb reboot bootloader

# Flash kernel
fastboot flash boot kernel_output/boot.img
# OR flash kernel and DTB separately
fastboot flash kernel kernel_output/Image.gz
fastboot flash dtb kernel_output/dtbs/sm8150-raphael.dtb

# Reboot device
fastboot reboot
```

### Option 3: Use Deployment Package
Extract the ZIP file from `kernel_build/deployment/` and follow the included instructions.

## Validation

Validate your build before deployment:

```bash
# Validate artifacts
python3 kernel_build/scripts/validate_kernel_artifacts.py --skip-boot-test

# Test on device (requires connected device)
python3 kernel_build/scripts/validate_kernel_artifacts.py
```

## Docker Setup After Kernel Flash

After successfully flashing the Docker-enabled kernel:

1. **Install Docker binaries** on your Android device
2. **Configure Docker daemon** with appropriate settings
3. **Test container functionality**

Refer to the main project documentation for Docker setup instructions.

## Performance Tips

### Faster Builds
```bash
# Use all CPU cores
make -j$(nproc)

# Use ccache for faster rebuilds
sudo apt-get install ccache
export USE_CCACHE=1
export CCACHE_DIR=~/.ccache
ccache -M 50G
```

### Reduce Build Time
- Use SSD storage for faster I/O
- Increase RAM if possible (16GB+ recommended)
- Close unnecessary applications during build

## Support

### Getting Help
1. Check the troubleshooting section above
2. Run `./check_binutils.sh` to verify dependencies
3. Check build logs for specific error messages
4. Ensure you have sufficient disk space and memory

### Common Build Times
- **First build**: 30-60 minutes (depending on hardware)
- **Incremental builds**: 5-15 minutes
- **Clean rebuild**: 20-40 minutes

### Hardware Recommendations
- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: SSD preferred, 50GB+ free space
- **Network**: Stable internet for downloading dependencies

---

**⚠️ Important**: Always backup your current kernel before flashing a custom kernel. Custom kernels can potentially brick your device if not properly tested.

**🔒 Security**: This kernel includes Docker support which may affect device security. Only install if you understand the implications.