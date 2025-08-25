#!/usr/bin/env python3
"""
Docker Functionality Test Suite
Tests for Docker daemon startup, container lifecycle, networking, and storage.
"""

import unittest
import tempfile
import subprocess
import json
import time
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

from kernel_build.runtime.docker_daemon import DockerDaemonManager
from kernel_build.runtime.network_manager import NetworkManager
from kernel_build.storage.overlay_manager import OverlayManager
from kernel_build.storage.volume_manager import VolumeManager


class TestDockerDaemonStartup(unittest.TestCase):
    """Test Docker daemon startup and basic operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.daemon_manager = DockerDaemonManager(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_docker_daemon_startup(self, mock_run):
        """Test Docker daemon startup process."""
        # Mock successful daemon startup
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Docker daemon started successfully\n",
            stderr=""
        )
        
        # Test daemon startup
        success, message = self.daemon_manager.start_daemon()
        
        self.assertTrue(success)
        self.assertIn("started", message.lower())
        
        # Verify dockerd command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('dockerd' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_docker_daemon_health_check(self, mock_run):
        """Test Docker daemon health checking."""
        # Mock successful health check
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"ServerVersion": "20.10.0", "KernelVersion": "5.4.0"}\n',
            stderr=""
        )
        
        # Test health check
        is_healthy, info = self.daemon_manager.check_daemon_health()
        
        self.assertTrue(is_healthy)
        self.assertIn('ServerVersion', info)
        
        # Verify docker info command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) and 'info' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_docker_daemon_startup_failure(self, mock_run):
        """Test Docker daemon startup failure handling."""
        # Mock daemon startup failure
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="failed to start daemon: error initializing graphdriver\n"
        )
        
        # Test daemon startup failure
        success, message = self.daemon_manager.start_daemon()
        
        self.assertFalse(success)
        self.assertIn("failed", message.lower())
        self.assertIn("graphdriver", message)
        
    def test_docker_daemon_configuration(self):
        """Test Docker daemon configuration generation."""
        # Test configuration generation
        config = self.daemon_manager.generate_daemon_config()
        
        # Should include essential Docker daemon options
        self.assertIn('storage-driver', config)
        self.assertIn('cgroup-parent', config)
        self.assertIn('exec-opts', config)
        
        # Should configure for Android environment
        self.assertEqual(config['storage-driver'], 'overlay2')
        self.assertIn('native.cgroupdriver=systemd', config['exec-opts'])
        
    @patch('subprocess.run')
    def test_docker_version_compatibility(self, mock_run):
        """Test Docker version compatibility checking."""
        # Mock Docker version output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"Client": {"Version": "20.10.0"}, "Server": {"Version": "20.10.0"}}\n',
            stderr=""
        )
        
        # Test version compatibility
        is_compatible, version_info = self.daemon_manager.check_version_compatibility()
        
        self.assertTrue(is_compatible)
        self.assertIn('Client', version_info)
        self.assertIn('Server', version_info)
        
        # Verify docker version command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) and 'version' in str(arg) for arg in call_args))


class TestContainerLifecycle(unittest.TestCase):
    """Test container lifecycle operations (create, start, stop, remove)."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_container_creation(self, mock_run):
        """Test container creation."""
        # Mock successful container creation
        mock_run.return_value = Mock(
            returncode=0,
            stdout="container_id_12345\n",
            stderr=""
        )
        
        # Test container creation
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        container_id = container_manager.create_container(
            image="alpine:latest",
            name="test_container",
            command=["echo", "hello"]
        )
        
        self.assertEqual(container_id, "container_id_12345")
        
        # Verify docker create command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('create' in str(arg) for arg in call_args))
        self.assertTrue(any('alpine:latest' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_container_start_stop(self, mock_run):
        """Test container start and stop operations."""
        # Mock successful start/stop operations
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        container_id = "test_container_123"
        
        # Test container start
        success = container_manager.start_container(container_id)
        self.assertTrue(success)
        
        # Test container stop
        success = container_manager.stop_container(container_id)
        self.assertTrue(success)
        
        # Verify both start and stop commands were called
        self.assertEqual(mock_run.call_count, 2)
        
    @patch('subprocess.run')
    def test_container_status_monitoring(self, mock_run):
        """Test container status monitoring."""
        # Mock container status output
        container_status = {
            "Id": "container_123",
            "State": {
                "Status": "running",
                "Running": True,
                "Pid": 1234,
                "ExitCode": 0
            },
            "Config": {
                "Image": "alpine:latest"
            }
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(container_status),
            stderr=""
        )
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Test status retrieval
        status = container_manager.get_container_status("container_123")
        
        self.assertEqual(status['State']['Status'], 'running')
        self.assertTrue(status['State']['Running'])
        self.assertEqual(status['State']['Pid'], 1234)
        
    @patch('subprocess.run')
    def test_container_logs(self, mock_run):
        """Test container log retrieval."""
        # Mock container logs
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Hello from container\nContainer is running\n",
            stderr=""
        )
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Test log retrieval
        logs = container_manager.get_container_logs("container_123")
        
        self.assertIn("Hello from container", logs)
        self.assertIn("Container is running", logs)
        
        # Verify docker logs command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('logs' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_container_removal(self, mock_run):
        """Test container removal."""
        # Mock successful container removal
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Test container removal
        success = container_manager.remove_container("container_123", force=True)
        self.assertTrue(success)
        
        # Verify docker rm command was called with force flag
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('rm' in str(arg) for arg in call_args))
        self.assertTrue(any('-f' in str(arg) for arg in call_args))


