#!/usr/bin/env python3
"""
Tests for volume manager.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module directly to avoid relative import issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "volume_manager", 
    Path(__file__).parent.parent / "storage" / "volume_manager.py"
)
volume_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(volume_module)
VolumeManager = volume_module.VolumeManager


class TestVolumeManager(unittest.TestCase):
    """Test cases for VolumeManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.volume_manager = VolumeManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """Test VolumeManager initialization."""
        self.assertEqual(str(self.volume_manager.base_path), self.temp_dir)
        self.assertEqual(
            str(self.volume_manager.volumes_path), 
            os.path.join(self.temp_dir, "volumes")
        )
        self.assertEqual(
            str(self.volume_manager.bind_mounts_config),
            os.path.join(self.temp_dir, "bind-mounts.json")
        )
    
    def test_create_volume_directories(self):
        """Test volume directory creation."""
        result = self.volume_manager._create_volume_directories()
        self.assertTrue(result)
        
        # Check that directories were created
        expected_dirs = [
            self.volume_manager.volumes_path,
            self.volume_manager.volumes_path / "metadata",
            self.volume_manager.base_path / "bind-mounts",
            self.volume_manager.base_path / "tmp-mounts"
        ]
        
        for directory in expected_dirs:
            self.assertTrue(directory.exists(), f"Directory {directory} was not created")
    
    def test_setup_volume_permissions(self):
        """Test volume permissions setup."""
        # Create directories first
        self.volume_manager._create_volume_directories()
        
        result = self.volume_manager._setup_volume_permissions()
        self.assertTrue(result)
        
        # Check permissions
        volumes_perms = oct(self.volume_manager.volumes_path.stat().st_mode)[-3:]
        metadata_perms = oct((self.volume_manager.volumes_path / "metadata").stat().st_mode)[-3:]
        bind_mounts_perms = oct((self.volume_manager.base_path / "bind-mounts").stat().st_mode)[-3:]
        
        self.assertEqual(volumes_perms, "755")
        self.assertEqual(metadata_perms, "700")
        self.assertEqual(bind_mounts_perms, "755")
    
    def test_initialize_volume_metadata(self):
        """Test volume metadata initialization."""
        # Create directories first
        self.volume_manager._create_volume_directories()
        
        result = self.volume_manager._initialize_volume_metadata()
        self.assertTrue(result)
        
        # Check metadata file was created
        metadata_file = self.volume_manager.volumes_path / "metadata" / "volumes.json"
        self.assertTrue(metadata_file.exists())
        
        # Check metadata content
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        self.assertIn("volumes", metadata)
        self.assertIn("version", metadata)
        self.assertEqual(metadata["version"], "1.0")
    
    def test_configure_bind_mount_security(self):
        """Test bind mount security configuration."""
        result = self.volume_manager._configure_bind_mount_security()
        self.assertTrue(result)
        
        # Check config file was created
        self.assertTrue(self.volume_manager.bind_mounts_config.exists())
        
        # Check config content
        with open(self.volume_manager.bind_mounts_config, 'r') as f:
            config = json.load(f)
        
        self.assertIn("allowed_host_paths", config)
        self.assertIn("default_options", config)
        self.assertIn("validation_enabled", config)
    
    def test_setup_volume_support(self):
        """Test complete volume support setup."""
        result = self.volume_manager.setup_volume_support()
        self.assertTrue(result)
        
        # Check all components were set up
        self.assertTrue(self.volume_manager.volumes_path.exists())
        self.assertTrue((self.volume_manager.volumes_path / "metadata").exists())
        self.assertTrue(self.volume_manager.bind_mounts_config.exists())
    
    def test_validate_volume_name(self):
        """Test volume name validation."""
        # Valid names
        self.assertTrue(self.volume_manager._validate_volume_name("test-volume"))
        self.assertTrue(self.volume_manager._validate_volume_name("volume123"))
        
        # Invalid names
        self.assertFalse(self.volume_manager._validate_volume_name(""))
        self.assertFalse(self.volume_manager._validate_volume_name("volume/with/slash"))
        self.assertFalse(self.volume_manager._validate_volume_name("volume:with:colon"))
        self.assertFalse(self.volume_manager._validate_volume_name("a" * 256))  # Too long
    
    def test_validate_bind_mount_path(self):
        """Test bind mount path validation."""
        # Use the temp directory as an allowed path since we know it exists
        original_allowed = self.volume_manager.allowed_host_paths
        # Get the resolved temp directory path to match what Path.resolve() returns
        resolved_temp = str(Path(self.temp_dir).resolve())
        self.volume_manager.allowed_host_paths = [resolved_temp]
        
        try:
            # Valid paths (from allowed list)
            test_path = os.path.join(self.temp_dir, "test")
            self.assertTrue(self.volume_manager._validate_bind_mount_path(test_path))
            
            # Invalid paths (not in allowed list)
            self.assertFalse(self.volume_manager._validate_bind_mount_path("/root/test"))
            self.assertFalse(self.volume_manager._validate_bind_mount_path("/etc/passwd"))
        finally:
            # Restore original allowed paths
            self.volume_manager.allowed_host_paths = original_allowed
    
    def test_create_volume(self):
        """Test volume creation."""
        # Setup volume support first
        self.volume_manager.setup_volume_support()
        
        result = self.volume_manager.create_volume("test-volume")
        self.assertTrue(result)
        
        # Check volume directory was created
        volume_path = self.volume_manager.volumes_path / "test-volume"
        self.assertTrue(volume_path.exists())
        
        # Check metadata was saved
        volumes = self.volume_manager.list_volumes()
        self.assertEqual(len(volumes), 1)
        self.assertEqual(volumes[0]["name"], "test-volume")
    
    def test_create_volume_duplicate(self):
        """Test creating duplicate volume."""
        # Setup and create first volume
        self.volume_manager.setup_volume_support()
        self.volume_manager.create_volume("test-volume")
        
        # Try to create duplicate
        result = self.volume_manager.create_volume("test-volume")
        self.assertTrue(result)  # Should succeed but not create duplicate
        
        # Check only one volume exists
        volumes = self.volume_manager.list_volumes()
        self.assertEqual(len(volumes), 1)
    
    @patch('subprocess.run')
    def test_remove_volume(self, mock_subprocess):
        """Test volume removal."""
        # Setup and create volume
        self.volume_manager.setup_volume_support()
        self.volume_manager.create_volume("test-volume")
        
        # Remove volume
        result = self.volume_manager.remove_volume("test-volume")
        self.assertTrue(result)
        
        # Check subprocess was called to remove directory
        mock_subprocess.assert_called()
        
        # Check volume is no longer listed
        volumes = self.volume_manager.list_volumes()
        self.assertEqual(len(volumes), 0)
    
    def test_create_bind_mount(self):
        """Test bind mount creation."""
        # Setup volume support
        self.volume_manager.setup_volume_support()
        
        # Create test host directory
        host_path = os.path.join(self.temp_dir, "host-data")
        os.makedirs(host_path)
        
        # Mock path validation to allow our test path
        with patch.object(self.volume_manager, '_validate_bind_mount_path', return_value=True):
            result = self.volume_manager.create_bind_mount(host_path, "/container/data")
            self.assertTrue(result)
        
        # Check bind mount was recorded
        bind_mounts = self.volume_manager.list_bind_mounts()
        self.assertEqual(len(bind_mounts), 1)
        self.assertEqual(bind_mounts[0]["host_path"], host_path)
        self.assertEqual(bind_mounts[0]["container_path"], "/container/data")
    
    def test_list_volumes(self):
        """Test volume listing."""
        # Setup and create volumes
        self.volume_manager.setup_volume_support()
        self.volume_manager.create_volume("volume1")
        self.volume_manager.create_volume("volume2")
        
        volumes = self.volume_manager.list_volumes()
        self.assertEqual(len(volumes), 2)
        
        volume_names = [v["name"] for v in volumes]
        self.assertIn("volume1", volume_names)
        self.assertIn("volume2", volume_names)
    
    def test_list_bind_mounts(self):
        """Test bind mount listing."""
        # Setup volume support
        self.volume_manager.setup_volume_support()
        
        # Create test directories and bind mounts
        host_path1 = os.path.join(self.temp_dir, "host1")
        host_path2 = os.path.join(self.temp_dir, "host2")
        os.makedirs(host_path1)
        os.makedirs(host_path2)
        
        with patch.object(self.volume_manager, '_validate_bind_mount_path', return_value=True):
            self.volume_manager.create_bind_mount(host_path1, "/container1")
            self.volume_manager.create_bind_mount(host_path2, "/container2")
        
        bind_mounts = self.volume_manager.list_bind_mounts()
        self.assertEqual(len(bind_mounts), 2)
    
    @patch('subprocess.run')
    def test_cleanup_volumes(self, mock_subprocess):
        """Test volume cleanup."""
        # Setup and create volume
        self.volume_manager.setup_volume_support()
        self.volume_manager.create_volume("test-volume")
        
        result = self.volume_manager.cleanup_volumes(remove_unused=True)
        self.assertTrue(result)
        
        # Check subprocess was called for cleanup
        mock_subprocess.assert_called()
    
    def test_validate_volume_setup(self):
        """Test volume setup validation."""
        # Setup volume support first
        self.volume_manager.setup_volume_support()
        
        results = self.volume_manager.validate_volume_setup()
        
        self.assertTrue(results["directories"])
        self.assertTrue(results["permissions"])
        self.assertTrue(results["metadata"])
        self.assertTrue(results["bind_mount_config"])
        self.assertTrue(results["volume_creation"])
    
    def test_get_volume_info(self):
        """Test volume information retrieval."""
        # Setup and create some volumes
        self.volume_manager.setup_volume_support()
        self.volume_manager.create_volume("volume1")
        self.volume_manager.create_volume("volume2")
        
        info = self.volume_manager.get_volume_info()
        
        self.assertEqual(info["total_volumes"], 2)
        self.assertEqual(info["total_bind_mounts"], 0)
        self.assertIn("volumes_path", info)
        self.assertIn("allowed_host_paths", info)


if __name__ == '__main__':
    unittest.main()