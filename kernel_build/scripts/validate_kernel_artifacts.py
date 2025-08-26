#!/usr/bin/env python3
"""
Comprehensive Kernel Artifact Validation Script

This script orchestrates all kernel artifact validation tasks including:
- Kernel image format and architecture verification
- Boot process testing
- Docker feature availability testing
- Deployment package creation

Requirements: 6.3, 6.4, 7.1
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import validation modules
from verification.kernel_artifact_validator import KernelArtifactValidator
from verification.boot_process_tester import KernelBootTester
from verification.deployment_image_creator import DeploymentImageCreator

class ComprehensiveKernelValidator:
    """Comprehensive kernel validation orchestrator"""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.logger = self._setup_logging()
        
        # Initialize validators
        self.artifact_validator = KernelArtifactValidator(str(self.workspace_root))
        self.boot_tester = KernelBootTester(str(self.workspace_root))
        self.deployment_creator = DeploymentImageCreator(str(self.workspace_root))
        
        # Validation phases
        self.validation_phases = [
            "artifact_validation",
            "boot_testing", 
            "deployment_creation"
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for comprehensive validator"""
        logger = logging.getLogger("comprehensive_kernel_validator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_dir = self.workspace_root / "kernel_build" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"comprehensive_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def run_artifact_validation(self, search_paths: List[str] = None) -> Dict:
        """Run kernel artifact validation"""
        self.logger.info("🔍 Phase 1: Kernel Artifact Validation")
        self.logger.info("=" * 50)
        
        try:
            result = self.artifact_validator.run_validation(search_paths)
            
            validation_summary = {
                "phase": "artifact_validation",
                "success": result.success,
                "deployment_ready": result.deployment_ready,
                "artifacts_count": len(result.artifacts),
                "errors_count": len(result.overall_errors),
                "warnings_count": len(result.overall_warnings),
                "report_file": result.report_file,
                "details": {
                    "artifacts": [
                        {
                            "path": artifact.path,
                            "valid": artifact.is_valid,
                            "size": artifact.size,
                            "architecture": artifact.architecture
                        } for artifact in result.artifacts
                    ],
                    "errors": result.overall_errors,
                    "warnings": result.overall_warnings
                }
            }
            
            if result.success:
                self.logger.info("✅ Artifact validation passed")
            else:
                self.logger.error("❌ Artifact validation failed")
                for error in result.overall_errors:
                    self.logger.error(f"  - {error}")
            
            return validation_summary
            
        except Exception as e:
            self.logger.error(f"Artifact validation failed with exception: {e}")
            return {
                "phase": "artifact_validation",
                "success": False,
                "error": str(e)
            }
    
    def run_boot_testing(self) -> Dict:
        """Run kernel boot process testing"""
        self.logger.info("🔍 Phase 2: Boot Process Testing")
        self.logger.info("=" * 50)
        
        try:
            results = self.boot_tester.run_all_tests()
            report_file = self.boot_tester.generate_test_report(results)
            
            # Analyze results
            passed_tests = [r for r in results if r.success]
            failed_tests = [r for r in results if not r.success]
            
            # Check critical tests
            critical_tests = ["device_connection", "kernel_version", "docker_features"]
            critical_passed = [r for r in results if r.test_name in critical_tests and r.success]
            
            boot_summary = {
                "phase": "boot_testing",
                "success": len(critical_passed) == len(critical_tests),
                "total_tests": len(results),
                "passed_tests": len(passed_tests),
                "failed_tests": len(failed_tests),
                "critical_tests_passed": len(critical_passed),
                "critical_tests_total": len(critical_tests),
                "report_file": report_file,
                "details": {
                    "test_results": [
                        {
                            "name": result.test_name,
                            "success": result.success,
                            "message": result.message,
                            "duration": result.duration
                        } for result in results
                    ],
                    "failed_tests": [r.test_name for r in failed_tests],
                    "critical_failures": [t for t in critical_tests if not any(r.test_name == t and r.success for r in results)]
                }
            }
            
            if boot_summary["success"]:
                self.logger.info("✅ Boot testing passed")
            else:
                self.logger.error("❌ Boot testing failed")
                for failure in boot_summary["details"]["critical_failures"]:
                    self.logger.error(f"  - Critical test failed: {failure}")
            
            return boot_summary
            
        except Exception as e:
            self.logger.error(f"Boot testing failed with exception: {e}")
            return {
                "phase": "boot_testing",
                "success": False,
                "error": str(e)
            }
    
    def run_deployment_creation(self, search_paths: List[str] = None) -> Dict:
        """Run deployment package creation"""
        self.logger.info("🔍 Phase 3: Deployment Package Creation")
        self.logger.info("=" * 50)
        
        try:
            package = self.deployment_creator.run_deployment_creation(search_paths)
            
            if package:
                deployment_summary = {
                    "phase": "deployment_creation",
                    "success": True,
                    "package_path": package.package_path,
                    "package_size": package.size,
                    "package_checksum": package.checksum,
                    "kernel_image": package.kernel_image,
                    "device_tree": package.device_tree,
                    "details": {
                        "metadata": package.metadata
                    }
                }
                
                self.logger.info("✅ Deployment package created successfully")
                self.logger.info(f"Package: {package.package_path}")
                
            else:
                deployment_summary = {
                    "phase": "deployment_creation",
                    "success": False,
                    "error": "Failed to create deployment package"
                }
                
                self.logger.error("❌ Deployment package creation failed")
            
            return deployment_summary
            
        except Exception as e:
            self.logger.error(f"Deployment creation failed with exception: {e}")
            return {
                "phase": "deployment_creation",
                "success": False,
                "error": str(e)
            }
    
    def generate_comprehensive_report(self, results: Dict) -> str:
        """Generate comprehensive validation report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COMPREHENSIVE KERNEL VALIDATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Overall summary
        all_phases_success = all(results.get(phase, {}).get("success", False) for phase in self.validation_phases)
        
        report_lines.append("📋 OVERALL SUMMARY")
        report_lines.append(f"   Validation Status: {'✅ PASSED' if all_phases_success else '❌ FAILED'}")
        report_lines.append(f"   Phases Completed: {len([p for p in self.validation_phases if p in results])}/{len(self.validation_phases)}")
        report_lines.append("")
        
        # Phase details
        for phase in self.validation_phases:
            if phase not in results:
                continue
            
            phase_result = results[phase]
            phase_name = phase.replace("_", " ").title()
            status = "✅ PASSED" if phase_result.get("success", False) else "❌ FAILED"
            
            report_lines.append(f"🔍 {phase_name.upper()}")
            report_lines.append(f"   Status: {status}")
            
            if phase == "artifact_validation":
                report_lines.append(f"   Artifacts Found: {phase_result.get('artifacts_count', 0)}")
                report_lines.append(f"   Deployment Ready: {'Yes' if phase_result.get('deployment_ready', False) else 'No'}")
                report_lines.append(f"   Errors: {phase_result.get('errors_count', 0)}")
                report_lines.append(f"   Warnings: {phase_result.get('warnings_count', 0)}")
                
                if phase_result.get("report_file"):
                    report_lines.append(f"   Report: {phase_result['report_file']}")
            
            elif phase == "boot_testing":
                report_lines.append(f"   Tests: {phase_result.get('passed_tests', 0)}/{phase_result.get('total_tests', 0)} passed")
                report_lines.append(f"   Critical Tests: {phase_result.get('critical_tests_passed', 0)}/{phase_result.get('critical_tests_total', 0)} passed")
                
                if phase_result.get("report_file"):
                    report_lines.append(f"   Report: {phase_result['report_file']}")
                
                failed_tests = phase_result.get("details", {}).get("failed_tests", [])
                if failed_tests:
                    report_lines.append(f"   Failed Tests: {', '.join(failed_tests)}")
            
            elif phase == "deployment_creation":
                if phase_result.get("success"):
                    report_lines.append(f"   Package: {Path(phase_result.get('package_path', '')).name}")
                    report_lines.append(f"   Size: {phase_result.get('package_size', 0):,} bytes")
                    report_lines.append(f"   Checksum: {phase_result.get('package_checksum', '')[:16]}...")
            
            if "error" in phase_result:
                report_lines.append(f"   Error: {phase_result['error']}")
            
            report_lines.append("")
        
        # Recommendations
        report_lines.append("💡 RECOMMENDATIONS")
        
        if all_phases_success:
            report_lines.append("   ✅ All validation phases passed successfully")
            report_lines.append("   🚀 Kernel is ready for deployment")
            report_lines.append("   📱 You can proceed with flashing the kernel to your device")
            report_lines.append("   ⚠️  Always backup your current kernel before flashing")
        else:
            report_lines.append("   ❌ Validation failed - kernel is not ready for deployment")
            
            # Specific recommendations based on failures
            if not results.get("artifact_validation", {}).get("success", False):
                report_lines.append("   🔧 Fix artifact validation issues first")
                report_lines.append("   📋 Ensure kernel compilation completed successfully")
            
            if not results.get("boot_testing", {}).get("success", False):
                report_lines.append("   🔧 Address boot testing failures")
                report_lines.append("   📱 Check device connection and kernel compatibility")
            
            if not results.get("deployment_creation", {}).get("success", False):
                report_lines.append("   🔧 Fix deployment package creation issues")
                report_lines.append("   📦 Ensure all required artifacts are available")
        
        report_lines.append("")
        
        # Save report
        report_content = "\n".join(report_lines)
        
        try:
            report_dir = self.workspace_root / "kernel_build" / "logs"
            report_dir.mkdir(parents=True, exist_ok=True)
            
            report_file = report_dir / f"comprehensive_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report_content)
            
            return str(report_file)
        except Exception as e:
            self.logger.error(f"Could not save comprehensive report: {e}")
            return ""
    
    def run_comprehensive_validation(self, search_paths: List[str] = None, 
                                   skip_boot_test: bool = False,
                                   skip_deployment: bool = False) -> Dict:
        """Run comprehensive kernel validation"""
        self.logger.info("🚀 Starting Comprehensive Kernel Validation")
        self.logger.info("=" * 60)
        
        results = {}
        
        # Phase 1: Artifact Validation
        results["artifact_validation"] = self.run_artifact_validation(search_paths)
        
        # Only proceed with boot testing if artifacts are valid
        if not skip_boot_test and results["artifact_validation"].get("success", False):
            # Phase 2: Boot Testing
            results["boot_testing"] = self.run_boot_testing()
        elif skip_boot_test:
            self.logger.info("⏭️  Skipping boot testing (--skip-boot-test)")
        else:
            self.logger.warning("⏭️  Skipping boot testing due to artifact validation failure")
        
        # Only proceed with deployment if artifacts are deployment-ready
        if not skip_deployment and results["artifact_validation"].get("deployment_ready", False):
            # Phase 3: Deployment Creation
            results["deployment_creation"] = self.run_deployment_creation(search_paths)
        elif skip_deployment:
            self.logger.info("⏭️  Skipping deployment creation (--skip-deployment)")
        else:
            self.logger.warning("⏭️  Skipping deployment creation - artifacts not deployment-ready")
        
        # Generate comprehensive report
        report_file = self.generate_comprehensive_report(results)
        results["comprehensive_report"] = report_file
        
        # Print summary
        all_phases_success = all(results.get(phase, {}).get("success", False) for phase in self.validation_phases if phase in results)
        
        print(f"\n{'='*60}")
        print("COMPREHENSIVE VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Overall Status: {'✅ PASSED' if all_phases_success else '❌ FAILED'}")
        print(f"Phases Completed: {len([p for p in self.validation_phases if p in results])}/{len(self.validation_phases)}")
        
        for phase in self.validation_phases:
            if phase in results:
                phase_name = phase.replace("_", " ").title()
                status = "✅ PASS" if results[phase].get("success", False) else "❌ FAIL"
                print(f"{phase_name}: {status}")
        
        if report_file:
            print(f"Comprehensive Report: {report_file}")
        
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Comprehensive kernel artifact validation"
    )
    parser.add_argument(
        '--search-paths',
        nargs='+',
        help='Paths to search for kernel artifacts'
    )
    parser.add_argument(
        '--skip-boot-test',
        action='store_true',
        help='Skip boot process testing (useful when device not connected)'
    )
    parser.add_argument(
        '--skip-deployment',
        action='store_true',
        help='Skip deployment package creation'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = ComprehensiveKernelValidator()
    results = validator.run_comprehensive_validation(
        search_paths=args.search_paths,
        skip_boot_test=args.skip_boot_test,
        skip_deployment=args.skip_deployment
    )
    
    # Determine exit code
    all_phases_success = all(
        results.get(phase, {}).get("success", False) 
        for phase in validator.validation_phases 
        if phase in results
    )
    
    sys.exit(0 if all_phases_success else 1)


if __name__ == '__main__':
    main()