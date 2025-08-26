#!/bin/bash
# Complete Ubuntu Setup and Kernel Build Script for Docker-Enabled K20 Pro Kernel
# This script installs all dependencies and builds the kernel

set -e

echo "🚀 Docker-Enabled Kernel Setup and Build for Ubuntu"
echo "===================================================="

# Check if running on Ubuntu/Debian
if ! command -v apt-get &> /dev/null; then
    echo "❌ This script is designed for Ubuntu/Debian systems with apt-get"
    echo "   For other distributions, please install dependencies manually"
    exit 1
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Running as root. This script will install system packages."
    SUDO=""
else
    echo "🔐 This script requires sudo privileges to install packages"
    SUDO="sudo"
fi

echo ""
echo "📦 Installing build dependencies..."

# Update package list
echo "🔄 Updating package list..."
$SUDO apt-get update

# Install essential build tools
echo "🔧 Installing essential build tools..."
$SUDO apt-get install -y \
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

# Install cross-compilation toolchain
echo "🎯 Installing ARM64 cross-compilation toolchain..."
$SUDO apt-get install -y \
    gcc-aarch64-linux-gnu \
    binutils-aarch64-linux-gnu \
    libc6-dev-arm64-cross

# Install additional binutils tools
echo "🔨 Installing additional binutils tools..."
$SUDO apt-get install -y \
    binutils \
    binutils-dev \
    binutils-multiarch

# Create python symlink if needed (kernel build system expects 'python')
if ! command -v python &> /dev/null; then
    echo "🐍 Creating python symlink..."
    $SUDO ln -sf /usr/bin/python3 /usr/bin/python
fi

# Install Android tools (optional but recommended)
echo "📱 Installing Android development tools..."
$SUDO apt-get install -y \
    android-tools-adb \
    android-tools-fastboot

# Try to install mkbootimg (for creating boot images)
echo "🥾 Installing mkbootimg..."
if ! $SUDO apt-get install -y mkbootimg 2>/dev/null; then
    echo "⚠️  mkbootimg not available in repositories, will try pip..."
    pip3 install --user mkbootimg || echo "⚠️  Could not install mkbootimg via pip"
fi

echo ""
echo "✅ All dependencies installed successfully!"

echo ""
echo "🔍 Verifying installation..."

# Verify cross-compiler
if command -v aarch64-linux-gnu-gcc &> /dev/null; then
    echo "✅ ARM64 cross-compiler: $(aarch64-linux-gnu-gcc --version | head -n1)"
else
    echo "❌ ARM64 cross-compiler not found"
    exit 1
fi

# Verify binutils
BINUTILS_OK=true
for tool in objcopy objdump readelf nm strip; do
    if command -v aarch64-linux-gnu-$tool &> /dev/null; then
        echo "✅ aarch64-linux-gnu-$tool: Available"
    else
        echo "❌ aarch64-linux-gnu-$tool: Not found"
        BINUTILS_OK=false
    fi
done

if [[ "$BINUTILS_OK" == false ]]; then
    echo "❌ Some binutils tools are missing"
    exit 1
fi

# Verify Python
if command -v python &> /dev/null && command -v python3 &> /dev/null; then
    echo "✅ Python: $(python --version) -> $(python3 --version)"
else
    echo "❌ Python not properly configured"
    exit 1
fi

echo ""
echo "🏗️  Setting up kernel source..."

# Check if kernel source exists
if [ ! -d "kernel_source" ]; then
    echo "📥 Downloading kernel source..."
    if [ -f "kernel_build/scripts/setup_kernel_source.py" ]; then
        python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1
    else
        echo "❌ Kernel source setup script not found"
        echo "   Please run this script from the project root directory"
        exit 1
    fi
else
    echo "✅ Kernel source already exists"
fi

echo ""
echo "🔧 Configuring build environment..."

# Set environment variables
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PYTHON=$(which python3)

# Verify kernel configuration
if [ -f "kernel_source/arch/arm64/configs/raphael_defconfig" ]; then
    echo "✅ Docker-enabled raphael_defconfig found"
elif [ -f "kernel_build/output/docker_raphael_defconfig" ]; then
    echo "📋 Copying Docker-enabled configuration..."
    cp kernel_build/output/docker_raphael_defconfig kernel_source/arch/arm64/configs/raphael_defconfig
    echo "✅ Docker-enabled raphael_defconfig installed"
else
    echo "⚠️  Docker-enabled configuration not found, will use base config"
fi

echo ""
echo "🚀 Starting kernel build..."

# Make the build script executable
chmod +x build_docker_kernel.sh

# Run the kernel build
if ./build_docker_kernel.sh; then
    echo ""
    echo "🎉 Kernel build completed successfully!"
    echo ""
    echo "📋 Build Results:"
    if [ -d "kernel_output" ]; then
        ls -la kernel_output/
        echo ""
        echo "📄 Build information:"
        if [ -f "kernel_output/build_info.txt" ]; then
            cat kernel_output/build_info.txt
        fi
    fi
    
    echo ""
    echo "🔍 Running validation..."
    if [ -f "kernel_build/scripts/validate_kernel_artifacts.py" ]; then
        python3 kernel_build/scripts/validate_kernel_artifacts.py --skip-boot-test
    fi
    
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Connect your K20 Pro device"
    echo "   2. Boot into fastboot mode: adb reboot bootloader"
    echo "   3. Flash kernel: ./deploy.sh deploy kernel_output/Image.gz"
    echo "   4. Or use deployment package in kernel_build/deployment/"
    echo ""
    echo "⚠️  IMPORTANT: Always backup your current kernel before flashing!"
    
else
    echo ""
    echo "❌ Kernel build failed!"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check build logs above for specific errors"
    echo "   2. Verify all dependencies: ./check_binutils.sh"
    echo "   3. Try manual build steps:"
    echo "      cd kernel_source"
    echo "      make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- raphael_defconfig"
    echo "      make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j\$(nproc) Image Image.gz dtbs"
    echo ""
    echo "   4. Check available disk space and memory"
    echo "   5. Ensure kernel source is properly downloaded"
    
    exit 1
fi

echo ""
echo "✅ Setup and build process completed!"
echo "📦 Your Docker-enabled kernel is ready for deployment!"