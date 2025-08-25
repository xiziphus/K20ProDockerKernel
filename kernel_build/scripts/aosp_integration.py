#!/usr/bin/env python3
"""
AOSP Integration Script for Docker-enabled K20 Pro Kernel

Command-line interface for AOSP integration, BoardConfig.mk modification,
and Android build system compatibility checks.
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build.aosp_integration import AOSPIntegrationHandler, AOSPConfig

def print_banner():
    """Print integration banner"""
    print("=" * 70)
    print("Docker-enabled K20 Pro Kernel - AOSP Integration")
    print("=" * 70)
    print()

def detect_environment(args):
    """Detect AOSP environment"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    print("Detecting AOSP environment...")
    aosp_root = handler.detect_aosp_environment(args.aosp_root)
    
    if aosp_root:
        print(f"✅ AOSP environment found: {aosp_root}")
        
        # Find device tree
        device_tree = handler.find_device_tree(aosp_root, args.target_device)
        if device_tree:
            print(f"✅ Device tree found: {device_tree}")
        else:
            print(f"❌ Device tree not found for: {args.target_device}")
        
        return True
    else:
        print("❌ AOSP environment not found")
        print("\nPlease ensure AOSP is properly set up and set one of:")
        print("  - ANDROID_BUILD_TOP environment variable")
        print("  - TOP environment variable")
        print("  - Provide --aosp-root argument")
        return False

def validate_compatibility(args):
    """Validate Android compatibility"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    # Create AOSP configuration
    aosp_config = create_aosp_config(args, handler)
    if not aosp_config:
        return False
    
    print("Validating Android build system compatibility...")
    print("-" * 50)
    
    valid, issues = handler.validate_android_compatibility(aosp_config)
    
    if valid:
        print("✅ All compatibility checks passed!")
        print("\nConfiguration Summary:")
        print(f"  AOSP Root: {aosp_config.aosp_root}")
        print(f"  Device Tree: {aosp_config.device_tree_path}")
        print(f"  Kernel Source: {aosp_config.kernel_source_path}")
        print(f"  Target Device: {aosp_config.target_device}")
        print(f"  Android Version: {aosp_config.android_version}")
        return True
    else:
        print("❌ Compatibility validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        return False

def modify_board_config(args):
    """Modify BoardConfig.mk"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    # Find device tree if not provided
    if not args.device_tree:
        aosp_root = handler.detect_aosp_environment(args.aosp_root)
        if not aosp_root:
            print("❌ AOSP environment not found")
            return False
        
        args.device_tree = handler.find_device_tree(aosp_root, args.target_device)
        if not args.device_tree:
            print(f"❌ Device tree not found for: {args.target_device}")
            return False
    
    print(f"Modifying BoardConfig.mk in: {args.device_tree}")
    
    # Custom modifications if provided
    modifications = None
    if args.board_config_vars:
        try:
            modifications = json.loads(args.board_config_vars)
        except json.JSONDecodeError:
            print("❌ Invalid JSON format for board config variables")
            return False
    
    if handler.modify_board_config(args.device_tree, modifications):
        print("✅ BoardConfig.mk modified successfully")
        
        # Show what was modified
        board_config_path = Path(args.device_tree) / "BoardConfig.mk"
        if board_config_path.exists():
            print(f"\nModified file: {board_config_path}")
            print("Backup created with .backup extension")
        
        return True
    else:
        print("❌ Failed to modify BoardConfig.mk")
        return False

def apply_patches(args):
    """Apply AOSP patches"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    if not args.kernel_source:
        print("❌ Kernel source path required")
        return False
    
    print(f"Applying AOSP patches to: {args.kernel_source}")
    
    if handler.apply_aosp_patches(args.kernel_source):
        print("✅ AOSP patches applied successfully")
        return True
    else:
        print("❌ Failed to apply AOSP patches")
        return False

def setup_selinux(args):
    """Setup SELinux policies"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    # Find device tree if not provided
    if not args.device_tree:
        aosp_root = handler.detect_aosp_environment(args.aosp_root)
        if not aosp_root:
            print("❌ AOSP environment not found")
            return False
        
        args.device_tree = handler.find_device_tree(aosp_root, args.target_device)
        if not args.device_tree:
            print(f"❌ Device tree not found for: {args.target_device}")
            return False
    
    print(f"Setting up SELinux policies in: {args.device_tree}")
    
    if handler.setup_selinux_policies(args.device_tree):
        print("✅ SELinux policies setup successfully")
        
        sepolicy_path = Path(args.device_tree) / "sepolicy" / "docker.te"
        print(f"Policy file created: {sepolicy_path}")
        
        return True
    else:
        print("❌ Failed to setup SELinux policies")
        return False