class TestDockerNetworking(unittest.TestCase):
    """Test Docker networking functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.network_manager = NetworkManager(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_bridge_network_creation(self, mock_run):
        """Test Docker bridge network creation."""
        # Mock successful network creation
        mock_run.return_value = Mock(
            returncode=0,
            stdout="network_id_12345\n",
            stderr=""
        )
        
        # Test network creation
        network_id = self.network_manager.create_bridge_network(
            name="test_bridge",
            subnet="172.20.0.0/16"
        )
        
        self.assertEqual(network_id, "network_id_12345")
        
        # Verify docker network create command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('network' in str(arg) for arg in call_args))
        self.assertTrue(any('create' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_container_network_connectivity(self, mock_run):
        """Test container network connectivity."""
        # Mock successful ping test
        mock_run.return_value = Mock(
            returncode=0,
            stdout="PING 8.8.8.8: 56 data bytes\n64 bytes from 8.8.8.8: seq=0 ttl=118 time=20.123 ms\n",
            stderr=""
        )
        
        # Test network connectivity
        is_connected = self.network_manager.test_container_connectivity(
            container_id="test_container",
            target_host="8.8.8.8"
        )
        
        self.assertTrue(is_connected)
        
        # Verify docker exec ping command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('exec' in str(arg) for arg in call_args))
        self.assertTrue(any('ping' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_port_mapping(self, mock_run):
        """Test container port mapping."""
        # Mock successful container creation with port mapping
        mock_run.return_value = Mock(
            returncode=0,
            stdout="container_with_ports_123\n",
            stderr=""
        )
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Test container creation with port mapping
        container_id = container_manager.create_container(
            image="nginx:alpine",
            name="web_server",
            ports={"80/tcp": 8080}
        )
        
        self.assertEqual(container_id, "container_with_ports_123")
        
        # Verify port mapping was included in docker create command
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('-p' in str(arg) for arg in call_args))
        self.assertTrue(any('8080:80' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_network_isolation(self, mock_run):
        """Test network isolation between containers."""
        # Mock network inspection
        network_info = {
            "Name": "isolated_network",
            "Driver": "bridge",
            "IPAM": {
                "Config": [{"Subnet": "172.21.0.0/16"}]
            },
            "Containers": {
                "container1": {"IPv4Address": "172.21.0.2/16"},
                "container2": {"IPv4Address": "172.21.0.3/16"}
            }
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(network_info),
            stderr=""
        )
        
        # Test network isolation
        isolation_info = self.network_manager.check_network_isolation("isolated_network")
        
        self.assertEqual(isolation_info['Name'], 'isolated_network')
        self.assertIn('container1', isolation_info['Containers'])
        self.assertIn('container2', isolation_info['Containers'])
        
    @patch('subprocess.run')
    def test_iptables_rules_validation(self, mock_run):
        """Test iptables rules validation for Docker."""
        # Mock iptables rules output
        iptables_output = """
Chain DOCKER (1 references)
target     prot opt source               destination
ACCEPT     tcp  --  0.0.0.0/0            172.17.0.2           tcp dpt:80
ACCEPT     tcp  --  0.0.0.0/0            172.17.0.3           tcp dpt:443

