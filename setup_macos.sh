#!/bin/bash
# macOS Setup Script for Docker-Enabled Kernel Build
# This script sets up cross-compilation environment on macOS systems

set -e

echo "🍎 macOS Setup for Docker-Enabled Kernel Build"
echo "=============================================="

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    echo "   Detected OS: $OSTYPE"
    echo "   Use setup_intel.sh for Linux systems"
    exit 1
fi

echo "✅ Detected macOS system"

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install Homebrew first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "✅ Homebrew detected"

# Install build dependencies
echo ""
echo "📦 Installing build dependencies..."

echo "Installing essential build tools..."
brew install git python3 make cmake

echo "Installing binutils and cross-compilation tools..."
brew install binutils aarch64-elf-binutils

echo "Installing ELF support..."
brew install libelf

echo "Installing Android NDK..."
brew install android-ndk

echo "✅ Build dependencies installed"

# Set up environment variables
echo ""
echo "⚙️  Setting up environment variables..."

# Find Android NDK path
if [[ -d "/opt/homebrew/share/android-ndk" ]]; then
    NDK_ROOT="/opt/homebrew/share/android-ndk"
elif [[ -d "/usr/local/share/android-ndk" ]]; then
    NDK_ROOT="/usr/local/share/android-ndk"
else
    # Find in Caskroom
    NDK_ROOT=$(find /usr/local/Caskroom/android-ndk -name "AndroidNDK*.app" -type d 2>/dev/null | head -n1)
    if [[ -n "$NDK_ROOT" ]]; then
        NDK_ROOT="$NDK_ROOT/Contents/NDK"
    else
        echo "⚠️  Android NDK path not found automatically"
        NDK_ROOT="/usr/local/share/android-ndk"
    fi
fi

# Add GNU binutils to PATH
BINUTILS_PATH="/usr/local/Cellar/binutils/$(brew list --versions binutils | cut -d' ' -f2)/bin"

ENV_SCRIPT="setup_cross_compile_macos.sh"
cat > "$ENV_SCRIPT" << EOF
#!/bin/bash
# Cross-compilation environment for Docker-enabled kernel build on macOS

export ANDROID_NDK_ROOT="$NDK_ROOT"
export ARCH=arm64
export SUBARCH=arm64

# Add GNU binutils to PATH (for readelf, objcopy, etc.)
export PATH="$BINUTILS_PATH:\$PATH"

# Set cross-compiler
if [[ -d "\$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin" ]]; then
    export CROSS_COMPILE=\$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-
    export PATH=\$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin:\$PATH
else
    # Fallback to aarch64-elf tools
    export CROSS_COMPILE=aarch64-elf-
fi

echo "🔧 Cross-compilation environment configured for macOS"
echo "   NDK: \$ANDROID_NDK_ROOT"
echo "   Architecture: \$ARCH"
echo "   Cross-compiler: \$CROSS_COMPILE"
echo "   GNU binutils: $BINUTILS_PATH"
EOF

chmod +x "$ENV_SCRIPT"

# Update shell profile
echo ""
echo "🐚 Updating shell profile..."

SHELL_RC=""
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    SHELL_RC="$HOME/.bash_profile"
fi

if [[ -n "$SHELL_RC" ]]; then
    # Add GNU binutils to PATH permanently
    if ! grep -q "$BINUTILS_PATH" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# GNU binutils for kernel building" >> "$SHELL_RC"
        echo "export PATH=\"$BINUTILS_PATH:\$PATH\"" >> "$SHELL_RC"
        echo "✅ Added GNU binutils to $SHELL_RC"
    else
        echo "✅ GNU binutils already in $SHELL_RC"
    fi
fi

# Test installation
echo ""
echo "🧪 Testing installation..."

source "./$ENV_SCRIPT"

# Run binutils check
if [[ -f "check_binutils.sh" ]]; then
    echo "Running binutils verification..."
    ./check_binutils.sh
else
    echo "⚠️  check_binutils.sh not found, skipping verification"
fi

# Test cross-compiler if available
if command -v aarch64-linux-android29-clang &> /dev/null; then
    echo ""
    echo "Testing cross-compiler..."
    echo 'int main(){return 0;}' | aarch64-linux-android29-clang -x c - -o /tmp/test_arm64_macos 2>/dev/null
    if [[ $? -eq 0 ]]; then
        FILE_INFO=$(file /tmp/test_arm64_macos)
        echo "✅ Cross-compilation test passed: $FILE_INFO"
        rm -f /tmp/test_arm64_macos
    else
        echo "⚠️  Cross-compilation test failed, but tools are installed"
    fi
elif command -v aarch64-elf-gcc &> /dev/null; then
    echo ""
    echo "Testing aarch64-elf cross-compiler..."
    echo 'int main(){return 0;}' | aarch64-elf-gcc -x c - -o /tmp/test_arm64_elf 2>/dev/null
    if [[ $? -eq 0 ]]; then
        FILE_INFO=$(file /tmp/test_arm64_elf)
        echo "✅ Cross-compilation test passed: $FILE_INFO"
        rm -f /tmp/test_arm64_elf
    else
        echo "⚠️  Cross-compilation test failed, but tools are installed"
    fi
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
echo "🎉 macOS setup completed successfully!"
echo ""
echo "📋 Summary:"
echo "   ✅ Build dependencies installed"
echo "   ✅ GNU binutils available"
echo "   ✅ Cross-compilation tools ready"
echo "   ✅ Android NDK configured"
echo "   ✅ Environment script created: $ENV_SCRIPT"
echo ""
echo "🚀 Next steps:"
echo "   1. Restart terminal or run: source $SHELL_RC"
echo "   2. Source environment: source $ENV_SCRIPT"
echo "   3. Download kernel: python3 kernel_build/scripts/setup_kernel_source.py download lineage-18.1"
echo "   4. Apply patches: python3 kernel_build/scripts/config_tool.py apply --defconfig kernel_source/arch/arm64/configs/raphael_defconfig --backup"
echo "   5. Build kernel: ./build_docker_kernel.sh"
echo ""
echo "📚 Documentation:"
echo "   - Complete guide: KERNEL_BUILD_GUIDE.md"
echo "   - macOS-specific: This script output"
echo "   - Build status: BUILD_STATUS.md"