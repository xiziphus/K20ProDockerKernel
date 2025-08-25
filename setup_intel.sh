#!/bin/bash
# Intel x86_64 Setup Script for Docker-Enabled Kernel Build
# This script sets up cross-compilation environment on Intel systems

set -e

echo "🖥️  Intel x86_64 Setup for Docker-Enabled Kernel Build"
echo "====================================================="

# Check if running on Intel
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" ]]; then
    echo "⚠️  This script is optimized for Intel x86_64 systems"
    echo "   Detected architecture: $ARCH"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ Detected Intel x86_64 system"

# Check OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✅ Linux detected"
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "❌ This script is for Linux. Use KERNEL_BUILD_GUIDE.md for macOS"
    exit 1
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Install build dependencies
echo ""
echo "📦 Installing build dependencies..."

if command -v apt-get &> /dev/null; then
    echo "Using apt (Ubuntu/Debian)"
    sudo apt-get update
    sudo apt-get install -y build-essential git python3 python3-pip
    sudo apt-get install -y libssl-dev libelf-dev bison flex bc device-tree-compiler
    sudo apt-get install -y binutils binutils-dev binutils-aarch64-linux-gnu
    sudo apt-get install -y wget unzip curl
elif command -v dnf &> /dev/null; then
    echo "Using dnf (Fedora/RHEL)"
    sudo dnf groupinstall -y "Development Tools"
    sudo dnf install -y git python3 python3-pip
    sudo dnf install -y openssl-devel elfutils-libelf-devel bison flex bc dtc
    sudo dnf install -y binutils binutils-devel binutils-aarch64-linux-gnu
    sudo dnf install -y wget unzip curl
elif command -v pacman &> /dev/null; then
    echo "Using pacman (Arch Linux)"
    sudo pacman -S --noconfirm base-devel git python python-pip
    sudo pacman -S --noconfirm openssl libelf bison flex bc dtc
    sudo pacman -S --noconfirm binutils aarch64-linux-gnu-binutils
    sudo pacman -S --noconfirm wget unzip curl
else
    echo "❌ Unsupported package manager. Install dependencies manually:"
    echo "   - build-essential/base-devel"
    echo "   - git, python3, python3-pip"
    echo "   - libssl-dev, libelf-dev, bison, flex, bc, dtc"
    echo "   - binutils, binutils-dev, binutils-aarch64-linux-gnu"
    exit 1
fi

echo "✅ Build dependencies installed"

# Verify binutils installation
echo ""
echo "🔧 Verifying binutils installation..."

if command -v objdump &> /dev/null && command -v readelf &> /dev/null; then
    OBJDUMP_VERSION=$(objdump --version | head -n1)
    READELF_VERSION=$(readelf --version | head -n1)
    echo "✅ Native binutils available: $OBJDUMP_VERSION"
    
    # Check for cross-compilation binutils
    if command -v aarch64-linux-gnu-objdump &> /dev/null; then
        CROSS_OBJDUMP_VERSION=$(aarch64-linux-gnu-objdump --version | head -n1)
        echo "✅ Cross-compilation binutils available: $CROSS_OBJDUMP_VERSION"
    else
        echo "⚠️  Cross-compilation binutils not found (may use NDK tools instead)"
    fi
else
    echo "❌ Binutils installation failed"
    exit 1
fi

# Fix Python symlink
echo ""
echo "🐍 Setting up Python symlink..."

if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ Python already available: $PYTHON_VERSION"
else
    echo "Creating python -> python3 symlink..."
    if [[ -w /usr/bin ]]; then
        sudo ln -sf /usr/bin/python3 /usr/bin/python
        echo "✅ Created system-wide python symlink"
    else
        mkdir -p ~/bin
        ln -sf /usr/bin/python3 ~/bin/python
        export PATH=~/bin:$PATH
        echo "✅ Created user python symlink"
        echo "Add ~/bin to your PATH: export PATH=~/bin:\$PATH"
    fi
fi

