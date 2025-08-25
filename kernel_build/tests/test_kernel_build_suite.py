#!/usr/bin/env python3
"""
Kernel Build Testing Suite
Comprehensive tests for kernel configuration, compilation, and Android compatibility.
"""

import unittest
import tempfile
import subprocess
import json
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from kernel_build.config.kernel_config import KernelConfigParser, DockerRequirements
from kernel_build.config.validator import KernelConfigValidator
from kernel_build.config.applier import ConfigApplier
from kernel_build.build.kernel_builder import KernelBuilder
from kernel_build.build.toolchain_manager import ToolchainManager
from kernel_build.build.aosp_integration import AOSPIntegration
from kernel_build.patch.patch_engine import PatchEngine


class TestKernelConfigurationSuite(unittest.TestCase):
    """Test suite for kernel configuration validation and application."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_parser = KernelConfigParser()
        self.validator = KernelConfigValidator()
        self.applier = ConfigApplier(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_docker_requirements_completeness(self):
        """Test that all Docker requirements are properly defined."""
        required_options = DockerRequirements.REQUIRED_OPTIONS
        recommended_options = DockerRequirements.RECOMMENDED_OPTIONS
        
        # Essential namespace options
        essential_namespaces = [
            'CONFIG_NAMESPACES',
            'CONFIG_PID_NS',
            'CONFIG_NET_NS',
            'CONFIG_IPC_NS',
            'CONFIG_UTS_NS',
            'CONFIG_USER_NS'
        ]
        
        for option in essential_namespaces:
            self.assertIn(option, required_options, 
                         f"Essential namespace option {option} missing from requirements")
            
        # Essential cgroup options
        essential_cgroups = [
            'CONFIG_CGROUPS',
            'CONFIG_CPUSETS',
            'CONFIG_MEMCG',
            'CONFIG_CGROUP_DEVICE',
            'CONFIG_CGROUP_FREEZER',
            'CONFIG_CGROUP_PIDS'
        ]
        
        for option in essential_cgroups:
            self.assertIn(option, required_options,
                         f"Essential cgroup option {option} missing from requirements")
            
        # Network options
        network_options = [
            'CONFIG_BRIDGE',
            'CONFIG_VETH',
            'CONFIG_NETFILTER_XT_MATCH_ADDRTYPE',
            'CONFIG_NETFILTER_XT_MATCH_CONNTRACK'
        ]
        
        for option in network_options:
            self.assertTrue(
                option in required_options or option in recommended_options,
                f"Network option {option} missing from requirements"
            )
            
    def test_raphael_defconfig_validation(self):
        """Test validation against raphael defconfig structure."""
        # Create mock raphael defconfig
        raphael_config = [
            "CONFIG_ARM64=y",
            "CONFIG_ARCH_QCOM=y",
            "CONFIG_ARCH_SM8150=y",
            "CONFIG_NAMESPACES=y",
            "CONFIG_CGROUPS=y",
            "CONFIG_CPUSETS=y",
            "CONFIG_MEMCG=y",
            "# CONFIG_USER_NS is not set",
            "CONFIG_NET=y",
            "CONFIG_BRIDGE=m",
            "CONFIG_VETH=m"
        ]
        
        config_path = Path(self.temp_dir) / "raphael_defconfig"
        with open(config_path, 'w') as f:
            f.write('\n'.join(raphael_config))
            
        # Parse and validate
        config = self.config_parser.parse_defconfig(str(config_path))
        results = self.validator.validate_config(self.config_parser)
        
        # Should detect missing Docker requirements
        errors = self.validator.get_errors()
        warnings = self.validator.get_warnings()
        
        # Should have errors for missing USER_NS
        user_ns_errors = [e for e in errors if 'USER_NS' in e.option]
        self.assertGreater(len(user_ns_errors), 0)
        
        # Should preserve ARM64 architecture settings
        self.assertEqual(config.get('CONFIG_ARM64'), 'y')
        self.assertEqual(config.get('CONFIG_ARCH_QCOM'), 'y')
        
    def test_config_application_preserves_device_specific(self):
        """Test that Docker config application preserves device-specific settings."""
        # Create config with device-specific options
        device_config = [
            "CONFIG_ARM64=y",
            "CONFIG_ARCH_QCOM=y",
            "CONFIG_ARCH_SM8150=y",
            "CONFIG_MSM_GCC_SM8150=y",
            "CONFIG_PINCTRL_SM8150=y",
            "CONFIG_QCOM_SMEM=y",
            "CONFIG_NAMESPACES=y",
            "CONFIG_CGROUPS=y"
        ]
        
        config_path = Path(self.temp_dir) / "test_defconfig"
        with open(config_path, 'w') as f:
            f.write('\n'.join(device_config))
            
        # Apply Docker configuration
        success, message = self.applier.apply_docker_config(
            str(config_path),
            backup=True,
            merge_mode='smart'
        )
        
        self.assertTrue(success)
        
        # Verify device-specific options are preserved
        updated_config = self.config_parser.parse_defconfig(str(config_path))
        
        device_options = [
            'CONFIG_ARM64',
            'CONFIG_ARCH_QCOM', 
            'CONFIG_ARCH_SM8150',
            'CONFIG_MSM_GCC_SM8150',
            'CONFIG_PINCTRL_SM8150',
            'CONFIG_QCOM_SMEM'
        ]
        
        for option in device_options:
            self.assertEqual(updated_config.get(option), 'y',
                           f"Device-specific option {option} was not preserved")
            
    def test_config_regression_detection(self):
        """Test detection of configuration regressions."""
        # Create baseline config
        baseline_config = DockerRequirements.get_all_requirements()
        baseline_config.update({
            'CONFIG_ARM64': 'y',
            'CONFIG_ARCH_QCOM': 'y'
        })
        
        baseline_path = Path(self.temp_dir) / "baseline.config"
        with open(baseline_path, 'w') as f:
            for option, value in baseline_config.items():
                f.write(f"{option}={value}\n")
                
        # Create regressed config (missing some Docker options)
        regressed_config = baseline_config.copy()
        del regressed_config['CONFIG_USER_NS']
        del regressed_config['CONFIG_CGROUP_PIDS']
        
        regressed_path = Path(self.temp_dir) / "regressed.config"
        with open(regressed_path, 'w') as f:
            for option, value in regressed_config.items():
                f.write(f"{option}={value}\n")
                
        # Detect regression
        from kernel_build.config.applier import ConfigMerger
        merger = ConfigMerger()
        
        differences = merger.diff_configs(str(baseline_path), str(regressed_path))
        
        # Should detect removed Docker requirements
        self.assertIn('CONFIG_USER_NS', differences['removed'])
        self.assertIn('CONFIG_CGROUP_PIDS', differences['removed'])
        
        # Device options should be unchanged
        self.assertIn('CONFIG_ARM64', differences['unchanged'])
        self.assertIn('CONFIG_ARCH_QCOM', differences['unchanged'])


class TestKernelCompilationSuite(unittest.TestCase):
    """Test suite for kernel compilation and build validation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.builder = KernelBuilder(self.temp_dir)
        self.toolchain_manager = ToolchainManager(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_toolchain_validation(self, mock_run):
        """Test toolchain setup and validation."""
        # Mock successful toolchain detection
        mock_run.return_value = Mock(
            returncode=0,
            stdout="aarch64-linux-android-gcc (GCC) 9.0.0\n",
            stderr=""
        )
        
        # Test toolchain detection
        is_valid, toolchain_info = self.toolchain_manager.detect_toolchain()
        
        self.assertTrue(is_valid)
        self.assertIn('version', toolchain_info)
        self.assertIn('path', toolchain_info)
        
        # Verify correct cross-compiler is detected
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('aarch64' in arg for arg in call_args))
        
    @patch('subprocess.run')
    def test_kernel_build_process(self, mock_run):
        """Test kernel build process validation."""
        # Mock successful build commands
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Create mock kernel source structure
        kernel_src = Path(self.temp_dir) / "kernel_source"
        kernel_src.mkdir()
        
        # Create minimal kernel files
        (kernel_src / "Makefile").touch()
        (kernel_src / "arch").mkdir()
        (kernel_src / "arch" / "arm64").mkdir()
        (kernel_src / "arch" / "arm64" / "configs").mkdir()
        
        # Create mock defconfig
        defconfig_path = kernel_src / "arch" / "arm64" / "configs" / "raphael_defconfig"
        with open(defconfig_path, 'w') as f:
            f.write("CONFIG_ARM64=y\nCONFIG_ARCH_QCOM=y\n")
            
        # Test build process
        build_config = {
            'source_path': str(kernel_src),
            'defconfig': 'raphael_defconfig',
            'target_arch': 'arm64',
            'cross_compile': 'aarch64-linux-android-',
            'jobs': 4
        }
        
        success, build_info = self.builder.build_kernel(build_config)
        
        self.assertTrue(success)
        self.assertIn('build_time', build_info)
        
        # Verify make commands were called
        make_calls = [call for call in mock_run.call_args_list 
                     if any('make' in str(arg) for arg in call[0][0])]
        self.assertGreater(len(make_calls), 0)
        
    def test_build_artifact_validation(self):
        """Test validation of build artifacts."""
        # Create mock build artifacts
        build_dir = Path(self.temp_dir) / "build_output"
        build_dir.mkdir()
        
        # Create mock kernel image
        kernel_image = build_dir / "Image"
        with open(kernel_image, 'wb') as f:
            f.write(b'\x00' * 1024)  # Mock kernel image data
            
        # Create mock device tree blobs
        dtb_dir = build_dir / "dtbs"
        dtb_dir.mkdir()
        (dtb_dir / "sm8150-mtp.dtb").touch()
        
        # Create mock modules
        modules_dir = build_dir / "modules"
        modules_dir.mkdir()
        (modules_dir / "test_module.ko").touch()
        
        # Validate artifacts
        artifacts = self.builder.validate_build_artifacts(str(build_dir))
        
        self.assertTrue(artifacts['kernel_image']['present'])
        self.assertTrue(artifacts['device_trees']['present'])
        self.assertTrue(artifacts['modules']['present'])
        
        # Check file sizes
        self.assertGreater(artifacts['kernel_image']['size'], 0)
        
    @patch('subprocess.run')
    def test_build_error_handling(self, mock_run):
        """Test build error detection and reporting."""
        # Mock build failure
        mock_run.return_value = Mock(
            returncode=2,
            stdout="",
            stderr="error: 'CONFIG_INVALID_OPTION' undeclared\n"
        )
        
        build_config = {
            'source_path': self.temp_dir,
            'defconfig': 'invalid_defconfig',
            'target_arch': 'arm64'
        }
        
        success, build_info = self.builder.build_kernel(build_config)
        
        self.assertFalse(success)
        self.assertIn('error', build_info)
        self.assertIn('CONFIG_INVALID_OPTION', build_info['error'])
        
    def test_parallel_build_optimization(self):
        """Test parallel build job optimization."""
        # Test job count calculation
        optimal_jobs = self.builder.calculate_optimal_jobs()
        
        # Should be reasonable number based on CPU cores
        self.assertGreater(optimal_jobs, 0)
        self.assertLessEqual(optimal_jobs, 32)  # Reasonable upper limit
        
        # Test with custom job count
        custom_jobs = self.builder.calculate_optimal_jobs(available_memory_gb=8)
        self.assertGreater(custom_jobs, 0)


