#!/usr/bin/env python3
"""
Cpuset.c Modification Handler for Docker-enabled kernel build.

This module handles automatic modification of kernel/cgroup/cpuset.c
to restore cpuset prefixes required for Docker compatibility.
"""

import os
import re
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# File utilities are available as functions in kernel_build.utils.file_utils


class CpusetModificationStatus(Enum):
    """Status of cpuset modification operation."""
    SUCCESS = "success"
    FAILED = "failed"
    ALREADY_MODIFIED = "already_modified"
    FILE_NOT_FOUND = "file_not_found"
    BACKUP_FAILED = "backup_failed"
    VERIFICATION_FAILED = "verification_failed"


@dataclass
class CpusetModificationResult:
    """Result of cpuset modification operation."""
    status: CpusetModificationStatus
    message: str
    backup_file: Optional[str] = None
    modified_lines: int = 0
    added_entries: List[str] = None
    
    def __post_init__(self):
        if self.added_entries is None:
            self.added_entries = []


class CpusetHandler:
    """
    Handler for modifying kernel/cgroup/cpuset.c to restore Docker-compatible cpuset prefixes.
    """
    
    def __init__(self, kernel_source_path: str, backup_dir: str = None):
        """
        Initialize the cpuset handler.
        
        Args:
            kernel_source_path: Path to kernel source directory
            backup_dir: Directory to store backups (optional)
        """
        self.kernel_source_path = Path(kernel_source_path)
        self.backup_dir = Path(backup_dir) if backup_dir else Path("kernel_build/backups/cpuset")
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Path to cpuset.c file
        self.cpuset_file = self.kernel_source_path / "kernel" / "cgroup" / "cpuset.c"
        
        # Docker-required cpuset entries
        self.required_cpuset_entries = [
            {
                'name': 'cpuset.cpus',
                'seq_show': 'cpuset_common_seq_show',
                'write': 'cpuset_write_resmask_wrapper',
                'max_write_len': '(100U + 6 * NR_CPUS)',
                'private': 'FILE_CPULIST'
            },
            {
                'name': 'cpuset.mems',
                'seq_show': 'cpuset_common_seq_show',
                'write': 'cpuset_write_resmask',
                'max_write_len': '(100U + 6 * MAX_NUMNODES)',
                'private': 'FILE_MEMLIST'
            },
            {
                'name': 'cpuset.effective_cpus',
                'seq_show': 'cpuset_common_seq_show',
                'private': 'FILE_EFFECTIVE_CPULIST'
            },
            {
                'name': 'cpuset.effective_mems',
                'seq_show': 'cpuset_common_seq_show',
                'private': 'FILE_EFFECTIVE_MEMLIST'
            },
            {
                'name': 'cpuset.cpu_exclusive',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_CPU_EXCLUSIVE'
            },
            {
                'name': 'cpuset.mem_exclusive',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_MEM_EXCLUSIVE'
            },
            {
                'name': 'cpuset.mem_hardwall',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_MEM_HARDWALL'
            },
            {
                'name': 'cpuset.sched_load_balance',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_SCHED_LOAD_BALANCE'
            },
            {
                'name': 'cpuset.sched_relax_domain_level',
                'read_s64': 'cpuset_read_s64',
                'write_s64': 'cpuset_write_s64',
                'private': 'FILE_SCHED_RELAX_DOMAIN_LEVEL'
            },
            {
                'name': 'cpuset.memory_migrate',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_MEMORY_MIGRATE'
            },
            {
                'name': 'cpuset.memory_pressure',
                'read_u64': 'cpuset_read_u64',
                'private': 'FILE_MEMORY_PRESSURE'
            },
            {
                'name': 'cpuset.memory_spread_page',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_SPREAD_PAGE'
            },
            {
                'name': 'cpuset.memory_spread_slab',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_SPREAD_SLAB'
            },
            {
                'name': 'cpuset.memory_pressure_enabled',
                'flags': 'CFTYPE_ONLY_ON_ROOT',
                'read_u64': 'cpuset_read_u64',
                'write_u64': 'cpuset_write_u64',
                'private': 'FILE_MEMORY_PRESSURE_ENABLED'
            }
        ]
    
    def modify_cpuset_file(self, force: bool = False) -> CpusetModificationResult:
        """
        Modify cpuset.c to add Docker-compatible cpuset prefixes.
        
        Args:
            force: Force modification even if already modified
            
        Returns:
            CpusetModificationResult object
        """
        if not self.cpuset_file.exists():
            return CpusetModificationResult(
                status=CpusetModificationStatus.FILE_NOT_FOUND,
                message=f"Cpuset file not found: {self.cpuset_file}"
            )
        
        # Check if already modified
        if not force and self._is_already_modified():
            return CpusetModificationResult(
                status=CpusetModificationStatus.ALREADY_MODIFIED,
                message="Cpuset file already contains Docker-compatible entries"
            )
        
        # Create backup
        backup_file = self._create_backup()
        if not backup_file:
            return CpusetModificationResult(
                status=CpusetModificationStatus.BACKUP_FAILED,
                message="Failed to create backup of cpuset.c"
            )
        
        try:
            # Read current file content
            with open(self.cpuset_file, 'r') as f:
                content = f.read()
            
            # Find the insertion point (end of files[] array before terminator)
            modified_content, added_entries = self._insert_cpuset_entries(content)
            
            if not modified_content:
                return CpusetModificationResult(
                    status=CpusetModificationStatus.FAILED,
                    message="Failed to find insertion point in cpuset.c"
                )
            
            # Write modified content
            with open(self.cpuset_file, 'w') as f:
                f.write(modified_content)
            
            # Verify modification
            if not self._verify_modification():
                return CpusetModificationResult(
                    status=CpusetModificationStatus.VERIFICATION_FAILED,
                    message="Modification verification failed"
                )
            
            self.logger.info(f"Successfully modified cpuset.c with {len(added_entries)} entries")
            
            return CpusetModificationResult(
                status=CpusetModificationStatus.SUCCESS,
                message=f"Successfully added {len(added_entries)} cpuset entries",
                backup_file=str(backup_file),
                modified_lines=len(modified_content.split('\n')) - len(content.split('\n')),
                added_entries=added_entries
            )
            
        except Exception as e:
            # Restore from backup on error
            if backup_file and backup_file.exists():
                shutil.copy2(backup_file, self.cpuset_file)
            
            return CpusetModificationResult(
                status=CpusetModificationStatus.FAILED,
                message=f"Modification failed: {str(e)}"
            )
    
    def restore_original(self) -> CpusetModificationResult:
        """
        Restore cpuset.c to its original state from backup.
        
        Returns:
            CpusetModificationResult object
        """
        # Find the most recent backup
        backup_files = list(self.backup_dir.glob("cpuset.c_*.backup"))
        
        if not backup_files:
            return CpusetModificationResult(
                status=CpusetModificationStatus.FAILED,
                message="No backup files found"
            )
        
        # Use the most recent backup
        latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
        
        try:
            shutil.copy2(latest_backup, self.cpuset_file)
            
            return CpusetModificationResult(
                status=CpusetModificationStatus.SUCCESS,
                message=f"Restored cpuset.c from backup: {latest_backup.name}",
                backup_file=str(latest_backup)
            )
            
        except Exception as e:
            return CpusetModificationResult(
                status=CpusetModificationStatus.FAILED,
                message=f"Restore failed: {str(e)}"
            )
    
    def verify_cpuset_compatibility(self) -> Tuple[bool, List[str]]:
        """
        Verify that cpuset.c contains all Docker-required entries.
        
        Returns:
            Tuple of (is_compatible, missing_entries)
        """
        if not self.cpuset_file.exists():
            return False, ["cpuset.c file not found"]
        
        try:
            with open(self.cpuset_file, 'r') as f:
                content = f.read()
            
            missing_entries = []
            
            for entry in self.required_cpuset_entries:
                entry_name = entry['name']
                if f'"{entry_name}"' not in content:
                    missing_entries.append(entry_name)
            
            is_compatible = len(missing_entries) == 0
            
            return is_compatible, missing_entries
            
        except Exception as e:
            self.logger.error(f"Error verifying cpuset compatibility: {e}")
            return False, [f"Verification error: {str(e)}"]
    
    def _is_already_modified(self) -> bool:
        """Check if cpuset.c is already modified with Docker entries."""
        try:
            with open(self.cpuset_file, 'r') as f:
                content = f.read()
            
            # Check for presence of key Docker cpuset entries
            docker_indicators = [
                '"cpuset.cpus"',
                '"cpuset.mems"',
                '"cpuset.effective_cpus"',
                '"cpuset.cpu_exclusive"'
            ]
            
            return all(indicator in content for indicator in docker_indicators)
            
        except Exception as e:
            self.logger.error(f"Error checking if cpuset.c is modified: {e}")
            return False
    
    def _create_backup(self) -> Optional[Path]:
        """Create backup of cpuset.c file."""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"cpuset.c_{timestamp}.backup"
            
            shutil.copy2(self.cpuset_file, backup_file)
            self.logger.info(f"Created backup: {backup_file}")
            
            return backup_file
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return None
    
    def _insert_cpuset_entries(self, content: str) -> Tuple[Optional[str], List[str]]:
        """
        Insert cpuset entries into the files[] array.
        
        Args:
            content: Original file content
            
        Returns:
            Tuple of (modified_content, added_entries)
        """
        try:
            # Find the files[] array and the terminator
            # Look for the pattern: },\n\t{ }\t/* terminate */
            terminator_pattern = r'(\},\s*\n\s*\{\s*\}\s*/\*\s*terminate\s*\*/)'
            
            match = re.search(terminator_pattern, content)
            if not match:
                self.logger.error("Could not find terminator pattern in cpuset.c")
                return None, []
            
            # Insert point is before the terminator
            insert_point = match.start()
            
            # Generate the cpuset entries
            entries_code = self._generate_cpuset_entries()
            
            # Insert the entries
            modified_content = (
                content[:insert_point] +
                entries_code +
                content[insert_point:]
            )
            
            added_entries = [entry['name'] for entry in self.required_cpuset_entries]
            
            return modified_content, added_entries
            
        except Exception as e:
            self.logger.error(f"Error inserting cpuset entries: {e}")
            return None, []
    
    def _generate_cpuset_entries(self) -> str:
        """Generate C code for cpuset entries."""
        entries = []
        
        for entry in self.required_cpuset_entries:
            entry_code = "\t{\n"
            entry_code += f'\t\t.name = "{entry["name"]}",\n'
            
            # Add function pointers based on entry configuration
            if 'seq_show' in entry:
                entry_code += f'\t\t.seq_show = {entry["seq_show"]},\n'
            
            if 'read_u64' in entry:
                entry_code += f'\t\t.read_u64 = {entry["read_u64"]},\n'
            
            if 'read_s64' in entry:
                entry_code += f'\t\t.read_s64 = {entry["read_s64"]},\n'
            
            if 'write' in entry:
                entry_code += f'\t\t.write = {entry["write"]},\n'
            
            if 'write_u64' in entry:
                entry_code += f'\t\t.write_u64 = {entry["write_u64"]},\n'
            
            if 'write_s64' in entry:
                entry_code += f'\t\t.write_s64 = {entry["write_s64"]},\n'
            
            if 'max_write_len' in entry:
                entry_code += f'\t\t.max_write_len = {entry["max_write_len"]},\n'
            
            if 'flags' in entry:
                entry_code += f'\t\t.flags = {entry["flags"]},\n'
            
            entry_code += f'\t\t.private = {entry["private"]},\n'
            entry_code += "\t},\n"
            
            entries.append(entry_code)
        
        return "\n".join(entries) + "\n"
    
    def _verify_modification(self) -> bool:
        """Verify that the modification was successful."""
        try:
            is_compatible, missing_entries = self.verify_cpuset_compatibility()
            
            if not is_compatible:
                self.logger.error(f"Verification failed, missing entries: {missing_entries}")
                return False
            
            # Additional syntax check - try to compile-check the file structure
            with open(self.cpuset_file, 'r') as f:
                content = f.read()
            
            # Basic syntax checks
            if content.count('{') != content.count('}'):
                self.logger.error("Brace mismatch in modified file")
                return False
            
            # Check for proper terminator
            if '{ }\t/* terminate */' not in content and '{ } /* terminate */' not in content:
                self.logger.error("Terminator not found in modified file")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Verification error: {e}")
            return False
    
    def get_modification_status(self) -> Dict[str, any]:
        """
        Get current modification status and information.
        
        Returns:
            Dictionary with status information
        """
        status = {
            'file_exists': self.cpuset_file.exists(),
            'is_modified': False,
            'is_compatible': False,
            'missing_entries': [],
            'backup_files': [],
            'file_size': 0,
            'last_modified': None
        }
        
        if status['file_exists']:
            try:
                stat = self.cpuset_file.stat()
                status['file_size'] = stat.st_size
                status['last_modified'] = stat.st_mtime
                
                status['is_modified'] = self._is_already_modified()
                status['is_compatible'], status['missing_entries'] = self.verify_cpuset_compatibility()
                
                # List backup files
                backup_files = list(self.backup_dir.glob("cpuset.c_*.backup"))
                status['backup_files'] = [f.name for f in backup_files]
                
            except Exception as e:
                self.logger.error(f"Error getting modification status: {e}")
        
        return status