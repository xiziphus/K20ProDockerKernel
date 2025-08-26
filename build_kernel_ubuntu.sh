#!/bin/bash
# Quick Kernel Build Script for Ubuntu (assumes dependencies are installed)
# Use setup_and_build_ubuntu.sh for complete setup with dependency installation

set -e

echo "🚀 Building Docker-Enabled Kernel for K20 Pro on Ubuntu"
echo "======================================================="

# Check if we're on a Debian/Ubuntu system
if ! command -v apt-get &> /dev/null; then
    echo "⚠️  This script is optimized for Ubuntu/Debian"
    echo "   For other distributions, use: ./build_docker_kernel.sh"
fi

# Quick dependency check
echo "🔍 Checking essential dependencies..."

MISSING_DEPS=()

# Check cross-compiler
if ! command -v aarch64-linux-gnu-gcc &> /dev/null; then
    echo "❌ ARM64 cross-compiler not found"
    MISSING_DEPS+=("gcc-aarch64-linux-gnu")
fi

# Check essential build tools
for tool in make gcc python3 bc bison flex; do
    if ! command -v $tool &> /dev/null; then
        echo "❌ $tool not found"
        MISSING_DEPS+=("$tool")
    fi
done

# Check for kernel build essentials
if ! dpkg -l | grep -q libssl-dev; then
    MISSING_DEPS+=("libssl-dev")
fi

if ! dpkg -l | grep -q libelf-dev; then
    MISSING_DEPS+=("libelf-dev")
fi

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo ""
    echo "❌ Missing dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "🔧 Quick fix - run this command:"
    echo "   sudo apt-get update && sudo apt-get install -y ${MISSING_DEPS[*]}"
    echo ""
    echo "🚀 Or use the complete setup script:"
    echo "   ./setup_and_build_ubuntu.sh"
    echo ""
    exit 1
fi

echo "✅ Essential dependencies found"

# Set Ubuntu-specific environment
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PYTHON=$(which python3)

# Create python symlink if needed
if ! command -v python &> /dev/null; then
    echo "🐍 Creating python symlink..."
    mkdir -p ~/bin
    ln -sf $(which python3) ~/bin/python
    export PATH=~/bin:$PATH
fi

echo ""
echo "📋 Build Configuration:"
echo "   OS: Ubuntu/Debian"
echo "   Architecture: $ARCH"
echo "   Cross Compiler: $CROSS_COMPILE"
echo "   Python: $PYTHON"
echo "   Jobs: $(nproc)"

# Check kernel source
if [ ! -d "kernel_source" ]; then
    echo ""
    echo "❌ Kernel source not found"
    echo "🔧 Download kernel source first:"
    echo "   python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1"
    exit 1
fi

# Run the main build script
echo ""
echo "🚀 Starting kernel build..."
exec ./build_docker_kernel.sh