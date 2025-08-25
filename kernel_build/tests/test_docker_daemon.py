#!/usr/bin/env python3
"""
Tests for Docker daemon manager.
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

from runtime.docker_daemon import DockerDaemonManager, DockerConfig


class TestDockerConfig(unittest.TestCase):
    """Test cases for DockerConfig dataclass."""
    
    def test_docker_config_creation(self):
        """Test DockerConfig creation with defaults."""
        config = DockerConfig(registry_mirrors=["https://registry.example.com"])
        self.assertEqual(config.registry_mirrors, ["https://registry.example.com"])
        self.assertTrue(config.experimental)
        self.assertEqual(config.storage_driver, "overlay2")
        self.assertEqual(config.log_driver, "json-file")
        self.assertEqual(config.log_opts, {"max-size": "10m", "max-file": "3"})
        self.assertEqual(config.insecure_registries, [])
        
    def test_docker_config_custom_values(self):
        """Test DockerConfig creation with custom values."""
        config = DockerConfig(
            registry_mirrors=["https://custom.registry.com"],
            experimental=False,
            storage_driver="devicemapper",
            log_driver="syslog",
            log_opts={"max-size": "50m"},
            insecure_registries=["localhost:5000"]
        )
        self.assertEqual(config.registry_mirrors, ["https://custom.registry.com"])
        self.assertFalse(config.experimental)
        self.assertEqual(config.storage_driver, "devicemapper")
        self.assertEqual(config.log_driver, "syslog")
        self.assertEqual(config.log_opts, {"max-size": "50m"})
        self.assertEqual(config.insecure_registries, ["localhost:5000"])


class TestDockerDaemonManager(unittest.TestCase):
    """Test cases for DockerDaemonManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.docker_path = os.path.join(self.temp_dir, "docker")
        self.config_path = os.path.join(self.temp_dir, "config")
        os.makedirs(self.docker_path, exist_ok=True)
        os.makedirs(self.config_path, exist_ok=True)
        
        self.manager = DockerDaemonManager(self.docker_path, self.config_path)
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.manager.daemon_process:
            self.manager.stop_daemon()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_init(self):
        """Test DockerDaemonManager initialization."""
        manager = DockerDaemonManager()
        self.assertEqual(str(manager.docker_path), "/system/bin")
        self.assertEqual(str(manager.config_path), "/etc/docker")
        self.assertIsNone(manager.daemon_process)
        
    @patch('subprocess.run')
    def test_find_binary(self, mock_run):
        """Test binary finding in PATH."""
        mock_run.return_value = MagicMock(returncode=0, stdout="/usr/bin/docker\n")
        
        result = self.manager._find_binary("docker")
        self.assertEqual(result, "/usr/bin/docker")
        
        mock_run.return_value = MagicMock(returncode=1)
        result = self.manager._find_binary("nonexistent")
        self.assertIsNone(result)
        
    @patch('os.path.exists')
    def test_check_kernel_support(self, mock_exists):
        """Test kernel support checking."""
        mock_exists.return_value = True
        self.assertTrue(self.manager._check_kernel_support())
        
        mock_exists.return_value = False
        self.assertFalse(self.manager._check_kernel_support())
        
    @patch('builtins.open', new_callable=mock_open, read_data='#subsys_name hierarchy num_cgroups enabled\ncpu 1 10 1\nmemory 2 5 1\ndevices 3 3 1\nfreezer 4 2 1\npids 5 1 1\n')
    @patch('os.path.exists')
    def test_check_cgroup_support(self, mock_exists, mock_file):
        """Test cgroup support checking."""
        mock_exists.return_value = True
        
        self.assertTrue(self.manager._check_cgroup_support())
        
    @patch('os.path.exists')
    def test_check_cgroup_support_no_proc_cgroups(self, mock_exists):
        """Test cgroup support checking when /proc/cgroups doesn't exist."""
        mock_exists.return_value = False
        
        self.assertFalse(self.manager._check_cgroup_support())
        
    @patch('os.geteuid')
    @patch('runtime.docker_daemon.DockerDaemonManager._check_cgroup_support')
    @patch('runtime.docker_daemon.DockerDaemonManager._check_kernel_support')
    @patch('runtime.docker_daemon.DockerDaemonManager._find_binary')
    def test_validate_environment_success(self, mock_find_binary, mock_kernel, mock_cgroup, mock_geteuid):
        """Test successful environment validation."""
        mock_find_binary.return_value = "/usr/bin/docker"
        mock_kernel.return_value = True
        mock_cgroup.return_value = True
        mock_geteuid.return_value = 0  # Root user
        
        # Create mock binaries
        for binary in self.manager.DOCKER_BINARIES:
            binary_path = Path(self.docker_path) / binary
            binary_path.touch()
            
        valid, issues = self.manager.validate_environment()
        self.assertTrue(valid)
        self.assertEqual(len(issues), 0)
        
    @patch('os.geteuid')
    def test_validate_environment_not_root(self, mock_geteuid):
        """Test environment validation when not running as root."""
        mock_geteuid.return_value = 1000  # Non-root user
        
        valid, issues = self.manager.validate_environment()
        self.assertFalse(valid)
        self.assertIn("Docker daemon requires root privileges", issues)
        
    @patch('subprocess.run')
    @patch('os.makedirs')
    def test_setup_directories(self, mock_makedirs, mock_run):
        """Test directory setup."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.setup_directories()
        self.assertTrue(result)
        mock_makedirs.assert_called()
        
    @patch('subprocess.run')
    @patch('os.makedirs')
    @patch('runtime.docker_daemon.DockerDaemonManager._is_mounted')
    def test_setup_cgroups(self, mock_is_mounted, mock_makedirs, mock_run):
        """Test cgroup setup."""
        mock_is_mounted.return_value = False
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.setup_cgroups()
        self.assertTrue(result)
        mock_makedirs.assert_called()
        mock_run.assert_called()
        
    @patch('builtins.open', new_callable=mock_open, read_data='tmpfs /sys/fs/cgroup tmpfs rw 0 0\n')
    def test_is_mounted(self, mock_file):
        """Test mount point detection."""
        self.assertTrue(self.manager._is_mounted("/sys/fs/cgroup"))
        self.assertFalse(self.manager._is_mounted("/nonexistent"))
        
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_setup_networking(self, mock_file, mock_run):
        """Test networking setup."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.setup_networking()
        self.assertTrue(result)
        mock_run.assert_called()
        
    def test_create_daemon_config(self):
        """Test Docker daemon configuration creation."""
        config = DockerConfig(registry_mirrors=["https://test.registry.com"])
        
        result = self.manager.create_daemon_config(config)
        self.assertTrue(result)
        
        config_file = Path(self.config_path) / "daemon.json"
        self.assertTrue(config_file.exists())
        
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
            
        self.assertEqual(saved_config["registry-mirrors"], ["https://test.registry.com"])
        self.assertTrue(saved_config["experimental"])
        
    @patch('subprocess.run')
    @patch('os.chmod')
    def test_deploy_binaries(self, mock_chmod, mock_run):
        """Test binary deployment."""
        # Create source binaries
        source_dir = os.path.join(self.temp_dir, "source")
        os.makedirs(source_dir, exist_ok=True)
        
        for binary in ["dockerd", "docker"]:
            binary_path = Path(source_dir) / binary
            binary_path.touch()
            
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.deploy_binaries(source_dir)
        self.assertTrue(result)
        mock_run.assert_called()
        mock_chmod.assert_called()
        
    def test_deploy_binaries_source_not_found(self):
        """Test binary deployment when source directory doesn't exist."""
        result = self.manager.deploy_binaries("/nonexistent")
        self.assertFalse(result)
        
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_start_daemon(self, mock_sleep, mock_run, mock_popen):
        """Test daemon startup."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = self.manager.start_daemon()
        self.assertTrue(result)
        self.assertEqual(self.manager.daemon_process, mock_process)
        
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_start_daemon_failure(self, mock_sleep, mock_run, mock_popen):
        """Test daemon startup failure."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process failed
        mock_process.communicate.return_value = (b"", b"Error starting daemon")
        mock_popen.return_value = mock_process
        
        result = self.manager.start_daemon()
        self.assertFalse(result)
        
    def test_get_daemon_status_not_running(self):
        """Test daemon status when not running."""
        status = self.manager.get_daemon_status()
        self.assertFalse(status["running"])
        self.assertIsNone(status["pid"])
        
    @patch('runtime.docker_daemon.DockerDaemonManager.create_daemon_config')
    @patch('runtime.docker_daemon.DockerDaemonManager.setup_networking')
    @patch('runtime.docker_daemon.DockerDaemonManager.setup_cgroups')
    @patch('runtime.docker_daemon.DockerDaemonManager.setup_directories')
    @patch('runtime.docker_daemon.DockerDaemonManager.validate_environment')
    def test_setup_complete_environment(self, mock_validate, mock_dirs, mock_cgroups, mock_network, mock_config):
        """Test complete environment setup."""
        mock_validate.return_value = (True, [])
        mock_dirs.return_value = True
        mock_cgroups.return_value = True
        mock_network.return_value = True
        mock_config.return_value = True
        
        result = self.manager.setup_complete_environment()
        self.assertTrue(result)
        
        mock_validate.assert_called_once()
        mock_dirs.assert_called_once()
        mock_cgroups.assert_called_once()
        mock_network.assert_called_once()
        mock_config.assert_called_once()


if __name__ == '__main__':
    unittest.main()