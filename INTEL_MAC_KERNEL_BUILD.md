# Docker-Enabled Kernel Build Guide for Intel Mac

This guide provides step-by-step instructions for building a Docker-enabled kernel for the Redmi K20 Pro on an Intel Mac.

## 🎯 Overview

We'll build a custom Android kernel with Docker support that includes:
- Container namespaces (PID, NET, IPC, UTS, USER)
- Cgroup subsystems (memory, cpu, cpuset, devices, pids, freezer)
- Overlay filesystem support
- Network bridge and VLAN support
- Checkpoint/restore support (CRIU)
- Cpuset Docker compatibility modifications

## 📋 Prerequisites

### System Requirements
- **Intel Mac** (x86_64 architecture)
- **macOS** with Xcode Command Line Tools
- **Python 3** (system version recommended)
- **Git** for source code management
- **At least 20GB free disk space**
- **8GB+ RAM** (16GB recommended)

### Target Device
- **Redmi K20 Pro (raphael)**
- **Unlocked bootloader**
- **Fastboot access**

## 🚀 Quick Start

### 1. Fix Python Environment (Intel Mac Specific)

Intel Macs often have Python compatibility issues with ARM64 Homebrew. Fix this first:

```bash
# Fix Python symlink for kernel build system
./fix_python.sh

# Verify Python is working
python --version
python3 --version
```

### 2. Set Up Cross-Compilation Toolchain

For Intel Mac, we need ARM64 cross-compiler:

```bash
# Option A: Android NDK (Recommended)
# Download Android NDK for macOS
curl -O https://dl.google.com/android/repository/android-ndk-r25c-darwin.zip
unzip android-ndk-r25c-darwin.zip
sudo mv android-ndk-r25c /opt/

# Set environment variables
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-

# Option B: Homebrew Cross-Compiler (Alternative)
brew install aarch64-elf-gcc
export CROSS_COMPILE=aarch64-elf-
```

### 3. Download and Configure Kernel Source

```bash
# Download LineageOS kernel source for K20 Pro
python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1

# Apply Docker configurations
python3 kernel_build/scripts/config_tool.py apply-docker-config

# Verify configuration
python3 kernel_build/scripts/config_tool.py summary
```

### 4. Build the Kernel

```bash
# Build Docker-enabled kernel
./build_docker_kernel.sh

# Monitor build progress
./monitor.sh system
```

### 5. Deploy to Device

```bash
# Put device in fastboot mode
# Power off device, then hold Volume Down + Power

# Deploy kernel
./deploy.sh deploy kernel_output/boot.img

# Validate deployment
./deploy.sh validate
```

## 📊 Monitoring and Diagnostics

### System Health Check

```bash
# Quick system status
./monitor.sh system

# Comprehensive health report
./monitor.sh health

# Interactive dashboard
./monitor.sh dashboard
```

### Docker Compatibility Check

```bash
# Check Docker daemon
./monitor.sh docker --check-once

# Container diagnostics
./monitor.sh containers

# Continuous monitoring
./monitor.sh watch
```

## 🔧 Detailed Build Process

### Step 1: Environment Setup

```bash
# Check current system status
./monitor.sh system --quiet

# Install dependencies (if needed)
python3 kernel_build/scripts/install_setup.py

# Verify environment
python3 kernel_build/scripts/install_setup.py --check
```

### Step 2: Kernel Source Preparation

```bash
# Download kernel source
python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1

# Check source info
python3 kernel_build/scripts/setup_kernel_source.py info

# Apply patches (if any)
python3 kernel_build/scripts/setup_kernel_source.py apply-patches
```

### Step 3: Docker Configuration

```bash
# Apply Docker kernel configurations
python3 kernel_build/scripts/config_tool.py apply-docker-config

# Apply cpuset modifications for Docker compatibility
python3 kernel_build/scripts/config_tool.py apply-cpuset-mods

# Generate configuration summary
python3 kernel_build/scripts/config_tool.py summary > docker_config_summary.txt
```

### Step 4: Kernel Compilation

```bash
# Set build environment
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-

# Build kernel with monitoring
./build_docker_kernel.sh 2>&1 | tee build.log

# Check build results
ls -la kernel_output/
```

### Step 5: Deployment and Testing

```bash
# Validate kernel image
python3 kernel_build/scripts/validate_deployment.py kernel_output/Image.gz

# Deploy to device (device in fastboot mode)
./deploy.sh deploy kernel_output/boot.img

# Verify deployment
./deploy.sh validate

# Check device status
./deploy.sh status
```

## 🐛 Troubleshooting

### Common Issues on Intel Mac

#### 1. Python "Bad CPU type" Error

**Problem**: `python: error: can't exec '/opt/homebrew/bin/python' (errno=Bad CPU type in executable)`

**Solution**:
```bash
# Fix Python symlink
./fix_python.sh

# Or manually create symlink
rm -f ~/bin/python
ln -sf /usr/bin/python3 ~/bin/python
export PATH=~/bin:$PATH
```

#### 2. Cross-Compiler Not Found

**Problem**: `aarch64-linux-android29-gcc: command not found`

**Solution**:
```bash
# Download and install Android NDK
curl -O https://dl.google.com/android/repository/android-ndk-r25c-darwin.zip
unzip android-ndk-r25c-darwin.zip
sudo mv android-ndk-r25c /opt/

# Set correct environment
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-
```

