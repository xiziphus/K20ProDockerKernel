#!/usr/bin/env python3
"""
Tests for Kernel Builder

Test suite for kernel compilation automation functionality.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build.kernel_builder import KernelBuilder, BuildConfig, BuildProgress, BuildResult

class TestKernelBuilder(unittest.TestCase):
    """Test cases for KernelBuilder"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.builder = KernelBuilder(self.temp_dir)
        
        # Create mock kernel source structure
        self.mock_source = Path(self.temp_dir) / "kernel_source"
        self.mock_source.mkdir()
        
        # Create essential kernel files
        (self.mock_source / "Makefile").write_text("# Mock Makefile")
        (self.mock_source / "Kconfig").write_text("# Mock Kconfig")
        (self.mock_source / "arch").mkdir()
        (self.mock_source / "kernel").mkdir()
        (self.mock_source / "drivers").mkdir()
        
        # Create arch structure
        arch_arm64 = self.mock_source / "arch" / "arm64"
        arch_arm64.mkdir(parents=True)
        (arch_arm64 / "configs").mkdir()
        (arch_arm64 / "boot").mkdir()
        (arch_arm64 / "boot" / "dts" / "qcom").mkdir(parents=True)
        
        # Create mock defconfig
        defconfig = arch_arm64 / "configs" / "raphael_defconfig"
        defconfig.write_text("CONFIG_DOCKER=y\nCONFIG_NAMESPACES=y")
        
        # Create mock build config
        self.build_config = BuildConfig(
            source_path=str(self.mock_source),
            output_path=str(Path(self.temp_dir) / "output"),
            config_file=str(defconfig),
            toolchain_config=str(Path(self.temp_dir) / "toolchain.json"),
            target_device="raphael",
            parallel_jobs=2,
            clean_build=False,
            verbose=False
        )
        
        # Create mock toolchain config
        toolchain_data = {
            "name": "test-toolchain",
            "path": "/test/toolchain/bin",
            "prefix": "aarch64-linux-android",
            "version": "21.0",
            "arch": "aarch64",
            "validated": True,
            "environment": {
                "CROSS_COMPILE": "aarch64-linux-android-",
                "ARCH": "arm64",
                "CC": "aarch64-linux-android-gcc"
            }
        }
        
        with open(self.build_config.toolchain_config, 'w') as f:
            json.dump(toolchain_data, f)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_detect_cpu_count(self):
        """Test CPU count detection"""
        cpu_count = self.builder.detect_cpu_count()
        self.assertIsInstance(cpu_count, int)
        self.assertGreater(cpu_count, 0)
        self.assertLessEqual(cpu_count, 16)
    
    def test_build_config_save_load(self):
        """Test build configuration save and load"""
        config_file = Path(self.temp_dir) / "build_config.json"
        
        # Save configuration
        self.builder.save_build_config(self.build_config, str(config_file))
        self.assertTrue(config_file.exists())
        
        # Load configuration
        loaded_config = self.builder.load_build_config(str(config_file))
        
        self.assertEqual(loaded_config.source_path, self.build_config.source_path)
        self.assertEqual(loaded_config.output_path, self.build_config.output_path)
        self.assertEqual(loaded_config.target_device, self.build_config.target_device)
        self.assertEqual(loaded_config.parallel_jobs, self.build_config.parallel_jobs)
    
    @patch('kernel_build.build.kernel_builder.ToolchainManager')
    def test_prepare_build_environment(self, mock_toolchain_manager):
        """Test build environment preparation"""
        # Mock toolchain manager
        mock_manager = MagicMock()
        mock_toolchain_manager.return_value = mock_manager
        
        mock_toolchain = MagicMock()
        mock_toolchain.name = "test-toolchain"
        mock_manager.load_toolchain_config.return_value = mock_toolchain
        mock_manager.setup_toolchain_environment.return_value = {
            "CROSS_COMPILE": "aarch64-linux-android-",
            "ARCH": "arm64"
        }
        
        self.builder.toolchain_manager = mock_manager
        
        start_time = datetime.now()
        env_vars, toolchain = self.builder.prepare_build_environment(self.build_config, start_time)
        
        self.assertIn("CROSS_COMPILE", env_vars)
        self.assertIn("ARCH", env_vars)
        self.assertIn("KBUILD_BUILD_USER", env_vars)
        self.assertEqual(toolchain, mock_toolchain)
    
    @patch('subprocess.Popen')
    def test_run_make_command_success(self, mock_popen):
        """Test successful make command execution"""
        # Mock successful process
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["output line 1", "output line 2", ""]
        mock_process.poll.side_effect = [None, None, 0]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        success, stdout, stderr = self.builder.run_make_command(
            ["make", "test"], {}, str(self.mock_source)
        )
        
        self.assertTrue(success)
        self.assertIn("output line 1", stdout)
        self.assertEqual(stderr, "")
    
    @patch('subprocess.Popen')
    def test_run_make_command_failure(self, mock_popen):
        """Test failed make command execution"""
        # Mock failed process
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["error output", ""]
        mock_process.poll.side_effect = [None, 1]
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process
        
        success, stdout, stderr = self.builder.run_make_command(
            ["make", "test"], {}, str(self.mock_source)
        )
        
        self.assertFalse(success)
        self.assertIn("error output", stdout)
    
    def test_validate_build_artifacts(self):
        """Test build artifact validation"""
        # Create mock artifacts
        output_dir = Path(self.temp_dir) / "output"
        output_dir.mkdir()
        
        image_file = output_dir / "Image"
        image_file.write_bytes(b"x" * 10000)  # 10KB mock kernel image
        
        image_gz_file = output_dir / "Image.gz"
        image_gz_file.write_bytes(b"x" * 5000)  # 5KB mock compressed image
        
        artifacts = [str(image_file), str(image_gz_file)]
        
        start_time = datetime.now()
        success, errors = self.builder.validate_build_artifacts(artifacts, start_time)
        
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)
    
    def test_validate_build_artifacts_missing(self):
        """Test build artifact validation with missing files"""
        artifacts = ["/nonexistent/Image", "/nonexistent/Image.gz"]
        
        start_time = datetime.now()
        success, errors = self.builder.validate_build_artifacts(artifacts, start_time)
        
        self.assertFalse(success)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("missing" in error.lower() for error in errors))
    
    def test_package_build_artifacts(self):
        """Test build artifact packaging"""
        # Create mock build outputs
        boot_dir = self.mock_source / "arch" / "arm64" / "boot"
        
        # Create mock kernel images
        (boot_dir / "Image").write_bytes(b"x" * 10000)
        (boot_dir / "Image.gz").write_bytes(b"x" * 5000)
        
        # Create mock DTB files
        dtb_dir = boot_dir / "dts" / "qcom"
        (dtb_dir / "sm8150-mtp.dtb").write_bytes(b"x" * 1000)
        
        start_time = datetime.now()
        artifacts = self.builder.package_build_artifacts(self.build_config, start_time)
        
        self.assertGreater(len(artifacts), 0)
        
        # Check that output files exist
        for artifact in artifacts:
            self.assertTrue(Path(artifact).exists())
    
    @patch('kernel_build.build.kernel_builder.KernelBuilder.run_make_command')
    @patch('kernel_build.build.kernel_builder.KernelBuilder.prepare_build_environment')
    def test_configure_kernel(self, mock_prepare_env, mock_run_make):
        """Test kernel configuration"""
        # Mock environment preparation
        mock_prepare_env.return_value = ({}, MagicMock())
        
        # Mock successful make command
        mock_run_make.return_value = (True, "Configuration successful", "")
        
        start_time = datetime.now()
        result = self.builder.configure_kernel(self.build_config, {}, start_time)
        
        self.assertTrue(result)
        mock_run_make.assert_called_once()
    
    def test_progress_callback(self):
        """Test progress callback functionality"""
        progress_updates = []
        
        def progress_callback(progress: BuildProgress):
            progress_updates.append(progress)
        
        self.builder.set_progress_callback(progress_callback)
        
        # Trigger a progress update
        start_time = datetime.now()
        self.builder._update_progress("test", 1, 2, "Test message", start_time)
        
        self.assertEqual(len(progress_updates), 1)
        self.assertEqual(progress_updates[0].stage, "test")
        self.assertEqual(progress_updates[0].message, "Test message")

