#!/usr/bin/env python3
"""
Integration Test Suite
End-to-end tests for complete kernel build, deployment, and Android compatibility.
"""

import unittest
import tempfile
import subprocess
import json
import time
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from kernel_build.config.config_manager import ConfigurationManager
from kernel_build.build.kernel_builder import KernelBuilder
from kernel_build.build.aosp_integration import AOSPIntegration
from kernel_build.runtime.docker_daemon import DockerDaemonManager
from kernel_build.migration.migration_orchestrator import MigrationOrchestrator


class TestEndToEndKernelBuild(unittest.TestCase):
    """Test complete kernel build and deployment process."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigurationManager(self.temp_dir)
        self.kernel_builder = KernelBuilder(self.temp_dir)
        self.aosp_integration = AOSPIntegration(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_complete_kernel_build_pipeline(self, mock_run):
        """Test complete kernel build pipeline from config to image."""
        # Mock successful build pipeline
        mock_responses = [
            # Config validation
            Mock(returncode=0, stdout="Config validation passed\n", stderr=""),
            # Patch application
            Mock(returncode=0, stdout="Patches applied successfully\n", stderr=""),
            # Toolchain setup
            Mock(returncode=0, stdout="aarch64-linux-android-gcc (GCC) 9.0.0\n", stderr=""),
            # Kernel compilation
            Mock(returncode=0, stdout="Kernel compiled successfully\n", stderr=""),
            # Image creation
            Mock(returncode=0, stdout="Boot image created\n", stderr=""),
            # AOSP integration
            Mock(returncode=0, stdout="AOSP integration completed\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Create mock kernel source
        kernel_src = Path(self.temp_dir) / "kernel_source"
        kernel_src.mkdir()
        self.create_mock_kernel_source(kernel_src)
        
        # Create mock defconfig
        defconfig_path = kernel_src / "arch" / "arm64" / "configs" / "raphael_defconfig"
        with open(defconfig_path, 'w') as f:
            f.write("CONFIG_ARM64=y\nCONFIG_ARCH_QCOM=y\n")
            
        # Run complete build pipeline
        build_config = {
            'source_path': str(kernel_src),
            'defconfig': 'raphael_defconfig',
            'target_arch': 'arm64',
            'target_device': 'raphael',
            'enable_docker': True,
            'apply_patches': True,
            'aosp_integration': True
        }
        
        success, build_result = self.kernel_builder.build_complete_kernel(build_config)
        
        self.assertTrue(success)
        self.assertIn('kernel_image', build_result)
        self.assertIn('build_time', build_result)
        
        # Verify all pipeline stages were executed
        self.assertGreaterEqual(mock_run.call_count, 6)
        
    def create_mock_kernel_source(self, kernel_src):
        """Create mock kernel source structure."""
        # Create essential directories
        (kernel_src / "arch" / "arm64" / "configs").mkdir(parents=True)
        (kernel_src / "kernel" / "cgroup").mkdir(parents=True)
        (kernel_src / "drivers").mkdir()
        (kernel_src / "fs").mkdir()
        (kernel_src / "net").mkdir()
        
        # Create essential files
        (kernel_src / "Makefile").touch()
        (kernel_src / "Kconfig").touch()
        (kernel_src / "kernel" / "cgroup" / "cpuset.c").touch()
        
    @patch('subprocess.run')
    def test_docker_config_integration(self, mock_run):
        """Test Docker configuration integration in kernel build."""
        # Mock config application
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Docker configuration applied\n",
            stderr=""
        )
        
        # Create test defconfig
        defconfig_path = Path(self.temp_dir) / "test_defconfig"
        with open(defconfig_path, 'w') as f:
            f.write("CONFIG_ARM64=y\nCONFIG_NAMESPACES=y\n")
            
        # Apply Docker configuration
        success, message = self.config_manager.apply_docker_configuration(
            str(defconfig_path)
        )
        
        self.assertTrue(success)
        
        # Verify Docker requirements are satisfied
        from kernel_build.config.validator import KernelConfigValidator
        validator = KernelConfigValidator()
        
        # Parse updated config
        from kernel_build.config.kernel_config import KernelConfigParser
        parser = KernelConfigParser()
        config = parser.parse_defconfig(str(defconfig_path))
        
        # Validate Docker requirements
        results = validator.validate_config(parser)
        errors = validator.get_errors()
        
        # Should have fewer errors after Docker config application
        self.assertLess(len(errors), 20)  # Some requirements should be satisfied
        
    @patch('subprocess.run')
    def test_patch_integration_workflow(self, mock_run):
        """Test patch application workflow."""
        # Mock patch application
        mock_responses = [
            Mock(returncode=0, stdout="kernel.diff applied\n", stderr=""),
            Mock(returncode=0, stdout="aosp.diff applied\n", stderr=""),
            Mock(returncode=0, stdout="cpuset.c modified\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Create mock kernel source
        kernel_src = Path(self.temp_dir) / "kernel_source"
        kernel_src.mkdir()
        self.create_mock_kernel_source(kernel_src)
        
        # Create mock patch files
        patches_dir = Path(self.temp_dir) / "patches"
        patches_dir.mkdir()
        
        (patches_dir / "kernel.diff").write_text("--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n")
        (patches_dir / "aosp.diff").write_text("--- a/aosp\n+++ b/aosp\n@@ -1 +1 @@\n-old\n+new\n")
        
        # Apply patches
        from kernel_build.patch.patch_engine import PatchEngine
        patch_engine = PatchEngine(str(kernel_src))
        
        success, results = patch_engine.apply_all_patches([
            str(patches_dir / "kernel.diff"),
            str(patches_dir / "aosp.diff")
        ])
        
        self.assertTrue(success)
        self.assertEqual(len(results), 2)
        
        # Verify patch application was called
        self.assertGreaterEqual(mock_run.call_count, 2)
        
    @patch('subprocess.run')
    def test_aosp_build_integration(self, mock_run):
        """Test AOSP build system integration."""
        # Mock AOSP build commands
        mock_responses = [
            Mock(returncode=0, stdout="BoardConfig.mk updated\n", stderr=""),
            Mock(returncode=0, stdout="Android.mk created\n", stderr=""),
            Mock(returncode=0, stdout="AOSP build successful\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Create mock AOSP environment
        aosp_dir = Path(self.temp_dir) / "aosp"
        aosp_dir.mkdir()
        (aosp_dir / "device" / "xiaomi" / "raphael").mkdir(parents=True)
        
        # Test AOSP integration
        success, integration_result = self.aosp_integration.integrate_kernel_build(
            kernel_image_path=str(Path(self.temp_dir) / "Image"),
            aosp_root=str(aosp_dir),
            device_name="raphael"
        )
        
        self.assertTrue(success)
        self.assertIn('boardconfig_updated', integration_result)
        
        # Verify AOSP integration commands were called
        self.assertGreaterEqual(mock_run.call_count, 2)


class TestAndroidSystemCompatibility(unittest.TestCase):
    """Test Android system compatibility validation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.aosp_integration = AOSPIntegration(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_android_service_compatibility_validation(self):
        """Test Android service compatibility validation."""
        # Mock Android services
        android_services = [
            {'name': 'zygote', 'status': 'running', 'pid': 1234},
            {'name': 'system_server', 'status': 'running', 'pid': 1235},
            {'name': 'surfaceflinger', 'status': 'running', 'pid': 1236},
            {'name': 'netd', 'status': 'running', 'pid': 1237},
            {'name': 'vold', 'status': 'running', 'pid': 1238}
        ]
        
        # Test service compatibility
        compatibility_report = self.aosp_integration.validate_service_compatibility(
            android_services
        )
        
        self.assertIn('compatible_services', compatibility_report)
        self.assertIn('potential_conflicts', compatibility_report)
        
        # Critical services should be compatible
        compatible = compatibility_report['compatible_services']
        self.assertIn('zygote', [s['name'] for s in compatible])
        self.assertIn('system_server', [s['name'] for s in compatible])
        
    def test_selinux_policy_validation(self):
        """Test SELinux policy validation for Docker compatibility."""
        # Create mock SELinux policy
        sepolicy_dir = Path(self.temp_dir) / "sepolicy"
        sepolicy_dir.mkdir()
        
        # Create mock policy files
        (sepolicy_dir / "sepolicy").write_text("allow untrusted_app app_data_file:file read;")
        (sepolicy_dir / "file_contexts").write_text("/system/bin/dockerd u:object_r:dockerd_exec:s0")
        
        # Test SELinux compatibility
        is_compatible, issues = self.aosp_integration.validate_selinux_docker_compatibility(
            str(sepolicy_dir)
        )
        
        self.assertIsInstance(is_compatible, bool)
        self.assertIsInstance(issues, list)
        
    def test_cgroup_hierarchy_validation(self):
        """Test cgroup hierarchy validation for Android compatibility."""
        # Mock Android cgroup configuration
        android_cgroups = {
            'cpu': '/dev/cpuctl',
            'memory': '/dev/memcg',
            'freezer': '/dev/freezer',
            'devices': '/dev/devices'
        }
        
        # Mock Docker cgroup requirements
        docker_cgroups = {
            'cpu': '/sys/fs/cgroup/cpu',
            'memory': '/sys/fs/cgroup/memory',
            'devices': '/sys/fs/cgroup/devices',
            'freezer': '/sys/fs/cgroup/freezer',
            'pids': '/sys/fs/cgroup/pids'
        }
        
        # Test cgroup compatibility
        compatibility_result = self.aosp_integration.validate_cgroup_compatibility(
            android_cgroups, docker_cgroups
        )
        
        self.assertIn('compatible', compatibility_result)
        self.assertIn('conflicts', compatibility_result)
        self.assertIn('recommendations', compatibility_result)
        
    @patch('subprocess.run')
    def test_android_boot_validation(self, mock_run):
        """Test Android boot process validation."""
        # Mock Android boot metrics
        boot_metrics = {
            'kernel_boot_time': 5.2,
            'init_time': 8.5,
            'zygote_start_time': 12.3,
            'system_server_start_time': 15.8,
            'boot_completed_time': 35.7
        }
        
        # Mock boot validation commands
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(boot_metrics),
            stderr=""
        )
        
        # Test boot validation
        boot_result = self.aosp_integration.validate_android_boot()
        
        self.assertIn('boot_time', boot_result)
        self.assertIn('services_started', boot_result)
        self.assertIn('boot_successful', boot_result)
        
    def test_android_property_system_validation(self):
        """Test Android property system validation."""
        # Mock Android properties
        android_properties = {
            'ro.build.version.release': '11',
            'ro.build.version.sdk': '30',
            'sys.boot_completed': '1',
            'ro.product.model': 'Redmi K20 Pro'
        }
        
        # Mock Docker properties
        docker_properties = {
            'ro.docker.enabled': '1',
            'persist.docker.daemon': '1',
            'ro.docker.version': '20.10.0'
        }
        
        # Test property compatibility
        compatibility = self.aosp_integration.validate_property_compatibility(
            android_properties, docker_properties
        )
        
        self.assertIn('compatible', compatibility)
        self.assertIn('conflicts', compatibility)
        
        # Should not conflict with Android system properties
        conflicts = compatibility['conflicts']
        system_conflicts = [c for c in conflicts if c.startswith('ro.build') or c.startswith('sys.')]
        self.assertEqual(len(system_conflicts), 0)


