#!/usr/bin/env python3
"""
Tests for overlay filesystem manager.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module directly to avoid relative import issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "overlay_manager", 
    Path(__file__).parent.parent / "storage" / "overlay_manager.py"
)
overlay_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay_module)
OverlayManager = overlay_module.OverlayManager


class TestOverlayManager(unittest.TestCase):
    """Test cases for OverlayManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.overlay_manager = OverlayManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """Test OverlayManager initialization."""
        self.assertEqual(str(self.overlay_manager.base_path), self.temp_dir)
        self.assertEqual(
            str(self.overlay_manager.overlay_path), 
            os.path.join(self.temp_dir, "overlay2")
        )
        self.assertEqual(
            str(self.overlay_manager.driver_config_path),
            os.path.join(self.temp_dir, "daemon.json")
        )
    
    def test_create_storage_directories(self):
        """Test storage directory creation."""
        result = self.overlay_manager._create_storage_directories()
        self.assertTrue(result)
        
        # Check that directories were created
        expected_dirs = [
            self.overlay_manager.base_path,
            self.overlay_manager.overlay_path,
            self.overlay_manager.overlay_path / "l",
            self.overlay_manager.base_path / "containers",
            self.overlay_manager.base_path / "image" / "overlay2",
            self.overlay_manager.base_path / "volumes",
            self.overlay_manager.base_path / "tmp"
        ]
        
        for directory in expected_dirs:
            self.assertTrue(directory.exists(), f"Directory {directory} was not created")
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data="overlay\n")
    def test_verify_kernel_support_proc_filesystems(self, mock_file, mock_subprocess):
        """Test kernel support verification via /proc/filesystems."""
        with patch('pathlib.Path.exists', return_value=True):
            result = self.overlay_manager._verify_kernel_support()
            self.assertTrue(result)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_verify_kernel_support_modprobe(self, mock_exists, mock_subprocess):
        """Test kernel support verification via modprobe."""
        # Mock successful modprobe
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        result = self.overlay_manager._verify_kernel_support()
        self.assertTrue(result)
        
        # Check that modprobe was called
        mock_subprocess.assert_called()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_verify_kernel_support_failure(self, mock_exists, mock_subprocess):
        """Test kernel support verification failure."""
        # Mock failed modprobe
        mock_subprocess.side_effect = [
            subprocess.CalledProcessError(1, 'modprobe'),
            subprocess.CalledProcessError(1, 'modprobe')
        ]
        
        result = self.overlay_manager._verify_kernel_support()
        self.assertFalse(result)
    
    def test_configure_storage_driver(self):
        """Test storage driver configuration."""
        result = self.overlay_manager._configure_storage_driver()
        self.assertTrue(result)
        
        # Check that daemon.json was created
        self.assertTrue(self.overlay_manager.driver_config_path.exists())
        
        # Check daemon.json content
        with open(self.overlay_manager.driver_config_path, 'r') as f:
            config = json.load(f)
        
        self.assertEqual(config["storage-driver"], "overlay2")
        self.assertEqual(config["data-root"], self.temp_dir)
        self.assertIn("overlay2.override_kernel_check=true", config["storage-opts"])
    
    def test_setup_filesystem_permissions(self):
        """Test filesystem permissions setup."""
        # Create directories first
        self.overlay_manager._create_storage_directories()
        
        with patch('subprocess.run') as mock_subprocess:
            result = self.overlay_manager._setup_filesystem_permissions()
            self.assertTrue(result)
        
        # Check permissions
        base_perms = oct(self.overlay_manager.base_path.stat().st_mode)[-3:]
        overlay_perms = oct(self.overlay_manager.overlay_path.stat().st_mode)[-3:]
        
        self.assertEqual(base_perms, "700")
        self.assertEqual(overlay_perms, "700")
    
    def test_create_mount_points(self):
        """Test mount point creation."""
        result = self.overlay_manager._create_mount_points()
        self.assertTrue(result)
        
        # Check mount points exist
        mount_points = [
            self.overlay_manager.base_path / "mnt",
            self.overlay_manager.base_path / "overlay-mounts"
        ]
        
        for mount_point in mount_points:
            self.assertTrue(mount_point.exists())
            perms = oct(mount_point.stat().st_mode)[-3:]
            self.assertEqual(perms, "755")
    
    @patch.object(OverlayManager, '_verify_kernel_support', return_value=True)
    @patch('subprocess.run')
    def test_setup_overlay_filesystem_success(self, mock_subprocess, mock_kernel):
        """Test successful overlay filesystem setup."""
        result = self.overlay_manager.setup_overlay_filesystem()
        self.assertTrue(result)
        
        # Check that all components were set up
        self.assertTrue(self.overlay_manager.base_path.exists())
        self.assertTrue(self.overlay_manager.overlay_path.exists())
        self.assertTrue(self.overlay_manager.driver_config_path.exists())
    
    @patch.object(OverlayManager, '_verify_kernel_support', return_value=False)
    def test_setup_overlay_filesystem_kernel_failure(self, mock_kernel):
        """Test overlay filesystem setup with kernel support failure."""
        result = self.overlay_manager.setup_overlay_filesystem()
        self.assertFalse(result)
    
    def test_validate_overlay_setup(self):
        """Test overlay setup validation."""
        # Set up overlay filesystem first
        self.overlay_manager._create_storage_directories()
        self.overlay_manager._configure_storage_driver()
        self.overlay_manager._setup_filesystem_permissions()
        
        with patch.object(self.overlay_manager, '_verify_kernel_support', return_value=True):
            with patch.object(self.overlay_manager, '_test_overlay_mount', return_value=True):
                results = self.overlay_manager.validate_overlay_setup()
        
        self.assertTrue(results["directories"])
        self.assertTrue(results["kernel_support"])
        self.assertTrue(results["daemon_config"])
        self.assertTrue(results["permissions"])
        self.assertTrue(results["mount_capability"])
    
    def test_get_storage_info(self):
        """Test storage information retrieval."""
        # Create directories first
        self.overlay_manager._create_storage_directories()
        
        info = self.overlay_manager.get_storage_info()
        
        self.assertEqual(info["base_path"], self.temp_dir)
        self.assertTrue(info["directories_exist"])
        self.assertGreater(info["total_size"], 0)
        self.assertGreaterEqual(info["available_size"], 0)
    
    @patch('subprocess.run')
    def test_cleanup_overlay_storage(self, mock_subprocess):
        """Test overlay storage cleanup."""
        # Create some directories first
        self.overlay_manager._create_storage_directories()
        
        result = self.overlay_manager.cleanup_overlay_storage()
        self.assertTrue(result)
        
        # Check that rm command was called
        mock_subprocess.assert_called()


if __name__ == '__main__':
    # Import subprocess here to avoid issues with mocking
    import subprocess
    unittest.main()