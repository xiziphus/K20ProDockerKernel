#!/usr/bin/env python3
"""
Patch Rollback System for Docker-enabled kernel build.

This module provides functionality for rolling back applied patches
and restoring the kernel source to previous states.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# File utilities are available as functions in kernel_build.utils.file_utils


class RollbackStatus(Enum):
    """Status of rollback operation."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    NO_BACKUP = "no_backup"
    ALREADY_CLEAN = "already_clean"


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    status: RollbackStatus
    patch_file: str
    message: str
    restored_files: List[str] = None
    failed_files: List[str] = None
    
    def __post_init__(self):
        if self.restored_files is None:
            self.restored_files = []
        if self.failed_files is None:
            self.failed_files = []


class PatchRollback:
    """
    System for rolling back applied patches and managing backup states.
    """
    
    def __init__(self, kernel_source_path: str, backup_dir: str = None):
        """
        Initialize the patch rollback system.
        
        Args:
            kernel_source_path: Path to kernel source directory
            backup_dir: Directory containing backups
        """
        self.kernel_source_path = Path(kernel_source_path)
        self.backup_dir = Path(backup_dir) if backup_dir else Path("kernel_build/backups/patches")
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Rollback history file
        self.rollback_history_file = self.backup_dir / "rollback_history.log"
    
    def rollback_patch(self, patch_file: str, method: str = "auto") -> RollbackResult:
        """
        Rollback a specific patch.
        
        Args:
            patch_file: Path to the patch file to rollback
            method: Rollback method ("auto", "reverse", "backup")
            
        Returns:
            RollbackResult object
        """
        patch_path = Path(patch_file)
        patch_name = patch_path.stem
        
        self.logger.info(f"Starting rollback for patch: {patch_file}")
        
        # Check if patch is applied
        if not self._is_patch_applied(patch_file):
            return RollbackResult(
                status=RollbackStatus.ALREADY_CLEAN,
                patch_file=patch_file,
                message="Patch is not applied, nothing to rollback"
            )
        
        # Try different rollback methods based on preference
        if method == "auto":
            # Try reverse patch first, then backup restore
            result = self._rollback_using_reverse_patch(patch_file)
            if result.status != RollbackStatus.SUCCESS:
                result = self._rollback_using_backup(patch_file)
        elif method == "reverse":
            result = self._rollback_using_reverse_patch(patch_file)
        elif method == "backup":
            result = self._rollback_using_backup(patch_file)
        else:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                patch_file=patch_file,
                message=f"Unknown rollback method: {method}"
            )
        
        # Log rollback operation
        if result.status == RollbackStatus.SUCCESS:
            self._log_rollback_operation(patch_file, method, result)
            self._remove_from_applied_patches(patch_file)
        
        return result
    
    def rollback_all_patches(self) -> List[RollbackResult]:
        """
        Rollback all applied patches in reverse order.
        
        Returns:
            List of RollbackResult objects
        """
        applied_patches = self._get_applied_patches()
        results = []
        
        # Rollback in reverse order (last applied first)
        for patch_file in reversed(applied_patches):
            self.logger.info(f"Rolling back patch: {patch_file}")
            result = self.rollback_patch(patch_file)
            results.append(result)
            
            # Stop on first failure to maintain consistency
            if result.status != RollbackStatus.SUCCESS:
                self.logger.error(f"Rollback failed for {patch_file}, stopping batch rollback")
                break
        
        return results
    
    def create_snapshot(self, snapshot_name: str = None) -> bool:
        """
        Create a snapshot of the current kernel source state.
        
        Args:
            snapshot_name: Name for the snapshot (optional)
            
        Returns:
            True if snapshot created successfully
        """
        if snapshot_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"snapshot_{timestamp}"
        
        snapshot_dir = self.backup_dir / "snapshots" / snapshot_name
        
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy important kernel source files
            important_paths = [
                "arch/arm64/configs/raphael_defconfig",
                "kernel/cgroup/cpuset.c",
                "include/linux/mm.h"
            ]
            
            for path in important_paths:
                source_file = self.kernel_source_path / path
                if source_file.exists():
                    target_file = snapshot_dir / path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target_file)
            
            # Save applied patches list
            applied_patches = self._get_applied_patches()
            with open(snapshot_dir / "applied_patches.txt", 'w') as f:
                for patch in applied_patches:
                    f.write(f"{patch}\n")
            
            self.logger.info(f"Created snapshot: {snapshot_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create snapshot {snapshot_name}: {e}")
            return False
    
    def restore_snapshot(self, snapshot_name: str) -> RollbackResult:
        """
        Restore kernel source from a snapshot.
        
        Args:
            snapshot_name: Name of the snapshot to restore
            
        Returns:
            RollbackResult object
        """
        snapshot_dir = self.backup_dir / "snapshots" / snapshot_name
        
        if not snapshot_dir.exists():
            return RollbackResult(
                status=RollbackStatus.NO_BACKUP,
                patch_file="snapshot",
                message=f"Snapshot not found: {snapshot_name}"
            )
        
        try:
            restored_files = []
            failed_files = []
            
            # Restore all files from snapshot
            for snapshot_file in snapshot_dir.rglob('*'):
                if snapshot_file.is_file() and snapshot_file.name != "applied_patches.txt":
                    relative_path = snapshot_file.relative_to(snapshot_dir)
                    target_file = self.kernel_source_path / relative_path
                    
                    try:
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(snapshot_file, target_file)
                        restored_files.append(str(relative_path))
                    except Exception as e:
                        self.logger.error(f"Failed to restore {relative_path}: {e}")
                        failed_files.append(str(relative_path))
            
            # Update applied patches list
            applied_patches_file = snapshot_dir / "applied_patches.txt"
            if applied_patches_file.exists():
                self._restore_applied_patches_list(applied_patches_file)
            
            # Determine status
            if failed_files:
                if restored_files:
                    status = RollbackStatus.PARTIAL
                    message = f"Partial restore: {len(restored_files)} restored, {len(failed_files)} failed"
                else:
                    status = RollbackStatus.FAILED
                    message = f"Restore failed for all files"
            else:
                status = RollbackStatus.SUCCESS
                message = f"Successfully restored {len(restored_files)} files from snapshot"
            
            return RollbackResult(
                status=status,
                patch_file="snapshot",
                message=message,
                restored_files=restored_files,
                failed_files=failed_files
            )
            
        except Exception as e:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                patch_file="snapshot",
                message=f"Snapshot restore error: {str(e)}"
            )
    
    def list_snapshots(self) -> List[str]:
        """
        List available snapshots.
        
        Returns:
            List of snapshot names
        """
        snapshots_dir = self.backup_dir / "snapshots"
        
        if not snapshots_dir.exists():
            return []
        
        snapshots = []
        for item in snapshots_dir.iterdir():
            if item.is_dir():
                snapshots.append(item.name)
        
        return sorted(snapshots)
    
    def _rollback_using_reverse_patch(self, patch_file: str) -> RollbackResult:
        """Rollback using reverse patch application."""
        try:
            import subprocess
            
            cmd = ['patch', '-p1', '-R', '-i', str(Path(patch_file).absolute())]
            result = subprocess.run(
                cmd,
                cwd=self.kernel_source_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Extract files that were restored
                restored_files = self._extract_modified_files(patch_file)
                
                return RollbackResult(
                    status=RollbackStatus.SUCCESS,
                    patch_file=patch_file,
                    message="Patch rolled back using reverse application",
                    restored_files=restored_files
                )
            else:
                return RollbackResult(
                    status=RollbackStatus.FAILED,
                    patch_file=patch_file,
                    message=f"Reverse patch failed: {result.stderr}"
                )
                
        except Exception as e:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                patch_file=patch_file,
                message=f"Reverse patch error: {str(e)}"
            )
    
    def _rollback_using_backup(self, patch_file: str) -> RollbackResult:
        """Rollback using backup files."""
        patch_name = Path(patch_file).stem
        backup_subdir = self.backup_dir / f"{patch_name}_backup"
        
        if not backup_subdir.exists():
            return RollbackResult(
                status=RollbackStatus.NO_BACKUP,
                patch_file=patch_file,
                message=f"No backup found for patch: {patch_file}"
            )
        
        try:
            restored_files = []
            failed_files = []
            
            # Restore all backed up files
            for backup_file in backup_subdir.rglob('*'):
                if backup_file.is_file():
                    relative_path = backup_file.relative_to(backup_subdir)
                    target_file = self.kernel_source_path / relative_path
                    
                    try:
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_file, target_file)
                        restored_files.append(str(relative_path))
                    except Exception as e:
                        self.logger.error(f"Failed to restore {relative_path}: {e}")
                        failed_files.append(str(relative_path))
            
            # Determine status
            if failed_files:
                if restored_files:
                    status = RollbackStatus.PARTIAL
                    message = f"Partial rollback: {len(restored_files)} restored, {len(failed_files)} failed"
                else:
                    status = RollbackStatus.FAILED
                    message = f"Backup rollback failed for all files"
            else:
                status = RollbackStatus.SUCCESS
                message = f"Successfully rolled back {len(restored_files)} files from backup"
            
            return RollbackResult(
                status=status,
                patch_file=patch_file,
                message=message,
                restored_files=restored_files,
                failed_files=failed_files
            )
            
        except Exception as e:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                patch_file=patch_file,
                message=f"Backup rollback error: {str(e)}"
            )
    
    def _extract_modified_files(self, patch_file: str) -> List[str]:
        """Extract list of files modified by the patch."""
        modified_files = []
        
        try:
            with open(patch_file, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            for line in lines:
                if line.startswith('diff --git'):
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[3][2:]  # Remove 'b/' prefix
                        if file_path not in modified_files:
                            modified_files.append(file_path)
        
        except Exception as e:
            self.logger.warning(f"Could not extract modified files from {patch_file}: {e}")
        
        return modified_files
    
    def _is_patch_applied(self, patch_file: str) -> bool:
        """Check if a patch is currently applied."""
        applied_patches = self._get_applied_patches()
        return patch_file in applied_patches
    
    def _get_applied_patches(self) -> List[str]:
        """Get list of currently applied patches."""
        applied_patches_file = self.backup_dir / "applied_patches.log"
        
        if not applied_patches_file.exists():
            return []
        
        applied_patches = []
        try:
            with open(applied_patches_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        applied_patches.append(line.strip().split()[0])
        except Exception as e:
            self.logger.error(f"Error reading applied patches log: {e}")
        
        return applied_patches
    
    def _remove_from_applied_patches(self, patch_file: str):
        """Remove patch from applied patches log."""
        applied_patches_file = self.backup_dir / "applied_patches.log"
        
        if not applied_patches_file.exists():
            return
        
        try:
            # Read all lines
            with open(applied_patches_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out the patch
            filtered_lines = [line for line in lines if not line.startswith(patch_file)]
            
            # Write back
            with open(applied_patches_file, 'w') as f:
                f.writelines(filtered_lines)
        except Exception as e:
            self.logger.error(f"Failed to remove applied patch log for {patch_file}: {e}")
    
    def _restore_applied_patches_list(self, snapshot_patches_file: Path):
        """Restore applied patches list from snapshot."""
        applied_patches_file = self.backup_dir / "applied_patches.log"
        
        try:
            shutil.copy2(snapshot_patches_file, applied_patches_file)
        except Exception as e:
            self.logger.error(f"Failed to restore applied patches list: {e}")
    
    def _log_rollback_operation(self, patch_file: str, method: str, result: RollbackResult):
        """Log rollback operation to history."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.rollback_history_file, 'a') as f:
                f.write(f"{timestamp} ROLLBACK {patch_file} {method} {result.status.value}\n")
        except Exception as e:
            self.logger.error(f"Failed to log rollback operation: {e}")