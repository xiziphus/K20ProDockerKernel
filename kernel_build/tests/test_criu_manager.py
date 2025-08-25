#!/usr/bin/env python3
"""
Tests for CRIU Manager.

This module contains unit tests for the CRIU integration system.
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

from migration.criu_manager import CRIUManager, CheckpointConfig, CRIUStatus


class TestCRIUManager(unittest.TestCase):
    """Test cases for CRIUManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.criu_binary = os.path.join(self.temp_dir, "criu")
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoints")
        self.manager = CRIUManager(self.criu_binary, checkpoint_dir)
        
        # Create mock CRIU binary
        with open(self.criu_binary, "w") as f:
            f.write("#!/bin/bash\necho 'mock criu'\n")
        os.chmod(self.criu_binary, 0o755)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_configure_criu_environment_success(self, mock_run):
        """Test successful CRIU environment configuration."""
        # Mock successful CRIU check
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="CRIU check passed")
        
        result = self.manager.configure_criu_environment()
        
        self.assertTrue(result)
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_configure_criu_environment_failure(self, mock_run):
        """Test CRIU environment configuration failure."""
        # Mock failed CRIU check
        mock_run.return_value = Mock(returncode=1, stderr="CRIU check failed", stdout="")
        
        result = self.manager.configure_criu_environment()
        
        self.assertFalse(result)
    
    def test_configure_criu_environment_missing_binary(self):
        """Test CRIU configuration with missing binary."""
        manager = CRIUManager("/nonexistent/criu")
        
        result = manager.configure_criu_environment()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_validate_container_for_checkpoint_success(self, mock_run):
        """Test successful container validation."""
        # Mock container inspect response
        container_info = {
            "State": {"Status": "running"},
            "Config": {"ExposedPorts": None},
            "HostConfig": {"Privileged": False, "NetworkMode": "bridge", "Binds": None}
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([container_info]),
            stderr=""
        )
        
        is_valid, warnings = self.manager.validate_container_for_checkpoint("test_container")
        
        self.assertTrue(is_valid)
        self.assertEqual(len(warnings), 0)
    
    @patch('subprocess.run')
    def test_validate_container_for_checkpoint_with_warnings(self, mock_run):
        """Test container validation with warnings."""
        # Mock container inspect response with problematic config
        container_info = {
            "State": {"Status": "running"},
            "Config": {"ExposedPorts": {"80/tcp": {}}},
            "HostConfig": {
                "Privileged": True,
                "NetworkMode": "host",
                "Binds": ["/host:/container"]
            }
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([container_info]),
            stderr=""
        )
        
        is_valid, warnings = self.manager.validate_container_for_checkpoint("test_container")
        
        self.assertTrue(is_valid)
        self.assertGreater(len(warnings), 0)
        self.assertIn("privileged mode", " ".join(warnings).lower())
        self.assertIn("host networking", " ".join(warnings).lower())
        self.assertIn("bind mounts", " ".join(warnings).lower())
        self.assertIn("exposed ports", " ".join(warnings).lower())
    
    @patch('subprocess.run')
    def test_validate_container_not_found(self, mock_run):
        """Test validation of non-existent container."""
        mock_run.return_value = Mock(returncode=1, stderr="No such container", stdout="")
        
        is_valid, warnings = self.manager.validate_container_for_checkpoint("nonexistent")
        
        self.assertFalse(is_valid)
        self.assertIn("not found", warnings[0])
    
    @patch('subprocess.run')
    def test_validate_container_not_running(self, mock_run):
        """Test validation of stopped container."""
        container_info = {
            "State": {"Status": "exited"},
            "Config": {},
            "HostConfig": {}
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([container_info]),
            stderr=""
        )
        
        is_valid, warnings = self.manager.validate_container_for_checkpoint("stopped_container")
        
        self.assertFalse(is_valid)
        self.assertIn("not running", warnings[0])
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_create_checkpoint_success(self, mock_exists, mock_run):
        """Test successful checkpoint creation."""
        # Mock file existence checks
        mock_exists.return_value = True
        
        # Mock container validation
        container_info = {
            "State": {"Status": "running"},
            "Config": {},
            "HostConfig": {"Privileged": False, "NetworkMode": "bridge"}
        }
        
        # Mock subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([container_info]), stderr=""),  # docker inspect
            Mock(returncode=0, stdout="12345", stderr=""),  # get PID
            Mock(returncode=0, stdout="", stderr=""),  # CRIU dump
            Mock(returncode=0, stdout="2023-01-01T12:00:00+00:00", stderr=""),  # date
            Mock(returncode=0, stdout="Linux 5.4.0", stderr=""),  # uname
            Mock(returncode=0, stdout="Docker version 20.10.0", stderr="")  # docker version
        ]
        
        config = CheckpointConfig(
            container_id="test_container",
            checkpoint_dir=self.temp_dir
        )
        
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            result = self.manager.create_checkpoint(config)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.checkpoint_path)
    
    @patch('subprocess.run')
    def test_create_checkpoint_validation_failure(self, mock_run):
        """Test checkpoint creation with validation failure."""
        # Mock container not found
        mock_run.return_value = Mock(returncode=1, stderr="No such container", stdout="")
        
        config = CheckpointConfig(
            container_id="nonexistent",
            checkpoint_dir=self.temp_dir
        )
        
        result = self.manager.create_checkpoint(config)
        
        self.assertFalse(result.success)
        self.assertIn("validation failed", result.error_message.lower())
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_create_checkpoint_criu_failure(self, mock_exists, mock_run):
        """Test checkpoint creation with CRIU failure."""
        mock_exists.return_value = True
        
        # Mock successful validation but failed CRIU dump
        container_info = {
            "State": {"Status": "running"},
            "Config": {},
            "HostConfig": {"Privileged": False}
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([container_info]), stderr=""),  # docker inspect
            Mock(returncode=0, stdout="12345", stderr=""),  # get PID
            Mock(returncode=1, stdout="", stderr="CRIU dump failed")  # CRIU dump failure
        ]
        
        config = CheckpointConfig(
            container_id="test_container",
            checkpoint_dir=self.temp_dir
        )
        
        result = self.manager.create_checkpoint(config)
        
        self.assertFalse(result.success)
        self.assertIn("CRIU dump failed", result.error_message)
    
    def test_validate_checkpoint_missing_directory(self):
        """Test validation of missing checkpoint directory."""
        result = self.manager.validate_checkpoint("/nonexistent/checkpoint")
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error_message)
    
    def test_validate_checkpoint_missing_files(self):
        """Test validation with missing required files."""
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoint")
        os.makedirs(checkpoint_dir)
        
        result = self.manager.validate_checkpoint(checkpoint_dir)
        
        self.assertFalse(result.success)
        self.assertIn("Missing checkpoint files", result.error_message)
    
    def test_validate_checkpoint_success(self):
        """Test successful checkpoint validation."""
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoint")
        os.makedirs(checkpoint_dir)
        
        # Create required files
        metadata = {
            "container_id": "test_container",
            "checkpoint_time": "2023-01-01T12:00:00+00:00",
            "architecture": "arm64"
        }
        
        with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        with open(os.path.join(checkpoint_dir, "dump.log"), "w") as f:
            f.write("Checkpoint completed successfully\n")
        
        result = self.manager.validate_checkpoint(checkpoint_dir)
        
        self.assertTrue(result.success)
        self.assertEqual(result.checkpoint_path, checkpoint_dir)
    
    def test_validate_checkpoint_with_warnings(self):
        """Test checkpoint validation with warnings in log."""
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoint")
        os.makedirs(checkpoint_dir)
        
        # Create required files
        metadata = {
            "container_id": "test_container",
            "checkpoint_time": "2023-01-01T12:00:00+00:00",
            "architecture": "arm64"
        }
        
        with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        with open(os.path.join(checkpoint_dir, "dump.log"), "w") as f:
            f.write("Warning: Some issue detected\nError: Critical problem\n")
        
        result = self.manager.validate_checkpoint(checkpoint_dir)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.warnings), 0)
    
    @patch('subprocess.run')
    def test_restore_checkpoint_success(self, mock_run):
        """Test successful checkpoint restoration."""
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoint")
        os.makedirs(checkpoint_dir)
        
        # Create metadata file
        metadata = {
            "container_id": "test_container",
            "checkpoint_time": "2023-01-01T12:00:00+00:00",
            "architecture": "arm64"
        }
        
        with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        with open(os.path.join(checkpoint_dir, "dump.log"), "w") as f:
            f.write("Checkpoint completed successfully\n")
        
        # Mock successful CRIU restore
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        result = self.manager.restore_checkpoint(checkpoint_dir)
        
        self.assertTrue(result.success)
        self.assertEqual(result.checkpoint_path, checkpoint_dir)
    
    @patch('subprocess.run')
    def test_restore_checkpoint_failure(self, mock_run):
        """Test checkpoint restoration failure."""
        checkpoint_dir = os.path.join(self.temp_dir, "checkpoint")
        os.makedirs(checkpoint_dir)
        
        # Create metadata file
        metadata = {
            "container_id": "test_container",
            "checkpoint_time": "2023-01-01T12:00:00+00:00",
            "architecture": "arm64"
        }
        
        with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        with open(os.path.join(checkpoint_dir, "dump.log"), "w") as f:
            f.write("Checkpoint completed successfully\n")
        
        # Mock failed CRIU restore
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="CRIU restore failed")
        
        result = self.manager.restore_checkpoint(checkpoint_dir)
        
        self.assertFalse(result.success)
        self.assertIn("CRIU restore failed", result.error_message)
    
    def test_list_checkpoints_empty(self):
        """Test listing checkpoints with empty directory."""
        result = self.manager.list_checkpoints()
        
        self.assertEqual(len(result), 0)
    
    def test_list_checkpoints_with_data(self):
        """Test listing checkpoints with existing data."""
        # Create checkpoint directories
        for i in range(2):
            checkpoint_dir = os.path.join(self.manager.checkpoint_base_dir, f"container_{i}")
            os.makedirs(checkpoint_dir)
            
            metadata = {
                "container_id": f"container_{i}",
                "checkpoint_time": f"2023-01-0{i+1}T12:00:00+00:00",
                "architecture": "arm64"
            }
            
            with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
                json.dump(metadata, f)
        
        result = self.manager.list_checkpoints()
        
        self.assertEqual(len(result), 2)
        self.assertTrue(all("container_id" in checkpoint for checkpoint in result))
    
    @patch('subprocess.run')
    def test_cleanup_checkpoint_success(self, mock_run):
        """Test successful checkpoint cleanup."""
        checkpoint_dir = os.path.join(self.temp_dir, "test_checkpoint")
        os.makedirs(checkpoint_dir)
        
        mock_run.return_value = Mock(returncode=0)
        
        result = self.manager.cleanup_checkpoint(checkpoint_dir)
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(["rm", "-rf", checkpoint_dir], check=True)
    
    @patch('subprocess.run')
    def test_cleanup_checkpoint_failure(self, mock_run):
        """Test checkpoint cleanup failure."""
        checkpoint_dir = os.path.join(self.temp_dir, "test_checkpoint")
        os.makedirs(checkpoint_dir)  # Create the directory so it exists
        
        mock_run.side_effect = subprocess.CalledProcessError(1, ["rm"])
        
        result = self.manager.cleanup_checkpoint(checkpoint_dir)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()