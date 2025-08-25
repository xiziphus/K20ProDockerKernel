#!/bin/bash
# Fix Python Command for Kernel Build
# This script resolves the "python: Command not found" issue

echo "🐍 Fixing Python command for kernel build..."

# Method 1: Create user bin directory with python symlink
mkdir -p ~/bin
ln -sf $(which python3) ~/bin/python

# Add to PATH
export PATH=~/bin:$PATH

# Method 2: Set PYTHON environment variable
export PYTHON=$(which python3)

# Method 3: Update shell profile for persistence
if [[ "$SHELL" == *"zsh"* ]]; then
    PROFILE="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    PROFILE="$HOME/.bashrc"
else
    PROFILE="$HOME/.profile"
fi

# Add to profile if not already there
if ! grep -q "export PATH=~/bin:\$PATH" "$PROFILE" 2>/dev/null; then
    echo "" >> "$PROFILE"
    echo "# Python fix for kernel build" >> "$PROFILE"
    echo "export PATH=~/bin:\$PATH" >> "$PROFILE"
    echo "export PYTHON=\$(which python3)" >> "$PROFILE"
    echo "✅ Added to $PROFILE"
fi

# Test python command
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    echo "✅ Python command working: $PYTHON_VERSION"
else
    echo "❌ Python command still not working"
    echo "Manual fix: ln -sf $(which python3) /usr/local/bin/python"
fi

echo ""
echo "🔧 Environment configured:"
echo "   PATH: $PATH"
echo "   PYTHON: $PYTHON"
echo ""
echo "🚀 Now you can run: ./build_docker_kernel.sh"