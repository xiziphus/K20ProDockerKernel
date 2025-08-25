#!/usr/bin/env python3
"""
Tests for cgroup configuration manager.
"""

import unittest
import tempfile
import json
import os
from unittest.mock import patch, mock_open, MagicMock
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.cgroup_manager import CgroupManager, CgroupConfig, CgroupV2Config


class TestCgroupManager(unittest.TestCase):
    """Test cases for CgroupManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_cgroups.json")
        self.manager = CgroupManager(self.config_file)
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_init(self):
        """Test CgroupManager initialization."""
        manager = CgroupManager()
        self.assertEqual(manager.config_file, "files/cgroups.json")
        self.assertEqual(len(manager.cgroup_configs), 0)
        self.assertIsNone(manager.cgroup2_config)
        
    def test_generate_default_config(self):
        """Test generation of default cgroup configuration."""
        config = self.manager.generate_default_config()
        
        self.assertIn("Cgroups", config)
        self.assertIn("Cgroups2", config)
        
        # Check that all required controllers are present
        controllers = [cg["Controller"] for cg in config["Cgroups"]]
        for required_controller in self.manager.DOCKER_REQUIRED_CONTROLLERS:
            self.assertIn(required_controller, controllers)
            
        # Check cgroup v2 configuration
        self.assertEqual(config["Cgroups2"]["Path"], "/dev/cg2_bpf")
        self.assertEqual(config["Cgroups2"]["UID"], "root")
        
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        # Generate and save default config
        config = self.manager.generate_default_config()
        self.assertTrue(self.manager.save_config(config, self.config_file))
        self.assertTrue(os.path.exists(self.config_file))
        
        # Load the configuration
        self.assertTrue(self.manager.load_config())
        
        # Verify loaded configuration
        self.assertGreater(len(self.manager.cgroup_configs), 0)
        self.assertIsNotNone(self.manager.cgroup2_config)
        
        # Check specific controller
        cpu_config = next((c for c in self.manager.cgroup_configs if c.controller == "cpu"), None)
        self.assertIsNotNone(cpu_config)
        self.assertEqual(cpu_config.path, "/dev/cpu")
        
    def test_load_config_file_not_found(self):
        """Test loading configuration when file doesn't exist."""
        manager = CgroupManager("nonexistent.json")
        self.assertFalse(manager.load_config())
        
    def test_load_config_invalid_json(self):
        """Test loading configuration with invalid JSON."""
        with open(self.config_file, 'w') as f:
            f.write("invalid json content")
            
        self.assertFalse(self.manager.load_config())
        
    @patch('builtins.open', new_callable=mock_open, read_data='#subsys_name hierarchy num_cgroups enabled\ncpu 1 10 1\nmemory 2 5 1\nblkio 3 3 1\n')
    @patch('os.path.exists')
    def test_validate_cgroup_support_success(self, mock_exists, mock_file):
        """Test successful cgroup support validation."""
        mock_exists.return_value = True
        
        supported, missing = self.manager.validate_cgroup_support()
        self.assertFalse(supported)  # Will be false because not all required controllers are in mock data
        self.assertGreater(len(missing), 0)
        
    @patch('os.path.exists')
    def test_validate_cgroup_support_no_proc_cgroups(self, mock_exists):
        """Test cgroup support validation when /proc/cgroups doesn't exist."""
        mock_exists.return_value = False
        
        supported, missing = self.manager.validate_cgroup_support()
        self.assertFalse(supported)
        self.assertIn("Cannot access /proc/cgroups", missing)
        
    @patch('os.makedirs')
    @patch('os.chmod')
    @patch('os.geteuid')
    def test_create_cgroup_hierarchy(self, mock_geteuid, mock_chmod, mock_makedirs):
        """Test cgroup hierarchy creation."""
        mock_geteuid.return_value = 1000  # Non-root user
        
        # Set up test configuration
        self.manager.cgroup_configs = [
            CgroupConfig("cpu", "/test/cpu", "system", "system", "0755")
        ]
        self.manager.cgroup2_config = CgroupV2Config("/test/cg2", "root", "root", "0755")
        
        result = self.manager.create_cgroup_hierarchy()
        self.assertTrue(result)
        
        # Verify directories were created
        mock_makedirs.assert_called()
        mock_chmod.assert_called()
        
    @patch('subprocess.run')
    @patch('runtime.cgroup_manager.CgroupManager._is_mounted')
    def test_mount_cgroups(self, mock_is_mounted, mock_run):
        """Test cgroup mounting."""
        mock_is_mounted.return_value = False
        mock_run.return_value = MagicMock(returncode=0)
        
        # Set up test configuration
        self.manager.cgroup_configs = [
            CgroupConfig("cpu", "/test/cpu")
        ]
        
        result = self.manager.mount_cgroups()
        self.assertTrue(result)
        mock_run.assert_called()
        
    @patch('builtins.open', new_callable=mock_open, read_data='/dev/cpu /test/cpu cgroup rw 0 0\n')
    def test_is_mounted(self, mock_file):
        """Test mount point detection."""
        self.assertTrue(self.manager._is_mounted("/test/cpu"))
        self.assertFalse(self.manager._is_mounted("/test/memory"))
        
    @patch('runtime.cgroup_manager.CgroupManager._is_mounted')
    def test_validate_mounts(self, mock_is_mounted):
        """Test mount validation."""
        mock_is_mounted.return_value = True
        
        # Set up test configuration
        self.manager.cgroup_configs = [
            CgroupConfig("cpu", "/test/cpu")
        ]
        
        mounted, unmounted = self.manager.validate_mounts()
        self.assertTrue(mounted)
        self.assertEqual(len(unmounted), 0)
        
    @patch('runtime.cgroup_manager.CgroupManager.validate_mounts')
    @patch('runtime.cgroup_manager.CgroupManager.mount_cgroups')
    @patch('runtime.cgroup_manager.CgroupManager.create_cgroup_hierarchy')
    @patch('runtime.cgroup_manager.CgroupManager.validate_cgroup_support')
    @patch('runtime.cgroup_manager.CgroupManager.load_config')
    def test_setup_docker_cgroups_success(self, mock_load, mock_validate, mock_create, mock_mount, mock_validate_mounts):
        """Test successful Docker cgroup setup."""
        mock_load.return_value = True
        mock_validate.return_value = (True, [])
        mock_create.return_value = True
        mock_mount.return_value = True
        mock_validate_mounts.return_value = (True, [])
        
        result = self.manager.setup_docker_cgroups()
        self.assertTrue(result)
        
    @patch('runtime.cgroup_manager.CgroupManager.validate_cgroup_support')
    @patch('runtime.cgroup_manager.CgroupManager.load_config')
    def test_setup_docker_cgroups_missing_support(self, mock_load, mock_validate):
        """Test Docker cgroup setup with missing kernel support."""
        mock_load.return_value = True
        mock_validate.return_value = (False, ["missing_controller"])
        
        result = self.manager.setup_docker_cgroups()
        self.assertFalse(result)


