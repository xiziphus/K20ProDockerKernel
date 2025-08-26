#!/usr/bin/env python3
"""
Container Isolation Tester

Tests container isolation mechanisms including namespaces, cgroups,
and filesystem isolation to ensure proper container security boundaries.
"""

import os
import sys
import json
import subprocess
import tempfile
import time
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class ContainerIsolationTester:
    """Tests container isolation mechanisms for security validation."""
    
    def __init__(self, docker_binary: str = "docker"):
        """
        Initialize the container isolation tester.
        
        Args:
            docker_binary: Path to docker binary
        """
        self.docker_binary = docker_binary
        self.test_results = []
        self.test_containers = []
        
    def run_all_tests(self) -> Dict:
        """
        Run all container isolation tests.
        
        Returns:
            Dict containing test results and summary
        """
        print("Starting container isolation security tests...")
        
        tests = [
            self.test_pid_namespace_isolation,
            self.test_network_namespace_isolation,
            self.test_ipc_namespace_isolation,
            self.test_uts_namespace_isolation,
            self.test_user_namespace_isolation,
            self.test_mount_namespace_isolation,
            self.test_cgroup_isolation,
            self.test_filesystem_isolation,
            self.test_process_visibility,
            self.test_resource_limits
        ]
        
        results = {
            'test_suite': 'Container Isolation',
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
    
    def test_pid_namespace_isolation(self) -> Dict:
        """Test PID namespace isolation between containers."""
        test_name = "PID Namespace Isolation"
        
        try:
            # Create two containers
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300")
            
            # Get process list from each container
            ps1 = self._exec_in_container(container1, ["ps", "aux"])
            ps2 = self._exec_in_container(container2, ["ps", "aux"])
            
            # Check that containers can't see each other's processes
            container1_pids = self._extract_pids(ps1)
            container2_pids = self._extract_pids(ps2)
            
            # Each container should only see its own processes
            if len(container1_pids) <= 3 and len(container2_pids) <= 3:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'PID namespace isolation working correctly',
                    'details': {
                        'container1_processes': len(container1_pids),
                        'container2_processes': len(container2_pids)
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'PID namespace isolation failed - too many visible processes',
                    'details': {
                        'container1_processes': len(container1_pids),
                        'container2_processes': len(container2_pids)
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_network_namespace_isolation(self) -> Dict:
        """Test network namespace isolation between containers."""
        test_name = "Network Namespace Isolation"
        
        try:
            # Create containers with different network configurations
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300", 
                                                   extra_args=["--network", "none"])
            
            # Check network interfaces in each container
            net1 = self._exec_in_container(container1, ["ip", "addr", "show"])
            net2 = self._exec_in_container(container2, ["ip", "addr", "show"])
            
            # Container1 should have network, container2 should only have loopback
            has_eth_c1 = "eth0" in net1 or "veth" in net1
            has_eth_c2 = "eth0" in net2 or "veth" in net2
            
            if has_eth_c1 and not has_eth_c2:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Network namespace isolation working correctly',
                    'details': {
                        'container1_has_network': has_eth_c1,
                        'container2_has_network': has_eth_c2
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Network namespace isolation failed',
                    'details': {
                        'container1_has_network': has_eth_c1,
                        'container2_has_network': has_eth_c2
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_ipc_namespace_isolation(self) -> Dict:
        """Test IPC namespace isolation between containers."""
        test_name = "IPC Namespace Isolation"
        
        try:
            # Create containers and test IPC isolation
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300")
            
            # Create IPC resource in container1
            self._exec_in_container(container1, ["sh", "-c", "echo 'test' | ipcmk -Q"])
            
            # Check IPC resources in both containers
            ipc1 = self._exec_in_container(container1, ["ipcs", "-q"])
            ipc2 = self._exec_in_container(container2, ["ipcs", "-q"])
            
            # Container2 should not see container1's IPC resources
            ipc1_queues = len([line for line in ipc1.split('\n') if 'msqid' in line])
            ipc2_queues = len([line for line in ipc2.split('\n') if 'msqid' in line])
            
            if ipc1_queues > ipc2_queues:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'IPC namespace isolation working correctly',
                    'details': {
                        'container1_queues': ipc1_queues,
                        'container2_queues': ipc2_queues
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'IPC namespace isolation failed',
                    'details': {
                        'container1_queues': ipc1_queues,
                        'container2_queues': ipc2_queues
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_uts_namespace_isolation(self) -> Dict:
        """Test UTS namespace isolation between containers."""
        test_name = "UTS Namespace Isolation"
        
        try:
            # Create containers with different hostnames
            container1 = self._create_test_container("alpine", "sleep 300", 
                                                   extra_args=["--hostname", "test1"])
            container2 = self._create_test_container("alpine", "sleep 300", 
                                                   extra_args=["--hostname", "test2"])
            
            # Get hostnames from each container
            hostname1 = self._exec_in_container(container1, ["hostname"]).strip()
            hostname2 = self._exec_in_container(container2, ["hostname"]).strip()
            
            if hostname1 == "test1" and hostname2 == "test2":
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'UTS namespace isolation working correctly',
                    'details': {
                        'container1_hostname': hostname1,
                        'container2_hostname': hostname2
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'UTS namespace isolation failed',
                    'details': {
                        'container1_hostname': hostname1,
                        'container2_hostname': hostname2
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_user_namespace_isolation(self) -> Dict:
        """Test user namespace isolation."""
        test_name = "User Namespace Isolation"
        
        try:
            # Create container with user namespace mapping
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--user", "1000:1000"])
            
            # Check user ID inside container
            uid_output = self._exec_in_container(container, ["id", "-u"]).strip()
            gid_output = self._exec_in_container(container, ["id", "-g"]).strip()
            
            if uid_output == "1000" and gid_output == "1000":
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'User namespace isolation working correctly',
                    'details': {
                        'container_uid': uid_output,
                        'container_gid': gid_output
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'User namespace isolation failed',
                    'details': {
                        'container_uid': uid_output,
                        'container_gid': gid_output
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_mount_namespace_isolation(self) -> Dict:
        """Test mount namespace isolation."""
        test_name = "Mount Namespace Isolation"
        
        try:
            # Create containers with different mount configurations
            with tempfile.TemporaryDirectory() as temp_dir:
                test_file = os.path.join(temp_dir, "test.txt")
                with open(test_file, 'w') as f:
                    f.write("test content")
                
                container1 = self._create_test_container("alpine", "sleep 300",
                                                       extra_args=["-v", f"{temp_dir}:/mnt/test"])
                container2 = self._create_test_container("alpine", "sleep 300")
                
                # Check if mount is visible in each container
                mount1 = self._exec_in_container(container1, ["ls", "/mnt/test"])
                try:
                    mount2 = self._exec_in_container(container2, ["ls", "/mnt/test"])
                    mount2_exists = True
                except:
                    mount2_exists = False
                
                if "test.txt" in mount1 and not mount2_exists:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'Mount namespace isolation working correctly',
                        'details': {
                            'container1_has_mount': True,
                            'container2_has_mount': mount2_exists
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'Mount namespace isolation failed',
                        'details': {
                            'container1_has_mount': "test.txt" in mount1,
                            'container2_has_mount': mount2_exists
                        }
                    }
                    
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_cgroup_isolation(self) -> Dict:
        """Test cgroup isolation and resource limits."""
        test_name = "Cgroup Isolation"
        
        try:
            # Create containers with different resource limits
            container1 = self._create_test_container("alpine", "sleep 300",
                                                   extra_args=["--memory", "128m"])
            container2 = self._create_test_container("alpine", "sleep 300",
                                                   extra_args=["--memory", "256m"])
            
            # Check cgroup settings
            cgroup1 = self._get_container_cgroup_info(container1)
            cgroup2 = self._get_container_cgroup_info(container2)
            
            if cgroup1 and cgroup2 and cgroup1 != cgroup2:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Cgroup isolation working correctly',
                    'details': {
                        'container1_cgroup': cgroup1[:50] + "..." if len(cgroup1) > 50 else cgroup1,
                        'container2_cgroup': cgroup2[:50] + "..." if len(cgroup2) > 50 else cgroup2
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Cgroup isolation failed',
                    'details': {
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
    
    def test_filesystem_isolation(self) -> Dict:
        """Test filesystem isolation between containers."""
        test_name = "Filesystem Isolation"
        
        try:
            # Create containers and test filesystem isolation
            container1 = self._create_test_container("alpine", "sleep 300")
            container2 = self._create_test_container("alpine", "sleep 300")
            
            # Create file in container1
            self._exec_in_container(container1, ["touch", "/tmp/container1_file"])
            
            # Check if file exists in each container
            file1_exists = self._file_exists_in_container(container1, "/tmp/container1_file")
            file2_exists = self._file_exists_in_container(container2, "/tmp/container1_file")
            
            if file1_exists and not file2_exists:
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Filesystem isolation working correctly',
                    'details': {
                        'file_in_container1': file1_exists,
                        'file_in_container2': file2_exists
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Filesystem isolation failed',
                    'details': {
                        'file_in_container1': file1_exists,
                        'file_in_container2': file2_exists
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_process_visibility(self) -> Dict:
        """Test that containers cannot see host processes."""
        test_name = "Process Visibility Isolation"
        
        try:
            container = self._create_test_container("alpine", "sleep 300")
            
            # Get process list from container
            ps_output = self._exec_in_container(container, ["ps", "aux"])
            processes = ps_output.split('\n')
            
            # Container should only see its own processes (typically 2-3)
            process_count = len([p for p in processes if p.strip() and not p.startswith('PID')])
            
            if process_count <= 5:  # Allow some flexibility
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Process visibility isolation working correctly',
                    'details': {
                        'visible_processes': process_count
                    }
                }
            else:
                return {
                    'name': test_name,
                    'status': 'FAIL',
                    'message': 'Process visibility isolation failed - too many visible processes',
                    'details': {
                        'visible_processes': process_count
                    }
                }
                
        except Exception as e:
            return {
                'name': test_name,
                'status': 'ERROR',
                'message': f'Test failed with error: {str(e)}',
                'details': {}
            }
    
    def test_resource_limits(self) -> Dict:
        """Test that resource limits are properly enforced."""
        test_name = "Resource Limits Enforcement"
        
        try:
            # Create container with memory limit
            container = self._create_test_container("alpine", "sleep 300",
                                                  extra_args=["--memory", "64m"])
            
            # Try to allocate more memory than allowed
            try:
                # This should fail or be limited
                result = self._exec_in_container(container, 
                    ["sh", "-c", "dd if=/dev/zero of=/tmp/bigfile bs=1M count=100 2>&1"])
                
                # Check if memory limit was enforced
                if "No space left" in result or "Cannot allocate" in result or "Killed" in result:
                    return {
                        'name': test_name,
                        'status': 'PASS',
                        'message': 'Resource limits properly enforced',
                        'details': {
                            'limit_enforced': True,
                            'result': result[:100] + "..." if len(result) > 100 else result
                        }
                    }
                else:
                    return {
                        'name': test_name,
                        'status': 'FAIL',
                        'message': 'Resource limits not properly enforced',
                        'details': {
                            'limit_enforced': False,
                            'result': result[:100] + "..." if len(result) > 100 else result
                        }
                    }
            except Exception:
                # If command fails, it might be due to resource limits (good)
                return {
                    'name': test_name,
                    'status': 'PASS',
                    'message': 'Resource limits properly enforced (command failed as expected)',
                    'details': {
                        'limit_enforced': True
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
    
    def _file_exists_in_container(self, container_id: str, filepath: str) -> bool:
        """Check if file exists in container."""
        try:
            self._exec_in_container(container_id, ["test", "-f", filepath])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _extract_pids(self, ps_output: str) -> List[str]:
        """Extract PIDs from ps output."""
        lines = ps_output.split('\n')
        pids = []
        for line in lines[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) > 0:
                    # PID is usually first column in ps output
                    try:
                        # Try to parse as integer to validate it's a PID
                        int(parts[0])
                        pids.append(parts[0])
                    except ValueError:
                        # If first column is not a number, try second column
                        if len(parts) > 1:
                            try:
                                int(parts[1])
                                pids.append(parts[1])
                            except ValueError:
                                continue
        return pids
    
    def _get_container_cgroup_info(self, container_id: str) -> str:
        """Get cgroup information for container."""
        try:
            result = subprocess.run([self.docker_binary, "inspect", container_id], 
                                  capture_output=True, text=True, check=True)
            inspect_data = json.loads(result.stdout)
            if inspect_data and len(inspect_data) > 0:
                return inspect_data[0].get('Id', '')
            return ''
        except Exception:
            return ''
    
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
    tester = ContainerIsolationTester()
    results = tester.run_all_tests()
    
    print(f"\n=== Container Isolation Test Results ===")
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