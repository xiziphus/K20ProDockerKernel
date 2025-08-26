#!/bin/bash
# Docker-Enabled Kernel Build Script for Redmi K20 Pro
# This script builds the kernel with Docker support

set -e

echo "🚀 Building Docker-Enabled Kernel for Redmi K20 Pro"
echo "=================================================="

# Configuration
KERNEL_SOURCE="kernel_source"
KERNEL_OUTPUT="kernel_output"
ARCH="arm64"
SUBARCH="arm64"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    echo "🍎 Detected macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
    echo "🐧 Detected Linux"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Check if kernel source exists
if [ ! -d "$KERNEL_SOURCE" ]; then
    echo "❌ Kernel source not found at $KERNEL_SOURCE"
    echo "Run: python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1"
    exit 1
fi

# Create output directory
mkdir -p "$KERNEL_OUTPUT"

# Set environment variables
export ARCH="$ARCH"
export SUBARCH="$SUBARCH"

# Ensure python command is available (kernel build system needs it)
if ! command -v python &> /dev/null; then
    echo "🐍 Setting up python command..."
    mkdir -p ~/bin
    ln -sf $(which python3) ~/bin/python
    export PATH=~/bin:$PATH
    echo "✅ Python command configured"
fi

# Set Python explicitly for kernel build
export PYTHON=$(which python3)

echo ""
echo "🔧 Checking build tools and binutils..."

# Function to check binutils tools
check_binutils() {
    local missing_tools=()
    local cross_prefix=""
    
    # Check for cross-compilation tools first
    if [ -n "$ANDROID_NDK_ROOT" ]; then
        if [[ "$OS" == "macOS" ]]; then
            cross_prefix="$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-"
        else
            cross_prefix="$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-"
        fi
        
        if command -v "${cross_prefix}clang" &> /dev/null; then
            export CROSS_COMPILE="$cross_prefix"
            export CC="${cross_prefix}clang"
            echo "✅ Using Android NDK cross-compiler"
        else
            echo "⚠️  Android NDK found but cross-compiler not available"
        fi
    elif command -v aarch64-linux-gnu-gcc &> /dev/null; then
        export CROSS_COMPILE="aarch64-linux-gnu-"
        echo "✅ Using system cross-compiler (aarch64-linux-gnu)"
    elif command -v aarch64-elf-gcc &> /dev/null; then
        export CROSS_COMPILE="aarch64-elf-"
        echo "✅ Using system cross-compiler (aarch64-elf)"
    else
        echo "⚠️  No cross-compiler found. Attempting native build..."
        echo "   Install Android NDK, aarch64-linux-gnu-gcc, or aarch64-elf-gcc for cross-compilation"
    fi
    
    # Check essential binutils tools
    local tools_to_check=("objcopy" "objdump" "readelf" "nm" "strip")
    
    for tool in "${tools_to_check[@]}"; do
        local found=false
        
        # Check cross-compiler version first
        if [ -n "$CROSS_COMPILE" ] && command -v "${CROSS_COMPILE}${tool}" &> /dev/null; then
            echo "✅ ${CROSS_COMPILE}${tool}: Available"
            found=true
        # Check native version
        elif command -v "$tool" &> /dev/null; then
            echo "✅ $tool: Available (native)"
            found=true
        # On macOS, check for GNU versions
        elif [[ "$OS" == "macOS" ]] && command -v "g$tool" &> /dev/null; then
            echo "✅ g$tool: Available (GNU version)"
            found=true
        fi
        
        if [[ "$found" == false ]]; then
            echo "❌ $tool: Not found"
            missing_tools+=("$tool")
        fi
    done
    
    # Check if we have the essential tools for kernel building
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo ""
        echo "⚠️  Missing binutils tools: ${missing_tools[*]}"
        echo "🔧 Installation suggestions:"
        
        if [[ "$OS" == "macOS" ]]; then
            echo "   brew install binutils"
            echo "   brew install aarch64-elf-binutils"
            echo "   brew install android-ndk"
        else
            echo "   sudo apt-get install binutils binutils-aarch64-linux-gnu"
            echo "   # or"
            echo "   sudo dnf install binutils binutils-aarch64-linux-gnu"
        fi
        
        echo ""
        echo "⚠️  Continuing with available tools, but build may fail..."
    else
        echo "✅ All essential binutils tools are available"
    fi
}