class TestAndroidCompatibilitySuite(unittest.TestCase):
    """Test suite for Android system compatibility validation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.aosp_integration = AOSPIntegration(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_selinux_policy_compatibility(self):
        """Test SELinux policy compatibility with Docker."""
        # Create mock SELinux policy files
        sepolicy_dir = Path(self.temp_dir) / "sepolicy"
        sepolicy_dir.mkdir()
        
        # Create mock policy files
        (sepolicy_dir / "file_contexts").touch()
        (sepolicy_dir / "sepolicy").touch()
        (sepolicy_dir / "property_contexts").touch()
        
        # Test policy validation
        is_compatible, issues = self.aosp_integration.validate_selinux_compatibility()
        
        # Should detect potential Docker-related policy issues
        self.assertIsInstance(is_compatible, bool)
        self.assertIsInstance(issues, list)
        
    def test_android_service_compatibility(self):
        """Test compatibility with Android system services."""
        # Mock Android service definitions
        services = [
            'surfaceflinger',
            'system_server',
            'zygote',
            'netd',
            'vold'
        ]
        
        # Test service compatibility
        compatibility_report = self.aosp_integration.check_service_compatibility(services)
        
        self.assertIn('compatible_services', compatibility_report)
        self.assertIn('potential_conflicts', compatibility_report)
        
        # Critical services should be compatible
        compatible = compatibility_report['compatible_services']
        self.assertIn('surfaceflinger', compatible)
        self.assertIn('system_server', compatible)
        
    def test_cgroup_hierarchy_compatibility(self):
        """Test cgroup hierarchy compatibility with Android."""
        # Create mock Android cgroup configuration
        android_cgroups = {
            'cpu': '/dev/cpuctl',
            'memory': '/dev/memcg',
            'freezer': '/dev/freezer'
        }
        
        # Create mock Docker cgroup requirements
        docker_cgroups = {
            'cpu': '/sys/fs/cgroup/cpu',
            'memory': '/sys/fs/cgroup/memory',
            'devices': '/sys/fs/cgroup/devices',
            'freezer': '/sys/fs/cgroup/freezer'
        }
        
        # Test compatibility
        is_compatible, conflicts = self.aosp_integration.check_cgroup_compatibility(
            android_cgroups, docker_cgroups
        )
        
        # Should identify potential mount point conflicts
        self.assertIsInstance(is_compatible, bool)
        self.assertIsInstance(conflicts, list)
        
    def test_init_system_integration(self):
        """Test integration with Android init system."""
        # Create mock init.rc entries for Docker
        docker_init_entries = [
            "service dockerd /system/bin/dockerd",
            "    class main",
            "    user root",
            "    group root",
            "    oneshot"
        ]
        
        # Test init system integration
        is_valid, warnings = self.aosp_integration.validate_init_integration(
            docker_init_entries
        )
        
        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(warnings, list)
        
    def test_property_system_compatibility(self):
        """Test Android property system compatibility."""
        # Mock Docker-related properties
        docker_properties = [
            'ro.docker.enabled=1',
            'persist.docker.daemon=1',
            'ro.docker.version=20.10'
        ]
        
        # Test property compatibility
        compatibility = self.aosp_integration.check_property_compatibility(
            docker_properties
        )
        
        self.assertIn('valid_properties', compatibility)
        self.assertIn('invalid_properties', compatibility)
        self.assertIn('conflicts', compatibility)


class TestBuildRegressionSuite(unittest.TestCase):
    """Test suite for detecting build regressions."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_config_regression_detection(self):
        """Test detection of configuration regressions."""
        # Create baseline configuration
        baseline_config = {
            'CONFIG_ARM64': 'y',
            'CONFIG_NAMESPACES': 'y',
            'CONFIG_CGROUPS': 'y',
            'CONFIG_USER_NS': 'y',
            'CONFIG_BRIDGE': 'm'
        }
        
        baseline_path = Path(self.temp_dir) / "baseline.config"
        with open(baseline_path, 'w') as f:
            for option, value in baseline_config.items():
                f.write(f"{option}={value}\n")
                
        # Create current configuration with regression
        current_config = baseline_config.copy()
        current_config['CONFIG_USER_NS'] = 'n'  # Regression
        del current_config['CONFIG_BRIDGE']      # Missing option
        
        current_path = Path(self.temp_dir) / "current.config"
        with open(current_path, 'w') as f:
            for option, value in current_config.items():
                f.write(f"{option}={value}\n")
                
        # Detect regressions
        from kernel_build.config.applier import ConfigMerger
        merger = ConfigMerger()
        
        regressions = merger.detect_regressions(
            str(baseline_path), 
            str(current_path)
        )
        
        # Should detect USER_NS regression
        self.assertIn('CONFIG_USER_NS', regressions['disabled'])
        self.assertIn('CONFIG_BRIDGE', regressions['removed'])
        
    def test_build_performance_regression(self):
        """Test detection of build performance regressions."""
        # Mock build times
        baseline_times = {
            'config_time': 30,
            'compile_time': 1800,
            'total_time': 1830
        }
        
        current_times = {
            'config_time': 45,      # 50% slower
            'compile_time': 2700,   # 50% slower  
            'total_time': 2745
        }
        
        # Calculate performance regression
        regression_threshold = 0.20  # 20% threshold
        
        config_regression = (current_times['config_time'] - baseline_times['config_time']) / baseline_times['config_time']
        compile_regression = (current_times['compile_time'] - baseline_times['compile_time']) / baseline_times['compile_time']
        
        # Should detect significant regressions
        self.assertGreater(config_regression, regression_threshold)
        self.assertGreater(compile_regression, regression_threshold)
        
    def test_android_boot_regression(self):
        """Test detection of Android boot regressions."""
        # Mock boot metrics
        baseline_boot = {
            'boot_time': 45.0,
            'service_start_time': 12.0,
            'ui_ready_time': 35.0,
            'failed_services': []
        }
        
        current_boot = {
            'boot_time': 65.0,      # Slower boot
            'service_start_time': 18.0,
            'ui_ready_time': 50.0,
            'failed_services': ['netd']  # Service failure
        }
        
        # Detect boot regressions
        boot_regression = (current_boot['boot_time'] - baseline_boot['boot_time']) / baseline_boot['boot_time']
        
        self.assertGreater(boot_regression, 0.20)  # >20% slower
        self.assertGreater(len(current_boot['failed_services']), 0)


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestKernelConfigurationSuite))
    suite.addTest(unittest.makeSuite(TestKernelCompilationSuite))
    suite.addTest(unittest.makeSuite(TestAndroidCompatibilitySuite))
    suite.addTest(unittest.makeSuite(TestBuildRegressionSuite))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)