#!/usr/bin/env python3
"""
Security Test Suite

Main orchestrator for container security validation tests.
Coordinates all security testing components and generates comprehensive reports.
"""

import os
import sys
import json
import argparse
import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from security.container_isolation_tester import ContainerIsolationTester
from security.privilege_escalation_tester import PrivilegeEscalationTester
from security.security_boundary_tester import SecurityBoundaryTester
from security.vulnerability_reporter import VulnerabilityReporter

class SecurityTestSuite:
    """Main security test suite orchestrator."""
    
    def __init__(self, docker_binary: str = "docker", output_dir: str = None):
        """
        Initialize the security test suite.
        
        Args:
            docker_binary: Path to docker binary
            output_dir: Directory for output files
        """
        self.docker_binary = docker_binary
        self.output_dir = Path(output_dir) if output_dir else Path("security_reports")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize test components
        self.isolation_tester = ContainerIsolationTester(docker_binary)
        self.privilege_tester = PrivilegeEscalationTester(docker_binary)
        self.boundary_tester = SecurityBoundaryTester(docker_binary)
        self.reporter = VulnerabilityReporter()
        
        self.test_results = []
    
    def run_all_tests(self, test_categories: List[str] = None) -> Dict:
        """
        Run all security tests or specified categories.
        
        Args:
            test_categories: List of test categories to run
                           ['isolation', 'privilege', 'boundary']
                           If None, runs all tests
        
        Returns:
            Dict containing comprehensive test results
        """
        print("=== Docker Container Security Validation Suite ===")
        print(f"Output directory: {self.output_dir}")
        print(f"Docker binary: {self.docker_binary}")
        print()
        
        if test_categories is None:
            test_categories = ['isolation', 'privilege', 'boundary']
        
        all_results = {
            'suite_info': {
                'name': 'Docker Container Security Validation',
                'version': '1.0.0',
                'timestamp': datetime.datetime.now().isoformat(),
                'categories_tested': test_categories
            },
            'test_results': [],
            'summary': {
                'total_tests': 0,
                'total_passed': 0,
                'total_failed': 0,
                'total_errors': 0,
                'categories': {}
            }
        }
        
        # Run container isolation tests
        if 'isolation' in test_categories:
            print("Running container isolation tests...")
            isolation_results = self.isolation_tester.run_all_tests()
            all_results['test_results'].extend(isolation_results['tests'])
            all_results['summary']['categories']['isolation'] = {
                'total': isolation_results['total_tests'],
                'passed': isolation_results['passed'],
                'failed': isolation_results['failed']
            }
            self._print_category_summary('Container Isolation', isolation_results)
        
        # Run privilege escalation tests
        if 'privilege' in test_categories:
            print("\nRunning privilege escalation prevention tests...")
            privilege_results = self.privilege_tester.run_all_tests()
            all_results['test_results'].extend(privilege_results['tests'])
            all_results['summary']['categories']['privilege'] = {
                'total': privilege_results['total_tests'],
                'passed': privilege_results['passed'],
                'failed': privilege_results['failed']
            }
            self._print_category_summary('Privilege Escalation Prevention', privilege_results)
        
        # Run security boundary tests
        if 'boundary' in test_categories:
            print("\nRunning security boundary tests...")
            boundary_results = self.boundary_tester.run_all_tests()
            all_results['test_results'].extend(boundary_results['tests'])
            all_results['summary']['categories']['boundary'] = {
                'total': boundary_results['total_tests'],
                'passed': boundary_results['passed'],
                'failed': boundary_results['failed']
            }
            self._print_category_summary('Security Boundaries', boundary_results)
        
        # Calculate overall summary
        all_results['summary']['total_tests'] = len(all_results['test_results'])
        all_results['summary']['total_passed'] = len([t for t in all_results['test_results'] 
                                                     if t['status'] == 'PASS'])
        all_results['summary']['total_failed'] = len([t for t in all_results['test_results'] 
                                                     if t['status'] == 'FAIL'])
        all_results['summary']['total_errors'] = len([t for t in all_results['test_results'] 
                                                     if t['status'] == 'ERROR'])
        
        self.test_results = all_results['test_results']
        
        return all_results
    
    def generate_security_report(self, test_results: Dict = None, 
                               export_formats: List[str] = None) -> Dict:
        """
        Generate comprehensive security vulnerability report.
        
        Args:
            test_results: Test results dict (uses last run if None)
            export_formats: List of export formats ['json', 'html', 'markdown', 'csv']
        
        Returns:
            Dict containing report info and file paths
        """
        if test_results is None:
            if not self.test_results:
                raise ValueError("No test results available. Run tests first.")
            test_data = self.test_results
        else:
            test_data = test_results.get('test_results', [])
        
        if export_formats is None:
            export_formats = ['json', 'markdown']
        
        print("\nGenerating security vulnerability report...")
        
        # Generate the report
        security_report = self.reporter.generate_report(test_data)
        
        # Export in requested formats
        report_files = {}
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for format_type in export_formats:
            filename = f"security_report_{timestamp}.{format_type}"
            filepath = self.output_dir / filename
            
            try:
                self.reporter.export_report(security_report, format_type, str(filepath))
                report_files[format_type] = str(filepath)
                print(f"  ✓ {format_type.upper()} report: {filepath}")
            except Exception as e:
                print(f"  ✗ Failed to export {format_type.upper()} report: {e}")
        
        # Print report summary
        print(f"\n=== Security Report Summary ===")
        print(f"Report ID: {security_report.report_id}")
        print(f"Risk Score: {security_report.risk_score:.1f}/100")
        print(f"Total Findings: {len(security_report.findings)}")
        
        # Print findings by severity
        severity_counts = {}
        for finding in security_report.findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                print(f"  {severity}: {count}")
        
        # Print compliance status
        print(f"\n=== Compliance Status ===")
        for framework, status in security_report.compliance_status.items():
            print(f"  {status['name']}: {status['status']} ({status['score']}%)")
        
        # Print top recommendations
        print(f"\n=== Top Recommendations ===")
        for i, rec in enumerate(security_report.recommendations[:3], 1):
            print(f"  {i}. {rec}")
        
        return {
            'report': security_report,
            'files': report_files,
            'summary': {
                'risk_score': security_report.risk_score,
                'total_findings': len(security_report.findings),
                'severity_counts': severity_counts,
                'compliance_status': security_report.compliance_status
            }
        }
    
    def run_quick_scan(self) -> Dict:
        """
        Run a quick security scan with essential tests only.
        
        Returns:
            Dict containing quick scan results
        """
        print("=== Quick Security Scan ===")
        
        # Run subset of critical tests
        quick_tests = []
        
        # Critical isolation tests
        isolation_results = self.isolation_tester.run_all_tests()
        critical_isolation = [t for t in isolation_results['tests'] 
                            if t['name'] in ['PID Namespace Isolation', 
                                           'Network Namespace Isolation',
                                           'Filesystem Isolation']]
        quick_tests.extend(critical_isolation)
        
        # Critical privilege tests
        privilege_results = self.privilege_tester.run_all_tests()
        critical_privilege = [t for t in privilege_results['tests']
                            if t['name'] in ['Capability Drops',
                                           'User Namespace Restrictions',
                                           'Container Escape Prevention']]
        quick_tests.extend(critical_privilege)
        
        # Critical boundary tests
        boundary_results = self.boundary_tester.run_all_tests()
        critical_boundary = [t for t in boundary_results['tests']
                           if t['name'] in ['Namespace Boundaries',
                                          'Cgroup Boundaries',
                                          'Filesystem Boundaries']]
        quick_tests.extend(critical_boundary)
        
        # Calculate summary
        total_tests = len(quick_tests)
        passed = len([t for t in quick_tests if t['status'] == 'PASS'])
        failed = len([t for t in quick_tests if t['status'] == 'FAIL'])
        errors = len([t for t in quick_tests if t['status'] == 'ERROR'])
        
        quick_results = {
            'scan_type': 'quick',
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'success_rate': (passed / total_tests * 100) if total_tests > 0 else 0,
            'tests': quick_tests
        }
        
        print(f"Quick scan completed: {passed}/{total_tests} tests passed")
        
        if failed > 0:
            print(f"⚠️  {failed} critical security issues found!")
            print("Run full security scan for detailed analysis.")
        else:
            print("✅ No critical security issues detected in quick scan.")
        
        return quick_results
    
    def validate_docker_environment(self) -> Dict:
        """
        Validate Docker environment for security testing.
        
        Returns:
            Dict containing validation results
        """
        print("Validating Docker environment...")
        
        validation_results = {
            'docker_available': False,
            'docker_version': None,
            'docker_daemon_running': False,
            'test_image_available': False,
            'permissions_ok': False,
            'issues': []
        }
        
        # Check Docker binary
        try:
            import subprocess
            result = subprocess.run([self.docker_binary, '--version'], 
                                  capture_output=True, text=True, check=True)
            validation_results['docker_available'] = True
            validation_results['docker_version'] = result.stdout.strip()
            print(f"  ✓ Docker binary: {validation_results['docker_version']}")
        except Exception as e:
            validation_results['issues'].append(f"Docker binary not found: {e}")
            print(f"  ✗ Docker binary not found: {e}")
            return validation_results
        
        # Check Docker daemon
        try:
            result = subprocess.run([self.docker_binary, 'info'], 
                                  capture_output=True, text=True, check=True)
            validation_results['docker_daemon_running'] = True
            print("  ✓ Docker daemon is running")
        except Exception as e:
            validation_results['issues'].append(f"Docker daemon not running: {e}")
            print(f"  ✗ Docker daemon not running: {e}")
            return validation_results
        
        # Check test image availability
        try:
            result = subprocess.run([self.docker_binary, 'images', 'alpine', '-q'], 
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                validation_results['test_image_available'] = True
                print("  ✓ Test image (alpine) available")
            else:
                print("  ⚠️  Test image (alpine) not found, will pull during tests")
                # Try to pull the image
                try:
                    subprocess.run([self.docker_binary, 'pull', 'alpine'], 
                                 capture_output=True, text=True, check=True)
                    validation_results['test_image_available'] = True
                    print("  ✓ Test image (alpine) pulled successfully")
                except Exception as e:
                    validation_results['issues'].append(f"Cannot pull test image: {e}")
                    print(f"  ✗ Cannot pull test image: {e}")
        except Exception as e:
            validation_results['issues'].append(f"Cannot check test image: {e}")
            print(f"  ✗ Cannot check test image: {e}")
        
        # Check permissions
        try:
            result = subprocess.run([self.docker_binary, 'run', '--rm', 'alpine', 'echo', 'test'], 
                                  capture_output=True, text=True, check=True)
            validation_results['permissions_ok'] = True
            print("  ✓ Docker permissions OK")
        except Exception as e:
            validation_results['issues'].append(f"Docker permission issues: {e}")
            print(f"  ✗ Docker permission issues: {e}")
        
        # Overall validation status
        all_checks_passed = (validation_results['docker_available'] and 
                           validation_results['docker_daemon_running'] and
                           validation_results['test_image_available'] and
                           validation_results['permissions_ok'])
        
        if all_checks_passed:
            print("✅ Docker environment validation passed")
        else:
            print("❌ Docker environment validation failed")
            print("Issues found:")
            for issue in validation_results['issues']:
                print(f"  - {issue}")
        
        return validation_results
    
    def _print_category_summary(self, category_name: str, results: Dict):
        """Print summary for a test category."""
        total = results['total_tests']
        passed = results['passed']
        failed = results['failed']
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"  {category_name}: {passed}/{total} passed ({success_rate:.1f}%)")
        
        if failed > 0:
            print(f"    ⚠️  {failed} tests failed")
            # Show failed test names
            failed_tests = [t['name'] for t in results['tests'] if t['status'] == 'FAIL']
            for test_name in failed_tests[:3]:  # Show first 3 failed tests
                print(f"      - {test_name}")
            if len(failed_tests) > 3:
                print(f"      ... and {len(failed_tests) - 3} more")


