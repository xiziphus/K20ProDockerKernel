#!/usr/bin/env python3
"""
Kernel Compilation Automation for Docker-enabled K20 Pro Kernel

This module handles automated kernel compilation with progress monitoring,
error reporting, and build artifact validation.
"""

import os
import sys
import subprocess
import threading
import time
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
import re

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory, backup_file
from build.toolchain_manager import ToolchainManager, ToolchainConfig

@dataclass
class BuildConfig:
    """Configuration for kernel build process"""
    source_path: str
    output_path: str
    config_file: str
    toolchain_config: str
    target_device: str = "raphael"
    parallel_jobs: int = 0  # 0 = auto-detect
    clean_build: bool = False
    verbose: bool = False

@dataclass
class BuildProgress:
    """Build progress tracking"""
    stage: str
    current_step: int
    total_steps: int
    percentage: float
    message: str
    start_time: datetime
    elapsed_time: float = 0.0

@dataclass
class BuildResult:
    """Build result information"""
    success: bool
    build_time: float
    output_files: List[str]
    errors: List[str]
    warnings: List[str]
    log_file: str

class KernelBuilder:
    """Automated kernel compilation system"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        self.toolchain_manager = ToolchainManager(str(self.workspace_root))
        
        # Build stages
        self.build_stages = [
            "preparation",
            "environment_setup", 
            "configuration",
            "compilation",
            "modules",
            "packaging",
            "validation"
        ]
        
        # Progress callback
        self.progress_callback: Optional[Callable[[BuildProgress], None]] = None
        
        # Build artifacts to validate
        self.expected_artifacts = [
            "arch/arm64/boot/Image",
            "arch/arm64/boot/Image.gz",
            "arch/arm64/boot/dts/qcom/sm8150-mtp.dtb"
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for kernel builder"""
        logger = logging.getLogger("kernel_builder")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_dir = self.workspace_root / "kernel_build" / "logs"
            ensure_directory(str(log_dir))
            
            log_file = log_dir / f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def set_progress_callback(self, callback: Callable[[BuildProgress], None]):
        """Set progress callback function"""
        self.progress_callback = callback
    
    def _update_progress(self, stage: str, step: int, total: int, message: str, start_time: datetime):
        """Update build progress"""
        percentage = (step / total) * 100 if total > 0 else 0
        elapsed = (datetime.now() - start_time).total_seconds()
        
        progress = BuildProgress(
            stage=stage,
            current_step=step,
            total_steps=total,
            percentage=percentage,
            message=message,
            start_time=start_time,
            elapsed_time=elapsed
        )
        
        self.logger.info(f"[{stage}] {message} ({step}/{total}) - {percentage:.1f}%")
        
        if self.progress_callback:
            self.progress_callback(progress)
    
    def detect_cpu_count(self) -> int:
        """Detect optimal number of parallel jobs"""
        try:
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            # Use CPU count + 1 for optimal performance
            return min(cpu_count + 1, 16)  # Cap at 16 to avoid overwhelming system
        except:
            return 4  # Safe default
    
    def load_build_config(self, config_file: str) -> BuildConfig:
        """Load build configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            return BuildConfig(
                source_path=config_data["source_path"],
                output_path=config_data["output_path"],
                config_file=config_data["config_file"],
                toolchain_config=config_data["toolchain_config"],
                target_device=config_data.get("target_device", "raphael"),
                parallel_jobs=config_data.get("parallel_jobs", 0),
                clean_build=config_data.get("clean_build", False),
                verbose=config_data.get("verbose", False)
            )
        except Exception as e:
            self.logger.error(f"Error loading build config: {e}")
            raise
    
    def save_build_config(self, config: BuildConfig, config_file: str):
        """Save build configuration to file"""
        config_data = {
            "source_path": config.source_path,
            "output_path": config.output_path,
            "config_file": config.config_file,
            "toolchain_config": config.toolchain_config,
            "target_device": config.target_device,
            "parallel_jobs": config.parallel_jobs,
            "clean_build": config.clean_build,
            "verbose": config.verbose
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def prepare_build_environment(self, config: BuildConfig, start_time: datetime) -> Tuple[Dict[str, str], ToolchainConfig]:
        """Prepare build environment and load toolchain"""
        self._update_progress("preparation", 1, 3, "Loading toolchain configuration", start_time)
        
        # Load toolchain configuration
        toolchain = self.toolchain_manager.load_toolchain_config(config.toolchain_config)
        if not toolchain:
            raise RuntimeError(f"Failed to load toolchain config: {config.toolchain_config}")
        
        self._update_progress("preparation", 2, 3, "Setting up environment variables", start_time)
        
        # Setup environment variables
        env_vars = self.toolchain_manager.setup_toolchain_environment(toolchain)
        
        # Add additional build variables
        env_vars.update({
            "KBUILD_BUILD_USER": "docker-kernel-builder",
            "KBUILD_BUILD_HOST": "build-system",
            "LOCALVERSION": "-docker-enabled"
        })
        
        # Set parallel jobs
        if config.parallel_jobs == 0:
            config.parallel_jobs = self.detect_cpu_count()
        
        self._update_progress("preparation", 3, 3, f"Environment prepared (using {config.parallel_jobs} parallel jobs)", start_time)
        
        return env_vars, toolchain
    
    def run_make_command(self, command: List[str], env_vars: Dict[str, str], 
                        cwd: str, timeout: int = 3600) -> Tuple[bool, str, str]:
        """Run make command with environment and capture output"""
        try:
            # Merge environment variables
            full_env = os.environ.copy()
            full_env.update(env_vars)
            
            self.logger.debug(f"Running command: {' '.join(command)}")
            self.logger.debug(f"Working directory: {cwd}")
            
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            output_lines = []
            
            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_lines.append(output.strip())
                    if self.logger.level <= logging.DEBUG:
                        self.logger.debug(output.strip())
            
            # Wait for process to complete
            return_code = process.wait(timeout=timeout)
            
            stdout = '\n'.join(output_lines)
            success = return_code == 0
            
            return success, stdout, ""
            
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def clean_build_directory(self, source_path: str, env_vars: Dict[str, str], start_time: datetime):
        """Clean build directory"""
        self._update_progress("preparation", 1, 1, "Cleaning build directory", start_time)
        
        clean_commands = [
            ["make", "clean"],
            ["make", "mrproper"]
        ]
        
        for i, cmd in enumerate(clean_commands):
            success, stdout, stderr = self.run_make_command(cmd, env_vars, source_path)
            if not success:
                self.logger.warning(f"Clean command failed: {' '.join(cmd)}")
                # Continue anyway, as clean failures are often not critical
    
    def configure_kernel(self, config: BuildConfig, env_vars: Dict[str, str], start_time: datetime) -> bool:
        """Configure kernel with defconfig"""
        self._update_progress("configuration", 1, 2, "Applying kernel configuration", start_time)
        
        # Copy defconfig to kernel source
        source_config_path = Path(config.source_path) / "arch" / "arm64" / "configs" / f"{config.target_device}_defconfig"
        
        if not Path(config.config_file).exists():
            raise RuntimeError(f"Configuration file not found: {config.config_file}")
        
        # Backup original defconfig if it exists
        if source_config_path.exists():
            backup_file(str(source_config_path))
        
        # Copy our configuration
        shutil.copy2(config.config_file, source_config_path)
        
        self._update_progress("configuration", 2, 2, "Running defconfig", start_time)
        
        # Run defconfig
        cmd = ["make", f"{config.target_device}_defconfig"]
        success, stdout, stderr = self.run_make_command(cmd, env_vars, config.source_path)
        
        if not success:
            self.logger.error(f"Kernel configuration failed: {stderr}")
            return False
        
        return True
    
    def compile_kernel(self, config: BuildConfig, env_vars: Dict[str, str], start_time: datetime) -> bool:
        """Compile kernel image"""
        self._update_progress("compilation", 1, 1, f"Compiling kernel with {config.parallel_jobs} jobs", start_time)
        
        # Build kernel image
        cmd = ["make", f"-j{config.parallel_jobs}", "Image", "Image.gz", "dtbs"]
        
        success, stdout, stderr = self.run_make_command(
            cmd, env_vars, config.source_path, timeout=7200  # 2 hours timeout
        )
        
        if not success:
            self.logger.error(f"Kernel compilation failed: {stderr}")
            return False
        
        return True
    
    def compile_modules(self, config: BuildConfig, env_vars: Dict[str, str], start_time: datetime) -> bool:
        """Compile kernel modules"""
        self._update_progress("modules", 1, 2, "Compiling kernel modules", start_time)
        
        # Build modules
        cmd = ["make", f"-j{config.parallel_jobs}", "modules"]
        success, stdout, stderr = self.run_make_command(
            cmd, env_vars, config.source_path, timeout=3600  # 1 hour timeout
        )
        
        if not success:
            self.logger.warning(f"Module compilation failed: {stderr}")
            # Modules failure is not always critical, continue
        
        self._update_progress("modules", 2, 2, "Installing modules", start_time)
        
        # Install modules to output directory
        modules_dir = Path(config.output_path) / "modules"
        ensure_directory(str(modules_dir))
        
        env_vars_with_install = env_vars.copy()
        env_vars_with_install["INSTALL_MOD_PATH"] = str(modules_dir)
        
        cmd = ["make", "modules_install"]
        success, stdout, stderr = self.run_make_command(
            cmd, env_vars_with_install, config.source_path
        )
        
        return True  # Continue even if module install fails
    
    def package_build_artifacts(self, config: BuildConfig, start_time: datetime) -> List[str]:
        """Package build artifacts"""
        self._update_progress("packaging", 1, 3, "Collecting build artifacts", start_time)
        
        source_path = Path(config.source_path)
        output_path = Path(config.output_path)
        ensure_directory(str(output_path))
        
        artifacts = []
        
        # Copy kernel images
        self._update_progress("packaging", 2, 3, "Copying kernel images", start_time)
        
        image_files = [
            "arch/arm64/boot/Image",
            "arch/arm64/boot/Image.gz"
        ]
        
        for image_file in image_files:
            src_file = source_path / image_file
            if src_file.exists():
                dst_file = output_path / Path(image_file).name
                shutil.copy2(src_file, dst_file)
                artifacts.append(str(dst_file))
                self.logger.info(f"Copied: {src_file} -> {dst_file}")
        
        # Copy device tree blobs
        self._update_progress("packaging", 3, 3, "Copying device tree files", start_time)
        
        dtb_dir = source_path / "arch" / "arm64" / "boot" / "dts" / "qcom"
        if dtb_dir.exists():
            dtb_output_dir = output_path / "dtbs"
            ensure_directory(str(dtb_output_dir))
            
            for dtb_file in dtb_dir.glob("*.dtb"):
                dst_file = dtb_output_dir / dtb_file.name
                shutil.copy2(dtb_file, dst_file)
                artifacts.append(str(dst_file))
        
        return artifacts
    
    def validate_build_artifacts(self, artifacts: List[str], start_time: datetime) -> Tuple[bool, List[str]]:
        """Validate build artifacts"""
        self._update_progress("validation", 1, 2, "Validating build artifacts", start_time)
        
        errors = []
        
        # Check if essential files exist
        essential_files = ["Image", "Image.gz"]
        for essential in essential_files:
            found = any(essential in artifact for artifact in artifacts)
            if not found:
                errors.append(f"Missing essential file: {essential}")
        
        # Check file sizes
        self._update_progress("validation", 2, 2, "Checking file sizes", start_time)
        
        for artifact in artifacts:
            if not Path(artifact).exists():
                errors.append(f"Artifact file missing: {artifact}")
                continue
            
            file_size = Path(artifact).stat().st_size
            if file_size == 0:
                errors.append(f"Artifact file is empty: {artifact}")
            elif file_size < 1024:  # Less than 1KB is suspicious
                errors.append(f"Artifact file suspiciously small: {artifact} ({file_size} bytes)")
        
        success = len(errors) == 0
        return success, errors
    
    def build_kernel(self, config: BuildConfig) -> BuildResult:
        """Main kernel build function"""
        start_time = datetime.now()
        errors = []
        warnings = []
        artifacts = []
        
        try:
            self.logger.info("Starting kernel build process")
            self.logger.info(f"Source: {config.source_path}")
            self.logger.info(f"Output: {config.output_path}")
            self.logger.info(f"Config: {config.config_file}")
            self.logger.info(f"Target: {config.target_device}")
            
            # Prepare environment
            env_vars, toolchain = self.prepare_build_environment(config, start_time)
            
            # Clean build if requested
            if config.clean_build:
                self.clean_build_directory(config.source_path, env_vars, start_time)
            
            # Configure kernel
            if not self.configure_kernel(config, env_vars, start_time):
                errors.append("Kernel configuration failed")
                raise RuntimeError("Configuration failed")
            
            # Compile kernel
            if not self.compile_kernel(config, env_vars, start_time):
                errors.append("Kernel compilation failed")
                raise RuntimeError("Compilation failed")
            
            # Compile modules
            self.compile_modules(config, env_vars, start_time)
            
            # Package artifacts
            artifacts = self.package_build_artifacts(config, start_time)
            
            # Validate artifacts
            validation_success, validation_errors = self.validate_build_artifacts(artifacts, start_time)
            if not validation_success:
                errors.extend(validation_errors)
            
            build_time = (datetime.now() - start_time).total_seconds()
            success = len(errors) == 0
            
            if success:
                self.logger.info(f"Kernel build completed successfully in {build_time:.1f} seconds")
            else:
                self.logger.error(f"Kernel build failed after {build_time:.1f} seconds")
            
            return BuildResult(
                success=success,
                build_time=build_time,
                output_files=artifacts,
                errors=errors,
                warnings=warnings,
                log_file=self.logger.handlers[1].baseFilename if len(self.logger.handlers) > 1 else ""
            )
            
        except Exception as e:
            build_time = (datetime.now() - start_time).total_seconds()
            errors.append(str(e))
            self.logger.error(f"Build failed with exception: {e}")
            
            return BuildResult(
                success=False,
                build_time=build_time,
                output_files=artifacts,
                errors=errors,
                warnings=warnings,
                log_file=self.logger.handlers[1].baseFilename if len(self.logger.handlers) > 1 else ""
            )

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kernel Compilation Automation")
    parser.add_argument("--config", required=True, help="Build configuration file")
    parser.add_argument("--clean", action="store_true", help="Clean build")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--jobs", type=int, default=0, help="Number of parallel jobs")
    
    args = parser.parse_args()
    
    builder = KernelBuilder()
    
    # Load configuration
    try:
        config = builder.load_build_config(args.config)
        
        # Override with command line arguments
        if args.clean:
            config.clean_build = True
        if args.verbose:
            config.verbose = True
        if args.jobs > 0:
            config.parallel_jobs = args.jobs
        
        # Build kernel
        result = builder.build_kernel(config)
        
        # Print results
        print(f"\nBuild Result:")
        print(f"Success: {result.success}")
        print(f"Build Time: {result.build_time:.1f} seconds")
        print(f"Output Files: {len(result.output_files)}")
        
        for artifact in result.output_files:
            print(f"  - {artifact}")
        
        if result.errors:
            print(f"Errors: {len(result.errors)}")
            for error in result.errors:
                print(f"  - {error}")
        
        if result.warnings:
            print(f"Warnings: {len(result.warnings)}")
            for warning in result.warnings:
                print(f"  - {warning}")
        
        if result.log_file:
            print(f"Log File: {result.log_file}")
        
        sys.exit(0 if result.success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()