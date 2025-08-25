#!/usr/bin/env python3
"""
Volume management tool for Docker containers.

This script provides command-line interface for managing Docker volumes
and bind mounts on Android devices.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.volume_manager import VolumeManager


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('volume_tool.log')
        ]
    )


def cmd_create_volume(args):
    """Create a new volume."""
    volume_manager = VolumeManager(args.base_path)
    
    options = {}
    if args.options:
        for option in args.options:
            if '=' in option:
                key, value = option.split('=', 1)
                options[key] = value
            else:
                options[option] = True
    
    if volume_manager.create_volume(args.name, args.driver, options):
        print(f"Volume '{args.name}' created successfully")
        return 0
    else:
        print(f"Failed to create volume '{args.name}'")
        return 1


def cmd_remove_volume(args):
    """Remove a volume."""
    volume_manager = VolumeManager(args.base_path)
    
    if volume_manager.remove_volume(args.name, args.force):
        print(f"Volume '{args.name}' removed successfully")
        return 0
    else:
        print(f"Failed to remove volume '{args.name}'")
        return 1


def cmd_list_volumes(args):
    """List all volumes."""
    volume_manager = VolumeManager(args.base_path)
    
    volumes = volume_manager.list_volumes()
    
    if not volumes:
        print("No volumes found")
        return 0
    
    print(f"{'NAME':<20} {'DRIVER':<10} {'MOUNTPOINT':<40}")
    print("-" * 70)
    
    for volume in volumes:
        name = volume.get('name', 'N/A')
        driver = volume.get('driver', 'N/A')
        mountpoint = volume.get('mountpoint', 'N/A')
        print(f"{name:<20} {driver:<10} {mountpoint:<40}")
    
    return 0


def cmd_create_bind_mount(args):
    """Create a bind mount."""
    volume_manager = VolumeManager(args.base_path)
    
    options = args.options if args.options else ["rw", "relatime"]
    
    if volume_manager.create_bind_mount(args.host_path, args.container_path, options):
        print(f"Bind mount created: {args.host_path} -> {args.container_path}")
        return 0
    else:
        print(f"Failed to create bind mount")
        return 1


def cmd_list_bind_mounts(args):
    """List all bind mounts."""
    volume_manager = VolumeManager(args.base_path)
    
    bind_mounts = volume_manager.list_bind_mounts()
    
    if not bind_mounts:
        print("No bind mounts found")
        return 0
    
    print(f"{'HOST PATH':<30} {'CONTAINER PATH':<30} {'OPTIONS':<20}")
    print("-" * 80)
    
    for bind_mount in bind_mounts:
        host_path = bind_mount.get('host_path', 'N/A')
        container_path = bind_mount.get('container_path', 'N/A')
        options = ','.join(bind_mount.get('options', []))
        print(f"{host_path:<30} {container_path:<30} {options:<20}")
    
    return 0


def cmd_cleanup(args):
    """Clean up volumes."""
    volume_manager = VolumeManager(args.base_path)
    
    if volume_manager.cleanup_volumes(args.remove_unused):
        print("Volume cleanup completed successfully")
        return 0
    else:
        print("Volume cleanup failed")
        return 1


def cmd_info(args):
    """Show volume information."""
    volume_manager = VolumeManager(args.base_path)
    
    info = volume_manager.get_volume_info()
    
    print("=== Volume Management Information ===")
    print(f"Volumes Path: {info['volumes_path']}")
    print(f"Bind Mounts Config: {info['bind_mounts_config']}")
    print(f"Total Volumes: {info['total_volumes']}")
    print(f"Total Bind Mounts: {info['total_bind_mounts']}")
    
    if 'storage_total' in info:
        total_gb = info['storage_total'] / (1024**3)
        used_gb = info['storage_used'] / (1024**3)
        avail_gb = info['storage_available'] / (1024**3)
        print(f"Storage Total: {total_gb:.2f} GB")
        print(f"Storage Used: {used_gb:.2f} GB")
        print(f"Storage Available: {avail_gb:.2f} GB")
    
    print("\nAllowed Host Paths for Bind Mounts:")
    for path in info['allowed_host_paths']:
        print(f"  - {path}")
    
    return 0


def cmd_validate(args):
    """Validate volume setup."""
    volume_manager = VolumeManager(args.base_path)
    
    results = volume_manager.validate_volume_setup()
    
    print("=== Volume Setup Validation ===")
    all_passed = True
    
    for component, status in results.items():
        if component == "error":
            continue
        status_str = "✓ PASS" if status else "✗ FAIL"
        print(f"{component:20}: {status_str}")
        if not status:
            all_passed = False
    
    if "error" in results:
        print(f"Error: {results['error']}")
        all_passed = False
    
    return 0 if all_passed else 1


def main():
    """Main function for volume tool."""
    parser = argparse.ArgumentParser(
        description="Volume management tool for Docker containers"
    )
    parser.add_argument(
        "--base-path", 
        default="/data/docker",
        help="Base path for Docker storage (default: /data/docker)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create volume command
    create_parser = subparsers.add_parser('create', help='Create a volume')
    create_parser.add_argument('name', help='Volume name')
    create_parser.add_argument('--driver', default='local', help='Volume driver')
    create_parser.add_argument('--options', nargs='*', help='Driver options')
    create_parser.set_defaults(func=cmd_create_volume)
    
    # Remove volume command
    remove_parser = subparsers.add_parser('remove', help='Remove a volume')
    remove_parser.add_argument('name', help='Volume name')
    remove_parser.add_argument('--force', action='store_true', help='Force removal')
    remove_parser.set_defaults(func=cmd_remove_volume)
    
    # List volumes command
    list_parser = subparsers.add_parser('list', help='List volumes')
    list_parser.set_defaults(func=cmd_list_volumes)
    
    # Create bind mount command
    bind_parser = subparsers.add_parser('bind', help='Create bind mount')
    bind_parser.add_argument('host_path', help='Host path')
    bind_parser.add_argument('container_path', help='Container path')
    bind_parser.add_argument('--options', nargs='*', help='Mount options')
    bind_parser.set_defaults(func=cmd_create_bind_mount)
    
    # List bind mounts command
    bind_list_parser = subparsers.add_parser('bind-list', help='List bind mounts')
    bind_list_parser.set_defaults(func=cmd_list_bind_mounts)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up volumes')
    cleanup_parser.add_argument('--remove-unused', action='store_true', 
                               help='Remove unused volumes')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show volume information')
    info_parser.set_defaults(func=cmd_info)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate volume setup')
    validate_parser.set_defaults(func=cmd_validate)
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())