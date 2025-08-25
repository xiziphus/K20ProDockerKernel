#!/usr/bin/env python3
"""
Docker Functionality Test Runner
Automated test runner for Docker daemon, container lifecycle, networking, and storage tests.
"""

import sys
import os
import argparse
import unittest
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Add kernel_build to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_docker_functionality import (
    TestDockerDaemonStartup,
    TestContainerLifecycle,
    TestDockerNetworking,
    TestDockerStorage,
    TestDockerIntegrationScenarios
)


class DockerTestRunner:
    """Test runner for Docker functionality validation."""
    
    def __init__(self, output_dir=None, docker_available=False):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "docker_test_results"
        self.output_dir.mkdir(exist_ok=True)
        self.docker_available = docker_available
        self.results = {}
        
    def check_docker_availability(self):
        """Check if Docker is available for testing."""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"Docker available: {result.stdout.strip()}")
                return True
            else:
                print("Docker not available or not responding")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Docker not found or not responding")
            return False
            
    def check_docker_daemon_status(self):
        """Check if Docker daemon is running."""
        try:
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("Docker daemon is running")
                return True
            else:
                print("Docker daemon is not running")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Cannot check Docker daemon status")
            return False
            
    def run_daemon_tests(self):
        """Run Docker daemon startup tests."""
        print("Running Docker daemon tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestDockerDaemonStartup)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['daemon'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_container_lifecycle_tests(self):
        """Run container lifecycle tests."""
        print("Running container lifecycle tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestContainerLifecycle)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['container_lifecycle'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_networking_tests(self):
        """Run Docker networking tests."""
        print("Running Docker networking tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestDockerNetworking)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['networking'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_storage_tests(self):
        """Run Docker storage tests."""
        print("Running Docker storage tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestDockerStorage)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['storage'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_integration_tests(self):
        """Run Docker integration scenario tests."""
        print("Running Docker integration tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestDockerIntegrationScenarios)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['integration'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_live_docker_tests(self):
        """Run tests against live Docker daemon."""
        if not self.docker_available:
            print("Skipping live Docker tests - Docker not available")
            return True
            
        print("Running live Docker tests...")
        
        # Test basic Docker functionality
        live_results = {
            'docker_version': self.test_docker_version(),
            'docker_info': self.test_docker_info(),
            'image_pull': self.test_image_pull(),
            'container_run': self.test_container_run(),
            'network_create': self.test_network_create(),
            'volume_create': self.test_volume_create()
        }
        
        self.results['live_tests'] = live_results
        
        # Return True if all live tests passed
        return all(live_results.values())
        
    def test_docker_version(self):
        """Test Docker version command."""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False
            
    def test_docker_info(self):
        """Test Docker info command."""
        try:
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False
            
    def test_image_pull(self):
        """Test Docker image pull."""
        try:
            result = subprocess.run(['docker', 'pull', 'alpine:latest'], 
                                  capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except:
            return False
            
    def test_container_run(self):
        """Test Docker container run."""
        try:
            # Run a simple container
            result = subprocess.run(['docker', 'run', '--rm', 'alpine:latest', 'echo', 'hello'], 
                                  capture_output=True, text=True, timeout=30)
            return result.returncode == 0 and 'hello' in result.stdout
        except:
            return False
            
    def test_network_create(self):
        """Test Docker network creation."""
        try:
            # Create test network
            result = subprocess.run(['docker', 'network', 'create', 'test_network'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False
                
            # Clean up
            subprocess.run(['docker', 'network', 'rm', 'test_network'], 
                          capture_output=True, text=True, timeout=10)
            return True
        except:
            return False
            
    def test_volume_create(self):
        """Test Docker volume creation."""
        try:
            # Create test volume
            result = subprocess.run(['docker', 'volume', 'create', 'test_volume'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False
                
            # Clean up
            subprocess.run(['docker', 'volume', 'rm', 'test_volume'], 
                          capture_output=True, text=True, timeout=10)
            return True
        except:
            return False
            
    def run_all_tests(self):
        """Run all Docker functionality tests."""
        start_time = time.time()
        
        print("Starting Docker functionality test suite...")
        print("=" * 60)
        
        # Check Docker availability
        self.docker_available = self.check_docker_availability()
        if self.docker_available:
            daemon_running = self.check_docker_daemon_status()
            if not daemon_running:
                print("Warning: Docker daemon not running, some tests may fail")
        
        # Run test suites
        daemon_success = self.run_daemon_tests()
        lifecycle_success = self.run_container_lifecycle_tests()
        networking_success = self.run_networking_tests()
        storage_success = self.run_storage_tests()
        integration_success = self.run_integration_tests()
        live_success = self.run_live_docker_tests()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Overall results
        overall_success = all([
            daemon_success, lifecycle_success, networking_success, 
            storage_success, integration_success, live_success
        ])
        
        self.results['summary'] = {
            'overall_success': overall_success,
            'total_time': total_time,
            'timestamp': datetime.now().isoformat(),
            'docker_available': self.docker_available,
            'test_suites': {
                'daemon': daemon_success,
                'container_lifecycle': lifecycle_success,
                'networking': networking_success,
                'storage': storage_success,
                'integration': integration_success,
                'live_tests': live_success
            }
        }
        
        return overall_success
        
    def generate_report(self):
        """Generate Docker test report."""
        report_file = self.output_dir / f"docker_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        # Generate human-readable report
        text_report = self.output_dir / f"docker_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(text_report, 'w') as f:
            f.write("Docker Functionality Test Report\n")
            f.write("=" * 50 + "\n\n")
            
            summary = self.results.get('summary', {})
            f.write(f"Overall Success: {summary.get('overall_success', False)}\n")
            f.write(f"Total Time: {summary.get('total_time', 0):.2f} seconds\n")
            f.write(f"Docker Available: {summary.get('docker_available', False)}\n")
            f.write(f"Timestamp: {summary.get('timestamp', 'Unknown')}\n\n")
            
            # Test suite results
            for suite_name, suite_results in self.results.items():
                if suite_name in ['summary', 'live_tests']:
                    continue
                    
                f.write(f"{suite_name.replace('_', ' ').title()} Tests:\n")
                f.write(f"  Tests Run: {suite_results.get('tests_run', 0)}\n")
                f.write(f"  Failures: {suite_results.get('failures', 0)}\n")
                f.write(f"  Errors: {suite_results.get('errors', 0)}\n")
                f.write(f"  Success: {suite_results.get('success', False)}\n")
                
                if suite_results.get('failure_details'):
                    f.write("  Failure Details:\n")
                    for failure in suite_results['failure_details']:
                        f.write(f"    - {failure}\n")
                        
                if suite_results.get('error_details'):
                    f.write("  Error Details:\n")
                    for error in suite_results['error_details']:
                        f.write(f"    - {error}\n")
                        
                f.write("\n")
                
            # Live test results
            if 'live_tests' in self.results:
                f.write("Live Docker Tests:\n")
                for test_name, result in self.results['live_tests'].items():
                    status = "PASS" if result else "FAIL"
                    f.write(f"  {test_name.replace('_', ' ').title()}: {status}\n")
                f.write("\n")
                
        print(f"\nDocker test reports generated:")
        print(f"  JSON: {report_file}")
        print(f"  Text: {text_report}")
        
        return report_file, text_report
        
    def print_summary(self):
        """Print Docker test summary to console."""
        print("\n" + "=" * 60)
        print("DOCKER FUNCTIONALITY TEST SUMMARY")
        print("=" * 60)
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        
        print(f"Overall Result: {'PASS' if overall_success else 'FAIL'}")
        print(f"Total Time: {summary.get('total_time', 0):.2f} seconds")
        print(f"Docker Available: {summary.get('docker_available', False)}")
        
        print("\nTest Suite Results:")
        for suite_name, suite_results in self.results.items():
            if suite_name in ['summary', 'live_tests']:
                continue
                
            success = suite_results.get('success', False)
            tests_run = suite_results.get('tests_run', 0)
            failures = suite_results.get('failures', 0)
            errors = suite_results.get('errors', 0)
            
            status = "PASS" if success else "FAIL"
            print(f"  {suite_name.replace('_', ' ').title()}: {status} ({tests_run} tests, {failures} failures, {errors} errors)")
            
        # Live test results
        if 'live_tests' in self.results:
            print("\nLive Docker Tests:")
            for test_name, result in self.results['live_tests'].items():
                status = "PASS" if result else "FAIL"
                print(f"  {test_name.replace('_', ' ').title()}: {status}")
                
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Docker functionality tests")
    parser.add_argument('--output-dir', '-o', 
                       help="Output directory for test results")
    parser.add_argument('--suite', '-s',
                       choices=['daemon', 'lifecycle', 'networking', 'storage', 'integration', 'live', 'all'],
                       default='all',
                       help="Test suite to run")
    parser.add_argument('--skip-live', action='store_true',
                       help="Skip live Docker tests")
    parser.add_argument('--verbose', '-v', action='store_true',
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = DockerTestRunner(args.output_dir)
    
    # Run specified test suite
    if args.suite == 'daemon':
        success = runner.run_daemon_tests()
    elif args.suite == 'lifecycle':
        success = runner.run_container_lifecycle_tests()
    elif args.suite == 'networking':
        success = runner.run_networking_tests()
    elif args.suite == 'storage':
        success = runner.run_storage_tests()
    elif args.suite == 'integration':
        success = runner.run_integration_tests()
    elif args.suite == 'live':
        runner.docker_available = runner.check_docker_availability()
        success = runner.run_live_docker_tests()
    else:
        if args.skip_live:
            runner.docker_available = False
        success = runner.run_all_tests()
        
    # Generate reports
    runner.generate_report()
    runner.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()