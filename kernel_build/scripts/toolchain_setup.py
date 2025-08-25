#!/usr/bin/env python3
"""
Toolchain Setup Script for Docker-enabled K20 Pro Kernel

Command-line interface for toolchain detection, configuration, and validation.
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build.toolchain_manager import ToolchainManager, ToolchainConfig

def print_banner():
    """Print setup banner"""
    print("=" * 60)
    print("Docker-enabled K20 Pro Kernel - Toolchain Setup")
    print("=" * 60)
    print()

def setup_toolchain(args):
    """Setup toolchain based on arguments"""
    manager = ToolchainManager()
    
    print("Starting toolchain setup...")
    print(f"Target architecture: {args.arch}")
    
    if args.ndk_path:
        print(f"Using specified NDK path: {args.ndk_path}")
        # Validate specified NDK path
        if not manager._validate_ndk_path(Path(args.ndk_path)):
            print(f"ERROR: Invalid NDK path: {args.ndk_path}")
            return False
        
        # Find toolchain for specified NDK
        toolchain = manager.find_toolchain_for_arch(args.ndk_path, args.arch)
    else:
        # Auto-detect and setup
        toolchain = manager.auto_setup_toolchain(args.arch)
    
    if not toolchain:
        print("ERROR: Toolchain setup failed")
        return False
    
    # Validate toolchain
    if not manager.validate_toolchain(toolchain):
        print("ERROR: Toolchain validation failed")
        return False
    
    # Save configuration
    config_file = manager.save_toolchain_config(toolchain)
    
    print("\nToolchain setup completed successfully!")
    print(f"Configuration saved to: {config_file}")
    
    # Show toolchain info
    show_toolchain_info(toolchain, manager)
    
    return True

def validate_toolchain(args):
    """Validate existing toolchain"""
    manager = ToolchainManager()
    
    if not args.config_file:
        # Look for default config file
        config_dir = Path.cwd() / "kernel_build" / "build" / "config"
        args.config_file = str(config_dir / "toolchain_config.json")
    
    if not Path(args.config_file).exists():
        print(f"ERROR: Configuration file not found: {args.config_file}")
        return False
    
    print(f"Validating toolchain from: {args.config_file}")
    
    toolchain = manager.load_toolchain_config(args.config_file)
    if not toolchain:
        print("ERROR: Failed to load toolchain configuration")
        return False
    
    if manager.validate_toolchain(toolchain):
        print("✓ Toolchain validation successful")
        show_toolchain_info(toolchain, manager)
        return True
    else:
        print("✗ Toolchain validation failed")
        return False

def show_info(args):
    """Show toolchain information"""
    manager = ToolchainManager()
    
    if args.config_file:
        # Show info from config file
        if not Path(args.config_file).exists():
            print(f"ERROR: Configuration file not found: {args.config_file}")
            return False
        
        toolchain = manager.load_toolchain_config(args.config_file)
        if not toolchain:
            print("ERROR: Failed to load toolchain configuration")
            return False
        
        show_toolchain_info(toolchain, manager)
    else:
        # Show detected NDK info
        ndk_path = manager.detect_android_ndk()
        if ndk_path:
            print(f"Detected Android NDK: {ndk_path}")
            version = manager.get_ndk_version(ndk_path)
            if version:
                print(f"NDK Version: {version}")
            
            # Show available toolchains
            for arch in ["aarch64", "arm"]:
                toolchain = manager.find_toolchain_for_arch(ndk_path, arch)
                if toolchain:
                    print(f"\nAvailable toolchain for {arch}:")
                    print(f"  Name: {toolchain.name}")
                    print(f"  Path: {toolchain.path}")
                    print(f"  Prefix: {toolchain.prefix}")
        else:
            print("No Android NDK detected")
    
    return True

def show_toolchain_info(toolchain: ToolchainConfig, manager: ToolchainManager):
    """Display detailed toolchain information"""
    info = manager.get_toolchain_info(toolchain)
    
    print("\nToolchain Information:")
    print("-" * 40)
    print(f"Name: {info['name']}")
    print(f"Path: {info['path']}")
    print(f"Prefix: {info['prefix']}")
    print(f"Version: {info['version']}")
    print(f"Architecture: {info['architecture']}")
    print(f"Validated: {'✓' if info['validated'] else '✗'}")
    
    print("\nAvailable Tools:")
    for tool, path in info['tools'].items():
        status = "✓" if path != "NOT_FOUND" else "✗"
        print(f"  {tool}: {status} {path if path != 'NOT_FOUND' else ''}")
    
    # Show environment variables
    env_vars = manager.setup_toolchain_environment(toolchain)
    print("\nEnvironment Variables:")
    for key, value in env_vars.items():
        if key != "PATH":  # PATH is too long to display nicely
            print(f"  {key}={value}")

def detect_ndk(args):
    """Detect Android NDK installation"""
    manager = ToolchainManager()
    
    print("Detecting Android NDK installation...")
    ndk_path = manager.detect_android_ndk()
    
    if ndk_path:
        print(f"✓ Android NDK found: {ndk_path}")
        version = manager.get_ndk_version(ndk_path)
        if version:
            print(f"  Version: {version}")
        return True
    else:
        print("✗ Android NDK not found")
        print("\nPlease install Android NDK and set one of these environment variables:")
        print("  - ANDROID_NDK_ROOT")
        print("  - NDK_ROOT")
        print("  - ANDROID_NDK_HOME")
        print("\nOr install NDK in one of these locations:")
        for path in manager.toolchain_paths:
            print(f"  - {path}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Toolchain Setup for Docker-enabled K20 Pro Kernel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-setup toolchain for aarch64
  python toolchain_setup.py setup

  # Setup with specific NDK path
  python toolchain_setup.py setup --ndk-path /opt/android-ndk

  # Validate existing toolchain
  python toolchain_setup.py validate

  # Show toolchain information
  python toolchain_setup.py info

  # Detect NDK installation
  python toolchain_setup.py detect
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup toolchain')
    setup_parser.add_argument('--arch', default='aarch64', 
                             choices=['aarch64', 'arm'],
                             help='Target architecture (default: aarch64)')
    setup_parser.add_argument('--ndk-path', help='Android NDK path')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate toolchain')
    validate_parser.add_argument('--config-file', help='Toolchain configuration file')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show toolchain information')
    info_parser.add_argument('--config-file', help='Toolchain configuration file')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect Android NDK')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print_banner()
    
    success = False
    
    if args.command == 'setup':
        success = setup_toolchain(args)
    elif args.command == 'validate':
        success = validate_toolchain(args)
    elif args.command == 'info':
        success = show_info(args)
    elif args.command == 'detect':
        success = detect_ndk(args)
    
    if not success:
        sys.exit(1)
    
    print("\nOperation completed successfully!")

if __name__ == "__main__":
    main()