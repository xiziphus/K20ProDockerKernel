#!/usr/bin/env python3
"""
Comprehensive Debugging Toolkit
Combines all debugging utilities for kernel and Docker issues
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import our debugging modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from log_analyzer import LogAnalyzer
    from network_debugger import NetworkDebugger
    from storage_debugger import StorageDebugger
except ImportError as e:
    print(f"❌ Failed to import debugging modules: {e}")
    sys.exit(1)

class DebugToolkit:
    """Comprehensive debugging toolkit for Docker-enabled kernel"""
    
    def __init__(self):
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        
        # Initialize debugging tools
        self.log_analyzer = LogAnalyzer()
        self.network_debugger = NetworkDebugger()
        self.storage_debugger = StorageDebugger()
    
    def run_comprehensive_diagnostics(self, hours: int = 24) -> Dict:
        """Run all diagnostic tools and generate comprehensive report"""
        print("🔍 Starting comprehensive system diagnostics...")
        print("="*60)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "diagnostic_version": "1.0.0",
            "system_info": self._get_system_info(),
            "summary": {
                "total_issues": 0,
                "critical_issues": 0,
                "warnings": 0,
                "recommendations": []
            },
            "diagnostics": {}
        }
        
        # Run log analysis
        print("📋 Analyzing system logs...")
        try:
            log_report = self.log_analyzer.generate_diagnostic_report(hours)
            report["diagnostics"]["logs"] = log_report
            print(f"   ✅ Found {log_report['summary']['total_errors']} log errors")
        except Exception as e:
            print(f"   ❌ Log analysis failed: {e}")
            report["diagnostics"]["logs"] = {"error": str(e)}
        
        # Run network diagnostics
        print("🌐 Checking network configuration...")
        try:
            network_report = self.network_debugger.diagnose_network_issues()
            report["diagnostics"]["network"] = network_report
            print(f"   ✅ Found {network_report['summary']['total_issues']} network issues")
        except Exception as e:
            print(f"   ❌ Network diagnostics failed: {e}")
            report["diagnostics"]["network"] = {"error": str(e)}
        
        # Run storage diagnostics
        print("💾 Checking storage configuration...")
        try:
            storage_report = self.storage_debugger.diagnose_storage_issues()
            report["diagnostics"]["storage"] = storage_report
            print(f"   ✅ Found {storage_report['summary']['total_issues']} storage issues")
        except Exception as e:
            print(f"   ❌ Storage diagnostics failed: {e}")
            report["diagnostics"]["storage"] = {"error": str(e)}
        
        # Run Docker-specific checks
        print("🐳 Checking Docker configuration...")
        try:
            docker_report = self._check_docker_health()
            report["diagnostics"]["docker"] = docker_report
            print(f"   ✅ Docker health check completed")
        except Exception as e:
            print(f"   ❌ Docker health check failed: {e}")
            report["diagnostics"]["docker"] = {"error": str(e)}
        
        # Run kernel-specific checks
        print("🔧 Checking kernel configuration...")
        try:
            kernel_report = self._check_kernel_config()
            report["diagnostics"]["kernel"] = kernel_report
            print(f"   ✅ Kernel configuration check completed")
        except Exception as e:
            print(f"   ❌ Kernel check failed: {e}")
            report["diagnostics"]["kernel"] = {"error": str(e)}
        
        # Generate summary and recommendations
        print("📊 Generating summary and recommendations...")
        self._generate_summary(report)
        
        print("="*60)
        print("✅ Comprehensive diagnostics completed")
        
        return report
    
    def _get_system_info(self) -> Dict:
        """Get basic system information"""
        info = {
            "timestamp": datetime.now().isoformat(),
            "hostname": "unknown",
            "kernel_version": "unknown",
            "os_release": "unknown",
            "docker_version": "unknown",
            "architecture": "unknown"
        }
        
        try:
            # Get hostname
            result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["hostname"] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            # Get kernel version
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["kernel_version"] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            # Get architecture
            result = subprocess.run(["uname", "-m"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["architecture"] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            # Get OS release
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            info["os_release"] = line.split("=", 1)[1].strip().strip('"')
                            break
        except Exception:
            pass
        
        try:
            # Get Docker version
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["docker_version"] = result.stdout.strip()
        except Exception:
            pass
        
        return info
    
    def _check_docker_health(self) -> Dict:
        """Check Docker daemon health and configuration"""
        health = {
            "timestamp": datetime.now().isoformat(),
            "daemon_running": False,
            "daemon_info": {},
            "service_status": "unknown",
            "container_count": 0,
            "image_count": 0,
            "volume_count": 0,
            "network_count": 0,
            "issues": []
        }
        
        try:
            # Check if Docker daemon is running
            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                health["daemon_running"] = True
                
                # Parse Docker info
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        
                        if key == "containers":
                            try:
                                health["container_count"] = int(value)
                            except ValueError:
                                pass
                        elif key == "images":
                            try:
                                health["image_count"] = int(value)
                            except ValueError:
                                pass
                        elif key in ["server_version", "storage_driver", "logging_driver", "cgroup_driver"]:
                            health["daemon_info"][key] = value
            else:
                health["issues"].append(f"Docker daemon not responding: {result.stderr}")
        
        except Exception as e:
            health["issues"].append(f"Docker health check failed: {e}")
        
        try:
            # Check Docker service status (systemd)
            result = subprocess.run(["systemctl", "is-active", "docker"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                health["service_status"] = result.stdout.strip()
            else:
                health["service_status"] = "inactive"
        except Exception:
            pass
        
        try:
            # Get volume count
            result = subprocess.run(["docker", "volume", "ls", "-q"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                volumes = [line for line in result.stdout.split('\n') if line.strip()]
                health["volume_count"] = len(volumes)
        except Exception:
            pass
        
        try:
            # Get network count
            result = subprocess.run(["docker", "network", "ls", "-q"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                networks = [line for line in result.stdout.split('\n') if line.strip()]
                health["network_count"] = len(networks)
        except Exception:
            pass
        
        return health
    
    def _check_kernel_config(self) -> Dict:
        """Check kernel configuration for Docker requirements"""
        config = {
            "timestamp": datetime.now().isoformat(),
            "config_available": False,
            "docker_requirements": {},
            "missing_features": [],
            "cgroup_support": {},
            "namespace_support": {},
            "issues": []
        }
        
        # Docker required kernel features
        required_features = {
            "CONFIG_NAMESPACES": "Namespace support",
            "CONFIG_NET_NS": "Network namespaces",
            "CONFIG_PID_NS": "PID namespaces",
            "CONFIG_IPC_NS": "IPC namespaces",
            "CONFIG_UTS_NS": "UTS namespaces",
            "CONFIG_CGROUPS": "Control groups",
            "CONFIG_CGROUP_CPUACCT": "CPU accounting",
            "CONFIG_CGROUP_DEVICE": "Device cgroup",
            "CONFIG_CGROUP_FREEZER": "Freezer cgroup",
            "CONFIG_CGROUP_SCHED": "CPU scheduler cgroup",
            "CONFIG_CPUSETS": "CPU sets",
            "CONFIG_MEMCG": "Memory cgroup",
            "CONFIG_KEYS": "Kernel key management",
            "CONFIG_VETH": "Virtual ethernet",
            "CONFIG_BRIDGE": "Bridge support",
            "CONFIG_BRIDGE_NETFILTER": "Bridge netfilter",
            "CONFIG_IP_NF_FILTER": "IP netfilter",
            "CONFIG_IP_NF_TARGET_MASQUERADE": "IP masquerading",
            "CONFIG_NETFILTER_XT_MATCH_ADDRTYPE": "Address type matching",
            "CONFIG_NETFILTER_XT_MATCH_CONNTRACK": "Connection tracking",
            "CONFIG_NETFILTER_XT_MATCH_IPVS": "IPVS matching",
            "CONFIG_IP_NF_NAT": "IP NAT",
            "CONFIG_NF_NAT": "NAT support",
            "CONFIG_POSIX_MQUEUE": "POSIX message queues",
            "CONFIG_OVERLAY_FS": "Overlay filesystem"
        }
        
        # Check kernel config
        config_paths = [
            "/proc/config.gz",
            "/boot/config-" + os.uname().release,
            "/usr/src/linux/.config"
        ]
        
        kernel_config = {}
        
        for config_path in config_paths:
            try:
                if config_path.endswith(".gz") and os.path.exists(config_path):
                    import gzip
                    with gzip.open(config_path, 'rt') as f:
                        content = f.read()
                elif os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        content = f.read()
                else:
                    continue
                
                # Parse config
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('CONFIG_') and '=' in line:
                        key, value = line.split('=', 1)
                        kernel_config[key] = value
                
                config["config_available"] = True
                break
                
            except Exception as e:
                config["issues"].append(f"Failed to read {config_path}: {e}")
        
        if not config["config_available"]:
            config["issues"].append("Kernel configuration not available")
            return config
        
        # Check required features
        for feature, description in required_features.items():
            if feature in kernel_config:
                value = kernel_config[feature]
                config["docker_requirements"][feature] = {
                    "description": description,
                    "value": value,
                    "enabled": value in ["y", "m"]
                }
                
                if value not in ["y", "m"]:
                    config["missing_features"].append(f"{feature} ({description})")
            else:
                config["docker_requirements"][feature] = {
                    "description": description,
                    "value": "not set",
                    "enabled": False
                }
                config["missing_features"].append(f"{feature} ({description})")
        
        # Check cgroup support
        cgroup_features = [f for f in required_features.keys() if "CGROUP" in f]
        enabled_cgroups = sum(1 for f in cgroup_features if config["docker_requirements"].get(f, {}).get("enabled", False))
        config["cgroup_support"] = {
            "total_features": len(cgroup_features),
            "enabled_features": enabled_cgroups,
            "support_level": "full" if enabled_cgroups == len(cgroup_features) else "partial" if enabled_cgroups > 0 else "none"
        }
        
        # Check namespace support
        namespace_features = [f for f in required_features.keys() if "_NS" in f or f == "CONFIG_NAMESPACES"]
        enabled_namespaces = sum(1 for f in namespace_features if config["docker_requirements"].get(f, {}).get("enabled", False))
        config["namespace_support"] = {
            "total_features": len(namespace_features),
            "enabled_features": enabled_namespaces,
            "support_level": "full" if enabled_namespaces == len(namespace_features) else "partial" if enabled_namespaces > 0 else "none"
        }
        
        return config
    
    def _generate_summary(self, report: Dict):
        """Generate summary and recommendations from all diagnostics"""
        summary = report["summary"]
        recommendations = []
        
        total_issues = 0
        critical_issues = 0
        
        # Analyze each diagnostic section
        for section_name, section_data in report["diagnostics"].items():
            if isinstance(section_data, dict) and "error" not in section_data:
                # Count issues from this section
                if "summary" in section_data:
                    section_summary = section_data["summary"]
                    total_issues += section_summary.get("total_issues", 0)
                    critical_issues += section_summary.get("critical_issues", 0)
                
                # Section-specific recommendations
                if section_name == "logs":
                    log_recommendations = section_data.get("recommendations", [])
                    recommendations.extend(log_recommendations)
                    
                    if section_data.get("summary", {}).get("critical_issues", 0) > 0:
                        recommendations.append("Critical kernel or system errors detected - review system logs")
                
                elif section_name == "network":
                    network_issues = section_data.get("summary", {}).get("total_issues", 0)
                    if network_issues > 5:
                        recommendations.append("Multiple network issues detected - check Docker networking configuration")
                    
                    # Check for Docker bridge
                    interfaces = section_data.get("network_interfaces", {}).get("docker_interfaces", {})
                    if "docker0" not in interfaces:
                        recommendations.append("Docker bridge interface missing - restart Docker daemon")
                
                elif section_name == "storage":
                    storage_driver = section_data.get("summary", {}).get("storage_driver", "")
                    if storage_driver == "vfs":
                        recommendations.append("Using inefficient VFS storage driver - consider switching to overlay2")
                    
                    disk_usage = section_data.get("summary", {}).get("disk_usage_percent", 0)
                    if disk_usage > 90:
                        recommendations.append("High disk usage detected - clean up Docker images and containers")
                
                elif section_name == "docker":
                    if not section_data.get("daemon_running", False):
                        recommendations.append("Docker daemon not running - start Docker service")
                        critical_issues += 1
                    
                    missing_features = section_data.get("missing_features", [])
                    if missing_features:
                        recommendations.append(f"Docker missing {len(missing_features)} kernel features - rebuild kernel with Docker support")
                
                elif section_name == "kernel":
                    missing_features = section_data.get("missing_features", [])
                    if len(missing_features) > 5:
                        recommendations.append("Many required kernel features missing - kernel may not support Docker properly")
                        critical_issues += 1
                    
                    cgroup_support = section_data.get("cgroup_support", {}).get("support_level", "none")
                    if cgroup_support != "full":
                        recommendations.append("Incomplete cgroup support - Docker resource management may not work properly")
        
        # Update summary
        summary["total_issues"] = total_issues
        summary["critical_issues"] = critical_issues
        summary["warnings"] = total_issues - critical_issues
        summary["recommendations"] = list(set(recommendations))  # Remove duplicates
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save comprehensive diagnostic report"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_diagnostics_{timestamp}.json"
        
        report_path = self.reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Comprehensive diagnostic report saved to {report_path}")
            return str(report_path)
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
            return None
    
    def print_summary(self, report: Dict):
        """Print comprehensive diagnostic summary"""
        print("\n" + "="*80)
        print("🔍 COMPREHENSIVE SYSTEM DIAGNOSTICS SUMMARY")
        print("="*80)
        
        # System info
        system_info = report["system_info"]
        print(f"System: {system_info['hostname']} ({system_info['architecture']})")
        print(f"Kernel: {system_info['kernel_version']}")
        print(f"OS: {system_info['os_release']}")
        print(f"Docker: {system_info['docker_version']}")
        print(f"Timestamp: {report['timestamp']}")
        
        # Overall summary
        summary = report["summary"]
        print(f"\n📊 OVERALL SUMMARY")
        print(f"Total Issues: {summary['total_issues']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Warnings: {summary['warnings']}")
        
        # Section summaries
        print(f"\n📋 DIAGNOSTIC SECTIONS")
        for section_name, section_data in report["diagnostics"].items():
            if isinstance(section_data, dict):
                if "error" in section_data:
                    print(f"  • {section_name.title()}: ❌ Failed ({section_data['error']})")
                else:
                    section_summary = section_data.get("summary", {})
                    issues = section_summary.get("total_issues", 0)
                    critical = section_summary.get("critical_issues", 0)
                    status = "✅ OK" if issues == 0 else f"⚠️  {issues} issues ({critical} critical)"
                    print(f"  • {section_name.title()}: {status}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS ({len(summary['recommendations'])})")
        if summary["recommendations"]:
            for i, rec in enumerate(summary["recommendations"], 1):
                print(f"  {i}. {rec}")
        else:
            print("  No specific recommendations - system appears healthy")
        
        # Health status
        print(f"\n🏥 SYSTEM HEALTH")
        if summary["critical_issues"] == 0:
            if summary["total_issues"] == 0:
                print("  🟢 EXCELLENT - No issues detected")
            elif summary["total_issues"] < 5:
                print("  🟡 GOOD - Minor issues detected")
            else:
                print("  🟠 FAIR - Multiple issues detected")
        else:
            print("  🔴 POOR - Critical issues require attention")
        
        print("\n" + "="*80)

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Debugging Toolkit")
    parser.add_argument("--hours", type=int, default=24, help="Hours of logs to analyze (default: 24)")
    parser.add_argument("--output", type=str, help="Output filename for report")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    parser.add_argument("--summary-only", action="store_true", help="Show summary only")
    
    args = parser.parse_args()
    
    toolkit = DebugToolkit()
    
    print("🔍 Docker-Enabled Kernel Debugging Toolkit")
    print("="*60)
    
    # Run comprehensive diagnostics
    report = toolkit.run_comprehensive_diagnostics(args.hours)
    
    # Save report
    report_path = toolkit.save_report(report, args.output)
    
    # Print summary
    if not args.quiet:
        toolkit.print_summary(report)
    elif args.summary_only:
        summary = report["summary"]
        print(f"\nQuick Summary: {summary['total_issues']} issues ({summary['critical_issues']} critical)")
        if summary["recommendations"]:
            print("Top recommendation:", summary["recommendations"][0])
    
    # Exit with appropriate code
    if report["summary"]["critical_issues"] > 0:
        sys.exit(2)  # Critical issues
    elif report["summary"]["total_issues"] > 0:
        sys.exit(1)  # Non-critical issues
    else:
        sys.exit(0)  # No issues

if __name__ == "__main__":
    main()