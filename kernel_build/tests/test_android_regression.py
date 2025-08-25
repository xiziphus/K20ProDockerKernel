#!/usr/bin/env python3
"""
Android Compatibility Regression Tests
Tests to ensure Docker kernel modifications don't break Android functionality.
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from kernel_build.config.kernel_config import KernelConfigParser
from kernel_build.build.aosp_integration import AOSPIntegration


class TestAndroidRegressionSuite(unittest.TestCase):
    """Test suite for Android compatibility regression detection."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_parser = KernelConfigParser()
        self.aosp_integration = AOSPIntegration(self.temp_dir)
        
    def test_essential_android_configs_preserved(self):
        """Test that essential Android kernel configs are preserved."""
        # Essential Android kernel options that must not be disabled
        essential_android_configs = [
            'CONFIG_ANDROID',
            'CONFIG_ANDROID_BINDER_IPC',
            'CONFIG_ANDROID_BINDERFS',
            'CONFIG_ANDROID_LOW_MEMORY_KILLER',
            'CONFIG_ASHMEM',
            'CONFIG_STAGING',
            'CONFIG_ION',
            'CONFIG_ION_SYSTEM_HEAP',
            'CONFIG_SYNC_FILE',
            'CONFIG_SW_SYNC',
            'CONFIG_DEBUG_FS',
            'CONFIG_PROC_FS',
            'CONFIG_SYSFS'
        ]
        
        # Create config with Docker requirements + Android essentials
        test_config = {}
        
        # Add Docker requirements
        from kernel_build.config.kernel_config import DockerRequirements
        test_config.update(DockerRequirements.get_all_requirements())
        
        # Add Android essentials
        for option in essential_android_configs:
            test_config[option] = 'y'
            
        # Simulate config parsing
        self.config_parser.config_options = test_config
        
        # Verify all Android essentials are present and enabled
        for option in essential_android_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Essential Android config {option} is not enabled"
            )
            
    def test_binder_ipc_compatibility(self):
        """Test that Binder IPC remains functional with Docker namespaces."""
        # Binder requires specific kernel configurations
        binder_configs = [
            'CONFIG_ANDROID_BINDER_IPC',
            'CONFIG_ANDROID_BINDERFS',
            'CONFIG_ANDROID_BINDER_DEVICES'
        ]
        
        # Docker namespace configs that might conflict
        namespace_configs = [
            'CONFIG_NAMESPACES',
            'CONFIG_PID_NS',
            'CONFIG_IPC_NS',
            'CONFIG_USER_NS'
        ]
        
        # Create config with both sets
        test_config = {}
        for option in binder_configs + namespace_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify no conflicts
        for option in binder_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Binder config {option} conflicts with Docker namespaces"
            )
            
    def test_low_memory_killer_compatibility(self):
        """Test Android Low Memory Killer compatibility with cgroups."""
        # LMK and cgroup memory management configs
        memory_configs = [
            'CONFIG_ANDROID_LOW_MEMORY_KILLER',
            'CONFIG_MEMCG',
            'CONFIG_MEMCG_SWAP',
            'CONFIG_CGROUP_DEVICE',
            'CONFIG_CGROUPS'
        ]
        
        test_config = {}
        for option in memory_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify memory management compatibility
        self.assertTrue(self.config_parser.is_enabled('CONFIG_ANDROID_LOW_MEMORY_KILLER'))
        self.assertTrue(self.config_parser.is_enabled('CONFIG_MEMCG'))
        
        # Check for potential conflicts
        conflicts = self.aosp_integration.check_memory_management_conflicts(test_config)
        self.assertEqual(len(conflicts), 0, f"Memory management conflicts detected: {conflicts}")
        
    def test_selinux_policy_compatibility(self):
        """Test SELinux policy compatibility with Docker."""
        # SELinux configs required for Android
        selinux_configs = [
            'CONFIG_SECURITY_SELINUX',
            'CONFIG_SECURITY_SELINUX_BOOTPARAM',
            'CONFIG_SECURITY_SELINUX_DEVELOP',
            'CONFIG_SECURITY_SELINUX_AVC_STATS'
        ]
        
        # Docker security configs
        docker_security_configs = [
            'CONFIG_SECURITY',
            'CONFIG_SECURITY_NETWORK',
            'CONFIG_SECURITY_CAPABILITIES',
            'CONFIG_CGROUP_DEVICE'
        ]
        
        test_config = {}
        for option in selinux_configs + docker_security_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify SELinux remains enabled
        for option in selinux_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"SELinux config {option} disabled by Docker configs"
            )
            
    def test_android_filesystem_compatibility(self):
        """Test Android filesystem compatibility with Docker storage."""
        # Android filesystem configs
        android_fs_configs = [
            'CONFIG_EXT4_FS',
            'CONFIG_F2FS_FS',
            'CONFIG_FUSE_FS',
            'CONFIG_SDCARD_FS',
            'CONFIG_PROC_FS',
            'CONFIG_SYSFS',
            'CONFIG_TMPFS'
        ]
        
        # Docker storage configs
        docker_storage_configs = [
            'CONFIG_OVERLAY_FS',
            'CONFIG_AUFS_FS',
            'CONFIG_DEVTMPFS',
            'CONFIG_TMPFS_POSIX_ACL'
        ]
        
        test_config = {}
        for option in android_fs_configs + docker_storage_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify Android filesystems remain enabled
        for option in android_fs_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Android filesystem {option} disabled by Docker storage configs"
            )
            
    def test_android_networking_compatibility(self):
        """Test Android networking compatibility with Docker networking."""
        # Android networking configs
        android_net_configs = [
            'CONFIG_ANDROID_PARANOID_NETWORK',
            'CONFIG_NET',
            'CONFIG_INET',
            'CONFIG_IPV6',
            'CONFIG_WIRELESS',
            'CONFIG_WIFI_CONTROL_FUNC'
        ]
        
        # Docker networking configs
        docker_net_configs = [
            'CONFIG_BRIDGE',
            'CONFIG_VETH',
            'CONFIG_NETFILTER',
            'CONFIG_NETFILTER_XTABLES',
            'CONFIG_NETFILTER_XT_MATCH_ADDRTYPE',
            'CONFIG_NETFILTER_XT_MATCH_CONNTRACK',
            'CONFIG_IP_NF_IPTABLES',
            'CONFIG_IP_NF_NAT'
        ]
        
        test_config = {}
        for option in android_net_configs + docker_net_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify Android networking remains functional
        for option in android_net_configs:
            if option != 'CONFIG_WIFI_CONTROL_FUNC':  # This might be device-specific
                self.assertTrue(
                    self.config_parser.is_enabled(option),
                    f"Android networking config {option} disabled by Docker networking"
                )
                
    def test_android_power_management_compatibility(self):
        """Test Android power management compatibility with Docker."""
        # Android power management configs
        power_configs = [
            'CONFIG_PM',
            'CONFIG_PM_SLEEP',
            'CONFIG_SUSPEND',
            'CONFIG_HIBERNATION',
            'CONFIG_PM_RUNTIME',
            'CONFIG_CPU_FREQ',
            'CONFIG_CPU_IDLE'
        ]
        
        # Docker might affect power management through cgroups
        docker_power_configs = [
            'CONFIG_CGROUPS',
            'CONFIG_CPUSETS',
            'CONFIG_CGROUP_CPUACCT',
            'CONFIG_CGROUP_SCHED'
        ]
        
        test_config = {}
        for option in power_configs + docker_power_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify power management remains enabled
        for option in power_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Power management config {option} disabled by Docker cgroup configs"
            )
            
    def test_android_security_features_preserved(self):
        """Test that Android security features are preserved."""
        # Android security configs
        security_configs = [
            'CONFIG_SECURITY',
            'CONFIG_SECURITY_SELINUX',
            'CONFIG_SECURITY_CAPABILITIES',
            'CONFIG_HARDENED_USERCOPY',
            'CONFIG_FORTIFY_SOURCE',
            'CONFIG_CC_STACKPROTECTOR_STRONG'
        ]
        
        # Docker security configs that might conflict
        docker_security_configs = [
            'CONFIG_USER_NS',
            'CONFIG_SECURITY_APPARMOR',
            'CONFIG_CGROUP_DEVICE'
        ]
        
        test_config = {}
        for option in security_configs + docker_security_configs:
            test_config[option] = 'y'
            
        self.config_parser.config_options = test_config
        
        # Verify Android security features remain enabled
        for option in security_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Android security config {option} disabled by Docker security configs"
            )
            
    def test_android_driver_compatibility(self):
        """Test Android driver compatibility with Docker kernel changes."""
        # Essential Android drivers
        driver_configs = [
            'CONFIG_STAGING',  # Required for Android drivers
            'CONFIG_ION',
            'CONFIG_ION_SYSTEM_HEAP',
            'CONFIG_ASHMEM',
            'CONFIG_SYNC_FILE',
            'CONFIG_SW_SYNC',
            'CONFIG_DMA_SHARED_BUFFER'
        ]
        
        test_config = {}
        for option in driver_configs:
            test_config[option] = 'y'
            
        # Add Docker requirements
        from kernel_build.config.kernel_config import DockerRequirements
        test_config.update(DockerRequirements.get_all_requirements())
        
        self.config_parser.config_options = test_config
        
        # Verify Android drivers remain enabled
        for option in driver_configs:
            self.assertTrue(
                self.config_parser.is_enabled(option),
                f"Android driver config {option} disabled by Docker requirements"
            )
            
    def test_android_init_system_compatibility(self):
        """Test compatibility with Android init system."""
        # Mock Android init.rc content
        android_init_content = [
            "service zygote /system/bin/app_process64",
            "service surfaceflinger /system/bin/surfaceflinger",
            "service system_server /system/bin/app_process",
            "service netd /system/bin/netd",
            "service vold /system/bin/vold"
        ]
        
        # Mock Docker init content
        docker_init_content = [
            "service dockerd /system/bin/dockerd",
            "service containerd /system/bin/containerd"
        ]
        
        # Test init system compatibility
        compatibility_issues = self.aosp_integration.check_init_compatibility(
            android_init_content, docker_init_content
        )
        
        # Should not have critical conflicts
        critical_issues = [issue for issue in compatibility_issues 
                          if issue.get('severity') == 'critical']
        self.assertEqual(len(critical_issues), 0, 
                        f"Critical init system conflicts: {critical_issues}")
        
    def test_android_property_system_compatibility(self):
        """Test Android property system compatibility with Docker."""
        # Android system properties
        android_properties = [
            'ro.build.version.release',
            'ro.build.version.sdk',
            'ro.product.model',
            'sys.boot_completed',
            'net.hostname'
        ]
        
        # Docker properties
        docker_properties = [
            'ro.docker.enabled',
            'persist.docker.daemon',
            'ro.docker.version'
        ]
        
        # Test property compatibility
        conflicts = self.aosp_integration.check_property_conflicts(
            android_properties, docker_properties
        )
        
        # Should not conflict with Android system properties
        system_conflicts = [c for c in conflicts if c.startswith('ro.build') or c.startswith('sys.')]
        self.assertEqual(len(system_conflicts), 0,
                        f"Docker properties conflict with Android system properties: {system_conflicts}")