class TestPerformanceAndStability(unittest.TestCase):
    """Test performance and stability validation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_kernel_build_performance(self):
        """Test kernel build performance metrics."""
        # Mock build performance data
        build_metrics = {
            'config_time': 30.5,
            'patch_time': 45.2,
            'compile_time': 1800.0,
            'link_time': 120.3,
            'total_time': 1995.0,
            'memory_usage': 4096,  # MB
            'cpu_usage': 85.5      # %
        }
        
        # Test performance validation
        from kernel_build.build.kernel_builder import PerformanceValidator
        validator = PerformanceValidator()
        
        performance_result = validator.validate_build_performance(build_metrics)
        
        self.assertIn('performance_score', performance_result)
        self.assertIn('bottlenecks', performance_result)
        self.assertIn('recommendations', performance_result)
        
        # Performance score should be reasonable
        score = performance_result['performance_score']
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
        
    def test_docker_runtime_performance(self):
        """Test Docker runtime performance validation."""
        # Mock Docker performance metrics
        docker_metrics = {
            'daemon_start_time': 5.2,
            'container_start_time': 2.1,
            'network_latency': 0.5,
            'storage_io_rate': 150.0,  # MB/s
            'memory_overhead': 256     # MB
        }
        
        # Test Docker performance
        from kernel_build.runtime.docker_daemon import PerformanceMonitor
        monitor = PerformanceMonitor()
        
        performance_result = monitor.validate_docker_performance(docker_metrics)
        
        self.assertIn('performance_rating', performance_result)
        self.assertIn('issues', performance_result)
        
        # Performance rating should be valid
        rating = performance_result['performance_rating']
        self.assertIn(rating, ['excellent', 'good', 'fair', 'poor'])
        
    @patch('subprocess.run')
    def test_system_stability_validation(self, mock_run):
        """Test system stability validation."""
        # Mock stability test commands
        mock_responses = [
            # Memory stress test
            Mock(returncode=0, stdout="Memory test passed\n", stderr=""),
            # CPU stress test
            Mock(returncode=0, stdout="CPU test passed\n", stderr=""),
            # I/O stress test
            Mock(returncode=0, stdout="I/O test passed\n", stderr=""),
            # Network stress test
            Mock(returncode=0, stdout="Network test passed\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Test system stability
        from kernel_build.tests.stability_tester import StabilityTester
        tester = StabilityTester(self.temp_dir)
        
        stability_result = tester.run_stability_tests()
        
        self.assertIn('overall_stability', stability_result)
        self.assertIn('test_results', stability_result)
        
        # All stability tests should pass
        test_results = stability_result['test_results']
        for test_name, result in test_results.items():
            self.assertTrue(result['passed'], f"Stability test {test_name} failed")
            
    def test_container_migration_performance(self):
        """Test container migration performance validation."""
        # Mock migration performance data
        migration_metrics = {
            'checkpoint_time': 15.2,
            'transfer_time': 45.8,
            'restore_time': 12.1,
            'total_migration_time': 73.1,
            'data_transferred': 512,  # MB
            'downtime': 2.3          # seconds
        }
        
        # Test migration performance
        from kernel_build.migration.migration_orchestrator import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()
        
        performance_result = analyzer.analyze_migration_performance(migration_metrics)
        
        self.assertIn('migration_efficiency', performance_result)
        self.assertIn('downtime_acceptable', performance_result)
        self.assertIn('optimization_suggestions', performance_result)
        
        # Migration efficiency should be reasonable
        efficiency = performance_result['migration_efficiency']
        self.assertGreater(efficiency, 0)
        self.assertLessEqual(efficiency, 100)


class TestCompleteIntegrationScenarios(unittest.TestCase):
    """Test complete integration scenarios."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('subprocess.run')
    def test_complete_docker_deployment_scenario(self, mock_run):
        """Test complete Docker deployment scenario."""
        # Mock complete deployment pipeline
        mock_responses = [
            # Kernel build
            Mock(returncode=0, stdout="Kernel built successfully\n", stderr=""),
            # Kernel flash
            Mock(returncode=0, stdout="Kernel flashed to device\n", stderr=""),
            # Android boot
            Mock(returncode=0, stdout="Android booted successfully\n", stderr=""),
            # Docker daemon start
            Mock(returncode=0, stdout="Docker daemon started\n", stderr=""),
            # Container deployment
            Mock(returncode=0, stdout="Container deployed successfully\n", stderr=""),
            # Service validation
            Mock(returncode=0, stdout="All services running\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Create integration orchestrator
        from kernel_build.integration.deployment_orchestrator import DeploymentOrchestrator
        orchestrator = DeploymentOrchestrator(self.temp_dir)
        
        # Run complete deployment
        deployment_config = {
            'kernel_source': str(Path(self.temp_dir) / "kernel"),
            'target_device': 'raphael',
            'enable_docker': True,
            'deploy_containers': ['nginx', 'redis'],
            'validate_android': True
        }
        
        success, deployment_result = orchestrator.deploy_complete_system(deployment_config)
        
        self.assertTrue(success)
        self.assertIn('kernel_deployed', deployment_result)
        self.assertIn('docker_running', deployment_result)
        self.assertIn('containers_deployed', deployment_result)
        self.assertIn('android_compatible', deployment_result)
        
    @patch('subprocess.run')
    def test_cross_architecture_migration_scenario(self, mock_run):
        """Test complete cross-architecture migration scenario."""
        # Mock migration pipeline
        mock_responses = [
            # Source container checkpoint
            Mock(returncode=0, stdout="Container checkpointed\n", stderr=""),
            # Checkpoint transfer
            Mock(returncode=0, stdout="Checkpoint transferred\n", stderr=""),
            # Target system preparation
            Mock(returncode=0, stdout="Target system ready\n", stderr=""),
            # Container restore
            Mock(returncode=0, stdout="Container restored\n", stderr=""),
            # Migration validation
            Mock(returncode=0, stdout="Migration successful\n", stderr="")
        ]
        mock_run.side_effect = mock_responses
        
        # Create migration orchestrator
        migration_orchestrator = MigrationOrchestrator(self.temp_dir)
        
        # Run complete migration
        migration_config = {
            'source_arch': 'x86_64',
            'target_arch': 'aarch64',
            'container_id': 'test_container_123',
            'source_host': '192.168.1.100',
            'target_host': '192.168.1.101',
            'validate_migration': True
        }
        
        success, migration_result = migration_orchestrator.migrate_container(migration_config)
        
        self.assertTrue(success)
        self.assertIn('checkpoint_created', migration_result)
        self.assertIn('transfer_completed', migration_result)
        self.assertIn('restore_successful', migration_result)
        self.assertIn('migration_validated', migration_result)
        
    def test_android_docker_coexistence_scenario(self):
        """Test Android and Docker coexistence scenario."""
        # Mock Android system state
        android_state = {
            'services_running': ['zygote', 'system_server', 'surfaceflinger'],
            'memory_usage': 2048,  # MB
            'cpu_usage': 45.0,     # %
            'battery_level': 85    # %
        }
        
        # Mock Docker system state
        docker_state = {
            'daemon_running': True,
            'containers_running': ['web_server', 'database'],
            'memory_usage': 512,   # MB
            'cpu_usage': 25.0,     # %
            'network_active': True
        }
        
        # Test coexistence validation
        from kernel_build.integration.coexistence_validator import CoexistenceValidator
        validator = CoexistenceValidator()
        
        coexistence_result = validator.validate_coexistence(android_state, docker_state)
        
        self.assertIn('coexistence_viable', coexistence_result)
        self.assertIn('resource_conflicts', coexistence_result)
        self.assertIn('performance_impact', coexistence_result)
        
        # Coexistence should be viable
        self.assertTrue(coexistence_result['coexistence_viable'])
        
        # Resource usage should be within acceptable limits
        total_memory = android_state['memory_usage'] + docker_state['memory_usage']
        total_cpu = android_state['cpu_usage'] + docker_state['cpu_usage']
        
        self.assertLess(total_memory, 4096)  # Less than 4GB total
        self.assertLess(total_cpu, 90.0)     # Less than 90% CPU
        
    @patch('subprocess.run')
    def test_regression_detection_scenario(self, mock_run):
        """Test regression detection in complete system."""
        # Mock baseline system metrics
        baseline_metrics = {
            'boot_time': 35.7,
            'app_launch_time': 2.1,
            'memory_usage': 1800,
            'battery_drain_rate': 5.2  # %/hour
        }
        
        # Mock current system metrics (with regressions)
        current_metrics = {
            'boot_time': 45.3,      # 27% slower
            'app_launch_time': 3.2,  # 52% slower
            'memory_usage': 2200,    # 22% higher
            'battery_drain_rate': 7.8  # 50% higher
        }
        
        # Mock system validation commands
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(current_metrics),
            stderr=""
        )
        
        # Test regression detection
        from kernel_build.tests.regression_detector import RegressionDetector
        detector = RegressionDetector()
        
        regressions = detector.detect_system_regressions(baseline_metrics, current_metrics)
        
        self.assertIn('performance_regressions', regressions)
        self.assertIn('resource_regressions', regressions)
        self.assertIn('severity_assessment', regressions)
        
        # Should detect significant regressions
        perf_regressions = regressions['performance_regressions']
        self.assertIn('boot_time', perf_regressions)
        self.assertIn('app_launch_time', perf_regressions)
        
        resource_regressions = regressions['resource_regressions']
        self.assertIn('memory_usage', resource_regressions)
        self.assertIn('battery_drain_rate', resource_regressions)


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestEndToEndKernelBuild))
    suite.addTest(unittest.makeSuite(TestAndroidSystemCompatibility))
    suite.addTest(unittest.makeSuite(TestPerformanceAndStability))
    suite.addTest(unittest.makeSuite(TestCompleteIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)