class TestCgroupConfig(unittest.TestCase):
    """Test cases for CgroupConfig dataclass."""
    
    def test_cgroup_config_creation(self):
        """Test CgroupConfig creation with defaults."""
        config = CgroupConfig("cpu", "/dev/cpu")
        self.assertEqual(config.controller, "cpu")
        self.assertEqual(config.path, "/dev/cpu")
        self.assertEqual(config.uid, "root")
        self.assertEqual(config.gid, "root")
        self.assertEqual(config.mode, "0755")
        
    def test_cgroup_config_custom_values(self):
        """Test CgroupConfig creation with custom values."""
        config = CgroupConfig("memory", "/dev/memcg", "system", "system", "0644")
        self.assertEqual(config.controller, "memory")
        self.assertEqual(config.path, "/dev/memcg")
        self.assertEqual(config.uid, "system")
        self.assertEqual(config.gid, "system")
        self.assertEqual(config.mode, "0644")


class TestCgroupV2Config(unittest.TestCase):
    """Test cases for CgroupV2Config dataclass."""
    
    def test_cgroup_v2_config_creation(self):
        """Test CgroupV2Config creation with defaults."""
        config = CgroupV2Config("/dev/cg2")
        self.assertEqual(config.path, "/dev/cg2")
        self.assertEqual(config.uid, "root")
        self.assertEqual(config.gid, "root")
        self.assertEqual(config.mode, "0755")


if __name__ == '__main__':
    unittest.main()