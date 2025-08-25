#!/usr/bin/env python3
"""
Tests for network manager.
"""

import unittest
import tempfile
import os
from unittest.mock import patch, mock_open, MagicMock
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.network_manager import NetworkManager, NetworkConfig, BridgeConfig


class TestBridgeConfig(unittest.TestCase):
    """Test cases for BridgeConfig dataclass."""
    
    def test_bridge_config_defaults(self):
        """Test BridgeConfig creation with defaults."""
        config = BridgeConfig()
        self.assertEqual(config.name, "docker0")
        self.assertEqual(config.subnet, "172.17.0.0/16")
        self.assertEqual(config.gateway, "172.17.0.1")
        self.assertEqual(config.mtu, 1500)
        self.assertTrue(config.enable_icc)
        self.assertTrue(config.enable_ip_masquerade)
        
    def test_bridge_config_custom(self):
        """Test BridgeConfig creation with custom values."""
        config = BridgeConfig(
            name="br-custom",
            subnet="192.168.1.0/24",
            gateway="192.168.1.1",
            mtu=9000,
            enable_icc=False,
            enable_ip_masquerade=False
        )
        self.assertEqual(config.name, "br-custom")
        self.assertEqual(config.subnet, "192.168.1.0/24")
        self.assertEqual(config.gateway, "192.168.1.1")
        self.assertEqual(config.mtu, 9000)
        self.assertFalse(config.enable_icc)
        self.assertFalse(config.enable_ip_masquerade)


class TestNetworkConfig(unittest.TestCase):
    """Test cases for NetworkConfig dataclass."""
    
    def test_network_config_defaults(self):
        """Test NetworkConfig creation with defaults."""
        bridge = BridgeConfig()
        config = NetworkConfig(bridge=bridge)
        self.assertEqual(config.bridge, bridge)
        self.assertFalse(config.enable_ipv6)
        self.assertIsNone(config.ipv6_subnet)
        self.assertEqual(config.dns_servers, ["8.8.8.8", "8.8.4.4"])
        
    def test_network_config_custom(self):
        """Test NetworkConfig creation with custom values."""
        bridge = BridgeConfig(name="custom-bridge")
        config = NetworkConfig(
            bridge=bridge,
            enable_ipv6=True,
            ipv6_subnet="2001:db8::/64",
            dns_servers=["1.1.1.1", "1.0.0.1"]
        )
        self.assertEqual(config.bridge.name, "custom-bridge")
        self.assertTrue(config.enable_ipv6)
        self.assertEqual(config.ipv6_subnet, "2001:db8::/64")
        self.assertEqual(config.dns_servers, ["1.1.1.1", "1.0.0.1"])


