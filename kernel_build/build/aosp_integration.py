#!/usr/bin/env python3
"""
AOSP Integration Handler for Docker-enabled K20 Pro Kernel

This module handles AOSP-specific modifications, BoardConfig.mk integration,
and Android build system compatibility checks.
"""

import os
import sys
import subprocess
import shutil
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory, backup_file

@dataclass
class AOSPConfig:
    """Configuration for AOSP integration"""
    aosp_root: str
    device_tree_path: str
    kernel_source_path: str
    kernel_output_path: str
    target_device: str = "raphael"
    android_version: str = "11"
    build_variant: str = "userdebug"

@dataclass
class BoardConfigModification:
    """Board configuration modification"""
    file_path: str
    variable: str
    value: str
    comment: str = ""

class AOSPIntegrationHandler:
    """Handles AOSP integration for Docker-enabled kernel"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # AOSP-specific patches and modifications
        self.aosp_patches = [
            "files/aosp.diff",
            "files/kernel.diff"
        ]
        
        # Required BoardConfig.mk variables for Docker support
        self.board_config_vars = {
            "BOARD_KERNEL_CMDLINE": self._get_docker_kernel_cmdline(),
            "TARGET_KERNEL_CONFIG": "docker_raphael_defconfig",
            "BOARD_KERNEL_BASE": "0x00000000",
            "BOARD_KERNEL_PAGESIZE": "4096",
            "BOARD_KERNEL_TAGS_OFFSET": "0x00000100",
            "BOARD_RAMDISK_OFFSET": "0x01000000",
            "BOARD_KERNEL_OFFSET": "0x00008000",
            "BOARD_KERNEL_SECOND_OFFSET": "0x00f00000",
            "BOARD_DTB_OFFSET": "0x01f00000",
            "BOARD_KERNEL_SEPARATED_DT": "true",
            "BOARD_INCLUDE_DTB_IN_BOOTIMG": "true"
        }
        
        # SELinux policies for Docker support
        self.selinux_policies = [
            "allow untrusted_app self:capability { sys_admin };",
            "allow system_server kernel:system module_load;",
            "allow init kernel:system module_load;",
            "allow shell proc_net:file { read open };",
            "allow system_app proc_net:file { read open };"
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for AOSP integration handler"""
        logger = logging.getLogger("aosp_integration")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _get_docker_kernel_cmdline(self) -> str:
        """Get kernel command line parameters for Docker support"""
        cmdline_params = [
            "androidboot.hardware=qcom",
            "androidboot.console=ttyMSM0",
            "msm_rtb.filter=0x237",
            "ehci-hcd.park=3",
            "lpm_levels.sleep_disabled=1",
            "service_locator.enable=1",
            "androidboot.configfs=true",
            "androidboot.usbcontroller=a600000.dwc3",
            "swiotlb=2048",
            "cgroup_disable=pressure",
            "systemd.unified_cgroup_hierarchy=false"
        ]
        return " ".join(cmdline_params)
    
    def detect_aosp_environment(self, aosp_root: str = None) -> Optional[str]:
        """Detect AOSP build environment"""
        self.logger.info("Detecting AOSP build environment...")
        
        # Check common AOSP root locations
        aosp_paths = [
            aosp_root,
            os.environ.get("ANDROID_BUILD_TOP"),
            os.environ.get("TOP"),
            str(Path.cwd() / "aosp"),
            str(Path.home() / "aosp"),
            "/opt/aosp"
        ]
        
        for aosp_path in aosp_paths:
            if not aosp_path:
                continue
                
            aosp_path = Path(aosp_path)
            if self._validate_aosp_root(aosp_path):
                self.logger.info(f"Found AOSP environment at: {aosp_path}")
                return str(aosp_path)
        
        self.logger.warning("AOSP environment not found")
        return None
    
    def _validate_aosp_root(self, aosp_path: Path) -> bool:
        """Validate AOSP root directory"""
        if not aosp_path.exists():
            return False
        
        # Check for essential AOSP files and directories
        essential_paths = [
            "build/envsetup.sh",
            "build/make",
            "system",
            "frameworks",
            "device",
            "kernel"
        ]
        
        for path in essential_paths:
            if not (aosp_path / path).exists():
                return False
        
        return True
    
    def find_device_tree(self, aosp_root: str, device: str = "raphael") -> Optional[str]:
        """Find device tree directory in AOSP"""
        self.logger.info(f"Finding device tree for: {device}")
        
        aosp_path = Path(aosp_root)
        
        # Common device tree locations
        device_paths = [
            aosp_path / "device" / "xiaomi" / device,
            aosp_path / "device" / "qcom" / device,
            aosp_path / "vendor" / "xiaomi" / device,
            aosp_path / "device" / "xiaomi" / "sm8150-common",
        ]
        
        for device_path in device_paths:
            if device_path.exists() and (device_path / "BoardConfig.mk").exists():
                self.logger.info(f"Found device tree at: {device_path}")
                return str(device_path)
        
        self.logger.warning(f"Device tree not found for: {device}")
        return None
    
    def apply_aosp_patches(self, kernel_source: str) -> bool:
        """Apply AOSP-specific patches to kernel source"""
        self.logger.info("Applying AOSP patches...")
        
        kernel_path = Path(kernel_source)
        if not kernel_path.exists():
            self.logger.error(f"Kernel source not found: {kernel_source}")
            return False
        
        success = True
        
        for patch_file in self.aosp_patches:
            patch_path = self.workspace_root / patch_file
            
            if not patch_path.exists():
                self.logger.warning(f"Patch file not found: {patch_path}")
                continue
            
            self.logger.info(f"Applying patch: {patch_path}")
            
            # Apply patch using git apply or patch command
            if not self._apply_patch_file(str(patch_path), kernel_source):
                self.logger.error(f"Failed to apply patch: {patch_path}")
                success = False
        
        return success
    
    def _apply_patch_file(self, patch_file: str, target_dir: str) -> bool:
        """Apply a single patch file"""
        try:
            # Try git apply first
            cmd = ["git", "apply", "--check", patch_file]
            result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Patch can be applied cleanly
                cmd = ["git", "apply", patch_file]
                result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True)
                return result.returncode == 0
            else:
                # Try with patch command
                cmd = ["patch", "-p1", "--dry-run", "-i", patch_file]
                result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True)
                
                if result.returncode == 0:
                    cmd = ["patch", "-p1", "-i", patch_file]
                    result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True)
                    return result.returncode == 0
        
        except Exception as e:
            self.logger.error(f"Error applying patch: {e}")
        
        return False
    
    def modify_board_config(self, device_tree_path: str, modifications: Dict[str, str] = None) -> bool:
        """Modify BoardConfig.mk for Docker support"""
        self.logger.info("Modifying BoardConfig.mk...")
        
        board_config_path = Path(device_tree_path) / "BoardConfig.mk"
        
        if not board_config_path.exists():
            self.logger.error(f"BoardConfig.mk not found: {board_config_path}")
            return False
        
        # Backup original file
        backup_file(str(board_config_path))
        
        # Use provided modifications or defaults
        if modifications is None:
            modifications = self.board_config_vars
        
        try:
            # Read current content
            with open(board_config_path, 'r') as f:
                content = f.read()
            
            # Apply modifications
            modified_content = self._apply_board_config_modifications(content, modifications)
            
            # Write modified content
            with open(board_config_path, 'w') as f:
                f.write(modified_content)
            
            self.logger.info("BoardConfig.mk modified successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error modifying BoardConfig.mk: {e}")
            return False
    
    def _apply_board_config_modifications(self, content: str, modifications: Dict[str, str]) -> str:
        """Apply modifications to BoardConfig.mk content"""
        lines = content.split('\n')
        modified_lines = []
        added_vars = set()
        
        # Process existing lines
        for line in lines:
            line_modified = False
            
            for var, value in modifications.items():
                if line.strip().startswith(f"{var}"):
                    # Replace existing variable
                    modified_lines.append(f"{var} := {value}")
                    added_vars.add(var)
                    line_modified = True
                    break
            
            if not line_modified:
                modified_lines.append(line)
        
        # Add new variables that weren't found
        if added_vars != set(modifications.keys()):
            modified_lines.append("")
            modified_lines.append("# Docker-enabled kernel configuration")
            
            for var, value in modifications.items():
                if var not in added_vars:
                    modified_lines.append(f"{var} := {value}")
        
        return '\n'.join(modified_lines)
    
    def setup_selinux_policies(self, device_tree_path: str) -> bool:
        """Setup SELinux policies for Docker support"""
        self.logger.info("Setting up SELinux policies...")
        
        sepolicy_dir = Path(device_tree_path) / "sepolicy"
        if not sepolicy_dir.exists():
            sepolicy_dir.mkdir()
        
        # Create docker.te policy file
        docker_te_path = sepolicy_dir / "docker.te"
        
        try:
            with open(docker_te_path, 'w') as f:
                f.write("# SELinux policies for Docker support\n\n")
                for policy in self.selinux_policies:
                    f.write(f"{policy}\n")
            
            self.logger.info(f"SELinux policies written to: {docker_te_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up SELinux policies: {e}")
            return False
    
    def validate_android_compatibility(self, aosp_config: AOSPConfig) -> Tuple[bool, List[str]]:
        """Validate Android build system compatibility"""
        self.logger.info("Validating Android compatibility...")
        
        issues = []
        
        # Check AOSP root
        if not self._validate_aosp_root(Path(aosp_config.aosp_root)):
            issues.append(f"Invalid AOSP root: {aosp_config.aosp_root}")
        
        # Check device tree
        device_tree_path = Path(aosp_config.device_tree_path)
        if not device_tree_path.exists():
            issues.append(f"Device tree not found: {aosp_config.device_tree_path}")
        elif not (device_tree_path / "BoardConfig.mk").exists():
            issues.append("BoardConfig.mk not found in device tree")
        
        # Check kernel source
        kernel_path = Path(aosp_config.kernel_source_path)
        if not kernel_path.exists():
            issues.append(f"Kernel source not found: {aosp_config.kernel_source_path}")
        elif not (kernel_path / "Makefile").exists():
            issues.append("Kernel Makefile not found")
        
        # Check Android version compatibility
        if aosp_config.android_version not in ["10", "11", "12", "13"]:
            issues.append(f"Unsupported Android version: {aosp_config.android_version}")
        
        # Check build tools
        build_tools = ["make", "gcc", "python3"]
        for tool in build_tools:
            if not shutil.which(tool):
                issues.append(f"Required build tool not found: {tool}")
        
        success = len(issues) == 0
        return success, issues
    
    def generate_build_script(self, aosp_config: AOSPConfig, output_file: str) -> bool:
        """Generate AOSP build script for Docker-enabled kernel"""
        self.logger.info("Generating AOSP build script...")
        
        script_content = self._create_build_script_content(aosp_config)
        
        try:
            with open(output_file, 'w') as f:
                f.write(script_content)
            
            # Make script executable
            os.chmod(output_file, 0o755)
            
            self.logger.info(f"Build script generated: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating build script: {e}")
            return False
    
    def _create_build_script_content(self, aosp_config: AOSPConfig) -> str:
        """Create build script content"""
        return f"""#!/bin/bash
# AOSP Build Script for Docker-enabled K20 Pro Kernel
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

set -e

# Configuration
AOSP_ROOT="{aosp_config.aosp_root}"
DEVICE_TREE="{aosp_config.device_tree_path}"
KERNEL_SOURCE="{aosp_config.kernel_source_path}"
KERNEL_OUTPUT="{aosp_config.kernel_output_path}"
TARGET_DEVICE="{aosp_config.target_device}"
ANDROID_VERSION="{aosp_config.android_version}"
BUILD_VARIANT="{aosp_config.build_variant}"

echo "Starting AOSP build for Docker-enabled kernel..."
echo "Target: $TARGET_DEVICE"
echo "Android Version: $ANDROID_VERSION"
echo "Build Variant: $BUILD_VARIANT"

# Setup AOSP environment
cd "$AOSP_ROOT"
source build/envsetup.sh

# Choose target
lunch "$TARGET_DEVICE-$BUILD_VARIANT"

# Build kernel
echo "Building kernel..."
cd "$KERNEL_SOURCE"
make clean
make docker_raphael_defconfig
make -j$(nproc) Image Image.gz dtbs

# Copy kernel artifacts
echo "Copying kernel artifacts..."
mkdir -p "$KERNEL_OUTPUT"
cp arch/arm64/boot/Image "$KERNEL_OUTPUT/"
cp arch/arm64/boot/Image.gz "$KERNEL_OUTPUT/"
cp arch/arm64/boot/dts/qcom/*.dtb "$KERNEL_OUTPUT/"

# Build Android
echo "Building Android system..."
cd "$AOSP_ROOT"
make -j$(nproc) bootimage systemimage

echo "Build completed successfully!"
echo "Kernel artifacts: $KERNEL_OUTPUT"
echo "System images: $AOSP_ROOT/out/target/product/$TARGET_DEVICE"
"""
    
    def integrate_with_aosp(self, aosp_config: AOSPConfig) -> bool:
        """Complete AOSP integration process"""
        self.logger.info("Starting AOSP integration...")
        
        try:
            # Validate environment
            valid, issues = self.validate_android_compatibility(aosp_config)
            if not valid:
                self.logger.error("Android compatibility validation failed:")
                for issue in issues:
                    self.logger.error(f"  - {issue}")
                return False
            
            # Apply AOSP patches
            if not self.apply_aosp_patches(aosp_config.kernel_source_path):
                self.logger.error("Failed to apply AOSP patches")
                return False
            
            # Modify BoardConfig.mk
            if not self.modify_board_config(aosp_config.device_tree_path):
                self.logger.error("Failed to modify BoardConfig.mk")
                return False
            
            # Setup SELinux policies
            if not self.setup_selinux_policies(aosp_config.device_tree_path):
                self.logger.warning("Failed to setup SELinux policies (non-critical)")
            
            # Generate build script
            build_script = str(Path(aosp_config.aosp_root) / "build_docker_kernel.sh")
            if not self.generate_build_script(aosp_config, build_script):
                self.logger.warning("Failed to generate build script (non-critical)")
            
            self.logger.info("AOSP integration completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"AOSP integration failed: {e}")
            return False

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AOSP Integration Handler")
    parser.add_argument("--aosp-root", required=True, help="AOSP root directory")
    parser.add_argument("--device-tree", help="Device tree path")
    parser.add_argument("--kernel-source", required=True, help="Kernel source path")
    parser.add_argument("--kernel-output", required=True, help="Kernel output path")
    parser.add_argument("--target-device", default="raphael", help="Target device")
    parser.add_argument("--android-version", default="11", help="Android version")
    parser.add_argument("--build-variant", default="userdebug", help="Build variant")
    parser.add_argument("--validate-only", action="store_true", help="Only validate compatibility")
    
    args = parser.parse_args()
    
    handler = AOSPIntegrationHandler()
    
    # Detect AOSP environment if not provided
    aosp_root = handler.detect_aosp_environment(args.aosp_root)
    if not aosp_root:
        print("ERROR: AOSP environment not found")
        sys.exit(1)
    
    # Find device tree if not provided
    device_tree = args.device_tree
    if not device_tree:
        device_tree = handler.find_device_tree(aosp_root, args.target_device)
        if not device_tree:
            print(f"ERROR: Device tree not found for {args.target_device}")
            sys.exit(1)
    
    # Create AOSP configuration
    aosp_config = AOSPConfig(
        aosp_root=aosp_root,
        device_tree_path=device_tree,
        kernel_source_path=args.kernel_source,
        kernel_output_path=args.kernel_output,
        target_device=args.target_device,
        android_version=args.android_version,
        build_variant=args.build_variant
    )
    
    if args.validate_only:
        # Validate compatibility only
        valid, issues = handler.validate_android_compatibility(aosp_config)
        if valid:
            print("✅ Android compatibility validation passed")
        else:
            print("❌ Android compatibility validation failed:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
    else:
        # Full integration
        if handler.integrate_with_aosp(aosp_config):
            print("✅ AOSP integration completed successfully")
        else:
            print("❌ AOSP integration failed")
            sys.exit(1)

if __name__ == "__main__":
    main()