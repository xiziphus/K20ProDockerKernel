#!/bin/bash
# Docker-Enabled Kernel Build System - Quick Setup Script
# This is a convenience wrapper for the Python installation script

set -e

echo "🚀 Docker-Enabled Kernel Build System Setup"
echo "============================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    echo "Please install Python 3.6 or newer and try again"
    exit 1
fi

# Run the Python installation script
echo "Running automated setup..."
python3 kernel_build/scripts/install_setup.py "$@"

echo ""
echo "Setup complete! Check the report above for any issues."
echo ""
echo "Next steps:"
echo "1. Review any missing dependencies"
echo "2. Set up Android NDK if needed"
echo "3. Run: python3 kernel_build/scripts/patch_integration.py apply-all"