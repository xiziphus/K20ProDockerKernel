#!/usr/bin/env python3
"""
Monitoring Dashboard
Unified dashboard for system status, Docker health, and container diagnostics
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Import our monitoring modules
try:
    from system_monitor import SystemMonitor
    from docker_health_monitor import DockerHealthMonitor
    from container_diagnostics import ContainerDiagnostics
except ImportError:
    # Handle case where modules are in same directory
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from system_monitor import SystemMonitor
    from docker_health_monitor import DockerHealthMonitor
    from container_diagnostics import ContainerDiagnostics

class MonitoringDashboard:
    """Unified monitoring dashboard"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.system_monitor = SystemMonitor(config_path)
        self.docker_monitor = DockerHealthMonitor(config_path)
        self.diagnostics = ContainerDiagnostics()
        self.dashboard_dir = Path("monitoring_dashboard")
        self.dashboard_dir.mkdir(exist_ok=True)
        
    def generate_unified_report(self) -> Dict:
        """Generate unified monitoring report"""
        print("📊 Generating unified monitoring report...")
        
        # Get all monitoring data
        system_health = self.system_monitor.generate_health_report()
        docker_daemon = self.docker_monitor.check_daemon_status()
        docker_containers = self.docker_monitor.check_container_health()
        docker_resources = self.docker_monitor.check_docker_resources()
        container_diagnostics = self.diagnostics.generate_diagnostic_report()
        
        # Create unified report
        report = {
            "timestamp": datetime.now().isoformat(),
            "dashboard_version": "1.0.0",
            "summary": {
                "overall_status": "unknown",
                "system_status": system_health["summary"]["overall_status"],
                "docker_status": "healthy" if docker_daemon["daemon_running"] else "critical",
                "container_status": "healthy" if docker_containers["failed_containers"] == 0 else "warning",
                "total_issues": 0,
                "total_containers": docker_containers.get("total_containers", 0),
                "running_containers": docker_containers.get("running_containers", 0),
                "failed_containers": docker_containers.get("failed_containers", 0)
            },
            "system_health": system_health,
            "docker_daemon": docker_daemon,
            "docker_containers": docker_containers,
            "docker_resources": docker_resources,
            "container_diagnostics": container_diagnostics,
            "alerts": [],
            "recommendations": []
        }
        
        # Calculate overall status
        status_priorities = {"critical": 3, "warning": 2, "healthy": 1, "unknown": 0}
        statuses = [
            report["summary"]["system_status"],
            report["summary"]["docker_status"],
            report["summary"]["container_status"]
        ]
        
        highest_priority = max(status_priorities.get(s, 0) for s in statuses)
        for status, priority in status_priorities.items():
            if priority == highest_priority:
                report["summary"]["overall_status"] = status
                break
        
        # Collect all issues
        all_issues = []
        for section in ["system_health", "docker_daemon", "docker_containers", "docker_resources"]:
            if section in report:
                section_issues = report[section].get("issues", [])
                all_issues.extend([(section, issue) for issue in section_issues])
        
        # Add container diagnostic issues
        diag_issues = container_diagnostics.get("kernel_features", {}).get("issues", [])
        diag_issues.extend(container_diagnostics.get("container_failures", {}).get("issues", []))
        diag_issues.extend(container_diagnostics.get("storage_issues", {}).get("issues", []))
        all_issues.extend([("diagnostics", issue) for issue in diag_issues])
        
        report["summary"]["total_issues"] = len(all_issues)
        
        # Generate alerts for critical issues
        critical_keywords = ["not found", "not available", "failed", "error", "critical", "dead", "killed"]
        for section, issue in all_issues:
            if any(keyword in issue.lower() for keyword in critical_keywords):
                alert = {
                    "timestamp": datetime.now().isoformat(),
                    "severity": "critical",
                    "source": section,
                    "message": issue,
                    "type": "system_issue"
                }
                report["alerts"].append(alert)
        
        # Collect recommendations
        all_recommendations = []
        for section in ["system_health", "docker_containers", "docker_resources"]:
            if section in report:
                recs = report[section].get("recommendations", [])
                all_recommendations.extend(recs)
        
        # Add diagnostic recommendations
        diag_recs = container_diagnostics.get("kernel_features", {}).get("recommendations", [])
        diag_recs.extend(container_diagnostics.get("container_failures", {}).get("recommendations", []))
        diag_recs.extend(container_diagnostics.get("storage_issues", {}).get("recommendations", []))
        all_recommendations.extend(diag_recs)
        
        report["recommendations"] = list(set(all_recommendations))
        
        return report
    
    def print_dashboard(self, report: Dict):
        """Print interactive dashboard"""
        # Clear screen (works on most terminals)
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("╔" + "="*78 + "╗")
        print("║" + " "*20 + "🚀 DOCKER KERNEL MONITORING DASHBOARD" + " "*19 + "║")
        print("╚" + "="*78 + "╝")
        
        timestamp = datetime.fromisoformat(report["timestamp"])
        print(f"📅 Last Updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Overall Status
        summary = report["summary"]
        status_icons = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "❌",
            "unknown": "❓"
        }
        
        overall_icon = status_icons.get(summary["overall_status"], "❓")
        print(f"\n🎯 Overall Status: {overall_icon} {summary['overall_status'].upper()}")
        
        # Status Grid
        print(f"\n┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐")
        print(f"│ System Health   │ Docker Daemon   │ Containers      │ Total Issues    │")
        print(f"├─────────────────┼─────────────────┼─────────────────┼─────────────────┤")
        
        system_icon = status_icons.get(summary["system_status"], "❓")
        docker_icon = status_icons.get(summary["docker_status"], "❓")
        container_icon = status_icons.get(summary["container_status"], "❓")
        
        print(f"│ {system_icon} {summary['system_status']:<12} │ {docker_icon} {summary['docker_status']:<12} │ {container_icon} {summary['container_status']:<12} │ {summary['total_issues']:<15} │")
        print(f"└─────────────────┴─────────────────┴─────────────────┴─────────────────┘")
        
        # Container Summary
        print(f"\n🐳 Container Summary:")
        print(f"   Total: {summary['total_containers']} | Running: {summary['running_containers']} | Failed: {summary['failed_containers']}")
        
        # System Resources
        system_resources = report["system_health"].get("system_resources", {})
        if "disk_usage" in system_resources:
            disk = system_resources["disk_usage"]
            disk_bar = self._create_progress_bar(disk.get("usage_percent", 0), 50)
            print(f"\n💾 Disk Usage: {disk.get('usage_percent', 0):.1f}% {disk_bar}")
            print(f"   Free: {disk.get('free_gb', 0):.1f}GB / Total: {disk.get('total_gb', 0):.1f}GB")
        
        if "memory_info" in system_resources:
            memory = system_resources["memory_info"]
            mem_bar = self._create_progress_bar(memory.get("usage_percent", 0), 50)
            print(f"\n🧠 Memory Usage: {memory.get('usage_percent', 0):.1f}% {mem_bar}")
            print(f"   Available: {memory.get('available_gb', 0):.1f}GB / Total: {memory.get('total_gb', 0):.1f}GB")
        
        # Docker Daemon Info
        docker_daemon = report["docker_daemon"]
        if docker_daemon["daemon_running"]:
            daemon_info = docker_daemon.get("daemon_info", {})
            print(f"\n🐋 Docker Daemon:")
            print(f"   Version: {docker_daemon.get('daemon_version', 'Unknown')}")
            print(f"   Response Time: {docker_daemon.get('response_time', 0):.2f}s")
            print(f"   Storage Driver: {daemon_info.get('storage_driver', 'Unknown')}")
        else:
            print(f"\n🐋 Docker Daemon: ❌ Not Running")
        
        # Recent Alerts
        alerts = report.get("alerts", [])
        if alerts:
            print(f"\n🚨 Recent Alerts ({len(alerts)}):")
            for alert in alerts[-5:]:  # Show last 5 alerts
                severity_icon = "🔴" if alert["severity"] == "critical" else "🟡"
                alert_time = datetime.fromisoformat(alert["timestamp"])
                time_str = alert_time.strftime("%H:%M:%S")
                print(f"   {severity_icon} [{time_str}] {alert['message'][:60]}...")
        
        # Top Recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Top Recommendations ({len(recommendations)}):")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"   {i}. {rec[:70]}...")
        
        # Build Environment Status
        build_env = report["system_health"].get("build_environment", {})
        tools = build_env.get("tools", {})
        
        print(f"\n🔧 Build Environment:")
        essential_tools = ["python", "python3", "make", "gcc", "cross_compiler"]
        tool_status = []
        for tool in essential_tools:
            if tool in tools:
                status = "✅" if tools[tool]["available"] else "❌"
                tool_status.append(f"{tool}:{status}")
        print(f"   {' | '.join(tool_status)}")
        
        # Kernel Features
        kernel_features = report["container_diagnostics"].get("kernel_features", {})
        required_features = kernel_features.get("required_features", {})
        if required_features:
            enabled_count = sum(1 for f in required_features.values() if f.get("enabled") == True)
            total_count = len(required_features)
            feature_bar = self._create_progress_bar((enabled_count / total_count) * 100, 30)
            print(f"\n🐧 Kernel Features: {enabled_count}/{total_count} {feature_bar}")
        
        # Footer
        print(f"\n" + "─"*80)
        print(f"📊 Dashboard v{report.get('dashboard_version', '1.0.0')} | Press Ctrl+C to exit | Refresh: 30s")
        print(f"📁 Reports saved to: {self.dashboard_dir}")
    
    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a text progress bar"""
        filled = int((percentage / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def save_dashboard_report(self, report: Dict, filename: Optional[str] = None):
        """Save dashboard report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dashboard_report_{timestamp}.json"
        
        report_path = self.dashboard_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Dashboard report saved to {report_path}")
        except Exception as e:
            print(f"❌ Failed to save dashboard report: {e}")
    
    def export_html_dashboard(self, report: Dict, filename: Optional[str] = None):
        """Export dashboard as HTML file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dashboard_{timestamp}.html"
        
        html_path = self.dashboard_dir / filename
        
        # Generate HTML content
        html_content = self._generate_html_dashboard(report)
        
        try:
            with open(html_path, 'w') as f:
                f.write(html_content)
            print(f"✅ HTML dashboard exported to {html_path}")
        except Exception as e:
            print(f"❌ Failed to export HTML dashboard: {e}")
    
    def _generate_html_dashboard(self, report: Dict) -> str:
        """Generate HTML dashboard content"""
        summary = report["summary"]
        timestamp = datetime.fromisoformat(report["timestamp"])
        
        # Status colors
        status_colors = {
            "healthy": "#28a745",
            "warning": "#ffc107", 
            "critical": "#dc3545",
            "unknown": "#6c757d"
        }
        
        overall_color = status_colors.get(summary["overall_status"], "#6c757d")
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Kernel Monitoring Dashboard</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }}
        .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .status-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .status-indicator {{ width: 20px; height: 20px; border-radius: 50%; display: inline-block; margin-right: 10px; }}
        .healthy {{ background-color: #28a745; }}
        .warning {{ background-color: #ffc107; }}
        .critical {{ background-color: #dc3545; }}
        .unknown {{ background-color: #6c757d; }}
        .progress-bar {{ width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #28a745, #ffc107, #dc3545); transition: width 0.3s; }}
        .alert {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        .recommendation {{ background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        .metric {{ display: flex; justify-content: space-between; margin: 10px 0; }}
        .timestamp {{ color: #6c757d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Docker Kernel Monitoring Dashboard</h1>
            <p class="timestamp">Last Updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>Overall Status</h3>
                <div style="font-size: 24px; color: {overall_color};">
                    <span class="status-indicator {summary['overall_status']}"></span>
                    {summary['overall_status'].upper()}
                </div>
            </div>
            
            <div class="status-card">
                <h3>System Health</h3>
                <div class="metric">
                    <span>Status:</span>
                    <span><span class="status-indicator {summary['system_status']}"></span>{summary['system_status']}</span>
                </div>
                <div class="metric">
                    <span>Total Issues:</span>
                    <span>{summary['total_issues']}</span>
                </div>
            </div>
            
            <div class="status-card">
                <h3>Docker Status</h3>
                <div class="metric">
                    <span>Daemon:</span>
                    <span><span class="status-indicator {summary['docker_status']}"></span>{summary['docker_status']}</span>
                </div>
                <div class="metric">
                    <span>Containers:</span>
                    <span>{summary['running_containers']}/{summary['total_containers']} running</span>
                </div>
            </div>
            
            <div class="status-card">
                <h3>Container Health</h3>
                <div class="metric">
                    <span>Status:</span>
                    <span><span class="status-indicator {summary['container_status']}"></span>{summary['container_status']}</span>
                </div>
                <div class="metric">
                    <span>Failed:</span>
                    <span>{summary['failed_containers']}</span>
                </div>
            </div>
        </div>
"""
        
        # Add system resources
        system_resources = report["system_health"].get("system_resources", {})
        if "disk_usage" in system_resources or "memory_info" in system_resources:
            html += '<div class="status-grid">'
            
            if "disk_usage" in system_resources:
                disk = system_resources["disk_usage"]
                disk_percent = disk.get("usage_percent", 0)
                html += f'''
                <div class="status-card">
                    <h3>💾 Disk Usage</h3>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {disk_percent}%;"></div>
                    </div>
                    <div class="metric">
                        <span>Used:</span>
                        <span>{disk_percent:.1f}%</span>
                    </div>
                    <div class="metric">
                        <span>Free:</span>
                        <span>{disk.get("free_gb", 0):.1f}GB</span>
                    </div>
                </div>
                '''
            
            if "memory_info" in system_resources:
                memory = system_resources["memory_info"]
                mem_percent = memory.get("usage_percent", 0)
                html += f'''
                <div class="status-card">
                    <h3>🧠 Memory Usage</h3>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {mem_percent}%;"></div>
                    </div>
                    <div class="metric">
                        <span>Used:</span>
                        <span>{mem_percent:.1f}%</span>
                    </div>
                    <div class="metric">
                        <span>Available:</span>
                        <span>{memory.get("available_gb", 0):.1f}GB</span>
                    </div>
                </div>
                '''
            
            html += '</div>'
        
        # Add alerts
        alerts = report.get("alerts", [])
        if alerts:
            html += '<div class="status-card"><h3>🚨 Recent Alerts</h3>'
            for alert in alerts[-10:]:  # Show last 10 alerts
                alert_time = datetime.fromisoformat(alert["timestamp"])
                html += f'<div class="alert">[{alert_time.strftime("%H:%M:%S")}] {alert["message"]}</div>'
            html += '</div>'
        
        # Add recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            html += '<div class="status-card"><h3>💡 Recommendations</h3>'
            for i, rec in enumerate(recommendations[:10], 1):
                html += f'<div class="recommendation">{i}. {rec}</div>'
            html += '</div>'
        
        html += '''
    </div>
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function() {
            location.reload();
        }, 300000);
    </script>
</body>
</html>
'''
        
        return html
    
    def run_dashboard(self, refresh_interval: int = 30, export_html: bool = False):
        """Run interactive dashboard with auto-refresh"""
        print("🚀 Starting monitoring dashboard...")
        print(f"📊 Refresh interval: {refresh_interval} seconds")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                report = self.generate_unified_report()
                self.print_dashboard(report)
                
                # Save report
                self.save_dashboard_report(report)
                
                # Export HTML if requested
                if export_html:
                    self.export_html_dashboard(report)
                
                # Wait for next refresh
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n👋 Dashboard stopped")
        except Exception as e:
            print(f"\n❌ Dashboard error: {e}")

def main():
    """Main dashboard function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Docker Kernel Monitoring Dashboard")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--refresh", "-r", type=int, default=30, help="Refresh interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--html", action="store_true", help="Export HTML dashboard")
    parser.add_argument("--output", "-o", help="Output report file")
    
    args = parser.parse_args()
    
    dashboard = MonitoringDashboard(args.config)
    
    if args.once:
        report = dashboard.generate_unified_report()
        dashboard.print_dashboard(report)
        
        if args.output:
            dashboard.save_dashboard_report(report, args.output)
        else:
            dashboard.save_dashboard_report(report)
        
        if args.html:
            dashboard.export_html_dashboard(report)
    else:
        dashboard.run_dashboard(args.refresh, args.html)

if __name__ == "__main__":
    main()