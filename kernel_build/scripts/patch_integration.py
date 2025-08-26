#!/usr/bin/env python3
"""
Integrated Patch Application Tool for Docker-enabled kernel build.

This script provides a unified interface for applying kernel patches
and modifying cpuset.c for Docker compatibility.
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
from kernel_build.patch.cpuset_handler import CpusetHandler, CpusetModificationStatus


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def apply_all_patches_command(args):
    """Apply all patches and modify cpuset.c command handler."""
    print("Docker Kernel Patching - Complete Integration")
    print("=" * 50)
    
    # Initialize components
    engine = PatchEngine(args.kernel_source, args.backup_dir)
    verifier = PatchVerifier(args.kernel_source)
    cpuset_handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    success_count = 0
    total_operations = 0
    
    # Step 1: Apply kernel.diff and aosp.diff patches
    patch_files = []
    if args.kernel_patch:
        patch_files.append(args.kernel_patch)
    if args.aosp_patch:
        patch_files.append(args.aosp_patch)
    
    if patch_files:
        print(f"\n1. Applying patches: {', '.join(patch_files)}")
        print("-" * 30)
        
        # Verify patch integrity first
        for patch_file in patch_files:
            total_operations += 1
            if verifier.verify_patch_integrity(patch_file):
                print(f"✓ Patch integrity verified: {patch_file}")
                success_count += 1
            else:
                print(f"✗ Patch integrity failed: {patch_file}")
                if not args.continue_on_error:
                    sys.exit(1)
        
        # Apply patches
        if not args.dry_run:
            results = engine.apply_patches(patch_files, dry_run=False)
            
            for result in results:
                total_operations += 1
                print(f"\nPatch: {result.patch_file}")
                print(f"Status: {result.status.value}")
                print(f"Message: {result.message}")
                
                if result.conflicts:
                    print(f"Conflicts: {', '.join(result.conflicts)}")
                
                if result.applied_files:
                    print(f"Applied files: {', '.join(result.applied_files)}")
                
                if result.status == PatchStatus.SUCCESS:
                    success_count += 1
                elif not args.continue_on_error:
                    print("Stopping due to patch failure")
                    sys.exit(1)
        else:
            print("DRY RUN MODE - Patches not actually applied")
    
    # Step 2: Modify cpuset.c for Docker compatibility
    print(f"\n2. Modifying cpuset.c for Docker compatibility")
    print("-" * 30)
    
    total_operations += 1
    
    if not args.dry_run:
        cpuset_result = cpuset_handler.modify_cpuset_file(force=args.force)
        
        print(f"Status: {cpuset_result.status.value}")
        print(f"Message: {cpuset_result.message}")
        
        if cpuset_result.backup_file:
            print(f"Backup created: {cpuset_result.backup_file}")
        
        if cpuset_result.added_entries:
            print(f"Added entries: {', '.join(cpuset_result.added_entries)}")
        
        if cpuset_result.status == CpusetModificationStatus.SUCCESS:
            success_count += 1
        elif cpuset_result.status == CpusetModificationStatus.ALREADY_MODIFIED:
            success_count += 1
            print("Note: Cpuset.c was already modified")
        elif not args.continue_on_error:
            print("Stopping due to cpuset modification failure")
            sys.exit(1)
    else:
        print("DRY RUN MODE - Cpuset.c not actually modified")
        success_count += 1  # Assume success for dry run
    
    # Step 3: Final verification
    print(f"\n3. Final verification")
    print("-" * 30)
    
    if not args.dry_run:
        # Verify cpuset compatibility
        is_compatible, missing_entries = cpuset_handler.verify_cpuset_compatibility()
        
        if is_compatible:
            print("✓ Cpuset.c is Docker-compatible")
        else:
            print(f"✗ Cpuset.c missing entries: {', '.join(missing_entries)}")
        
        # Verify applied patches
        applied_patches = engine.get_applied_patches()
        print(f"Applied patches: {len(applied_patches)}")
        for patch in applied_patches:
            print(f"  - {patch}")
    
    # Summary
    print(f"\n4. Summary")
    print("-" * 30)
    print(f"Operations completed: {success_count}/{total_operations}")
    
    if success_count == total_operations:
        print("✓ All operations completed successfully!")
        print("\nYour kernel source is now ready for Docker-enabled compilation.")
    else:
        print("✗ Some operations failed")
        if not args.continue_on_error:
            sys.exit(1)


def rollback_all_command(args):
    """Rollback all patches and cpuset modifications command handler."""
    print("Docker Kernel Patching - Complete Rollback")
    print("=" * 50)
    
    # Initialize components
    rollback = PatchRollback(args.kernel_source, args.backup_dir)
    cpuset_handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    success_count = 0
    total_operations = 0
    
    # Step 1: Rollback cpuset.c modifications
    print(f"\n1. Rolling back cpuset.c modifications")
    print("-" * 30)
    
    total_operations += 1
    cpuset_result = cpuset_handler.restore_original()
    
    print(f"Status: {cpuset_result.status.value}")
    print(f"Message: {cpuset_result.message}")
    
    if cpuset_result.backup_file:
        print(f"Restored from: {cpuset_result.backup_file}")
    
    if cpuset_result.status == CpusetModificationStatus.SUCCESS:
        success_count += 1
    
    # Step 2: Rollback all patches
    print(f"\n2. Rolling back all patches")
    print("-" * 30)
    
    patch_results = rollback.rollback_all_patches()
    
    for result in patch_results:
        total_operations += 1
        print(f"\nPatch: {result.patch_file}")
        print(f"Status: {result.status.value}")
        print(f"Message: {result.message}")
        
        if result.restored_files:
            print(f"Restored files: {', '.join(result.restored_files)}")
        
        if result.status == RollbackStatus.SUCCESS:
            success_count += 1
    
    # Summary
    print(f"\n3. Summary")
    print("-" * 30)
    print(f"Operations completed: {success_count}/{total_operations}")
    
    if success_count == total_operations:
        print("✓ All rollback operations completed successfully!")
        print("\nYour kernel source has been restored to its original state.")
    else:
        print("✗ Some rollback operations failed")
        sys.exit(1)


def status_command(args):
    """Show comprehensive status command handler."""
    print("Docker Kernel Patching - Status Report")
    print("=" * 50)
    
    # Initialize components
    engine = PatchEngine(args.kernel_source, args.backup_dir)
    cpuset_handler = CpusetHandler(args.kernel_source, args.backup_dir)
    
    # Patch status
    print(f"\n1. Patch Status")
    print("-" * 30)
    
    applied_patches = engine.get_applied_patches()
    print(f"Applied patches: {len(applied_patches)}")
    
    if applied_patches:
        for patch in applied_patches:
            print(f"  ✓ {patch}")
    else:
        print("  No patches currently applied")
    
    # Cpuset status
    print(f"\n2. Cpuset Status")
    print("-" * 30)
    
    cpuset_status = cpuset_handler.get_modification_status()
    
    print(f"File exists: {'Yes' if cpuset_status['file_exists'] else 'No'}")
    
    if cpuset_status['file_exists']:
        print(f"Is modified: {'Yes' if cpuset_status['is_modified'] else 'No'}")
        print(f"Is Docker-compatible: {'Yes' if cpuset_status['is_compatible'] else 'No'}")
        
        if cpuset_status['missing_entries']:
            print(f"Missing entries: {', '.join(cpuset_status['missing_entries'])}")
        
        print(f"Available backups: {len(cpuset_status['backup_files'])}")
    
    # Overall status
    print(f"\n3. Overall Status")
    print("-" * 30)
    
    is_ready = (
        len(applied_patches) > 0 and
        cpuset_status.get('is_compatible', False)
    )
    
    if is_ready:
        print("✓ Kernel source is ready for Docker-enabled compilation")
    else:
        print("✗ Kernel source is NOT ready for Docker-enabled compilation")
        
        if len(applied_patches) == 0:
            print("  - No patches applied")
        
        if not cpuset_status.get('is_compatible', False):
            print("  - Cpuset.c is not Docker-compatible")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integrated Patch Application Tool for Docker-enabled kernel build"
    )
    
    parser.add_argument(
        '--kernel-source',
        default='.',
        help='Path to kernel source directory (default: current directory)'
    )
    
    parser.add_argument(
        '--backup-dir',
        default='kernel_build/backups',
        help='Directory for backups (default: kernel_build/backups)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Apply all command
    apply_parser = subparsers.add_parser('apply-all', help='Apply all patches and modifications')
    apply_parser.add_argument(
        '--kernel-patch',
        default='files/kernel.diff',
        help='Path to kernel.diff file'
    )
    apply_parser.add_argument(
        '--aosp-patch',
        default='files/aosp.diff',
        help='Path to aosp.diff file'
    )
    apply_parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    apply_parser.add_argument('--force', action='store_true', help='Force modifications')
    apply_parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue even if some operations fail'
    )
    apply_parser.set_defaults(func=apply_all_patches_command)
    
    # Rollback all command
    rollback_parser = subparsers.add_parser('rollback-all', help='Rollback all patches and modifications')
    rollback_parser.set_defaults(func=rollback_all_command)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show comprehensive status')
    status_parser.set_defaults(func=status_command)
    
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