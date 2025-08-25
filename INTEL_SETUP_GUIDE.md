# Intel x86_64 Setup Guide for Docker-Enabled Kernel Build

Since you're on Intel architecture, here's the optimized setup for cross-compiling the ARM64 kernel.

## 🖥️ Intel-Specific Setup

### Option 1: Android NDK (Recommended)

The Android NDK provides the best cross-compilation toolchain for Android kernels:

```bash
# Download Android NDK for Linux x86_64
cd ~/Downloads
wget https://dl.google.com/android/repository/android-ndk-r25c-linux.zip
unzip android-ndk-r25c-linux.zip
sudo mv android-ndk-r25c /opt/

# Set environment variables
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
export PATH=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH

# Add to your shell profile for persistence
echo 'export ANDROID_NDK_ROOT=/opt/android-ndk-r25c' >> ~/.bashrc
echo 'export PATH=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Option 2: System Cross-Compiler

If you prefer using system packages:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# Fedora/RHEL/CentOS
sudo dnf install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# Arch Linux
sudo pacman -S aarch64-linux-gnu-gcc
```

### Option 3: Linaro Toolchain

For the latest ARM64 toolchain:

```bash
# Download Linaro GCC toolchain
cd ~/Downloads
wget https://releases.linaro.org/components/toolchain/binaries/latest-7/aarch64-linux-gnu/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz
tar -xf gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz
sudo mv gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu /opt/

# Set environment
export PATH=/opt/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu/bin:$PATH
export CROSS_COMPILE=aarch64-linux-gnu-
```

## 🔧 Intel Build Environment Setup

### 1. Install Build Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install build-essential git python3 python3-pip
sudo apt-get install libssl-dev libelf-dev bison flex bc
sudo apt-get install device-tree-compiler

# Fedora/RHEL/CentOS
sudo dnf groupinstall "Development Tools"
sudo dnf install git python3 python3-pip
sudo dnf install openssl-devel elfutils-libelf-devel bison flex bc
sudo dnf install dtc

# Arch Linux
sudo pacman -S base-devel git python python-pip
sudo pacman -S openssl libelf bison flex bc dtc
```

### 2. Fix Python Symlink

The kernel build system expects `python` command:

```bash
# Create python symlink
sudo ln -sf /usr/bin/python3 /usr/bin/python

# Or add to PATH
mkdir -p ~/bin
ln -s /usr/bin/python3 ~/bin/python
export PATH=~/bin:$PATH
```

### 3. Verify Cross-Compiler

```bash
# Test Android NDK compiler
aarch64-linux-android29-clang --version

# Or test system compiler
aarch64-linux-gnu-gcc --version

# Test compilation
echo 'int main(){return 0;}' | aarch64-linux-gnu-gcc -x c - -o test_arm64
file test_arm64
rm test_arm64
```

## 🚀 Quick Build Commands for Intel

Once you have the cross-compiler set up:

```bash
# 1. Set up environment (choose one based on your toolchain)

# For Android NDK:
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-

# For system cross-compiler:
export CROSS_COMPILE=aarch64-linux-gnu-

# 2. Set kernel architecture
export ARCH=arm64
export SUBARCH=arm64

# 3. Build the Docker-enabled kernel
./build_docker_kernel.sh
```

## 🔍 Intel-Specific Troubleshooting

### Issue: "python: command not found"
```bash
# Solution 1: Create symlink
sudo ln -sf /usr/bin/python3 /usr/bin/python

# Solution 2: Use python3 explicitly
sed -i 's/python /python3 /g' kernel_source/scripts/gcc-version.sh
```

### Issue: Cross-compiler not found
```bash
# Check if cross-compiler is in PATH
which aarch64-linux-gnu-gcc
which aarch64-linux-android29-clang

# Add to PATH if needed
export PATH=/opt/android-ndk-r25c/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH
```

### Issue: Missing headers
```bash
# Install kernel build dependencies
sudo apt-get install linux-headers-$(uname -r)
sudo apt-get install libssl-dev libelf-dev
```

### Issue: "No rule to make target 'Image'"
```bash
# Clean and reconfigure
cd kernel_source
make clean
make mrproper
make raphael_defconfig
make -j$(nproc) Image Image.gz dtbs
```

## 📊 Intel Performance Optimization

### Multi-core Build
```bash
# Use all CPU cores
make -j$(nproc)

# Or specify core count
make -j8  # for 8 cores

# Check CPU info
nproc
lscpu
```

### Memory Optimization
```bash
# For systems with limited RAM, reduce parallel jobs
make -j4  # Use fewer cores if you have <8GB RAM

# Monitor memory usage during build
htop
```

### Build Time Estimates (Intel)
- **4-core Intel i5**: ~30-45 minutes
- **8-core Intel i7**: ~15-25 minutes  
- **16-core Intel i9**: ~10-15 minutes

## 🎯 Complete Intel Build Workflow

```bash
# 1. Install Android NDK
wget https://dl.google.com/android/repository/android-ndk-r25c-linux.zip
unzip android-ndk-r25c-linux.zip
sudo mv android-ndk-r25c /opt/
export ANDROID_NDK_ROOT=/opt/android-ndk-r25c

# 2. Set up environment
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-

# 3. Fix python symlink
sudo ln -sf /usr/bin/python3 /usr/bin/python

# 4. Build kernel
./build_docker_kernel.sh

# 5. Deploy to device
./deploy.sh deploy kernel_output/boot.img
```

## 🔐 Intel Security Considerations

### Secure Boot
If you have Secure Boot enabled:
```bash
# Check Secure Boot status
mokutil --sb-state

# You may need to disable it for kernel development
# Or sign your kernel modules
```

### Virtualization
If using VMs for development:
```bash
# Enable nested virtualization
# Add to VM configuration: -cpu host,+vmx
```

---

**This Intel-specific guide optimizes the Docker-enabled kernel build process for x86_64 systems with proper cross-compilation setup.**