#!/usr/bin/env python3
"""
Tests for the patch application engine.
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kernel_build.patch.patch_engine import PatchEngine, PatchStatus, PatchResult
from kernel_build.patch.patch_verifier import PatchVerifier, VerificationStatus
from kernel_build.patch.patch_rollback import PatchRollback, RollbackStatus


class TestPatchEngine(unittest.TestCase):
    """Test cases for PatchEngine class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.backup_dir = Path(self.test_dir) / "backups"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        
        # Create test files
        self.test_file = self.kernel_source / "test_file.c"
        self.test_file.write_text("original content\n")
        
        # Create test patch
        self.patch_file = Path(self.test_dir) / "test.patch"
        self.patch_file.write_text("""
diff --git a/test_file.c b/test_file.c
index 1234567..abcdefg 100644
--- a/test_file.c
+++ b/test_file.c
@@ -1 +1,2 @@
 original content
+new line
""")
        
        self.engine = PatchEngine(str(self.kernel_source), str(self.backup_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_patch_engine_initialization(self):
        """Test patch engine initialization."""
        self.assertEqual(self.engine.kernel_source_path, self.kernel_source)
        self.assertEqual(self.engine.backup_dir, self.backup_dir)
        self.assertTrue(self.engine.backup_dir.exists())
    
    def test_extract_applied_files(self):
        """Test extraction of applied files from patch."""
        applied_files = self.engine._extract_applied_files(str(self.patch_file))
        self.assertIn("test_file.c", applied_files)
    
    def test_is_patch_applied_false(self):
        """Test checking if patch is applied when it's not."""
        self.assertFalse(self.engine._is_patch_applied(str(self.patch_file)))
    
    def test_create_backup(self):
        """Test backup creation."""
        success = self.engine._create_backup(str(self.patch_file))
        self.assertTrue(success)
        
        # Check if backup was created
        backup_subdir = self.backup_dir / "test_backup"
        self.assertTrue(backup_subdir.exists())
    
    @patch('subprocess.run')
    def test_apply_single_patch_success(self, mock_run):
        """Test successful patch application."""
        # Mock successful patch command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = self.engine.apply_single_patch(str(self.patch_file))
        
        self.assertEqual(result.status, PatchStatus.SUCCESS)
        self.assertEqual(result.patch_file, str(self.patch_file))
        self.assertIn("test_file.c", result.applied_files)
    
    @patch('subprocess.run')
    def test_apply_single_patch_conflict(self, mock_run):
        """Test patch application with conflicts."""
        # Mock patch command with conflicts
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "FAILED: test_file.c rejected"
        mock_run.return_value = mock_result
        
        result = self.engine.apply_single_patch(str(self.patch_file))
        
        self.assertEqual(result.status, PatchStatus.CONFLICT)
        self.assertIn("FAILED", result.conflicts)
    
    def test_apply_nonexistent_patch(self):
        """Test applying non-existent patch file."""
        result = self.engine.apply_single_patch("nonexistent.patch")
        
        self.assertEqual(result.status, PatchStatus.FAILED)
        self.assertIn("not found", result.message)
    
    def test_get_applied_patches_empty(self):
        """Test getting applied patches when none are applied."""
        applied = self.engine.get_applied_patches()
        self.assertEqual(applied, [])


class TestPatchVerifier(unittest.TestCase):
    """Test cases for PatchVerifier class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.verification_dir = Path(self.test_dir) / "verification"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        self.verification_dir.mkdir(parents=True)
        
        # Create test files
        self.test_file = self.kernel_source / "test_file.c"
        self.test_file.write_text("test content\n")
        
        # Create test patch
        self.patch_file = Path(self.test_dir) / "test.patch"
        self.patch_file.write_text("""
diff --git a/test_file.c b/test_file.c
index 1234567..abcdefg 100644
--- a/test_file.c
+++ b/test_file.c
@@ -1 +1,2 @@
 test content
+new line
""")
        
        self.verifier = PatchVerifier(str(self.kernel_source), str(self.verification_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_verifier_initialization(self):
        """Test verifier initialization."""
        self.assertEqual(self.verifier.kernel_source_path, self.kernel_source)
        self.assertEqual(self.verifier.verification_data_dir, self.verification_dir)
        self.assertTrue(self.verifier.verification_data_dir.exists())
    
    def test_extract_modified_files(self):
        """Test extraction of modified files from patch."""
        modified_files = self.verifier._extract_modified_files(str(self.patch_file))
        self.assertIn("test_file.c", modified_files)
    
    def test_verify_patch_integrity_valid(self):
        """Test patch integrity verification for valid patch."""
        result = self.verifier.verify_patch_integrity(str(self.patch_file))
        self.assertTrue(result)
    
    def test_verify_patch_integrity_invalid(self):
        """Test patch integrity verification for invalid patch."""
        invalid_patch = Path(self.test_dir) / "invalid.patch"
        invalid_patch.write_text("not a patch file")
        
        result = self.verifier.verify_patch_integrity(str(invalid_patch))
        self.assertFalse(result)
    
    def test_verify_patch_application_success(self):
        """Test successful patch application verification."""
        result = self.verifier.verify_patch_application(str(self.patch_file))
        
        # Should verify successfully since test_file.c exists
        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertIn("test_file.c", result.verified_files)
    
    def test_verify_patch_application_missing_files(self):
        """Test patch verification with missing files."""
        # Remove the test file
        self.test_file.unlink()
        
        result = self.verifier.verify_patch_application(str(self.patch_file))
        
        self.assertEqual(result.status, VerificationStatus.MISSING_FILES)
        self.assertIn("test_file.c", result.missing_files)
    
    def test_create_verification_baseline(self):
        """Test creation of verification baseline."""
        success = self.verifier.create_verification_baseline(str(self.patch_file))
        self.assertTrue(success)
        
        # Check if baseline file was created
        baseline_file = self.verification_dir / "test_baseline.json"
        self.assertTrue(baseline_file.exists())


class TestPatchRollback(unittest.TestCase):
    """Test cases for PatchRollback class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.backup_dir = Path(self.test_dir) / "backups"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        
        # Create test files
        self.test_file = self.kernel_source / "test_file.c"
        self.test_file.write_text("original content\n")
        
        # Create applied patches log
        applied_patches_file = self.backup_dir / "applied_patches.log"
        applied_patches_file.write_text("test.patch test_file.c\n")
        
        self.rollback = PatchRollback(str(self.kernel_source), str(self.backup_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_rollback_initialization(self):
        """Test rollback system initialization."""
        self.assertEqual(self.rollback.kernel_source_path, self.kernel_source)
        self.assertEqual(self.rollback.backup_dir, self.backup_dir)
        self.assertTrue(self.rollback.backup_dir.exists())
    
    def test_get_applied_patches(self):
        """Test getting list of applied patches."""
        applied = self.rollback._get_applied_patches()
        self.assertIn("test.patch", applied)
    
    def test_is_patch_applied_true(self):
        """Test checking if patch is applied when it is."""
        self.assertTrue(self.rollback._is_patch_applied("test.patch"))
    
    def test_is_patch_applied_false(self):
        """Test checking if patch is applied when it's not."""
        self.assertFalse(self.rollback._is_patch_applied("nonexistent.patch"))
    
    def test_create_snapshot(self):
        """Test snapshot creation."""
        success = self.rollback.create_snapshot("test_snapshot")
        self.assertTrue(success)
        
        # Check if snapshot was created
        snapshot_dir = self.backup_dir / "snapshots" / "test_snapshot"
        self.assertTrue(snapshot_dir.exists())
    
    def test_list_snapshots_empty(self):
        """Test listing snapshots when none exist."""
        snapshots = self.rollback.list_snapshots()
        self.assertEqual(snapshots, [])
    
    def test_list_snapshots_with_snapshots(self):
        """Test listing snapshots when they exist."""
        # Create a test snapshot
        snapshot_dir = self.backup_dir / "snapshots" / "test_snapshot"
        snapshot_dir.mkdir(parents=True)
        
        snapshots = self.rollback.list_snapshots()
        self.assertIn("test_snapshot", snapshots)
    
    def test_rollback_patch_not_applied(self):
        """Test rolling back patch that's not applied."""
        result = self.rollback.rollback_patch("nonexistent.patch")
        
        self.assertEqual(result.status, RollbackStatus.ALREADY_CLEAN)
        self.assertIn("not applied", result.message)


class TestPatchIntegration(unittest.TestCase):
    """Integration tests for patch system components."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.kernel_source = Path(self.test_dir) / "kernel_source"
        self.backup_dir = Path(self.test_dir) / "backups"
        
        # Create test directories
        self.kernel_source.mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        
        # Create test files
        self.test_file = self.kernel_source / "test_file.c"
        self.test_file.write_text("original content\n")
        
        # Create test patch
        self.patch_file = Path(self.test_dir) / "test.patch"
        self.patch_file.write_text("""
diff --git a/test_file.c b/test_file.c
index 1234567..abcdefg 100644
--- a/test_file.c
+++ b/test_file.c
@@ -1 +1,2 @@
 original content
+new line
""")
        
        self.engine = PatchEngine(str(self.kernel_source), str(self.backup_dir))
        self.verifier = PatchVerifier(str(self.kernel_source))
        self.rollback = PatchRollback(str(self.kernel_source), str(self.backup_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_patch_workflow_integration(self):
        """Test complete patch workflow integration."""
        # 1. Verify patch integrity
        self.assertTrue(self.verifier.verify_patch_integrity(str(self.patch_file)))
        
        # 2. Apply patch (dry run first)
        results = self.engine.apply_patches([str(self.patch_file)], dry_run=True)
        self.assertEqual(len(results), 1)
        
        # 3. Check that no patches are applied yet
        applied = self.engine.get_applied_patches()
        self.assertEqual(len(applied), 0)
        
        # 4. Create snapshot before applying
        self.assertTrue(self.rollback.create_snapshot("before_patch"))
        
        # 5. List snapshots
        snapshots = self.rollback.list_snapshots()
        self.assertIn("before_patch", snapshots)


if __name__ == '__main__':
    unittest.main()