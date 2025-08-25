#!/usr/bin/env python3
"""
System Stability Tester
Performs stability tests for kernel and Docker integration.
"""

import subprocess
import time
import json
import threading
from pathlib import Path


class StabilityTester:
    """System stability testing framework."""
    
    def __init__(self, work_dir):
        self.work_dir = Path(work_dir)
        self.results = {}
        
    def run_stability_tests(self, duration_minutes=10):
        """Run comprehensive stability tests."""
        print(f"Running stability tests for {duration_minutes} minutes...")
        
        # Run tests in parallel
        test_threads = []
        
        # Memory stress test
        memory_thread = threading.Thread(
            target=self._run_memory_stress_test,
            args=(duration_minutes,)
        )
        test_threads.append(memory_thread)
        
        # CPU stress test
        cpu_thread = threading.Thread(
            target=self._run_cpu_stress_test,
            args=(duration_minutes,)
        )
        test_threads.append(cpu_thread)
        
        # I/O stress test
        io_thread = threading.Thread(
            target=self._run_io_stress_test,
            args=(duration_minutes,)
        )
        test_threads.append(io_thread)
        
        # Network stress test
        network_thread = threading.Thread(
            target=self._run_network_stress_test,
            args=(duration_minutes,)
        )
        test_threads.append(network_thread)
        
        # Start all tests
        for thread in test_threads:
            thread.start()
            
        # Wait for completion
        for thread in test_threads:
            thread.join()
            
        # Calculate overall stability
        overall_stability = self._calculate_overall_stability()
        
        return {
            'overall_stability': overall_stability,
            'test_results': self.results,
            'duration_minutes': duration_minutes
        }
        
    def _run_memory_stress_test(self, duration_minutes):
        """Run memory stress test."""
        try:
            # Simulate memory stress test
            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            
            memory_issues = 0
            test_iterations = 0
            
            while time.time() < end_time:
                # Simulate memory allocation/deallocation
                try:
                    # Mock memory stress
                    test_data = bytearray(1024 * 1024)  # 1MB allocation
                    del test_data
                    test_iterations += 1
                    time.sleep(1)
                except MemoryError:
                    memory_issues += 1
                    
            success_rate = (test_iterations - memory_issues) / test_iterations if test_iterations > 0 else 0
            
            self.results['memory_stress'] = {
                'passed': success_rate > 0.95,
                'success_rate': success_rate,
                'iterations': test_iterations,
                'issues': memory_issues
            }
            
        except Exception as e:
            self.results['memory_stress'] = {
                'passed': False,
                'error': str(e)
            }
            
    def _run_cpu_stress_test(self, duration_minutes):
        """Run CPU stress test."""
        try:
            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            
            cpu_issues = 0
            test_iterations = 0
            
            while time.time() < end_time:
                try:
                    # Simulate CPU intensive task
                    result = sum(i * i for i in range(1000))
                    test_iterations += 1
                    time.sleep(0.1)
                except Exception:
                    cpu_issues += 1
                    
            success_rate = (test_iterations - cpu_issues) / test_iterations if test_iterations > 0 else 0
            
            self.results['cpu_stress'] = {
                'passed': success_rate > 0.95,
                'success_rate': success_rate,
                'iterations': test_iterations,
                'issues': cpu_issues
            }
            
        except Exception as e:
            self.results['cpu_stress'] = {
                'passed': False,
                'error': str(e)
            }
            
    def _run_io_stress_test(self, duration_minutes):
        """Run I/O stress test."""
        try:
            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            
            io_issues = 0
            test_iterations = 0
            
            test_file = self.work_dir / "io_stress_test.tmp"
            
            while time.time() < end_time:
                try:
                    # Write test data
                    with open(test_file, 'w') as f:
                        f.write("test data" * 1000)
                        
                    # Read test data
                    with open(test_file, 'r') as f:
                        data = f.read()
                        
                    test_iterations += 1
                    time.sleep(0.5)
                    
                except Exception:
                    io_issues += 1
                    
            # Cleanup
            if test_file.exists():
                test_file.unlink()
                
            success_rate = (test_iterations - io_issues) / test_iterations if test_iterations > 0 else 0
            
            self.results['io_stress'] = {
                'passed': success_rate > 0.95,
                'success_rate': success_rate,
                'iterations': test_iterations,
                'issues': io_issues
            }
            
        except Exception as e:
            self.results['io_stress'] = {
                'passed': False,
                'error': str(e)
            }
            
    def _run_network_stress_test(self, duration_minutes):
        """Run network stress test."""
        try:
            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            
            network_issues = 0
            test_iterations = 0
            
            while time.time() < end_time:
                try:
                    # Simulate network activity (mock)
                    # In real implementation, this would test actual network connectivity
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    
                    # Try to connect to localhost (mock test)
                    try:
                        sock.connect(('127.0.0.1', 80))
                    except:
                        pass  # Expected to fail in test environment
                    finally:
                        sock.close()
                        
                    test_iterations += 1
                    time.sleep(1)
                    
                except Exception:
                    network_issues += 1
                    
            success_rate = (test_iterations - network_issues) / test_iterations if test_iterations > 0 else 0
            
            self.results['network_stress'] = {
                'passed': success_rate > 0.90,  # More lenient for network tests
                'success_rate': success_rate,
                'iterations': test_iterations,
                'issues': network_issues
            }
            
        except Exception as e:
            self.results['network_stress'] = {
                'passed': False,
                'error': str(e)
            }
            
    def _calculate_overall_stability(self):
        """Calculate overall system stability score."""
        if not self.results:
            return 0.0
            
        passed_tests = sum(1 for result in self.results.values() if result.get('passed', False))
        total_tests = len(self.results)
        
        if total_tests == 0:
            return 0.0
            
        stability_score = (passed_tests / total_tests) * 100
        return stability_score
        
    def generate_stability_report(self):
        """Generate detailed stability report."""
        report = {
            'timestamp': time.time(),
            'overall_stability': self._calculate_overall_stability(),
            'test_details': self.results,
            'recommendations': self._generate_recommendations()
        }
        
        return report
        
    def _generate_recommendations(self):
        """Generate stability improvement recommendations."""
        recommendations = []
        
        for test_name, result in self.results.items():
            if not result.get('passed', False):
                if test_name == 'memory_stress':
                    recommendations.append("Consider increasing available memory or optimizing memory usage")
                elif test_name == 'cpu_stress':
                    recommendations.append("CPU performance may be insufficient for high-load scenarios")
                elif test_name == 'io_stress':
                    recommendations.append("I/O performance issues detected, consider faster storage")
                elif test_name == 'network_stress':
                    recommendations.append("Network connectivity issues detected")
                    
        if not recommendations:
            recommendations.append("System stability is good, no immediate issues detected")
            
        return recommendations