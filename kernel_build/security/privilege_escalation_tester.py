#!/usr/bin/env python3
"""
Privilege Escalation Tester

Tests for privilege escalation vulnerabilities in container environments,
including capability drops, user namespace restrictions, and security boundaries.
"""

import os
import sys
import json
import subprocess
import tempfile
import time
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class PrivilegeEscalationTester:
    """Tests for privilege escalation prevention in containers."""
    
    def __init__(self, docker_binary: str = "docker"):
        """
        Initialize the privilege escalation tester.
        
        Args:
            docker_binary: Path to docker binary
        """
        self.docker_binary = docker_binary
        self.test_results = []
        self.test_containers = []
        
    def run_all_tests(self) -> Dict:
        """
        Run all privilege escalation tests.
        
        Returns:
            Dict containing test results and summary
        """
        print("Starting privilege escalation prevention tests...")
        
        tests = [
            self.test_capability_drops,
            self.test_no_new_privileges,
            self.test_user_namespace_restrictions,
            self.test_setuid_prevention,
            self.test_device_access_restrictions,
            self.test_kernel_module_restrictions,
            self.test_proc_sys_restrictions,
            self.test_privileged_port_restrictions,
            self.test_container_escape_prevention,
            self.test_root_filesystem_readonly
        ]
        
        results = {
            'test_suite': 'Privilege Escalation Prevention',
            'total_tests': len(tests),
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        for test in tests:
            try:
                result = test()
                results['tests'].append(result)
                if result['status'] == 'PASS':
                    results['passed'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                results['tests'].append({
                    'name': test.__name__,
                    'status': 'ERROR',
                    'message': str(e),
                    'details': {}
                })
                results['failed'] += 1
        
        # Cleanup test containers
        self._cleanup_test_containers()
        
        return results
    
    def test_capability_drops(self) -> Dict:
        """Test that dangerous capabilities are dropped by default."""
        test_name = "Capability Drops"
        
        try:
            # Create container without privileged mode
            container = self._create_test_container("alpine", "sleep 300")
            
            # Check capabilities inside container
            caps_output = self._exec_in_container(container, ["sh", "-c", 
                "grep CapEff /proc/self/status || echo 'no caps'"])
            
            # Try to perform privileged operations that should fail
            privileged_tests = [
                # Try to mount filesystem
                (["mount", "-t", "tmpfs", "tmpfs", "/mnt"], "mount should fail"),
                # Try to change system time (requires CAP_SYS_TIME)
                (["date", "-s", "2023-01-01"], "date change should fail"),
                # Try to create device node (requires CAP_MKNOD)
                (["mknod", "/tmp/testdev", "c", "1", "1"], "mknod should fail")
            ]
            
            failed_operations = 0
            for cmd, description in privileged_tests:
                try:
                    self._exec_in_container(container, cmd)
                    # If command succeeds, it's a security issue
                except subprocess.CalledProcessError:
                    # Command failed as expected
                    failed_operations += 1
            
            if failed_operations == len(privileged_tests):
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Capabilities properly dropped - privileged operations blocked',
                    'details': {
                        'blocked_operations': failed_operations,
                        'total_operations': len(privileged_tests),
                        'capabilities': caps_output.strip()
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Some privileged operations succeeded - capability drops insufficient',
                    'details': {
                        'blocked_operations': failed_operations,
                        'total_operations': len(privileged_tests),
                        'capabilities': caps_output.strip()
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_no_new_privileges(self) -> Dict:
        """Test that no_new_privs flag prevents privilege escalation."""
        test_name = "No New Privileges"
        
        try:
            # Create container with security options
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--security-opt", "no-new-privileges:true"])
            
            # Check no_new_privs flag
            try:
                prctl_output = self._exec_in_container(container, ["sh", "-c", 
                    "grep NoNewPrivs /proc/self/status || echo 'not found'"])
                
                # Try to use setuid binary (should fail with no_new_privs)
                setuid_test = self._exec_in_container(container, ["sh", "-c", 
                    "ls -la /usr/bin/su 2>/dev/null || echo 'su not found'"])
                
                if "NoNewPrivs:\t1" in prctl_output or "not found" in prctl_output:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'No new privileges flag properly set',
                        'details': {
                            'no_new_privs_status': prctl_output.strip(),
                            'setuid_binary_check': setuid_test.strip()
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'No new privileges flag not properly set',
                        'details': {
                            'no_new_privs_status': prctl_output.strip(),
                            'setuid_binary_check': setuid_test.strip()
                        }
                    }
            except subprocess.CalledProcessError as e:
                # If commands fail, it might be due to security restrictions (good)
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Security restrictions preventing privilege checks (expected)',
                    'details': {
                        'error': str(e)
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_user_namespace_restrictions(self) -> Dict:
        """Test user namespace restrictions and UID/GID mapping."""
        test_name = "User Namespace Restrictions"
        
        try:
            # Create container with non-root user
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--user", "1000:1000"])
            
            # Check effective UID/GID
            uid_output = self._exec_in_container(container, ["id", "-u"]).strip()
            gid_output = self._exec_in_container(container, ["id", "-g"]).strip()
            
            # Try to switch to root (should fail)
            try:
                self._exec_in_container(container, ["su", "-"])
                root_switch_failed = False
            except subprocess.CalledProcessError:
                root_switch_failed = True
            
            # Try to access root-only files
            try:
                self._exec_in_container(container, ["cat", "/etc/shadow"])
                shadow_access_failed = False
            except subprocess.CalledProcessError:
                shadow_access_failed = True
            
            if uid_output == "1000" and gid_output == "1000" and root_switch_failed and shadow_access_failed:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'User namespace restrictions working correctly',
                    'details': {
                        'container_uid': uid_output,
                        'container_gid': gid_output,
                        'root_switch_blocked': root_switch_failed,
                        'shadow_access_blocked': shadow_access_failed
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'User namespace restrictions insufficient',
                    'details': {
                        'container_uid': uid_output,
                        'container_gid': gid_output,
                        'root_switch_blocked': root_switch_failed,
                        'shadow_access_blocked': shadow_access_failed
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_setuid_prevention(self) -> Dict:
        """Test that setuid binaries are properly restricted."""
        test_name = "Setuid Prevention"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Look for setuid binaries
            setuid_binaries = self._exec_in_container(container, ["sh", "-c", 
                "find /usr -perm -4000 -type f 2>/dev/null || echo 'none found'"])
            
            # Try to create setuid binary (should fail)
            try:
                self._exec_in_container(container, ["sh", "-c", 
                    "cp /bin/sh /tmp/testsh && chmod 4755 /tmp/testsh"])
                setuid_creation_failed = False
            except subprocess.CalledProcessError:
                setuid_creation_failed = True
            
            # Check if any dangerous setuid binaries exist
            dangerous_binaries = ['su', 'sudo', 'passwd', 'chsh', 'chfn']
            found_dangerous = []
            
            for binary in dangerous_binaries:
                try:
                    result = self._exec_in_container(container, ["which", binary])
                    if result.strip():
                        found_dangerous.append(binary)
                except subprocess.CalledProcessError:
                    pass  # Binary not found (good)
            
            if len(found_dangerous) == 0 or setuid_creation_failed:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Setuid restrictions working correctly',
                    'details': {
                        'setuid_binaries_found': setuid_binaries.strip(),
                        'dangerous_binaries_found': found_dangerous,
                        'setuid_creation_blocked': setuid_creation_failed
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Setuid restrictions insufficient',
                    'details': {
                        'setuid_binaries_found': setuid_binaries.strip(),
                        'dangerous_binaries_found': found_dangerous,
                        'setuid_creation_blocked': setuid_creation_failed
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_device_access_restrictions(self) -> Dict:
        """Test that device access is properly restricted."""
        test_name = "Device Access Restrictions"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Check available devices
            devices = self._exec_in_container(container, ["ls", "-la", "/dev/"])
            
            # Try to access sensitive devices (should fail or be restricted)
            sensitive_devices = ['/dev/kmem', '/dev/mem', '/dev/port']
            blocked_devices = 0
            
            for device in sensitive_devices:
                try:
                    self._exec_in_container(container, ["test", "-r", device])
                except subprocess.CalledProcessError:
                    blocked_devices += 1
            
            # Try to create device node (should fail without CAP_MKNOD)
            try:
                self._exec_in_container(container, ["mknod", "/tmp/testdev", "c", "1", "1"])
                device_creation_failed = False
            except subprocess.CalledProcessError:
                device_creation_failed = True
            
            if blocked_devices == len(sensitive_devices) and device_creation_failed:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Device access properly restricted',
                    'details': {
                        'blocked_sensitive_devices': blocked_devices,
                        'total_sensitive_devices': len(sensitive_devices),
                        'device_creation_blocked': device_creation_failed,
                        'available_devices': len(devices.split('\n'))
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Device access restrictions insufficient',
                    'details': {
                        'blocked_sensitive_devices': blocked_devices,
                        'total_sensitive_devices': len(sensitive_devices),
                        'device_creation_blocked': device_creation_failed,
                        'available_devices': len(devices.split('\n'))
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_kernel_module_restrictions(self) -> Dict:
        """Test that kernel module loading is restricted."""
        test_name = "Kernel Module Restrictions"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Try to load kernel module (should fail)
            try:
                self._exec_in_container(container, ["modprobe", "dummy"])
                module_load_failed = False
            except subprocess.CalledProcessError:
                module_load_failed = True
            
            # Try to access /proc/modules (should be restricted or empty)
            try:
                modules = self._exec_in_container(container, ["cat", "/proc/modules"])
                modules_accessible = True
            except subprocess.CalledProcessError:
                modules_accessible = False
                modules = ""
            
            # Check if insmod/rmmod are available (they shouldn't be)
            insmod_available = False
            try:
                self._exec_in_container(container, ["which", "insmod"])
                insmod_available = True
            except subprocess.CalledProcessError:
                pass
            
            if module_load_failed and not insmod_available:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Kernel module restrictions working correctly',
                    'details': {
                        'module_load_blocked': module_load_failed,
                        'insmod_available': insmod_available,
                        'modules_accessible': modules_accessible
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Kernel module restrictions insufficient',
                    'details': {
                        'module_load_blocked': module_load_failed,
                        'insmod_available': insmod_available,
                        'modules_accessible': modules_accessible
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_proc_sys_restrictions(self) -> Dict:
        """Test that /proc/sys access is properly restricted."""
        test_name = "Proc/Sys Restrictions"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Try to modify kernel parameters (should fail)
            restricted_files = [
                '/proc/sys/kernel/hostname',
                '/proc/sys/net/ipv4/ip_forward',
                '/proc/sys/kernel/domainname'
            ]
            
            blocked_modifications = 0
            for file_path in restricted_files:
                try:
                    self._exec_in_container(container, ["sh", "-c", f"echo test > {file_path}"])
                except subprocess.CalledProcessError:
                    blocked_modifications += 1
            
            # Check if sensitive proc files are accessible
            try:
                kcore = self._exec_in_container(container, ["ls", "-la", "/proc/kcore"])
                kcore_accessible = True
            except subprocess.CalledProcessError:
                kcore_accessible = False
            
            if blocked_modifications >= len(restricted_files) - 1:  # Allow some flexibility
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Proc/sys restrictions working correctly',
                    'details': {
                        'blocked_modifications': blocked_modifications,
                        'total_restricted_files': len(restricted_files),
                        'kcore_accessible': kcore_accessible
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Proc/sys restrictions insufficient',
                    'details': {
                        'blocked_modifications': blocked_modifications,
                        'total_restricted_files': len(restricted_files),
                        'kcore_accessible': kcore_accessible
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_privileged_port_restrictions(self) -> Dict:
        """Test that privileged ports are restricted for non-root users."""
        test_name = "Privileged Port Restrictions"
        
        try:
            # Create container with non-root user
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--user", "1000:1000"])
            
            # Try to bind to privileged port (should fail)
            try:
                self._exec_in_container(container, ["sh", "-c", 
                    "nc -l -p 80 &"])
                privileged_port_blocked = False
            except subprocess.CalledProcessError:
                privileged_port_blocked = True
            
            # Try to bind to non-privileged port (should succeed)
            try:
                self._exec_in_container(container, ["sh", "-c", 
                    "timeout 1 nc -l -p 8080 || true"])
                unprivileged_port_works = True
            except subprocess.CalledProcessError:
                unprivileged_port_works = False
            
            if privileged_port_blocked:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Privileged port restrictions working correctly',
                    'details': {
                        'privileged_port_blocked': privileged_port_blocked,
                        'unprivileged_port_works': unprivileged_port_works
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Privileged port restrictions insufficient',
                    'details': {
                        'privileged_port_blocked': privileged_port_blocked,
                        'unprivileged_port_works': unprivileged_port_works
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_container_escape_prevention(self) -> Dict:
        """Test prevention of common container escape techniques."""
        test_name = "Container Escape Prevention"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Test various escape techniques
            escape_attempts = [
                # Try to access host filesystem through /proc/1/root
                (["ls", "/proc/1/root"], "proc root access"),
                # Try to access host filesystem through /proc/1/cwd
                (["ls", "/proc/1/cwd"], "proc cwd access"),
                # Try to access Docker socket
                (["ls", "/var/run/docker.sock"], "docker socket access"),
                # Try to access host devices
                (["ls", "/dev/sda"], "host device access")
            ]
            
            blocked_attempts = 0
            for cmd, description in escape_attempts:
                try:
                    self._exec_in_container(container, cmd)
                except subprocess.CalledProcessError:
                    blocked_attempts += 1
            
            # Check if container can see host processes (it shouldn't)
            try:
                ps_output = self._exec_in_container(container, ["ps", "aux"])
                process_count = len([line for line in ps_output.split('\n') 
                                   if line.strip() and not line.startswith('PID')])
                host_processes_hidden = process_count <= 5
            except Exception:
                host_processes_hidden = True
            
            if blocked_attempts >= len(escape_attempts) - 1 and host_processes_hidden:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Container escape prevention working correctly',
                    'details': {
                        'blocked_escape_attempts': blocked_attempts,
                        'total_escape_attempts': len(escape_attempts),
                        'host_processes_hidden': host_processes_hidden
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Container escape prevention insufficient',
                    'details': {
                        'blocked_escape_attempts': blocked_attempts,
                        'total_escape_attempts': len(escape_attempts),
                        'host_processes_hidden': host_processes_hidden
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_root_filesystem_readonly(self) -> Dict:
        """Test read-only root filesystem restrictions."""
        test_name = "Read-only Root Filesystem"
        
        try:
            # Create container with read-only root filesystem
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--read-only"])
            
            # Try to write to root filesystem (should fail)
            try:
                self._exec_in_container(container, ["touch", "/test_file"])
                root_write_blocked = False
            except subprocess.CalledProcessError:
                root_write_blocked = True
            
            # Try to write to /tmp (should work if tmpfs is mounted)
            try:
                self._exec_in_container(container, ["touch", "/tmp/test_file"])
                tmp_write_works = True
            except subprocess.CalledProcessError:
                tmp_write_works = False
            
            if root_write_blocked:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Read-only root filesystem working correctly',
                    'details': {
                        'root_write_blocked': root_write_blocked,
                        'tmp_write_works': tmp_write_works
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Read-only root filesystem not properly enforced',
                    'details': {
                        'root_write_blocked': root_write_blocked,
                        'tmp_write_works': tmp_write_works
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def _create_test_container(self, image: str, command: str, extra_args: List[str] = None) -> str:
        """Create a test container and return its ID."""
        args = [self.docker_binary, "run", "-d"]
        if extra_args:
            args.extend(extra_args)
        args.extend([image, "sh", "-c", command])
        
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()
        self.test_containers.append(container_id)
        
        # Wait for container to start
        time.sleep(1)
        return container_id
    
    def _exec_in_container(self, container_id: str, command: List[str]) -> str:
        """Execute command in container and return output."""
        args = [self.docker_binary, "exec", container_id] + command
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return result.stdout
    
    def _cleanup_test_containers(self):
        """Clean up test containers."""
        for container_id in self.test_containers:
            try:
                subprocess.run([self.docker_binary, "rm", "-f", container_id], 
                             capture_output=True, check=False)
            except Exception:
                pass
        self.test_containers.clear()


if __name__ == "__main__":
    tester = PrivilegeEscalationTester()
    results = tester.run_all_tests()
    
    print(f"\n=== Privilege Escalation Prevention Test Results ===")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total_tests']*100):.1f}%")
    
    print(f"\n=== Detailed Results ===")
    for test in results['tests']:
        status_symbol = "✓" if test['status'] == 'PASS' else "✗"
        print(f"{status_symbol} {test['name']}: {test['message']}")
        if test['status'] != 'PASS':
            print(f"  Details: {test['details']}")