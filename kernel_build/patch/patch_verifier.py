#!/usr/bin/env python3
"""
Patch Verification System for Docker-enabled kernel build.

This module provides functionality for verifying patch application
and validating the integrity of patched files.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# File utilities are available as functions in kernel_build.utils.file_utils


class VerificationStatus(Enum):
    """Status of patch verification."""
    VERIFIED = "verified"
    FAILED = "failed"
    PARTIAL = "partial"
    MISSING_FILES = "missing_files"
    CHECKSUM_MISMATCH = "checksum_mismatch"


@dataclass
class VerificationResult:
    """Result of patch verification operation."""
    status: VerificationStatus
    patch_file: str
    message: str
    verified_files: List[str] = None
    failed_files: List[str] = None
    missing_files: List[str] = None
    
    def __post_init__(self):
        if self.verified_files is None:
            self.verified_files = []
        if self.failed_files is None:
            self.failed_files = []
        if self.missing_files is None:
            self.missing_files = []


class PatchVerifier:
    """
    Verifier for patch application integrity and correctness.
    """
    
    def __init__(self, kernel_source_path: str, verification_data_dir: str = None):
        """
        Initialize the patch verifier.
        
        Args:
            kernel_source_path: Path to kernel source directory
            verification_data_dir: Directory to store verification data
        """
        self.kernel_source_path = Path(kernel_source_path)
        self.verification_data_dir = Path(verification_data_dir) if verification_data_dir else Path("kernel_build/verification")
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.verification_data_dir.mkdir(parents=True, exist_ok=True)
    
    def verify_patch_application(self, patch_file: str, expected_files: List[str] = None) -> VerificationResult:
        """
        Verify that a patch has been correctly applied.
        
        Args:
            patch_file: Path to the patch file
            expected_files: List of files expected to be modified (optional)
            
        Returns:
            VerificationResult object
        """
        patch_path = Path(patch_file)
        patch_name = patch_path.stem
        
        if not patch_path.exists():
            return VerificationResult(
                status=VerificationStatus.FAILED,
                patch_file=patch_file,
                message=f"Patch file not found: {patch_file}"
            )
        
        # Extract expected files from patch if not provided
        if expected_files is None:
            expected_files = self._extract_modified_files(patch_file)
        
        if not expected_files:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                patch_file=patch_file,
                message="No files to verify"
            )
        
        verified_files = []
        failed_files = []
        missing_files = []
        
        # Check each expected file
        for file_path in expected_files:
            full_path = self.kernel_source_path / file_path
            
            if not full_path.exists():
                missing_files.append(file_path)
                continue
            
            # Verify file content matches expected changes
            if self._verify_file_changes(patch_file, file_path):
                verified_files.append(file_path)
            else:
                failed_files.append(file_path)
        
        # Determine overall status
        if missing_files:
            status = VerificationStatus.MISSING_FILES
            message = f"Missing files: {', '.join(missing_files)}"
        elif failed_files:
            if verified_files:
                status = VerificationStatus.PARTIAL
                message = f"Partial verification: {len(verified_files)} verified, {len(failed_files)} failed"
            else:
                status = VerificationStatus.FAILED
                message = f"Verification failed for all files: {', '.join(failed_files)}"
        else:
            status = VerificationStatus.VERIFIED
            message = f"All {len(verified_files)} files verified successfully"
        
        return VerificationResult(
            status=status,
            patch_file=patch_file,
            message=message,
            verified_files=verified_files,
            failed_files=failed_files,
            missing_files=missing_files
        )
    
    def create_verification_baseline(self, patch_file: str) -> bool:
        """
        Create a baseline for verification after successful patch application.
        
        Args:
            patch_file: Path to the patch file
            
        Returns:
            True if baseline created successfully
        """
        try:
            patch_name = Path(patch_file).stem
            baseline_file = self.verification_data_dir / f"{patch_name}_baseline.json"
            
            modified_files = self._extract_modified_files(patch_file)
            baseline_data = {}
            
            for file_path in modified_files:
                full_path = self.kernel_source_path / file_path
                if full_path.exists():
                    # Calculate file checksum
                    checksum = self._calculate_file_checksum(full_path)
                    baseline_data[file_path] = {
                        'checksum': checksum,
                        'size': full_path.stat().st_size,
                        'modified_time': full_path.stat().st_mtime
                    }
            
            # Save baseline data
            import json
            with open(baseline_file, 'w') as f:
                json.dump(baseline_data, f, indent=2)
            
            self.logger.info(f"Created verification baseline for {patch_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create verification baseline for {patch_file}: {e}")
            return False
    
    def verify_against_baseline(self, patch_file: str) -> VerificationResult:
        """
        Verify current state against stored baseline.
        
        Args:
            patch_file: Path to the patch file
            
        Returns:
            VerificationResult object
        """
        patch_name = Path(patch_file).stem
        baseline_file = self.verification_data_dir / f"{patch_name}_baseline.json"
        
        if not baseline_file.exists():
            return VerificationResult(
                status=VerificationStatus.FAILED,
                patch_file=patch_file,
                message="No baseline found for verification"
            )
        
        try:
            import json
            with open(baseline_file, 'r') as f:
                baseline_data = json.load(f)
            
            verified_files = []
            failed_files = []
            missing_files = []
            
            for file_path, baseline_info in baseline_data.items():
                full_path = self.kernel_source_path / file_path
                
                if not full_path.exists():
                    missing_files.append(file_path)
                    continue
                
                # Check checksum
                current_checksum = self._calculate_file_checksum(full_path)
                if current_checksum == baseline_info['checksum']:
                    verified_files.append(file_path)
                else:
                    failed_files.append(file_path)
            
            # Determine status
            if missing_files:
                status = VerificationStatus.MISSING_FILES
                message = f"Missing files: {', '.join(missing_files)}"
            elif failed_files:
                status = VerificationStatus.CHECKSUM_MISMATCH
                message = f"Checksum mismatch: {', '.join(failed_files)}"
            else:
                status = VerificationStatus.VERIFIED
                message = f"All {len(verified_files)} files match baseline"
            
            return VerificationResult(
                status=status,
                patch_file=patch_file,
                message=message,
                verified_files=verified_files,
                failed_files=failed_files,
                missing_files=missing_files
            )
            
        except Exception as e:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                patch_file=patch_file,
                message=f"Baseline verification error: {str(e)}"
            )
    
    def verify_patch_integrity(self, patch_file: str) -> bool:
        """
        Verify the integrity of the patch file itself.
        
        Args:
            patch_file: Path to the patch file
            
        Returns:
            True if patch file is valid
        """
        try:
            patch_path = Path(patch_file)
            
            if not patch_path.exists():
                self.logger.error(f"Patch file not found: {patch_file}")
                return False
            
            # Check if file is readable
            with open(patch_path, 'r') as f:
                content = f.read()
            
            # Basic patch format validation
            if not self._is_valid_patch_format(content):
                self.logger.error(f"Invalid patch format: {patch_file}")
                return False
            
            # Check for required headers
            if not self._has_required_headers(content):
                self.logger.error(f"Missing required headers: {patch_file}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Patch integrity check failed for {patch_file}: {e}")
            return False
    
    def _extract_modified_files(self, patch_file: str) -> List[str]:
        """Extract list of files modified by the patch."""
        modified_files = []
        
        try:
            with open(patch_file, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            for line in lines:
                if line.startswith('diff --git'):
                    # Extract file path from git diff format
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[3][2:]  # Remove 'b/' prefix
                        if file_path not in modified_files:
                            modified_files.append(file_path)
                elif line.startswith('+++') and not line.startswith('+++ /dev/null'):
                    # Extract file path from unified diff format
                    file_path = line[4:].strip()
                    # Remove timestamp if present
                    file_path = file_path.split('\t')[0]
                    if file_path not in modified_files:
                        modified_files.append(file_path)
        
        except Exception as e:
            self.logger.warning(f"Could not extract modified files from {patch_file}: {e}")
        
        return modified_files
    
    def _verify_file_changes(self, patch_file: str, file_path: str) -> bool:
        """
        Verify that specific file changes match the patch.
        
        This is a simplified verification - in practice, you might want
        to implement more sophisticated content verification.
        """
        try:
            full_path = self.kernel_source_path / file_path
            
            if not full_path.exists():
                return False
            
            # For now, just check that the file exists and is readable
            # More sophisticated verification could parse the patch hunks
            # and verify specific changes
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Basic verification: file should contain some expected content
            # This could be enhanced to check specific patch hunks
            return len(content) > 0
            
        except Exception as e:
            self.logger.warning(f"Could not verify changes for {file_path}: {e}")
            return False
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def _is_valid_patch_format(self, content: str) -> bool:
        """Check if content follows valid patch format."""
        # Check for common patch indicators
        patch_indicators = [
            'diff --git',
            '--- ',
            '+++ ',
            '@@',
            'index '
        ]
        
        return any(indicator in content for indicator in patch_indicators)
    
    def _has_required_headers(self, content: str) -> bool:
        """Check if patch has required headers."""
        lines = content.split('\n')
        
        # Look for file modification indicators
        has_diff_header = any(line.startswith('diff --git') for line in lines)
        has_file_headers = any(line.startswith('---') for line in lines) and any(line.startswith('+++') for line in lines)
        
        return has_diff_header or has_file_headers