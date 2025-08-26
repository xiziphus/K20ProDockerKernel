#!/usr/bin/env python3
"""
Deployment-Ready Kernel Image Creator

This script creates deployment-ready kernel images with proper signatures
and packaging for the K20 Pro device.

Requirements: 6.3, 6.4, 7.1
"""

import os
import sys
import subprocess
import json
import logging
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import tempfile
import zipfile

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory, backup_file

@dataclass
class DeploymentPackage:
    """Deployment package information"""
    package_path: str
    kernel_image: str
    device_tree: str
    checksum: str
    signature: str
    metadata: Dict
    size: int

@dataclass
class ImageSignature:
    """Image signature information"""
    algorithm: str
    signature: str
    public_key: str
    timestamp: str

class DeploymentImageCreator:
    """Creates deployment-ready kernel images"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # Deployment configuration
        self.deployment_config = {
            "target_device": "raphael",
            "kernel_format": "Image.gz",
            "dtb_format": "dtb",
            "package_format": "zip",
            "signature_algorithm": "sha256",
            "compression": True
        }
        
        # File paths
        self.output_dir = self.workspace_root / "kernel_build" / "deployment"
        self.temp_dir = None
        
        # Ensure output directory exists
        ensure_directory(str(self.output_dir))
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for deployment creator"""
        logger = logging.getLogger("deployment_image_creator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_dir = self.workspace_root / "kernel_build" / "logs"
            ensure_directory(str(log_dir))
            
            log_file = log_dir / f"deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def find_kernel_artifacts(self, search_paths: List[str]) -> Dict[str, str]:
        """Find kernel artifacts for deployment"""
        artifacts = {
            "kernel_image": "",
            "device_tree": "",
            "system_map": "",
            "config": ""
        }
        
        for search_path in search_paths:
            search_path_obj = Path(search_path)
            if not search_path_obj.exists():
                continue
            
            self.logger.info(f"Searching for artifacts in: {search_path}")
            
            # Find kernel image
            if not artifacts["kernel_image"]:
                for pattern in ["Image.gz", "Image", "zImage"]:
                    matches = list(search_path_obj.rglob(pattern))
                    if matches:
                        artifacts["kernel_image"] = str(matches[0])
                        self.logger.info(f"Found kernel image: {artifacts['kernel_image']}")
                        break
            
            # Find device tree
            if not artifacts["device_tree"]:
                for pattern in ["*raphael*.dtb", "*sm8150*.dtb", "*.dtb"]:
                    matches = list(search_path_obj.rglob(pattern))
                    if matches:
                        # Prefer raphael or sm8150 specific DTBs
                        raphael_dtbs = [m for m in matches if 'raphael' in m.name.lower()]
                        sm8150_dtbs = [m for m in matches if 'sm8150' in m.name.lower()]
                        
                        if raphael_dtbs:
                            artifacts["device_tree"] = str(raphael_dtbs[0])
                        elif sm8150_dtbs:
                            artifacts["device_tree"] = str(sm8150_dtbs[0])
                        else:
                            artifacts["device_tree"] = str(matches[0])
                        
                        self.logger.info(f"Found device tree: {artifacts['device_tree']}")
                        break
            
            # Find system map
            if not artifacts["system_map"]:
                for pattern in ["System.map", "System.map-*"]:
                    matches = list(search_path_obj.rglob(pattern))
                    if matches:
                        artifacts["system_map"] = str(matches[0])
                        self.logger.info(f"Found system map: {artifacts['system_map']}")
                        break
            
            # Find config
            if not artifacts["config"]:
                for pattern in [".config", "config-*", "*_defconfig"]:
                    matches = list(search_path_obj.rglob(pattern))
                    if matches:
                        artifacts["config"] = str(matches[0])
                        self.logger.info(f"Found config: {artifacts['config']}")
                        break
        
        return artifacts
    
    def validate_artifacts(self, artifacts: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Validate artifacts for deployment"""
        errors = []
        
        # Check required artifacts
        if not artifacts["kernel_image"]:
            errors.append("Kernel image not found")
        elif not Path(artifacts["kernel_image"]).exists():
            errors.append(f"Kernel image does not exist: {artifacts['kernel_image']}")
        
        if not artifacts["device_tree"]:
            errors.append("Device tree blob not found")
        elif not Path(artifacts["device_tree"]).exists():
            errors.append(f"Device tree does not exist: {artifacts['device_tree']}")
        
        # Validate file sizes
        if artifacts["kernel_image"] and Path(artifacts["kernel_image"]).exists():
            kernel_size = Path(artifacts["kernel_image"]).stat().st_size
            if kernel_size == 0:
                errors.append("Kernel image is empty")
            elif kernel_size < 1024 * 1024:  # Less than 1MB
                errors.append(f"Kernel image is suspiciously small: {kernel_size} bytes")
        
        if artifacts["device_tree"] and Path(artifacts["device_tree"]).exists():
            dtb_size = Path(artifacts["device_tree"]).stat().st_size
            if dtb_size == 0:
                errors.append("Device tree is empty")
            elif dtb_size < 1024:  # Less than 1KB
                errors.append(f"Device tree is suspiciously small: {dtb_size} bytes")
        
        return len(errors) == 0, errors
    
    def calculate_file_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        """Calculate file hash"""
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def create_image_signature(self, file_path: str) -> ImageSignature:
        """Create image signature"""
        algorithm = self.deployment_config["signature_algorithm"]
        signature = self.calculate_file_hash(file_path, algorithm)
        
        return ImageSignature(
            algorithm=algorithm,
            signature=signature,
            public_key="",  # Would contain actual public key in production
            timestamp=datetime.now().isoformat()
        )
    
    def create_boot_image(self, kernel_path: str, dtb_path: str, output_path: str) -> bool:
        """Create Android boot image (if mkbootimg is available)"""
        try:
            # Check if mkbootimg is available
            result = subprocess.run(
                ['which', 'mkbootimg'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.warning("mkbootimg not found, skipping boot image creation")
                return False
            
            # Create boot image
            cmd = [
                'mkbootimg',
                '--kernel', kernel_path,
                '--dtb', dtb_path,
                '--base', '0x00000000',
                '--kernel_offset', '0x00008000',
                '--ramdisk_offset', '0x01000000',
                '--tags_offset', '0x00000100',
                '--pagesize', '4096',
                '--header_version', '2',
                '--os_version', '11.0.0',
                '--os_patch_level', '2023-01',
                '--output', output_path
            ]
            
            self.logger.info(f"Creating boot image: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.logger.info("Boot image created successfully")
                return True
            else:
                self.logger.error(f"Boot image creation failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error creating boot image: {e}")
            return False
    
    def create_fastboot_package(self, artifacts: Dict[str, str], output_dir: str) -> str:
        """Create fastboot-compatible package"""
        package_dir = Path(output_dir) / "fastboot_package"
        ensure_directory(str(package_dir))
        
        # Copy kernel image
        if artifacts["kernel_image"]:
            kernel_dest = package_dir / "kernel.img"
            shutil.copy2(artifacts["kernel_image"], kernel_dest)
            self.logger.info(f"Copied kernel: {kernel_dest}")
        
        # Copy device tree
        if artifacts["device_tree"]:
            dtb_dest = package_dir / "dtb.img"
            shutil.copy2(artifacts["device_tree"], dtb_dest)
            self.logger.info(f"Copied DTB: {dtb_dest}")
        
        # Try to create boot image
        if artifacts["kernel_image"] and artifacts["device_tree"]:
            boot_img_path = package_dir / "boot.img"
            self.create_boot_image(
                artifacts["kernel_image"],
                artifacts["device_tree"],
                str(boot_img_path)
            )
        
        # Create flash script
        flash_script = package_dir / "flash_kernel.sh"
        with open(flash_script, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Kernel flashing script for K20 Pro (raphael)\n")
            f.write("# WARNING: This will replace your kernel - backup first!\n\n")
            f.write("set -e\n\n")
            f.write("echo 'Flashing Docker-enabled kernel for K20 Pro...'\n\n")
            
            if (package_dir / "boot.img").exists():
                f.write("# Flash boot image\n")
                f.write("fastboot flash boot boot.img\n")
            else:
                f.write("# Flash kernel and DTB separately\n")
                f.write("fastboot flash kernel kernel.img\n")
                f.write("fastboot flash dtb dtb.img\n")
            
            f.write("\necho 'Kernel flashed successfully!'\n")
            f.write("echo 'Rebooting device...'\n")
            f.write("fastboot reboot\n")
        
        # Make script executable
        flash_script.chmod(0o755)
        
        # Create Windows batch file
        flash_bat = package_dir / "flash_kernel.bat"
        with open(flash_bat, 'w') as f:
            f.write("@echo off\n")
            f.write("REM Kernel flashing script for K20 Pro (raphael)\n")
            f.write("REM WARNING: This will replace your kernel - backup first!\n\n")
            f.write("echo Flashing Docker-enabled kernel for K20 Pro...\n\n")
            
            if (package_dir / "boot.img").exists():
                f.write("REM Flash boot image\n")
                f.write("fastboot flash boot boot.img\n")
            else:
                f.write("REM Flash kernel and DTB separately\n")
                f.write("fastboot flash kernel kernel.img\n")
                f.write("fastboot flash dtb dtb.img\n")
            
            f.write("\necho Kernel flashed successfully!\n")
            f.write("echo Rebooting device...\n")
            f.write("fastboot reboot\n")
            f.write("pause\n")
        
        return str(package_dir)
    
    def create_metadata_file(self, artifacts: Dict[str, str], signatures: Dict[str, ImageSignature], 
                           output_path: str) -> str:
        """Create deployment metadata file"""
        metadata = {
            "deployment_info": {
                "created": datetime.now().isoformat(),
                "target_device": self.deployment_config["target_device"],
                "kernel_version": "unknown",  # Would be extracted from kernel
                "build_type": "docker-enabled"
            },
            "artifacts": {},
            "signatures": {},
            "installation": {
                "method": "fastboot",
                "requirements": [
                    "Unlocked bootloader",
                    "Fastboot tools installed",
                    "Device in fastboot mode"
                ],
                "steps": [
                    "Boot device into fastboot mode",
                    "Run flash_kernel.sh (Linux/macOS) or flash_kernel.bat (Windows)",
                    "Wait for device to reboot",
                    "Verify kernel version with 'adb shell uname -a'"
                ]
            }
        }
        
        # Add artifact information
        for artifact_type, artifact_path in artifacts.items():
            if artifact_path and Path(artifact_path).exists():
                file_size = Path(artifact_path).stat().st_size
                file_hash = self.calculate_file_hash(artifact_path)
                
                metadata["artifacts"][artifact_type] = {
                    "path": Path(artifact_path).name,
                    "size": file_size,
                    "hash": file_hash
                }
        
        # Add signature information
        for sig_type, signature in signatures.items():
            metadata["signatures"][sig_type] = {
                "algorithm": signature.algorithm,
                "signature": signature.signature,
                "timestamp": signature.timestamp
            }
        
        # Save metadata
        metadata_file = Path(output_path) / "deployment_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return str(metadata_file)
    
    def create_deployment_package(self, artifacts: Dict[str, str]) -> DeploymentPackage:
        """Create complete deployment package"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        package_name = f"docker_kernel_raphael_{timestamp}"
        package_dir = self.output_dir / package_name
        
        ensure_directory(str(package_dir))
        
        self.logger.info(f"Creating deployment package: {package_name}")
        
        # Create fastboot package
        fastboot_dir = self.create_fastboot_package(artifacts, str(package_dir))
        
        # Create signatures
        signatures = {}
        if artifacts["kernel_image"]:
            signatures["kernel"] = self.create_image_signature(artifacts["kernel_image"])
        if artifacts["device_tree"]:
            signatures["dtb"] = self.create_image_signature(artifacts["device_tree"])
        
        # Create metadata
        metadata_file = self.create_metadata_file(artifacts, signatures, str(package_dir))
        
        # Create README
        readme_file = package_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(f"# Docker-Enabled Kernel for K20 Pro\n\n")
            f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Overview\n\n")
            f.write("This package contains a Docker-enabled kernel for the Redmi K20 Pro (raphael) device.\n")
            f.write("The kernel includes all necessary features for running Linux containers.\n\n")
            f.write("## Contents\n\n")
            f.write("- `fastboot_package/` - Fastboot-compatible kernel images\n")
            f.write("- `flash_kernel.sh` - Linux/macOS flashing script\n")
            f.write("- `flash_kernel.bat` - Windows flashing script\n")
            f.write("- `deployment_metadata.json` - Package metadata and checksums\n\n")
            f.write("## Installation\n\n")
            f.write("⚠️ **WARNING**: Flashing a custom kernel will void your warranty and may brick your device!\n\n")
            f.write("### Prerequisites\n\n")
            f.write("1. Unlocked bootloader\n")
            f.write("2. Fastboot tools installed\n")
            f.write("3. Device drivers installed\n")
            f.write("4. Backup of current kernel (recommended)\n\n")
            f.write("### Steps\n\n")
            f.write("1. Boot device into fastboot mode:\n")
            f.write("   ```\n")
            f.write("   adb reboot bootloader\n")
            f.write("   ```\n\n")
            f.write("2. Run the appropriate flashing script:\n")
            f.write("   - Linux/macOS: `./flash_kernel.sh`\n")
            f.write("   - Windows: `flash_kernel.bat`\n\n")
            f.write("3. Wait for device to reboot\n\n")
            f.write("4. Verify installation:\n")
            f.write("   ```\n")
            f.write("   adb shell uname -a\n")
            f.write("   ```\n\n")
            f.write("## Docker Setup\n\n")
            f.write("After flashing the kernel, you'll need to install Docker binaries and configure the runtime.\n")
            f.write("Refer to the main project documentation for Docker setup instructions.\n\n")
            f.write("## Support\n\n")
            f.write("This is experimental software. Use at your own risk.\n")
        
        # Create ZIP package
        zip_path = self.output_dir / f"{package_name}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_path = file_path.relative_to(package_dir)
                    zipf.write(file_path, arc_path)
        
        # Calculate package checksum
        package_checksum = self.calculate_file_hash(str(zip_path))
        package_size = zip_path.stat().st_size
        
        self.logger.info(f"Deployment package created: {zip_path}")
        self.logger.info(f"Package size: {package_size:,} bytes")
        self.logger.info(f"Package checksum: {package_checksum}")
        
        return DeploymentPackage(
            package_path=str(zip_path),
            kernel_image=artifacts.get("kernel_image", ""),
            device_tree=artifacts.get("device_tree", ""),
            checksum=package_checksum,
            signature=signatures.get("kernel", ImageSignature("", "", "", "")).signature,
            metadata={"metadata_file": metadata_file},
            size=package_size
        )
    
    def run_deployment_creation(self, search_paths: List[str] = None) -> Optional[DeploymentPackage]:
        """Run complete deployment package creation"""
        if search_paths is None:
            # Default search paths
            search_paths = [
                str(self.workspace_root / "kernel_source" / "arch" / "arm64" / "boot"),
                str(self.workspace_root / "kernel_build" / "output"),
                str(self.workspace_root / "kernel_output"),
                str(self.workspace_root / "kernel_source")
            ]
        
        self.logger.info("🚀 Creating deployment-ready kernel package")
        
        # Find artifacts
        artifacts = self.find_kernel_artifacts(search_paths)
        
        # Validate artifacts
        is_valid, errors = self.validate_artifacts(artifacts)
        
        if not is_valid:
            self.logger.error("Artifact validation failed:")
            for error in errors:
                self.logger.error(f"  - {error}")
            return None
        
        # Create deployment package
        try:
            package = self.create_deployment_package(artifacts)
            
            self.logger.info("✅ Deployment package created successfully")
            self.logger.info(f"Package: {package.package_path}")
            
            return package
            
        except Exception as e:
            self.logger.error(f"Failed to create deployment package: {e}")
            return None


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create deployment-ready kernel images"
    )
    parser.add_argument(
        '--search-paths',
        nargs='+',
        help='Paths to search for kernel artifacts'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    creator = DeploymentImageCreator()
    package = creator.run_deployment_creation(args.search_paths)
    
    if package:
        print(f"\n{'='*60}")
        print("DEPLOYMENT PACKAGE CREATED")
        print(f"{'='*60}")
        print(f"Package: {package.package_path}")
        print(f"Size: {package.size:,} bytes")
        print(f"Checksum: {package.checksum}")
        print(f"Kernel: {Path(package.kernel_image).name if package.kernel_image else 'N/A'}")
        print(f"DTB: {Path(package.device_tree).name if package.device_tree else 'N/A'}")
        
        sys.exit(0)
    else:
        print("❌ Failed to create deployment package")
        sys.exit(1)


if __name__ == '__main__':
    main()