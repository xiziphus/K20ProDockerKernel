#!/usr/bin/env python3
"""
Patch Application Tool for Docker-enabled kernel build.

Command-line interface for applying, verifying, and rolling back kernel patches.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kernel_build.patch.patch_engine import PatchEngine, PatchStatus
from kernel_build.patch.patch_verifier import PatchVerifier, VerificationStatus
from kernel_build.patch.patch_rollback import PatchRollback, RollbackStatus


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def apply_patches_command(args):
    """Apply patches command handler."""
    engine = PatchEngine(args.kernel_source, args.backup_dir)
    
    print(f"Applying patches to kernel source: {args.kernel_source}")
    print(f"Patch files: {', '.join(args.patches)}")
    
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
    
    results = engine.apply_patches(args.patches, dry_run=args.dry_run)
    
    success_count = 0
    for result in results:
        print(f"\nPatch: {result.patch_file}")
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        
        if result.conflicts:
            print(f"Conflicts: {', '.join(result.conflicts)}")
        
        if result.applied_files:
            print(f"Applied files: {', '.join(result.applied_files)}")
        
        if result.status == PatchStatus.SUCCESS:
            success_count += 1
    
    print(f"\nSummary: {success_count}/{len(results)} patches applied successfully")
    
    if success_count < len(results):
        sys.exit(1)


def verify_patches_command(args):
    """Verify patches command handler."""
    verifier = PatchVerifier(args.kernel_source, args.verification_dir)
    
    print(f"Verifying patches in kernel source: {args.kernel_source}")
    
    success_count = 0
    for patch_file in args.patches:
        print(f"\nVerifying patch: {patch_file}")
        
        # First verify patch integrity
        if not verifier.verify_patch_integrity(patch_file):
            print(f"FAILED: Patch integrity check failed")
            continue
        
        # Then verify application
        result = verifier.verify_patch_application(patch_file)
        
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        
        if result.verified_files:
            print(f"Verified files: {', '.join(result.verified_files)}")
        
        if result.failed_files:
            print(f"Failed files: {', '.join(result.failed_files)}")
        
        if result.missing_files:
            print(f"Missing files: {', '.join(result.missing_files)}")
        
        if result.status == VerificationStatus.VERIFIED:
            success_count += 1
    
    print(f"\nSummary: {success_count}/{len(args.patches)} patches verified successfully")
    
    if success_count < len(args.patches):
        sys.exit(1)


def rollback_patches_command(args):
    """Rollback patches command handler."""
    rollback = PatchRollback(args.kernel_source, args.backup_dir)
    
    if args.all:
        print("Rolling back all applied patches...")
        results = rollback.rollback_all_patches()
    else:
        print(f"Rolling back patches: {', '.join(args.patches)}")
        results = []
        for patch_file in args.patches:
            result = rollback.rollback_patch(patch_file, args.method)
            results.append(result)
    
    success_count = 0
    for result in results:
        print(f"\nPatch: {result.patch_file}")
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        
        if result.restored_files:
            print(f"Restored files: {', '.join(result.restored_files)}")
        
        if result.failed_files:
            print(f"Failed files: {', '.join(result.failed_files)}")
        
        if result.status == RollbackStatus.SUCCESS:
            success_count += 1
    
    print(f"\nSummary: {success_count}/{len(results)} patches rolled back successfully")
    
    if success_count < len(results):
        sys.exit(1)


def list_applied_command(args):
    """List applied patches command handler."""
    engine = PatchEngine(args.kernel_source, args.backup_dir)
    applied_patches = engine.get_applied_patches()
    
    if applied_patches:
        print("Applied patches:")
        for patch in applied_patches:
            print(f"  - {patch}")
    else:
        print("No patches currently applied")


def snapshot_command(args):
    """Snapshot management command handler."""
    rollback = PatchRollback(args.kernel_source, args.backup_dir)
    
    if args.snapshot_action == 'create':
        success = rollback.create_snapshot(args.name)
        if success:
            print(f"Snapshot created: {args.name or 'auto-generated'}")
        else:
            print("Failed to create snapshot")
            sys.exit(1)
    
    elif args.snapshot_action == 'restore':
        if not args.name:
            print("Snapshot name required for restore")
            sys.exit(1)
        
        result = rollback.restore_snapshot(args.name)
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        
        if result.status != RollbackStatus.SUCCESS:
            sys.exit(1)
    
    elif args.snapshot_action == 'list':
        snapshots = rollback.list_snapshots()
        if snapshots:
            print("Available snapshots:")
            for snapshot in snapshots:
                print(f"  - {snapshot}")
        else:
            print("No snapshots available")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Patch Application Tool for Docker-enabled kernel build"
    )
    
    parser.add_argument(
        '--kernel-source',
        default='.',
        help='Path to kernel source directory (default: current directory)'
    )
    
    parser.add_argument(
        '--backup-dir',
        default='kernel_build/backups/patches',
        help='Directory for backups (default: kernel_build/backups/patches)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Apply patches command
    apply_parser = subparsers.add_parser('apply', help='Apply patches')
    apply_parser.add_argument('patches', nargs='+', help='Patch files to apply')
    apply_parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    apply_parser.set_defaults(func=apply_patches_command)
    
    # Verify patches command
    verify_parser = subparsers.add_parser('verify', help='Verify patches')
    verify_parser.add_argument('patches', nargs='+', help='Patch files to verify')
    verify_parser.add_argument(
        '--verification-dir',
        default='kernel_build/verification',
        help='Directory for verification data'
    )
    verify_parser.set_defaults(func=verify_patches_command)
    
    # Rollback patches command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback patches')
    rollback_parser.add_argument('patches', nargs='*', help='Patch files to rollback')
    rollback_parser.add_argument('--all', action='store_true', help='Rollback all patches')
    rollback_parser.add_argument(
        '--method',
        choices=['auto', 'reverse', 'backup'],
        default='auto',
        help='Rollback method'
    )
    rollback_parser.set_defaults(func=rollback_patches_command)
    
    # List applied patches command
    list_parser = subparsers.add_parser('list', help='List applied patches')
    list_parser.set_defaults(func=list_applied_command)
    
    # Snapshot management command
    snapshot_parser = subparsers.add_parser('snapshot', help='Manage snapshots')
    snapshot_parser.add_argument(
        'snapshot_action',
        choices=['create', 'restore', 'list'],
        help='Snapshot action'
    )
    snapshot_parser.add_argument('--name', help='Snapshot name')
    snapshot_parser.set_defaults(func=snapshot_command)
    
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