# Container Security Validation Suite

A comprehensive security testing framework for Docker-enabled kernel validation, focusing on container isolation, privilege escalation prevention, and security boundary enforcement.

## Overview

This security validation suite provides automated testing for container security controls required by the Docker-enabled kernel for K20 Pro. It validates that containers are properly isolated and that security boundaries are enforced according to industry best practices.

## Components

### 1. Container Isolation Tester (`container_isolation_tester.py`)

Tests container isolation mechanisms including:
- **PID Namespace Isolation**: Ensures containers cannot see each other's processes
- **Network Namespace Isolation**: Validates network separation between containers
- **IPC Namespace Isolation**: Tests Inter-Process Communication isolation
- **UTS Namespace Isolation**: Verifies hostname and domain name isolation
- **User Namespace Isolation**: Tests user ID mapping and restrictions
- **Mount Namespace Isolation**: Validates filesystem mount isolation
- **Cgroup Isolation**: Tests resource group separation
- **Filesystem Isolation**: Ensures container filesystem boundaries
- **Process Visibility**: Validates that containers cannot see host processes
- **Resource Limits**: Tests that resource constraints are enforced

### 2. Privilege Escalation Tester (`privilege_escalation_tester.py`)

Tests privilege escalation prevention including:
- **Capability Drops**: Ensures dangerous capabilities are removed
- **No New Privileges**: Tests the no_new_privs security flag
- **User Namespace Restrictions**: Validates UID/GID mapping security
- **Setuid Prevention**: Tests setuid binary restrictions
- **Device Access Restrictions**: Validates device node access controls
- **Kernel Module Restrictions**: Tests kernel module loading prevention
- **Proc/Sys Restrictions**: Validates /proc and /sys access controls
- **Privileged Port Restrictions**: Tests port binding restrictions
- **Container Escape Prevention**: Tests common escape technique prevention
- **Read-only Root Filesystem**: Validates filesystem write restrictions

### 3. Security Boundary Tester (`security_boundary_tester.py`)

Tests security boundary enforcement including:
- **SELinux Enforcement**: Tests SELinux policy enforcement for containers
- **AppArmor Enforcement**: Validates AppArmor profile enforcement
- **Seccomp Filtering**: Tests system call filtering
- **Capability Bounding Set**: Validates capability restrictions
- **Namespace Boundaries**: Tests namespace isolation boundaries
- **Cgroup Boundaries**: Validates cgroup resource boundaries
- **Filesystem Boundaries**: Tests filesystem access boundaries
- **Network Boundaries**: Validates network isolation boundaries
- **IPC Boundaries**: Tests IPC isolation boundaries
- **Resource Boundaries**: Validates resource limit enforcement

### 4. Vulnerability Reporter (`vulnerability_reporter.py`)

Generates comprehensive security reports including:
- **Vulnerability Findings**: Detailed security issue identification
- **Risk Assessment**: Calculated risk scores and severity ratings
- **Compliance Checking**: Validation against security frameworks
- **Remediation Recommendations**: Actionable security improvements
- **Multiple Export Formats**: JSON, HTML, Markdown, and CSV reports

### 5. Security Test Suite (`security_test_suite.py`)

Main orchestrator that:
- **Coordinates All Tests**: Runs all security validation components
- **Environment Validation**: Checks Docker environment prerequisites
- **Report Generation**: Creates comprehensive security reports
- **Quick Scan Mode**: Provides rapid security assessment
- **Flexible Configuration**: Supports selective test execution

## Usage

### Basic Usage

```bash
# Run comprehensive security validation
python kernel_build/scripts/run_security_validation.py

# Run quick security scan
python kernel_build/scripts/run_security_validation.py --quick

# Run specific test categories
python kernel_build/scripts/run_security_validation.py --categories isolation privilege

# Validate Docker environment only
python kernel_build/scripts/run_security_validation.py --validate-only
```

### Advanced Usage

