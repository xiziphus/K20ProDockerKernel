#!/usr/bin/env python3
"""
Kernel configuration validation functions for Docker requirements.
Validates that kernel configurations meet Docker runtime requirements.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from .kernel_config import KernelConfigParser, DockerRequirements, CgroupConfig


class ValidationLevel(Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a configuration validation check."""
    level: ValidationLevel
    option: str
    message: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None


class KernelConfigValidator:
    """Validates kernel configuration against Docker requirements."""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        
    def validate_config(self, config_parser: KernelConfigParser) -> List[ValidationResult]:
        """
        Validate kernel configuration against Docker requirements.
        
        Args:
            config_parser: Parsed kernel configuration
            
        Returns:
            List of validation results
        """
        self.results = []
        
        # Validate required options
        self._validate_required_options(config_parser)
        
        # Validate recommended options
        self._validate_recommended_options(config_parser)
        
        # Validate namespace support
        self._validate_namespace_support(config_parser)
        
        # Validate cgroup support
        self._validate_cgroup_support(config_parser)
        
        # Validate networking support
        self._validate_networking_support(config_parser)
        
        # Validate storage support
        self._validate_storage_support(config_parser)
        
        # Validate security features
        self._validate_security_features(config_parser)
        
        return self.results
        
    def _validate_required_options(self, config_parser: KernelConfigParser) -> None:
        """Validate required Docker kernel options."""
        for option, expected_value in DockerRequirements.REQUIRED_OPTIONS.items():
            actual_value = config_parser.get_option(option)
            
            if actual_value != expected_value:
                self.results.append(ValidationResult(
                    level=ValidationLevel.ERROR,
                    option=option,
                    message=f"Required Docker option missing or incorrect",
                    expected_value=expected_value,
                    actual_value=actual_value or "not set"
                ))
                
    def _validate_recommended_options(self, config_parser: KernelConfigParser) -> None:
        """Validate recommended Docker kernel options."""
        for option, expected_value in DockerRequirements.RECOMMENDED_OPTIONS.items():
            actual_value = config_parser.get_option(option)
            
            if actual_value != expected_value:
                self.results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    option=option,
                    message=f"Recommended Docker option missing or incorrect",
                    expected_value=expected_value,
                    actual_value=actual_value or "not set"
                ))
                
    def _validate_namespace_support(self, config_parser: KernelConfigParser) -> None:
        """Validate namespace support for containers."""
        namespace_options = [
            'CONFIG_NAMESPACES',
            'CONFIG_UTS_NS',
            'CONFIG_IPC_NS', 
            'CONFIG_PID_NS',
            'CONFIG_NET_NS',
            'CONFIG_USER_NS'
        ]
        
        missing_namespaces = []
        for option in namespace_options:
            if not config_parser.is_enabled(option):
                missing_namespaces.append(option)
                
        if missing_namespaces:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="NAMESPACE_SUPPORT",
                message=f"Missing namespace support: {', '.join(missing_namespaces)}"
            ))
            
    def _validate_cgroup_support(self, config_parser: KernelConfigParser) -> None:
        """Validate cgroup support for resource management."""
        essential_cgroups = [
            'CONFIG_CGROUPS',
            'CONFIG_CGROUP_CPUACCT',
            'CONFIG_CGROUP_DEVICE',
            'CONFIG_CGROUP_FREEZER',
            'CONFIG_CGROUP_SCHED',
            'CONFIG_CPUSETS',
            'CONFIG_MEMCG'
        ]
        
        missing_cgroups = []
        for option in essential_cgroups:
            if not config_parser.is_enabled(option):
                missing_cgroups.append(option)
                
        if missing_cgroups:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="CGROUP_SUPPORT",
                message=f"Missing cgroup support: {', '.join(missing_cgroups)}"
            ))
            
        # Check for cpuset prefix support (required for Docker)
        if config_parser.is_enabled('CONFIG_CPUSETS'):
            self.results.append(ValidationResult(
                level=ValidationLevel.INFO,
                option="CONFIG_CPUSETS",
                message="Cpuset support enabled - ensure cpuset prefix is restored in kernel/cgroup/cpuset.c"
            ))
            
    def _validate_networking_support(self, config_parser: KernelConfigParser) -> None:
        """Validate networking support for containers."""
        networking_options = [
            'CONFIG_NETFILTER',
            'CONFIG_BRIDGE_NETFILTER',
            'CONFIG_IP_NF_FILTER',
            'CONFIG_IP_NF_TARGET_MASQUERADE',
            'CONFIG_BRIDGE',
            'CONFIG_VETH'
        ]
        
        missing_networking = []
        for option in networking_options:
            if not config_parser.is_enabled(option):
                missing_networking.append(option)
                
        if missing_networking:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="NETWORKING_SUPPORT",
                message=f"Missing networking support: {', '.join(missing_networking)}"
            ))
            
    def _validate_storage_support(self, config_parser: KernelConfigParser) -> None:
        """Validate storage support for containers."""
        storage_options = [
            'CONFIG_BLK_DEV_DM',
            'CONFIG_DM_THIN_PROVISIONING',
            'CONFIG_OVERLAY_FS'
        ]
        
        missing_storage = []
        for option in storage_options:
            if not config_parser.is_enabled(option):
                missing_storage.append(option)
                
        if missing_storage:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="STORAGE_SUPPORT",
                message=f"Missing storage support: {', '.join(missing_storage)}"
            ))
            
    def _validate_security_features(self, config_parser: KernelConfigParser) -> None:
        """Validate security features for containers."""
        security_options = [
            'CONFIG_SECCOMP',
            'CONFIG_CHECKPOINT_RESTORE'
        ]
        
        for option in security_options:
            if not config_parser.is_enabled(option):
                self.results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    option=option,
                    message=f"Security feature not enabled: {option}"
                ))
                
    def get_errors(self) -> List[ValidationResult]:
        """Get validation errors."""
        return [r for r in self.results if r.level == ValidationLevel.ERROR]
        
    def get_warnings(self) -> List[ValidationResult]:
        """Get validation warnings."""
        return [r for r in self.results if r.level == ValidationLevel.WARNING]
        
    def get_info(self) -> List[ValidationResult]:
        """Get validation info messages."""
        return [r for r in self.results if r.level == ValidationLevel.INFO]
        
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.get_errors()) > 0
        
    def generate_report(self) -> str:
        """Generate a human-readable validation report."""
        report_lines = []
        
        errors = self.get_errors()
        warnings = self.get_warnings()
        info = self.get_info()
        
        report_lines.append("=== Kernel Configuration Validation Report ===\n")
        
        if errors:
            report_lines.append(f"ERRORS ({len(errors)}):")
            for result in errors:
                report_lines.append(f"  ❌ {result.option}: {result.message}")
                if result.expected_value and result.actual_value:
                    report_lines.append(f"     Expected: {result.expected_value}, Got: {result.actual_value}")
            report_lines.append("")
            
        if warnings:
            report_lines.append(f"WARNINGS ({len(warnings)}):")
            for result in warnings:
                report_lines.append(f"  ⚠️  {result.option}: {result.message}")
                if result.expected_value and result.actual_value:
                    report_lines.append(f"     Expected: {result.expected_value}, Got: {result.actual_value}")
            report_lines.append("")
            
        if info:
            report_lines.append(f"INFO ({len(info)}):")
            for result in info:
                report_lines.append(f"  ℹ️  {result.option}: {result.message}")
            report_lines.append("")
            
        # Summary
        if not errors and not warnings:
            report_lines.append("✅ All Docker requirements satisfied!")
        elif not errors:
            report_lines.append("✅ All critical requirements satisfied (warnings present)")
        else:
            report_lines.append("❌ Critical requirements missing - kernel will not support Docker")
            
        return "\n".join(report_lines)


