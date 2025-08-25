#!/usr/bin/env python3
"""
Container Runtime Diagnostics
Provides detailed diagnostics and troubleshooting for container runtime issues
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class ContainerDiagnostics:
    """Container runtime diagnostics and troubleshooting"""
    
    def __init__(self):
        self.kernel_source = Path("kernel_source")
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        
    def check_kernel_features(self) -> Dict:
        """Check kernel features required for containers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "kernel_version": None,
            "required_features": {},
            "optional_features": {},
            "cgroup_support": {},
            "namespace_support": {},
            "issues": []
        }
        
        # Get kernel version
        try:
            with open("/proc/version", "r") as f:
                status["kernel_version"] = f.read().strip()
        except Exception as e:
            status["issues"].append(f"Cannot read kernel version: {e}")
        
        # Check required kernel features
        required_features = {
            "CONFIG_NAMESPACES": "Namespace support",
            "CONFIG_NET_NS": "Network namespaces",
            "CONFIG_PID_NS": "PID namespaces", 
            "CONFIG_IPC_NS": "IPC namespaces",
            "CONFIG_UTS_NS": "UTS namespaces",
            "CONFIG_USER_NS": "User namespaces",
            "CONFIG_CGROUPS": "Control groups",
            "CONFIG_CGROUP_CPUACCT": "CPU accounting",
            "CONFIG_CGROUP_DEVICE": "Device cgroup",
            "CONFIG_CGROUP_FREEZER": "Freezer cgroup",
            "CONFIG_CGROUP_SCHED": "CPU scheduler cgroup",
            "CONFIG_CPUSETS": "CPU sets",
            "CONFIG_MEMCG": "Memory cgroup",
            "CONFIG_OVERLAY_FS": "Overlay filesystem",
            "CONFIG_BRIDGE": "Bridge networking"
        }
        
        optional_features = {
            "CONFIG_CHECKPOINT_RESTORE": "Checkpoint/restore support",
            "CONFIG_SECCOMP": "Secure computing mode",
            "CONFIG_SECURITY_APPARMOR": "AppArmor security",
            "CONFIG_SECURITY_SELINUX": "SELinux security",
            "CONFIG_VETH": "Virtual ethernet",
            "CONFIG_MACVLAN": "MAC VLAN support",
            "CONFIG_VLAN_8021Q": "802.1Q VLAN support"
        }
        
        # Check kernel config if available
        config_paths = ["/proc/config.gz", "/boot/config-$(uname -r)", "/boot/config"]
        kernel_config = None
        
        for config_path in config_paths:
            try:
                if config_path == "/proc/config.gz":
                    result = subprocess.run(["zcat", "/proc/config.gz"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        kernel_config = result.stdout
                        break
                else:
                    # Expand $(uname -r) if present
                    if "$(uname -r)" in config_path:
                        uname_result = subprocess.run(["uname", "-r"], 
                                                    capture_output=True, text=True)
                        if uname_result.returncode == 0:
                            config_path = config_path.replace("$(uname -r)", uname_result.stdout.strip())
                    
                    if os.path.exists(config_path):
                        with open(config_path, 'r') as f:
                            kernel_config = f.read()
                        break
            except Exception:
                continue
        
        if kernel_config:
            # Check required features
            for feature, description in required_features.items():
                if f"{feature}=y" in kernel_config:
                    status["required_features"][feature] = {"enabled": True, "description": description}
                elif f"{feature}=m" in kernel_config:
                    status["required_features"][feature] = {"enabled": "module", "description": description}
                else:
                    status["required_features"][feature] = {"enabled": False, "description": description}
                    status["issues"].append(f"Missing required feature: {feature} ({description})")
            
            # Check optional features
            for feature, description in optional_features.items():
                if f"{feature}=y" in kernel_config:
                    status["optional_features"][feature] = {"enabled": True, "description": description}
                elif f"{feature}=m" in kernel_config:
                    status["optional_features"][feature] = {"enabled": "module", "description": description}
                else:
                    status["optional_features"][feature] = {"enabled": False, "description": description}
        else:
            status["issues"].append("Kernel configuration not accessible")
        
        # Check cgroup support
        cgroup_mounts = ["/sys/fs/cgroup", "/sys/fs/cgroup/unified"]
        for mount in cgroup_mounts:
            if os.path.exists(mount):
                status["cgroup_support"][mount] = {"mounted": True}
                
                # Check cgroup controllers
                try:
                    controllers_file = os.path.join(mount, "cgroup.controllers")
                    if os.path.exists(controllers_file):
                        with open(controllers_file, 'r') as f:
                            controllers = f.read().strip().split()
                            status["cgroup_support"][mount]["controllers"] = controllers
                except Exception as e:
                    status["cgroup_support"][mount]["error"] = str(e)
            else:
                status["cgroup_support"][mount] = {"mounted": False}
        
        # Check namespace support
        ns_types = ["mnt", "pid", "net", "ipc", "uts", "user", "cgroup"]
        for ns_type in ns_types:
            ns_file = f"/proc/self/ns/{ns_type}"
            status["namespace_support"][ns_type] = {"available": os.path.exists(ns_file)}
        
        return status
    
    def diagnose_container_failures(self, container_id: Optional[str] = None) -> Dict:
        """Diagnose container startup and runtime failures"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "containers_checked": 0,
            "failed_containers": [],
            "common_issues": [],
            "recommendations": []
        }
        
        try:
            # Get container list
            cmd = ["docker", "ps", "-a", "--format", "json"]
            if container_id:
                cmd.extend(["--filter", f"id={container_id}"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                status["common_issues"].append("Docker daemon not accessible")
                return status
            
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            status["containers_checked"] = len(containers)
            
            for container in containers:
                container_id = container["ID"]
                container_name = container["Names"]
                container_status = container["Status"]
                
                # Skip running containers unless specifically requested
                if "Up" in container_status and not container_id:
                    continue
                
                # Get detailed container info
                inspect_result = subprocess.run(
                    ["docker", "inspect", container_id],
                    capture_output=True, text=True, timeout=5
                )
                
                if inspect_result.returncode != 0:
                    continue
                
                try:
                    inspect_data = json.loads(inspect_result.stdout)[0]
                    state = inspect_data.get("State", {})
                    config = inspect_data.get("Config", {})
                    host_config = inspect_data.get("HostConfig", {})
                    
                    container_info = {
                        "id": container_id[:12],
                        "name": container_name,
                        "image": container["Image"],
                        "status": container_status,
                        "state": state,
                        "issues": [],
                        "recommendations": []
                    }
                    
                    # Check for common failure patterns
                    if state.get("Dead"):
                        container_info["issues"].append("Container is dead")
                        container_info["recommendations"].append("Remove and recreate container")
                    
                    if state.get("OOMKilled"):
                        container_info["issues"].append("Killed by out-of-memory")
                        memory_limit = host_config.get("Memory", 0)
                        if memory_limit:
                            container_info["recommendations"].append(f"Increase memory limit (current: {memory_limit} bytes)")
                        else:
                            container_info["recommendations"].append("Set memory limit to prevent OOM kills")
                    
                    exit_code = state.get("ExitCode", 0)
                    if exit_code != 0 and not state.get("Running"):
                        container_info["issues"].append(f"Exited with non-zero code: {exit_code}")
                        
                        # Common exit code meanings
                        exit_code_meanings = {
                            1: "General errors",
                            2: "Misuse of shell builtins",
                            125: "Docker daemon error",
                            126: "Container command not executable",
                            127: "Container command not found",
                            128: "Invalid argument to exit",
                            130: "Container terminated by Ctrl+C",
                            137: "Container killed (SIGKILL)",
                            139: "Container segmentation fault"
                        }
                        
                        if exit_code in exit_code_meanings:
                            container_info["issues"].append(f"Exit code meaning: {exit_code_meanings[exit_code]}")
                    
                    # Check restart policy and count
                    restart_count = state.get("RestartCount", 0)
                    if restart_count > 0:
                        container_info["issues"].append(f"Container restarted {restart_count} times")
                        if restart_count > 5:
                            container_info["recommendations"].append("Investigate application stability")
                    
                    # Check for resource constraints
                    if host_config.get("CpuShares", 0) < 512:
                        container_info["recommendations"].append("Consider increasing CPU shares")
                    
                    # Check mount issues
                    mounts = inspect_data.get("Mounts", [])
                    for mount in mounts:
                        if mount.get("Type") == "bind":
                            source = mount.get("Source")
                            if source and not os.path.exists(source):
                                container_info["issues"].append(f"Bind mount source missing: {source}")
                                container_info["recommendations"].append(f"Create missing directory: {source}")
                    
                    # Check network issues
                    networks = inspect_data.get("NetworkSettings", {}).get("Networks", {})
                    if not networks:
                        container_info["issues"].append("No network configuration")
                        container_info["recommendations"].append("Check Docker network setup")
                    
                    # Get container logs for error analysis
                    logs_result = subprocess.run(
                        ["docker", "logs", "--tail", "50", container_id],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if logs_result.returncode == 0:
                        logs = logs_result.stdout + logs_result.stderr
                        
                        # Look for common error patterns in logs
                        error_patterns = [
                            ("permission denied", "Permission issues - check file/directory permissions"),
                            ("no such file or directory", "Missing files - verify image contents and mounts"),
                            ("connection refused", "Network connectivity issues"),
                            ("address already in use", "Port conflicts - check port bindings"),
                            ("out of memory", "Memory issues - increase container memory limit"),
                            ("disk space", "Storage issues - check available disk space"),
                            ("segmentation fault", "Application crash - check application logs")
                        ]
                        
                        logs_lower = logs.lower()
                        for pattern, recommendation in error_patterns:
                            if pattern in logs_lower:
                                container_info["issues"].append(f"Log pattern found: {pattern}")
                                container_info["recommendations"].append(recommendation)
                    
                    # Only add to failed containers if issues found
                    if container_info["issues"]:
                        status["failed_containers"].append(container_info)
                
                except json.JSONDecodeError:
                    continue
            
            # Generate common issues and recommendations
            all_issues = []
            all_recommendations = []
            
            for container in status["failed_containers"]:
                all_issues.extend(container["issues"])
                all_recommendations.extend(container["recommendations"])
            
            # Find most common issues
            issue_counts = {}
            for issue in all_issues:
                issue_type = issue.split(":")[0]  # Get issue type before colon
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
            
            status["common_issues"] = [
                f"{issue} (affects {count} containers)" 
                for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
                if count > 1
            ]
            
            # Deduplicate recommendations
            status["recommendations"] = list(set(all_recommendations))
            
        except Exception as e:
            status["common_issues"].append(f"Diagnostic error: {e}")
        
        return status
    
    def check_storage_issues(self) -> Dict:
        """Check for storage and filesystem issues"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "storage_driver": None,
            "storage_info": {},
            "overlay_support": {},
            "disk_usage": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Get Docker storage info
            result = subprocess.run(
                ["docker", "system", "info", "--format", "json"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                status["storage_driver"] = info.get("Driver")
                
                # Get storage driver details
                driver_status = info.get("DriverStatus", [])
                storage_info = {}
                for item in driver_status:
                    if len(item) >= 2:
                        storage_info[item[0]] = item[1]
                status["storage_info"] = storage_info
                
                # Check for storage warnings
                warnings = info.get("Warnings", [])
                for warning in warnings:
                    if "storage" in warning.lower() or "overlay" in warning.lower():
                        status["issues"].append(f"Storage warning: {warning}")
            
            # Check overlay filesystem support
            overlay_checks = {
                "overlay_module": "/proc/filesystems",
                "overlay_mount": "/sys/fs/overlay",
                "overlay_features": "/sys/module/overlay/parameters"
            }
            
            for check_name, check_path in overlay_checks.items():
                if os.path.exists(check_path):
                    status["overlay_support"][check_name] = {"available": True}
                    
                    if check_name == "overlay_module":
                        try:
                            with open(check_path, 'r') as f:
                                filesystems = f.read()
                                status["overlay_support"][check_name]["overlay_listed"] = "overlay" in filesystems
                        except Exception as e:
                            status["overlay_support"][check_name]["error"] = str(e)
                else:
                    status["overlay_support"][check_name] = {"available": False}
            
            # Check Docker data directory usage
            docker_root = "/var/lib/docker"
            try:
                result = subprocess.run(
                    ["docker", "system", "df", "--format", "json"],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    df_data = json.loads(result.stdout)
                    
                    total_size = 0
                    for item in df_data:
                        size_str = item.get("Size", "0B")
                        # Simple size parsing (assumes format like "1.2GB")
                        try:
                            if size_str.endswith("GB"):
                                total_size += float(size_str[:-2]) * 1024**3
                            elif size_str.endswith("MB"):
                                total_size += float(size_str[:-2]) * 1024**2
                            elif size_str.endswith("KB"):
                                total_size += float(size_str[:-2]) * 1024
                        except ValueError:
                            pass
                    
                    status["disk_usage"]["docker_data_size"] = total_size
                    
                    # Check available space
                    import shutil
                    total, used, free = shutil.disk_usage(docker_root if os.path.exists(docker_root) else "/")
                    status["disk_usage"]["total_space"] = total
                    status["disk_usage"]["free_space"] = free
                    status["disk_usage"]["usage_percent"] = (used / total) * 100
                    
                    # Check if running low on space
                    if free < 1024**3:  # Less than 1GB free
                        status["issues"].append("Low disk space: less than 1GB available")
                        status["recommendations"].append("Clean up Docker images and containers")
                    
                    if status["disk_usage"]["usage_percent"] > 90:
                        status["issues"].append(f"High disk usage: {status['disk_usage']['usage_percent']:.1f}%")
                        status["recommendations"].append("Run 'docker system prune' to free space")
            
            except Exception as e:
                status["issues"].append(f"Disk usage check failed: {e}")
            
            # Check for common storage issues
            if status["storage_driver"] == "vfs":
                status["issues"].append("Using VFS storage driver (inefficient)")
                status["recommendations"].append("Configure overlay2 storage driver for better performance")
            
            if not status["overlay_support"].get("overlay_module", {}).get("overlay_listed"):
                status["issues"].append("Overlay filesystem not available in kernel")
                status["recommendations"].append("Enable overlay filesystem in kernel configuration")
        
        except Exception as e:
            status["issues"].append(f"Storage check failed: {e}")
        
        return status
    
    def generate_diagnostic_report(self, container_id: Optional[str] = None) -> Dict:
        """Generate comprehensive diagnostic report"""
        print("🔍 Generating container diagnostic report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_issues": 0,
                "critical_issues": 0,
                "recommendations": 0
            },
            "kernel_features": self.check_kernel_features(),
            "container_failures": self.diagnose_container_failures(container_id),
            "storage_issues": self.check_storage_issues()
        }
        
        # Count issues and recommendations
        all_issues = []
        all_recommendations = []
        
        for section in ["kernel_features", "container_failures", "storage_issues"]:
            section_data = report[section]
            all_issues.extend(section_data.get("issues", []))
            all_recommendations.extend(section_data.get("recommendations", []))
        
        report["summary"]["total_issues"] = len(all_issues)
        report["summary"]["recommendations"] = len(set(all_recommendations))
        
        # Categorize critical issues
        critical_keywords = ["missing required", "not accessible", "dead", "killed", "failed"]
        critical_issues = [
            issue for issue in all_issues 
            if any(keyword in issue.lower() for keyword in critical_keywords)
        ]
        report["summary"]["critical_issues"] = len(critical_issues)
        
        return report
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save diagnostic report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"container_diagnostics_{timestamp}.json"
        
        report_path = self.reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Diagnostic report saved to {report_path}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
    
    def print_summary(self, report: Dict):
        """Print human-readable diagnostic summary"""
        print("\n" + "="*60)
        print("🔧 CONTAINER DIAGNOSTICS SUMMARY")
        print("="*60)
        
        summary = report["summary"]
        print(f"Total Issues Found: {summary['total_issues']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Recommendations: {summary['recommendations']}")
        
        # Kernel Features
        print(f"\n🐧 KERNEL FEATURES")
        kernel = report["kernel_features"]
        if kernel.get("kernel_version"):
            print(f"Kernel: {kernel['kernel_version'].split()[2]}")
        
        required = kernel.get("required_features", {})
        enabled_required = sum(1 for f in required.values() if f.get("enabled") == True)
        print(f"Required Features: {enabled_required}/{len(required)} enabled")
        
        optional = kernel.get("optional_features", {})
        enabled_optional = sum(1 for f in optional.values() if f.get("enabled") == True)
        print(f"Optional Features: {enabled_optional}/{len(optional)} enabled")
        
        # Container Failures
        print(f"\n🐳 CONTAINER ANALYSIS")
        containers = report["container_failures"]
        print(f"Containers Checked: {containers.get('containers_checked', 0)}")
        print(f"Failed Containers: {len(containers.get('failed_containers', []))}")
        
        if containers.get("common_issues"):
            print("Common Issues:")
            for issue in containers["common_issues"][:3]:  # Show top 3
                print(f"  • {issue}")
        
        # Storage Issues
        print(f"\n💾 STORAGE STATUS")
        storage = report["storage_issues"]
        driver = storage.get("storage_driver", "unknown")
        print(f"Storage Driver: {driver}")
        
        disk_usage = storage.get("disk_usage", {})
        if "usage_percent" in disk_usage:
            print(f"Disk Usage: {disk_usage['usage_percent']:.1f}%")
        
        # All Issues
        all_issues = []
        for section in ["kernel_features", "container_failures", "storage_issues"]:
            issues = report[section].get("issues", [])
            all_issues.extend([(section, issue) for issue in issues])
        
        if all_issues:
            print(f"\n⚠️  ALL ISSUES ({len(all_issues)})")
            for section, issue in all_issues[:10]:  # Show first 10
                print(f"  • [{section}] {issue}")
            
            if len(all_issues) > 10:
                print(f"  ... and {len(all_issues) - 10} more issues")
        
        # Recommendations
        all_recommendations = []
        for section in ["kernel_features", "container_failures", "storage_issues"]:
            recs = report[section].get("recommendations", [])
            all_recommendations.extend(recs)
        
        unique_recommendations = list(set(all_recommendations))
        if unique_recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(unique_recommendations)})")
            for rec in unique_recommendations[:5]:  # Show top 5
                print(f"  • {rec}")
            
            if len(unique_recommendations) > 5:
                print(f"  ... and {len(unique_recommendations) - 5} more recommendations")
        
        print("="*60)

def main():
    """Main diagnostic function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Container Runtime Diagnostics")
    parser.add_argument("--container", "-c", help="Specific container ID to diagnose")
    parser.add_argument("--output", "-o", help="Output report file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode - minimal output")
    parser.add_argument("--check", choices=["kernel", "containers", "storage"], 
                       help="Run specific diagnostic check only")
    
    args = parser.parse_args()
    
    diagnostics = ContainerDiagnostics()
    
    if args.check:
        # Run specific check
        if args.check == "kernel":
            result = diagnostics.check_kernel_features()
        elif args.check == "containers":
            result = diagnostics.diagnose_container_failures(args.container)
        elif args.check == "storage":
            result = diagnostics.check_storage_issues()
        
        if not args.quiet:
            print(json.dumps(result, indent=2))
    else:
        # Run full diagnostic report
        report = diagnostics.generate_diagnostic_report(args.container)
        
        if not args.quiet:
            diagnostics.print_summary(report)
        
        if args.output:
            diagnostics.save_report(report, args.output)
        else:
            diagnostics.save_report(report)

if __name__ == "__main__":
    main()