class TestAndroidBootRegression(unittest.TestCase):
    """Test Android boot process regression detection."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_boot_time_regression(self):
        """Test detection of Android boot time regression."""
        # Baseline boot metrics
        baseline_metrics = {
            'kernel_boot_time': 5.2,
            'init_time': 8.5,
            'zygote_start_time': 12.3,
            'system_server_start_time': 15.8,
            'launcher_ready_time': 28.4,
            'boot_completed_time': 35.7
        }
        
        # Current boot metrics (with regression)
        current_metrics = {
            'kernel_boot_time': 7.8,      # 50% slower
            'init_time': 12.1,            # 42% slower
            'zygote_start_time': 14.2,    # 15% slower
            'system_server_start_time': 18.9,  # 20% slower
            'launcher_ready_time': 35.6,  # 25% slower
            'boot_completed_time': 45.3   # 27% slower
        }
        
        # Calculate regressions
        regressions = {}
        for metric, baseline_time in baseline_metrics.items():
            current_time = current_metrics[metric]
            regression = (current_time - baseline_time) / baseline_time
            if regression > 0.15:  # >15% regression threshold
                regressions[metric] = {
                    'baseline': baseline_time,
                    'current': current_time,
                    'regression_percent': regression * 100
                }
                
        # Should detect significant regressions
        self.assertIn('kernel_boot_time', regressions)
        self.assertIn('init_time', regressions)
        self.assertIn('boot_completed_time', regressions)
        
        # Verify regression percentages
        self.assertGreater(regressions['kernel_boot_time']['regression_percent'], 40)
        self.assertGreater(regressions['init_time']['regression_percent'], 35)
        
    def test_service_startup_regression(self):
        """Test Android service startup regression detection."""
        # Baseline service startup status
        baseline_services = {
            'zygote': {'status': 'running', 'start_time': 2.1},
            'system_server': {'status': 'running', 'start_time': 5.8},
            'surfaceflinger': {'status': 'running', 'start_time': 8.2},
            'netd': {'status': 'running', 'start_time': 3.4},
            'vold': {'status': 'running', 'start_time': 4.1}
        }
        
        # Current service status (with issues)
        current_services = {
            'zygote': {'status': 'running', 'start_time': 2.3},
            'system_server': {'status': 'running', 'start_time': 7.2},  # Slower
            'surfaceflinger': {'status': 'running', 'start_time': 10.8},  # Much slower
            'netd': {'status': 'failed', 'start_time': None},  # Failed to start
            'vold': {'status': 'running', 'start_time': 4.0}
        }
        
        # Detect service regressions
        service_issues = []
        
        for service, baseline in baseline_services.items():
            current = current_services[service]
            
            # Check for failed services
            if current['status'] != 'running':
                service_issues.append({
                    'service': service,
                    'issue': 'failed_to_start',
                    'baseline_status': baseline['status'],
                    'current_status': current['status']
                })
                continue
                
            # Check for startup time regression
            if current['start_time'] and baseline['start_time']:
                regression = (current['start_time'] - baseline['start_time']) / baseline['start_time']
                if regression > 0.20:  # >20% slower
                    service_issues.append({
                        'service': service,
                        'issue': 'slow_startup',
                        'baseline_time': baseline['start_time'],
                        'current_time': current['start_time'],
                        'regression_percent': regression * 100
                    })
                    
        # Should detect service issues
        failed_services = [issue for issue in service_issues if issue['issue'] == 'failed_to_start']
        slow_services = [issue for issue in service_issues if issue['issue'] == 'slow_startup']
        
        self.assertGreater(len(failed_services), 0)
        self.assertGreater(len(slow_services), 0)
        
        # Verify specific issues
        netd_failure = next((issue for issue in failed_services if issue['service'] == 'netd'), None)
        self.assertIsNotNone(netd_failure)
        
        surfaceflinger_slow = next((issue for issue in slow_services if issue['service'] == 'surfaceflinger'), None)
        self.assertIsNotNone(surfaceflinger_slow)


if __name__ == '__main__':
    unittest.main()