#### 3. Make Command Issues

**Problem**: Kernel build fails with make errors

**Solution**:
```bash
# Ensure GNU Make is available
brew install make

# Use specific make version if needed
export PATH="/usr/local/opt/make/libexec/gnubin:$PATH"

# Clean and rebuild
cd kernel_source
make clean
cd ..
./build_docker_kernel.sh
```

#### 4. Disk Space Issues

**Problem**: Build fails due to insufficient disk space

**Solution**:
```bash
# Check disk usage
df -h

# Clean up Docker (if installed)
docker system prune -a

# Clean kernel build artifacts
rm -rf kernel_output/
cd kernel_source && make clean && cd ..
```

### Build Diagnostics

```bash
# Run comprehensive diagnostics
./monitor.sh containers

# Check kernel features
python3 kernel_build/scripts/container_diagnostics.py --check kernel

# Analyze build environment
./monitor.sh system --output build_env_report.json
```

## 📁 Build Outputs

After successful build, you'll find:

```
kernel_output/
├── Image              # Raw kernel image
├── Image.gz           # Compressed kernel (for fastboot)
├── boot.img           # Complete boot image (if mkbootimg available)
├── dtbs/              # Device tree blobs
└── build_info.txt     # Build information and configuration
```

## 🔍 Verification

### Kernel Features Verification

```bash
# Check Docker configurations in built kernel
python3 kernel_build/scripts/config_tool.py verify kernel_output/

# Verify cpuset modifications
grep -r "docker\." kernel_source/kernel/cgroup/cpuset.c
```

### Device Testing

After flashing the kernel:

```bash
# Check kernel version on device
adb shell uname -a

# Verify Docker-required features
adb shell cat /proc/config.gz | gunzip | grep -E "(NAMESPACE|CGROUP|OVERLAY)"

# Test container capabilities
adb shell ls -la /sys/fs/cgroup/
```

## 📊 Performance Monitoring

### Build Performance

```bash
# Monitor build with system resources
./monitor.sh watch &
./build_docker_kernel.sh

# Analyze build time
tail -f build.log | grep -E "(Building|Finished|Error)"
```

### Runtime Monitoring

```bash
# Start continuous monitoring
./monitor.sh dashboard

# Export HTML dashboard
./monitor.sh dashboard --html --once
```

## 🔄 Automation

### Automated Build Script

Create `auto_build.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting automated Docker kernel build for Intel Mac"

# Fix Python environment
./fix_python.sh

# Set up environment
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-

# Download source if needed
if [ ! -d "kernel_source" ]; then
    python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1
fi

# Apply Docker configurations
python3 kernel_build/scripts/config_tool.py apply-docker-config

# Build kernel
./build_docker_kernel.sh

# Generate reports
./monitor.sh health --output "build_report_$(date +%Y%m%d_%H%M%S).json"

echo "✅ Build completed successfully!"
echo "📁 Kernel output: kernel_output/"
echo "🚀 Deploy with: ./deploy.sh deploy kernel_output/boot.img"
```

### Continuous Integration

For automated builds, create `.github/workflows/build-kernel.yml`:

```yaml
name: Build Docker Kernel
on: [push, pull_request]

jobs:
  build:
    runs-on: macos-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install Android NDK
      run: |
        curl -O https://dl.google.com/android/repository/android-ndk-r25c-darwin.zip
        unzip android-ndk-r25c-darwin.zip
        sudo mv android-ndk-r25c /opt/
    
    - name: Build Kernel
      run: |
        export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
        export ARCH=arm64
        export SUBARCH=arm64
        export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-
        ./auto_build.sh
    
    - name: Upload Artifacts
      uses: actions/upload-artifact@v3
      with:
        name: kernel-output
        path: kernel_output/
```

## 📚 Additional Resources

### Documentation Files
- `KERNEL_BUILD_GUIDE.md` - General build guide
- `BUILD_STATUS.md` - Current build status
- `kernel_build/deployment/README.md` - Deployment guide
- `kernel_build/README.md` - Build system documentation

### Configuration Files
- `kernel_build/config/deployment_config.json` - Deployment settings
- `kernel_build/config/docker_kernel_config.txt` - Docker kernel options

### Scripts and Tools
- `build_docker_kernel.sh` - Main build script
- `deploy.sh` - Deployment script
- `monitor.sh` - Monitoring tools launcher
- `fix_python.sh` - Python environment fix

## 🎯 Next Steps

After successful kernel build and deployment:

1. **Install Docker on Android**: Deploy Docker binaries to the device
2. **Test Container Support**: Run basic container operations
3. **Performance Tuning**: Optimize kernel parameters for containers
4. **Security Configuration**: Set up SELinux policies for Docker
5. **Container Migration**: Test CRIU checkpoint/restore functionality

## 🤝 Support

If you encounter issues:

1. **Check System Status**: `./monitor.sh system`
2. **Run Diagnostics**: `./monitor.sh containers`
3. **Review Build Logs**: Check `build.log` and monitoring reports
4. **Verify Environment**: Ensure all prerequisites are met
5. **Clean and Retry**: Clean build artifacts and retry

---

**Happy Building! 🚀**

This kernel will enable full Docker container support on your Redmi K20 Pro, including advanced features like container migration and checkpoint/restore capabilities.