class TestBuildConfig(unittest.TestCase):
    """Test cases for BuildConfig dataclass"""
    
    def test_build_config_creation(self):
        """Test BuildConfig creation"""
        config = BuildConfig(
            source_path="/test/source",
            output_path="/test/output",
            config_file="/test/config",
            toolchain_config="/test/toolchain.json"
        )
        
        self.assertEqual(config.source_path, "/test/source")
        self.assertEqual(config.output_path, "/test/output")
        self.assertEqual(config.config_file, "/test/config")
        self.assertEqual(config.toolchain_config, "/test/toolchain.json")
        self.assertEqual(config.target_device, "raphael")  # Default value
        self.assertEqual(config.parallel_jobs, 0)  # Default value
        self.assertFalse(config.clean_build)  # Default value
        self.assertFalse(config.verbose)  # Default value

class TestBuildProgress(unittest.TestCase):
    """Test cases for BuildProgress dataclass"""
    
    def test_build_progress_creation(self):
        """Test BuildProgress creation"""
        start_time = datetime.now()
        progress = BuildProgress(
            stage="compilation",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Compiling kernel",
            start_time=start_time
        )
        
        self.assertEqual(progress.stage, "compilation")
        self.assertEqual(progress.current_step, 5)
        self.assertEqual(progress.total_steps, 10)
        self.assertEqual(progress.percentage, 50.0)
        self.assertEqual(progress.message, "Compiling kernel")
        self.assertEqual(progress.start_time, start_time)
        self.assertEqual(progress.elapsed_time, 0.0)  # Default value

class TestBuildResult(unittest.TestCase):
    """Test cases for BuildResult dataclass"""
    
    def test_build_result_creation(self):
        """Test BuildResult creation"""
        result = BuildResult(
            success=True,
            build_time=120.5,
            output_files=["/test/Image", "/test/Image.gz"],
            errors=[],
            warnings=["Warning message"],
            log_file="/test/build.log"
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.build_time, 120.5)
        self.assertEqual(len(result.output_files), 2)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.log_file, "/test/build.log")

def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)

if __name__ == "__main__":
    run_tests()