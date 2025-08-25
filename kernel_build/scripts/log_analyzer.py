#!/usr/bin/env python3
"""
Log Collection and Analysis Tool
Collects and analyzes logs from kernel, Docker daemon, and containers for troubleshooting
"""

import os
import sys
import json
import subprocess
import re
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

class LogAnalyzer:
    """Log collection and analysis for kernel and Docker issues"""
    
    def __init__(self):
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        self.log_patterns = self._load_log_patterns()
        
    def _load_log_patterns(self) -> Dict:
        """Load common log patterns for issue detection"""
        return {
            "kernel_errors": [
                (r"kernel: Out of memory", "OOM Killer activated"),
                (r"kernel: segfault", "Segmentation fault in kernel"),
                (r"kernel: BUG:", "Kernel BUG detected"),
                (r"kernel: WARNING:", "Kernel warning"),
                (r"kernel: Call Trace:", "Kernel stack trace"),
                (r"cgroup: .*failed", "Cgroup operation failed"),
                (r"overlayfs: .*error", "Overlay filesystem error"),
                (r"bridge: .*failed", "Bridge networking error")
            ],
            "docker_errors": [
                (r"dockerd.*error", "Docker daemon error"),
                (r"containerd.*error", "Containerd error"),
                (r"runc.*error", "Runc error"),
                (r"failed to start container", "Container start failure"),
                (r"failed to create.*container", "Container creation failure"),
                (r"network.*not found", "Network configuration error"),
                (r"storage driver.*failed", "Storage driver error"),
                (r"permission denied", "Permission error"),
                (r"no space left", "Disk space error")
            ],
            "container_errors": [
                (r"exec format error", "Architecture mismatch"),
                (r"no such file or directory", "Missing file/binary"),
                (r"permission denied", "Permission issue"),
                (r"connection refused", "Network connectivity issue"),
                (r"address already in use", "Port conflict"),
                (r"killed", "Process killed"),
                (r"exit code [1-9]", "Non-zero exit code")
            ]
        }
    
    def collect_kernel_logs(self, hours: int = 24) -> Dict:
        """Collect kernel logs from various sources"""
        logs = {
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "entries": [],
            "issues": []
        }
        
        # Calculate time range
        since_time = datetime.now() - timedelta(hours=hours)
        
        # Try different log sources
        log_sources = [
            ("dmesg", ["dmesg", "-T"]),
            ("journalctl_kernel", ["journalctl", "-k", "--since", f"{hours} hours ago", "--no-pager"]),
            ("syslog", None),  # Will read file directly
            ("kern.log", None)  # Will read file directly
        ]
        
        for source_name, command in log_sources:
            try:
                if command:
                    # Command-based log collection
                    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logs["sources"][source_name] = {
                            "available": True,
                            "lines": len(result.stdout.split('\n')),
                            "command": ' '.join(command)
                        }
                        
                        # Parse log entries
                        for line in result.stdout.split('\n'):
                            if line.strip():
                                entry = self._parse_log_line(line, source_name)
                                if entry and entry.get("timestamp", datetime.min) >= since_time:
                                    logs["entries"].append(entry)
                    else:
                        logs["sources"][source_name] = {
                            "available": False,
                            "error": result.stderr or "Command failed"
                        }
                else:
                    # File-based log collection
                    log_files = []
                    if source_name == "syslog":
                        log_files = ["/var/log/syslog", "/var/log/messages"]
                    elif source_name == "kern.log":
                        log_files = ["/var/log/kern.log"]
                    
                    for log_file in log_files:
                        if os.path.exists(log_file):
                            try:
                                with open(log_file, 'r') as f:
                                    content = f.read()
                                    
                                logs["sources"][f"{source_name}_{log_file}"] = {
                                    "available": True,
                                    "lines": len(content.split('\n')),
                                    "file": log_file
                                }
                                
                                # Parse recent entries
                                for line in content.split('\n')[-1000:]:  # Last 1000 lines
                                    if line.strip():
                                        entry = self._parse_log_line(line, source_name)
                                        if entry and entry.get("timestamp", datetime.min) >= since_time:
                                            logs["entries"].append(entry)
                                break
                            except Exception as e:
                                logs["sources"][f"{source_name}_{log_file}"] = {
                                    "available": False,
                                    "error": str(e)
                                }
                        else:
                            logs["sources"][f"{source_name}_{log_file}"] = {
                                "available": False,
                                "error": "File not found"
                            }
            
            except Exception as e:
                logs["sources"][source_name] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Analyze collected logs for issues
        logs["issues"] = self._analyze_log_entries(logs["entries"], "kernel_errors")
        
        return logs
    
    def collect_docker_logs(self, hours: int = 24) -> Dict:
        """Collect Docker daemon and container logs"""
        logs = {
            "timestamp": datetime.now().isoformat(),
            "daemon_logs": {},
            "container_logs": {},
            "issues": []
        }
        
        # Collect Docker daemon logs
        daemon_sources = [
            ("journalctl_docker", ["journalctl", "-u", "docker", "--since", f"{hours} hours ago", "--no-pager"]),
            ("docker_log_file", None)  # Will check common locations
        ]
        
        for source_name, command in daemon_sources:
            try:
                if command:
                    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        logs["daemon_logs"][source_name] = {
                            "available": True,
                            "content": result.stdout,
                            "lines": len(result.stdout.split('\n'))
                        }
                    else:
                        logs["daemon_logs"][source_name] = {
                            "available": False,
                            "error": result.stderr or "Command failed"
                        }
                else:
                    # Check common Docker log file locations
                    docker_log_paths = [
                        "/var/log/docker.log",
                        "/var/log/upstart/docker.log",
                        "/var/lib/docker/containers/*/docker.log"
                    ]
                    
                    for log_path in docker_log_paths:
                        if "*" in log_path:
                            # Handle glob patterns
                            import glob
                            matching_files = glob.glob(log_path)
                            for file_path in matching_files[:5]:  # Limit to 5 files
                                try:
                                    with open(file_path, 'r') as f:
                                        content = f.read()
                                    logs["daemon_logs"][f"docker_log_{os.path.basename(file_path)}"] = {
                                        "available": True,
                                        "content": content[-10000:],  # Last 10KB
                                        "file": file_path
                                    }
                                except Exception as e:
                                    logs["daemon_logs"][f"docker_log_{os.path.basename(file_path)}"] = {
                                        "available": False,
                                        "error": str(e)
                                    }
                        else:
                            if os.path.exists(log_path):
                                try:
                                    with open(log_path, 'r') as f:
                                        content = f.read()
                                    logs["daemon_logs"][f"docker_log_{os.path.basename(log_path)}"] = {
                                        "available": True,
                                        "content": content[-10000:],  # Last 10KB
                                        "file": log_path
                                    }
                                except Exception as e:
                                    logs["daemon_logs"][f"docker_log_{os.path.basename(log_path)}"] = {
                                        "available": False,
                                        "error": str(e)
                                    }
            
            except Exception as e:
                logs["daemon_logs"][source_name] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Collect container logs
        try:
            result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                
                # Get logs for each container
                for container in containers[:10]:  # Limit to 10 containers
                    container_id = container["ID"]
                    container_name = container["Names"]
                    
                    try:
                        log_result = subprocess.run(
                            ["docker", "logs", "--since", f"{hours}h", "--tail", "500", container_id],
                            capture_output=True, text=True, timeout=15
                        )
                        
                        if log_result.returncode == 0:
                            logs["container_logs"][container_name] = {
                                "id": container_id[:12],
                                "status": container["Status"],
                                "logs": log_result.stdout + log_result.stderr,
                                "lines": len((log_result.stdout + log_result.stderr).split('\n'))
                            }
                        else:
                            logs["container_logs"][container_name] = {
                                "id": container_id[:12],
                                "error": "Failed to get logs"
                            }
                    
                    except Exception as e:
                        logs["container_logs"][container_name] = {
                            "id": container_id[:12],
                            "error": str(e)
                        }
        
        except Exception as e:
            logs["issues"].append(f"Failed to get container list: {e}")
        
        # Analyze Docker logs for issues
        all_docker_content = []
        for source_data in logs["daemon_logs"].values():
            if source_data.get("available") and "content" in source_data:
                all_docker_content.append(source_data["content"])
        
        for container_data in logs["container_logs"].values():
            if "logs" in container_data:
                all_docker_content.append(container_data["logs"])
        
        combined_content = '\n'.join(all_docker_content)
        logs["issues"].extend(self._analyze_log_content(combined_content, "docker_errors"))
        
        return logs
    
    def _parse_log_line(self, line: str, source: str) -> Optional[Dict]:
        """Parse a single log line into structured format"""
        if not line.strip():
            return None
        
        entry = {
            "source": source,
            "raw_line": line,
            "timestamp": None,
            "level": "INFO",
            "message": line,
            "component": "unknown"
        }
        
        # Try to extract timestamp
        timestamp_patterns = [
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',  # syslog format
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',  # ISO format
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',  # Standard format
            r'\[(\d+\.\d+)\]'  # dmesg format
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                timestamp_str = match.group(1)
                try:
                    if '.' in timestamp_str and timestamp_str.replace('.', '').isdigit():
                        # dmesg timestamp (seconds since boot)
                        entry["timestamp"] = datetime.now()  # Approximate
                    else:
                        # Try to parse various timestamp formats
                        for fmt in ['%b %d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                            try:
                                if fmt == '%b %d %H:%M:%S':
                                    # Add current year for syslog format
                                    timestamp_str = f"{datetime.now().year} {timestamp_str}"
                                    fmt = f"%Y {fmt}"
                                entry["timestamp"] = datetime.strptime(timestamp_str, fmt)
                                break
                            except ValueError:
                                continue
                except Exception:
                    pass
                break
        
        # Extract log level
        level_patterns = [
            (r'\b(EMERG|EMERGENCY)\b', "EMERGENCY"),
            (r'\b(ALERT)\b', "ALERT"),
            (r'\b(CRIT|CRITICAL)\b', "CRITICAL"),
            (r'\b(ERR|ERROR)\b', "ERROR"),
            (r'\b(WARN|WARNING)\b', "WARNING"),
            (r'\b(NOTICE)\b', "NOTICE"),
            (r'\b(INFO)\b', "INFO"),
            (r'\b(DEBUG)\b', "DEBUG")
        ]
        
        for pattern, level in level_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                entry["level"] = level
                break
        
        # Extract component
        component_patterns = [
            (r'kernel:', "kernel"),
            (r'dockerd:', "dockerd"),
            (r'containerd:', "containerd"),
            (r'runc:', "runc"),
            (r'systemd:', "systemd"),
            (r'NetworkManager:', "networkmanager")
        ]
        
        for pattern, component in component_patterns:
            if re.search(pattern, line):
                entry["component"] = component
                break
        
        return entry
    
    def _analyze_log_entries(self, entries: List[Dict], pattern_category: str) -> List[Dict]:
        """Analyze log entries for known issues"""
        issues = []
        patterns = self.log_patterns.get(pattern_category, [])
        
        for entry in entries:
            message = entry.get("message", "")
            for pattern, description in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    issues.append({
                        "timestamp": entry.get("timestamp", datetime.now()).isoformat() if entry.get("timestamp") else None,
                        "source": entry.get("source"),
                        "component": entry.get("component"),
                        "level": entry.get("level"),
                        "pattern": pattern,
                        "description": description,
                        "message": message.strip(),
                        "raw_line": entry.get("raw_line", "")
                    })
        
        return issues
    
    def _analyze_log_content(self, content: str, pattern_category: str) -> List[Dict]:
        """Analyze log content for known issues"""
        issues = []
        patterns = self.log_patterns.get(pattern_category, [])
        
        for line in content.split('\n'):
            if line.strip():
                for pattern, description in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "timestamp": datetime.now().isoformat(),
                            "pattern": pattern,
                            "description": description,
                            "message": line.strip()
                        })
        
        return issues
    
    def analyze_error_trends(self, logs: Dict) -> Dict:
        """Analyze error trends and patterns"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "error_frequency": {},
            "component_errors": defaultdict(int),
            "time_distribution": defaultdict(int),
            "critical_patterns": [],
            "recommendations": []
        }
        
        all_issues = []
        
        # Collect all issues from different log sources
        if "issues" in logs:
            all_issues.extend(logs["issues"])
        
        # Analyze kernel logs if present
        if "entries" in logs:
            kernel_issues = self._analyze_log_entries(logs["entries"], "kernel_errors")
            all_issues.extend(kernel_issues)
        
        if not all_issues:
            return analysis
        
        # Count error frequencies
        error_descriptions = [issue.get("description", "Unknown") for issue in all_issues]
        analysis["error_frequency"] = dict(Counter(error_descriptions))
        
        # Count errors by component
        for issue in all_issues:
            component = issue.get("component", "unknown")
            analysis["component_errors"][component] += 1
        
        # Analyze time distribution (by hour)
        for issue in all_issues:
            timestamp_str = issue.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    hour = timestamp.hour
                    analysis["time_distribution"][hour] += 1
                except Exception:
                    pass
        
        # Identify critical patterns
        critical_keywords = ["kernel bug", "segfault", "out of memory", "failed to start", "critical"]
        for issue in all_issues:
            message = issue.get("message", "").lower()
            if any(keyword in message for keyword in critical_keywords):
                analysis["critical_patterns"].append({
                    "timestamp": issue.get("timestamp"),
                    "description": issue.get("description"),
                    "message": issue.get("message")
                })
        
        # Generate recommendations based on patterns
        error_counts = analysis["error_frequency"]
        
        if "OOM Killer activated" in error_counts:
            analysis["recommendations"].append("System running out of memory - consider increasing memory or reducing container memory limits")
        
        if "Container start failure" in error_counts:
            analysis["recommendations"].append("Multiple container start failures - check container configurations and dependencies")
        
        if "Permission error" in error_counts:
            analysis["recommendations"].append("Permission issues detected - verify file/directory permissions and SELinux contexts")
        
        if "Network configuration error" in error_counts:
            analysis["recommendations"].append("Network issues detected - check Docker network configuration and iptables rules")
        
        if analysis["component_errors"]["kernel"] > 10:
            analysis["recommendations"].append("High kernel error count - consider kernel update or configuration review")
        
        if analysis["component_errors"]["dockerd"] > 5:
            analysis["recommendations"].append("Docker daemon errors detected - check daemon configuration and restart if needed")
        
        return analysis
    
    def generate_log_report(self, hours: int = 24) -> Dict:
        """Generate comprehensive log analysis report"""
        print(f"📋 Collecting logs from the last {hours} hours...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "collection_period_hours": hours,
            "summary": {
                "total_issues": 0,
                "critical_issues": 0,
                "kernel_issues": 0,
                "docker_issues": 0
            },
            "kernel_logs": self.collect_kernel_logs(hours),
            "docker_logs": self.collect_docker_logs(hours),
            "trend_analysis": {}
        }
        
        # Combine all logs for trend analysis
        combined_logs = {
            "issues": [],
            "entries": report["kernel_logs"].get("entries", [])
        }
        
        combined_logs["issues"].extend(report["kernel_logs"].get("issues", []))
        combined_logs["issues"].extend(report["docker_logs"].get("issues", []))
        
        report["trend_analysis"] = self.analyze_error_trends(combined_logs)
        
        # Update summary
        report["summary"]["total_issues"] = len(combined_logs["issues"])
        report["summary"]["kernel_issues"] = len(report["kernel_logs"].get("issues", []))
        report["summary"]["docker_issues"] = len(report["docker_logs"].get("issues", []))
        
        critical_count = len(report["trend_analysis"].get("critical_patterns", []))
        report["summary"]["critical_issues"] = critical_count
        
        return report
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save log analysis report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"log_analysis_{timestamp}.json"
        
        report_path = self.reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Log analysis report saved to {report_path}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
    
    def print_summary(self, report: Dict):
        """Print human-readable log analysis summary"""
        print("\n" + "="*60)
        print("📋 LOG ANALYSIS SUMMARY")
        print("="*60)
        
        summary = report["summary"]
        print(f"Collection Period: {report['collection_period_hours']} hours")
        print(f"Total Issues: {summary['total_issues']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Kernel Issues: {summary['kernel_issues']}")
        print(f"Docker Issues: {summary['docker_issues']}")
        
        # Kernel logs summary
        print(f"\n🐧 KERNEL LOGS")
        kernel_logs = report["kernel_logs"]
        available_sources = sum(1 for s in kernel_logs["sources"].values() if s.get("available"))
        total_sources = len(kernel_logs["sources"])
        print(f"Log Sources: {available_sources}/{total_sources} available")
        print(f"Log Entries: {len(kernel_logs.get('entries', []))}")
        
        # Docker logs summary
        print(f"\n🐳 DOCKER LOGS")
        docker_logs = report["docker_logs"]
        daemon_sources = sum(1 for s in docker_logs["daemon_logs"].values() if s.get("available"))
        print(f"Daemon Log Sources: {daemon_sources}")
        print(f"Container Logs: {len(docker_logs['container_logs'])}")
        
        # Error frequency
        print(f"\n📊 ERROR FREQUENCY")
        trend_analysis = report["trend_analysis"]
        error_freq = trend_analysis.get("error_frequency", {})
        
        if error_freq:
            sorted_errors = sorted(error_freq.items(), key=lambda x: x[1], reverse=True)
            for error, count in sorted_errors[:5]:  # Top 5 errors
                print(f"  • {error}: {count} occurrences")
        else:
            print("  No errors detected")
        
        # Component errors
        print(f"\n🔧 ERRORS BY COMPONENT")
        component_errors = trend_analysis.get("component_errors", {})
        if component_errors:
            for component, count in sorted(component_errors.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {component}: {count} errors")
        
        # Critical patterns
        critical_patterns = trend_analysis.get("critical_patterns", [])
        if critical_patterns:
            print(f"\n🚨 CRITICAL ISSUES ({len(critical_patterns)})")
            for pattern in critical_patterns[:3]:  # Show first 3
                timestamp = pattern.get("timestamp", "Unknown time")
                description = pattern.get("description", "Unknown issue")
                print(f"  • [{timestamp}] {description}")
        
        # Recommendations
        recommendations = trend_analysis.get("recommendations", [])
        if recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(recommendations)})")
            for rec in recommendations:
                print(f"  • {rec}")
        
        print("="*60)

def main():
    """Main log analysis function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Log Collection and Analysis Tool")
    parser.add_argument("--hours", "-t", type=int, default=24, help="Hours of logs to collect (default: 24)")
    parser.add_argument("--output", "-o", help="Output report file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode - minimal output")
    parser.add_argument("--type", choices=["kernel", "docker", "all"], default="all", 
                       help="Type of logs to collect")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    
    if args.type == "kernel":
        result = analyzer.collect_kernel_logs(args.hours)
        if not args.quiet:
            print(json.dumps(result, indent=2, default=str))
    elif args.type == "docker":
        result = analyzer.collect_docker_logs(args.hours)
        if not args.quiet:
            print(json.dumps(result, indent=2, default=str))
    else:
        # Full log analysis report
        report = analyzer.generate_log_report(args.hours)
        
        if not args.quiet:
            analyzer.print_summary(report)
        
        if args.output:
            analyzer.save_report(report, args.output)
        else:
            analyzer.save_report(report)

if __name__ == "__main__":
    main()