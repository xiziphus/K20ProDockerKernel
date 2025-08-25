#!/usr/bin/env python3
"""
Tests for the cpuset modification handler.
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kernel_build.patch.cpuset_handler import CpusetHandler, CpusetModificationStatus


class TestCpusetHandler(unittest.TestCase):
    """Test cases for CpusetHandler class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.backup_dir = Path(self.test_dir) / "backups"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        (self.kernel_source / "kernel" / "cgroup").mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        
        # Create test cpuset.c file
        self.cpuset_file = self.kernel_source / "kernel" / "cgroup" / "cpuset.c"
        self.cpuset_file.write_text(self._get_original_cpuset_content())
        
        self.handler = CpusetHandler(str(self.kernel_source), str(self.backup_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _get_original_cpuset_content(self):
        """Get original cpuset.c content for testing."""
        return """
static struct cftype files[] = {
    {
        .name = "cpus",
        .seq_show = cpuset_common_seq_show,
        .write = cpuset_write_resmask,
        .max_write_len = (100U + 6 * NR_CPUS),
        .private = FILE_CPULIST,
    },
    {
        .name = "memory_pressure_enabled",
        .flags = CFTYPE_ONLY_ON_ROOT,
        .read_u64 = cpuset_read_u64,
        .write_u64 = cpuset_write_u64,
        .private = FILE_MEMORY_PRESSURE_ENABLED,
    },

    { }	/* terminate */
};
"""
    
    def _get_modified_cpuset_content(self):
        """Get modified cpuset.c content for testing."""
        return """
static struct cftype files[] = {
    {
        .name = "cpus",
        .seq_show = cpuset_common_seq_show,
        .write = cpuset_write_resmask,
        .max_write_len = (100U + 6 * NR_CPUS),
        .private = FILE_CPULIST,
    },
    {
        .name = "memory_pressure_enabled",
        .flags = CFTYPE_ONLY_ON_ROOT,
        .read_u64 = cpuset_read_u64,
        .write_u64 = cpuset_write_u64,
        .private = FILE_MEMORY_PRESSURE_ENABLED,
    },
    {
        .name = "cpuset.cpus",
        .seq_show = cpuset_common_seq_show,
        .write = cpuset_write_resmask_wrapper,
        .max_write_len = (100U + 6 * NR_CPUS),
        .private = FILE_CPULIST,
    },
    {
        .name = "cpuset.mems",
        .seq_show = cpuset_common_seq_show,
        .write = cpuset_write_resmask,
        .max_write_len = (100U + 6 * MAX_NUMNODES),
        .private = FILE_MEMLIST,
    },

    { }	/* terminate */
};
"""
    
    def test_handler_initialization(self):
        """Test cpuset handler initialization."""
        self.assertEqual(self.handler.kernel_source_path, self.kernel_source)
        self.assertEqual(self.handler.backup_dir, self.backup_dir)
        self.assertTrue(self.handler.backup_dir.exists())
        self.assertEqual(self.handler.cpuset_file, self.cpuset_file)
    
    def test_cpuset_file_exists(self):
        """Test that cpuset.c file exists."""
        self.assertTrue(self.handler.cpuset_file.exists())
    
    def test_is_already_modified_false(self):
        """Test checking if cpuset.c is modified when it's not."""
        self.assertFalse(self.handler._is_already_modified())
    
    def test_is_already_modified_true(self):
        """Test checking if cpuset.c is modified when it is."""
        # Write modified content
        self.cpuset_file.write_text(self._get_modified_cpuset_content())
        self.assertTrue(self.handler._is_already_modified())
    
    def test_verify_cpuset_compatibility_false(self):
        """Test compatibility verification when not compatible."""
        is_compatible, missing_entries = self.handler.verify_cpuset_compatibility()
        
        self.assertFalse(is_compatible)
        self.assertGreater(len(missing_entries), 0)
        self.assertIn("cpuset.cpus", missing_entries)
    
    def test_verify_cpuset_compatibility_true(self):
        """Test compatibility verification when compatible."""
        # Write modified content with all required entries
        modified_content = self._get_modified_cpuset_content()
        
        # Add all required entries for full compatibility
        for entry in self.handler.required_cpuset_entries:
            if f'"{entry["name"]}"' not in modified_content:
                # Add a basic entry structure
                entry_code = f'''    {{
        .name = "{entry['name']}",
        .private = {entry['private']},
    }},
'''
                # Insert before terminator
                modified_content = modified_content.replace(
                    '    { }\t/* terminate */',
                    entry_code + '    { }\t/* terminate */'
                )
        
        self.cpuset_file.write_text(modified_content)
        
        is_compatible, missing_entries = self.handler.verify_cpuset_compatibility()
        
        self.assertTrue(is_compatible)
        self.assertEqual(len(missing_entries), 0)
    
    def test_create_backup(self):
        """Test backup creation."""
        backup_file = self.handler._create_backup()
        
        self.assertIsNotNone(backup_file)
        self.assertTrue(backup_file.exists())
        self.assertTrue(backup_file.name.startswith("cpuset.c_"))
        self.assertTrue(backup_file.name.endswith(".backup"))
    
    def test_generate_cpuset_entries(self):
        """Test generation of cpuset entries code."""
        entries_code = self.handler._generate_cpuset_entries()
        
        self.assertIn('"cpuset.cpus"', entries_code)
        self.assertIn('"cpuset.mems"', entries_code)
        self.assertIn('cpuset_common_seq_show', entries_code)
        self.assertIn('FILE_CPULIST', entries_code)
    
    def test_insert_cpuset_entries(self):
        """Test insertion of cpuset entries into file content."""
        original_content = self._get_original_cpuset_content()
        
        modified_content, added_entries = self.handler._insert_cpuset_entries(original_content)
        
        self.assertIsNotNone(modified_content)
        self.assertGreater(len(added_entries), 0)
        self.assertIn("cpuset.cpus", added_entries)
        self.assertIn('"cpuset.cpus"', modified_content)
        self.assertIn('{ }\t/* terminate */', modified_content)
    
    def test_modify_cpuset_file_success(self):
        """Test successful cpuset.c modification."""
        result = self.handler.modify_cpuset_file()
        
        self.assertEqual(result.status, CpusetModificationStatus.SUCCESS)
        self.assertIsNotNone(result.backup_file)
        self.assertGreater(len(result.added_entries), 0)
        self.assertGreater(result.modified_lines, 0)
        
        # Verify file was actually modified
        self.assertTrue(self.handler._is_already_modified())
    
    def test_modify_cpuset_file_already_modified(self):
        """Test modification when file is already modified."""
        # First modification
        result1 = self.handler.modify_cpuset_file()
        self.assertEqual(result1.status, CpusetModificationStatus.SUCCESS)
        
        # Second modification without force
        result2 = self.handler.modify_cpuset_file()
        self.assertEqual(result2.status, CpusetModificationStatus.ALREADY_MODIFIED)
    
    def test_modify_cpuset_file_force(self):
        """Test forced modification when file is already modified."""
        # First modification
        result1 = self.handler.modify_cpuset_file()
        self.assertEqual(result1.status, CpusetModificationStatus.SUCCESS)
        
        # Forced modification
        result2 = self.handler.modify_cpuset_file(force=True)
        self.assertEqual(result2.status, CpusetModificationStatus.SUCCESS)
    
    def test_modify_cpuset_file_not_found(self):
        """Test modification when cpuset.c file doesn't exist."""
        # Remove the file
        self.cpuset_file.unlink()
        
        result = self.handler.modify_cpuset_file()
        
        self.assertEqual(result.status, CpusetModificationStatus.FILE_NOT_FOUND)
        self.assertIn("not found", result.message)
    
    def test_restore_original_success(self):
        """Test successful restoration from backup."""
        # First modify the file
        result1 = self.handler.modify_cpuset_file()
        self.assertEqual(result1.status, CpusetModificationStatus.SUCCESS)
        
        # Verify it's modified
        self.assertTrue(self.handler._is_already_modified())
        
        # Restore original
        result2 = self.handler.restore_original()
        self.assertEqual(result2.status, CpusetModificationStatus.SUCCESS)
        
        # Verify it's restored
        self.assertFalse(self.handler._is_already_modified())
    
    def test_restore_original_no_backup(self):
        """Test restoration when no backup exists."""
        result = self.handler.restore_original()
        
        self.assertEqual(result.status, CpusetModificationStatus.FAILED)
        self.assertIn("No backup files found", result.message)
    
    def test_get_modification_status(self):
        """Test getting modification status."""
        status = self.handler.get_modification_status()
        
        self.assertTrue(status['file_exists'])
        self.assertFalse(status['is_modified'])
        self.assertFalse(status['is_compatible'])
        self.assertGreater(len(status['missing_entries']), 0)
        self.assertEqual(len(status['backup_files']), 0)
        self.assertGreater(status['file_size'], 0)
        self.assertIsNotNone(status['last_modified'])
    
    def test_get_modification_status_after_modification(self):
        """Test getting modification status after modification."""
        # Modify the file
        result = self.handler.modify_cpuset_file()
        self.assertEqual(result.status, CpusetModificationStatus.SUCCESS)
        
        # Get status
        status = self.handler.get_modification_status()
        
        self.assertTrue(status['file_exists'])
        self.assertTrue(status['is_modified'])
        self.assertTrue(status['is_compatible'])
        self.assertEqual(len(status['missing_entries']), 0)
        self.assertGreater(len(status['backup_files']), 0)
    
    def test_verify_modification(self):
        """Test modification verification."""
        # Modify the file
        result = self.handler.modify_cpuset_file()
        self.assertEqual(result.status, CpusetModificationStatus.SUCCESS)
        
        # Verify modification
        self.assertTrue(self.handler._verify_modification())


class TestCpusetHandlerEdgeCases(unittest.TestCase):
    """Test edge cases for CpusetHandler."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.backup_dir = Path(self.test_dir) / "backups"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        (self.kernel_source / "kernel" / "cgroup").mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_malformed_cpuset_file(self):
        """Test handling of malformed cpuset.c file."""
        cpuset_file = self.kernel_source / "kernel" / "cgroup" / "cpuset.c"
        cpuset_file.write_text("malformed content without proper structure")
        
        handler = CpusetHandler(str(self.kernel_source), str(self.backup_dir))
        
        result = handler.modify_cpuset_file()
        
        self.assertEqual(result.status, CpusetModificationStatus.FAILED)
    
    def test_empty_cpuset_file(self):
        """Test handling of empty cpuset.c file."""
        cpuset_file = self.kernel_source / "kernel" / "cgroup" / "cpuset.c"
        cpuset_file.write_text("")
        
        handler = CpusetHandler(str(self.kernel_source), str(self.backup_dir))
        
        result = handler.modify_cpuset_file()
        
        self.assertEqual(result.status, CpusetModificationStatus.FAILED)
    
    def test_permission_error(self):
        """Test handling of permission errors."""
        cpuset_file = self.kernel_source / "kernel" / "cgroup" / "cpuset.c"
        cpuset_file.write_text("test content")
        
        handler = CpusetHandler(str(self.kernel_source), str(self.backup_dir))
        
        # Make file read-only
        cpuset_file.chmod(0o444)
        
        try:
            result = handler.modify_cpuset_file()
            # Should fail due to permission error
            self.assertEqual(result.status, CpusetModificationStatus.FAILED)
        finally:
            # Restore permissions for cleanup
            cpuset_file.chmod(0o644)


if __name__ == '__main__':
    unittest.main()