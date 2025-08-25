#!/usr/bin/env python3
"""
Tests for Migration Orchestrator.

This module contains unit tests for the cross-architecture migration system.
"""

import os
import json
import tempfile
import unittest
import subprocess
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.migration_orchestrator import (
    MigrationOrchestrator, 
    MigrationConfig, 
    MigrationStatus,
    CompatibilityCheck
)


class TestMigrationOrchestrator(unittest.TestCase):
    """Test cases for MigrationOrchestrator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = MigrationOrchestrator(self.temp_dir)
        
        # Sample migration config
        self.config = MigrationConfig(
            container_id="test_container",
            source_host="localhost",
            target_host="adb:test_device",
            source_arch="x86_64",
            target_arch="aarch64"
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_validate_migration_prerequisites_success(self, mock_run):
        """Test successful prerequisites validation."""
        # Mock container inspect
        container_info = {
            "State": {"Status": "running"},
            "Config": {},
            "HostConfig": {}
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([container_info]), stderr=""),  # docker inspect
            Mock(returncode=0, stdout="test", stderr="")  # adb connectivity test
        ]
        
        # Mock CRIU environment configuration
        with patch.object(self.orchestrator.criu_manager, 'configure_criu_environment', return_value=True):
            is_valid, errors = self.orchestrator.validate_migration_prerequisites(self.config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    @patch('subprocess.run')
    def test_validate_migration_prerequisites_container_not_found(self, mock_run):
        """Test prerequisites validation with missing container."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="No such container")
        
        is_valid, errors = self.orchestrator.validate_migration_prerequisites(self.config)
        
        self.assertFalse(is_valid)
        self.assertIn("not found", errors[0])
    
    @patch('subprocess.run')
    def test_validate_migration_prerequisites_container_not_running(self, mock_run):
        """Test prerequisites validation with stopped container."""
        container_info = {
            "State": {"Status": "exited"},
            "Config": {},
            "HostConfig": {}
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([container_info]), stderr=""),  # docker inspect
            Mock(returncode=0, stdout="test", stderr="")  # adb connectivity test
        ]
        
        with patch.object(self.orchestrator.criu_manager, 'configure_criu_environment', return_value=True):
            is_valid, errors = self.orchestrator.validate_migration_prerequisites(self.config)
        
        self.assertFalse(is_valid)
        self.assertIn("not running", errors[0])
    
    @patch('subprocess.run')
    def test_validate_migration_prerequisites_target_unreachable(self, mock_run):
        """Test prerequisites validation with unreachable target."""
        container_info = {
            "State": {"Status": "running"},
            "Config": {},
            "HostConfig": {}
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([container_info]), stderr=""),  # docker inspect
            Mock(returncode=1, stdout="", stderr="device not found")  # adb connectivity test
        ]
        
        with patch.object(self.orchestrator.criu_manager, 'configure_criu_environment', return_value=True):
            is_valid, errors = self.orchestrator.validate_migration_prerequisites(self.config)
        
        self.assertFalse(is_valid)
        self.assertIn("Cannot connect to target device", errors[0])
    
    @patch('subprocess.run')
    def test_check_container_compatibility_success(self, mock_run):
        """Test successful container compatibility check."""
        container_info = {
            "Config": {
                "Architecture": "amd64"
            },
            "HostConfig": {
                "Privileged": False,
                "NetworkMode": "bridge",
                "Devices": [],
                "Binds": [],
                "CapAdd": []
            }
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([container_info]),
            stderr=""
        )
        
        compatibility = self.orchestrator.check_container_compatibility("test_container")
        
        self.assertTrue(compatibility.is_compatible)
        self.assertTrue(compatibility.architecture_compatible)
        self.assertTrue(compatibility.kernel_compatible)
        self.assertTrue(compatibility.runtime_compatible)
        self.assertEqual(len(compatibility.issues), 0)
    
    @patch('subprocess.run')
    def test_check_container_compatibility_with_issues(self, mock_run):
        """Test container compatibility check with issues."""
        container_info = {
            "Config": {
                "Architecture": "amd64"
            },
            "HostConfig": {
                "Privileged": True,
                "NetworkMode": "host",
                "Devices": [{"PathOnHost": "/dev/test"}],
                "Binds": ["/host:/container"],
                "CapAdd": ["SYS_ADMIN"]
            }
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([container_info]),
            stderr=""
        )
        
        compatibility = self.orchestrator.check_container_compatibility("test_container")
        
        self.assertFalse(compatibility.is_compatible)
        self.assertTrue(compatibility.architecture_compatible)
        self.assertFalse(compatibility.kernel_compatible)  # Privileged mode
        self.assertFalse(compatibility.runtime_compatible)  # Host networking and devices
        self.assertGreater(len(compatibility.issues), 0)
        self.assertGreater(len(compatibility.recommendations), 0)
    
    @patch('subprocess.run')
    def test_check_container_compatibility_container_not_found(self, mock_run):
        """Test compatibility check with missing container."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="No such container")
        
        compatibility = self.orchestrator.check_container_compatibility("nonexistent")
        
        self.assertFalse(compatibility.is_compatible)
        self.assertFalse(compatibility.architecture_compatible)
        self.assertFalse(compatibility.kernel_compatible)
        self.assertFalse(compatibility.runtime_compatible)
        self.assertIn("not found", compatibility.issues[0])
    
    def test_get_migration_status_not_found(self):
        """Test getting status of non-existent migration."""
        status = self.orchestrator.get_migration_status("nonexistent")
        
        self.assertIsNone(status)
    
    def test_list_active_migrations_empty(self):
        """Test listing migrations when none are active."""
        migrations = self.orchestrator.list_active_migrations()
        
        self.assertEqual(len(migrations), 0)
    
    def test_cancel_migration_not_found(self):
        """Test cancelling non-existent migration."""
        result = self.orchestrator.cancel_migration("nonexistent")
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_validate_migration_success_container_running(self, mock_run):
        """Test migration success validation with running container."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="container_id_123",
            stderr=""
        )
        
        from migration.migration_orchestrator import MigrationResult
        result = MigrationResult(
            success=False,
            status=MigrationStatus.IN_PROGRESS,
            container_id="test_container"
        )
        
        is_valid = self.orchestrator._validate_migration_success(self.config, result)
        
        self.assertTrue(is_valid)
    
    @patch('subprocess.run')
    def test_validate_migration_success_container_not_running(self, mock_run):
        """Test migration success validation with non-running container."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",  # No container ID returned
            stderr=""
        )
        
        from migration.migration_orchestrator import MigrationResult
        result = MigrationResult(
            success=False,
            status=MigrationStatus.IN_PROGRESS,
            container_id="test_container"
        )
        
        is_valid = self.orchestrator._validate_migration_success(self.config, result)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(result.warnings), 0)
    
    @patch('subprocess.run')
    def test_validate_migration_success_ssh_target(self, mock_run):
        """Test migration success validation with SSH target."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="container_id_123",
            stderr=""
        )
        
        ssh_config = MigrationConfig(
            container_id="test_container",
            source_host="localhost",
            target_host="user@remote.host",
            source_arch="x86_64",
            target_arch="aarch64"
        )
        
        from migration.migration_orchestrator import MigrationResult
        result = MigrationResult(
            success=False,
            status=MigrationStatus.IN_PROGRESS,
            container_id="test_container"
        )
        
        is_valid = self.orchestrator._validate_migration_success(ssh_config, result)
        
        self.assertTrue(is_valid)
        # Verify SSH command was used
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("ssh", call_args)
        self.assertIn("user@remote.host", call_args)
    
    def test_rollback_migration_no_checkpoint(self):
        """Test rollback with no checkpoint available."""
        from migration.migration_orchestrator import MigrationResult
        result = MigrationResult(
            success=False,
            status=MigrationStatus.FAILED,
            container_id="test_container",
            source_checkpoint_path=None
        )
        
        self.orchestrator._rollback_migration(self.config, result)
        
        self.assertIn("No checkpoint available", result.warnings[-1])
    
    def test_rollback_migration_with_checkpoint(self):
        """Test rollback with available checkpoint."""
        from migration.migration_orchestrator import MigrationResult, CRIUStatus
        result = MigrationResult(
            success=False,
            status=MigrationStatus.FAILED,
            container_id="test_container",
            source_checkpoint_path="/tmp/test_checkpoint"
        )
        
        # Mock successful restore
        mock_status = CRIUStatus(success=True)
        with patch.object(self.orchestrator.criu_manager, 'restore_checkpoint', return_value=mock_status):
            self.orchestrator._rollback_migration(self.config, result)
        
        self.assertEqual(result.status, MigrationStatus.ROLLED_BACK)
        self.assertIn("rolled back successfully", result.warnings[-1])
    
    def test_rollback_migration_restore_failure(self):
        """Test rollback with restore failure."""
        from migration.migration_orchestrator import MigrationResult, CRIUStatus
        result = MigrationResult(
            success=False,
            status=MigrationStatus.FAILED,
            container_id="test_container",
            source_checkpoint_path="/tmp/test_checkpoint"
        )
        
        # Mock failed restore
        mock_status = CRIUStatus(success=False, error_message="Restore failed")
        with patch.object(self.orchestrator.criu_manager, 'restore_checkpoint', return_value=mock_status):
            self.orchestrator._rollback_migration(self.config, result)
        
        self.assertIn("Rollback failed", result.warnings[-1])


if __name__ == '__main__':
    unittest.main()