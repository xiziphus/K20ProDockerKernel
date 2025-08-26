#!/usr/bin/env python3
"""
Cpuset Modification Tool for Docker-enabled kernel build.

Command-line interface for modifying kernel/cgroup/cpuset.c to restore
Docker-compatible cpuset prefixes.
"""

import argparse
import logging
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kernel_build.patch.cpuset_handler import CpusetHandler, CpusetModificationStatus


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def modify_command(args):
    """Modify cpuset.c command handler."""
    handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    print(f"Modifying cpuset.c in kernel source: {args.kernel_source}")
    
    if args.force:
        print("FORCE MODE - Will modify even if already modified")
    
    result = handler.modify_cpuset_file(force=args.force)
    
    print(f"Status: {result.status.value}")
    print(f"Message: {result.message}")
    
    if result.backup_file:
        print(f"Backup created: {result.backup_file}")
    
    if result.added_entries:
        print(f"Added entries: {', '.join(result.added_entries)}")
    
    if result.modified_lines > 0:
        print(f"Lines added: {result.modified_lines}")
    
    if result.status != CpusetModificationStatus.SUCCESS:
        sys.exit(1)


def restore_command(args):
    """Restore cpuset.c command handler."""
    handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    print(f"Restoring cpuset.c in kernel source: {args.kernel_source}")
    
    result = handler.restore_original()
    
    print(f"Status: {result.status.value}")
    print(f"Message: {result.message}")
    
    if result.backup_file:
        print(f"Restored from: {result.backup_file}")
    
    if result.status != CpusetModificationStatus.SUCCESS:
        sys.exit(1)


def verify_command(args):
    """Verify cpuset.c compatibility command handler."""
    handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    print(f"Verifying cpuset.c compatibility in: {args.kernel_source}")
    
    is_compatible, missing_entries = handler.verify_cpuset_compatibility()
    
    if is_compatible:
        print("✓ Cpuset.c is Docker-compatible")
        print("All required cpuset entries are present")
    else:
        print("✗ Cpuset.c is NOT Docker-compatible")
        print(f"Missing entries: {', '.join(missing_entries)}")
        sys.exit(1)


def status_command(args):
    """Show cpuset.c status command handler."""
    handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    print(f"Cpuset.c status for kernel source: {args.kernel_source}")
    print("=" * 50)
    
    status = handler.get_modification_status()
    
    print(f"File exists: {'Yes' if status['file_exists'] else 'No'}")
    
    if status['file_exists']:
        print(f"File size: {status['file_size']} bytes")
        
        if status['last_modified']:
            from datetime import datetime
            mod_time = datetime.fromtimestamp(status['last_modified'])
            print(f"Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"Is modified: {'Yes' if status['is_modified'] else 'No'}")
        print(f"Is Docker-compatible: {'Yes' if status['is_compatible'] else 'No'}")
        
        if status['missing_entries']:
            print(f"Missing entries: {', '.join(status['missing_entries'])}")
        
        if status['backup_files']:
            print(f"Available backups: {len(status['backup_files'])}")
            if args.verbose:
                for backup in status['backup_files']:
                    print(f"  - {backup}")
    
    if args.json:
        print("\nJSON Status:")
        print(json.dumps(status, indent=2, default=str))


def list_backups_command(args):
    """List available backups command handler."""
    handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    backup_files = list(handler.backup_dir.glob("cpuset.c_*.backup"))
    
    if backup_files:
        print(f"Available backups in {handler.backup_dir}:")
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            stat = backup_file.stat()
            from datetime import datetime
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size
            
            print(f"  {backup_file.name}")
            print(f"    Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Size: {size} bytes")
            print()
    else:
        print("No backup files found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cpuset Modification Tool for Docker-enabled kernel build"
    )
    
    parser.add_argument(
        '--kernel-source',
        default='.',
        help='Path to kernel source directory (default: current directory)'
    )
    
    parser.add_argument(
        '--backup-dir',
        default='kernel_build/backups/cpuset',
        help='Directory for backups (default: kernel_build/backups/cpuset)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Modify command
    modify_parser = subparsers.add_parser('modify', help='Modify cpuset.c for Docker compatibility')
    modify_parser.add_argument(
        '--force',
        action='store_true',
        help='Force modification even if already modified'
    )
    modify_parser.set_defaults(func=modify_command)
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore cpuset.c from backup')
    restore_parser.set_defaults(func=restore_command)
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify Docker compatibility')
    verify_parser.set_defaults(func=verify_command)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show cpuset.c status')
    status_parser.add_argument(
        '--json',
        action='store_true',
        help='Output status in JSON format'
    )
    status_parser.set_defaults(func=status_command)
    
    # List backups command
    backups_parser = subparsers.add_parser('backups', help='List available backups')
    backups_parser.set_defaults(func=list_backups_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(args.verbose)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()