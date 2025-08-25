#!/usr/bin/env python3
"""
Tests for Toolchain Manager

Test suite for toolchain detection, configuration, and validation functionality.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build.toolchain_manager import ToolchainManager, ToolchainConfig

class TestToolchainManager(unittest.TestCase):
    """Test cases for ToolchainManager"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ToolchainManager(self.temp_dir)
        
        # Create mock NDK structure
        self.mock_ndk_path = Path(self.temp_dir) / "android-ndk"
        self.mock_ndk_path.mkdir()
        
        # Create essential NDK directories
        (self.mock_ndk_path / "toolchains").mkdir()
        (self.mock_ndk_path / "platforms").mkdir()
        (self.mock_ndk_path / "build" / "cmake").mkdir(parents=True)
        
        # Create android.toolchain.cmake
        cmake_file = self.mock_ndk_path / "build" / "cmake" / "android.toolchain.cmake"
        cmake_file.write_text("# Mock Android toolchain file")
        
        # Create source.properties
        props_file = self.mock_ndk_path / "source.properties"
        props_file.write_text("Pkg.Revision = 21.4.7075529")
        
        # Create toolchain structure
        toolchain_dir = (self.mock_ndk_path / "toolchains" / "llvm" / 
                        "prebuilt" / "linux-x86_64" / "bin")
        toolchain_dir.mkdir(parents=True)
        
        # Create mock compiler binaries
        mock_tools = [
            "aarch64-linux-android-gcc",
            "aarch64-linux-android-g++",
            "aarch64-linux-android-ld",
            "aarch64-linux-android-ar",
            "aarch64-linux-android-objcopy",
            "aarch64-linux-android-objdump",
            "aarch64-linux-android-strip",
            "aarch64-linux-android-nm"
        ]
        
        for tool in mock_tools:
            tool_file = toolchain_dir / tool
            tool_file.write_text("#!/bin/bash\necho 'mock tool'")
            tool_file.chmod(0o755)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_validate_ndk_path_valid(self):
        """Test NDK path validation with valid path"""
        result = self.manager._validate_ndk_path(self.mock_ndk_path)
        self.assertTrue(result)
    
    def test_validate_ndk_path_invalid(self):
        """Test NDK path validation with invalid path"""
        invalid_path = Path(self.temp_dir) / "invalid-ndk"
        result = self.manager._validate_ndk_path(invalid_path)
        self.assertFalse(result)
    
    def test_get_ndk_version(self):
        """Test NDK version detection"""
        version = self.manager.get_ndk_version(str(self.mock_ndk_path))
        self.assertEqual(version, "21.4.7075529")
    
    def test_find_toolchain_for_arch(self):
        """Test toolchain detection for architecture"""
        toolchain = self.manager.find_toolchain_for_arch(
            str(self.mock_ndk_path), "aarch64"
        )
        
        self.assertIsNotNone(toolchain)
        self.assertEqual(toolchain.arch, "aarch64")
        self.assertEqual(toolchain.prefix, "aarch64-linux-android")
        self.assertEqual(toolchain.version, "21.4.7075529")
    
    def test_setup_toolchain_environment(self):
        """Test environment variable setup"""
        toolchain = ToolchainConfig(
            name="test-toolchain",
            path="/test/path",
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64"
        )
        
        env_vars = self.manager.setup_toolchain_environment(toolchain)
        
        self.assertEqual(env_vars["CROSS_COMPILE"], "aarch64-linux-android-")
        self.assertEqual(env_vars["ARCH"], "arm64")
        self.assertEqual(env_vars["CC"], "aarch64-linux-android-gcc")
        self.assertIn("/test/path", env_vars["PATH"])
    
    def test_save_and_load_toolchain_config(self):
        """Test toolchain configuration save and load"""
        toolchain = ToolchainConfig(
            name="test-toolchain",
            path="/test/path",
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64",
            validated=True
        )
        
        # Save configuration
        config_file = self.manager.save_toolchain_config(toolchain)
        self.assertTrue(Path(config_file).exists())
        
        # Load configuration
        loaded_toolchain = self.manager.load_toolchain_config(config_file)
        
        self.assertIsNotNone(loaded_toolchain)
        self.assertEqual(loaded_toolchain.name, toolchain.name)
        self.assertEqual(loaded_toolchain.path, toolchain.path)
        self.assertEqual(loaded_toolchain.prefix, toolchain.prefix)
        self.assertEqual(loaded_toolchain.version, toolchain.version)
        self.assertEqual(loaded_toolchain.arch, toolchain.arch)
        self.assertEqual(loaded_toolchain.validated, toolchain.validated)
    
    @patch.dict(os.environ, {"ANDROID_NDK_ROOT": ""})
    def test_detect_android_ndk_with_mock(self):
        """Test NDK detection with mock path"""
        # Override toolchain_paths to include our mock path
        self.manager.toolchain_paths = [str(self.mock_ndk_path)]
        
        ndk_path = self.manager.detect_android_ndk()
        self.assertEqual(ndk_path, str(self.mock_ndk_path))
    
    def test_get_toolchain_info(self):
        """Test toolchain information gathering"""
        toolchain_dir = (self.mock_ndk_path / "toolchains" / "llvm" / 
                        "prebuilt" / "linux-x86_64" / "bin")
        
        toolchain = ToolchainConfig(
            name="test-toolchain",
            path=str(toolchain_dir),
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64",
            validated=True
        )
        
        info = self.manager.get_toolchain_info(toolchain)
        
        self.assertEqual(info["name"], "test-toolchain")
        self.assertEqual(info["architecture"], "aarch64")
        self.assertTrue(info["validated"])
        self.assertIn("gcc", info["tools"])
        self.assertNotEqual(info["tools"]["gcc"], "NOT_FOUND")
    
    @patch('subprocess.run')
    def test_test_compiler_success(self, mock_run):
        """Test compiler functionality test - success case"""
        # Mock successful compilation
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        toolchain_dir = (self.mock_ndk_path / "toolchains" / "llvm" / 
                        "prebuilt" / "linux-x86_64" / "bin")
        
        toolchain = ToolchainConfig(
            name="test-toolchain",
            path=str(toolchain_dir),
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64"
        )
        
        result = self.manager._test_compiler(toolchain)
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_test_compiler_failure(self, mock_run):
        """Test compiler functionality test - failure case"""
        # Mock failed compilation
        mock_run.return_value = MagicMock(returncode=1, stderr="compilation error")
        
        toolchain_dir = (self.mock_ndk_path / "toolchains" / "llvm" / 
                        "prebuilt" / "linux-x86_64" / "bin")
        
        toolchain = ToolchainConfig(
            name="test-toolchain",
            path=str(toolchain_dir),
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64"
        )
        
        result = self.manager._test_compiler(toolchain)
        self.assertFalse(result)

class TestToolchainConfig(unittest.TestCase):
    """Test cases for ToolchainConfig dataclass"""
    
    def test_toolchain_config_creation(self):
        """Test ToolchainConfig creation"""
        config = ToolchainConfig(
            name="test-toolchain",
            path="/test/path",
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64"
        )
        
        self.assertEqual(config.name, "test-toolchain")
        self.assertEqual(config.path, "/test/path")
        self.assertEqual(config.prefix, "aarch64-linux-android")
        self.assertEqual(config.version, "21.0")
        self.assertEqual(config.arch, "aarch64")
        self.assertFalse(config.validated)  # Default value
    
    def test_toolchain_config_with_validation(self):
        """Test ToolchainConfig with validation flag"""
        config = ToolchainConfig(
            name="test-toolchain",
            path="/test/path",
            prefix="aarch64-linux-android",
            version="21.0",
            arch="aarch64",
            validated=True
        )
        
        self.assertTrue(config.validated)

def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)

if __name__ == "__main__":
    run_tests()