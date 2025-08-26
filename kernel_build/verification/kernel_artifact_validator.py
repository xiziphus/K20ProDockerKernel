#!/usr/bin/env python3
"""
Kernel Artifact Validation System

This script validates compiled kernel artifacts for Docker-enabled K20 Pro kernel,
including format verification, architecture compatibility, and deployment readiness.

Requirements: 6.3, 6.4, 7.1
"""

import os
import sys
import subprocess
import json
import logging
import struct
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
import tempfile

# Optional import for file type detection
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory

@dataclass
class ArtifactInfo:
    """Information about a kernel artifact"""
    path: str
    size: int
    file_type: str
    architecture: str
    checksum: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]

@dataclass
class ValidationResult:
    """Result of kernel artifact validation"""
    success: bool
    artifacts: List[ArtifactInfo]
    overall_errors: List[str]
    overall_warnings: List[str]
    deployment_ready: bool
    report_file: str

class KernelArtifactValidator:
    """Validates kernel build artifacts for deployment readiness"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # Expected kernel artifacts
        self.expected_artifacts = {
            "kernel_image": {
                "patterns": ["Image", "Image.gz", "zImage"],
                "required": True,
                "description": "Main kernel image"
            },
            "device_tree": {
                "patterns": ["*.dtb", "sm8150-*.dtb", "raphael*.dtb"],
                "required": True,
                "description": "Device tree blob"
            },
            "system_map": {
                "patterns": ["System.map", "System.map-*"],
                "required": False,
                "description": "Kernel symbol map"
            },
            "config": {
                "patterns": [".config", "config-*"],
                "required": False,
                "description": "Kernel configuration"
            }
        }
        
        # Architecture validation
        self.target_architecture = "aarch64"
        self.target_endianness = "little"
        
        # File magic for detection
        if HAS_MAGIC:
            try:
                self.magic = magic.Magic(mime=True)
            except:
                self.magic = None
                self.logger.warning("python-magic initialization failed, file type detection limited")
        else:
            self.magic = None
            self.logger.warning("python-magic not available, file type detection limited")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for artifact validator"""
        logger = logging.getLogger("kernel_artifact_validator")
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
            
            log_file = log_dir / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    def detect_file_type(self, file_path: str) -> str:
        """Detect file type using magic numbers"""
        try:
            if self.magic:
                return self.magic.from_file(file_path)
            else:
                # Fallback to file command
                result = subprocess.run(
                    ['file', '--mime-type', file_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return result.stdout.split(':')[1].strip()
                else:
                    return "unknown"
        except Exception as e:
            self.logger.warning(f"Could not detect file type for {file_path}: {e}")
            return "unknown"
    
    def validate_elf_header(self, file_path: str) -> Tuple[bool, str, List[str], List[str]]:
        """Validate ELF header for architecture compatibility"""
        errors = []
        warnings = []
        architecture = "unknown"
        
        try:
            with open(file_path, 'rb') as f:
                # Read ELF header
                header = f.read(64)
                
                if len(header) < 16:
                    errors.append("File too small to be valid ELF")
                    return False, architecture, errors, warnings
                
                # Check ELF magic
                if header[:4] != b'\x7fELF':
                    # Not an ELF file, might be raw kernel image
                    warnings.append("Not an ELF file - might be raw kernel image")
                    return True, "raw", errors, warnings
                
                # Parse ELF header
                ei_class = header[4]  # 32-bit or 64-bit
                ei_data = header[5]   # Endianness
                e_machine = struct.unpack('<H' if ei_data == 1 else '>H', header[18:20])[0]
                
                # Validate class (should be 64-bit for ARM64)
                if ei_class == 1:
                    warnings.append("32-bit ELF detected, expected 64-bit for ARM64")
                elif ei_class == 2:
                    # 64-bit, good
                    pass
                else:
                    errors.append(f"Invalid ELF class: {ei_class}")
                
                # Validate endianness (should be little-endian)
                if ei_data == 1:
                    # Little-endian, good for ARM64
                    pass
                elif ei_data == 2:
                    warnings.append("Big-endian ELF detected, ARM64 typically uses little-endian")
                else:
                    errors.append(f"Invalid ELF endianness: {ei_data}")
                
                # Validate machine type
                if e_machine == 0xB7:  # EM_AARCH64
                    architecture = "aarch64"
                elif e_machine == 0x28:  # EM_ARM
                    architecture = "arm"
                    warnings.append("ARM 32-bit architecture detected, expected ARM64")
                elif e_machine == 0x3E:  # EM_X86_64
                    architecture = "x86_64"
                    errors.append("x86_64 architecture detected, expected ARM64")
                else:
                    architecture = f"unknown_0x{e_machine:x}"
                    errors.append(f"Unknown machine type: 0x{e_machine:x}")
                
                return len(errors) == 0, architecture, errors, warnings
                
        except Exception as e:
            errors.append(f"Error reading ELF header: {e}")
            return False, architecture, errors, warnings
    
    def validate_kernel_image(self, file_path: str) -> ArtifactInfo:
        """Validate kernel image file"""
        errors = []
        warnings = []
        
        file_path_obj = Path(file_path)
        
        # Basic file checks
        if not file_path_obj.exists():
            errors.append("File does not exist")
            return ArtifactInfo(
                path=file_path,
                size=0,
                file_type="missing",
                architecture="unknown",
                checksum="",
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        file_size = file_path_obj.stat().st_size
        file_type = self.detect_file_type(file_path)
        checksum = self.calculate_checksum(file_path)
        
        # Size validation
        if file_size == 0:
            errors.append("File is empty")
        elif file_size < 1024 * 1024:  # Less than 1MB
            warnings.append(f"File size is small for kernel image: {file_size} bytes")
        elif file_size > 100 * 1024 * 1024:  # More than 100MB
            warnings.append(f"File size is large for kernel image: {file_size} bytes")
        
        # Architecture validation
        is_valid_arch, architecture, arch_errors, arch_warnings = self.validate_elf_header(file_path)
        errors.extend(arch_errors)
        warnings.extend(arch_warnings)
        
        # File type specific validation
        if file_path_obj.name.endswith('.gz'):
            # Compressed kernel image
            if 'gzip' not in file_type.lower():
                warnings.append("File has .gz extension but doesn't appear to be gzip compressed")
        
        # Docker-specific kernel features validation
        if architecture == "aarch64" or architecture == "raw":
            # Try to check for Docker-required symbols (if it's not compressed)
            if not file_path_obj.name.endswith('.gz'):
                docker_features = self.check_docker_kernel_features(file_path)
                if not docker_features:
                    warnings.append("Could not verify Docker kernel features")
        
        is_valid = len(errors) == 0
        
        return ArtifactInfo(
            path=file_path,
            size=file_size,
            file_type=file_type,
            architecture=architecture,
            checksum=checksum,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def validate_device_tree(self, file_path: str) -> ArtifactInfo:
        """Validate device tree blob file"""
        errors = []
        warnings = []
        
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            errors.append("File does not exist")
            return ArtifactInfo(
                path=file_path,
                size=0,
                file_type="missing",
                architecture="unknown",
                checksum="",
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        file_size = file_path_obj.stat().st_size
        file_type = self.detect_file_type(file_path)
        checksum = self.calculate_checksum(file_path)
        
        # Size validation
        if file_size == 0:
            errors.append("File is empty")
        elif file_size < 1024:  # Less than 1KB
            warnings.append(f"DTB file is very small: {file_size} bytes")
        
        # DTB magic validation
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if len(header) >= 4:
                    # DTB magic number is 0xd00dfeed (big-endian)
                    magic = struct.unpack('>I', header[:4])[0]
                    if magic == 0xd00dfeed:
                        # Valid DTB magic
                        pass
                    else:
                        warnings.append(f"DTB magic number not found: 0x{magic:x}")
                else:
                    errors.append("File too small to contain DTB header")
        except Exception as e:
            warnings.append(f"Could not validate DTB header: {e}")
        
        # Check for K20 Pro specific content
        if 'raphael' not in file_path_obj.name.lower() and 'sm8150' not in file_path_obj.name.lower():
            warnings.append("DTB filename doesn't contain expected device identifiers (raphael/sm8150)")
        
        is_valid = len(errors) == 0
        
        return ArtifactInfo(
            path=file_path,
            size=file_size,
            file_type=file_type,
            architecture="device_tree",
            checksum=checksum,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def check_docker_kernel_features(self, kernel_path: str) -> bool:
        """Check if kernel contains Docker-required features"""
        try:
            # Use strings command to look for Docker-related symbols
            result = subprocess.run(
                ['strings', kernel_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return False
            
            strings_output = result.stdout.lower()
            
            # Look for Docker-related kernel features
            docker_features = [
                'cgroup',
                'namespace',
                'overlay',
                'bridge',
                'netfilter',
                'iptables'
            ]
            
            found_features = 0
            for feature in docker_features:
                if feature in strings_output:
                    found_features += 1
            
            # If we found at least half the features, consider it promising
            return found_features >= len(docker_features) // 2
            
        except Exception as e:
            self.logger.debug(f"Could not check Docker features: {e}")
            return False
    
    def find_kernel_artifacts(self, search_paths: List[str]) -> Dict[str, List[str]]:
        """Find kernel artifacts in specified paths"""
        found_artifacts = {
            "kernel_image": [],
            "device_tree": [],
            "system_map": [],
            "config": []
        }
        
        for search_path in search_paths:
            search_path_obj = Path(search_path)
            if not search_path_obj.exists():
                continue
            
            self.logger.info(f"Searching for artifacts in: {search_path}")
            
            # Search for each artifact type
            for artifact_type, config in self.expected_artifacts.items():
                for pattern in config["patterns"]:
                    if search_path_obj.is_file():
                        # Single file check
                        if search_path_obj.name == pattern or search_path_obj.match(pattern):
                            found_artifacts[artifact_type].append(str(search_path_obj))
                    else:
                        # Directory search
                        matches = list(search_path_obj.rglob(pattern))
                        for match in matches:
                            if match.is_file():
                                found_artifacts[artifact_type].append(str(match))
        
        return found_artifacts
    
    def validate_artifacts(self, artifacts: Dict[str, List[str]]) -> ValidationResult:
        """Validate all found artifacts"""
        validated_artifacts = []
        overall_errors = []
        overall_warnings = []
        
        # Validate each artifact
        for artifact_type, file_list in artifacts.items():
            config = self.expected_artifacts[artifact_type]
            
            if not file_list and config["required"]:
                overall_errors.append(f"Required artifact type missing: {config['description']}")
                continue
            
            for file_path in file_list:
                self.logger.info(f"Validating {artifact_type}: {file_path}")
                
                if artifact_type == "kernel_image":
                    artifact_info = self.validate_kernel_image(file_path)
                elif artifact_type == "device_tree":
                    artifact_info = self.validate_device_tree(file_path)
                else:
                    # Generic file validation
                    artifact_info = self.validate_generic_file(file_path)
                
                validated_artifacts.append(artifact_info)
                
                if artifact_info.errors:
                    overall_errors.extend([f"{file_path}: {error}" for error in artifact_info.errors])
                if artifact_info.warnings:
                    overall_warnings.extend([f"{file_path}: {warning}" for warning in artifact_info.warnings])
        
        # Determine deployment readiness
        deployment_ready = self.assess_deployment_readiness(validated_artifacts, overall_errors)
        
        # Generate report
        report_file = self.generate_validation_report(validated_artifacts, overall_errors, overall_warnings, deployment_ready)
        
        success = len(overall_errors) == 0
        
        return ValidationResult(
            success=success,
            artifacts=validated_artifacts,
            overall_errors=overall_errors,
            overall_warnings=overall_warnings,
            deployment_ready=deployment_ready,
            report_file=report_file
        )
    
    def validate_generic_file(self, file_path: str) -> ArtifactInfo:
        """Generic file validation"""
        errors = []
        warnings = []
        
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            errors.append("File does not exist")
            return ArtifactInfo(
                path=file_path,
                size=0,
                file_type="missing",
                architecture="unknown",
                checksum="",
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        file_size = file_path_obj.stat().st_size
        file_type = self.detect_file_type(file_path)
        checksum = self.calculate_checksum(file_path)
        
        if file_size == 0:
            errors.append("File is empty")
        
        is_valid = len(errors) == 0
        
        return ArtifactInfo(
            path=file_path,
            size=file_size,
            file_type=file_type,
            architecture="generic",
            checksum=checksum,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def assess_deployment_readiness(self, artifacts: List[ArtifactInfo], errors: List[str]) -> bool:
        """Assess if artifacts are ready for deployment"""
        # Must have at least one valid kernel image
        kernel_images = [a for a in artifacts if 'Image' in Path(a.path).name and a.is_valid]
        if not kernel_images:
            return False
        
        # Must have at least one valid device tree
        device_trees = [a for a in artifacts if a.path.endswith('.dtb') and a.is_valid]
        if not device_trees:
            return False
        
        # No critical errors
        if errors:
            return False
        
        return True
    
    def generate_validation_report(self, artifacts: List[ArtifactInfo], errors: List[str], 
                                 warnings: List[str], deployment_ready: bool) -> str:
        """Generate comprehensive validation report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("KERNEL ARTIFACT VALIDATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Summary
        report_lines.append("📋 VALIDATION SUMMARY")
        report_lines.append(f"   Total artifacts: {len(artifacts)}")
        report_lines.append(f"   Valid artifacts: {len([a for a in artifacts if a.is_valid])}")
        report_lines.append(f"   Errors: {len(errors)}")
        report_lines.append(f"   Warnings: {len(warnings)}")
        report_lines.append(f"   Deployment ready: {'✅ YES' if deployment_ready else '❌ NO'}")
        report_lines.append("")
        
        # Artifact details
        report_lines.append("🔍 ARTIFACT DETAILS")
        for artifact in artifacts:
            status = "✅ VALID" if artifact.is_valid else "❌ INVALID"
            report_lines.append(f"   {status} {Path(artifact.path).name}")
            report_lines.append(f"      Path: {artifact.path}")
            report_lines.append(f"      Size: {artifact.size:,} bytes")
            report_lines.append(f"      Type: {artifact.file_type}")
            report_lines.append(f"      Architecture: {artifact.architecture}")
            report_lines.append(f"      Checksum: {artifact.checksum[:16]}...")
            
            if artifact.errors:
                report_lines.append("      Errors:")
                for error in artifact.errors:
                    report_lines.append(f"        - {error}")
            
            if artifact.warnings:
                report_lines.append("      Warnings:")
                for warning in artifact.warnings:
                    report_lines.append(f"        - {warning}")
            
            report_lines.append("")
        
        # Overall errors
        if errors:
            report_lines.append("❌ OVERALL ERRORS")
            for error in errors:
                report_lines.append(f"   - {error}")
            report_lines.append("")
        
        # Overall warnings
        if warnings:
            report_lines.append("⚠️  OVERALL WARNINGS")
            for warning in warnings:
                report_lines.append(f"   - {warning}")
            report_lines.append("")
        
        # Deployment guidance
        report_lines.append("🚀 DEPLOYMENT GUIDANCE")
        if deployment_ready:
            report_lines.append("   ✅ Artifacts are ready for deployment")
            report_lines.append("   📱 You can proceed with flashing the kernel to your device")
            report_lines.append("   ⚠️  Always backup your current kernel before flashing")
        else:
            report_lines.append("   ❌ Artifacts are NOT ready for deployment")
            report_lines.append("   🔧 Please address the errors above before deploying")
            if not any('Image' in Path(a.path).name for a in artifacts if a.is_valid):
                report_lines.append("   📋 Missing valid kernel image - rebuild required")
            if not any(a.path.endswith('.dtb') for a in artifacts if a.is_valid):
                report_lines.append("   📋 Missing valid device tree - rebuild required")
        
        report_lines.append("")
        
        # Save report
        report_content = "\n".join(report_lines)
        
        try:
            report_dir = self.workspace_root / "kernel_build" / "logs"
            ensure_directory(str(report_dir))
            
            report_file = report_dir / f"artifact_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report_content)
            
            return str(report_file)
        except Exception as e:
            self.logger.error(f"Could not save validation report: {e}")
            return ""
    
    def run_validation(self, search_paths: List[str] = None) -> ValidationResult:
        """Run complete artifact validation"""
        if search_paths is None:
            # Default search paths
            search_paths = [
                str(self.workspace_root / "kernel_source" / "arch" / "arm64" / "boot"),
                str(self.workspace_root / "kernel_build" / "output"),
                str(self.workspace_root / "kernel_output"),
                str(self.workspace_root / "kernel_source")
            ]
        
        self.logger.info("🔍 Starting kernel artifact validation")
        self.logger.info(f"Search paths: {search_paths}")
        
        # Find artifacts
        artifacts = self.find_kernel_artifacts(search_paths)
        
        # Log found artifacts
        total_found = sum(len(files) for files in artifacts.values())
        self.logger.info(f"Found {total_found} artifacts")
        
        for artifact_type, files in artifacts.items():
            if files:
                self.logger.info(f"  {artifact_type}: {len(files)} files")
                for file_path in files:
                    self.logger.info(f"    - {file_path}")
        
        # Validate artifacts
        result = self.validate_artifacts(artifacts)
        
        # Print summary
        print(f"\n{'='*60}")
        print("KERNEL ARTIFACT VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Success: {'✅ YES' if result.success else '❌ NO'}")
        print(f"Deployment Ready: {'✅ YES' if result.deployment_ready else '❌ NO'}")
        print(f"Artifacts Validated: {len(result.artifacts)}")
        print(f"Errors: {len(result.overall_errors)}")
        print(f"Warnings: {len(result.overall_warnings)}")
        
        if result.report_file:
            print(f"Report: {result.report_file}")
        
        return result


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate kernel build artifacts for deployment"
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
    
    validator = KernelArtifactValidator()
    result = validator.run_validation(args.search_paths)
    
    sys.exit(0 if result.deployment_ready else 1)


if __name__ == '__main__':
    main()