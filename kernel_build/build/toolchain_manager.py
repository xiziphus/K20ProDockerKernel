#!/usr/bin/env python3
"""
Toolchain Setup Automation for Docker-enabled K20 Pro Kernel

This module handles detection, configuration, and validation of cross-compilation
toolchains required for building the Android kernel with Docker support.
"""

import os
import sys
import subprocess
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory, backup_file

@dataclass
class ToolchainConfig:
    """Configuration for cross-compilation toolchain"""
    name: str
    path: str
    prefix: str
    version: str
    arch: str
    validated: bool = False

class ToolchainManager:
    """Manages cross-compilation toolchain setup and validation"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # Common toolchain locations
        self.toolchain_paths = [
            "/opt/android-ndk",
            "/usr/local/android-ndk",
            "~/Android/Sdk/ndk",
            "~/android-ndk",
            "/android-ndk",
            "./toolchain"
        ]
        
        # Required tools for kernel compilation
        self.required_tools = [
            "gcc", "g++", "ld", "ar", "objcopy", "objdump", "strip", "nm"
        ]
        
        # Minimum versions
        self.min_versions = {
            "gcc": "4.9.0",
            "ndk": "r21"
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for toolchain manager"""
        logger = logging.getLogger("toolchain_manager")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def detect_android_ndk(self) -> Optional[str]:
        """Detect Android NDK installation"""
        self.logger.info("Detecting Android NDK installation...")
        
        # Check environment variables
        ndk_paths = [
            os.environ.get("ANDROID_NDK_ROOT"),
            os.environ.get("NDK_ROOT"),
            os.environ.get("ANDROID_NDK_HOME")
        ]
        
        # Add common installation paths
        ndk_paths.extend([
            os.path.expanduser(path) for path in self.toolchain_paths
        ])
        
        for ndk_path in ndk_paths:
            if not ndk_path:
                continue
                
            ndk_path = Path(ndk_path)
            if self._validate_ndk_path(ndk_path):
                self.logger.info(f"Found Android NDK at: {ndk_path}")
                return str(ndk_path)
        
        self.logger.warning("Android NDK not found in common locations")
        return None
    
    def _validate_ndk_path(self, ndk_path: Path) -> bool:
        """Validate NDK installation path"""
        if not ndk_path.exists():
            return False
        
        # Check for essential NDK files
        essential_files = [
            "toolchains",
            "platforms",
            "build/cmake/android.toolchain.cmake"
        ]
        
        for file_path in essential_files:
            if not (ndk_path / file_path).exists():
                return False
        
        return True
    
    def get_ndk_version(self, ndk_path: str) -> Optional[str]:
        """Get NDK version from installation"""
        try:
            # Try source.properties first (newer NDK versions)
            props_file = Path(ndk_path) / "source.properties"
            if props_file.exists():
                with open(props_file, 'r') as f:
                    for line in f:
                        if line.startswith("Pkg.Revision"):
                            return line.split("=")[1].strip()
            
            # Try RELEASE.TXT (older NDK versions)
            release_file = Path(ndk_path) / "RELEASE.TXT"
            if release_file.exists():
                with open(release_file, 'r') as f:
                    return f.readline().strip()
            
            return None
        except Exception as e:
            self.logger.error(f"Error reading NDK version: {e}")
            return None
    
    def find_toolchain_for_arch(self, ndk_path: str, arch: str = "aarch64") -> Optional[ToolchainConfig]:
        """Find appropriate toolchain for target architecture"""
        self.logger.info(f"Finding toolchain for architecture: {arch}")
        
        ndk_path = Path(ndk_path)
        toolchains_dir = ndk_path / "toolchains" / "llvm" / "prebuilt"
        
        # Find host platform directory
        host_platforms = ["linux-x86_64", "darwin-x86_64", "windows-x86_64"]
        host_dir = None
        
        for platform in host_platforms:
            platform_dir = toolchains_dir / platform
            if platform_dir.exists():
                host_dir = platform_dir
                break
        
        if not host_dir:
            self.logger.error("No compatible host platform found in NDK")
            return None
        
        # Configure toolchain based on architecture
        if arch == "aarch64":
            prefix = "aarch64-linux-android"
            toolchain_name = "aarch64-linux-android"
        elif arch == "arm":
            prefix = "arm-linux-androideabi"
            toolchain_name = "arm-linux-androideabi"
        else:
            self.logger.error(f"Unsupported architecture: {arch}")
            return None
        
        toolchain_config = ToolchainConfig(
            name=toolchain_name,
            path=str(host_dir / "bin"),
            prefix=prefix,
            version=self.get_ndk_version(str(ndk_path)) or "unknown",
            arch=arch
        )
        
        return toolchain_config
    
    def validate_toolchain(self, toolchain: ToolchainConfig) -> bool:
        """Validate toolchain installation and tools"""
        self.logger.info(f"Validating toolchain: {toolchain.name}")
        
        toolchain_path = Path(toolchain.path)
        if not toolchain_path.exists():
            self.logger.error(f"Toolchain path does not exist: {toolchain.path}")
            return False
        
        # Check for required tools
        missing_tools = []
        for tool in self.required_tools:
            tool_variants = [
                f"{toolchain.prefix}-{tool}",
                f"{toolchain.prefix}21-{tool}",  # API level specific
                f"{toolchain.prefix}29-{tool}",
                tool  # Generic tool name
            ]
            
            found = False
            for variant in tool_variants:
                tool_path = toolchain_path / variant
                if tool_path.exists() and os.access(tool_path, os.X_OK):
                    found = True
                    break
            
            if not found:
                missing_tools.append(tool)
        
        if missing_tools:
            self.logger.error(f"Missing tools in toolchain: {missing_tools}")
            return False
        
        # Test compiler functionality
        if not self._test_compiler(toolchain):
            return False
        
        toolchain.validated = True
        self.logger.info("Toolchain validation successful")
        return True
    
    def _test_compiler(self, toolchain: ToolchainConfig) -> bool:
        """Test compiler functionality with a simple compilation"""
        try:
            # Find the compiler
            compiler_variants = [
                f"{toolchain.prefix}-gcc",
                f"{toolchain.prefix}21-clang",
                f"{toolchain.prefix}29-clang"
            ]
            
            compiler_path = None
            toolchain_path = Path(toolchain.path)
            
            for variant in compiler_variants:
                candidate = toolchain_path / variant
                if candidate.exists():
                    compiler_path = str(candidate)
                    break
            
            if not compiler_path:
                self.logger.error("No suitable compiler found in toolchain")
                return False
            
            # Create a simple test program
            test_code = """
            int main() {
                return 0;
            }
            """
            
            test_dir = self.workspace_root / "kernel_build" / "build" / "test"
            ensure_directory(str(test_dir))
            
            test_file = test_dir / "test.c"
            output_file = test_dir / "test_output"
            
            # Write test code
            with open(test_file, 'w') as f:
                f.write(test_code)
            
            # Compile test program
            cmd = [compiler_path, str(test_file), "-o", str(output_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up
            if test_file.exists():
                test_file.unlink()
            if output_file.exists():
                output_file.unlink()
            
            if result.returncode == 0:
                self.logger.info("Compiler test successful")
                return True
            else:
                self.logger.error(f"Compiler test failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error testing compiler: {e}")
            return False
    
    def setup_toolchain_environment(self, toolchain: ToolchainConfig) -> Dict[str, str]:
        """Setup environment variables for toolchain"""
        env_vars = {
            "CROSS_COMPILE": f"{toolchain.prefix}-",
            "ARCH": "arm64" if toolchain.arch == "aarch64" else "arm",
            "TOOLCHAIN_PATH": toolchain.path,
            "TOOLCHAIN_PREFIX": toolchain.prefix,
            "CC": f"{toolchain.prefix}-gcc",
            "CXX": f"{toolchain.prefix}-g++",
            "LD": f"{toolchain.prefix}-ld",
            "AR": f"{toolchain.prefix}-ar",
            "OBJCOPY": f"{toolchain.prefix}-objcopy",
            "OBJDUMP": f"{toolchain.prefix}-objdump",
            "STRIP": f"{toolchain.prefix}-strip",
            "NM": f"{toolchain.prefix}-nm"
        }
        
        # Add toolchain to PATH
        current_path = os.environ.get("PATH", "")
        env_vars["PATH"] = f"{toolchain.path}:{current_path}"
        
        return env_vars
    
    def save_toolchain_config(self, toolchain: ToolchainConfig, config_file: str = None) -> str:
        """Save toolchain configuration to file"""
        if not config_file:
            config_dir = self.workspace_root / "kernel_build" / "build" / "config"
            ensure_directory(str(config_dir))
            config_file = str(config_dir / "toolchain_config.json")
        
        config_data = {
            "name": toolchain.name,
            "path": toolchain.path,
            "prefix": toolchain.prefix,
            "version": toolchain.version,
            "arch": toolchain.arch,
            "validated": toolchain.validated,
            "environment": self.setup_toolchain_environment(toolchain)
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        self.logger.info(f"Toolchain configuration saved to: {config_file}")
        return config_file
    
    def load_toolchain_config(self, config_file: str) -> Optional[ToolchainConfig]:
        """Load toolchain configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            toolchain = ToolchainConfig(
                name=config_data["name"],
                path=config_data["path"],
                prefix=config_data["prefix"],
                version=config_data["version"],
                arch=config_data["arch"],
                validated=config_data.get("validated", False)
            )
            
            return toolchain
        except Exception as e:
            self.logger.error(f"Error loading toolchain config: {e}")
            return None
    
    def auto_setup_toolchain(self, arch: str = "aarch64") -> Optional[ToolchainConfig]:
        """Automatically detect and setup toolchain"""
        self.logger.info("Starting automatic toolchain setup...")
        
        # Detect Android NDK
        ndk_path = self.detect_android_ndk()
        if not ndk_path:
            self.logger.error("Android NDK not found. Please install Android NDK.")
            return None
        
        # Find toolchain for architecture
        toolchain = self.find_toolchain_for_arch(ndk_path, arch)
        if not toolchain:
            self.logger.error(f"No suitable toolchain found for architecture: {arch}")
            return None
        
        # Validate toolchain
        if not self.validate_toolchain(toolchain):
            self.logger.error("Toolchain validation failed")
            return None
        
        # Save configuration
        self.save_toolchain_config(toolchain)
        
        self.logger.info("Toolchain setup completed successfully")
        return toolchain
    
    def get_toolchain_info(self, toolchain: ToolchainConfig) -> Dict:
        """Get detailed toolchain information"""
        info = {
            "name": toolchain.name,
            "path": toolchain.path,
            "prefix": toolchain.prefix,
            "version": toolchain.version,
            "architecture": toolchain.arch,
            "validated": toolchain.validated,
            "tools": {}
        }
        
        # Check individual tools
        toolchain_path = Path(toolchain.path)
        for tool in self.required_tools:
            tool_variants = [
                f"{toolchain.prefix}-{tool}",
                f"{toolchain.prefix}21-{tool}",
                f"{toolchain.prefix}29-{tool}"
            ]
            
            for variant in tool_variants:
                tool_path = toolchain_path / variant
                if tool_path.exists():
                    info["tools"][tool] = str(tool_path)
                    break
            else:
                info["tools"][tool] = "NOT_FOUND"
        
        return info

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Toolchain Setup Automation")
    parser.add_argument("--arch", default="aarch64", help="Target architecture")
    parser.add_argument("--ndk-path", help="Android NDK path")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing toolchain")
    parser.add_argument("--info", action="store_true", help="Show toolchain information")
    parser.add_argument("--config-file", help="Toolchain configuration file")
    
    args = parser.parse_args()
    
    manager = ToolchainManager()
    
    if args.info and args.config_file:
        # Show toolchain info from config file
        toolchain = manager.load_toolchain_config(args.config_file)
        if toolchain:
            info = manager.get_toolchain_info(toolchain)
            print(json.dumps(info, indent=2))
        return
    
    if args.validate_only and args.config_file:
        # Validate existing toolchain
        toolchain = manager.load_toolchain_config(args.config_file)
        if toolchain and manager.validate_toolchain(toolchain):
            print("Toolchain validation successful")
        else:
            print("Toolchain validation failed")
            sys.exit(1)
        return
    
    # Auto setup toolchain
    toolchain = manager.auto_setup_toolchain(args.arch)
    if toolchain:
        print("Toolchain setup completed successfully")
        info = manager.get_toolchain_info(toolchain)
        print(json.dumps(info, indent=2))
    else:
        print("Toolchain setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()