```bash
# Export reports in multiple formats
python kernel_build/scripts/run_security_validation.py --export-formats json markdown html csv

# Use custom Docker binary
python kernel_build/scripts/run_security_validation.py --docker-binary /usr/local/bin/docker

# Specify output directory
python kernel_build/scripts/run_security_validation.py --output-dir /path/to/reports

# Enable verbose output
python kernel_build/scripts/run_security_validation.py --verbose
```

### Programmatic Usage

```python
from kernel_build.security.security_test_suite import SecurityTestSuite

# Initialize test suite
suite = SecurityTestSuite()

# Validate environment
validation = suite.validate_docker_environment()
if not validation['docker_available']:
    print("Docker not available")
    exit(1)

# Run all tests
results = suite.run_all_tests()

# Generate security report
report_info = suite.generate_security_report(results)
print(f"Risk Score: {report_info['summary']['risk_score']}")
```

## Test Categories

### Isolation Tests
Focus on container isolation mechanisms and namespace separation:
- Validates that containers cannot access each other's resources
- Tests process, network, filesystem, and IPC isolation
- Ensures proper resource group separation

### Privilege Escalation Tests
Focus on preventing privilege escalation attacks:
- Tests capability dropping and user namespace restrictions
- Validates setuid binary and device access controls
- Ensures containers cannot escape to host privileges

### Security Boundary Tests
Focus on security policy enforcement:
- Tests SELinux, AppArmor, and seccomp enforcement
- Validates capability bounding sets and system call filtering
- Ensures proper security boundary enforcement

## Report Formats

### JSON Report
Machine-readable format containing:
- Complete test results and findings
- Risk scores and compliance status
- Detailed evidence and remediation steps

### Markdown Report
Human-readable format including:
- Executive summary and risk assessment
- Findings organized by severity
- Compliance status and recommendations

### HTML Report
Web-viewable format with:
- Interactive security dashboard
- Detailed finding descriptions
- Visual risk indicators

### CSV Report
Spreadsheet-compatible format for:
- Finding tracking and management
- Risk analysis and reporting
- Integration with security tools

## Security Frameworks

The validation suite checks compliance against:

- **CIS Docker Benchmark**: Industry-standard Docker security guidelines
- **NIST SP 800-190**: Application Container Security Guide
- **PCI DSS**: Payment Card Industry container security requirements
- **SOC 2**: Service Organization Control security standards

## Requirements Mapping

This implementation addresses the following requirements:

- **Requirement 1.2**: Container namespaces and isolation validation
- **Requirement 1.4**: Proper isolation and resource management testing
- **Requirement 7.3**: SELinux policy enforcement for Docker operations

## Prerequisites

- Docker daemon running and accessible
- Python 3.7+ with required dependencies
- Alpine container image (automatically pulled if needed)
- Appropriate permissions to run Docker containers

## Output

The security validation suite generates:

1. **Console Output**: Real-time test progress and summary
2. **Security Reports**: Detailed vulnerability and compliance reports
3. **Test Artifacts**: Individual test results and evidence
4. **Recommendations**: Actionable security improvement guidance

## Integration

This security validation suite integrates with:

- **Kernel Build Process**: Validates security after kernel compilation
- **CI/CD Pipelines**: Automated security testing in build workflows
- **Security Monitoring**: Continuous security validation
- **Compliance Reporting**: Regular security assessment reports

## Troubleshooting

### Common Issues

1. **Docker Not Available**: Ensure Docker is installed and daemon is running
2. **Permission Denied**: Add user to docker group or run with sudo
3. **Image Pull Failures**: Check network connectivity and Docker registry access
4. **Test Timeouts**: Increase timeout values for slow systems

### Debug Mode

Enable verbose output for detailed troubleshooting:
```bash
python kernel_build/scripts/run_security_validation.py --verbose
```

## Contributing

When adding new security tests:

1. Follow the existing test pattern and naming conventions
2. Include comprehensive error handling and cleanup
3. Add appropriate test cases and documentation
4. Map tests to specific security requirements
5. Update vulnerability reporter with new finding types

## Security Considerations

- Tests are designed to be non-destructive and safe to run
- All test containers are automatically cleaned up
- No persistent changes are made to the host system
- Sensitive information is not logged or stored in reports