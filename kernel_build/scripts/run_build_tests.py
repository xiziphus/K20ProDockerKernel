#!/usr/bin/env python3
"""
Kernel Build Test Runner
Automated test runner for kernel build validation and regression testing.
"""

import sys
import os
import argparse
import unittest
import json
import time
from pathlib import Path
from datetime import datetime

# Add kernel_build to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_kernel_build_suite import (
    TestKernelConfigurationSuite,
    TestKernelCompilationSuite, 
    TestAndroidCompatibilitySuite,
    TestBuildRegressionSuite
)


class BuildTestRunner:
    """Test runner for kernel build validation."""
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "test_results"
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
        
    def run_configuration_tests(self):
        """Run kernel configuration tests."""
        print("Running kernel configuration tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestKernelConfigurationSuite)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['configuration'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_compilation_tests(self):
        """Run kernel compilation tests."""
        print("Running kernel compilation tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestKernelCompilationSuite)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['compilation'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_compatibility_tests(self):
        """Run Android compatibility tests."""
        print("Running Android compatibility tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAndroidCompatibilitySuite)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['compatibility'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_regression_tests(self):
        """Run regression detection tests."""
        print("Running regression detection tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestBuildRegressionSuite)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['regression'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_all_tests(self):
        """Run all test suites."""
        start_time = time.time()
        
        print("Starting kernel build test suite...")
        print("=" * 60)
        
        # Run test suites
        config_success = self.run_configuration_tests()
        compile_success = self.run_compilation_tests()
        compat_success = self.run_compatibility_tests()
        regression_success = self.run_regression_tests()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Overall results
        overall_success = all([config_success, compile_success, compat_success, regression_success])
        
        self.results['summary'] = {
            'overall_success': overall_success,
            'total_time': total_time,
            'timestamp': datetime.now().isoformat(),
            'test_suites': {
                'configuration': config_success,
                'compilation': compile_success,
                'compatibility': compat_success,
                'regression': regression_success
            }
        }
        
        return overall_success
        
    def generate_report(self):
        """Generate test report."""
        report_file = self.output_dir / f"build_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        # Generate human-readable report
        text_report = self.output_dir / f"build_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(text_report, 'w') as f:
            f.write("Kernel Build Test Report\n")
            f.write("=" * 50 + "\n\n")
            
            summary = self.results.get('summary', {})
            f.write(f"Overall Success: {summary.get('overall_success', False)}\n")
            f.write(f"Total Time: {summary.get('total_time', 0):.2f} seconds\n")
            f.write(f"Timestamp: {summary.get('timestamp', 'Unknown')}\n\n")
            
            # Test suite results
            for suite_name, suite_results in self.results.items():
                if suite_name == 'summary':
                    continue
                    
                f.write(f"{suite_name.title()} Tests:\n")
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
                
        print(f"\nTest reports generated:")
        print(f"  JSON: {report_file}")
        print(f"  Text: {text_report}")
        
        return report_file, text_report
        
    def print_summary(self):
        """Print test summary to console."""
        print("\n" + "=" * 60)
        print("KERNEL BUILD TEST SUMMARY")
        print("=" * 60)
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        
        print(f"Overall Result: {'PASS' if overall_success else 'FAIL'}")
        print(f"Total Time: {summary.get('total_time', 0):.2f} seconds")
        
        print("\nTest Suite Results:")
        for suite_name, suite_results in self.results.items():
            if suite_name == 'summary':
                continue
                
            success = suite_results.get('success', False)
            tests_run = suite_results.get('tests_run', 0)
            failures = suite_results.get('failures', 0)
            errors = suite_results.get('errors', 0)
            
            status = "PASS" if success else "FAIL"
            print(f"  {suite_name.title()}: {status} ({tests_run} tests, {failures} failures, {errors} errors)")
            
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run kernel build tests")
    parser.add_argument('--output-dir', '-o', 
                       help="Output directory for test results")
    parser.add_argument('--suite', '-s',
                       choices=['config', 'compile', 'compat', 'regression', 'all'],
                       default='all',
                       help="Test suite to run")
    parser.add_argument('--verbose', '-v', action='store_true',
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = BuildTestRunner(args.output_dir)
    
    # Run specified test suite
    if args.suite == 'config':
        success = runner.run_configuration_tests()
    elif args.suite == 'compile':
        success = runner.run_compilation_tests()
    elif args.suite == 'compat':
        success = runner.run_compatibility_tests()
    elif args.suite == 'regression':
        success = runner.run_regression_tests()
    else:
        success = runner.run_all_tests()
        
    # Generate reports
    runner.generate_report()
    runner.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()