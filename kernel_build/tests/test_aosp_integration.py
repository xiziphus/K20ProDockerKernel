#!/usr/bin/env python3
"""
Tests for AOSP Integration Handler

Test suite for AOSP integration, BoardConfig.mk modification,
and Android build system compatibility functionality.
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
from build.aosp_integration import AOSPIntegrationHandler, AOSPConfig, BoardConfigModification

class TestAOSPIntegrationHandler(unittest.TestCase):
    """Test cases for AOSPIntegrationHandler"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.handler = AOSPIntegrationHandler(self.temp_dir)
        
        # Create mock AOSP structure
        self.mock_aosp = Path(self.temp_dir) / "aosp"
        self.mock_aosp.mkdir()
        
        # Create essential AOSP directories
        (self.mock_aosp / "build").mkdir()
        (self.mock_aosp / "build" / "make").mkdir()
        (self.mock_aosp / "system").mkdir()
        (self.mock_aosp / "frameworks").mkdir()
        (self.mock_aosp / "device").mkdir()
        (self.mock_aosp / "kernel").mkdir()
        
        # Create envsetup.sh
        envsetup = self.mock_aosp / "build" / "envsetup.sh"
        envsetup.write_text("#!/bin/bash\necho 'AOSP environment setup'")
        
        # Create device tree structure
        self.device_tree = self.mock_aosp / "device" / "xiaomi" / "raphael"
        self.device_tree.mkdir(parents=True)
        
        # Create BoardConfig.mk
        board_config = self.device_tree / "BoardConfig.mk"
        board_config.write_text("""# BoardConfig.mk for raphael
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
BOARD_KERNEL_CMDLINE := androidboot.hardware=qcom
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_PAGESIZE := 4096
""")
        
        # Create kernel source structure
        self.kernel_source = Path(self.temp_dir) / "kernel_source"
        self.kernel_source.mkdir()
        (self.kernel_source / "Makefile").write_text("# Kernel Makefile")
        (self.kernel_source / "arch").mkdir()
        (self.kernel_source / "kernel").mkdir()
        (self.kernel_source / "drivers").mkdir()
        
        # Create patch files
        patch_dir = Path(self.temp_dir) / "files"
        patch_dir.mkdir()
        
        aosp_patch = patch_dir / "aosp.diff"
        aosp_patch.write_text("""--- a/test.c
+++ b/test.c
@@ -1,3 +1,4 @@
 int main() {
+    // AOSP modification
     return 0;
 }
""")
        
        kernel_patch = patch_dir / "kernel.diff"
        kernel_patch.write_text("""--- a/kernel/test.c
+++ b/kernel/test.c
@@ -1,3 +1,4 @@
 void kernel_func() {
+    // Kernel modification
     return;
 }
""")
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_validate_aosp_root_valid(self):
        """Test AOSP root validation with valid path"""
        result = self.handler._validate_aosp_root(self.mock_aosp)
        self.assertTrue(result)
    
    def test_validate_aosp_root_invalid(self):
        """Test AOSP root validation with invalid path"""
        invalid_path = Path(self.temp_dir) / "invalid-aosp"
        result = self.handler._validate_aosp_root(invalid_path)
        self.assertFalse(result)
    
    def test_detect_aosp_environment(self):
        """Test AOSP environment detection"""
        # Override toolchain_paths to include our mock path
        original_paths = self.handler.toolchain_manager.toolchain_paths if hasattr(self.handler, 'toolchain_manager') else []
        
        # Test with explicit path
        aosp_root = self.handler.detect_aosp_environment(str(self.mock_aosp))
        self.assertEqual(aosp_root, str(self.mock_aosp))
    
    def test_find_device_tree(self):
        """Test device tree detection"""
        device_tree = self.handler.find_device_tree(str(self.mock_aosp), "raphael")
        self.assertEqual(device_tree, str(self.device_tree))
    
    def test_find_device_tree_not_found(self):
        """Test device tree detection with non-existent device"""
        device_tree = self.handler.find_device_tree(str(self.mock_aosp), "nonexistent")
        self.assertIsNone(device_tree)
    
    def test_get_docker_kernel_cmdline(self):
        """Test Docker kernel command line generation"""
        cmdline = self.handler._get_docker_kernel_cmdline()
        
        self.assertIn("androidboot.hardware=qcom", cmdline)
        self.assertIn("cgroup_disable=pressure", cmdline)
        self.assertIn("systemd.unified_cgroup_hierarchy=false", cmdline)
    
    def test_apply_board_config_modifications(self):
        """Test BoardConfig.mk modifications"""
        original_content = """TARGET_ARCH := arm64
BOARD_KERNEL_CMDLINE := androidboot.hardware=qcom
BOARD_KERNEL_BASE := 0x00000000
"""
        
        modifications = {
            "BOARD_KERNEL_CMDLINE": "androidboot.hardware=qcom cgroup_disable=pressure",
            "TARGET_KERNEL_CONFIG": "docker_raphael_defconfig",
            "BOARD_KERNEL_PAGESIZE": "4096"
        }
        
        modified_content = self.handler._apply_board_config_modifications(
            original_content, modifications
        )
        
        self.assertIn("TARGET_KERNEL_CONFIG := docker_raphael_defconfig", modified_content)
        self.assertIn("cgroup_disable=pressure", modified_content)
        self.assertIn("BOARD_KERNEL_PAGESIZE := 4096", modified_content)
    
    def test_modify_board_config(self):
        """Test BoardConfig.mk modification"""
        result = self.handler.modify_board_config(str(self.device_tree))
        self.assertTrue(result)
        
        # Check if backup was created
        backup_files = list(self.device_tree.glob("BoardConfig.mk.backup*"))
        self.assertGreater(len(backup_files), 0)
        
        # Check if modifications were applied
        board_config = self.device_tree / "BoardConfig.mk"
        content = board_config.read_text()
        self.assertIn("TARGET_KERNEL_CONFIG := docker_raphael_defconfig", content)
        self.assertIn("cgroup_disable=pressure", content)
    
    def test_setup_selinux_policies(self):
        """Test SELinux policy setup"""
        result = self.handler.setup_selinux_policies(str(self.device_tree))
        self.assertTrue(result)
        
        # Check if policy file was created
        policy_file = self.device_tree / "sepolicy" / "docker.te"
        self.assertTrue(policy_file.exists())
        
        # Check policy content
        content = policy_file.read_text()
        self.assertIn("allow untrusted_app self:capability", content)
        self.assertIn("allow system_server kernel:system module_load", content)
    
    @patch('subprocess.run')
    def test_apply_patch_file_git_success(self, mock_run):
        """Test patch application with git - success case"""
        # Mock successful git apply
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git apply --check
            MagicMock(returncode=0)   # git apply
        ]
        
        patch_file = str(Path(self.temp_dir) / "files" / "aosp.diff")
        result = self.handler._apply_patch_file(patch_file, str(self.kernel_source))
        
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('subprocess.run')
    def test_apply_patch_file_patch_fallback(self, mock_run):
        """Test patch application with patch command fallback"""
        # Mock git apply failure, patch success
        mock_run.side_effect = [
            MagicMock(returncode=1),  # git apply --check fails
            MagicMock(returncode=0),  # patch --dry-run succeeds
            MagicMock(returncode=0)   # patch succeeds
        ]
        
        patch_file = str(Path(self.temp_dir) / "files" / "aosp.diff")
        result = self.handler._apply_patch_file(patch_file, str(self.kernel_source))
        
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 3)
    
    def test_validate_android_compatibility_valid(self):
        """Test Android compatibility validation - valid case"""
        aosp_config = AOSPConfig(
            aosp_root=str(self.mock_aosp),
            device_tree_path=str(self.device_tree),
            kernel_source_path=str(self.kernel_source),
            kernel_output_path=str(Path(self.temp_dir) / "output"),
            target_device="raphael",
            android_version="11"
        )
        
        valid, issues = self.handler.validate_android_compatibility(aosp_config)
        
        # May have some issues due to missing build tools in test environment
        # but AOSP structure should be valid
        aosp_issues = [issue for issue in issues if "AOSP" in issue or "Device tree" in issue or "Kernel" in issue]
        self.assertEqual(len(aosp_issues), 0)
    
    def test_validate_android_compatibility_invalid(self):
        """Test Android compatibility validation - invalid case"""
        aosp_config = AOSPConfig(
            aosp_root="/nonexistent/aosp",
            device_tree_path="/nonexistent/device",
            kernel_source_path="/nonexistent/kernel",
            kernel_output_path="/nonexistent/output",
            target_device="raphael",
            android_version="99"  # Invalid version
        )
        
        valid, issues = self.handler.validate_android_compatibility(aosp_config)
        
        self.assertFalse(valid)
        self.assertGreater(len(issues), 0)
        
        # Check for specific issues
        issue_text = " ".join(issues)
        self.assertIn("Invalid AOSP root", issue_text)
        self.assertIn("Device tree not found", issue_text)
        self.assertIn("Kernel source not found", issue_text)
        self.assertIn("Unsupported Android version", issue_text)
    
    def test_generate_build_script(self):
        """Test build script generation"""
        aosp_config = AOSPConfig(
            aosp_root=str(self.mock_aosp),
            device_tree_path=str(self.device_tree),
            kernel_source_path=str(self.kernel_source),
            kernel_output_path=str(Path(self.temp_dir) / "output"),
            target_device="raphael",
            android_version="11",
            build_variant="userdebug"
        )
        
        script_file = str(Path(self.temp_dir) / "build_script.sh")
        result = self.handler.generate_build_script(aosp_config, script_file)
        
        self.assertTrue(result)
        self.assertTrue(Path(script_file).exists())
        
        # Check script content
        content = Path(script_file).read_text()
        self.assertIn("#!/bin/bash", content)
        self.assertIn(f'AOSP_ROOT="{aosp_config.aosp_root}"', content)
        self.assertIn(f'TARGET_DEVICE="{aosp_config.target_device}"', content)
        self.assertIn("source build/envsetup.sh", content)
        self.assertIn("make docker_raphael_defconfig", content)
        
        # Check if script is executable
        self.assertTrue(os.access(script_file, os.X_OK))
    
    def test_create_build_script_content(self):
        """Test build script content creation"""
        aosp_config = AOSPConfig(
            aosp_root="/test/aosp",
            device_tree_path="/test/device",
            kernel_source_path="/test/kernel",
            kernel_output_path="/test/output",
            target_device="raphael",
            android_version="11",
            build_variant="userdebug"
        )
        
        content = self.handler._create_build_script_content(aosp_config)
        
        self.assertIn("#!/bin/bash", content)
        self.assertIn("AOSP_ROOT=\"/test/aosp\"", content)
        self.assertIn("TARGET_DEVICE=\"raphael\"", content)
        self.assertIn("ANDROID_VERSION=\"11\"", content)
        self.assertIn("BUILD_VARIANT=\"userdebug\"", content)

