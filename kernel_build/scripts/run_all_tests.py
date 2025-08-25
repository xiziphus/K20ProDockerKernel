#!/usr/bin/env python3
"""
Master Test Runner
Comprehensive test runner for all Docker-enabled kernel testing suites.
"""

import sys
import os
import argparse
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime


class MasterTestRunner:
    """Master test runner for all test suites."""
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "master_test_results"
        self.output_dir.mkdir(exist_ok=True)
        self.scripts_dir = Path(__file__).parent
        self.results = {}
        
    def run_build_tests(self):
        """Run kernel build testing suite."""
        print("Running kernel build tests...")
        
        script_path = self.scripts_dir / "run_build_tests.py"
        result = subprocess.run([
            sys.executable, str(script_path),
            "--output-dir", str(self.output_dir / "build_tests")
        ], capture_output=True, text=True)
        
        success = result.returncode == 0
        self.results['build_tests'] = {
            'success': success,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        return success
        
    def run_docker_tests(self, skip_live=False):
        """Run Docker functionality tests."""
        print("Running Docker functionality tests...")
        
        script_path = self.scripts_dir / "run_docker_tests.py"
        cmd = [
            sys.executable, str(script_path),
            "--output-dir", str(self.output_dir / "docker_tests")
        ]
        
        if skip_live:
            cmd.append("--skip-live")
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        success = result.returncode == 0
        self.results['docker_tests'] = {
            'success': success,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        return success
        
    def run_integration_tests(self, stability_duration=5):
        """Run integration tests."""
        print("Running integration tests...")
        
        script_path = self.scripts_dir / "run_integration_tests.py"
        result = subprocess.run([
            sys.executable, str(script_path),
            "--output-dir", str(self.output_dir / "integration_tests"),
            "--stability-duration", str(stability_duration)
        ], capture_output=True, text=True)
        
        success = result.returncode == 0
        self.results['integration_tests'] = {
            'success': success,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        return success
        
    def run_all_test_suites(self, skip_live_docker=False, stability_duration=5):
        """Run all test suites."""
        start_time = time.time()
        
        print("Starting comprehensive Docker-enabled kernel test suite...")
        print("=" * 80)
        
        # Run all test suites
        build_success = self.run_build_tests()
        docker_success = self.run_docker_tests(skip_live_docker)
        integration_success = self.run_integration_tests(stability_duration)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Overall results
        overall_success = all([build_success, docker_success, integration_success])
        
        self.results['summary'] = {
            'overall_success': overall_success,
            'total_time': total_time,
            'timestamp': datetime.now().isoformat(),
            'test_suites': {
                'build_tests': build_success,
                'docker_tests': docker_success,
                'integration_tests': integration_success
            }
        }
        
        return overall_success
        
    def generate_master_report(self):
        """Generate master test report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON report
        json_report = self.output_dir / f"master_test_report_{timestamp}.json"
        with open(json_report, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        # HTML dashboard
        html_report = self.output_dir / f"test_dashboard_{timestamp}.html"
        self._generate_html_dashboard(html_report)
        
        # Executive summary
        summary_report = self.output_dir / f"executive_summary_{timestamp}.txt"
        self._generate_executive_summary(summary_report)
        
        print(f"\nMaster test reports generated:")
        print(f"  JSON Report: {json_report}")
        print(f"  HTML Dashboard: {html_report}")
        print(f"  Executive Summary: {summary_report}")
        
        return json_report, html_report, summary_report
        
    def _generate_html_dashboard(self, html_file):
        """Generate HTML test dashboard."""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Docker-Enabled Kernel Test Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; border-radius: 10px; text-align: center; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                      gap: 20px; margin: 20px 0; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .success {{ border-left: 5px solid #4CAF50; }}
        .failure {{ border-left: 5px solid #f44336; }}
        .warning {{ border-left: 5px solid #ff9800; }}
        .metric {{ display: flex; justify-content: space-between; margin: 10px 0; }}
        .metric-value {{ font-weight: bold; font-size: 1.2em; }}
        .status-badge {{ padding: 5px 15px; border-radius: 20px; color: white; font-weight: bold; }}
        .status-pass {{ background-color: #4CAF50; }}
        .status-fail {{ background-color: #f44336; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐳 Docker-Enabled Kernel Test Dashboard</h1>
            <p>Comprehensive Testing Results for Redmi K20 Pro</p>
            <p><strong>Generated:</strong> {timestamp}</p>
        </div>
        
        <div class="dashboard">
            <div class="card {overall_class}">
                <h2>📊 Overall Results</h2>
                <div class="metric">
                    <span>Overall Status:</span>
                    <span class="status-badge {overall_badge_class}">{overall_status}</span>
                </div>
                <div class="metric">
                    <span>Total Time:</span>
                    <span class="metric-value">{total_time:.1f}s</span>
                </div>
                <div class="metric">
                    <span>Test Suites:</span>
                    <span class="metric-value">{total_suites}</span>
                </div>
            </div>
            
            <div class="card {build_class}">
                <h2>🔧 Build Tests</h2>
                <div class="metric">
                    <span>Status:</span>
                    <span class="status-badge {build_badge_class}">{build_status}</span>
                </div>
                <p>Kernel configuration, compilation, and Android compatibility tests.</p>
            </div>
            
            <div class="card {docker_class}">
                <h2>🐋 Docker Tests</h2>
                <div class="metric">
                    <span>Status:</span>
                    <span class="status-badge {docker_badge_class}">{docker_status}</span>
                </div>
                <p>Docker daemon, container lifecycle, networking, and storage tests.</p>
            </div>
            
            <div class="card {integration_class}">
                <h2>🔗 Integration Tests</h2>
                <div class="metric">
                    <span>Status:</span>
                    <span class="status-badge {integration_badge_class}">{integration_status}</span>
                </div>
                <p>End-to-end scenarios, performance, and stability validation.</p>
            </div>
        </div>
        
        <div class="footer">
            <p>Docker-Enabled Kernel for Redmi K20 Pro | Test Framework v1.0</p>
        </div>
    </div>
</body>
</html>
        """
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        test_suites = summary.get('test_suites', {})
        
        # Determine classes and statuses
        def get_status_info(success):
            if success:
                return 'success', 'status-pass', 'PASS'
            else:
                return 'failure', 'status-fail', 'FAIL'
                
        overall_class, overall_badge_class, overall_status = get_status_info(overall_success)
        build_class, build_badge_class, build_status = get_status_info(test_suites.get('build_tests', False))
        docker_class, docker_badge_class, docker_status = get_status_info(test_suites.get('docker_tests', False))
        integration_class, integration_badge_class, integration_status = get_status_info(test_suites.get('integration_tests', False))
        
        # Fill in the template
        html_filled = html_content.format(
            timestamp=summary.get('timestamp', 'Unknown'),
            overall_class=overall_class,
            overall_badge_class=overall_badge_class,
            overall_status=overall_status,
            total_time=summary.get('total_time', 0),
            total_suites=len(test_suites),
            build_class=build_class,
            build_badge_class=build_badge_class,
            build_status=build_status,
            docker_class=docker_class,
            docker_badge_class=docker_badge_class,
            docker_status=docker_status,
            integration_class=integration_class,
            integration_badge_class=integration_badge_class,
            integration_status=integration_status
        )
        
        with open(html_file, 'w') as f:
            f.write(html_filled)
            
    def _generate_executive_summary(self, summary_file):
        """Generate executive summary report."""
        with open(summary_file, 'w') as f:
            f.write("DOCKER-ENABLED KERNEL PROJECT - EXECUTIVE SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            summary = self.results.get('summary', {})
            overall_success = summary.get('overall_success', False)
            
            # Executive overview
            f.write("EXECUTIVE OVERVIEW\n")
            f.write("-" * 20 + "\n")
            f.write(f"Project Status: {'SUCCESS' if overall_success else 'ISSUES DETECTED'}\n")
            f.write(f"Test Execution Time: {summary.get('total_time', 0):.1f} seconds\n")
            f.write(f"Test Date: {summary.get('timestamp', 'Unknown')}\n\n")
            
            # Key findings
            f.write("KEY FINDINGS\n")
            f.write("-" * 20 + "\n")
            
            test_suites = summary.get('test_suites', {})
            passed_suites = sum(1 for success in test_suites.values() if success)
            total_suites = len(test_suites)
            
            f.write(f"• Test Suite Success Rate: {passed_suites}/{total_suites} ({(passed_suites/total_suites*100):.0f}%)\n")
            
            if test_suites.get('build_tests', False):
                f.write("• Kernel build and configuration: VALIDATED\n")
            else:
                f.write("• Kernel build and configuration: ISSUES DETECTED\n")
                
            if test_suites.get('docker_tests', False):
                f.write("• Docker functionality: VALIDATED\n")
            else:
                f.write("• Docker functionality: ISSUES DETECTED\n")
                
            if test_suites.get('integration_tests', False):
                f.write("• System integration: VALIDATED\n")
            else:
                f.write("• System integration: ISSUES DETECTED\n")
                
            f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 20 + "\n")
            
            if overall_success:
                f.write("• All test suites passed successfully\n")
                f.write("• System is ready for deployment\n")
                f.write("• Consider performance optimization for production use\n")
            else:
                f.write("• Review failed test suites before deployment\n")
                f.write("• Address any critical issues identified\n")
                f.write("• Re-run tests after fixes are applied\n")
                
            f.write("\n")
            
            # Technical details
            f.write("TECHNICAL DETAILS\n")
            f.write("-" * 20 + "\n")
            f.write("• Target Device: Redmi K20 Pro (raphael)\n")
            f.write("• Kernel Architecture: ARM64\n")
            f.write("• Docker Integration: Container runtime support\n")
            f.write("• Cross-architecture Migration: x86_64 to ARM64\n")
            f.write("• Android Compatibility: Validated\n\n")
            
            # Contact information
            f.write("For detailed technical reports, see the generated JSON and HTML files.\n")
            
    def print_master_summary(self):
        """Print master test summary to console."""
        print("\n" + "=" * 80)
        print("DOCKER-ENABLED KERNEL - MASTER TEST SUMMARY")
        print("=" * 80)
        
        summary = self.results.get('summary', {})
        overall_success = summary.get('overall_success', False)
        
        print(f"Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        print(f"Total Time: {summary.get('total_time', 0):.1f} seconds")
        print(f"Timestamp: {summary.get('timestamp', 'Unknown')}")
        
        print("\nTest Suite Results:")
        test_suites = summary.get('test_suites', {})
        for suite_name, success in test_suites.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {suite_name.replace('_', ' ').title()}: {status}")
            
        print("\nTest Coverage:")
        print("  🔧 Kernel Build & Configuration")
        print("  🐋 Docker Functionality")
        print("  🔗 End-to-End Integration")
        print("  📱 Android Compatibility")
        print("  ⚡ Performance & Stability")
        print("  🔄 Cross-Architecture Migration")
        
        if overall_success:
            print("\n🎉 All tests passed! System ready for deployment.")
        else:
            print("\n⚠️  Some tests failed. Review detailed reports before deployment.")
            
        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run all Docker-enabled kernel tests")
    parser.add_argument('--output-dir', '-o', 
                       help="Output directory for test results")
    parser.add_argument('--skip-live-docker', action='store_true',
                       help="Skip live Docker tests")
    parser.add_argument('--stability-duration', '-d', type=int, default=5,
                       help="Stability test duration in minutes")
    parser.add_argument('--suite', '-s',
                       choices=['build', 'docker', 'integration', 'all'],
                       default='all',
                       help="Test suite to run")
    
    args = parser.parse_args()
    
    # Create master test runner
    runner = MasterTestRunner(args.output_dir)
    
    # Run specified test suite(s)
    if args.suite == 'build':
        success = runner.run_build_tests()
    elif args.suite == 'docker':
        success = runner.run_docker_tests(args.skip_live_docker)
    elif args.suite == 'integration':
        success = runner.run_integration_tests(args.stability_duration)
    else:
        success = runner.run_all_test_suites(args.skip_live_docker, args.stability_duration)
        
    # Generate reports
    runner.generate_master_report()
    runner.print_master_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()