# Download and install Android NDK
echo ""
echo "📱 Setting up Android NDK..."

NDK_VERSION="r25c"
NDK_DIR="/opt/android-ndk-$NDK_VERSION"
NDK_URL="https://dl.google.com/android/repository/android-ndk-$NDK_VERSION-linux.zip"

if [[ -d "$NDK_DIR" ]]; then
    echo "✅ Android NDK already installed at $NDK_DIR"
else
    echo "Downloading Android NDK $NDK_VERSION..."
    
    cd /tmp
    wget -O "android-ndk-$NDK_VERSION-linux.zip" "$NDK_URL"
    
    echo "Installing Android NDK..."
    unzip -q "android-ndk-$NDK_VERSION-linux.zip"
    sudo mv "android-ndk-$NDK_VERSION" "$NDK_DIR"
    rm "android-ndk-$NDK_VERSION-linux.zip"
    
    echo "✅ Android NDK installed at $NDK_DIR"
fi

# Set up environment variables
echo ""
echo "⚙️  Setting up environment variables..."

ENV_SCRIPT="setup_cross_compile.sh"
cat > "$ENV_SCRIPT" << EOF
#!/bin/bash
# Cross-compilation environment for Docker-enabled kernel build

export ANDROID_NDK_ROOT="$NDK_DIR"
export ARCH=arm64
export SUBARCH=arm64
export CROSS_COMPILE=\$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-
export PATH=\$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:\$PATH

echo "🔧 Cross-compilation environment configured"
echo "   NDK: \$ANDROID_NDK_ROOT"
echo "   Architecture: \$ARCH"
echo "   Cross-compiler: \$CROSS_COMPILE"
EOF

chmod +x "$ENV_SCRIPT"

# Test cross-compiler
echo ""
echo "🧪 Testing cross-compiler..."

source "./$ENV_SCRIPT"

if command -v aarch64-linux-android29-clang &> /dev/null; then
    CLANG_VERSION=$(aarch64-linux-android29-clang --version | head -n1)
    echo "✅ Cross-compiler working: $CLANG_VERSION"
    
    # Test compilation
    echo 'int main(){return 0;}' | aarch64-linux-android29-clang -x c - -o /tmp/test_arm64 2>/dev/null
    if [[ $? -eq 0 ]]; then
        FILE_INFO=$(file /tmp/test_arm64)
        echo "✅ Cross-compilation test passed: $FILE_INFO"
        rm -f /tmp/test_arm64
    else
        echo "⚠️  Cross-compilation test failed, but NDK is installed"
    fi
else
    echo "❌ Cross-compiler not found. Check NDK installation."
    exit 1
fi

# Run kernel build system setup
echo ""
echo "🚀 Running kernel build system setup..."

if [[ -f "kernel_build/scripts/install_setup.py" ]]; then
    python3 kernel_build/scripts/install_setup.py
else
    echo "⚠️  Kernel build system not found. Run from project root."
fi

echo ""
echo "🎉 Intel x86_64 setup completed successfully!"
echo ""
echo "📋 Summary:"
echo "   ✅ Build dependencies installed"
echo "   ✅ Python symlink configured"
echo "   ✅ Android NDK $NDK_VERSION installed"
echo "   ✅ Cross-compiler tested"
echo "   ✅ Environment script created: $ENV_SCRIPT"
echo ""
echo "🚀 Next steps:"
echo "   1. Source environment: source $ENV_SCRIPT"
echo "   2. Download kernel: python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1"
echo "   3. Apply patches: python3 kernel_build/scripts/config_tool.py apply --defconfig kernel_source/arch/arm64/configs/raphael_defconfig --backup"
echo "   4. Build kernel: ./build_docker_kernel.sh"
echo ""
echo "📚 Documentation:"
echo "   - Complete guide: KERNEL_BUILD_GUIDE.md"
echo "   - Intel-specific: INTEL_SETUP_GUIDE.md"
echo "   - Build status: BUILD_STATUS.md"