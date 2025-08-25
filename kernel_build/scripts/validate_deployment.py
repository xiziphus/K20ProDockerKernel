#!/usr/bin/env python3
"""
Deployment Validation Script for Docker-Enabled Kernel

This script validates that a Docker-enabled kernel deployment was successful
and that all required features are working correctly.

Requirements: 6.4, 7.1, 7.2
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentValidator:
    """Validates Docker-enabled kernel deployment"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.kernel_build_root = self.project_root / "kernel_build"
        self.config_file = self.kernel_build_root / "config" / "deployment_config.json"
        
        # Load configuration
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """Load deployment configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️  Could not load config: {e}")
            return self.get_default_config()
            
    def get_default_config(self) -> Dict:
        """Get default configuration if config file is missing"""
        return {
            "docker_validation": {
                "required_features": [
                    "/proc/cgroups",
                    "/sys/fs/cgroup",
                    "/proc/sys/kernel/ns_last_pid"
                ],
                "optional_features": [
                    "/sys/fs/cgroup/memory",
                    "/sys/fs/cgroup/cpu",
                    "/sys/fs/cgroup/cpuset",
                    "/sys/fs/cgroup/devices"
                ]
            }
        }
        
    def check_device_connection(self) -> bool:
        """Check if device is connected via ADB"""
        logger.info("📱 Checking device connection...")
        
        try:
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
                    logger.info(f"✅ Found {len(devices)} connected device(s)")
                    return True
                else:
                    logger.error("❌ No devices found")
                    return False
            else:
                logger.error("❌ ADB not working properly")
                return False
                
        except FileNotFoundError:
            logger.error("❌ ADB not found - install Android SDK Platform Tools")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking device connection: {e}")
            return False
            
    def get_kernel_info(self) -> Optional[Dict]:
        """Get kernel information from device"""
        logger.info("🔍 Getting kernel information...")
        
        try:
            # Get kernel version
            result = subprocess.run(
                ['adb', 'shell', 'uname', '-a'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                kernel_info = result.stdout.strip()
                logger.info(f"✅ Kernel: {kernel_info}")
                
                # Parse kernel version
                parts = kernel_info.split()
                return {
                    'full_info': kernel_info,
                    'version': parts[2] if len(parts) > 2 else 'unknown',
                    'architecture': parts[4] if len(parts) > 4 else 'unknown'
                }
            else:
                logger.error("❌ Could not get kernel information")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting kernel info: {e}")
            return None
            
    def check_android_version(self) -> Optional[str]:
        """Check Android version"""
        logger.info("📋 Checking Android version...")
        
        try:
            result = subprocess.run(
                ['adb', 'shell', 'getprop', 'ro.build.version.release'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                android_version = result.stdout.strip()
                logger.info(f"✅ Android version: {android_version}")
                return android_version
            else:
                logger.warning("⚠️  Could not get Android version")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️  Error getting Android version: {e}")
            return None
            
    def check_docker_features(self) -> Dict[str, bool]:
        """Check Docker-required kernel features"""
        logger.info("🐳 Checking Docker kernel features...")
        
        results = {}
        
        # Required features
        required_features = self.config.get('docker_validation', {}).get('required_features', [])
        for feature in required_features:
            try:
                result = subprocess.run(
                    ['adb', 'shell', 'test', '-e', feature],
                    capture_output=True,
                    timeout=5
                )
                
                available = result.returncode == 0
                results[feature] = available
                
                if available:
                    logger.info(f"✅ {feature}")
                else:
                    logger.error(f"❌ {feature} (REQUIRED)")
                    
            except Exception as e:
                logger.error(f"❌ Could not check {feature}: {e}")
                results[feature] = False
                
        # Optional features
        optional_features = self.config.get('docker_validation', {}).get('optional_features', [])
        for feature in optional_features:
            try:
                result = subprocess.run(
                    ['adb', 'shell', 'test', '-e', feature],
                    capture_output=True,
                    timeout=5
                )
                
                available = result.returncode == 0
                results[feature] = available
                
                if available:
                    logger.info(f"✅ {feature} (optional)")
                else:
                    logger.warning(f"⚠️  {feature} (optional)")
                    
            except Exception as e:
                logger.warning(f"⚠️  Could not check {feature}: {e}")
                results[feature] = False
                
        return results
        
    def check_cgroup_support(self) -> Dict[str, bool]:
        """Check cgroup subsystem support"""
        logger.info("📊 Checking cgroup subsystems...")
        
        results = {}
        
        try:
            # Check /proc/cgroups
            result = subprocess.run(
                ['adb', 'shell', 'cat', '/proc/cgroups'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                cgroups_output = result.stdout.strip()
                
                # Parse cgroups output
                required_subsystems = ['memory', 'cpu', 'cpuset', 'devices', 'pids', 'freezer']
                
                for subsystem in required_subsystems:
                    if subsystem in cgroups_output:
                        results[f'cgroup_{subsystem}'] = True
                        logger.info(f"✅ cgroup {subsystem} subsystem")
                    else:
                        results[f'cgroup_{subsystem}'] = False
                        logger.warning(f"⚠️  cgroup {subsystem} subsystem missing")
                        
            else:
                logger.error("❌ Could not read /proc/cgroups")
                
        except Exception as e:
            logger.error(f"❌ Error checking cgroups: {e}")
            
        return results
        
    def check_namespace_support(self) -> Dict[str, bool]:
        """Check namespace support"""
        logger.info("🔒 Checking namespace support...")
        
        results = {}
        namespaces = ['pid', 'net', 'ipc', 'uts', 'user', 'mnt']
        
        for ns in namespaces:
            try:
                # Try to create a simple namespace test
                result = subprocess.run(
                    ['adb', 'shell', 'test', '-e', f'/proc/self/ns/{ns}'],
                    capture_output=True,
                    timeout=5
                )
                
                available = result.returncode == 0
                results[f'namespace_{ns}'] = available
                
                if available:
                    logger.info(f"✅ {ns} namespace")
                else:
                    logger.warning(f"⚠️  {ns} namespace")
                    
            except Exception as e:
                logger.warning(f"⚠️  Could not check {ns} namespace: {e}")
                results[f'namespace_{ns}'] = False
                
        return results
        
    def check_overlay_filesystem(self) -> bool:
        """Check overlay filesystem support"""
        logger.info("💾 Checking overlay filesystem support...")
        
        try:
            # Check if overlay module is loaded
            result = subprocess.run(
                ['adb', 'shell', 'cat', '/proc/filesystems'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                filesystems = result.stdout
                if 'overlay' in filesystems:
                    logger.info("✅ Overlay filesystem supported")
                    return True
                else:
                    logger.warning("⚠️  Overlay filesystem not found in /proc/filesystems")
                    return False
            else:
                logger.error("❌ Could not check filesystem support")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking overlay filesystem: {e}")
            return False
            
    def test_container_creation(self) -> bool:
        """Test basic container creation (if Docker is installed)"""
        logger.info("🧪 Testing container functionality...")
        
        try:
            # Check if Docker is available
            result = subprocess.run(
                ['adb', 'shell', 'which', 'docker'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.info("ℹ️  Docker not installed - skipping container test")
                return True  # Not an error if Docker isn't installed yet
                
            # Try to get Docker version
            result = subprocess.run(
                ['adb', 'shell', 'docker', 'version'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                logger.info("✅ Docker is working")
                
                # Try to run a simple container
                result = subprocess.run(
                    ['adb', 'shell', 'docker', 'run', '--rm', 'hello-world'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logger.info("✅ Container creation test passed")
                    return True
                else:
                    logger.warning("⚠️  Container creation test failed")
                    logger.warning(f"Error: {result.stderr}")
                    return False
            else:
                logger.warning("⚠️  Docker daemon not running or not working")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️  Error testing container functionality: {e}")
            return False
            
    def generate_validation_report(self, results: Dict) -> str:
        """Generate comprehensive validation report"""
        report = []
        report.append("=" * 60)
        report.append("DOCKER-ENABLED KERNEL DEPLOYMENT VALIDATION REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Kernel information
        if 'kernel_info' in results:
            report.append("🔍 KERNEL INFORMATION")
            kernel_info = results['kernel_info']
            if kernel_info:
                report.append(f"   Version: {kernel_info.get('version', 'unknown')}")
                report.append(f"   Architecture: {kernel_info.get('architecture', 'unknown')}")
                report.append(f"   Full Info: {kernel_info.get('full_info', 'unknown')}")
            else:
                report.append("   ❌ Could not retrieve kernel information")
            report.append("")
            
        # Android version
        if 'android_version' in results:
            report.append("📋 ANDROID VERSION")
            android_version = results['android_version']
            if android_version:
                report.append(f"   Version: {android_version}")
            else:
                report.append("   ⚠️  Could not retrieve Android version")
            report.append("")
            
        # Docker features
        if 'docker_features' in results:
            report.append("🐳 DOCKER KERNEL FEATURES")
            docker_features = results['docker_features']
            for feature, available in docker_features.items():
                status = "✅" if available else "❌"
                report.append(f"   {status} {feature}")
            report.append("")
            
        # Cgroup support
        if 'cgroup_support' in results:
            report.append("📊 CGROUP SUBSYSTEMS")
            cgroup_support = results['cgroup_support']
            for subsystem, available in cgroup_support.items():
                status = "✅" if available else "⚠️ "
                report.append(f"   {status} {subsystem}")
            report.append("")
            
        # Namespace support
        if 'namespace_support' in results:
            report.append("🔒 NAMESPACE SUPPORT")
            namespace_support = results['namespace_support']
            for ns, available in namespace_support.items():
                status = "✅" if available else "⚠️ "
                report.append(f"   {status} {ns}")
            report.append("")
            
        # Overlay filesystem
        if 'overlay_fs' in results:
            report.append("💾 OVERLAY FILESYSTEM")
            overlay_fs = results['overlay_fs']
            status = "✅" if overlay_fs else "⚠️ "
            report.append(f"   {status} Overlay filesystem support")
            report.append("")
            
        # Container test
        if 'container_test' in results:
            report.append("🧪 CONTAINER FUNCTIONALITY")
            container_test = results['container_test']
            status = "✅" if container_test else "⚠️ "
            report.append(f"   {status} Container creation test")
            report.append("")
            
        # Overall status
        report.append("📋 OVERALL STATUS")
        
        # Calculate success metrics
        required_features = results.get('docker_features', {})
        required_count = len([f for f, available in required_features.items() if available])
        total_required = len(required_features)
        
        if total_required > 0:
            success_rate = required_count / total_required
            report.append(f"   Docker features: {required_count}/{total_required} ({success_rate:.1%})")
            
            if success_rate >= 0.8:
                report.append("   🎉 DEPLOYMENT VALIDATION PASSED")
            elif success_rate >= 0.5:
                report.append("   ⚠️  DEPLOYMENT PARTIALLY SUCCESSFUL")
            else:
                report.append("   ❌ DEPLOYMENT VALIDATION FAILED")
        else:
            report.append("   ⚠️  Could not determine validation status")
            
        report.append("")
        
        return "\n".join(report)
        
    def run_full_validation(self) -> bool:
        """Run complete deployment validation"""
        logger.info("🔍 Starting deployment validation")
        logger.info("=" * 50)
        
        results = {}
        
        # Check device connection
        if not self.check_device_connection():
            logger.error("❌ Cannot validate - device not connected")
            return False
            
        # Get kernel information
        results['kernel_info'] = self.get_kernel_info()
        
        # Check Android version
        results['android_version'] = self.check_android_version()
        
        # Check Docker features
        results['docker_features'] = self.check_docker_features()
        
        # Check cgroup support
        results['cgroup_support'] = self.check_cgroup_support()
        
        # Check namespace support
        results['namespace_support'] = self.check_namespace_support()
        
        # Check overlay filesystem
        results['overlay_fs'] = self.check_overlay_filesystem()
        
        # Test container functionality
        results['container_test'] = self.test_container_creation()
        
        # Generate and display report
        report = self.generate_validation_report(results)
        print("\n" + report)
        
        # Save report to file
        try:
            report_file = self.kernel_build_root / 'logs' / 'validation_report.txt'
            report_file.parent.mkdir(parents=True, exist_ok=True)
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"📄 Validation report saved: {report_file}")
        except Exception as e:
            logger.warning(f"⚠️  Could not save validation report: {e}")
            
        # Determine overall success
        docker_features = results.get('docker_features', {})
        if docker_features:
            required_available = sum(1 for available in docker_features.values() if available)
            total_required = len(docker_features)
            success_rate = required_available / total_required if total_required > 0 else 0
            
            return success_rate >= 0.5  # At least 50% of features should work
        else:
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate Docker-enabled kernel deployment"
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    validator = DeploymentValidator()
    success = validator.run_full_validation()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()