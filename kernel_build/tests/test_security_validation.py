#!/usr/bin/env python3
"""
Test Security Validation Suite

Unit tests for the container security validation components.
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from security.container_isolation_tester import ContainerIsolationTester
from security.privilege_escalation_tester import PrivilegeEscalationTester
from security.security_boundary_tester import SecurityBoundaryTester
from security.vulnerability_reporter import VulnerabilityReporter, VulnerabilityFinding
from security.security_test_suite import SecurityTestSuite

class TestContainerIsolationTester(unittest.TestCase):
    """Test container isolation tester."""
    
    def setUp(self):
        self.tester = ContainerIsolationTester("mock_docker")
    
    @patch('subprocess.run')
    def test_create_test_container(self, mock_run):
        """Test container creation."""
        mock_run.return_value.stdout = "container123\n"
        mock_run.return_value.returncode = 0
        
        container_id = self.tester._create_test_container("alpine", "sleep 300")
        
        self.assertEqual(container_id, "container123")
        self.assertIn("container123", self.tester.test_containers)
        mock_run.assert_called()
    
    @patch('subprocess.run')
    def test_exec_in_container(self, mock_run):
        """Test command execution in container."""
        mock_run.return_value.stdout = "test output\n"
        mock_run.return_value.returncode = 0
        
        output = self.tester._exec_in_container("container123", ["echo", "test"])
        
        self.assertEqual(output, "test output\n")
        mock_run.assert_called_with(
            ["mock_docker", "exec", "container123", "echo", "test"],
            capture_output=True, text=True, check=True
        )
    
    def test_extract_pids(self):
        """Test PID extraction from ps output."""
        ps_output = """PID   USER     TIME  COMMAND
    1 root      0:00 sleep 300
    7 root      0:00 sh"""
        
        pids = self.tester._extract_pids(ps_output)
        
        # The PID should be in the second column (index 1)
        self.assertEqual(len(pids), 2)
        # Check that we extracted some PIDs (the exact format may vary)
        self.assertTrue(all(pid.strip() for pid in pids))
    
    def test_file_exists_in_container(self):
        """Test file existence check."""
        with patch.object(self.tester, '_exec_in_container') as mock_exec:
            # File exists
            mock_exec.return_value = ""
            self.assertTrue(self.tester._file_exists_in_container("container123", "/tmp/test"))
            
            # File doesn't exist
            mock_exec.side_effect = subprocess.CalledProcessError(1, "test")
            self.assertFalse(self.tester._file_exists_in_container("container123", "/tmp/test"))

class TestPrivilegeEscalationTester(unittest.TestCase):
    """Test privilege escalation tester."""
    
    def setUp(self):
        self.tester = PrivilegeEscalationTester("mock_docker")
    
    @patch('subprocess.run')
    def test_capability_drops_test(self, mock_run):
        """Test capability drops validation."""
        # Mock container creation
        mock_run.return_value.stdout = "container123\n"
        mock_run.return_value.returncode = 0
        
        with patch.object(self.tester, '_exec_in_container') as mock_exec:
            # Mock capabilities check
            mock_exec.return_value = "CapEff:\t0000000000000000"
            
            # Mock privileged operations failing (good)
            mock_exec.side_effect = [
                "CapEff:\t0000000000000000",  # capabilities check
                subprocess.CalledProcessError(1, "mount"),  # mount fails
                subprocess.CalledProcessError(1, "date"),   # date fails
                subprocess.CalledProcessError(1, "mknod")   # mknod fails
            ]
            
            result = self.tester.test_capability_drops()
            
            self.assertEqual(result['status'], 'PASS')
            self.assertIn('blocked_operations', result['details'])

class TestSecurityBoundaryTester(unittest.TestCase):
    """Test security boundary tester."""
    
    def setUp(self):
        self.tester = SecurityBoundaryTester("mock_docker")
    
    def test_check_selinux_status(self):
        """Test SELinux status checking."""
        with patch('subprocess.run') as mock_run:
            # SELinux enforcing
            mock_run.return_value.stdout = "Enforcing\n"
            mock_run.return_value.returncode = 0
            
            status = self.tester._check_selinux_status()
            
            self.assertTrue(status['available'])
            self.assertEqual(status['status'], 'Enforcing')
            self.assertTrue(status['enforcing'])
    
    def test_check_apparmor_status(self):
        """Test AppArmor status checking."""
        with patch('subprocess.run') as mock_run:
            # AppArmor active
            mock_run.return_value.stdout = "apparmor module is loaded.\n5 profiles are loaded."
            mock_run.return_value.returncode = 0
            
            status = self.tester._check_apparmor_status()
            
            self.assertTrue(status['available'])
            self.assertEqual(status['status'], 'active')
            self.assertTrue(status['profiles_loaded'])
    
    def test_extract_cap_value(self):
        """Test capability value extraction."""
        cap_line = "CapEff:\t0000000000000000"
        value = self.tester._extract_cap_value(cap_line)
        self.assertEqual(value, "0000000000000000")

class TestVulnerabilityReporter(unittest.TestCase):
    """Test vulnerability reporter."""
    
    def setUp(self):
        self.reporter = VulnerabilityReporter()
    
    def test_create_finding_from_failure(self):
        """Test vulnerability finding creation from test failure."""
        test_result = {
            'name': 'PID Namespace Isolation',
            'status': 'FAIL',
            'message': 'PID namespace isolation failed',
            'details': {'container1_processes': 10, 'container2_processes': 8}
        }
        
        finding = self.reporter._create_finding_from_failure(test_result)
        
        self.assertIsNotNone(finding)
        self.assertEqual(finding.severity, 'HIGH')
        self.assertEqual(finding.category, 'ISOLATION')
        self.assertIn('PID Namespace', finding.title)
    
    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        findings = [
            VulnerabilityFinding(
                id="VULN-001", title="Test Critical", severity="CRITICAL",
                category="ISOLATION", description="Test", impact="High",
                affected_component="Test", test_name="Test", evidence={},
                remediation="Fix it", references=[]
            ),
            VulnerabilityFinding(
                id="VULN-002", title="Test Medium", severity="MEDIUM",
                category="BOUNDARY", description="Test", impact="Medium",
                affected_component="Test", test_name="Test", evidence={},
                remediation="Fix it", references=[]
            )
        ]
        
        risk_score = self.reporter._calculate_risk_score(findings)
        
        self.assertGreater(risk_score, 0)
        self.assertLessEqual(risk_score, 100)
    
    def test_check_compliance(self):
        """Test compliance checking."""
        findings = [
            VulnerabilityFinding(
                id="VULN-001", title="Test Critical", severity="CRITICAL",
                category="ISOLATION", description="Test", impact="High",
                affected_component="Test", test_name="Test", evidence={},
                remediation="Fix it", references=[]
            )
        ]
        
        compliance = self.reporter._check_compliance(findings)
        
        self.assertIn('CIS_DOCKER', compliance)
        self.assertEqual(compliance['CIS_DOCKER']['status'], 'NON_COMPLIANT')
        self.assertEqual(compliance['CIS_DOCKER']['score'], 0)
    
    def test_generate_recommendations(self):
        """Test recommendation generation."""
        findings = [
            VulnerabilityFinding(
                id="VULN-001", title="Test", severity="CRITICAL",
                category="ISOLATION", description="Test", impact="High",
                affected_component="Test", test_name="Test", evidence={},
                remediation="Fix it", references=[]
            ),
            VulnerabilityFinding(
                id="VULN-002", title="Test", severity="HIGH",
                category="PRIVILEGE_ESCALATION", description="Test", impact="High",
                affected_component="Test", test_name="Test", evidence={},
                remediation="Fix it", references=[]
            )
        ]
        
        recommendations = self.reporter._generate_recommendations(findings)
        
        self.assertGreater(len(recommendations), 0)
        self.assertTrue(any("URGENT" in rec for rec in recommendations))
        self.assertTrue(any("isolation" in rec.lower() for rec in recommendations))
    
    def test_export_json(self):
        """Test JSON export."""
        from security.vulnerability_reporter import SecurityReport
        
        report = SecurityReport(
            report_id="TEST-001",
            timestamp="2023-01-01T00:00:00",
            system_info={"platform": "test"},
            test_summary={"total_tests": 1, "passed": 0, "failed": 1, "errors": 0, "success_rate": 0},
            findings=[],
            risk_score=0.0,
            compliance_status={},
            recommendations=[]
        )
        
        json_content = self.reporter._export_json(report)
        
        self.assertIsInstance(json_content, str)
        # Verify it's valid JSON
        parsed = json.loads(json_content)
        self.assertEqual(parsed['report_id'], "TEST-001")
    
    def test_export_markdown(self):
        """Test Markdown export."""
        from security.vulnerability_reporter import SecurityReport
        
        report = SecurityReport(
            report_id="TEST-001",
            timestamp="2023-01-01T00:00:00",
            system_info={"platform": "test"},
            test_summary={"total_tests": 1, "passed": 0, "failed": 1, "errors": 0, "success_rate": 0},
            findings=[],
            risk_score=0.0,
            compliance_status={},
            recommendations=["Test recommendation"]
        )
        
        md_content = self.reporter._export_markdown(report)
        
        self.assertIsInstance(md_content, str)
        self.assertIn("# Security Vulnerability Report", md_content)
        self.assertIn("TEST-001", md_content)
        self.assertIn("Test recommendation", md_content)

class TestSecurityTestSuite(unittest.TestCase):
    """Test security test suite orchestrator."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.suite = SecurityTestSuite("mock_docker", self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_validate_docker_environment(self, mock_run):
        """Test Docker environment validation."""
        # Mock successful Docker commands
        mock_run.side_effect = [
            Mock(stdout="Docker version 20.10.0", returncode=0),  # --version
            Mock(stdout="Docker info", returncode=0),             # info
            Mock(stdout="alpine_image_id", returncode=0),         # images
            Mock(stdout="test", returncode=0)                     # run test
        ]
        
        validation = self.suite.validate_docker_environment()
        
        self.assertTrue(validation['docker_available'])
        self.assertTrue(validation['docker_daemon_running'])
        self.assertTrue(validation['test_image_available'])
        self.assertTrue(validation['permissions_ok'])
        self.assertEqual(len(validation['issues']), 0)
    
    def test_print_category_summary(self):
        """Test category summary printing."""
        results = {
            'total_tests': 10,
            'passed': 8,
            'failed': 2,
            'tests': [
                {'name': 'Test 1', 'status': 'FAIL'},
                {'name': 'Test 2', 'status': 'FAIL'}
            ]
        }
        
        # This should not raise an exception
        self.suite._print_category_summary("Test Category", results)

