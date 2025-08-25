#!/usr/bin/env python3
"""
Kernel Source Setup Script

This script downloads and sets up the Android kernel source for Redmi K20 Pro (raphael)
with support for multiple ROM sources (LineageOS, PixelExperience, etc.).
"""

import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KernelSourceManager:
    """Manages kernel source download and setup"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.kernel_source_dir = self.project_root / "kernel_source"
        
        # Kernel source repositories
        self.kernel_repos = {
            'lineage-18.1': {
                'url': 'https://github.com/LineageOS/android_kernel_xiaomi_sm8150.git',
                'branch': 'lineage-18.1',
                'description': 'LineageOS 18.1 (Android 11) - Recommended',
                'android_version': '11',
                'stability': 'stable'
            },
            'lineage-19.1': {
                'url': 'https://github.com/LineageOS/android_kernel_xiaomi_sm8150.git',
                'branch': 'lineage-19.1',
                'description': 'LineageOS 19.1 (Android 12)',
                'android_version': '12',
                'stability': 'stable'
            },
            'lineage-20': {
                'url': 'https://github.com/LineageOS/android_kernel_xiaomi_sm8150.git',
                'branch': 'lineage-20',
                'description': 'LineageOS 20 (Android 13)',
                'android_version': '13',
                'stability': 'beta'
            }
        }
        
    def check_git_availability(self) -> bool:
        """Check if git is available"""
        if not shutil.which('git'):
            logger.error("❌ Git is not installed or not in PATH")
            return False
            
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"✅ Git available: {version}")
                return True
            else:
                logger.error("❌ Git not working properly")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking git: {e}")
            return False
            
    def list_available_sources(self) -> None:
        """List available kernel sources"""
        logger.info("📋 Available kernel sources:")
        logger.info("=" * 50)
        
        for key, repo in self.kernel_repos.items():
            stability_icon = "✅" if repo['stability'] == 'stable' else "🧪"
            logger.info(f"{stability_icon} {key}")
            logger.info(f"   Description: {repo['description']}")
            logger.info(f"   Android: {repo['android_version']}")
            logger.info(f"   Stability: {repo['stability']}")
            logger.info(f"   URL: {repo['url']}")
            logger.info("")
            
    def download_kernel_source(self, source_key: str, shallow: bool = True) -> bool:
        """Download kernel source from specified repository"""
        if source_key not in self.kernel_repos:
            logger.error(f"❌ Unknown kernel source: {source_key}")
            logger.info("Available sources:")
            for key in self.kernel_repos.keys():
                logger.info(f"  - {key}")
            return False
            
        repo_info = self.kernel_repos[source_key]
        logger.info(f"📥 Downloading kernel source: {source_key}")
        logger.info(f"Repository: {repo_info['url']}")
        logger.info(f"Branch: {repo_info['branch']}")
        
        # Remove existing kernel source if it exists
        if self.kernel_source_dir.exists():
            logger.info("🗑️  Removing existing kernel source...")
            shutil.rmtree(self.kernel_source_dir)
            
        # Create kernel source directory
        self.kernel_source_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Clone repository
            cmd = ['git', 'clone']
            
            if shallow:
                cmd.extend(['--depth', '1'])
                
            cmd.extend([
                '--branch', repo_info['branch'],
                repo_info['url'],
                str(self.kernel_source_dir)
            ])
            
            logger.info(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info("✅ Kernel source downloaded successfully")
                
                # Verify download
                if self.verify_kernel_source():
                    logger.info("✅ Kernel source verification passed")
                    return True
                else:
                    logger.error("❌ Kernel source verification failed")
                    return False
            else:
                logger.error("❌ Failed to download kernel source")
                logger.error(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Download timed out (10 minutes)")
            return False
        except Exception as e:
            logger.error(f"❌ Error downloading kernel source: {e}")
            return False
            
    def verify_kernel_source(self) -> bool:
        """Verify that kernel source was downloaded correctly"""
        logger.info("🔍 Verifying kernel source...")
        
        required_files = [
            'Makefile',
            'arch/arm64/Makefile',
            'arch/arm64/configs',
            'kernel/cgroup/cpuset.c'
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.kernel_source_dir / file_path
            if not full_path.exists():
                missing_files.append(file_path)
                
        if missing_files:
            logger.error("❌ Missing required files:")
            for file_path in missing_files:
                logger.error(f"   - {file_path}")
            return False
            
        # Check for raphael defconfig
        defconfig_paths = [
            'arch/arm64/configs/raphael_defconfig',
            'arch/arm64/configs/vendor/raphael_defconfig',
            'arch/arm64/configs/lineageos_raphael_defconfig'
        ]
        
        defconfig_found = False
        for defconfig_path in defconfig_paths:
            full_path = self.kernel_source_dir / defconfig_path
            if full_path.exists():
                logger.info(f"✅ Found defconfig: {defconfig_path}")
                defconfig_found = True
                break
                
        if not defconfig_found:
            logger.warning("⚠️  No raphael defconfig found in standard locations")
            logger.info("Available defconfigs:")
            
            configs_dir = self.kernel_source_dir / 'arch' / 'arm64' / 'configs'
            if configs_dir.exists():
                for config_file in configs_dir.glob('*defconfig'):
                    logger.info(f"   - {config_file.name}")
                    
        # Get kernel version
        try:
            makefile_path = self.kernel_source_dir / 'Makefile'
            with open(makefile_path, 'r') as f:
                makefile_content = f.read()
                
            version_lines = []
            for line in makefile_content.split('\n')[:10]:
                if line.startswith('VERSION') or line.startswith('PATCHLEVEL') or line.startswith('SUBLEVEL'):
                    version_lines.append(line.strip())
                    
            if version_lines:
                logger.info("📋 Kernel version info:")
                for line in version_lines:
                    logger.info(f"   {line}")
                    
        except Exception as e:
            logger.warning(f"⚠️  Could not read kernel version: {e}")
            
        logger.info("✅ Kernel source verification completed")
        return True
        
    def get_kernel_info(self) -> Optional[Dict]:
        """Get information about the current kernel source"""
        if not self.kernel_source_dir.exists():
            return None
            
        info = {
            'path': str(self.kernel_source_dir),
            'exists': True
        }
        
        try:
            # Get git information
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.kernel_source_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                info['remote_url'] = result.stdout.strip()
                
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.kernel_source_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                info['branch'] = result.stdout.strip()
                
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%H %s'],
                cwd=self.kernel_source_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                commit_info = result.stdout.strip()
                info['last_commit'] = commit_info
                
        except Exception as e:
            logger.debug(f"Could not get git info: {e}")
            
        return info
        
    def setup_build_environment(self) -> bool:
        """Set up build environment for kernel compilation"""
        logger.info("⚙️  Setting up build environment...")
        
        if not self.kernel_source_dir.exists():
            logger.error("❌ Kernel source not found")
            return False
            
        # Create build output directory
        build_output = self.project_root / "kernel_output"
        build_output.mkdir(exist_ok=True)
        
        # Set up environment variables
        env_vars = {
            'KERNEL_SOURCE': str(self.kernel_source_dir),
            'KERNEL_OUTPUT': str(build_output),
            'ARCH': 'arm64',
            'SUBARCH': 'arm64'
        }
        
        # Create environment setup script
        env_script = self.project_root / "setup_env.sh"
        with open(env_script, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Kernel build environment setup\n\n")
            
            for var, value in env_vars.items():
                f.write(f"export {var}='{value}'\n")
                
            f.write("\n# Add to PATH if needed\n")
            f.write("# export PATH=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH\n")
            f.write("\necho 'Kernel build environment configured'\n")
            f.write("echo 'Kernel source: $KERNEL_SOURCE'\n")
            f.write("echo 'Build output: $KERNEL_OUTPUT'\n")
            
        # Make script executable
        os.chmod(env_script, 0o755)
        
        logger.info(f"✅ Environment setup script created: {env_script}")
        logger.info("Run 'source setup_env.sh' to configure environment")
        
        return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Setup kernel source for Docker-enabled Android kernel"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available kernel sources')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download kernel source')
    download_parser.add_argument('source', help='Kernel source to download')
    download_parser.add_argument('--full', action='store_true', help='Full clone (not shallow)')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show current kernel source info')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup build environment')
    
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    if not args.command:
        parser.print_help()
        return
        
    manager = KernelSourceManager()
    
    if not manager.check_git_availability():
        sys.exit(1)
        
    if args.command == 'list':
        manager.list_available_sources()
        
    elif args.command == 'download':
        success = manager.download_kernel_source(
            args.source,
            shallow=not args.full
        )
        if success:
            manager.setup_build_environment()
        sys.exit(0 if success else 1)
        
    elif args.command == 'info':
        info = manager.get_kernel_info()
        if info:
            logger.info("📋 Current kernel source info:")
            for key, value in info.items():
                logger.info(f"   {key}: {value}")
        else:
            logger.info("No kernel source found")
            
    elif args.command == 'setup':
        success = manager.setup_build_environment()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()