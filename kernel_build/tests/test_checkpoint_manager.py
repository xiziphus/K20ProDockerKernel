#!/usr/bin/env python3
"""
Tests for Checkpoint Manager.

This module contains unit tests for the checkpoint data management system.
"""

import os
import json
import tempfile
import tarfile
import unittest
from unittest.mock import Mock, patch
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.checkpoint_manager import CheckpointManager, TransferConfig, CheckpointPackage


class TestCheckpointManager(unittest.TestCase):
    """Test cases for CheckpointManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(self.temp_dir)
        
        # Create sample checkpoint directory
        self.checkpoint_dir = os.path.join(self.temp_dir, "test_checkpoint")
        os.makedirs(self.checkpoint_dir)
        
        # Create sample metadata
        self.metadata = {
            "container_id": "test_container",
            "checkpoint_time": "2023-01-01T12:00:00+00:00",
            "architecture": "arm64",
            "kernel_version": "5.4.0",
            "docker_version": "Docker version 20.10.0"
        }
        
        with open(os.path.join(self.checkpoint_dir, "metadata.json"), "w") as f:
            json.dump(self.metadata, f)
        
        # Create sample checkpoint files
        with open(os.path.join(self.checkpoint_dir, "dump.log"), "w") as f:
            f.write("Checkpoint completed successfully\n")
        
        with open(os.path.join(self.checkpoint_dir, "pages.img"), "w") as f:
            f.write("binary checkpoint data\n")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_package_checkpoint_success(self, mock_run):
        """Test successful checkpoint packaging."""
        # Mock date command
        mock_run.return_value = Mock(
            returncode=0,
            stdout="2023-01-01T12:00:00+00:00",
            stderr=""
        )
        
        package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        self.assertIsNotNone(package)
        self.assertTrue(os.path.exists(package.package_path))
        self.assertEqual(package.container_id, "test_container")
        self.assertGreater(package.size_bytes, 0)
        self.assertIsNotNone(package.checksum)
        
        # Verify metadata file was created
        metadata_file = package.package_path + ".metadata.json"
        self.assertTrue(os.path.exists(metadata_file))
    
    def test_package_checkpoint_missing_directory(self):
        """Test packaging non-existent checkpoint directory."""
        package = self.manager.package_checkpoint("/nonexistent/checkpoint")
        
        self.assertIsNone(package)
    
    def test_package_checkpoint_missing_metadata(self):
        """Test packaging checkpoint without metadata."""
        # Remove metadata file
        os.remove(os.path.join(self.checkpoint_dir, "metadata.json"))
        
        package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        self.assertIsNone(package)
    
    @patch('subprocess.run')
    def test_package_checkpoint_custom_output(self, mock_run):
        """Test packaging with custom output path."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="2023-01-01T12:00:00+00:00",
            stderr=""
        )
        
        custom_output = os.path.join(self.temp_dir, "custom_package.tar.gz")
        package = self.manager.package_checkpoint(self.checkpoint_dir, custom_output)
        
        self.assertIsNotNone(package)
        self.assertEqual(package.package_path, custom_output)
        self.assertTrue(os.path.exists(custom_output))
    
    def test_unpack_checkpoint_success(self):
        """Test successful checkpoint unpacking."""
        # First create a package
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Now unpack it
        output_dir = self.manager.unpack_checkpoint(package.package_path)
        
        self.assertIsNotNone(output_dir)
        self.assertTrue(os.path.exists(output_dir))
        
        # Verify files were extracted
        self.assertTrue(os.path.exists(os.path.join(output_dir, "metadata.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "dump.log")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "pages.img")))
    
    def test_unpack_checkpoint_missing_package(self):
        """Test unpacking non-existent package."""
        output_dir = self.manager.unpack_checkpoint("/nonexistent/package.tar.gz")
        
        self.assertIsNone(output_dir)
    
    def test_unpack_checkpoint_custom_output(self):
        """Test unpacking to custom output directory."""
        # First create a package
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Unpack to custom directory
        custom_output = os.path.join(self.temp_dir, "custom_unpack")
        output_dir = self.manager.unpack_checkpoint(package.package_path, custom_output)
        
        self.assertEqual(output_dir, custom_output)
        self.assertTrue(os.path.exists(custom_output))
    
    @patch('subprocess.run')
    def test_transfer_checkpoint_adb_success(self, mock_run):
        """Test successful checkpoint transfer via ADB."""
        # Create a package first
        with patch('subprocess.run') as mock_run_package:
            mock_run_package.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Mock successful ADB transfer
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        config = TransferConfig(
            source_path=package.package_path,
            target_host="adb:device123",
            target_path="/data/local/tmp/checkpoint.tar.gz"
        )
        
        result = self.manager.transfer_checkpoint(config)
        
        self.assertTrue(result)
        # Verify ADB push was called
        self.assertTrue(any("adb" in str(call) for call in mock_run.call_args_list))
    
    @patch('subprocess.run')
    def test_transfer_checkpoint_scp_success(self, mock_run):
        """Test successful checkpoint transfer via SCP."""
        # Create a package first
        with patch('subprocess.run') as mock_run_package:
            mock_run_package.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Mock successful SCP transfer
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        config = TransferConfig(
            source_path=package.package_path,
            target_host="user@remote.host",
            target_path="/tmp/checkpoint.tar.gz"
        )
        
        result = self.manager.transfer_checkpoint(config)
        
        self.assertTrue(result)
        # Verify SCP was called
        self.assertTrue(any("scp" in str(call) for call in mock_run.call_args_list))
    
    @patch('subprocess.run')
    def test_transfer_checkpoint_failure(self, mock_run):
        """Test checkpoint transfer failure."""
        # Create a package first
        with patch('subprocess.run') as mock_run_package:
            mock_run_package.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Mock failed transfer
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Transfer failed")
        
        config = TransferConfig(
            source_path=package.package_path,
            target_host="user@remote.host",
            target_path="/tmp/checkpoint.tar.gz"
        )
        
        result = self.manager.transfer_checkpoint(config)
        
        self.assertFalse(result)
    
    def test_transfer_checkpoint_missing_source(self):
        """Test transfer with missing source package."""
        config = TransferConfig(
            source_path="/nonexistent/package.tar.gz",
            target_host="user@remote.host",
            target_path="/tmp/checkpoint.tar.gz"
        )
        
        result = self.manager.transfer_checkpoint(config)
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_transfer_checkpoint_with_cleanup(self, mock_run):
        """Test checkpoint transfer with source cleanup."""
        # Create a package first
        with patch('subprocess.run') as mock_run_package:
            mock_run_package.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Mock successful transfer
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        config = TransferConfig(
            source_path=package.package_path,
            target_host="user@remote.host",
            target_path="/tmp/checkpoint.tar.gz",
            cleanup_source=True
        )
        
        # Verify package exists before transfer
        self.assertTrue(os.path.exists(package.package_path))
        
        result = self.manager.transfer_checkpoint(config)
        
        self.assertTrue(result)
        # Verify package was cleaned up
        self.assertFalse(os.path.exists(package.package_path))
    
    def test_verify_package_integrity_success(self):
        """Test successful package integrity verification."""
        # Create a package first
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        result = self.manager.verify_package_integrity(package.package_path)
        
        self.assertTrue(result)
    
    def test_verify_package_integrity_no_metadata(self):
        """Test integrity verification without metadata file."""
        # Create a simple tar.gz file without metadata
        package_path = os.path.join(self.temp_dir, "test.tar.gz")
        with tarfile.open(package_path, "w:gz") as tar:
            tar.add(self.checkpoint_dir, arcname="checkpoint")
        
        result = self.manager.verify_package_integrity(package_path)
        
        # Should pass (skip verification) when no metadata
        self.assertTrue(result)
    
    def test_verify_package_integrity_checksum_mismatch(self):
        """Test integrity verification with checksum mismatch."""
        # Create a package first
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Modify the package metadata to have wrong checksum
        metadata_file = package.package_path + ".metadata.json"
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        metadata["checksum"] = "wrong_checksum"
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)
        
        result = self.manager.verify_package_integrity(package.package_path)
        
        self.assertFalse(result)
    
    def test_get_package_info_success(self):
        """Test getting package information."""
        # Create a package first
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        info = self.manager.get_package_info(package.package_path)
        
        self.assertIsNotNone(info)
        self.assertEqual(info["container_id"], "test_container")
        self.assertIn("size_bytes", info)
        self.assertIn("checksum", info)
        self.assertIn("package_path", info)
    
    def test_get_package_info_missing_package(self):
        """Test getting info for non-existent package."""
        info = self.manager.get_package_info("/nonexistent/package.tar.gz")
        
        self.assertIsNone(info)
    
    def test_list_packages_empty(self):
        """Test listing packages in empty directory."""
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir)
        
        packages = self.manager.list_packages(empty_dir)
        
        self.assertEqual(len(packages), 0)
    
    def test_list_packages_with_data(self):
        """Test listing packages with existing data."""
        # Create multiple packages
        packages_created = []
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            
            for i in range(2):
                # Create different checkpoint directories
                checkpoint_dir = os.path.join(self.temp_dir, f"checkpoint_{i}")
                os.makedirs(checkpoint_dir)
                
                metadata = self.metadata.copy()
                metadata["container_id"] = f"container_{i}"
                
                with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
                    json.dump(metadata, f)
                
                with open(os.path.join(checkpoint_dir, "dump.log"), "w") as f:
                    f.write("Checkpoint completed\n")
                
                package = self.manager.package_checkpoint(checkpoint_dir)
                packages_created.append(package)
        
        packages = self.manager.list_packages()
        
        self.assertEqual(len(packages), 2)
        self.assertTrue(all("container_id" in pkg for pkg in packages))
    
    def test_cleanup_package_success(self):
        """Test successful package cleanup."""
        # Create a package first
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="2023-01-01T12:00:00+00:00",
                stderr=""
            )
            package = self.manager.package_checkpoint(self.checkpoint_dir)
        
        # Verify package and metadata exist
        self.assertTrue(os.path.exists(package.package_path))
        metadata_file = package.package_path + ".metadata.json"
        self.assertTrue(os.path.exists(metadata_file))
        
        result = self.manager.cleanup_package(package.package_path)
        
        self.assertTrue(result)
        # Verify files were removed
        self.assertFalse(os.path.exists(package.package_path))
        self.assertFalse(os.path.exists(metadata_file))
    
    def test_cleanup_package_missing_package(self):
        """Test cleanup of non-existent package."""
        result = self.manager.cleanup_package("/nonexistent/package.tar.gz")
        
        # Should succeed even if package doesn't exist
        self.assertTrue(result)
    
    def test_calculate_checksum_consistency(self):
        """Test checksum calculation consistency."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content for checksum")
        
        # Calculate checksum multiple times
        checksum1 = self.manager._calculate_checksum(test_file)
        checksum2 = self.manager._calculate_checksum(test_file)
        
        self.assertEqual(checksum1, checksum2)
        self.assertEqual(len(checksum1), 64)  # SHA256 hex length


if __name__ == '__main__':
    unittest.main()