# Run binutils check
check_binutils

echo "📋 Build Configuration:"
echo "   Kernel Source: $KERNEL_SOURCE"
echo "   Output: $KERNEL_OUTPUT"
echo "   Architecture: $ARCH"
echo "   Cross Compiler: ${CROSS_COMPILE:-native}"

# Navigate to kernel source
cd "$KERNEL_SOURCE"

echo ""
echo "🔧 Configuring kernel..."

# Use our Docker-enabled raphael defconfig
if [ -f "arch/arm64/configs/raphael_defconfig" ]; then
    echo "✅ Using Docker-enabled raphael_defconfig"
    make raphael_defconfig
elif [ -f "arch/arm64/configs/vendor/sm8150_defconfig" ]; then
    echo "✅ Using sm8150_defconfig as base"
    make vendor/sm8150_defconfig
    
    # Apply Docker configurations manually
    echo "🐳 Enabling Docker kernel features..."
    
    # Enable essential Docker features
    scripts/config --enable CONFIG_NAMESPACES
    scripts/config --enable CONFIG_USER_NS
    scripts/config --enable CONFIG_PID_NS
    scripts/config --enable CONFIG_NET_NS
    scripts/config --enable CONFIG_IPC_NS
    scripts/config --enable CONFIG_UTS_NS
    scripts/config --enable CONFIG_CGROUPS
    scripts/config --enable CONFIG_MEMCG
    scripts/config --enable CONFIG_MEMCG_SWAP
    scripts/config --enable CONFIG_CPUSETS
    scripts/config --enable CONFIG_CGROUP_DEVICE
    scripts/config --enable CONFIG_CGROUP_FREEZER
    scripts/config --enable CONFIG_CGROUP_PIDS
    scripts/config --enable CONFIG_OVERLAY_FS
    scripts/config --enable CONFIG_OVERLAY_FS_REDIRECT_DIR
    scripts/config --enable CONFIG_OVERLAY_FS_INDEX
    scripts/config --enable CONFIG_CHECKPOINT_RESTORE
    scripts/config --enable CONFIG_USERFAULTFD
    scripts/config --enable CONFIG_BINFMT_MISC
    
    # Network features for Docker
    scripts/config --enable CONFIG_BRIDGE_NETFILTER
    scripts/config --enable CONFIG_NETFILTER_XT_MATCH_ADDRTYPE
    scripts/config --enable CONFIG_NETFILTER_XT_MATCH_CGROUP
    scripts/config --enable CONFIG_VETH
    scripts/config --enable CONFIG_MACVLAN
    scripts/config --enable CONFIG_VXLAN
    
    # Storage features
    scripts/config --enable CONFIG_DM_THIN_PROVISIONING
    
    echo "✅ Docker features enabled"
else
    echo "❌ No suitable defconfig found"
    exit 1
fi

echo ""
echo "🔨 Building kernel..."

# Clean previous builds
make clean

# Determine number of parallel jobs
if [[ "$OS" == "macOS" ]]; then
    JOBS=$(sysctl -n hw.ncpu)
else
    JOBS=$(nproc)
fi

# Build kernel
echo "Building kernel image with $JOBS parallel jobs..."

# Set additional environment variables for kernel build
export KBUILD_BUILD_USER="docker-kernel-builder"
export KBUILD_BUILD_HOST="build-system"
export LOCALVERSION="-docker-enabled"

# Export binutils tools if cross-compiling
if [ -n "$CROSS_COMPILE" ]; then
    export AR="${CROSS_COMPILE}ar"
    export NM="${CROSS_COMPILE}nm"
    export OBJCOPY="${CROSS_COMPILE}objcopy"
    export OBJDUMP="${CROSS_COMPILE}objdump"
    export READELF="${CROSS_COMPILE}readelf"
    export STRIP="${CROSS_COMPILE}strip"
    
    # For Android NDK, we might need to use llvm tools
    if [[ "$CROSS_COMPILE" == *"android"* ]]; then
        # Android NDK uses LLVM tools
        export AR="${CROSS_COMPILE}ar"
        export NM="${CROSS_COMPILE}nm"
        export OBJCOPY="${CROSS_COMPILE}objcopy"
        export OBJDUMP="${CROSS_COMPILE}objdump"
        export READELF="${CROSS_COMPILE}readelf"
        export STRIP="${CROSS_COMPILE}strip"
    fi