class TestAOSPConfig(unittest.TestCase):
    """Test cases for AOSPConfig dataclass"""
    
    def test_aosp_config_creation(self):
        """Test AOSPConfig creation"""
        config = AOSPConfig(
            aosp_root="/test/aosp",
            device_tree_path="/test/device",
            kernel_source_path="/test/kernel",
            kernel_output_path="/test/output"
        )
        
        self.assertEqual(config.aosp_root, "/test/aosp")
        self.assertEqual(config.device_tree_path, "/test/device")
        self.assertEqual(config.kernel_source_path, "/test/kernel")
        self.assertEqual(config.kernel_output_path, "/test/output")
        self.assertEqual(config.target_device, "raphael")  # Default value
        self.assertEqual(config.android_version, "11")  # Default value
        self.assertEqual(config.build_variant, "userdebug")  # Default value
    
    def test_aosp_config_with_custom_values(self):
        """Test AOSPConfig with custom values"""
        config = AOSPConfig(
            aosp_root="/test/aosp",
            device_tree_path="/test/device",
            kernel_source_path="/test/kernel",
            kernel_output_path="/test/output",
            target_device="custom_device",
            android_version="12",
            build_variant="eng"
        )
        
        self.assertEqual(config.target_device, "custom_device")
        self.assertEqual(config.android_version, "12")
        self.assertEqual(config.build_variant, "eng")

class TestBoardConfigModification(unittest.TestCase):
    """Test cases for BoardConfigModification dataclass"""
    
    def test_board_config_modification_creation(self):
        """Test BoardConfigModification creation"""
        modification = BoardConfigModification(
            file_path="/test/BoardConfig.mk",
            variable="TEST_VAR",
            value="test_value",
            comment="Test modification"
        )
        
        self.assertEqual(modification.file_path, "/test/BoardConfig.mk")
        self.assertEqual(modification.variable, "TEST_VAR")
        self.assertEqual(modification.value, "test_value")
        self.assertEqual(modification.comment, "Test modification")

def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)

if __name__ == "__main__":
    run_tests()