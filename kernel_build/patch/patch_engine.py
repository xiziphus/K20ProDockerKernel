#!/usr/bin/env python3
"""
Patch Application Engine for Docker-enabled kernel build.

This module handles the application of kernel.diff and aosp.diff patches
with conflict detection, verification, and rollback capabilities.
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# File utilities are available as functions in kernel_build.utils.file_utils


class PatchStatus(Enum):
    """Status of patch application."""
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    ALREADY_APPLIED = "already_applied"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass
class PatchResult:
    """Result of patch application operation."""
    status: PatchStatus
    patch_file: str
    message: str
    conflicts: List[str] = None
    applied_files: List[str] = None
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.applied_files is None:
            self.applied_files = []


class PatchEngine:
    """
    Engine for applying kernel patches with conflict detection and rollback.
    """
    
    def __init__(self, kernel_source_path: str, backup_dir: str = None):
        """
        Initialize the patch engine.
        
        Args:
            kernel_source_path: Path to kernel source directory
            backup_dir: Directory to store backups (optional)
        """
        self.kernel_source_path = Path(kernel_source_path)
        self.backup_dir = Path(backup_dir) if backup_dir else Path("kernel_build/backups/patches")
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Track applied patches
        self.applied_patches_file = self.backup_dir / "applied_patches.log"
        
    def apply_patches(self, patch_files: List[str], dry_run: bool = False) -> List[PatchResult]:
        """
        Apply multiple patch files to the kernel source.
        
        Args:
            patch_files: List of patch file paths
            dry_run: If True, only check if patches can be applied without applying them
            
        Returns:
            List of PatchResult objects
        """
        results = []
        
        for patch_file in patch_files:
            self.logger.info(f"Processing patch: {patch_file}")
            result = self.apply_single_patch(patch_file, dry_run)
            results.append(result)
            
            # Stop on first failure unless it's a dry run
            if not dry_run and result.status in [PatchStatus.FAILED, PatchStatus.CONFLICT]:
                self.logger.error(f"Patch application failed for {patch_file}, stopping")
                break
                
        return results
    
    def apply_single_patch(self, patch_file: str, dry_run: bool = False) -> PatchResult:
        """
        Apply a single patch file.
        
        Args:
            patch_file: Path to patch file
            dry_run: If True, only check if patch can be applied
            
        Returns:
            PatchResult object
        """
        patch_path = Path(patch_file)
        
        if not patch_path.exists():
            return PatchResult(
                status=PatchStatus.FAILED,
                patch_file=patch_file,
                message=f"Patch file not found: {patch_file}"
            )
        
        # Check if patch is already applied
        if self._is_patch_applied(patch_file):
            return PatchResult(
                status=PatchStatus.ALREADY_APPLIED,
                patch_file=patch_file,
                message=f"Patch already applied: {patch_file}"
            )
        
        # Create backup before applying patch
        if not dry_run:
            backup_success = self._create_backup(patch_file)
            if not backup_success:
                return PatchResult(
                    status=PatchStatus.FAILED,
                    patch_file=patch_file,
                    message="Failed to create backup before applying patch"
                )
        
        # Try to apply the patch
        try:
            cmd = self._build_patch_command(patch_file, dry_run)
            result = subprocess.run(
                cmd,
                cwd=self.kernel_source_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Patch applied successfully
                applied_files = self._extract_applied_files(patch_file)
                
                if not dry_run:
                    self._log_applied_patch(patch_file, applied_files)
                
                return PatchResult(
                    status=PatchStatus.SUCCESS,
                    patch_file=patch_file,
                    message="Patch applied successfully",
                    applied_files=applied_files
                )
            else:
                # Check if it's a conflict or other error
                conflicts = self._detect_conflicts(result.stderr)
                
                if conflicts:
                    return PatchResult(
                        status=PatchStatus.CONFLICT,
                        patch_file=patch_file,
                        message=f"Patch conflicts detected: {result.stderr}",
                        conflicts=conflicts
                    )
                else:
                    return PatchResult(
                        status=PatchStatus.FAILED,
                        patch_file=patch_file,
                        message=f"Patch application failed: {result.stderr}"
                    )
                    
        except subprocess.TimeoutExpired:
            return PatchResult(
                status=PatchStatus.FAILED,
                patch_file=patch_file,
                message="Patch application timed out"
            )
        except Exception as e:
            return PatchResult(
                status=PatchStatus.FAILED,
                patch_file=patch_file,
                message=f"Unexpected error: {str(e)}"
            )
    
    def rollback_patch(self, patch_file: str) -> PatchResult:
        """
        Rollback a previously applied patch.
        
        Args:
            patch_file: Path to patch file to rollback
            
        Returns:
            PatchResult object
        """
        if not self._is_patch_applied(patch_file):
            return PatchResult(
                status=PatchStatus.FAILED,
                patch_file=patch_file,
                message="Patch is not applied, cannot rollback"
            )
        
        try:
            # Try to reverse the patch
            cmd = self._build_patch_command(patch_file, dry_run=False, reverse=True)
            result = subprocess.run(
                cmd,
                cwd=self.kernel_source_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self._remove_applied_patch_log(patch_file)
                return PatchResult(
                    status=PatchStatus.ROLLBACK_SUCCESS,
                    patch_file=patch_file,
                    message="Patch rolled back successfully"
                )
            else:
                # Try to restore from backup
                backup_success = self._restore_from_backup(patch_file)
                if backup_success:
                    self._remove_applied_patch_log(patch_file)
                    return PatchResult(
                        status=PatchStatus.ROLLBACK_SUCCESS,
                        patch_file=patch_file,
                        message="Patch rolled back using backup"
                    )
                else:
                    return PatchResult(
                        status=PatchStatus.ROLLBACK_FAILED,
                        patch_file=patch_file,
                        message=f"Rollback failed: {result.stderr}"
                    )
                    
        except Exception as e:
            return PatchResult(
                status=PatchStatus.ROLLBACK_FAILED,
                patch_file=patch_file,
                message=f"Rollback error: {str(e)}"
            )
    
    def get_applied_patches(self) -> List[str]:
        """
        Get list of currently applied patches.
        
        Returns:
            List of applied patch file paths
        """
        if not self.applied_patches_file.exists():
            return []
        
        applied_patches = []
        try:
            with open(self.applied_patches_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        applied_patches.append(line.strip().split()[0])
        except Exception as e:
            self.logger.error(f"Error reading applied patches log: {e}")
        
        return applied_patches
    
    def _build_patch_command(self, patch_file: str, dry_run: bool = False, reverse: bool = False) -> List[str]:
        """Build the patch command with appropriate options."""
        cmd = ['patch']
        
        # Add options
        cmd.extend(['-p1'])  # Strip one level of directory
        
        if dry_run:
            cmd.append('--dry-run')
        
        if reverse:
            cmd.append('-R')
        
        # Add input file
        cmd.extend(['-i', str(Path(patch_file).absolute())])
        
        return cmd
    
    def _detect_conflicts(self, stderr_output: str) -> List[str]:
        """Detect conflicts from patch command stderr output."""
        conflicts = []
        
        # Common conflict indicators
        conflict_indicators = [
            'FAILED',
            'rejected',
            'conflict',
            'Hunk #',
            'malformed patch'
        ]
        
        lines = stderr_output.split('\n')
        for line in lines:
            for indicator in conflict_indicators:
                if indicator.lower() in line.lower():
                    conflicts.append(line.strip())
                    break
        
        return conflicts
    
    def _extract_applied_files(self, patch_file: str) -> List[str]:
        """Extract list of files that would be modified by the patch."""
        applied_files = []
        
        try:
            with open(patch_file, 'r') as f:
                content = f.read()
            
            # Parse diff format to extract file paths
            lines = content.split('\n')
            for line in lines:
                if line.startswith('diff --git'):
                    # Extract file path from git diff format
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[3][2:]  # Remove 'b/' prefix
                        applied_files.append(file_path)
                elif line.startswith('---') and not line.startswith('--- /dev/null'):
                    # Extract file path from unified diff format
                    file_path = line[4:].strip()
                    if file_path not in applied_files:
                        applied_files.append(file_path)
        
        except Exception as e:
            self.logger.warning(f"Could not extract applied files from {patch_file}: {e}")
        
        return applied_files
    
    def _create_backup(self, patch_file: str) -> bool:
        """Create backup of files that will be modified by the patch."""
        try:
            applied_files = self._extract_applied_files(patch_file)
            patch_name = Path(patch_file).stem
            backup_subdir = self.backup_dir / f"{patch_name}_backup"
            backup_subdir.mkdir(exist_ok=True)
            
            for file_path in applied_files:
                source_file = self.kernel_source_path / file_path
                if source_file.exists():
                    backup_file = backup_subdir / file_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, backup_file)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to create backup for {patch_file}: {e}")
            return False
    
    def _restore_from_backup(self, patch_file: str) -> bool:
        """Restore files from backup."""
        try:
            patch_name = Path(patch_file).stem
            backup_subdir = self.backup_dir / f"{patch_name}_backup"
            
            if not backup_subdir.exists():
                return False
            
            # Restore all backed up files
            for backup_file in backup_subdir.rglob('*'):
                if backup_file.is_file():
                    relative_path = backup_file.relative_to(backup_subdir)
                    target_file = self.kernel_source_path / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore from backup for {patch_file}: {e}")
            return False
    
    def _is_patch_applied(self, patch_file: str) -> bool:
        """Check if a patch is already applied."""
        applied_patches = self.get_applied_patches()
        return patch_file in applied_patches
    
    def _log_applied_patch(self, patch_file: str, applied_files: List[str]):
        """Log that a patch has been applied."""
        try:
            with open(self.applied_patches_file, 'a') as f:
                f.write(f"{patch_file} {' '.join(applied_files)}\n")
        except Exception as e:
            self.logger.error(f"Failed to log applied patch {patch_file}: {e}")
    
    def _remove_applied_patch_log(self, patch_file: str):
        """Remove patch from applied patches log."""
        if not self.applied_patches_file.exists():
            return
        
        try:
            # Read all lines
            with open(self.applied_patches_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out the patch
            filtered_lines = [line for line in lines if not line.startswith(patch_file)]
            
            # Write back
            with open(self.applied_patches_file, 'w') as f:
                f.writelines(filtered_lines)
        except Exception as e:
            self.logger.error(f"Failed to remove applied patch log for {patch_file}: {e}")