Chain DOCKER-ISOLATION-STAGE-1 (1 references)
target     prot opt source               destination
DOCKER-ISOLATION-STAGE-2  all  --  0.0.0.0/0            0.0.0.0/0
RETURN     all  --  0.0.0.0/0            0.0.0.0/0
"""
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=iptables_output,
            stderr=""
        )
        
        # Test iptables rules validation
        rules_valid = self.network_manager.validate_iptables_rules()
        
        self.assertTrue(rules_valid)
        
        # Verify iptables command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('iptables' in str(arg) for arg in call_args))


class TestDockerStorage(unittest.TestCase):
    """Test Docker storage functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.overlay_manager = OverlayManager(self.temp_dir)
        self.volume_manager = VolumeManager(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_overlay_filesystem_setup(self):
        """Test overlay filesystem setup for Docker."""
        # Create mock overlay directories
        overlay_dir = Path(self.temp_dir) / "overlay2"
        overlay_dir.mkdir()
        
        # Test overlay setup
        success, message = self.overlay_manager.setup_overlay_storage(str(overlay_dir))
        
        self.assertTrue(success)
        self.assertIn("overlay", message.lower())
        
        # Verify overlay directories were created
        self.assertTrue((overlay_dir / "l").exists())
        self.assertTrue((overlay_dir / "diff").exists())
        
    @patch('subprocess.run')
    def test_volume_creation(self, mock_run):
        """Test Docker volume creation."""
        # Mock successful volume creation
        mock_run.return_value = Mock(
            returncode=0,
            stdout="test_volume\n",
            stderr=""
        )
        
        # Test volume creation
        volume_name = self.volume_manager.create_volume("test_volume")
        
        self.assertEqual(volume_name, "test_volume")
        
        # Verify docker volume create command was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('docker' in str(arg) for arg in call_args))
        self.assertTrue(any('volume' in str(arg) for arg in call_args))
        self.assertTrue(any('create' in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_bind_mount_validation(self, mock_run):
        """Test bind mount validation."""
        # Create test directory for bind mount
        bind_source = Path(self.temp_dir) / "bind_source"
        bind_source.mkdir()
        (bind_source / "test_file.txt").write_text("test content")
        
        # Mock successful container creation with bind mount
        mock_run.return_value = Mock(
            returncode=0,
            stdout="container_with_bind_123\n",
            stderr=""
        )
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Test container creation with bind mount
        container_id = container_manager.create_container(
            image="alpine:latest",
            name="bind_test",
            volumes={str(bind_source): "/data"}
        )
        
        self.assertEqual(container_id, "container_with_bind_123")
        
        # Verify bind mount was included in docker create command
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('-v' in str(arg) for arg in call_args))
        self.assertTrue(any(str(bind_source) in str(arg) for arg in call_args))
        
    @patch('subprocess.run')
    def test_storage_driver_validation(self, mock_run):
        """Test storage driver validation."""
        # Mock docker info output with storage driver info
        docker_info = {
            "StorageDriver": "overlay2",
            "DriverStatus": [
                ["Backing Filesystem", "extfs"],
                ["Supports d_type", "true"],
                ["Native Overlay Diff", "true"]
            ]
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(docker_info),
            stderr=""
        )
        
        # Test storage driver validation
        is_valid, driver_info = self.overlay_manager.validate_storage_driver()
        
        self.assertTrue(is_valid)
        self.assertEqual(driver_info['StorageDriver'], 'overlay2')
        self.assertIn('DriverStatus', driver_info)
        
    def test_storage_cleanup(self):
        """Test storage cleanup functionality."""
        # Create mock storage directories
        storage_dir = Path(self.temp_dir) / "docker_storage"
        storage_dir.mkdir()
        
        # Create mock container layers
        containers_dir = storage_dir / "containers"
        containers_dir.mkdir()
        (containers_dir / "container1").mkdir()
        (containers_dir / "container2").mkdir()
        
        # Create mock image layers
        images_dir = storage_dir / "image" / "overlay2"
        images_dir.mkdir(parents=True)
        (images_dir / "layer1").mkdir()
        (images_dir / "layer2").mkdir()
        
        # Test storage cleanup
        cleaned_size = self.overlay_manager.cleanup_unused_storage(str(storage_dir))
        
        self.assertGreater(cleaned_size, 0)
        
    @patch('subprocess.run')
    def test_volume_persistence(self, mock_run):
        """Test volume data persistence."""
        # Mock volume inspection
        volume_info = {
            "Name": "persistent_volume",
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/persistent_volume/_data",
            "Labels": {},
            "Scope": "local"
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(volume_info),
            stderr=""
        )
        
        # Test volume persistence
        persistence_info = self.volume_manager.check_volume_persistence("persistent_volume")
        
        self.assertEqual(persistence_info['Name'], 'persistent_volume')
        self.assertEqual(persistence_info['Driver'], 'local')
        self.assertIn('Mountpoint', persistence_info)


class TestDockerIntegrationScenarios(unittest.TestCase):
    """Test complete Docker integration scenarios."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_web_server_deployment(self, mock_run):
        """Test complete web server deployment scenario."""
        # Mock successful commands for web server deployment
        mock_responses = [
            Mock(returncode=0, stdout="nginx_container_123\n", stderr=""),  # create
            Mock(returncode=0, stdout="", stderr=""),  # start
            Mock(returncode=0, stdout="nginx is running\n", stderr=""),  # logs
            Mock(returncode=0, stdout="HTTP/1.1 200 OK\n", stderr="")  # curl test
        ]
        mock_run.side_effect = mock_responses
        
        from kernel_build.runtime.docker_daemon import ContainerManager
        container_manager = ContainerManager(self.temp_dir)
        
        # Deploy web server
        container_id = container_manager.create_container(
            image="nginx:alpine",
            name="web_server",
            ports={"80/tcp": 8080}
        )
        
        # Start container
        success = container_manager.start_container(container_id)
        self.assertTrue(success)
        
        # Check logs
        logs = container_manager.get_container_logs(container_id)
        self.assertIn("nginx is running", logs)
        
        # Test HTTP connectivity
        from kernel_build.runtime.network_manager import NetworkManager
        network_manager = NetworkManager(self.temp_dir)
        
        response = network_manager.test_http_connectivity("localhost", 8080)
        self.assertIn("200 OK", response)
        
    @patch('subprocess.run')
    def test_database_with_persistent_storage(self, mock_run):
        """Test database deployment with persistent storage."""
        # Mock successful commands for database deployment
        mock_responses = [
            Mock(returncode=0, stdout="db_volume\n", stderr=""),  # volume create
            Mock(returncode=0, stdout="postgres_container_123\n", stderr=""),  # create
            Mock(returncode=0, stdout="", stderr=""),  # start
            Mock(returncode=0, stdout="database system is ready\n", stderr="")  # logs
        ]
        mock_run.side_effect = mock_responses
        
        from kernel_build.storage.volume_manager import VolumeManager
        from kernel_build.runtime.docker_daemon import ContainerManager
        
        volume_manager = VolumeManager(self.temp_dir)
        container_manager = ContainerManager(self.temp_dir)
        
        # Create persistent volume
        volume_name = volume_manager.create_volume("db_volume")
        self.assertEqual(volume_name, "db_volume")
        
        # Deploy database with persistent storage
        container_id = container_manager.create_container(
            image="postgres:13-alpine",
            name="database",
            environment={"POSTGRES_PASSWORD": "testpass"},
            volumes={"db_volume": "/var/lib/postgresql/data"}
        )
        
        # Start database
        success = container_manager.start_container(container_id)
        self.assertTrue(success)
        
        # Verify database is ready
        logs = container_manager.get_container_logs(container_id)
        self.assertIn("database system is ready", logs)
        
    @patch('subprocess.run')
    def test_multi_container_application(self, mock_run):
        """Test multi-container application deployment."""
        # Mock successful commands for multi-container deployment
        mock_responses = [
            Mock(returncode=0, stdout="app_network\n", stderr=""),  # network create
            Mock(returncode=0, stdout="redis_container_123\n", stderr=""),  # redis create
            Mock(returncode=0, stdout="app_container_456\n", stderr=""),  # app create
            Mock(returncode=0, stdout="", stderr=""),  # redis start
            Mock(returncode=0, stdout="", stderr=""),  # app start
            Mock(returncode=0, stdout="Redis server started\n", stderr=""),  # redis logs
            Mock(returncode=0, stdout="App connected to Redis\n", stderr="")  # app logs
        ]
        mock_run.side_effect = mock_responses
        
        from kernel_build.runtime.network_manager import NetworkManager
        from kernel_build.runtime.docker_daemon import ContainerManager
        
        network_manager = NetworkManager(self.temp_dir)
        container_manager = ContainerManager(self.temp_dir)
        
        # Create application network
        network_id = network_manager.create_bridge_network("app_network")
        self.assertEqual(network_id, "app_network")
        
        # Deploy Redis
        redis_id = container_manager.create_container(
            image="redis:alpine",
            name="redis",
            network="app_network"
        )
        
        # Deploy application
        app_id = container_manager.create_container(
            image="node:alpine",
            name="app",
            network="app_network",
            environment={"REDIS_HOST": "redis"}
        )
        
        # Start containers
        container_manager.start_container(redis_id)
        container_manager.start_container(app_id)
        
        # Verify both containers are running
        redis_logs = container_manager.get_container_logs(redis_id)
        app_logs = container_manager.get_container_logs(app_id)
        
        self.assertIn("Redis server started", redis_logs)
        self.assertIn("App connected to Redis", app_logs)


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestDockerDaemonStartup))
    suite.addTest(unittest.makeSuite(TestContainerLifecycle))
    suite.addTest(unittest.makeSuite(TestDockerNetworking))
    suite.addTest(unittest.makeSuite(TestDockerStorage))
    suite.addTest(unittest.makeSuite(TestDockerIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)