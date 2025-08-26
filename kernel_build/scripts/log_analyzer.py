#!/usr/bin/env python3
"""
Log Collection and Analysis Tools
Provides comprehensive log collection and analysis for kernel and Docker issues
"""

import os
import sys
import json
import subprocess
import re
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter

class LogAnalyzer:
    """Log collection and analysis utilities for kernel and Docker issues"""
    
    def __init__(self):
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        self.log_patterns = self._init_log_patterns()
        
    def _init_log_patterns(self) -> Dict:
        """Initialize log patterns for different issue types"""
        return {
            "kernel_errors": [
                r"kernel: .*error.*",
                r"kernel: .*panic.*",
                r"kernel: .*oops.*",
                r"kernel: .*bug.*",
                r"kernel: .*warning.*",
                r"kernel: .*failed.*",
                r"segfault at",
                r"general protection fault",
                r"unable to handle kernel",
                r"call trace:",
                r"rip:",
                r"code:"
            ],
            "docker_errors": [
                r"dockerd.*error.*",
                r"docker.*failed.*",
                r"containerd.*error.*",
                r"runc.*error.*",
                r"oci runtime error",
                r"container.*failed.*",
                r"image.*failed.*",
                r"network.*failed.*",
                r"storage.*failed.*",
                r"cgroup.*error.*",
                r"overlay.*error.*",
                r"bridge.*error.*"
            ],
            "network_errors": [
                r"network.*error.*",
                r"iptables.*error.*",
                r"bridge.*error.*",
                r"veth.*error.*",
                r"netlink.*error.*",
                r"routing.*error.*",
                r"dns.*error.*",
                r"connection.*failed.*",
                r"timeout.*network.*",
                r"no route to host"
            ],
            "storage_errors": [
                r"storage.*error.*",
                r"overlay.*error.*",
                r"mount.*failed.*",
                r"filesystem.*error.*",
                r"disk.*error.*",
                r"i/o error.*",
                r"read-only.*filesystem.*",
                r"no space left.*",
                r"permission denied.*",
                r"device.*busy.*"
            ],
            "cgroup_errors": [
                r"cgroup.*error.*",
                r"cgroup.*failed.*",
                r"systemd.*cgroup.*",
                r"memory.*cgroup.*",
                r"cpu.*cgroup.*",
                r"blkio.*cgroup.*",
                r"devices.*cgroup.*",
                r"freezer.*cgroup.*",
                r"net_cls.*cgroup.*",
                r"cpuset.*cgroup.*"
            ]
        }
    
    def collect_system_logs(self, hours: int = 24) -> Dict:
        """Collect system logs from various sources"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "collection_period_hours": hours,
            "sources": {},
            "total_entries": 0,
            "issues": []
        }
        
        since_time = datetime.now() - timedelta(hours=hours)
        since_str = since_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Collect from journalctl (systemd)
        try:
            result = subprocess.run([
                "journalctl", "--since", since_str, "--no-pager", "-o", "json"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                journal_entries = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            entry = json.loads(line)
                            journal_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
                
                status["sources"]["journalctl"] = {
                    "available": True,
                    "entries": len(journal_entries),
                    "data": journal_entries
                }
                status["total_entries"] += len(journal_entries)
            else:
                status["sources"]["journalctl"] = {
                    "available": False,
                    "error": result.stderr or "Command failed"
                }
        
        except Exception as e:
            status["sources"]["journalctl"] = {
                "available": False,
                "error": str(e)
            }
        
        # Collect from dmesg (kernel messages)
        try:
            result = subprocess.run(["dmesg", "-T"], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                dmesg_lines = result.stdout.strip().split('\n')
                # Filter by time if possible
                filtered_lines = []
                for line in dmesg_lines:
                    if line.strip():
                        filtered_lines.append(line)
                
                status["sources"]["dmesg"] = {
                    "available": True,
                    "entries": len(filtered_lines),
                    "data": filtered_lines
                }
                status["total_entries"] += len(filtered_lines)
            else:
                status["sources"]["dmesg"] = {
                    "available": False,
                    "error": result.stderr or "Command failed"
                }
        
        except Exception as e:
            status["sources"]["dmesg"] = {
                "available": False,
                "error": str(e)
            }
        
        # Collect Docker daemon logs
        try:
            # Try journalctl for Docker service
            result = subprocess.run([
                "journalctl", "-u", "docker", "--since", since_str, "--no-pager", "-o", "json"
            ], capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0:
                docker_entries = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            entry = json.loads(line)
                            docker_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
                
                status["sources"]["docker_service"] = {
                    "available": True,
                    "entries": len(docker_entries),
                    "data": docker_entries
                }
                status["total_entries"] += len(docker_entries)
            else:
                # Try Docker logs command
                docker_result = subprocess.run([
                    "docker", "system", "events", "--since", f"{hours}h", "--format", "json"
                ], capture_output=True, text=True, timeout=15)
                
                if docker_result.returncode == 0:
                    docker_events = []
                    for line in docker_result.stdout.strip().split('\n'):
                        if line:
                            try:
                                event = json.loads(line)
                                docker_events.append(event)
                            except json.JSONDecodeError:
                                continue
                    
                    status["sources"]["docker_events"] = {
                        "available": True,
                        "entries": len(docker_events),
                        "data": docker_events
                    }
                    status["total_entries"] += len(docker_events)
                else:
                    status["sources"]["docker_service"] = {
                        "available": False,
                        "error": "Docker service logs not available"
                    }
        
        except Exception as e:
            status["sources"]["docker_service"] = {
                "available": False,
                "error": str(e)
            }
        
        # Collect from traditional log files
        log_files = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/kern.log",
            "/var/log/daemon.log"
        ]
        
        for log_file in log_files:
            try:
                if os.path.exists(log_file):
                    # Read recent entries
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    # Filter by time (approximate)
                    recent_lines = lines[-10000:]  # Last 10k lines as approximation
                    
                    status["sources"][os.path.basename(log_file)] = {
                        "available": True,
                        "entries": len(recent_lines),
                        "path": log_file,
                        "data": recent_lines
                    }
                    status["total_entries"] += len(recent_lines)
                else:
                    status["sources"][os.path.basename(log_file)] = {
                        "available": False,
                        "error": "File not found"
                    }
            
            except Exception as e:
                status["sources"][os.path.basename(log_file)] = {
                    "available": False,
                    "error": str(e)
                }
        
        return status
    
    def analyze_logs_for_patterns(self, log_data: Dict) -> Dict:
        """Analyze collected logs for error patterns"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "pattern_matches": defaultdict(list),
            "error_summary": defaultdict(int),
            "timeline": [],
            "top_errors": [],
            "recommendations": []
        }
        
        all_log_entries = []
        
        # Process different log sources
        for source_name, source_data in log_data["sources"].items():
            if not source_data.get("available"):
                continue
            
            entries = source_data.get("data", [])
            
            for entry in entries:
                log_entry = {
                    "source": source_name,
                    "timestamp": None,
                    "message": "",
                    "raw": entry
                }
                
                # Extract message and timestamp based on source type
                if isinstance(entry, dict):
                    # JSON format (journalctl)
                    log_entry["message"] = entry.get("MESSAGE", "")
                    log_entry["timestamp"] = entry.get("__REALTIME_TIMESTAMP")
                    if log_entry["timestamp"]:
                        try:
                            # Convert microseconds to datetime
                            ts = int(log_entry["timestamp"]) / 1000000
                            log_entry["timestamp"] = datetime.fromtimestamp(ts)
                        except (ValueError, TypeError):
                            log_entry["timestamp"] = None
                elif isinstance(entry, str):
                    # String format (dmesg, log files)
                    log_entry["message"] = entry
                    # Try to extract timestamp from string
                    timestamp_match = re.search(r'\[(.*?)\]|\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', entry)
                    if timestamp_match:
                        try:
                            ts_str = timestamp_match.group(1) if timestamp_match.group(1) else timestamp_match.group(0)
                            # This is a simplified timestamp parsing
                            log_entry["timestamp"] = datetime.now()  # Placeholder
                        except:
                            pass
                
                all_log_entries.append(log_entry)
        
        # Analyze patterns
        for category, patterns in self.log_patterns.items():
            for entry in all_log_entries:
                message = entry["message"].lower()
                
                for pattern in patterns:
                    if re.search(pattern, message, re.IGNORECASE):
                        match_info = {
                            "timestamp": entry["timestamp"].isoformat() if entry["timestamp"] else "unknown",
                            "source": entry["source"],
                            "message": entry["message"][:200],  # Truncate long messages
                            "pattern": pattern
                        }
                        
                        analysis["pattern_matches"][category].append(match_info)
                        analysis["error_summary"][category] += 1
                        
                        # Add to timeline
                        if entry["timestamp"]:
                            analysis["timeline"].append({
                                "timestamp": entry["timestamp"].isoformat(),
                                "category": category,
                                "source": entry["source"],
                                "message": entry["message"][:100]
                            })
        
        # Sort timeline by timestamp
        analysis["timeline"].sort(key=lambda x: x["timestamp"])
        
        # Generate top errors
        error_counter = Counter()
        for category, matches in analysis["pattern_matches"].items():
            for match in matches:
                # Extract key error terms
                message = match["message"].lower()
                error_terms = re.findall(r'\b(?:error|failed|panic|oops|warning|timeout|denied)\b', message)
                for term in error_terms:
                    error_counter[f"{category}:{term}"] += 1
        
        analysis["top_errors"] = [
            {"error": error, "count": count}
            for error, count in error_counter.most_common(10)
        ]
        
        # Generate recommendations
        recommendations = []
        
        if analysis["error_summary"]["kernel_errors"] > 10:
            recommendations.append("High number of kernel errors detected - check hardware and drivers")
        
        if analysis["error_summary"]["docker_errors"] > 5:
            recommendations.append("Docker errors detected - check Docker daemon configuration")
        
        if analysis["error_summary"]["network_errors"] > 5:
            recommendations.append("Network errors detected - check network configuration and connectivity")
        
        if analysis["error_summary"]["storage_errors"] > 5:
            recommendations.append("Storage errors detected - check disk space and filesystem health")
        
        if analysis["error_summary"]["cgroup_errors"] > 3:
            recommendations.append("Cgroup errors detected - check cgroup configuration and systemd")
        
        analysis["recommendations"] = recommendations
        
        return dict(analysis)
    
    def collect_container_logs(self, container_name: Optional[str] = None, lines: int = 1000) -> Dict:
        """Collect logs from Docker containers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "containers": {},
            "total_log_lines": 0,
            "issues": []
        }
        
        try:
            # Get container list
            if container_name:
                containers = [{"Names": container_name, "ID": container_name}]
            else:
                result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode != 0:
                    status["issues"].append("Failed to get container list")
                    return status
                
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            # Collect logs from each container
            for container in containers:
                container_id = container["ID"]
                container_name = container["Names"]
                
                try:
                    # Get container logs
                    log_result = subprocess.run([
                        "docker", "logs", "--tail", str(lines), "--timestamps", container_id
                    ], capture_output=True, text=True, timeout=20)
                    
                    if log_result.returncode == 0:
                        log_lines = log_result.stdout.split('\n')
                        stderr_lines = log_result.stderr.split('\n') if log_result.stderr else []
                        
                        container_logs = {
                            "id": container_id[:12],
                            "status": container.get("Status", "unknown"),
                            "stdout_lines": len([l for l in log_lines if l.strip()]),
                            "stderr_lines": len([l for l in stderr_lines if l.strip()]),
                            "stdout": log_lines,
                            "stderr": stderr_lines,
                            "log_errors": [],
                            "log_warnings": []
                        }
                        
                        # Analyze container logs for errors
                        all_lines = log_lines + stderr_lines
                        for line in all_lines:
                            line_lower = line.lower()
                            if any(term in line_lower for term in ["error", "failed", "exception", "panic"]):
                                container_logs["log_errors"].append(line.strip())
                            elif any(term in line_lower for term in ["warning", "warn", "deprecated"]):
                                container_logs["log_warnings"].append(line.strip())
                        
                        status["containers"][container_name] = container_logs
                        status["total_log_lines"] += len(all_lines)
                    
                    else:
                        status["containers"][container_name] = {
                            "id": container_id[:12],
                            "error": f"Failed to get logs: {log_result.stderr}"
                        }
                
                except Exception as e:
                    status["containers"][container_name] = {
                        "id": container_id[:12],
                        "error": str(e)
                    }
        
        except Exception as e:
            status["issues"].append(f"Container log collection failed: {e}")
        
        return status
    
    def generate_diagnostic_report(self, hours: int = 24) -> Dict:
        """Generate comprehensive diagnostic report"""
        print("🔍 Collecting system logs...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "collection_period_hours": hours,
            "summary": {
                "total_log_entries": 0,
                "total_errors": 0,
                "total_warnings": 0,
                "critical_issues": 0,
                "containers_analyzed": 0
            },
            "system_logs": self.collect_system_logs(hours),
            "container_logs": self.collect_container_logs(),
            "log_analysis": {},
            "recommendations": []
        }
        
        print("🔍 Analyzing log patterns...")
        
        # Analyze system logs
        report["log_analysis"] = self.analyze_logs_for_patterns(report["system_logs"])
        
        # Update summary
        report["summary"]["total_log_entries"] = report["system_logs"]["total_entries"]
        report["summary"]["total_errors"] = sum(report["log_analysis"]["error_summary"].values())
        report["summary"]["containers_analyzed"] = len(report["container_logs"]["containers"])
        
        # Count warnings and critical issues
        warning_count = 0
        critical_count = 0
        
        for category, count in report["log_analysis"]["error_summary"].items():
            if "kernel" in category or "panic" in category:
                critical_count += count
            else:
                warning_count += count
        
        report["summary"]["total_warnings"] = warning_count
        report["summary"]["critical_issues"] = critical_count
        
        # Combine recommendations
        report["recommendations"] = report["log_analysis"]["recommendations"]
        
        # Add container-specific recommendations
        container_errors = 0
        for container_name, container_data in report["container_logs"]["containers"].items():
            if isinstance(container_data, dict) and "log_errors" in container_data:
                container_errors += len(container_data["log_errors"])
        
        if container_errors > 10:
            report["recommendations"].append("Multiple container errors detected - review container configurations")
        
        return report
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save diagnostic report to file"""
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
        print(f"Total Log Entries: {summary['total_log_entries']:,}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Containers Analyzed: {summary['containers_analyzed']}")
        
        # Error breakdown
        print(f"\n📊 ERROR BREAKDOWN")
        error_summary = report["log_analysis"]["error_summary"]
        if error_summary:
            for category, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True):
                print(f"  {category.replace('_', ' ').title()}: {count}")
        else:
            print("  No errors detected")
        
        # Top errors
        print(f"\n🔥 TOP ERRORS")
        top_errors = report["log_analysis"]["top_errors"]
        if top_errors:
            for error_info in top_errors[:5]:
                print(f"  • {error_info['error']}: {error_info['count']} occurrences")
        else:
            print("  No recurring errors found")
        
        # Container issues
        print(f"\n🐳 CONTAINER LOG ISSUES")
        containers = report["container_logs"]["containers"]
        container_issues = 0
        
        for container_name, container_data in containers.items():
            if isinstance(container_data, dict):
                errors = len(container_data.get("log_errors", []))
                warnings = len(container_data.get("log_warnings", []))
                if errors > 0 or warnings > 0:
                    print(f"  • {container_name}: {errors} errors, {warnings} warnings")
                    container_issues += 1
        
        if container_issues == 0:
            print("  No container log issues detected")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        recommendations = report["recommendations"]
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        else:
            print("  No specific recommendations - system appears healthy")
        
        print("\n" + "="*60)

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Log Analysis and Collection Tool")
    parser.add_argument("--hours", type=int, default=24, help="Hours of logs to collect (default: 24)")
    parser.add_argument("--container", type=str, help="Specific container to analyze")
    parser.add_argument("--output", type=str, help="Output filename for report")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    
    if args.container:
        print(f"🔍 Analyzing logs for container: {args.container}")
        container_logs = analyzer.collect_container_logs(args.container)
        
        if not args.quiet:
            print(f"\nContainer Log Summary:")
            for name, data in container_logs["containers"].items():
                if isinstance(data, dict) and "log_errors" in data:
                    print(f"  {name}: {len(data['log_errors'])} errors, {len(data['log_warnings'])} warnings")
    else:
        print(f"🔍 Generating comprehensive diagnostic report...")
        report = analyzer.generate_diagnostic_report(args.hours)
        
        if not args.quiet:
            analyzer.print_summary(report)
        
        analyzer.save_report(report, args.output)

if __name__ == "__main__":
    main()