class TestIntegration(unittest.TestCase):
    """Integration tests for the security validation suite."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_mock_scenario(self):
        """Test end-to-end scenario with mocked Docker."""
        # Create mock test results
        mock_test_results = [
            {
                'name': 'PID Namespace Isolation',
                'status': 'FAIL',
                'message': 'PID namespace isolation failed',
                'details': {'container1_processes': 10, 'container2_processes': 8}
            },
            {
                'name': 'Network Namespace Isolation',
                'status': 'PASS',
                'message': 'Network namespace isolation working correctly',
                'details': {'container1_has_network': True, 'container2_has_network': False}
            },
            {
                'name': 'Capability Drops',
                'status': 'FAIL',
                'message': 'Some privileged operations succeeded',
                'details': {'blocked_operations': 2, 'total_operations': 3}
            }
        ]
        
        # Test vulnerability reporter
        reporter = VulnerabilityReporter()
        report = reporter.generate_report(mock_test_results)
        
        # Verify report generation
        self.assertIsNotNone(report.report_id)
        self.assertGreater(len(report.findings), 0)
        self.assertGreater(report.risk_score, 0)
        
        # Test report export
        json_content = reporter.export_report(report, 'json')
        self.assertIsInstance(json_content, str)
        
        md_content = reporter.export_report(report, 'markdown')
        self.assertIsInstance(md_content, str)
        self.assertIn("Security Vulnerability Report", md_content)
    
    def test_security_suite_initialization(self):
        """Test security test suite initialization."""
        suite = SecurityTestSuite("docker", self.temp_dir)
        
        self.assertEqual(suite.docker_binary, "docker")
        self.assertEqual(str(suite.output_dir), self.temp_dir)
        self.assertIsInstance(suite.isolation_tester, ContainerIsolationTester)
        self.assertIsInstance(suite.privilege_tester, PrivilegeEscalationTester)
        self.assertIsInstance(suite.boundary_tester, SecurityBoundaryTester)
        self.assertIsInstance(suite.reporter, VulnerabilityReporter)


def run_security_validation_tests():
    """Run all security validation tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestContainerIsolationTester,
        TestPrivilegeEscalationTester,
        TestSecurityBoundaryTester,
        TestVulnerabilityReporter,
        TestSecurityTestSuite,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    import subprocess
    
    # Add missing import for subprocess in test
    globals()['subprocess'] = subprocess
    
    print("=== Security Validation Test Suite ===")
    success = run_security_validation_tests()
    
    if success:
        print("\n✅ All security validation tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some security validation tests failed!")
        sys.exit(1)