class CgroupValidator:
    """Validates cgroup configuration for Docker requirements."""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        
    def validate_cgroup_config(self, cgroup_config: CgroupConfig) -> List[ValidationResult]:
        """
        Validate cgroup configuration against Docker requirements.
        
        Args:
            cgroup_config: Parsed cgroup configuration
            
        Returns:
            List of validation results
        """
        self.results = []
        
        # Check if required controllers are present
        is_valid, missing_controllers = cgroup_config.validate_docker_cgroups()
        
        if not is_valid:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="CGROUP_CONTROLLERS",
                message=f"Missing required cgroup controllers: {', '.join(missing_controllers)}"
            ))
            
        # Validate controller paths and permissions
        self._validate_controller_paths(cgroup_config)
        
        return self.results
        
    def _validate_controller_paths(self, cgroup_config: CgroupConfig) -> None:
        """Validate cgroup controller paths and permissions."""
        if 'Cgroups' not in cgroup_config.cgroup_config:
            self.results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                option="CGROUP_CONFIG",
                message="No cgroup configuration found"
            ))
            return
            
        for cgroup in cgroup_config.cgroup_config['Cgroups']:
            controller = cgroup.get('Controller', 'unknown')
            path = cgroup.get('Path', '')
            
            if not path.startswith('/dev/'):
                self.results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    option=f"CGROUP_{controller.upper()}_PATH",
                    message=f"Controller {controller} path should be under /dev/: {path}"
                ))
                
    def generate_report(self) -> str:
        """Generate a human-readable cgroup validation report."""
        report_lines = []
        
        errors = [r for r in self.results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in self.results if r.level == ValidationLevel.WARNING]
        
        report_lines.append("=== Cgroup Configuration Validation Report ===\n")
        
        if errors:
            report_lines.append(f"ERRORS ({len(errors)}):")
            for result in errors:
                report_lines.append(f"  ❌ {result.option}: {result.message}")
            report_lines.append("")
            
        if warnings:
            report_lines.append(f"WARNINGS ({len(warnings)}):")
            for result in warnings:
                report_lines.append(f"  ⚠️  {result.option}: {result.message}")
            report_lines.append("")
            
        if not errors and not warnings:
            report_lines.append("✅ Cgroup configuration is valid for Docker!")
        elif not errors:
            report_lines.append("✅ Cgroup configuration is functional (warnings present)")
        else:
            report_lines.append("❌ Cgroup configuration has critical issues")
            
        return "\n".join(report_lines)