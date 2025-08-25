#!/usr/bin/env python3
"""
Automated Installation Script for Docker-Enabled Kernel Build System

This script sets up the development environment prerequisites, checks dependencies,
and validates the environment for building Docker-enabled Android kernels.

Requirements: 6.4, 7.1
"""

import os
import sys
import subprocess
import shutil
import platform
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InstallationManager:
    """Manages the automated installation and setup process"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.kernel_build_root = self.project_root / "kernel_build"
        self.requirements = {
            'python': {'min_version': '3.6', 'required': True},
            'git': {'min_version': '2.0', 'required': True},
            'make': {'min_version': '4.0', 'required': True},
            'gcc': {'min_version': '7.0', 'required': True},
            'adb': {'min_version': '1.0', 'required': False},
            'fastboot': {'min_version': '1.0', 'required': False}
        }
        self.android_tools = {
            'android_ndk': {'required': True, 'env_var': 'ANDROID_NDK_ROOT'},
            'aosp_source': {'required': False, 'env_var': 'ANDROID_BUILD_TOP'}
        }
        
    def check_system_compatibility(self) -> bool:
        """Check if the system is compatible with the build requirements"""
        logger.info("🔍 Checking system compatibility...")
        
        system = platform.system().lower()
        if system not in ['linux', 'darwin']:
            logger.error(f"❌ Unsupported operating system: {system}")
            logger.error("This build system requires Linux or macOS")
            return False
            
        arch = platform.machine().lower()
        if arch not in ['x86_64', 'amd64', 'arm64', 'aarch64']:
            logger.warning(f"⚠️  Untested architecture: {arch}")
            logger.warning("Build may work but is not officially supported")
            
        logger.info(f"✅ System: {system} {arch}")
        return True
        
    def check_python_environment(self) -> bool:
        """Check Python version and required modules"""
        logger.info("🐍 Checking Python environment...")
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 6):
            logger.error(f"❌ Python {python_version.major}.{python_version.minor} is too old")
            logger.error("Python 3.6 or newer is required")
            return False
            
        logger.info(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Check required Python modules
        required_modules = ['json', 'subprocess', 'pathlib', 'tempfile', 'shutil']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
                
        if missing_modules:
            logger.error(f"❌ Missing Python modules: {', '.join(missing_modules)}")
            return False
            
        logger.info("✅ All required Python modules available")
        return True
        
    def check_command_availability(self, command: str) -> Tuple[bool, Optional[str]]:
        """Check if a command is available and get its version"""
        try:
            # Check if command exists
            if not shutil.which(command):
                return False, None
                
            # Try to get version
            version_commands = [
                [command, '--version'],
                [command, '-version'],
                [command, 'version'],
                [command, '-V']
            ]
            
            for cmd in version_commands:
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    if result.returncode == 0:
                        return True, result.stdout.strip()
                except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                    continue
                    
            return True, "version unknown"
            
        except Exception as e:
            logger.debug(f"Error checking {command}: {e}")
            return False, None
            
    def check_build_dependencies(self) -> Dict[str, bool]:
        """Check all build dependencies"""
        logger.info("🔧 Checking build dependencies...")
        
        results = {}
        
        for tool, config in self.requirements.items():
            available, version = self.check_command_availability(tool)
            results[tool] = available
            
            if available:
                logger.info(f"✅ {tool}: {version}")
            else:
                if config['required']:
                    logger.error(f"❌ {tool}: Not found (REQUIRED)")
                else:
                    logger.warning(f"⚠️  {tool}: Not found (optional)")
                    
        return results
        
    def check_android_tools(self) -> Dict[str, bool]:
        """Check Android development tools"""
        logger.info("📱 Checking Android development tools...")
        
        results = {}
        
        for tool, config in self.android_tools.items():
            env_var = config['env_var']
            path = os.environ.get(env_var)
            
            if path and os.path.exists(path):
                results[tool] = True
                logger.info(f"✅ {tool}: {path}")
            else:
                results[tool] = False
                if config['required']:
                    logger.error(f"❌ {tool}: Not found at ${env_var}")
                    logger.error(f"   Set {env_var} environment variable")
                else:
                    logger.warning(f"⚠️  {tool}: Not found at ${env_var} (optional)")
                    
        return results
        
    def setup_project_structure(self) -> bool:
        """Ensure project directory structure exists"""
        logger.info("📁 Setting up project structure...")
        
        required_dirs = [
            'kernel_build/backups',
            'kernel_build/logs',
            'kernel_build/output',
            'kernel_build/output/exported_configs'
        ]
        
        try:
            for dir_path in required_dirs:
                full_path = self.project_root / dir_path
                full_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {full_path}")
                
            logger.info("✅ Project structure ready")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create project structure: {e}")
            return False
            
    def validate_kernel_source(self) -> bool:
        """Validate kernel source files are present"""
        logger.info("🔍 Validating kernel source files...")
        
        required_files = [
            'files/raphael_defconfig',
            'files/kernel.diff',
            'files/aosp.diff',
            'files/cgroups.json',
            'files/dockerd.sh'
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
                
        if missing_files:
            logger.error("❌ Missing required kernel source files:")
            for file_path in missing_files:
                logger.error(f"   - {file_path}")
            return False
            
        logger.info("✅ All required kernel source files present")
        return True
        
    def validate_build_system(self) -> bool:
        """Validate the kernel build system components"""
        logger.info("🛠️  Validating build system components...")
        
        try:
            # Test import of key modules
            sys.path.insert(0, str(self.kernel_build_root))
            
            from config.config_manager import ConfigurationManager
            from patch.patch_engine import PatchEngine
            from patch.cpuset_handler import CpusetHandler
            
            logger.info("✅ Build system components validated")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Build system validation failed: {e}")
            logger.error("Some build system components are missing or broken")
            return False
            
    def create_environment_config(self) -> bool:
        """Create environment configuration file"""
        logger.info("⚙️  Creating environment configuration...")
        
        config = {
            'project_root': str(self.project_root),
            'kernel_build_root': str(self.kernel_build_root),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'system': platform.system(),
            'architecture': platform.machine(),
            'setup_timestamp': subprocess.run(['date'], capture_output=True, text=True).stdout.strip()
        }
        
        # Add tool availability
        build_deps = self.check_build_dependencies()
        android_tools = self.check_android_tools()
        
        config['dependencies'] = {
            'build_tools': build_deps,
            'android_tools': android_tools
        }
        
        try:
            config_file = self.kernel_build_root / 'environment_config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"✅ Environment config saved: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create environment config: {e}")
            return False
            
    def install_missing_dependencies(self) -> bool:
        """Attempt to install missing dependencies"""
        logger.info("📦 Checking for package manager to install dependencies...")
        
        system = platform.system().lower()
        
        if system == 'linux':
            # Check for common Linux package managers
            if shutil.which('apt-get'):
                return self._install_with_apt()
            elif shutil.which('yum'):
                return self._install_with_yum()
            elif shutil.which('pacman'):
                return self._install_with_pacman()
            else:
                logger.warning("⚠️  No supported package manager found")
                return False
                
        elif system == 'darwin':
            # macOS with Homebrew
            if shutil.which('brew'):
                return self._install_with_brew()
            else:
                logger.warning("⚠️  Homebrew not found. Install from https://brew.sh/")
                return False
                
        return False
        
    def _install_with_apt(self) -> bool:
        """Install dependencies using apt (Ubuntu/Debian)"""
        logger.info("📦 Installing dependencies with apt...")
        
        packages = ['build-essential', 'git', 'python3', 'python3-pip']
        
        try:
            cmd = ['sudo', 'apt-get', 'update']
            subprocess.run(cmd, check=True)
            
            cmd = ['sudo', 'apt-get', 'install', '-y'] + packages
            subprocess.run(cmd, check=True)
            
            logger.info("✅ Dependencies installed with apt")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install with apt: {e}")
            return False
            
    def _install_with_brew(self) -> bool:
        """Install dependencies using Homebrew (macOS)"""
        logger.info("📦 Installing dependencies with Homebrew...")
        
        packages = ['git', 'python3', 'make']
        
        try:
            for package in packages:
                cmd = ['brew', 'install', package]
                subprocess.run(cmd, check=True)
                
            logger.info("✅ Dependencies installed with Homebrew")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install with Homebrew: {e}")
            return False
            
    def _install_with_yum(self) -> bool:
        """Install dependencies using yum (RHEL/CentOS)"""
        logger.info("📦 Installing dependencies with yum...")
        
        packages = ['gcc', 'gcc-c++', 'make', 'git', 'python3', 'python3-pip']
        
        try:
            cmd = ['sudo', 'yum', 'install', '-y'] + packages
            subprocess.run(cmd, check=True)
            
            logger.info("✅ Dependencies installed with yum")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install with yum: {e}")
            return False
            
    def _install_with_pacman(self) -> bool:
        """Install dependencies using pacman (Arch Linux)"""
        logger.info("📦 Installing dependencies with pacman...")
        
        packages = ['base-devel', 'git', 'python', 'python-pip']
        
        try:
            cmd = ['sudo', 'pacman', '-S', '--noconfirm'] + packages
            subprocess.run(cmd, check=True)
            
            logger.info("✅ Dependencies installed with pacman")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install with pacman: {e}")
            return False
            
    def run_installation_tests(self) -> bool:
        """Run basic tests to verify installation"""
        logger.info("🧪 Running installation verification tests...")
        
        try:
            # Test configuration system
            sys.path.insert(0, str(self.kernel_build_root))
            from config.config_manager import ConfigurationManager
            
            config_manager = ConfigurationManager()
            logger.info("✅ Configuration system test passed")
            
            # Test patch system
            from patch.patch_engine import PatchEngine
            
            patch_engine = PatchEngine()
            logger.info("✅ Patch system test passed")
            
            # Test file utilities
            from utils.file_utils import FileUtils
            
            file_utils = FileUtils()
            logger.info("✅ File utilities test passed")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Installation verification failed: {e}")
            return False
            
    def generate_setup_report(self, results: Dict) -> str:
        """Generate a comprehensive setup report"""
        report = []
        report.append("=" * 60)
        report.append("DOCKER-ENABLED KERNEL BUILD SYSTEM - SETUP REPORT")
        report.append("=" * 60)
        report.append("")
        
        # System information
        report.append("📋 SYSTEM INFORMATION")
        report.append(f"   Operating System: {platform.system()} {platform.release()}")
        report.append(f"   Architecture: {platform.machine()}")
        report.append(f"   Python Version: {sys.version.split()[0]}")
        report.append("")
        
        # Dependency status
        report.append("🔧 DEPENDENCY STATUS")
        for category, deps in results.items():
            if isinstance(deps, dict):
                report.append(f"   {category.upper()}:")
                for tool, status in deps.items():
                    status_icon = "✅" if status else "❌"
                    report.append(f"     {status_icon} {tool}")
        report.append("")
        
        # Project structure
        report.append("📁 PROJECT STRUCTURE")
        report.append(f"   Project Root: {self.project_root}")
        report.append(f"   Kernel Build: {self.kernel_build_root}")
        report.append("")
        
        # Next steps
        report.append("🚀 NEXT STEPS")
        report.append("   1. Review any missing dependencies above")
        report.append("   2. Set up Android NDK if not already configured")
        report.append("   3. Run: python kernel_build/scripts/patch_integration.py apply-all")
        report.append("   4. Build kernel using your AOSP build system")
        report.append("")
        
        return "\n".join(report)
        
    def run_full_setup(self) -> bool:
        """Run the complete setup process"""
        logger.info("🚀 Starting Docker-Enabled Kernel Build System Setup")
        logger.info("=" * 60)
        
        results = {}
        success = True
        
        # System compatibility check
        if not self.check_system_compatibility():
            success = False
            
        # Python environment check
        if not self.check_python_environment():
            success = False
            
        # Build dependencies
        build_deps = self.check_build_dependencies()
        results['build_dependencies'] = build_deps
        
        # Android tools
        android_tools = self.check_android_tools()
        results['android_tools'] = android_tools
        
        # Project structure setup
        if not self.setup_project_structure():
            success = False
            
        # Kernel source validation
        if not self.validate_kernel_source():
            success = False
            
        # Build system validation
        if not self.validate_build_system():
            success = False
            
        # Create environment config
        if not self.create_environment_config():
            success = False
            
        # Run verification tests
        if success and not self.run_installation_tests():
            success = False
            
        # Generate and display report
        report = self.generate_setup_report(results)
        print("\n" + report)
        
        # Save report to file
        try:
            report_file = self.kernel_build_root / 'logs' / 'setup_report.txt'
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"📄 Setup report saved: {report_file}")
        except Exception as e:
            logger.warning(f"⚠️  Could not save setup report: {e}")
            
        if success:
            logger.info("🎉 Setup completed successfully!")
            logger.info("You can now run: python kernel_build/scripts/patch_integration.py apply-all")
        else:
            logger.error("❌ Setup completed with errors. Please review the report above.")
            
        return success


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automated installation script for Docker-enabled kernel build system"
    )
    parser.add_argument(
        '--install-deps', 
        action='store_true',
        help='Attempt to install missing dependencies automatically'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    installer = InstallationManager()
    
    # Attempt to install dependencies if requested
    if args.install_deps:
        installer.install_missing_dependencies()
        
    # Run full setup
    success = installer.run_full_setup()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()