def generate_build_script(args):
    """Generate AOSP build script"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    # Create AOSP configuration
    aosp_config = create_aosp_config(args, handler)
    if not aosp_config:
        return False
    
    output_file = args.output or str(Path(aosp_config.aosp_root) / "build_docker_kernel.sh")
    
    print(f"Generating AOSP build script: {output_file}")
    
    if handler.generate_build_script(aosp_config, output_file):
        print("✅ Build script generated successfully")
        print(f"\nTo build the Docker-enabled kernel:")
        print(f"  cd {aosp_config.aosp_root}")
        print(f"  ./{Path(output_file).name}")
        return True
    else:
        print("❌ Failed to generate build script")
        return False

def full_integration(args):
    """Perform full AOSP integration"""
    print_banner()
    
    handler = AOSPIntegrationHandler()
    
    # Create AOSP configuration
    aosp_config = create_aosp_config(args, handler)
    if not aosp_config:
        return False
    
    print("Starting full AOSP integration...")
    print("=" * 50)
    
    # Show configuration
    print("Configuration:")
    print(f"  AOSP Root: {aosp_config.aosp_root}")
    print(f"  Device Tree: {aosp_config.device_tree_path}")
    print(f"  Kernel Source: {aosp_config.kernel_source_path}")
    print(f"  Target Device: {aosp_config.target_device}")
    print(f"  Android Version: {aosp_config.android_version}")
    print()
    
    # Confirm integration
    if not args.yes:
        response = input("Proceed with AOSP integration? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Integration cancelled.")
            return False
    
    if handler.integrate_with_aosp(aosp_config):
        print("\n✅ AOSP integration completed successfully!")
        
        print("\nNext steps:")
        print("1. Review modified BoardConfig.mk")
        print("2. Check SELinux policies in sepolicy/docker.te")
        print("3. Run the generated build script")
        print("4. Test the built kernel on device")
        
        return True
    else:
        print("\n❌ AOSP integration failed!")
        return False

def create_aosp_config(args, handler: AOSPIntegrationHandler) -> AOSPConfig:
    """Create AOSP configuration from arguments"""
    # Detect AOSP root
    aosp_root = handler.detect_aosp_environment(args.aosp_root)
    if not aosp_root:
        print("❌ AOSP environment not found")
        return None
    
    # Find device tree if not provided
    device_tree = args.device_tree
    if not device_tree:
        device_tree = handler.find_device_tree(aosp_root, args.target_device)
        if not device_tree:
            print(f"❌ Device tree not found for: {args.target_device}")
            return None
    
    # Set default paths if not provided
    kernel_source = args.kernel_source or str(Path.cwd() / "kernel_source")
    kernel_output = args.kernel_output or str(Path.cwd() / "kernel_build" / "output" / "aosp")
    
    return AOSPConfig(
        aosp_root=aosp_root,
        device_tree_path=device_tree,
        kernel_source_path=kernel_source,
        kernel_output_path=kernel_output,
        target_device=args.target_device,
        android_version=args.android_version,
        build_variant=args.build_variant
    )

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="AOSP Integration for Docker-enabled K20 Pro Kernel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect AOSP environment
  python aosp_integration.py detect

  # Validate compatibility
  python aosp_integration.py validate --aosp-root /path/to/aosp

  # Modify BoardConfig.mk
  python aosp_integration.py board-config --device-tree /path/to/device/tree

  # Apply AOSP patches
  python aosp_integration.py patches --kernel-source /path/to/kernel

  # Full integration
  python aosp_integration.py integrate --aosp-root /path/to/aosp --kernel-source /path/to/kernel
        """
    )
    
    # Common arguments
    parser.add_argument('--aosp-root', help='AOSP root directory')
    parser.add_argument('--device-tree', help='Device tree path')
    parser.add_argument('--kernel-source', help='Kernel source path')
    parser.add_argument('--kernel-output', help='Kernel output path')
    parser.add_argument('--target-device', default='raphael', help='Target device (default: raphael)')
    parser.add_argument('--android-version', default='11', help='Android version (default: 11)')
    parser.add_argument('--build-variant', default='userdebug', help='Build variant (default: userdebug)')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompts')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect AOSP environment')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate Android compatibility')
    
    # Board config command
    board_parser = subparsers.add_parser('board-config', help='Modify BoardConfig.mk')
    board_parser.add_argument('--board-config-vars', help='Custom board config variables (JSON format)')
    
    # Patches command
    patches_parser = subparsers.add_parser('patches', help='Apply AOSP patches')
    
    # SELinux command
    selinux_parser = subparsers.add_parser('selinux', help='Setup SELinux policies')
    
    # Build script command
    script_parser = subparsers.add_parser('build-script', help='Generate AOSP build script')
    script_parser.add_argument('--output', help='Output script file path')
    
    # Full integration command
    integrate_parser = subparsers.add_parser('integrate', help='Perform full AOSP integration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    success = False
    
    try:
        if args.command == 'detect':
            success = detect_environment(args)
        elif args.command == 'validate':
            success = validate_compatibility(args)
        elif args.command == 'board-config':
            success = modify_board_config(args)
        elif args.command == 'patches':
            success = apply_patches(args)
        elif args.command == 'selinux':
            success = setup_selinux(args)
        elif args.command == 'build-script':
            success = generate_build_script(args)
        elif args.command == 'integrate':
            success = full_integration(args)
        
        if success:
            print("\n✅ Operation completed successfully!")
        else:
            print("\n❌ Operation failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()