#!/bin/bash
# Binutils Installation Verification Script
# Checks if binutils and cross-compilation tools are properly installed

set -e

echo "🔧 Binutils Installation Check"
echo "=============================="

# Check OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    echo "✅ Detected macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
    echo "✅ Detected Linux"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

echo ""
echo "📦 Checking native binutils..."

# Check native binutils
MISSING_TOOLS=()

for tool in objdump readelf nm strip objcopy; do
    FOUND=false
    
    # Check for the tool directly
    if command -v $tool &> /dev/null; then
        if [[ "$tool" == "strip" ]]; then
            # macOS strip doesn't support --version, just check if it exists
            echo "✅ $tool: Available (macOS version)"
        else
            VERSION=$($tool --version 2>/dev/null | head -n1 || echo "Available")
            echo "✅ $tool: $VERSION"
        fi
        FOUND=true
    # On macOS, check for GNU versions with 'g' prefix
    elif [[ "$OS" == "macOS" ]] && command -v g$tool &> /dev/null; then
        VERSION=$(g$tool --version | head -n1)
        echo "✅ $tool (GNU): $VERSION"
        FOUND=true
    fi
    
    if [[ "$FOUND" == false ]]; then
        echo "❌ $tool: Not found"
        MISSING_TOOLS+=($tool)
    fi
done

echo ""
echo "🎯 Checking cross-compilation binutils..."

# Check cross-compilation tools
CROSS_TOOLS_FOUND=false

# Check for different cross-compilation prefixes
CROSS_PREFIXES=("aarch64-linux-gnu" "aarch64-elf" "aarch64-linux-android29")

for prefix in "${CROSS_PREFIXES[@]}"; do
    if command -v ${prefix}-objdump &> /dev/null; then
        VERSION=$(${prefix}-objdump --version | head -n1)
        echo "✅ ${prefix}-objdump: $VERSION"
        CROSS_TOOLS_FOUND=true
        
        # Check other tools with this prefix
        for tool in readelf nm strip objcopy; do
            if command -v ${prefix}-${tool} &> /dev/null; then
                echo "✅ ${prefix}-${tool}: Available"
            else
                echo "⚠️  ${prefix}-${tool}: Not found"
            fi
        done
        break
    fi
done

if [[ "$CROSS_TOOLS_FOUND" == false ]]; then
    echo "❌ No cross-compilation binutils found"
    echo "   Checked prefixes: ${CROSS_PREFIXES[*]}"
fi

echo ""
echo "🧪 Testing ELF header availability..."

# Check for ELF headers
ELF_HEADERS_FOUND=false

if [[ "$OS" == "macOS" ]]; then
    SEARCH_PATHS=("/opt/homebrew/include" "/usr/local/include" "/usr/local/Cellar/binutils/*/include" "/usr/local/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK/toolchains/llvm/prebuilt/darwin-x86_64/sysroot/usr/include")
else
    SEARCH_PATHS=("/usr/include" "/usr/local/include")
fi

for path_pattern in "${SEARCH_PATHS[@]}"; do
    # Expand wildcards
    for path in $path_pattern; do
        if [[ -f "$path/elf.h" ]]; then
            echo "✅ ELF headers found: $path/elf.h"
            ELF_HEADERS_FOUND=true
            break 2
        fi
    done
done

if [[ "$ELF_HEADERS_FOUND" == false ]]; then
    echo "❌ ELF headers not found in standard locations"
    echo "   Searched: ${SEARCH_PATHS[*]}"
fi

echo ""
echo "📋 Summary"
echo "=========="

if [[ ${#MISSING_TOOLS[@]} -eq 0 ]] && [[ "$CROSS_TOOLS_FOUND" == true ]] && [[ "$ELF_HEADERS_FOUND" == true ]]; then
    echo "🎉 All binutils components are properly installed!"
    echo ""
    echo "✅ Native binutils: Complete"
    echo "✅ Cross-compilation tools: Available"
    echo "✅ ELF headers: Found"
    echo ""
    echo "🚀 Ready for kernel building!"
    exit 0
else
    echo "⚠️  Some components are missing or incomplete"
    echo ""
    
    if [[ ${#MISSING_TOOLS[@]} -gt 0 ]]; then
        echo "❌ Missing native tools: ${MISSING_TOOLS[*]}"
    fi
    
    if [[ "$CROSS_TOOLS_FOUND" == false ]]; then
        echo "❌ Missing cross-compilation tools"
    fi
    
    if [[ "$ELF_HEADERS_FOUND" == false ]]; then
        echo "❌ Missing ELF headers"
    fi
    
    echo ""
    echo "🔧 Installation suggestions:"
    
    if [[ "$OS" == "macOS" ]]; then
        echo "   brew install binutils aarch64-elf-binutils"
        echo "   brew install android-ndk"
    else
        echo "   sudo apt-get install binutils binutils-dev binutils-aarch64-linux-gnu"
        echo "   # or"
        echo "   sudo dnf install binutils binutils-devel binutils-aarch64-linux-gnu"
    fi
    
    exit 1
fi