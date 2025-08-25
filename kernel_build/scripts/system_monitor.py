#!/usr/bin/env python3
"""
System Status Monitoring for Docker-Enabled Kernel Build
Monitors kernel status, Docker compatibility, and build environment health
"""

import os
import sys
import json
import subprocess
import platform
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class SystemMonitor:
    """System status monitoring and health checks"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "kernel_build/config/deployment_config.json"
        self.config = self._load_config()
        self.kernel_source = Path("kernel_source")
        self.kernel_output = Path("kernel_output")
        
    def _load_config(self) -> Dict:
        """Load monitoring configuration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
        
        return {
            "monitoring": {
                "check_interval": 30,
                "log_retention_days": 7,
                "alert_thresholds": {
                    "disk_usage": 90,
                    "memory_usage": 85,
                    "build_time": 3600
                }
            }
        }
    
    def check_build_environment(self) -> Dict:
        """Check build environment status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version()
            },
            "environment": {},
            "tools": {},
            "issues": []
        }
        
        # Check environment variables
        env_vars = ["ARCH", "SUBARCH", "CROSS_COMPILE", "ANDROID_NDK_ROOT", "PYTHON"]
        for var in env_vars:
            status["environment"][var] = os.environ.get(var, "Not set")
        
        # Check essential tools
        tools = {
            "python": ["python", "--version"],
            "python3": ["python3", "--version"],
            "make": ["make", "--version"],
            "gcc": ["gcc", "--version"],
            "git": ["git", "--version"]
        }
        
        for tool, cmd in tools.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0] if result.stdout else "Available"
                    status["tools"][tool] = {"available": True, "version": version}
                else:
                    status["tools"][tool] = {"available": False, "error": result.stderr}
            except Exception as e:
                status["tools"][tool] = {"available": False, "error": str(e)}
        
        # Check cross-compiler
        cross_compile = os.environ.get("CROSS_COMPILE", "")
        if cross_compile:
            gcc_cmd = f"{cross_compile}gcc"
            try:
                result = subprocess.run([gcc_cmd, "--version"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    status["tools"]["cross_compiler"] = {
                        "available": True,
                        "command": gcc_cmd,
                        "version": result.stdout.split('\n')[0]
                    }
                else:
                    status["tools"]["cross_compiler"] = {
                        "available": False,
                        "command": gcc_cmd,
                        "error": result.stderr
                    }
                    status["issues"].append(f"Cross-compiler not working: {gcc_cmd}")
            except Exception as e:
                status["tools"]["cross_compiler"] = {
                    "available": False,
                    "command": gcc_cmd,
                    "error": str(e)
                }
                status["issues"].append(f"Cross-compiler error: {e}")
        else:
            status["issues"].append("CROSS_COMPILE environment variable not set")
        
        # Check Python command availability (critical for kernel build)
        if not status["tools"]["python"]["available"]:
            status["issues"].append("Python command not available - kernel build will fail")
            
        return status
    
    def check_kernel_source_status(self) -> Dict:
        """Check kernel source and configuration status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "source_available": self.kernel_source.exists(),
            "source_path": str(self.kernel_source),
            "config_files": {},
            "patches_applied": {},
            "issues": []
        }
        
        if not status["source_available"]:
            status["issues"].append("Kernel source not found")
            return status
        
        # Check important config files
        config_files = {
            "defconfig": self.kernel_source / "arch/arm64/configs/raphael_defconfig",
            "makefile": self.kernel_source / "Makefile",
            "cpuset": self.kernel_source / "kernel/cgroup/cpuset.c"
        }
        
        for name, path in config_files.items():
            status["config_files"][name] = {
                "exists": path.exists(),
                "path": str(path),
                "size": path.stat().st_size if path.exists() else 0,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
            }
        
        # Check for Docker-specific configurations
        defconfig_path = config_files["defconfig"]
        if defconfig_path.exists():
            try:
                with open(defconfig_path, 'r') as f:
                    content = f.read()
                
                docker_configs = [
                    "CONFIG_NAMESPACES=y",
                    "CONFIG_NET_NS=y",
                    "CONFIG_PID_NS=y",
                    "CONFIG_IPC_NS=y",
                    "CONFIG_UTS_NS=y",
                    "CONFIG_CGROUPS=y",
                    "CONFIG_CGROUP_CPUACCT=y",
                    "CONFIG_CGROUP_DEVICE=y",
                    "CONFIG_CGROUP_FREEZER=y",
                    "CONFIG_CGROUP_SCHED=y",
                    "CONFIG_CPUSETS=y",
                    "CONFIG_MEMCG=y",
                    "CONFIG_OVERLAY_FS=y",
                    "CONFIG_BRIDGE=y"
                ]
                
                docker_status = {}
                for config in docker_configs:
                    docker_status[config] = config in content
                
                status["docker_configs"] = docker_status
                missing_configs = [k for k, v in docker_status.items() if not v]
                if missing_configs:
                    status["issues"].append(f"Missing Docker configs: {', '.join(missing_configs)}")
                
            except Exception as e:
                status["issues"].append(f"Could not check defconfig: {e}")
        
        # Check cpuset modifications
        cpuset_path = config_files["cpuset"]
        if cpuset_path.exists():
            try:
                with open(cpuset_path, 'r') as f:
                    content = f.read()
                
                docker_cpuset_files = [
                    "docker.cpus", "docker.mems", "docker.memory_migrate",
                    "docker.cpu_exclusive", "docker.mem_exclusive", "docker.mem_hardwall",
                    "docker.memory_pressure", "docker.memory_spread_page", "docker.memory_spread_slab",
                    "docker.sched_load_balance", "docker.sched_relax_domain_level"
                ]
                
                cpuset_modifications = {}
                for file_name in docker_cpuset_files:
                    cpuset_modifications[file_name] = file_name in content
                
                status["cpuset_modifications"] = cpuset_modifications
                missing_mods = [k for k, v in cpuset_modifications.items() if not v]
                if missing_mods:
                    status["issues"].append(f"Missing cpuset modifications: {', '.join(missing_mods)}")
                    
            except Exception as e:
                status["issues"].append(f"Could not check cpuset modifications: {e}")
        
        return status
    
    def check_docker_compatibility(self) -> Dict:
        """Check Docker daemon and container compatibility"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "docker_available": False,
            "daemon_running": False,
            "containers": [],
            "images": [],
            "system_info": {},
            "issues": []
        }
        
        # Check if Docker is available
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                status["docker_available"] = True
                status["docker_version"] = result.stdout.strip()
            else:
                status["issues"].append("Docker command not available")
        except Exception as e:
            status["issues"].append(f"Docker check failed: {e}")
        
        if not status["docker_available"]:
            return status
        
        # Check if Docker daemon is running
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                status["daemon_running"] = True
                # Parse basic system info
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        if key in ['containers', 'images', 'server_version', 'storage_driver', 'kernel_version']:
                            status["system_info"][key] = value.strip()
            else:
                status["issues"].append("Docker daemon not running")
        except Exception as e:
            status["issues"].append(f"Docker daemon check failed: {e}")
        
        if status["daemon_running"]:
            # Get container list
            try:
                result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            try:
                                container = json.loads(line)
                                status["containers"].append({
                                    "id": container.get("ID", ""),
                                    "name": container.get("Names", ""),
                                    "image": container.get("Image", ""),
                                    "status": container.get("Status", ""),
                                    "state": container.get("State", "")
                                })
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                status["issues"].append(f"Container list failed: {e}")
            
            # Get image list
            try:
                result = subprocess.run(["docker", "images", "--format", "json"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            try:
                                image = json.loads(line)
                                status["images"].append({
                                    "repository": image.get("Repository", ""),
                                    "tag": image.get("Tag", ""),
                                    "id": image.get("ID", ""),
                                    "size": image.get("Size", "")
                                })
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                status["issues"].append(f"Image list failed: {e}")
        
        return status
    
    def check_system_resources(self) -> Dict:
        """Check system resource usage"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "disk_usage": {},
            "memory_info": {},
            "load_average": {},
            "issues": []
        }
        
        # Check disk usage
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            usage_percent = (used / total) * 100
            
            status["disk_usage"] = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "usage_percent": round(usage_percent, 2)
            }
            
            threshold = self.config.get("monitoring", {}).get("alert_thresholds", {}).get("disk_usage", 90)
            if usage_percent > threshold:
                status["issues"].append(f"Disk usage high: {usage_percent:.1f}% (threshold: {threshold}%)")
                
        except Exception as e:
            status["issues"].append(f"Disk usage check failed: {e}")
        
        # Check memory (if available)
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                
                mem_total = 0
                mem_available = 0
                for line in meminfo.split('\n'):
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1]) * 1024  # Convert KB to bytes
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1]) * 1024
                
                if mem_total > 0:
                    mem_used = mem_total - mem_available
                    usage_percent = (mem_used / mem_total) * 100
                    
                    status["memory_info"] = {
                        "total_gb": round(mem_total / (1024**3), 2),
                        "used_gb": round(mem_used / (1024**3), 2),
                        "available_gb": round(mem_available / (1024**3), 2),
                        "usage_percent": round(usage_percent, 2)
                    }
                    
                    threshold = self.config.get("monitoring", {}).get("alert_thresholds", {}).get("memory_usage", 85)
                    if usage_percent > threshold:
                        status["issues"].append(f"Memory usage high: {usage_percent:.1f}% (threshold: {threshold}%)")
            
            elif platform.system() == "Darwin":  # macOS
                try:
                    # Get memory info using vm_stat
                    result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        page_size = 4096  # Default page size
                        
                        for line in lines:
                            if "page size of" in line:
                                page_size = int(line.split()[-2])
                                break
                        
                        mem_stats = {}
                        for line in lines:
                            if ":" in line:
                                key, value = line.split(":", 1)
                                key = key.strip().lower().replace(" ", "_")
                                try:
                                    # Extract number from value (remove dots and convert)
                                    num_value = int(value.strip().rstrip('.'))
                                    mem_stats[key] = num_value * page_size
                                except (ValueError, AttributeError):
                                    pass
                        
                        if "pages_free" in mem_stats and "pages_active" in mem_stats:
                            free_mem = mem_stats.get("pages_free", 0)
                            active_mem = mem_stats.get("pages_active", 0)
                            inactive_mem = mem_stats.get("pages_inactive", 0)
                            wired_mem = mem_stats.get("pages_wired_down", 0)
                            
                            total_mem = free_mem + active_mem + inactive_mem + wired_mem
                            used_mem = active_mem + wired_mem
                            
                            if total_mem > 0:
                                usage_percent = (used_mem / total_mem) * 100
                                
                                status["memory_info"] = {
                                    "total_gb": round(total_mem / (1024**3), 2),
                                    "used_gb": round(used_mem / (1024**3), 2),
                                    "free_gb": round(free_mem / (1024**3), 2),
                                    "usage_percent": round(usage_percent, 2)
                                }
                except Exception as e:
                    status["issues"].append(f"macOS memory check failed: {e}")
                    
        except Exception as e:
            status["issues"].append(f"Memory check failed: {e}")
        
        # Check load average (Unix systems)
        try:
            if hasattr(os, 'getloadavg'):
                load1, load5, load15 = os.getloadavg()
                status["load_average"] = {
                    "1min": round(load1, 2),
                    "5min": round(load5, 2),
                    "15min": round(load15, 2)
                }
        except Exception as e:
            status["issues"].append(f"Load average check failed: {e}")
        
        return status
    
    def generate_health_report(self) -> Dict:
        """Generate comprehensive system health report"""
        print("🔍 Generating system health report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "overall_status": "unknown",
                "critical_issues": 0,
                "warnings": 0,
                "checks_passed": 0,
                "total_checks": 0
            },
            "build_environment": self.check_build_environment(),
            "kernel_source": self.check_kernel_source_status(),
            "docker_compatibility": self.check_docker_compatibility(),
            "system_resources": self.check_system_resources()
        }
        
        # Analyze overall health
        all_issues = []
        for section in ["build_environment", "kernel_source", "docker_compatibility", "system_resources"]:
            issues = report[section].get("issues", [])
            all_issues.extend(issues)
        
        # Categorize issues
        critical_keywords = ["not found", "not available", "failed", "error", "missing"]
        warning_keywords = ["high", "threshold", "not set"]
        
        critical_issues = []
        warnings = []
        
        for issue in all_issues:
            issue_lower = issue.lower()
            if any(keyword in issue_lower for keyword in critical_keywords):
                critical_issues.append(issue)
            elif any(keyword in issue_lower for keyword in warning_keywords):
                warnings.append(issue)
            else:
                warnings.append(issue)  # Default to warning
        
        report["summary"]["critical_issues"] = len(critical_issues)
        report["summary"]["warnings"] = len(warnings)
        report["summary"]["total_checks"] = 4  # Number of main check categories
        
        # Determine overall status
        if critical_issues:
            report["summary"]["overall_status"] = "critical"
        elif warnings:
            report["summary"]["overall_status"] = "warning"
        else:
            report["summary"]["overall_status"] = "healthy"
            report["summary"]["checks_passed"] = 4
        
        return report
    
    def save_report(self, report: Dict, output_path: str = "system_health_report.json"):
        """Save health report to file"""
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Health report saved to {output_path}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
    
    def print_summary(self, report: Dict):
        """Print human-readable summary"""
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("🏥 SYSTEM HEALTH SUMMARY")
        print("="*60)
        
        # Overall status
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "❌",
            "unknown": "❓"
        }
        
        status = summary["overall_status"]
        print(f"Overall Status: {status_emoji.get(status, '❓')} {status.upper()}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Warnings: {summary['warnings']}")
        print(f"Checks Passed: {summary['checks_passed']}/{summary['total_checks']}")
        
        # Build Environment
        print(f"\n🔧 BUILD ENVIRONMENT")
        build_env = report["build_environment"]
        platform_info = build_env["platform"]
        print(f"Platform: {platform_info['system']} {platform_info['machine']}")
        print(f"Python: {platform_info['python_version']}")
        
        tools = build_env["tools"]
        for tool, info in tools.items():
            status_icon = "✅" if info["available"] else "❌"
            print(f"  {status_icon} {tool}: {info.get('version', 'Not available')}")
        
        # Kernel Source
        print(f"\n🐧 KERNEL SOURCE")
        kernel = report["kernel_source"]
        source_icon = "✅" if kernel["source_available"] else "❌"
        print(f"  {source_icon} Source Available: {kernel['source_available']}")
        
        if "docker_configs" in kernel:
            docker_configs = kernel["docker_configs"]
            enabled_count = sum(1 for v in docker_configs.values() if v)
            total_count = len(docker_configs)
            print(f"  📦 Docker Configs: {enabled_count}/{total_count} enabled")
        
        if "cpuset_modifications" in kernel:
            cpuset_mods = kernel["cpuset_modifications"]
            mod_count = sum(1 for v in cpuset_mods.values() if v)
            total_mods = len(cpuset_mods)
            print(f"  🔧 Cpuset Mods: {mod_count}/{total_mods} applied")
        
        # Docker Compatibility
        print(f"\n🐳 DOCKER COMPATIBILITY")
        docker = report["docker_compatibility"]
        docker_icon = "✅" if docker["docker_available"] else "❌"
        daemon_icon = "✅" if docker["daemon_running"] else "❌"
        print(f"  {docker_icon} Docker Available: {docker['docker_available']}")
        print(f"  {daemon_icon} Daemon Running: {docker['daemon_running']}")
        
        if docker["daemon_running"]:
            print(f"  📦 Containers: {len(docker['containers'])}")
            print(f"  💿 Images: {len(docker['images'])}")
        
        # System Resources
        print(f"\n💻 SYSTEM RESOURCES")
        resources = report["system_resources"]
        
        if "disk_usage" in resources:
            disk = resources["disk_usage"]
            disk_icon = "⚠️" if disk.get("usage_percent", 0) > 80 else "✅"
            print(f"  {disk_icon} Disk: {disk.get('usage_percent', 0):.1f}% used ({disk.get('free_gb', 0):.1f}GB free)")
        
        if "memory_info" in resources:
            memory = resources["memory_info"]
            mem_icon = "⚠️" if memory.get("usage_percent", 0) > 80 else "✅"
            print(f"  {mem_icon} Memory: {memory.get('usage_percent', 0):.1f}% used ({memory.get('available_gb', 0):.1f}GB available)")
        
        if "load_average" in resources:
            load = resources["load_average"]
            print(f"  📊 Load: {load.get('1min', 0)} {load.get('5min', 0)} {load.get('15min', 0)}")
        
        # Issues
        all_issues = []
        for section in ["build_environment", "kernel_source", "docker_compatibility", "system_resources"]:
            issues = report[section].get("issues", [])
            all_issues.extend([(section, issue) for issue in issues])
        
        if all_issues:
            print(f"\n⚠️  ISSUES FOUND ({len(all_issues)})")
            for section, issue in all_issues:
                print(f"  • [{section}] {issue}")
        else:
            print(f"\n✅ No issues found!")
        
        print("="*60)

def main():
    """Main monitoring function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Status Monitor for Docker-Enabled Kernel Build")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--output", default="system_health_report.json", help="Output report file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode - minimal output")
    parser.add_argument("--watch", "-w", type=int, help="Watch mode - repeat every N seconds")
    parser.add_argument("--check", choices=["env", "kernel", "docker", "resources"], 
                       help="Run specific check only")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.config)
    
    def run_checks():
        if args.check:
            # Run specific check
            if args.check == "env":
                result = monitor.check_build_environment()
            elif args.check == "kernel":
                result = monitor.check_kernel_source_status()
            elif args.check == "docker":
                result = monitor.check_docker_compatibility()
            elif args.check == "resources":
                result = monitor.check_system_resources()
            
            if not args.quiet:
                print(json.dumps(result, indent=2))
        else:
            # Run full health report
            report = monitor.generate_health_report()
            
            if not args.quiet:
                monitor.print_summary(report)
            
            monitor.save_report(report, args.output)
    
    if args.watch:
        print(f"🔄 Starting monitoring (checking every {args.watch} seconds)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                run_checks()
                if not args.quiet:
                    print(f"\n⏰ Next check in {args.watch} seconds...")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
    else:
        run_checks()

if __name__ == "__main__":
    main()