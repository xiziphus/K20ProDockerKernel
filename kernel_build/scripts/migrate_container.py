#!/usr/bin/env python3
"""
Container Migration Script for cross-architecture migration.

This script handles the migration of containers from x86 to ARM64 platforms
using CRIU checkpointing and restoration.
"""

import os
import sys
import json
import logging
import argparse
import time
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.migration_orchestrator import (
    MigrationOrchestrator, 
    MigrationConfig, 
    MigrationStatus
)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def print_compatibility_report(compatibility):
    """Print container compatibility report."""
    print("\n=== Container Compatibility Report ===")
    print(f"Overall Compatible: {'✓' if compatibility.is_compatible else '✗'}")
    print(f"Architecture Compatible: {'✓' if compatibility.architecture_compatible else '✗'}")
    print(f"Kernel Compatible: {'✓' if compatibility.kernel_compatible else '✗'}")
    print(f"Runtime Compatible: {'✓' if compatibility.runtime_compatible else '✗'}")
    
    if compatibility.issues:
        print("\nIssues:")
        for issue in compatibility.issues:
            print(f"  • {issue}")
    
    if compatibility.recommendations:
        print("\nRecommendations:")
        for rec in compatibility.recommendations:
            print(f"  • {rec}")
    print()


def print_migration_result(result):
    """Print migration result summary."""
    print("\n=== Migration Result ===")
    print(f"Status: {result.status.value}")
    print(f"Success: {'✓' if result.success else '✗'}")
    print(f"Container ID: {result.container_id}")
    
    if result.migration_time:
        print(f"Migration Time: {result.migration_time:.2f} seconds")
    
    if result.source_checkpoint_path:
        print(f"Source Checkpoint: {result.source_checkpoint_path}")
    
    if result.target_checkpoint_path:
        print(f"Target Checkpoint: {result.target_checkpoint_path}")
    
    if result.error_message:
        print(f"Error: {result.error_message}")
    
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  • {warning}")
    print()


def check_container_compatibility(container_id: str, target_arch: str = "aarch64"):
    """Check and display container compatibility."""
    orchestrator = MigrationOrchestrator()
    
    print(f"Checking compatibility for container: {container_id}")
    compatibility = orchestrator.check_container_compatibility(container_id, target_arch)
    
    print_compatibility_report(compatibility)
    
    return compatibility.is_compatible


def migrate_container(
    container_id: str,
    target_host: str,
    source_arch: str = "x86_64",
    target_arch: str = "aarch64",
    preserve_networking: bool = True,
    preserve_volumes: bool = True,
    rollback_on_failure: bool = True,
    dry_run: bool = False
):
    """Migrate container to target host."""
    
    orchestrator = MigrationOrchestrator()
    
    # Create migration configuration
    config = MigrationConfig(
        container_id=container_id,
        source_host="localhost",
        target_host=target_host,
        source_arch=source_arch,
        target_arch=target_arch,
        preserve_networking=preserve_networking,
        preserve_volumes=preserve_volumes,
        rollback_on_failure=rollback_on_failure
    )
    
    if dry_run:
        print("=== DRY RUN MODE ===")
        print("Checking migration prerequisites and compatibility...")
        
        # Check prerequisites
        is_valid, errors = orchestrator.validate_migration_prerequisites(config)
        if not is_valid:
            print("Prerequisites validation failed:")
            for error in errors:
                print(f"  • {error}")
            return False
        else:
            print("✓ Prerequisites validation passed")
        
        # Check compatibility
        compatibility = orchestrator.check_container_compatibility(container_id, target_arch)
        print_compatibility_report(compatibility)
        
        if compatibility.is_compatible:
            print("✓ Container is compatible for migration")
            print("Migration would proceed in normal mode")
        else:
            print("✗ Container has compatibility issues")
            print("Migration would fail in normal mode")
        
        return compatibility.is_compatible
    
    # Perform actual migration
    print(f"Starting migration of container {container_id} to {target_host}")
    print("This may take several minutes...")
    
    result = orchestrator.migrate_container(config)
    
    print_migration_result(result)
    
    return result.success


def list_active_migrations():
    """List active migrations."""
    orchestrator = MigrationOrchestrator()
    migrations = orchestrator.list_active_migrations()
    
    if not migrations:
        print("No active migrations")
        return
    
    print("=== Active Migrations ===")
    for migration in migrations:
        print(f"Container: {migration.container_id}")
        print(f"Status: {migration.status.value}")
        if migration.error_message:
            print(f"Error: {migration.error_message}")
        print()


def cancel_migration(container_id: str):
    """Cancel active migration."""
    orchestrator = MigrationOrchestrator()
    
    if orchestrator.cancel_migration(container_id):
        print(f"Migration for container {container_id} cancelled successfully")
        return True
    else:
        print(f"Failed to cancel migration for container {container_id}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Container cross-architecture migration tool")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Check compatibility command
    check_parser = subparsers.add_parser("check", help="Check container compatibility")
    check_parser.add_argument("container_id", help="Container ID to check")
    check_parser.add_argument("--target-arch", default="aarch64", help="Target architecture")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate container")
    migrate_parser.add_argument("container_id", help="Container ID to migrate")
    migrate_parser.add_argument("target_host", help="Target host (e.g., adb:device_id or user@host)")
    migrate_parser.add_argument("--source-arch", default="x86_64", help="Source architecture")
    migrate_parser.add_argument("--target-arch", default="aarch64", help="Target architecture")
    migrate_parser.add_argument("--no-preserve-networking", action="store_true", help="Don't preserve networking")
    migrate_parser.add_argument("--no-preserve-volumes", action="store_true", help="Don't preserve volumes")
    migrate_parser.add_argument("--no-rollback", action="store_true", help="Don't rollback on failure")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Perform dry run without actual migration")
    
    # List active migrations command
    list_parser = subparsers.add_parser("list", help="List active migrations")
    
    # Cancel migration command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel active migration")
    cancel_parser.add_argument("container_id", help="Container ID to cancel")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    setup_logging(args.verbose)
    
    try:
        if args.command == "check":
            success = check_container_compatibility(args.container_id, args.target_arch)
            return 0 if success else 1
        
        elif args.command == "migrate":
            success = migrate_container(
                container_id=args.container_id,
                target_host=args.target_host,
                source_arch=args.source_arch,
                target_arch=args.target_arch,
                preserve_networking=not args.no_preserve_networking,
                preserve_volumes=not args.no_preserve_volumes,
                rollback_on_failure=not args.no_rollback,
                dry_run=args.dry_run
            )
            return 0 if success else 1
        
        elif args.command == "list":
            list_active_migrations()
            return 0
        
        elif args.command == "cancel":
            success = cancel_migration(args.container_id)
            return 0 if success else 1
        
        else:
            parser.print_help()
            return 1
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())