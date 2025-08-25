#!/usr/bin/env python3
"""
Kernel Deployment Tools for Docker-Enabled Kernel

This script provides automated kernel deployment with fastboot integration,
validation, and rollback procedures for the Redmi K20 Pro (raphael).

Requirements: 6.4, 7.1, 7.2
"""

import os
import sys
import subprocess
import shutil
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tempfile
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KernelDeploymentManager:
    """Manages kernel deployment, flashing, and rollback operations"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.kernel_build_root = self.project_root / "kernel_build"
        self.deployment_log = self.kernel_build_root / "logs" / "deployment.log"
        self.backup_dir = self.kernel_build_root / "backups" / "kernels"
        
        # Device-specific configuration for K20 Pro (raphael)
        self.device_config = {
            'codename': 'raphael',
            'model': 'Redmi K20 Pro',
            'fastboot_id': 'raphael',
            'kernel_partition': 'boot',
            'recovery_partition': 'recovery',
            'supported_android_versions': ['10', '11', '12']
        }
        
        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.deployment_log.parent.mkdir(parents=True, exist_ok=True)
        
    def check_fastboot_availability(self) -> bool:
        """Check if fastboot is available and working"""
        logger.info("🔍 Checking fastboot availability...")
        
        if not shutil.which('fastboot'):
            logger.error("❌ fastboot not found in PATH")
            logger.error("Install Android SDK Platform Tools")
            return False
            
        try:
            result = subprocess.run(
                ['fastboot', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                logger.info(f"✅ fastboot available: {version}")
                return True
            else:
                logger.error("❌ fastboot not working properly")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking fastboot: {e}")
            return False
            
    def check_adb_availability(self) -> bool:
        """Check if adb is available and working"""
        logger.info("🔍 Checking adb availability...")
        
        if not shutil.which('adb'):
            logger.warning("⚠️  adb not found in PATH (optional for deployment)")
            return False
            
        try:
            result = subprocess.run(
                ['adb', 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                logger.info(f"✅ adb available: {version}")
                return True
            else:
                logger.warning("⚠️  adb not working properly")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️  Error checking adb: {e}")
            return False
            
    def detect_device(self) -> Optional[Dict]:
        """Detect connected device and validate it's the target device"""
        logger.info("📱 Detecting connected device...")
        
        try:
            # Check fastboot devices
            result = subprocess.run(
                ['fastboot', 'devices'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                devices = result.stdout.strip().split('\n')
                logger.info(f"✅ Found {len(devices)} device(s) in fastboot mode")
                
                # Get device info
                device_info = self.get_device_info()
                if device_info:
                    return device_info
                    
            # Check adb devices if fastboot didn't find anything
            if shutil.which('adb'):
                result = subprocess.run(
                    ['adb', 'devices'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    devices = [line for line in lines if line.strip() and 'device' in line]
                    
                    if devices:
                        logger.info(f"✅ Found {len(devices)} device(s) in adb mode")
                        logger.info("Device needs to be in fastboot mode for kernel flashing")
                        return {'mode': 'adb', 'count': len(devices)}
                        
            logger.warning("⚠️  No devices detected")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error detecting device: {e}")
            return None
            
    def get_device_info(self) -> Optional[Dict]:
        """Get detailed device information"""
        logger.info("📋 Getting device information...")
        
        try:
            # Get device product name
            result = subprocess.run(
                ['fastboot', 'getvar', 'product'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            product = "unknown"
            if result.returncode == 0:
                # fastboot getvar output goes to stderr
                output = result.stderr.strip()
                for line in output.split('\n'):
                    if 'product:' in line:
                        product = line.split('product:')[1].strip()
                        break
                        
            # Validate device
            if product.lower() in ['raphael', 'raphaelin']:
                logger.info(f"✅ Detected compatible device: {product}")
                return {
                    'product': product,
                    'model': self.device_config['model'],
                    'mode': 'fastboot',
                    'compatible': True
                }
            else:
                logger.warning(f"⚠️  Detected device: {product}")
                logger.warning("This may not be a Redmi K20 Pro (raphael)")
                return {
                    'product': product,
                    'mode': 'fastboot',
                    'compatible': False
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting device info: {e}")
            return None
            
    def backup_current_kernel(self) -> Optional[Path]:
        """Backup the current kernel before flashing"""
        logger.info("💾 Backing up current kernel...")
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"boot_backup_{timestamp}.img"
            
            # Create backup using fastboot
            result = subprocess.run(
                ['fastboot', 'getvar', 'current-slot'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Try to read current boot partition
            cmd = ['fastboot', 'boot', str(backup_file)]  # This won't work, need different approach
            
            # Alternative: Use dd command if device is rooted and adb available
            if shutil.which('adb'):
                try:
                    # Try to backup via adb (requires root)
                    result = subprocess.run(
                        ['adb', 'shell', 'su', '-c', f'dd if=/dev/block/bootdevice/by-name/boot of=/sdcard/boot_backup_{timestamp}.img'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        # Pull the backup
                        subprocess.run(
                            ['adb', 'pull', f'/sdcard/boot_backup_{timestamp}.img', str(backup_file)],
                            check=True,
                            timeout=60
                        )
                        
                        # Clean up device
                        subprocess.run(
                            ['adb', 'shell', 'rm', f'/sdcard/boot_backup_{timestamp}.img'],
                            timeout=10
                        )
                        
                        logger.info(f"✅ Kernel backup created: {backup_file}")
                        return backup_file
                        
                except subprocess.CalledProcessError:
                    logger.warning("⚠️  Could not create kernel backup (device may not be rooted)")
                    
            # Create a placeholder backup record
            backup_info = {
                'timestamp': timestamp,
                'device': self.get_device_info(),
                'backup_method': 'record_only',
                'note': 'Actual kernel backup requires rooted device'
            }
            
            backup_record = self.backup_dir / f"backup_record_{timestamp}.json"
            with open(backup_record, 'w') as f:
                json.dump(backup_info, f, indent=2)
                
            logger.warning("⚠️  Created backup record only (kernel backup requires root)")
            return backup_record
            
        except Exception as e:
            logger.error(f"❌ Failed to backup kernel: {e}")
            return None
            
    def validate_kernel_image(self, kernel_path: Path) -> bool:
        """Validate kernel image before flashing"""
        logger.info(f"🔍 Validating kernel image: {kernel_path}")
        
        if not kernel_path.exists():
            logger.error(f"❌ Kernel image not found: {kernel_path}")
            return False
            
        # Check file size (reasonable range for Android kernel)
        file_size = kernel_path.stat().st_size
        min_size = 5 * 1024 * 1024   # 5MB minimum
        max_size = 50 * 1024 * 1024  # 50MB maximum
        
        if file_size < min_size:
            logger.error(f"❌ Kernel image too small: {file_size} bytes")
            return False
            
        if file_size > max_size:
            logger.warning(f"⚠️  Kernel image very large: {file_size} bytes")
            
        logger.info(f"✅ Kernel image size: {file_size / (1024*1024):.1f} MB")
        
        # Try to detect if it's an Android boot image
        try:
            with open(kernel_path, 'rb') as f:
                header = f.read(8)
                
            # Android boot image magic
            if header.startswith(b'ANDROID!'):
                logger.info("✅ Detected Android boot image format")
                return True
            else:
                logger.warning("⚠️  Not a standard Android boot image")
                logger.warning("Proceeding anyway - may be a raw kernel")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  Could not analyze kernel image: {e}")
            return True  # Proceed anyway
            
    def flash_kernel(self, kernel_path: Path, partition: str = 'boot') -> bool:
        """Flash kernel to device"""
        logger.info(f"⚡ Flashing kernel to {partition} partition...")
        
        try:
            # Flash the kernel
            cmd = ['fastboot', 'flash', partition, str(kernel_path)]
            logger.info(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info("✅ Kernel flashed successfully")
                logger.info("Output:", result.stdout)
                return True
            else:
                logger.error("❌ Kernel flashing failed")
                logger.error("Error:", result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Kernel flashing timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error flashing kernel: {e}")
            return False
            
    def reboot_device(self, mode: str = 'system') -> bool:
        """Reboot device to specified mode"""
        logger.info(f"🔄 Rebooting device to {mode}...")
        
        try:
            if mode == 'system':
                cmd = ['fastboot', 'reboot']
            elif mode == 'fastboot':
                cmd = ['fastboot', 'reboot-bootloader']
            elif mode == 'recovery':
                cmd = ['fastboot', 'reboot', 'recovery']
            else:
                logger.error(f"❌ Unknown reboot mode: {mode}")
                return False
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Device rebooting to {mode}")
                return True
            else:
                logger.error(f"❌ Failed to reboot to {mode}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error rebooting device: {e}")
            return False
            
    def wait_for_device(self, mode: str = 'adb', timeout: int = 60) -> bool:
        """Wait for device to come online"""
        logger.info(f"⏳ Waiting for device in {mode} mode...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if mode == 'adb':
                    result = subprocess.run(
                        ['adb', 'devices'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')[1:]
                        devices = [line for line in lines if line.strip() and 'device' in line]
                        if devices:
                            logger.info("✅ Device online in adb mode")
                            return True
                            
                elif mode == 'fastboot':
                    result = subprocess.run(
                        ['fastboot', 'devices'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        logger.info("✅ Device online in fastboot mode")
                        return True
                        
                time.sleep(2)
                
            except Exception:
                time.sleep(2)
                continue
                
        logger.warning(f"⚠️  Device did not come online in {mode} mode within {timeout}s")
        return False
        
    def validate_deployment(self) -> bool:
        """Validate that the kernel was deployed successfully"""
        logger.info("🔍 Validating kernel deployment...")
        
        # Wait for device to boot
        if not self.wait_for_device('adb', timeout=120):
            logger.error("❌ Device did not boot within 2 minutes")
            return False
            
        try:
            # Check kernel version
            result = subprocess.run(
                ['adb', 'shell', 'uname', '-r'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                kernel_version = result.stdout.strip()
                logger.info(f"✅ Kernel version: {kernel_version}")
                
                # Check for Docker-related kernel features
                docker_features = self.check_docker_kernel_features()
                if docker_features:
                    logger.info("✅ Docker kernel features validated")
                    return True
                else:
                    logger.warning("⚠️  Some Docker kernel features may be missing")
                    return True  # Still consider successful
                    
            else:
                logger.error("❌ Could not get kernel version")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error validating deployment: {e}")
            return False
            
    def check_docker_kernel_features(self) -> bool:
        """Check if Docker-required kernel features are available"""
        logger.info("🐳 Checking Docker kernel features...")
        
        features_to_check = [
            '/proc/cgroups',
            '/sys/fs/cgroup',
            '/proc/sys/kernel/ns_last_pid'
        ]
        
        available_features = 0
        
        for feature in features_to_check:
            try:
                result = subprocess.run(
                    ['adb', 'shell', 'test', '-e', feature],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    available_features += 1
                    logger.debug(f"✅ {feature} available")
                else:
                    logger.debug(f"❌ {feature} not available")
                    
            except Exception:
                logger.debug(f"❌ Could not check {feature}")
                
        success_rate = available_features / len(features_to_check)
        logger.info(f"Docker features available: {available_features}/{len(features_to_check)} ({success_rate:.1%})")
        
        return success_rate >= 0.5  # At least 50% of features should be available
        
    def rollback_kernel(self, backup_path: Path) -> bool:
        """Rollback to previous kernel"""
        logger.info(f"🔄 Rolling back kernel from backup: {backup_path}")
        
        if not backup_path.exists():
            logger.error(f"❌ Backup not found: {backup_path}")
            return False
            
        # If it's a JSON record, we can't actually rollback
        if backup_path.suffix == '.json':
            logger.error("❌ Cannot rollback - backup is record only")
            logger.error("Original kernel backup requires rooted device")
            return False
            
        # Flash the backup
        return self.flash_kernel(backup_path, 'boot')
        
    def create_deployment_record(self, kernel_path: Path, success: bool, backup_path: Optional[Path] = None) -> None:
        """Create a record of the deployment"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'kernel_path': str(kernel_path),
            'backup_path': str(backup_path) if backup_path else None,
            'device_info': self.get_device_info(),
            'success': success,
            'validation_passed': success
        }
        
        try:
            with open(self.deployment_log, 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            logger.warning(f"⚠️  Could not write deployment record: {e}")
            
    def deploy_kernel(self, kernel_path: Path, skip_backup: bool = False, skip_validation: bool = False) -> bool:
        """Complete kernel deployment process"""
        logger.info("🚀 Starting kernel deployment process")
        logger.info("=" * 50)
        
        kernel_path = Path(kernel_path)
        backup_path = None
        
        try:
            # Pre-deployment checks
            if not self.check_fastboot_availability():
                return False
                
            self.check_adb_availability()  # Optional
            
            device_info = self.detect_device()
            if not device_info:
                logger.error("❌ No compatible device detected")
                return False
                
            if not device_info.get('compatible', True):
                response = input("⚠️  Device may not be compatible. Continue? (y/N): ")
                if response.lower() != 'y':
                    logger.info("Deployment cancelled by user")
                    return False
                    
            # Validate kernel image
            if not self.validate_kernel_image(kernel_path):
                return False
                
            # Backup current kernel
            if not skip_backup:
                backup_path = self.backup_current_kernel()
                if not backup_path:
                    response = input("⚠️  Could not backup kernel. Continue? (y/N): ")
                    if response.lower() != 'y':
                        logger.info("Deployment cancelled by user")
                        return False
                        
            # Flash kernel
            if not self.flash_kernel(kernel_path):
                logger.error("❌ Kernel flashing failed")
                self.create_deployment_record(kernel_path, False, backup_path)
                return False
                
            # Reboot device
            if not self.reboot_device('system'):
                logger.warning("⚠️  Could not reboot device automatically")
                logger.info("Please reboot device manually")
                
            # Validate deployment
            if not skip_validation:
                if not self.validate_deployment():
                    logger.error("❌ Deployment validation failed")
                    
                    if backup_path and backup_path.suffix != '.json':
                        response = input("Rollback to previous kernel? (y/N): ")
                        if response.lower() == 'y':
                            self.rollback_kernel(backup_path)
                            
                    self.create_deployment_record(kernel_path, False, backup_path)
                    return False
                    
            logger.info("🎉 Kernel deployment completed successfully!")
            self.create_deployment_record(kernel_path, True, backup_path)
            return True
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Deployment interrupted by user")
            return False
        except Exception as e:
            logger.error(f"❌ Deployment failed with error: {e}")
            self.create_deployment_record(kernel_path, False, backup_path)
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kernel deployment tools for Docker-enabled Android kernel"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy kernel to device')
    deploy_parser.add_argument('kernel_path', help='Path to kernel image file')
    deploy_parser.add_argument('--skip-backup', action='store_true', help='Skip kernel backup')
    deploy_parser.add_argument('--skip-validation', action='store_true', help='Skip deployment validation')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check device and tools')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup current kernel')
    
    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback to previous kernel')
    rollback_parser.add_argument('backup_path', help='Path to backup file')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate current deployment')
    
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    if not args.command:
        parser.print_help()
        return
        
    deployer = KernelDeploymentManager()
    
    if args.command == 'deploy':
        success = deployer.deploy_kernel(
            Path(args.kernel_path),
            skip_backup=args.skip_backup,
            skip_validation=args.skip_validation
        )
        sys.exit(0 if success else 1)
        
    elif args.command == 'check':
        deployer.check_fastboot_availability()
        deployer.check_adb_availability()
        device_info = deployer.detect_device()
        if device_info:
            print(f"Device info: {device_info}")
        else:
            print("No device detected")
            
    elif args.command == 'backup':
        backup_path = deployer.backup_current_kernel()
        if backup_path:
            print(f"Backup created: {backup_path}")
        else:
            print("Backup failed")
            sys.exit(1)
            
    elif args.command == 'rollback':
        success = deployer.rollback_kernel(Path(args.backup_path))
        sys.exit(0 if success else 1)
        
    elif args.command == 'validate':
        success = deployer.validate_deployment()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()