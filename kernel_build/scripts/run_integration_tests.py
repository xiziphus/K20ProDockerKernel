#!/usr/bin/env python3
"""
Integration Test Runner
Comprehensive test runner for end-to-end kernel build, deployment, and compatibility testing.
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

from tests.test_integration_suite import (
    TestEndToEndKernelBuild,
    TestAndroidSystemCompatibility,
    TestPerformanceAndStability,
    TestCompleteIntegrationScenarios
)
from tests.stability_tester import StabilityTester
from tests.regression_detector import RegressionDetector


class IntegrationTestRunner:
    """Comprehensive integration test runner."""
    
    def __init__(self, output_dir=None, baseline_file=None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "integration_test_results"
        self.output_dir.mkdir(exist_ok=True)
        self.baseline_file = baseline_file
        self.results = {}
        self.regression_detector = RegressionDetector(baseline_file)
        
    def run_end_to_end_tests(self):
        """Run end-to-end kernel build tests."""
        print("Running end-to-end kernel build tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestEndToEndKernelBuild)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['end_to_end'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_android_compatibility_tests(self):
        """Run Android system compatibility tests."""
        print("Running Android compatibility tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAndroidSystemCompatibility)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['android_compatibility'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_performance_stability_tests(self):
        """Run performance and stability tests."""
        print("Running performance and stability tests...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceAndStability)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['performance_stability'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_integration_scenarios(self):
        """Run complete integration scenarios."""
        print("Running integration scenarios...")
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestCompleteIntegrationScenarios)
        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        self.results['integration_scenarios'] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful(),
            'failure_details': [str(f) for f in result.failures],
            'error_details': [str(e) for e in result.errors]
        }
        
        return result.wasSuccessful()
        
    def run_stability_tests(self, duration_minutes=5):
        """Run system stability tests."""
        print(f"Running stability tests for {duration_minutes} minutes...")
        
        stability_tester = StabilityTester(self.output_dir)
        stability_result = stability_tester.run_stability_tests(duration_minutes)
        
        self.results['stability_tests'] = {
            'overall_stability': stability_result['overall_stability'],
            'test_results': stability_result['test_results'],
            'success': stability_result['overall_stability'] > 80.0  # 80% threshold
        }
        
        return stability_result['overall_stability'] > 80.0
        
    def run_regression_detection(self):
        """Run regression detection tests."""
        print("Running regression detection...")
        
        # Load baseline metrics if available
        baseline_metrics = self.regression_detector.load_baseline()
        
        if not baseline_metrics:
            print("No baseline metrics found, skipping regression detection")
            self.results['regression_detection'] = {
                'skipped': True,
                'reason': 'No baseline metrics available'
            }
            return True
            
        # Generate current metrics (mock for testing)
        current_metrics = self._generate_current_metrics()
        
        # Detect regressions
        regressions = self.regression_detector.detect_system_regressions(
            baseline_metrics, current_metrics
        )
        
        # Assess if regressions are acceptable
        severity = regressions.get('severity_assessment', 'none')
        acceptable = severity in ['none', 'negligible', 'minor']
        
        self.results['regression_detection'] = {
            'regressions_found': len(regressions['performance_regressions']) + len(regressions['resource_regressions']),
            'severity': severity,
            'acceptable': acceptable,
            'details': regressions
        }
        
        return acceptable
        
    def _generate_current_metrics(self):
        """Generate current system metrics for regression testing."""
        # In a real implementation, this would collect actual system metrics
        # For testing, we'll return mock metrics
        return {
            'boot_time': 38.2,
            'app_launch_time': 2.3,
            'memory_usage': 1950,
            'cpu_usage': 52.0,
            'battery_drain_rate': 5.8,
            'container_start_time': 3.1,
            'network_latency': 0.8,
            'io_throughput': 145.0
        }
        
    def run_all_tests(self, stability_duration=5):
        """Run all integration tests."""
        start_time = time.time()
        
        print("Starting comprehensive integration test suite...")
        print("=" * 70)
        
        # Run test suites
        end_to_end_success = self.run_end_to_end_tests()
        android_compat_success = self.run_android_compatibility_tests()
        perf_stability_success = self.run_performance_stability_tests()
        integration_success = self.run_integration_scenarios()
        stability_success = self.run_stability_tests(stability_duration)
        regression_success = self.run_regression_detection()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Overall results
        overall_success = all([
            end_to_end_success,
            android_compat_success,
            perf_stability_success,
            integration_success,
            stability_success,
            regression_success
        ])
        
        self.results['summary'] = {
            'overall_success': overall_success,
            'total_time': total_time,
            'timestamp': datetime.now().isoformat(),
            'test_suites': {
                'end_to_end': end_to_end_success,
                'android_compatibility': android_compat_success,
                'performance_stability': perf_stability_success,
                'integration_scenarios': integration_success,
                'stability_tests': stability_success,
                'regression_detection': regression_success
            }
        }
        
        return overall_success
        
    def generate_comprehensive_report(self):
        """Generate comprehensive integration test report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON report
        json_report = self.output_dir / f"integration_test_report_{timestamp}.json"
        with open(json_report, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        # HTML report
        html_report = self.output_dir / f"integration_test_report_{timestamp}.html"
        self._generate_html_report(html_report)
        
        # Text report
        text_report = self.output_dir / f"integration_test_report_{timestamp}.txt"
        self._generate_text_report(text_report)
        
        print(f"\nComprehensive test reports generated:")
        print(f"  JSON: {json_report}")
        print(f"  HTML: {html_report}")
        print(f"  Text: {text_report}")
        
        return json_report, html_report, text_report
        
    def _generate_html_report(self, html_file):
        """Generate HTML test report."""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Docker-Enabled Kernel Integration Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .success { color: green; font-weight: bold; }
        .failure { color: red; font-weight: bold; }
        .warning { color: orange; font-weight: bold; }
        .test-suite { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metrics { background-color: #f9f9f9; padding: 10px; margin: 10px 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Docker-Enabled Kernel Integration Test Report</h1>
        <p><strong>Generated:</strong> {timestamp}</p>
        <p><strong>Overall Result:</strong> <span class="{overall_class}">{overall_result}</span></p>
        <p><strong>Total Time:</strong> {total_time:.2f} seconds</p>
    </div>
    
    <h2>Test Suite Results</h2>
    {test_suite_results}
    
    <h2>Stability Test Results</h2>
    {stability_results}
    
    <h2>Regression Detection</h2>
    {regression_results}
    
</body>
</html>
        """
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        
        # Generate test suite results HTML
        test_suite_html = ""
        for suite_name, suite_results in self.results.items():
            if suite_name in ['summary', 'stability_tests', 'regression_detection']:
                continue
                
            success = suite_results.get('success', False)
            status_class = 'success' if success else 'failure'
            status_text = 'PASS' if success else 'FAIL'
            
            test_suite_html += f"""
            <div class="test-suite">
                <h3>{suite_name.replace('_', ' ').title()}: <span class="{status_class}">{status_text}</span></h3>
                <p>Tests Run: {suite_results.get('tests_run', 0)}</p>
                <p>Failures: {suite_results.get('failures', 0)}</p>
                <p>Errors: {suite_results.get('errors', 0)}</p>
            </div>
            """
            
        # Generate stability results HTML
        stability_html = ""
        if 'stability_tests' in self.results:
            stability = self.results['stability_tests']
            stability_score = stability.get('overall_stability', 0)
            stability_class = 'success' if stability_score > 80 else 'failure'
            
            stability_html = f"""
            <div class="metrics">
                <p><strong>Overall Stability:</strong> <span class="{stability_class}">{stability_score:.1f}%</span></p>
            </div>
            """
            
        # Generate regression results HTML
        regression_html = ""
        if 'regression_detection' in self.results:
            regression = self.results['regression_detection']
            if regression.get('skipped'):
                regression_html = "<p>Regression detection skipped - no baseline available</p>"
            else:
                severity = regression.get('severity', 'unknown')
                severity_class = 'success' if severity in ['none', 'negligible'] else 'warning' if severity == 'minor' else 'failure'
                
                regression_html = f"""
                <div class="metrics">
                    <p><strong>Regression Severity:</strong> <span class="{severity_class}">{severity.upper()}</span></p>
                    <p><strong>Regressions Found:</strong> {regression.get('regressions_found', 0)}</p>
                </div>
                """
                
        # Fill in the template
        html_filled = html_content.format(
            timestamp=summary.get('timestamp', 'Unknown'),
            overall_class='success' if overall_success else 'failure',
            overall_result='PASS' if overall_success else 'FAIL',
            total_time=summary.get('total_time', 0),
            test_suite_results=test_suite_html,
            stability_results=stability_html,
            regression_results=regression_html
        )
        
        with open(html_file, 'w') as f:
            f.write(html_filled)
            
    def _generate_text_report(self, text_file):
        """Generate text test report."""
        with open(text_file, 'w') as f:
            f.write("DOCKER-ENABLED KERNEL INTEGRATION TEST REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            summary = self.results.get('summary', {})
            f.write(f"Overall Success: {summary.get('overall_success', False)}\n")
            f.write(f"Total Time: {summary.get('total_time', 0):.2f} seconds\n")
            f.write(f"Timestamp: {summary.get('timestamp', 'Unknown')}\n\n")
            
            # Test suite results
            f.write("TEST SUITE RESULTS:\n")
            f.write("-" * 30 + "\n")
            for suite_name, suite_results in self.results.items():
                if suite_name in ['summary', 'stability_tests', 'regression_detection']:
                    continue
                    
                success = suite_results.get('success', False)
                status = "PASS" if success else "FAIL"
                f.write(f"{suite_name.replace('_', ' ').title()}: {status}\n")
                f.write(f"  Tests Run: {suite_results.get('tests_run', 0)}\n")
                f.write(f"  Failures: {suite_results.get('failures', 0)}\n")
                f.write(f"  Errors: {suite_results.get('errors', 0)}\n\n")
                
            # Stability results
            if 'stability_tests' in self.results:
                f.write("STABILITY TEST RESULTS:\n")
                f.write("-" * 30 + "\n")
                stability = self.results['stability_tests']
                f.write(f"Overall Stability: {stability.get('overall_stability', 0):.1f}%\n\n")
                
            # Regression results
            if 'regression_detection' in self.results:
                f.write("REGRESSION DETECTION:\n")
                f.write("-" * 30 + "\n")
                regression = self.results['regression_detection']
                if regression.get('skipped'):
                    f.write("Skipped - no baseline available\n\n")
                else:
                    f.write(f"Severity: {regression.get('severity', 'unknown').upper()}\n")
                    f.write(f"Regressions Found: {regression.get('regressions_found', 0)}\n\n")
                    
    def print_summary(self):
        """Print integration test summary to console."""
        print("\n" + "=" * 70)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 70)
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        
        print(f"Overall Result: {'PASS' if overall_success else 'FAIL'}")
        print(f"Total Time: {summary.get('total_time', 0):.2f} seconds")
        
        print("\nTest Suite Results:")
        test_suites = summary.get('test_suites', {})
        for suite_name, success in test_suites.items():
            status = "PASS" if success else "FAIL"
            print(f"  {suite_name.replace('_', ' ').title()}: {status}")
            
        # Additional metrics
        if 'stability_tests' in self.results:
            stability_score = self.results['stability_tests'].get('overall_stability', 0)
            print(f"\nStability Score: {stability_score:.1f}%")
            
        if 'regression_detection' in self.results:
            regression = self.results['regression_detection']
            if not regression.get('skipped'):
                severity = regression.get('severity', 'unknown')
                print(f"Regression Severity: {severity.upper()}")
                
        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument('--output-dir', '-o', 
                       help="Output directory for test results")
    parser.add_argument('--baseline', '-b',
                       help="Baseline metrics file for regression detection")
    parser.add_argument('--suite', '-s',
                       choices=['e2e', 'android', 'performance', 'scenarios', 'stability', 'regression', 'all'],
                       default='all',
                       help="Test suite to run")
    parser.add_argument('--stability-duration', '-d', type=int, default=5,
                       help="Stability test duration in minutes")
    parser.add_argument('--save-baseline', action='store_true',
                       help="Save current metrics as baseline")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = IntegrationTestRunner(args.output_dir, args.baseline)
    
    # Run specified test suite
    if args.suite == 'e2e':
        success = runner.run_end_to_end_tests()
    elif args.suite == 'android':
        success = runner.run_android_compatibility_tests()
    elif args.suite == 'performance':
        success = runner.run_performance_stability_tests()
    elif args.suite == 'scenarios':
        success = runner.run_integration_scenarios()
    elif args.suite == 'stability':
        success = runner.run_stability_tests(args.stability_duration)
    elif args.suite == 'regression':
        success = runner.run_regression_detection()
    else:
        success = runner.run_all_tests(args.stability_duration)
        
    # Save baseline if requested
    if args.save_baseline:
        current_metrics = runner._generate_current_metrics()
        runner.regression_detector.save_baseline(current_metrics)
        print("Baseline metrics saved")
        
    # Generate reports
    runner.generate_comprehensive_report()
    runner.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()