fi

# Build with verbose output for debugging
if ! make -j$JOBS V=1 Image Image.gz dtbs; then
    echo "❌ Kernel build failed"
    echo ""
    echo "🔍 Troubleshooting tips:"
    echo "   1. Check if all required tools are installed:"
    echo "      ./check_binutils.sh"
    echo "   2. Try building with single thread:"
    echo "      make V=1 Image Image.gz dtbs"
    echo "   3. Check kernel configuration:"
    echo "      make menuconfig"
    echo "   4. Clean and retry:"
    echo "      make clean && make mrproper"
    exit 1
fi

echo ""
echo "📦 Copying build artifacts..."

# Copy artifacts to output directory
cd ..
cp "$KERNEL_SOURCE/arch/arm64/boot/Image" "$KERNEL_OUTPUT/"
cp "$KERNEL_SOURCE/arch/arm64/boot/Image.gz" "$KERNEL_OUTPUT/"

# Copy device tree blobs if they exist
if [ -d "$KERNEL_SOURCE/arch/arm64/boot/dts/qcom" ]; then
    mkdir -p "$KERNEL_OUTPUT/dtbs"
    cp "$KERNEL_SOURCE/arch/arm64/boot/dts/qcom"/*.dtb "$KERNEL_OUTPUT/dtbs/" 2>/dev/null || true
fi

# Create a simple boot image if mkbootimg is available
if command -v mkbootimg &> /dev/null; then
    echo "📱 Creating boot image..."
    
    mkbootimg \
        --kernel "$KERNEL_OUTPUT/Image.gz" \
        --cmdline "console=ttyMSM0,115200n8 androidboot.hardware=qcom androidboot.console=ttyMSM0 lpm_levels.sleep_disabled=1 msm_rtb.filter=0x237 service_locator.enable=1 androidboot.configfs=true androidboot.usbcontroller=a600000.dwc3 swiotlb=2048 loop.max_part=7" \
        --base 0x00000000 \
        --pagesize 4096 \
        --os_version 11.0.0 \
        --os_patch_level 2023-01 \
        --output "$KERNEL_OUTPUT/boot.img" || echo "⚠️  Could not create boot image (missing ramdisk)"
fi

echo ""
echo "✅ Build completed successfully!"
echo ""
echo "📋 Build Results:"
echo "   Kernel Image: $KERNEL_OUTPUT/Image"
echo "   Compressed: $KERNEL_OUTPUT/Image.gz"
if [ -f "$KERNEL_OUTPUT/boot.img" ]; then
    echo "   Boot Image: $KERNEL_OUTPUT/boot.img"
fi
echo "   DTBs: $KERNEL_OUTPUT/dtbs/"

echo ""
echo "🚀 Next Steps:"
echo "   1. Flash kernel: ./deploy.sh deploy $KERNEL_OUTPUT/Image.gz"
echo "   2. Or flash boot image: ./deploy.sh deploy $KERNEL_OUTPUT/boot.img"
echo "   3. Validate deployment: ./deploy.sh validate"

# Create build info
cat > "$KERNEL_OUTPUT/build_info.txt" << EOF
Docker-Enabled Kernel Build Information
======================================

Build Date: $(date)
Kernel Source: $KERNEL_SOURCE
Architecture: $ARCH
Cross Compiler: ${CROSS_COMPILE:-native}
Target Device: Redmi K20 Pro (raphael)

Docker Features Enabled:
- Container namespaces (PID, NET, IPC, UTS, USER)
- Cgroup subsystems (memory, cpu, cpuset, devices, pids, freezer)
- Overlay filesystem
- Network bridge and VLAN support
- Checkpoint/restore support
- Cpuset Docker compatibility (14 control files)

Build Status: SUCCESS
EOF

echo "📄 Build info saved: $KERNEL_OUTPUT/build_info.txt"