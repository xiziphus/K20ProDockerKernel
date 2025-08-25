#!/bin/bash
# Docker-Enabled Kernel Deployment Script
# Quick deployment wrapper for the Python deployment tool

set -e

echo "⚡ Docker-Enabled Kernel Deployment Tool"
echo "========================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Check if fastboot is available
if ! command -v fastboot &> /dev/null; then
    echo "❌ fastboot is required but not found"
    echo "Install Android SDK Platform Tools"
    exit 1
fi

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  deploy <kernel_image>  - Deploy kernel to device"
    echo "  check                  - Check device and tools"
    echo "  backup                 - Backup current kernel"
    echo "  rollback <backup>      - Rollback to previous kernel"
    echo "  validate               - Validate current deployment"
    echo ""
    echo "Examples:"
    echo "  $0 deploy boot.img"
    echo "  $0 check"
    echo "  $0 backup"
    echo ""
    exit 1
fi

# Run the Python deployment script
python3 kernel_build/scripts/deploy_kernel.py "$@"