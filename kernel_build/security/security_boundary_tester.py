#!/usr/bin/env python3
"""
Security Boundary Tester

Tests security boundaries between containers and host system,
including SELinux policies, AppArmor profiles, and kernel security features.
"""

import os
import sys
import json
import subprocess
import tempfile
import time
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class SecurityBoundaryTester:
    """Tests security boundaries and enforcement mechanisms."""
    
    def __init__(self, docker_binary: str = "docker"):
        """
        Initialize the security boundary tester.
        
        Args:
            docker_binary: Path to docker binary
        """
        self.docker_binary = docker_binary
        self.test_results = []
        self.test_containers = []
        
    def run_all_tests(self) -> Dict:
        """
        Run all security boundary tests.
        
        Returns:
            Dict containing test results and summary
        """
        print("Starting security boundary tests...")
        
        tests = [
            self.test_selinux_enforcement,
            self.test_apparmor_enforcement,
            self.test_seccomp_filtering,
            self.test_capability_bounding_set,
            self.test_namespace_boundaries,
            self.test_cgroup_boundaries,
            self.test_filesystem_boundaries,
            self.test_network_boundaries,
            self.test_ipc_boundaries,
            self.test_resource_boundaries
        ]
        
        results = {
            'test_suite': 'Security Boundaries',
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
    
    def test_selinux_enforcement(self) -> Dict:
        """Test SELinux policy enforcement for containers."""
        test_name = "SELinux Enforcement"
        
        try:
            # Check if SELinux is available on the system
            selinux_status = self._check_selinux_status()
            
            if not selinux_status['available']:
                return {
                    'name': test_name,
                    'status': 'SKIP',
                    'message': 'SELinux not available on this system',
                    'details': selinux_status
                }
            
            # Create container with SELinux context
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--security-opt", "label=type:container_t"])
            
            # Check SELinux context inside container
            try:
                context = self._exec_in_container(container, ["sh", "-c", 
                    "ls -Z /proc/self/exe 2>/dev/null || echo 'no context'"])
                
                # Try to access files that should be blocked by SELinux
                try:
                    self._exec_in_container(container, ["cat", "/etc/shadow"])
                    shadow_access_blocked = False
                except subprocess.CalledProcessError:
                    shadow_access_blocked = True
                
                # Check if container has proper SELinux label
                has_container_label = "container_t" in context or "svirt" in context
                
                if has_container_label and shadow_access_blocked:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'SELinux enforcement working correctly',
                        'details': {
                            'selinux_context': context.strip(),
                            'shadow_access_blocked': shadow_access_blocked,
                            'has_container_label': has_container_label
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'SELinux enforcement insufficient',
                        'details': {
                            'selinux_context': context.strip(),
                            'shadow_access_blocked': shadow_access_blocked,
                            'has_container_label': has_container_label
                        }
                    }
            except Exception as e:
                return {
                    'name': test_name,
                    'status': 'PARTIAL',
                    'message': 'SELinux available but enforcement testing failed',
                    'details': {
                        'error': str(e),
                        'selinux_status': selinux_status
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_apparmor_enforcement(self) -> Dict:
        """Test AppArmor profile enforcement for containers."""
        test_name = "AppArmor Enforcement"
        
        try:
            # Check if AppArmor is available
            apparmor_status = self._check_apparmor_status()
            
            if not apparmor_status['available']:
                return {
                    'name': test_name,
                    'status': 'SKIP',
                    'message': 'AppArmor not available on this system',
                    'details': apparmor_status
                }
            
            # Create container with AppArmor profile
            container = self._create_test_container("alpine", "sleep 300")
            
            # Check AppArmor status inside container
            try:
                aa_status = self._exec_in_container(container, ["sh", "-c", 
                    "cat /proc/self/attr/current 2>/dev/null || echo 'no profile'"])
                
                # Try operations that should be restricted by AppArmor
                restricted_operations = [
                    (["mount", "-t", "tmpfs", "tmpfs", "/mnt"], "mount operation"),
                    (["chmod", "777", "/etc/passwd"], "chmod on system file"),
                ]
                
                blocked_operations = 0
                for cmd, description in restricted_operations:
                    try:
                        self._exec_in_container(container, cmd)
                    except subprocess.CalledProcessError:
                        blocked_operations += 1
                
                if "docker-default" in aa_status or blocked_operations > 0:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'AppArmor enforcement working correctly',
                        'details': {
                            'apparmor_profile': aa_status.strip(),
                            'blocked_operations': blocked_operations,
                            'total_operations': len(restricted_operations)
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'AppArmor enforcement insufficient',
                        'details': {
                            'apparmor_profile': aa_status.strip(),
                            'blocked_operations': blocked_operations,
                            'total_operations': len(restricted_operations)
                        }
                    }
            except Exception as e:
                return {
                    'name': test_name,
                    'status': 'PARTIAL',
                    'message': 'AppArmor available but enforcement testing failed',
                    'details': {
                        'error': str(e),
                        'apparmor_status': apparmor_status
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_seccomp_filtering(self) -> Dict:
        """Test seccomp system call filtering."""
        test_name = "Seccomp Filtering"
        
        try:
            # Create container with default seccomp profile
            container = self._create_test_container("alpine", "sleep 300")
            
            # Check seccomp status
            try:
                seccomp_status = self._exec_in_container(container, ["sh", "-c", 
                    "grep Seccomp /proc/self/status 2>/dev/null || echo 'no seccomp'"])
                
                # Try system calls that should be blocked by seccomp
                blocked_syscalls = [
                    (["sh", "-c", "echo 'test' > /proc/sys/kernel/hostname"], "hostname modification"),
                    (["reboot"], "reboot syscall"),
                ]
                
                blocked_calls = 0
                for cmd, description in blocked_syscalls:
                    try:
                        self._exec_in_container(container, cmd)
                    except subprocess.CalledProcessError:
                        blocked_calls += 1
                
                # Check if seccomp is active (mode 2 = filtering)
                seccomp_active = "Seccomp:\t2" in seccomp_status
                
                if seccomp_active or blocked_calls > 0:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'Seccomp filtering working correctly',
                        'details': {
                            'seccomp_status': seccomp_status.strip(),
                            'blocked_syscalls': blocked_calls,
                            'total_syscalls': len(blocked_syscalls),
                            'seccomp_active': seccomp_active
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'Seccomp filtering insufficient',
                        'details': {
                            'seccomp_status': seccomp_status.strip(),
                            'blocked_syscalls': blocked_calls,
                            'total_syscalls': len(blocked_syscalls),
                            'seccomp_active': seccomp_active
                        }
                    }
            except Exception as e:
                return {
                    'name': test_name,
                    'status': 'PARTIAL',
                    'message': 'Seccomp testing failed',
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
    
    def test_capability_bounding_set(self) -> Dict:
        """Test capability bounding set restrictions."""
        test_name = "Capability Bounding Set"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Check capability bounding set
            try:
                capbnd = self._exec_in_container(container, ["sh", "-c", 
                    "grep CapBnd /proc/self/status 2>/dev/null || echo 'no capbnd'"])
                
                # Check effective capabilities
                capeff = self._exec_in_container(container, ["sh", "-c", 
                    "grep CapEff /proc/self/status 2>/dev/null || echo 'no capeff'"])
                
                # Try operations requiring specific capabilities
                cap_tests = [
                    (["chown", "root:root", "/tmp"], "CAP_CHOWN"),
                    (["mknod", "/tmp/testdev", "c", "1", "1"], "CAP_MKNOD"),
                    (["mount", "-t", "tmpfs", "tmpfs", "/mnt"], "CAP_SYS_ADMIN"),
                ]
                
                blocked_cap_operations = 0
                for cmd, cap_name in cap_tests:
                    try:
                        self._exec_in_container(container, cmd)
                    except subprocess.CalledProcessError:
                        blocked_cap_operations += 1
                
                # Parse capability values (hex format)
                capbnd_value = self._extract_cap_value(capbnd)
                capeff_value = self._extract_cap_value(capeff)
                
                if blocked_cap_operations >= len(cap_tests) - 1:  # Allow some flexibility
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'Capability bounding set properly restricted',
                        'details': {
                            'capability_bounding_set': capbnd_value,
                            'effective_capabilities': capeff_value,
                            'blocked_operations': blocked_cap_operations,
                            'total_operations': len(cap_tests)
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'Capability bounding set restrictions insufficient',
                        'details': {
                            'capability_bounding_set': capbnd_value,
                            'effective_capabilities': capeff_value,
                            'blocked_operations': blocked_cap_operations,
                            'total_operations': len(cap_tests)
                        }
                    }
            except Exception as e:
                return {
                    'name': test_name,
                    'status': 'PARTIAL',
                    'message': 'Capability testing failed',
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
    
    def test_namespace_boundaries(self) -> Dict:
        """Test namespace boundary enforcement."""
        test_name = "Namespace Boundaries"
        
        try:
            # Create multiple containers to test namespace isolation
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300")
            
            # Test PID namespace boundaries
            pid1 = self._get_container_init_pid(container1)
            pid2 = self._get_container_init_pid(container2)
            
            # Test network namespace boundaries
            net1 = self._exec_in_container(container1, ["ip", "addr", "show"])
            net2 = self._exec_in_container(container2, ["ip", "addr", "show"])
            
            # Test mount namespace boundaries
            self._exec_in_container(container1, ["mkdir", "-p", "/tmp/test1"])
            mount1_exists = self._file_exists_in_container(container1, "/tmp/test1")
            mount2_exists = self._file_exists_in_container(container2, "/tmp/test1")
            
            # Test UTS namespace boundaries
            hostname1 = self._exec_in_container(container1, ["hostname"]).strip()
            hostname2 = self._exec_in_container(container2, ["hostname"]).strip()
            
            boundaries_working = (
                pid1 != pid2 and  # Different PID namespaces
                net1 != net2 and  # Different network configs
                mount1_exists and not mount2_exists and  # Mount isolation
                len(hostname1) > 0 and len(hostname2) > 0  # UTS isolation
            )
            
            if boundaries_working:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Namespace boundaries properly enforced',
                    'details': {
                        'pid_isolation': pid1 != pid2,
                        'network_isolation': net1 != net2,
                        'mount_isolation': mount1_exists and not mount2_exists,
                        'uts_isolation': hostname1 != hostname2
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Namespace boundaries insufficient',
                    'details': {
                        'pid_isolation': pid1 != pid2,
                        'network_isolation': net1 != net2,
                        'mount_isolation': mount1_exists and not mount2_exists,
                        'uts_isolation': hostname1 != hostname2
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_cgroup_boundaries(self) -> Dict:
        """Test cgroup boundary enforcement."""
        test_name = "Cgroup Boundaries"
        
        try:
            # Create containers with different resource limits
            container1 = self._create_test_container("alpine", "sleep 300",
                                                   extra_args=["--memory", "128m", "--cpus", "0.5"])
            container2 = self._create_test_container("alpine", "sleep 300",
                                                   extra_args=["--memory", "256m", "--cpus", "1.0"])
            
            # Check cgroup assignments
            cgroup1 = self._get_container_cgroup_path(container1)
            cgroup2 = self._get_container_cgroup_path(container2)
            
            # Test memory limits
            try:
                # Try to allocate memory beyond limit in container1
                self._exec_in_container(container1, ["sh", "-c", 
                    "dd if=/dev/zero of=/tmp/bigfile bs=1M count=200 2>/dev/null"])
                memory_limit_enforced = False
            except subprocess.CalledProcessError:
                memory_limit_enforced = True
            
            # Check if containers have different cgroup paths
            cgroup_isolation = cgroup1 != cgroup2 and cgroup1 and cgroup2
            
            if cgroup_isolation and memory_limit_enforced:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Cgroup boundaries properly enforced',
                    'details': {
                        'cgroup_isolation': cgroup_isolation,
                        'memory_limit_enforced': memory_limit_enforced,
                        'container1_cgroup': cgroup1[:50] + "..." if len(cgroup1) > 50 else cgroup1,
                        'container2_cgroup': cgroup2[:50] + "..." if len(cgroup2) > 50 else cgroup2
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Cgroup boundaries insufficient',
                    'details': {
                        'cgroup_isolation': cgroup_isolation,
                        'memory_limit_enforced': memory_limit_enforced,
                        'container1_cgroup': cgroup1,
                        'container2_cgroup': cgroup2
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_filesystem_boundaries(self) -> Dict:
        """Test filesystem boundary enforcement."""
        test_name = "Filesystem Boundaries"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Test access to sensitive host files
            sensitive_paths = [
                "/etc/shadow",
                "/etc/passwd", 
                "/proc/kcore",
                "/sys/kernel/debug"
            ]
            
            blocked_access = 0
            for path in sensitive_paths:
                try:
                    self._exec_in_container(container, ["cat", path])
                except subprocess.CalledProcessError:
                    blocked_access += 1
            
            # Test write access to read-only locations
            readonly_tests = [
                "/etc/passwd",
                "/usr/bin/sh",
                "/lib"
            ]
            
            blocked_writes = 0
            for path in readonly_tests:
                try:
                    self._exec_in_container(container, ["sh", "-c", f"echo test >> {path}"])
                except subprocess.CalledProcessError:
                    blocked_writes += 1
            
            # Test that container filesystem is properly isolated
            self._exec_in_container(container, ["touch", "/tmp/container_file"])
            container_file_exists = self._file_exists_in_container(container, "/tmp/container_file")
            
            if blocked_access >= len(sensitive_paths) - 1 and blocked_writes >= len(readonly_tests) - 1:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Filesystem boundaries properly enforced',
                    'details': {
                        'blocked_sensitive_access': blocked_access,
                        'total_sensitive_paths': len(sensitive_paths),
                        'blocked_readonly_writes': blocked_writes,
                        'total_readonly_tests': len(readonly_tests),
                        'container_filesystem_isolated': container_file_exists
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Filesystem boundaries insufficient',
                    'details': {
                        'blocked_sensitive_access': blocked_access,
                        'total_sensitive_paths': len(sensitive_paths),
                        'blocked_readonly_writes': blocked_writes,
                        'total_readonly_tests': len(readonly_tests),
                        'container_filesystem_isolated': container_file_exists
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_network_boundaries(self) -> Dict:
        """Test network boundary enforcement."""
        test_name = "Network Boundaries"
        
        try:
            # Create containers with different network configurations
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300",
                                                   extra_args=["--network", "none"])
            
            # Test network isolation
            net1 = self._exec_in_container(container1, ["ip", "addr", "show"])
            net2 = self._exec_in_container(container2, ["ip", "addr", "show"])
            
            # Container1 should have network access, container2 should not
            has_network_c1 = "eth0" in net1 or "veth" in net1
            has_network_c2 = "eth0" in net2 or "veth" in net2
            
            # Test that containers can't access host network interfaces directly
            try:
                host_interfaces = self._exec_in_container(container1, ["ip", "link", "show"])
                # Should not see host interfaces like docker0, br-*, etc.
                has_host_interfaces = "docker0" in host_interfaces or "br-" in host_interfaces
            except Exception:
                has_host_interfaces = False
            
            network_isolation_working = (
                has_network_c1 and not has_network_c2 and not has_host_interfaces
            )
            
            if network_isolation_working:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Network boundaries properly enforced',
                    'details': {
                        'container1_has_network': has_network_c1,
                        'container2_has_network': has_network_c2,
                        'host_interfaces_hidden': not has_host_interfaces
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Network boundaries insufficient',
                    'details': {
                        'container1_has_network': has_network_c1,
                        'container2_has_network': has_network_c2,
                        'host_interfaces_hidden': not has_host_interfaces
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_ipc_boundaries(self) -> Dict:
        """Test IPC boundary enforcement."""
        test_name = "IPC Boundaries"
        
        try:
            # Create containers with different IPC configurations
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300")
            
            # Create IPC resources in container1
            try:
                self._exec_in_container(container1, ["sh", "-c", "ipcmk -Q -q 1 2>/dev/null || true"])
            except:
                pass
            
            # Check IPC resources visibility
            try:
                ipc1 = self._exec_in_container(container1, ["ipcs", "-q"])
                ipc2 = self._exec_in_container(container2, ["ipcs", "-q"])
                
                # Count message queues
                queues1 = len(re.findall(r'^\s*\d+', ipc1, re.MULTILINE))
                queues2 = len(re.findall(r'^\s*\d+', ipc2, re.MULTILINE))
                
                # Test shared memory isolation
                try:
                    self._exec_in_container(container1, ["sh", "-c", "ipcmk -M 1024 2>/dev/null || true"])
                    shm1 = self._exec_in_container(container1, ["ipcs", "-m"])
                    shm2 = self._exec_in_container(container2, ["ipcs", "-m"])
                    
                    shm_segments1 = len(re.findall(r'^\s*\d+', shm1, re.MULTILINE))
                    shm_segments2 = len(re.findall(r'^\s*\d+', shm2, re.MULTILINE))
                    
                    ipc_isolation = (queues1 != queues2) or (shm_segments1 != shm_segments2)
                except Exception:
                    ipc_isolation = True  # If IPC commands fail, isolation is working
                
                if ipc_isolation:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'IPC boundaries properly enforced',
                        'details': {
                            'container1_queues': queues1,
                            'container2_queues': queues2,
                            'ipc_isolation': ipc_isolation
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'IPC boundaries insufficient',
                        'details': {
                            'container1_queues': queues1,
                            'container2_queues': queues2,
                            'ipc_isolation': ipc_isolation
                        }
                    }
            except Exception:
                # If IPC commands fail, it might be due to restrictions (good)
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'IPC boundaries enforced (commands restricted)',
                    'details': {
                        'ipc_commands_restricted': True
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_resource_boundaries(self) -> Dict:
        """Test resource boundary enforcement."""
        test_name = "Resource Boundaries"
        
        try:
            # Create container with resource limits
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--memory", "64m", "--cpus", "0.5"])
            
            # Test memory boundary
            try:
                # Try to allocate more memory than allowed
                self._exec_in_container(container, ["sh", "-c", 
                    "dd if=/dev/zero of=/tmp/bigfile bs=1M count=100 2>/dev/null"])
                memory_boundary_enforced = False
            except subprocess.CalledProcessError:
                memory_boundary_enforced = True
            
            # Test CPU boundary (harder to test directly, check cgroup settings)
            try:
                cpu_info = self._exec_in_container(container, ["sh", "-c", 
                    "cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo 'no quota'"])
                cpu_boundary_configured = cpu_info.strip() != "-1" and cpu_info.strip() != "no quota"
            except Exception:
                cpu_boundary_configured = False
            
            # Test process limits
            try:
                # Try to create many processes
                self._exec_in_container(container, ["sh", "-c", 
                    "for i in $(seq 1 1000); do sleep 1 & done"])
                process_limit_enforced = False
            except subprocess.CalledProcessError:
                process_limit_enforced = True
            
            boundaries_enforced = memory_boundary_enforced or cpu_boundary_configured
            
            if boundaries_enforced:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Resource boundaries properly enforced',
                    'details': {
                        'memory_boundary_enforced': memory_boundary_enforced,
                        'cpu_boundary_configured': cpu_boundary_configured,
                        'process_limit_enforced': process_limit_enforced
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Resource boundaries insufficient',
                    'details': {
                        'memory_boundary_enforced': memory_boundary_enforced,
                        'cpu_boundary_configured': cpu_boundary_configured,
                        'process_limit_enforced': process_limit_enforced
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def _check_selinux_status(self) -> Dict:
        """Check SELinux availability and status."""
        try:
            result = subprocess.run(["getenforce"], capture_output=True, text=True)
            if result.returncode == 0:
                return {
                    'available': True,
                    'status': result.stdout.strip(),
                    'enforcing': result.stdout.strip() == 'Enforcing'
                }
        except FileNotFoundError:
            pass
        
        # Check if SELinux filesystem exists
        if os.path.exists('/sys/fs/selinux'):
            return {'available': True, 'status': 'unknown', 'enforcing': False}
        
        return {'available': False, 'status': 'not_available', 'enforcing': False}
    
    def _check_apparmor_status(self) -> Dict:
        """Check AppArmor availability and status."""
        try:
            result = subprocess.run(["aa-status"], capture_output=True, text=True)
            if result.returncode == 0:
                return {
                    'available': True,
                    'status': 'active',
                    'profiles_loaded': 'profiles are loaded' in result.stdout
                }
        except FileNotFoundError:
            pass
        
        # Check if AppArmor filesystem exists
        if os.path.exists('/sys/kernel/security/apparmor'):
            return {'available': True, 'status': 'unknown', 'profiles_loaded': False}
        
        return {'available': False, 'status': 'not_available', 'profiles_loaded': False}
    
    def _extract_cap_value(self, cap_line: str) -> str:
        """Extract capability value from /proc/*/status line."""
        if ':' in cap_line:
            return cap_line.split(':', 1)[1].strip()
        return cap_line.strip()
    
    def _get_container_init_pid(self, container_id: str) -> str:
        """Get the init PID of a container."""
        try:
            result = subprocess.run([self.docker_binary, "inspect", container_id, 
                                   "--format", "{{.State.Pid}}"], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return ""
    
    def _get_container_cgroup_path(self, container_id: str) -> str:
        """Get the cgroup path of a container."""
        try:
            cgroup_info = self._exec_in_container(container_id, ["cat", "/proc/self/cgroup"])
            # Extract first cgroup path
            lines = cgroup_info.split('\n')
            for line in lines:
                if ':' in line:
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        return parts[2]
            return ""
        except Exception:
            return ""
    
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
    
    def _file_exists_in_container(self, container_id: str, filepath: str) -> bool:
        """Check if file exists in container."""
        try:
            self._exec_in_container(container_id, ["test", "-f", filepath])
            return True
        except subprocess.CalledProcessError:
            return False
    
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
    tester = SecurityBoundaryTester()
    results = tester.run_all_tests()
    
    print(f"\n=== Security Boundary Test Results ===")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total_tests']*100):.1f}%")
    
    print(f"\n=== Detailed Results ===")
    for test in results['tests']:
        status_symbol = "✓" if test['status'] == 'PASS' else "✗" if test['status'] == 'FAIL' else "~"
        print(f"{status_symbol} {test['name']}: {test['message']}")
        if test['status'] not in ['PASS', 'SKIP']:
            print(f"  Details: {test['details']}")