#!/usr/bin/env python3
"""
Regression Detection System
Detects performance and functionality regressions in the Docker-enabled kernel.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple


class RegressionDetector:
    """System for detecting various types of regressions."""
    
    def __init__(self, baseline_file=None):
        self.baseline_file = baseline_file
        self.regression_thresholds = {
            'performance': 0.15,  # 15% performance degradation
            'memory': 0.20,       # 20% memory increase
            'boot_time': 0.10,    # 10% boot time increase
            'battery': 0.25       # 25% battery drain increase
        }
        
    def detect_system_regressions(self, baseline_metrics: Dict, current_metrics: Dict) -> Dict:
        """Detect system-wide regressions."""
        regressions = {
            'performance_regressions': {},
            'resource_regressions': {},
            'functionality_regressions': {},
            'severity_assessment': 'none'
        }
        
        # Detect performance regressions
        perf_regressions = self._detect_performance_regressions(baseline_metrics, current_metrics)
        regressions['performance_regressions'] = perf_regressions
        
        # Detect resource regressions
        resource_regressions = self._detect_resource_regressions(baseline_metrics, current_metrics)
        regressions['resource_regressions'] = resource_regressions
        
        # Assess overall severity
        severity = self._assess_regression_severity(perf_regressions, resource_regressions)
        regressions['severity_assessment'] = severity
        
        return regressions
        
    def _detect_performance_regressions(self, baseline: Dict, current: Dict) -> Dict:
        """Detect performance-related regressions."""
        performance_metrics = [
            'boot_time', 'app_launch_time', 'container_start_time',
            'network_latency', 'io_throughput', 'cpu_performance'
        ]
        
        regressions = {}
        
        for metric in performance_metrics:
            if metric in baseline and metric in current:
                baseline_value = baseline[metric]
                current_value = current[metric]
                
                # Calculate regression percentage
                if baseline_value > 0:
                    regression = (current_value - baseline_value) / baseline_value
                    
                    # Check if regression exceeds threshold
                    threshold = self.regression_thresholds.get('performance', 0.15)
                    if regression > threshold:
                        regressions[metric] = {
                            'baseline': baseline_value,
                            'current': current_value,
                            'regression_percent': regression * 100,
                            'severity': self._classify_regression_severity(regression)
                        }
                        
        return regressions
        
    def _detect_resource_regressions(self, baseline: Dict, current: Dict) -> Dict:
        """Detect resource usage regressions."""
        resource_metrics = [
            'memory_usage', 'cpu_usage', 'battery_drain_rate',
            'storage_usage', 'network_usage'
        ]
        
        regressions = {}
        
        for metric in resource_metrics:
            if metric in baseline and metric in current:
                baseline_value = baseline[metric]
                current_value = current[metric]
                
                # Calculate regression percentage
                if baseline_value > 0:
                    regression = (current_value - baseline_value) / baseline_value
                    
                    # Determine appropriate threshold
                    if 'memory' in metric:
                        threshold = self.regression_thresholds.get('memory', 0.20)
                    elif 'battery' in metric:
                        threshold = self.regression_thresholds.get('battery', 0.25)
                    else:
                        threshold = self.regression_thresholds.get('performance', 0.15)
                        
                    if regression > threshold:
                        regressions[metric] = {
                            'baseline': baseline_value,
                            'current': current_value,
                            'regression_percent': regression * 100,
                            'severity': self._classify_regression_severity(regression)
                        }
                        
        return regressions
        
    def _classify_regression_severity(self, regression_percent: float) -> str:
        """Classify regression severity."""
        if regression_percent > 0.50:  # >50%
            return 'critical'
        elif regression_percent > 0.30:  # >30%
            return 'major'
        elif regression_percent > 0.15:  # >15%
            return 'minor'
        else:
            return 'negligible'
            
    def _assess_regression_severity(self, perf_regressions: Dict, resource_regressions: Dict) -> str:
        """Assess overall regression severity."""
        all_regressions = {**perf_regressions, **resource_regressions}
        
        if not all_regressions:
            return 'none'
            
        # Count regressions by severity
        critical_count = sum(1 for r in all_regressions.values() if r.get('severity') == 'critical')
        major_count = sum(1 for r in all_regressions.values() if r.get('severity') == 'major')
        minor_count = sum(1 for r in all_regressions.values() if r.get('severity') == 'minor')
        
        if critical_count > 0:
            return 'critical'
        elif major_count > 2:
            return 'major'
        elif major_count > 0 or minor_count > 3:
            return 'minor'
        else:
            return 'negligible'
            
    def detect_android_compatibility_regressions(self, baseline_services: List, current_services: List) -> Dict:
        """Detect Android compatibility regressions."""
        regressions = {
            'failed_services': [],
            'slow_services': [],
            'missing_services': [],
            'new_issues': []
        }
        
        # Convert to dictionaries for easier comparison
        baseline_dict = {s['name']: s for s in baseline_services}
        current_dict = {s['name']: s for s in current_services}
        
        # Check for failed services
        for service_name, baseline_service in baseline_dict.items():
            if service_name in current_dict:
                current_service = current_dict[service_name]
                
                # Check if service failed
                if baseline_service.get('status') == 'running' and current_service.get('status') != 'running':
                    regressions['failed_services'].append({
                        'service': service_name,
                        'baseline_status': baseline_service.get('status'),
                        'current_status': current_service.get('status')
                    })
                    
                # Check for slow startup
                baseline_start = baseline_service.get('start_time', 0)
                current_start = current_service.get('start_time', 0)
                
                if baseline_start > 0 and current_start > 0:
                    slowdown = (current_start - baseline_start) / baseline_start
                    if slowdown > 0.30:  # >30% slower
                        regressions['slow_services'].append({
                            'service': service_name,
                            'baseline_start_time': baseline_start,
                            'current_start_time': current_start,
                            'slowdown_percent': slowdown * 100
                        })
            else:
                # Service missing in current
                regressions['missing_services'].append(service_name)
                
        return regressions
        
    def detect_docker_functionality_regressions(self, baseline_tests: Dict, current_tests: Dict) -> Dict:
        """Detect Docker functionality regressions."""
        regressions = {
            'failed_tests': [],
            'performance_degradation': [],
            'new_failures': []
        }
        
        for test_name, baseline_result in baseline_tests.items():
            if test_name in current_tests:
                current_result = current_tests[test_name]
                
                # Check for test failures
                if baseline_result.get('passed', False) and not current_result.get('passed', False):
                    regressions['failed_tests'].append({
                        'test': test_name,
                        'baseline_status': 'passed',
                        'current_status': 'failed',
                        'error': current_result.get('error', 'Unknown error')
                    })
                    
                # Check for performance degradation
                baseline_time = baseline_result.get('execution_time', 0)
                current_time = current_result.get('execution_time', 0)
                
                if baseline_time > 0 and current_time > 0:
                    degradation = (current_time - baseline_time) / baseline_time
                    if degradation > 0.25:  # >25% slower
                        regressions['performance_degradation'].append({
                            'test': test_name,
                            'baseline_time': baseline_time,
                            'current_time': current_time,
                            'degradation_percent': degradation * 100
                        })
            else:
                # Test missing in current results
                regressions['new_failures'].append(f"Test {test_name} not executed")
                
        return regressions
        
    def generate_regression_report(self, regressions: Dict) -> str:
        """Generate human-readable regression report."""
        report_lines = []
        report_lines.append("REGRESSION DETECTION REPORT")
        report_lines.append("=" * 50)
        report_lines.append("")
        
        # Overall severity
        severity = regressions.get('severity_assessment', 'unknown')
        report_lines.append(f"Overall Severity: {severity.upper()}")
        report_lines.append("")
        
        # Performance regressions
        perf_regressions = regressions.get('performance_regressions', {})
        if perf_regressions:
            report_lines.append("PERFORMANCE REGRESSIONS:")
            for metric, details in perf_regressions.items():
                report_lines.append(f"  {metric}:")
                report_lines.append(f"    Baseline: {details['baseline']}")
                report_lines.append(f"    Current: {details['current']}")
                report_lines.append(f"    Regression: {details['regression_percent']:.1f}%")
                report_lines.append(f"    Severity: {details['severity']}")
                report_lines.append("")
        else:
            report_lines.append("No performance regressions detected.")
            report_lines.append("")
            
        # Resource regressions
        resource_regressions = regressions.get('resource_regressions', {})
        if resource_regressions:
            report_lines.append("RESOURCE USAGE REGRESSIONS:")
            for metric, details in resource_regressions.items():
                report_lines.append(f"  {metric}:")
                report_lines.append(f"    Baseline: {details['baseline']}")
                report_lines.append(f"    Current: {details['current']}")
                report_lines.append(f"    Increase: {details['regression_percent']:.1f}%")
                report_lines.append(f"    Severity: {details['severity']}")
                report_lines.append("")
        else:
            report_lines.append("No resource usage regressions detected.")
            report_lines.append("")
            
        # Recommendations
        recommendations = self._generate_regression_recommendations(regressions)
        if recommendations:
            report_lines.append("RECOMMENDATIONS:")
            for rec in recommendations:
                report_lines.append(f"  - {rec}")
            report_lines.append("")
            
        return "\n".join(report_lines)
        
    def _generate_regression_recommendations(self, regressions: Dict) -> List[str]:
        """Generate recommendations based on detected regressions."""
        recommendations = []
        
        perf_regressions = regressions.get('performance_regressions', {})
        resource_regressions = regressions.get('resource_regressions', {})
        
        # Performance recommendations
        if 'boot_time' in perf_regressions:
            recommendations.append("Investigate kernel boot process for performance bottlenecks")
            
        if 'app_launch_time' in perf_regressions:
            recommendations.append("Check Android system services and memory management")
            
        if 'container_start_time' in perf_regressions:
            recommendations.append("Optimize Docker daemon configuration and storage driver")
            
        # Resource recommendations
        if 'memory_usage' in resource_regressions:
            recommendations.append("Investigate memory leaks or inefficient memory allocation")
            
        if 'battery_drain_rate' in resource_regressions:
            recommendations.append("Check for background processes causing excessive power consumption")
            
        if 'cpu_usage' in resource_regressions:
            recommendations.append("Profile CPU usage to identify performance bottlenecks")
            
        # General recommendations based on severity
        severity = regressions.get('severity_assessment', 'none')
        if severity == 'critical':
            recommendations.append("URGENT: Critical regressions detected, immediate investigation required")
        elif severity == 'major':
            recommendations.append("Major regressions detected, prioritize investigation and fixes")
            
        return recommendations
        
    def save_baseline(self, metrics: Dict, baseline_file: str = None):
        """Save current metrics as baseline for future comparisons."""
        if baseline_file is None:
            baseline_file = self.baseline_file or "baseline_metrics.json"
            
        baseline_data = {
            'timestamp': time.time(),
            'metrics': metrics,
            'version': '1.0'
        }
        
        with open(baseline_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)
            
    def load_baseline(self, baseline_file: str = None) -> Dict:
        """Load baseline metrics from file."""
        if baseline_file is None:
            baseline_file = self.baseline_file or "baseline_metrics.json"
            
        try:
            with open(baseline_file, 'r') as f:
                baseline_data = json.load(f)
                return baseline_data.get('metrics', {})
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}