#!/usr/bin/env python3
"""
Kernel Boot Process Testing System

This script tests kernel boot process and Docker feature availability
on the target device through ADB interface.

Requirements: 6.3, 6.4, 7.1
"""

import os
import sys
import subprocess
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import re

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory

@dataclass
class BootTestResult:
    """Result of boot process test"""
    test_name: str
    success: bool
    message: str
    details: Dict
    duration: float

@dataclass
class DockerFeatureTest:
    """Docker feature test result"""
    feature_name: str
    available: bool
    path: str
    details: str

class KernelBootTester:
    """Tests kernel boot process and Docker features"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # Docker required kernel features
        self.docker_features = {
            "cgroups": {
                "paths": ["/proc/cgroups", "/sys/fs/cgroup"],
                "required": True,
                "description": "Control Groups support"
            },
            "namespaces": {
                "paths": ["/proc/self/ns/pid", "/proc/self/ns/net", "/proc/self/ns/mnt"],
                "required": True,
                "description": "Namespace support"
            },
            "overlay_fs": {
                "paths": ["/proc/filesystems"],
                "required": True,
                "description": "Overlay filesystem support",
                "check_content": "overlay"
            },
            "bridge_netfilter": {
                "paths": ["/proc/sys/net/bridge"],
                "required": True,
                "description": "Bridge netfilter support"
            },
            "ip_forward": {
                "paths": ["/proc/sys/net/ipv4/ip_forward"],
                "required": True,
                "description": "IP forwarding support"
            },
            "iptables": {
                "paths": ["/proc/net/ip_tables_names"],
                "required": False,
                "description": "IPTables support"
            },
            "apparmor": {
                "paths": ["/sys/kernel/security/apparmor"],
                "required": False,
                "description": "AppArmor security module"
            },
            "seccomp": {
                "paths": ["/proc/sys/kernel/seccomp"],
                "required": False,
                "description": "Secure computing mode"
            }
        }
        
        # Boot process tests
        self.boot_tests = [
            "device_connection",
            "kernel_version",
            "android_version",
            "system_properties",
            "mount_points",
            "docker_features",
            "cgroup_subsystems",
            "network_interfaces",
            "security_modules"
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for boot tester"""
        logger = logging.getLogger("kernel_boot_tester")
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
            
            log_file = log_dir / f"boot_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def run_adb_command(self, command: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """Run ADB command and return result"""
        try:
            full_command = ['adb'] + command
            self.logger.debug(f"Running: {' '.join(full_command)}")
            
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Command timed out after {timeout} seconds"
        except FileNotFoundError:
            return False, "", "ADB not found - install Android SDK Platform Tools"
        except Exception as e:
            return False, "", str(e)
    
    def test_device_connection(self) -> BootTestResult:
        """Test device connection via ADB"""
        start_time = time.time()
        
        success, stdout, stderr = self.run_adb_command(['devices'])
        
        if success:
            lines = stdout.split('\n')[1:]  # Skip header
            devices = [line for line in lines if line.strip() and 'device' in line]
            
            if devices:
                device_info = devices[0].split('\t')[0]  # Get device ID
                message = f"Device connected: {device_info}"
                details = {"device_id": device_info, "device_count": len(devices)}
                test_success = True
            else:
                message = "No devices found"
                details = {"error": "No devices connected"}
                test_success = False
        else:
            message = f"ADB error: {stderr}"
            details = {"error": stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="device_connection",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_kernel_version(self) -> BootTestResult:
        """Test kernel version information"""
        start_time = time.time()
        
        success, stdout, stderr = self.run_adb_command(['shell', 'uname', '-a'])
        
        if success:
            kernel_info = stdout
            # Parse kernel version
            parts = kernel_info.split()
            
            details = {
                "full_info": kernel_info,
                "kernel_name": parts[0] if len(parts) > 0 else "unknown",
                "version": parts[2] if len(parts) > 2 else "unknown",
                "architecture": parts[4] if len(parts) > 4 else "unknown",
                "build_date": " ".join(parts[5:]) if len(parts) > 5 else "unknown"
            }
            
            # Check if it's ARM64
            is_arm64 = "aarch64" in kernel_info or "arm64" in kernel_info
            
            message = f"Kernel: {details['version']} ({details['architecture']})"
            test_success = True
            
            if not is_arm64:
                details["warning"] = "Not ARM64 architecture"
        else:
            message = f"Could not get kernel version: {stderr}"
            details = {"error": stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="kernel_version",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_android_version(self) -> BootTestResult:
        """Test Android version information"""
        start_time = time.time()
        
        # Get Android version
        success, version_stdout, version_stderr = self.run_adb_command(
            ['shell', 'getprop', 'ro.build.version.release']
        )
        
        # Get API level
        api_success, api_stdout, api_stderr = self.run_adb_command(
            ['shell', 'getprop', 'ro.build.version.sdk']
        )
        
        # Get build info
        build_success, build_stdout, build_stderr = self.run_adb_command(
            ['shell', 'getprop', 'ro.build.display.id']
        )
        
        if success:
            details = {
                "android_version": version_stdout,
                "api_level": api_stdout if api_success else "unknown",
                "build_id": build_stdout if build_success else "unknown"
            }
            
            message = f"Android {details['android_version']} (API {details['api_level']})"
            test_success = True
        else:
            message = f"Could not get Android version: {version_stderr}"
            details = {"error": version_stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="android_version",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_system_properties(self) -> BootTestResult:
        """Test important system properties"""
        start_time = time.time()
        
        properties_to_check = [
            "ro.product.model",
            "ro.product.device",
            "ro.build.type",
            "ro.debuggable",
            "ro.secure"
        ]
        
        details = {}
        all_success = True
        
        for prop in properties_to_check:
            success, stdout, stderr = self.run_adb_command(['shell', 'getprop', prop])
            if success:
                details[prop] = stdout
            else:
                details[prop] = f"error: {stderr}"
                all_success = False
        
        if all_success:
            device_model = details.get("ro.product.model", "unknown")
            message = f"Device: {device_model}"
            test_success = True
        else:
            message = "Could not retrieve all system properties"
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="system_properties",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_mount_points(self) -> BootTestResult:
        """Test important mount points"""
        start_time = time.time()
        
        success, stdout, stderr = self.run_adb_command(['shell', 'mount'])
        
        if success:
            mount_info = stdout
            
            # Look for important mount points
            important_mounts = [
                "/system",
                "/vendor",
                "/data",
                "/proc",
                "/sys",
                "/dev"
            ]
            
            found_mounts = {}
            for mount in important_mounts:
                if mount in mount_info:
                    # Extract mount details
                    for line in mount_info.split('\n'):
                        if f" {mount} " in line or line.endswith(f" {mount}"):
                            found_mounts[mount] = line.strip()
                            break
                    else:
                        found_mounts[mount] = "found but no details"
                else:
                    found_mounts[mount] = "not found"
            
            details = {
                "mount_points": found_mounts,
                "total_mounts": len(mount_info.split('\n'))
            }
            
            missing_mounts = [m for m, status in found_mounts.items() if status == "not found"]
            
            if missing_mounts:
                message = f"Missing mount points: {', '.join(missing_mounts)}"
                test_success = False
            else:
                message = f"All important mount points found ({len(found_mounts)})"
                test_success = True
        else:
            message = f"Could not get mount information: {stderr}"
            details = {"error": stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="mount_points",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_docker_features(self) -> BootTestResult:
        """Test Docker-required kernel features"""
        start_time = time.time()
        
        feature_results = []
        
        for feature_name, config in self.docker_features.items():
            feature_test = DockerFeatureTest(
                feature_name=feature_name,
                available=False,
                path="",
                details=""
            )
            
            # Test each path for this feature
            for path in config["paths"]:
                success, stdout, stderr = self.run_adb_command(['shell', 'test', '-e', path])
                
                if success:
                    feature_test.available = True
                    feature_test.path = path
                    
                    # If we need to check content
                    if "check_content" in config:
                        content_success, content_stdout, content_stderr = self.run_adb_command(
                            ['shell', 'cat', path]
                        )
                        if content_success and config["check_content"] in content_stdout:
                            feature_test.details = f"Content check passed: {config['check_content']} found"
                        else:
                            feature_test.available = False
                            feature_test.details = f"Content check failed: {config['check_content']} not found"
                    else:
                        feature_test.details = "Path exists"
                    
                    break  # Found at least one path
            
            if not feature_test.available:
                feature_test.details = f"None of the paths exist: {', '.join(config['paths'])}"
            
            feature_results.append(feature_test)
        
        # Analyze results
        required_features = [f for f in feature_results if self.docker_features[f.feature_name]["required"]]
        available_required = [f for f in required_features if f.available]
        
        optional_features = [f for f in feature_results if not self.docker_features[f.feature_name]["required"]]
        available_optional = [f for f in optional_features if f.available]
        
        details = {
            "required_features": {
                "total": len(required_features),
                "available": len(available_required),
                "missing": [f.feature_name for f in required_features if not f.available]
            },
            "optional_features": {
                "total": len(optional_features),
                "available": len(available_optional),
                "missing": [f.feature_name for f in optional_features if not f.available]
            },
            "feature_details": {
                f.feature_name: {
                    "available": f.available,
                    "path": f.path,
                    "details": f.details
                } for f in feature_results
            }
        }
        
        # Success if all required features are available
        test_success = len(available_required) == len(required_features)
        
        if test_success:
            message = f"Docker features: {len(available_required)}/{len(required_features)} required, {len(available_optional)}/{len(optional_features)} optional"
        else:
            missing_required = [f.feature_name for f in required_features if not f.available]
            message = f"Missing required Docker features: {', '.join(missing_required)}"
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="docker_features",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_cgroup_subsystems(self) -> BootTestResult:
        """Test cgroup subsystem availability"""
        start_time = time.time()
        
        success, stdout, stderr = self.run_adb_command(['shell', 'cat', '/proc/cgroups'])
        
        if success:
            cgroups_output = stdout
            
            # Parse cgroups output
            required_subsystems = ['memory', 'cpu', 'cpuset', 'devices', 'pids', 'freezer']
            found_subsystems = {}
            
            for line in cgroups_output.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 4:
                    subsystem = parts[0]
                    hierarchy = parts[1]
                    num_cgroups = parts[2]
                    enabled = parts[3] == '1'
                    
                    found_subsystems[subsystem] = {
                        "hierarchy": hierarchy,
                        "num_cgroups": num_cgroups,
                        "enabled": enabled
                    }
            
            # Check required subsystems
            missing_subsystems = []
            disabled_subsystems = []
            
            for subsystem in required_subsystems:
                if subsystem not in found_subsystems:
                    missing_subsystems.append(subsystem)
                elif not found_subsystems[subsystem]["enabled"]:
                    disabled_subsystems.append(subsystem)
            
            details = {
                "found_subsystems": found_subsystems,
                "required_subsystems": required_subsystems,
                "missing_subsystems": missing_subsystems,
                "disabled_subsystems": disabled_subsystems
            }
            
            if missing_subsystems or disabled_subsystems:
                issues = []
                if missing_subsystems:
                    issues.append(f"missing: {', '.join(missing_subsystems)}")
                if disabled_subsystems:
                    issues.append(f"disabled: {', '.join(disabled_subsystems)}")
                
                message = f"Cgroup issues: {'; '.join(issues)}"
                test_success = False
            else:
                message = f"All required cgroup subsystems available ({len(required_subsystems)})"
                test_success = True
        else:
            message = f"Could not read /proc/cgroups: {stderr}"
            details = {"error": stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="cgroup_subsystems",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_network_interfaces(self) -> BootTestResult:
        """Test network interface availability"""
        start_time = time.time()
        
        success, stdout, stderr = self.run_adb_command(['shell', 'ip', 'link', 'show'])
        
        if success:
            interfaces_output = stdout
            
            # Parse network interfaces
            interfaces = []
            for line in interfaces_output.split('\n'):
                if ': ' in line and not line.startswith(' '):
                    # Interface line
                    parts = line.split(': ')
                    if len(parts) >= 2:
                        interface_name = parts[1].split('@')[0]  # Remove @if suffix
                        interfaces.append(interface_name)
            
            # Check for important interfaces
            important_interfaces = ['lo', 'wlan0', 'rmnet0', 'dummy0']
            found_important = [iface for iface in important_interfaces if iface in interfaces]
            
            details = {
                "all_interfaces": interfaces,
                "important_interfaces": important_interfaces,
                "found_important": found_important,
                "total_interfaces": len(interfaces)
            }
            
            if 'lo' not in interfaces:
                message = "Loopback interface missing"
                test_success = False
            else:
                message = f"Network interfaces: {len(interfaces)} total, {len(found_important)} important"
                test_success = True
        else:
            message = f"Could not get network interfaces: {stderr}"
            details = {"error": stderr}
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="network_interfaces",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def test_security_modules(self) -> BootTestResult:
        """Test security module availability"""
        start_time = time.time()
        
        # Check SELinux
        selinux_success, selinux_stdout, selinux_stderr = self.run_adb_command(
            ['shell', 'getenforce']
        )
        
        # Check AppArmor
        apparmor_success, apparmor_stdout, apparmor_stderr = self.run_adb_command(
            ['shell', 'test', '-d', '/sys/kernel/security/apparmor']
        )
        
        details = {
            "selinux": {
                "available": selinux_success,
                "status": selinux_stdout if selinux_success else selinux_stderr
            },
            "apparmor": {
                "available": apparmor_success,
                "status": "available" if apparmor_success else "not available"
            }
        }
        
        if selinux_success:
            message = f"SELinux: {selinux_stdout}"
            test_success = True
            
            if apparmor_success:
                message += ", AppArmor: available"
        else:
            message = "No security modules detected"
            test_success = False
        
        duration = time.time() - start_time
        
        return BootTestResult(
            test_name="security_modules",
            success=test_success,
            message=message,
            details=details,
            duration=duration
        )
    
    def run_all_tests(self) -> List[BootTestResult]:
        """Run all boot process tests"""
        self.logger.info("🔍 Starting kernel boot process tests")
        
        results = []
        
        for test_name in self.boot_tests:
            self.logger.info(f"Running test: {test_name}")
            
            if test_name == "device_connection":
                result = self.test_device_connection()
            elif test_name == "kernel_version":
                result = self.test_kernel_version()
            elif test_name == "android_version":
                result = self.test_android_version()
            elif test_name == "system_properties":
                result = self.test_system_properties()
            elif test_name == "mount_points":
                result = self.test_mount_points()
            elif test_name == "docker_features":
                result = self.test_docker_features()
            elif test_name == "cgroup_subsystems":
                result = self.test_cgroup_subsystems()
            elif test_name == "network_interfaces":
                result = self.test_network_interfaces()
            elif test_name == "security_modules":
                result = self.test_security_modules()
            else:
                continue
            
            results.append(result)
            
            status = "✅ PASS" if result.success else "❌ FAIL"
            self.logger.info(f"{status} {test_name}: {result.message}")
        
        return results
    
    def generate_test_report(self, results: List[BootTestResult]) -> str:
        """Generate comprehensive test report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("KERNEL BOOT PROCESS TEST REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Summary
        passed_tests = [r for r in results if r.success]
        failed_tests = [r for r in results if not r.success]
        total_duration = sum(r.duration for r in results)
        
        report_lines.append("📋 TEST SUMMARY")
        report_lines.append(f"   Total tests: {len(results)}")
        report_lines.append(f"   Passed: {len(passed_tests)}")
        report_lines.append(f"   Failed: {len(failed_tests)}")
        report_lines.append(f"   Success rate: {len(passed_tests)/len(results)*100:.1f}%")
        report_lines.append(f"   Total duration: {total_duration:.2f} seconds")
        report_lines.append("")
        
        # Test details
        report_lines.append("🔍 TEST DETAILS")
        for result in results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            report_lines.append(f"   {status} {result.test_name}")
            report_lines.append(f"      Message: {result.message}")
            report_lines.append(f"      Duration: {result.duration:.2f}s")
            
            if result.details:
                report_lines.append("      Details:")
                for key, value in result.details.items():
                    if isinstance(value, dict):
                        report_lines.append(f"        {key}:")
                        for sub_key, sub_value in value.items():
                            report_lines.append(f"          {sub_key}: {sub_value}")
                    elif isinstance(value, list):
                        report_lines.append(f"        {key}: {', '.join(map(str, value))}")
                    else:
                        report_lines.append(f"        {key}: {value}")
            
            report_lines.append("")
        
        # Overall assessment
        report_lines.append("🎯 OVERALL ASSESSMENT")
        
        # Check critical tests
        critical_tests = ["device_connection", "kernel_version", "docker_features"]
        critical_passed = [r for r in results if r.test_name in critical_tests and r.success]
        
        if len(critical_passed) == len(critical_tests):
            report_lines.append("   ✅ All critical tests passed")
            report_lines.append("   🚀 Kernel appears to be Docker-ready")
        else:
            failed_critical = [t for t in critical_tests if not any(r.test_name == t and r.success for r in results)]
            report_lines.append(f"   ❌ Critical tests failed: {', '.join(failed_critical)}")
            report_lines.append("   🔧 Kernel may need additional configuration")
        
        report_lines.append("")
        
        # Save report
        report_content = "\n".join(report_lines)
        
        try:
            report_dir = self.workspace_root / "kernel_build" / "logs"
            ensure_directory(str(report_dir))
            
            report_file = report_dir / f"boot_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report_content)
            
            return str(report_file)
        except Exception as e:
            self.logger.error(f"Could not save test report: {e}")
            return ""


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test kernel boot process and Docker features"
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = KernelBootTester()
    results = tester.run_all_tests()
    
    # Generate and save report
    report_file = tester.generate_test_report(results)
    
    # Print summary
    passed_tests = [r for r in results if r.success]
    failed_tests = [r for r in results if not r.success]
    
    print(f"\n{'='*60}")
    print("KERNEL BOOT TEST RESULTS")
    print(f"{'='*60}")
    print(f"Tests: {len(results)} total, {len(passed_tests)} passed, {len(failed_tests)} failed")
    print(f"Success Rate: {len(passed_tests)/len(results)*100:.1f}%")
    
    if report_file:
        print(f"Report: {report_file}")
    
    # Exit with appropriate code
    critical_tests = ["device_connection", "kernel_version", "docker_features"]
    critical_passed = [r for r in results if r.test_name in critical_tests and r.success]
    
    sys.exit(0 if len(critical_passed) == len(critical_tests) else 1)


if __name__ == '__main__':
    main()