def main():
    """Main entry point for security test suite."""
    parser = argparse.ArgumentParser(description='Docker Container Security Validation Suite')
    parser.add_argument('--docker-binary', default='docker', 
                       help='Path to Docker binary (default: docker)')
    parser.add_argument('--output-dir', default='security_reports',
                       help='Output directory for reports (default: security_reports)')
    parser.add_argument('--categories', nargs='+', 
                       choices=['isolation', 'privilege', 'boundary'],
                       help='Test categories to run (default: all)')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick security scan with essential tests only')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate Docker environment, do not run tests')
    parser.add_argument('--export-formats', nargs='+',
                       choices=['json', 'html', 'markdown', 'csv'],
                       default=['json', 'markdown'],
                       help='Report export formats (default: json markdown)')
    
    args = parser.parse_args()
    
    # Initialize test suite
    suite = SecurityTestSuite(args.docker_binary, args.output_dir)
    
    # Validate environment
    validation = suite.validate_docker_environment()
    if not all([validation['docker_available'], validation['docker_daemon_running'], 
               validation['permissions_ok']]):
        print("\n❌ Environment validation failed. Cannot proceed with tests.")
        return 1
    
    if args.validate_only:
        print("\n✅ Environment validation completed successfully.")
        return 0
    
    try:
        if args.quick:
            # Run quick scan
            results = suite.run_quick_scan()
            
            # Generate quick report
            if results['failed'] > 0 or results['errors'] > 0:
                print("\nGenerating security report for failed tests...")
                suite.test_results = results['tests']
                suite.generate_security_report(export_formats=args.export_formats)
        else:
            # Run full test suite
            results = suite.run_all_tests(args.categories)
            
            # Print overall summary
            print(f"\n=== Overall Test Summary ===")
            print(f"Total Tests: {results['summary']['total_tests']}")
            print(f"Passed: {results['summary']['total_passed']}")
            print(f"Failed: {results['summary']['total_failed']}")
            print(f"Errors: {results['summary']['total_errors']}")
            success_rate = (results['summary']['total_passed'] / 
                          results['summary']['total_tests'] * 100) if results['summary']['total_tests'] > 0 else 0
            print(f"Success Rate: {success_rate:.1f}%")
            
            # Generate comprehensive security report
            suite.generate_security_report(results, args.export_formats)
        
        print(f"\n✅ Security validation completed. Reports saved to: {suite.output_dir}")
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Security validation interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Security validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())