class TestNetworkManager(unittest.TestCase):
    """Test cases for NetworkManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bridge_config = BridgeConfig()
        self.network_config = NetworkConfig(bridge=self.bridge_config)
        self.manager = NetworkManager(self.network_config)
        
    def test_init_default(self):
        """Test NetworkManager initialization with defaults."""
        manager = NetworkManager()
        self.assertIsNotNone(manager.config)
        self.assertEqual(manager.config.bridge.name, "docker0")
        
    def test_init_custom_config(self):
        """Test NetworkManager initialization with custom config."""
        self.assertEqual(self.manager.config, self.network_config)
        
    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_validate_kernel_support_success(self, mock_run, mock_exists):
        """Test successful kernel support validation."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        supported, missing = self.manager.validate_kernel_support()
        self.assertTrue(supported)
        self.assertEqual(len(missing), 0)
        
    @patch('os.path.exists')
    def test_validate_kernel_support_missing_features(self, mock_exists):
        """Test kernel support validation with missing features."""
        mock_exists.return_value = False
        
        supported, missing = self.manager.validate_kernel_support()
        self.assertFalse(supported)
        self.assertGreater(len(missing), 0)
        
    @patch('subprocess.run')
    def test_load_kernel_modules(self, mock_run):
        """Test kernel module loading."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.load_kernel_modules()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, len(self.manager.REQUIRED_MODULES))
        
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_enable_ip_forwarding(self, mock_exists, mock_file):
        """Test IP forwarding enablement."""
        mock_exists.return_value = True
        
        result = self.manager.enable_ip_forwarding()
        self.assertTrue(result)
        mock_file.assert_called()
        
    def test_get_subnet_prefix(self):
        """Test subnet prefix calculation."""
        prefix = self.manager._get_subnet_prefix()
        self.assertEqual(prefix, 16)  # 172.17.0.0/16
        
    @patch('subprocess.run')
    def test_create_bridge_interface_new(self, mock_run):
        """Test creating new bridge interface."""
        # First call (check if exists) returns error, second call (create) succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1),  # Bridge doesn't exist
            MagicMock(returncode=0),  # Create bridge
            MagicMock(returncode=0),  # Set MTU
            MagicMock(returncode=0),  # Add IP
            MagicMock(returncode=0)   # Bring up
        ]
        
        result = self.manager.create_bridge_interface()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 5)
        
    @patch('subprocess.run')
    def test_create_bridge_interface_exists(self, mock_run):
        """Test when bridge interface already exists."""
        mock_run.return_value = MagicMock(returncode=0)  # Bridge exists
        
        result = self.manager.create_bridge_interface()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 1)  # Only check call
        
    @patch('subprocess.run')
    def test_ensure_iptables_chain_exists(self, mock_run):
        """Test ensuring iptables chain when it already exists."""
        mock_run.return_value = MagicMock(returncode=0)  # Chain exists
        
        result = self.manager._ensure_iptables_chain("filter", "DOCKER")
        self.assertTrue(result)
        
    @patch('subprocess.run')
    def test_ensure_iptables_chain_create(self, mock_run):
        """Test creating new iptables chain."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # Chain doesn't exist
            MagicMock(returncode=0)   # Create chain
        ]
        
        result = self.manager._ensure_iptables_chain("filter", "DOCKER")
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
        
    @patch('subprocess.run')
    def test_setup_routing_rules(self, mock_run):
        """Test routing rules setup."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.setup_routing_rules()
        self.assertTrue(result)
        
    @patch('subprocess.run')
    def test_create_network_namespace_new(self, mock_run):
        """Test creating new network namespace."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # List namespaces (empty)
            MagicMock(returncode=0),  # Create namespace
            MagicMock(returncode=0)   # Bring up loopback
        ]
        
        result = self.manager.create_network_namespace("test-ns")
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 3)
        
    @patch('subprocess.run')
    def test_create_network_namespace_exists(self, mock_run):
        """Test when network namespace already exists."""
        mock_run.return_value = MagicMock(returncode=0, stdout="test-ns")
        
        result = self.manager.create_network_namespace("test-ns")
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 1)  # Only list call
        
    @patch('subprocess.run')
    def test_delete_network_namespace(self, mock_run):
        """Test deleting network namespace."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.delete_network_namespace("test-ns")
        self.assertTrue(result)
        
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_setup_dns_configuration(self, mock_file, mock_makedirs):
        """Test DNS configuration setup."""
        result = self.manager.setup_dns_configuration()
        self.assertTrue(result)
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once()
        
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data='1')
    @patch('os.path.exists')
    def test_validate_network_connectivity_success(self, mock_exists, mock_file, mock_run):
        """Test successful network connectivity validation."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="state UP"),  # Bridge exists and up
            MagicMock(returncode=0, stdout="172.17.0.1"),  # Bridge has correct IP
            MagicMock(returncode=0, stdout="MASQUERADE"),  # NAT rules exist
            MagicMock(returncode=0),  # DNS ping 1
            MagicMock(returncode=0)   # DNS ping 2
        ]
        
        valid, issues = self.manager.validate_network_connectivity()
        self.assertTrue(valid)
        self.assertEqual(len(issues), 0)
        
    @patch('subprocess.run')
    def test_cleanup_network_configuration(self, mock_run):
        """Test network configuration cleanup."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.cleanup_network_configuration()
        self.assertTrue(result)
        
    @patch('runtime.network_manager.NetworkManager.setup_dns_configuration')
    @patch('runtime.network_manager.NetworkManager.setup_routing_rules')
    @patch('runtime.network_manager.NetworkManager.setup_iptables_rules')
    @patch('runtime.network_manager.NetworkManager.create_bridge_interface')
    @patch('runtime.network_manager.NetworkManager.enable_ip_forwarding')
    @patch('runtime.network_manager.NetworkManager.load_kernel_modules')
    @patch('runtime.network_manager.NetworkManager.validate_kernel_support')
    def test_setup_complete_networking(self, mock_validate, mock_modules, mock_forwarding, 
                                     mock_bridge, mock_iptables, mock_routing, mock_dns):
        """Test complete networking setup."""
        mock_validate.return_value = (True, [])
        mock_modules.return_value = True
        mock_forwarding.return_value = True
        mock_bridge.return_value = True
        mock_iptables.return_value = True
        mock_routing.return_value = True
        mock_dns.return_value = True
        
        result = self.manager.setup_complete_networking()
        self.assertTrue(result)
        
        # Verify all setup methods were called
        mock_validate.assert_called_once()
        mock_modules.assert_called_once()
        mock_forwarding.assert_called_once()
        mock_bridge.assert_called_once()
        mock_iptables.assert_called_once()
        mock_routing.assert_called_once()
        mock_dns.assert_called_once()


if __name__ == '__main__':
    unittest.main()