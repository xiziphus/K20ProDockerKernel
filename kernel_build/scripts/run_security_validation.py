#!/usr/bin/env python3
"""
Run Security Validation

Script to execute container security validation tests and generate reports.
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from security.security_test_suite import SecurityTestSuite

def main():
    """Main entry point for security validation script."""
    parser = argparse.ArgumentParser(
        description='Run Docker Container Security Validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full security validation
  python run_security_validation.py

  # Run quick security scan
  python run_security_validation.py --quick

  # Run specific test categories
  python run_security_validation.py --categories isolation privilege

  # Validate Docker environment only
  python run_security_validation.py --validate-only

  # Export reports in multiple formats
  python run_security_validation.py --export-formats json markdown html csv
        """
    )
    
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
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        print("=== Docker Container Security Validation ===")
        print(f"Docker binary: {args.docker_binary}")
        print(f"Output directory: {args.output_dir}")
        print(f"Export formats: {', '.join(args.export_formats)}")
        if args.categories:
            print(f"Test categories: {', '.join(args.categories)}")
        print()
    
    try:
        # Initialize security test suite
        suite = SecurityTestSuite(args.docker_binary, args.output_dir)
        
        # Validate Docker environment
        if args.verbose:
            print("Validating Docker environment...")
        
        validation = suite.validate_docker_environment()
        
        if not all([validation['docker_available'], 
                   validation['docker_daemon_running'], 
                   validation['permissions_ok']]):
            print("❌ Docker environment validation failed!")
            if validation['issues']:
                print("Issues found:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            return 1
        
        if args.validate_only:
            print("✅ Docker environment validation completed successfully.")
            return 0
        
        # Run security tests
        if args.quick:
            if args.verbose:
                print("Running quick security scan...")
            results = suite.run_quick_scan()
            
            # Generate report if issues found
            if results['failed'] > 0 or results['errors'] > 0:
                if args.verbose:
                    print("Generating security report for identified issues...")
                suite.test_results = results['tests']
                report_info = suite.generate_security_report(
                    export_formats=args.export_formats
                )
                
                print(f"\n⚠️  Quick scan found {results['failed']} security issues!")
                print(f"Risk Score: {report_info['summary']['risk_score']:.1f}/100")
                print(f"Reports generated in: {suite.output_dir}")
            else:
                print("\n✅ Quick security scan completed - no critical issues found.")
        else:
            if args.verbose:
                print("Running comprehensive security validation...")
            
            # Run full test suite
            results = suite.run_all_tests(args.categories)
            
            # Generate comprehensive report
            report_info = suite.generate_security_report(
                results, args.export_formats
            )
            
            # Print summary
            print(f"\n=== Security Validation Summary ===")
            print(f"Total Tests: {results['summary']['total_tests']}")
            print(f"Passed: {results['summary']['total_passed']}")
            print(f"Failed: {results['summary']['total_failed']}")
            print(f"Errors: {results['summary']['total_errors']}")
            
            success_rate = (results['summary']['total_passed'] / 
                          results['summary']['total_tests'] * 100) if results['summary']['total_tests'] > 0 else 0
            print(f"Success Rate: {success_rate:.1f}%")
            print(f"Risk Score: {report_info['summary']['risk_score']:.1f}/100")
            
            # Print severity breakdown
            severity_counts = report_info['summary']['severity_counts']
            if severity_counts:
                print(f"\nFindings by Severity:")
                for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
                    count = severity_counts.get(severity, 0)
                    if count > 0:
                        print(f"  {severity}: {count}")
            
            print(f"\nReports generated in: {suite.output_dir}")
            
            # Return appropriate exit code
            if results['summary']['total_failed'] > 0:
                return 2  # Security issues found
            elif results['summary']['total_errors'] > 0:
                return 3  # Test errors occurred
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Security validation interrupted by user.")
        return 130
    except Exception as e:
        print(f"\n❌ Security validation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())