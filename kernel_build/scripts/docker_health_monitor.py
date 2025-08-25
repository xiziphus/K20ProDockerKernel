#!/usr/bin/env python3
"""
Docker Daemon Health Monitor
Specialized monitoring for Docker daemon status and container runtime health
"""

import os
import sys
import json
import subprocess
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

class DockerHealthMonitor:
    """Docker daemon and container health monitoring"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "kernel_build/config/deployment_config.json"
        self.config = self._load_config()
        self.log_file = Path("docker_health.log")
        self.alert_file = Path("docker_alerts.json")
        self.running = False
        
    def _load_config(self) -> Dict:
        """Load monitoring configuration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("docker_monitoring", {})
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
        
        return {
            "check_interval": 30,
            "restart_attempts": 3,
            "restart_delay": 10,
            "alert_thresholds": {
                "container_restart_count": 5,
                "daemon_downtime": 300,  # 5 minutes
                "memory_usage": 80,
                "failed_containers": 3
            },
            "auto_restart": True,
            "log_retention_hours": 24
        }
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        print(log_entry)
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"Failed to write to log file: {e}")
    
    def _save_alert(self, alert: Dict):
        """Save alert to alerts file"""
        try:
            alerts = []
            if self.alert_file.exists():
                with open(self.alert_file, 'r') as f:
                    alerts = json.load(f)
            
            alerts.append(alert)
            
            # Keep only recent alerts (last 24 hours)
            cutoff = datetime.now() - timedelta(hours=self.config.get("log_retention_hours", 24))
            alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) > cutoff]
            
            with open(self.alert_file, 'w') as f:
                json.dump(alerts, f, indent=2)
                
        except Exception as e:
            self._log(f"Failed to save alert: {e}", "ERROR")
    
    def check_daemon_status(self) -> Dict:
        """Check Docker daemon status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "daemon_running": False,
            "daemon_version": None,
            "daemon_info": {},
            "response_time": None,
            "issues": []
        }
        
        start_time = time.time()
        
        try:
            # Check daemon with timeout
            result = subprocess.run(
                ["docker", "version", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            response_time = time.time() - start_time
            status["response_time"] = round(response_time, 2)
            
            if result.returncode == 0:
                try:
                    version_info = json.loads(result.stdout)
                    status["daemon_running"] = True
                    status["daemon_version"] = version_info.get("Server", {}).get("Version")
                    
                    # Get detailed daemon info
                    info_result = subprocess.run(
                        ["docker", "system", "info", "--format", "json"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if info_result.returncode == 0:
                        daemon_info = json.loads(info_result.stdout)
                        status["daemon_info"] = {
                            "containers": daemon_info.get("Containers", 0),
                            "containers_running": daemon_info.get("ContainersRunning", 0),
                            "containers_paused": daemon_info.get("ContainersPaused", 0),
                            "containers_stopped": daemon_info.get("ContainersStopped", 0),
                            "images": daemon_info.get("Images", 0),
                            "storage_driver": daemon_info.get("Driver"),
                            "kernel_version": daemon_info.get("KernelVersion"),
                            "operating_system": daemon_info.get("OperatingSystem"),
                            "total_memory": daemon_info.get("MemTotal", 0),
                            "ncpu": daemon_info.get("NCPU", 0)
                        }
                        
                        # Check for warnings in daemon info
                        warnings = daemon_info.get("Warnings", [])
                        if warnings:
                            status["issues"].extend([f"Daemon warning: {w}" for w in warnings])
                    
                except json.JSONDecodeError as e:
                    status["issues"].append(f"Failed to parse daemon info: {e}")
                    
            else:
                status["issues"].append(f"Docker daemon not responding: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            status["issues"].append("Docker daemon response timeout")
        except Exception as e:
            status["issues"].append(f"Docker daemon check failed: {e}")
        
        # Check response time threshold
        if status["response_time"] and status["response_time"] > 5.0:
            status["issues"].append(f"Slow daemon response: {status['response_time']}s")
        
        return status
    
    def check_container_health(self) -> Dict:
        """Check health of all containers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "total_containers": 0,
            "running_containers": 0,
            "failed_containers": 0,
            "containers": [],
            "issues": []
        }
        
        try:
            # Get all containers
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            container = json.loads(line)
                            
                            # Get detailed container info
                            inspect_result = subprocess.run(
                                ["docker", "inspect", container["ID"]],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            
                            container_detail = {
                                "id": container["ID"][:12],
                                "name": container["Names"],
                                "image": container["Image"],
                                "status": container["Status"],
                                "state": container["State"],
                                "created": container["CreatedAt"],
                                "health": "unknown",
                                "restart_count": 0,
                                "issues": []
                            }
                            
                            if inspect_result.returncode == 0:
                                try:
                                    inspect_data = json.loads(inspect_result.stdout)[0]
                                    state = inspect_data.get("State", {})
                                    
                                    container_detail["health"] = state.get("Health", {}).get("Status", "none")
                                    container_detail["restart_count"] = state.get("RestartCount", 0)
                                    
                                    # Check for issues
                                    if state.get("Dead"):
                                        container_detail["issues"].append("Container is dead")
                                    if state.get("OOMKilled"):
                                        container_detail["issues"].append("Killed by OOM")
                                    if state.get("ExitCode", 0) != 0 and not state.get("Running"):
                                        container_detail["issues"].append(f"Exited with code {state.get('ExitCode')}")
                                    
                                    # Check restart count threshold
                                    restart_threshold = self.config.get("alert_thresholds", {}).get("container_restart_count", 5)
                                    if container_detail["restart_count"] > restart_threshold:
                                        container_detail["issues"].append(f"High restart count: {container_detail['restart_count']}")
                                    
                                except json.JSONDecodeError:
                                    container_detail["issues"].append("Failed to parse container details")
                            
                            containers.append(container_detail)
                            
                        except json.JSONDecodeError:
                            continue
                
                status["containers"] = containers
                status["total_containers"] = len(containers)
                status["running_containers"] = len([c for c in containers if c["state"] == "running"])
                status["failed_containers"] = len([c for c in containers if c["issues"]])
                
                # Check failed container threshold
                failed_threshold = self.config.get("alert_thresholds", {}).get("failed_containers", 3)
                if status["failed_containers"] > failed_threshold:
                    status["issues"].append(f"Too many failed containers: {status['failed_containers']}")
                
            else:
                status["issues"].append(f"Failed to get container list: {result.stderr}")
                
        except Exception as e:
            status["issues"].append(f"Container health check failed: {e}")
        
        return status
    
    def check_docker_resources(self) -> Dict:
        """Check Docker resource usage"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "system_usage": {},
            "container_usage": [],
            "issues": []
        }
        
        try:
            # Get system-wide Docker stats
            result = subprocess.run(
                ["docker", "system", "df", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                try:
                    df_data = json.loads(result.stdout)
                    
                    # Parse system usage
                    for item in df_data:
                        item_type = item.get("Type", "").lower()
                        if item_type in ["images", "containers", "local volumes", "build cache"]:
                            status["system_usage"][item_type] = {
                                "total": item.get("Total", 0),
                                "active": item.get("Active", 0),
                                "size": item.get("Size", "0B"),
                                "reclaimable": item.get("Reclaimable", "0B")
                            }
                    
                except json.JSONDecodeError:
                    status["issues"].append("Failed to parse system usage data")
            
            # Get container resource usage
            stats_result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if stats_result.returncode == 0:
                container_stats = []
                for line in stats_result.stdout.strip().split('\n'):
                    if line:
                        try:
                            stat = json.loads(line)
                            
                            # Parse CPU and memory percentages
                            cpu_percent = float(stat.get("CPUPerc", "0%").rstrip('%'))
                            mem_percent = float(stat.get("MemPerc", "0%").rstrip('%'))
                            
                            container_stat = {
                                "id": stat.get("ID", "")[:12],
                                "name": stat.get("Name", ""),
                                "cpu_percent": cpu_percent,
                                "memory_usage": stat.get("MemUsage", ""),
                                "memory_percent": mem_percent,
                                "network_io": stat.get("NetIO", ""),
                                "block_io": stat.get("BlockIO", ""),
                                "pids": stat.get("PIDs", "")
                            }
                            
                            # Check memory threshold
                            mem_threshold = self.config.get("alert_thresholds", {}).get("memory_usage", 80)
                            if mem_percent > mem_threshold:
                                status["issues"].append(
                                    f"Container {container_stat['name']} high memory usage: {mem_percent:.1f}%"
                                )
                            
                            container_stats.append(container_stat)
                            
                        except (json.JSONDecodeError, ValueError):
                            continue
                
                status["container_usage"] = container_stats
            
        except Exception as e:
            status["issues"].append(f"Resource usage check failed: {e}")
        
        return status
    
    def attempt_daemon_restart(self) -> bool:
        """Attempt to restart Docker daemon"""
        self._log("Attempting to restart Docker daemon", "WARNING")
        
        try:
            # Try different restart methods based on system
            restart_commands = [
                ["sudo", "systemctl", "restart", "docker"],  # systemd
                ["sudo", "service", "docker", "restart"],    # sysv
                ["sudo", "launchctl", "kickstart", "-k", "system/com.docker.dockerd"]  # macOS
            ]
            
            for cmd in restart_commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        self._log(f"Docker daemon restart successful with: {' '.join(cmd)}")
                        
                        # Wait for daemon to be ready
                        for i in range(10):
                            time.sleep(2)
                            daemon_status = self.check_daemon_status()
                            if daemon_status["daemon_running"]:
                                self._log("Docker daemon is now running")
                                return True
                        
                        self._log("Docker daemon restart command succeeded but daemon not responding", "WARNING")
                        return False
                        
                except subprocess.TimeoutExpired:
                    self._log(f"Restart command timed out: {' '.join(cmd)}", "WARNING")
                except FileNotFoundError:
                    continue  # Try next command
                except Exception as e:
                    self._log(f"Restart command failed: {e}", "WARNING")
            
            self._log("All restart methods failed", "ERROR")
            return False
            
        except Exception as e:
            self._log(f"Daemon restart attempt failed: {e}", "ERROR")
            return False
    
    def generate_alert(self, alert_type: str, message: str, severity: str = "warning", data: Dict = None):
        """Generate and save alert"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "type": alert_type,
            "severity": severity,
            "message": message,
            "data": data or {}
        }
        
        self._log(f"ALERT [{severity.upper()}] {alert_type}: {message}", "ALERT")
        self._save_alert(alert)
        
        return alert
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self._log("Starting Docker health monitoring")
        self.running = True
        
        check_interval = self.config.get("check_interval", 30)
        restart_attempts = 0
        max_restart_attempts = self.config.get("restart_attempts", 3)
        last_daemon_check = None
        daemon_downtime_start = None
        
        try:
            while self.running:
                # Check daemon status
                daemon_status = self.check_daemon_status()
                
                if daemon_status["daemon_running"]:
                    if daemon_downtime_start:
                        downtime = (datetime.now() - daemon_downtime_start).total_seconds()
                        self._log(f"Docker daemon recovered after {downtime:.1f}s downtime")
                        daemon_downtime_start = None
                        restart_attempts = 0
                    
                    # Check container health
                    container_status = self.check_container_health()
                    if container_status["issues"]:
                        for issue in container_status["issues"]:
                            self.generate_alert("container_health", issue, "warning", container_status)
                    
                    # Check resource usage
                    resource_status = self.check_docker_resources()
                    if resource_status["issues"]:
                        for issue in resource_status["issues"]:
                            self.generate_alert("resource_usage", issue, "warning", resource_status)
                    
                    self._log(f"Health check: {container_status['running_containers']}/{container_status['total_containers']} containers running")
                    
                else:
                    # Daemon is down
                    if not daemon_downtime_start:
                        daemon_downtime_start = datetime.now()
                        self.generate_alert("daemon_down", "Docker daemon is not responding", "critical", daemon_status)
                    
                    downtime = (datetime.now() - daemon_downtime_start).total_seconds()
                    downtime_threshold = self.config.get("alert_thresholds", {}).get("daemon_downtime", 300)
                    
                    if downtime > downtime_threshold:
                        self.generate_alert("daemon_extended_downtime", 
                                          f"Docker daemon down for {downtime:.1f}s", "critical")
                    
                    # Attempt restart if enabled and within limits
                    if (self.config.get("auto_restart", True) and 
                        restart_attempts < max_restart_attempts):
                        
                        restart_attempts += 1
                        self._log(f"Daemon restart attempt {restart_attempts}/{max_restart_attempts}")
                        
                        if self.attempt_daemon_restart():
                            continue  # Skip sleep and check immediately
                        else:
                            restart_delay = self.config.get("restart_delay", 10)
                            self._log(f"Restart failed, waiting {restart_delay}s before next attempt")
                            time.sleep(restart_delay)
                    
                    elif restart_attempts >= max_restart_attempts:
                        self.generate_alert("restart_failed", 
                                          f"Failed to restart daemon after {restart_attempts} attempts", "critical")
                
                # Wait for next check
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            self._log("Monitoring stopped by user")
        except Exception as e:
            self._log(f"Monitoring error: {e}", "ERROR")
        finally:
            self.running = False
            self._log("Docker health monitoring stopped")
    
    def stop_monitoring(self):
        """Stop monitoring loop"""
        self.running = False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Docker Daemon Health Monitor")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    parser.add_argument("--check-once", action="store_true", help="Run single health check")
    parser.add_argument("--restart-daemon", action="store_true", help="Attempt to restart Docker daemon")
    
    args = parser.parse_args()
    
    monitor = DockerHealthMonitor(args.config)
    
    if args.restart_daemon:
        success = monitor.attempt_daemon_restart()
        sys.exit(0 if success else 1)
    
    elif args.check_once:
        daemon_status = monitor.check_daemon_status()
        container_status = monitor.check_container_health()
        resource_status = monitor.check_docker_resources()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "daemon": daemon_status,
            "containers": container_status,
            "resources": resource_status
        }
        
        print(json.dumps(report, indent=2))
        
        # Exit with error code if issues found
        all_issues = (daemon_status.get("issues", []) + 
                     container_status.get("issues", []) + 
                     resource_status.get("issues", []))
        sys.exit(1 if all_issues else 0)
    
    else:
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print("\nReceived shutdown signal, stopping monitoring...")
            monitor.stop_monitoring()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run monitoring loop
        monitor.monitor_loop()

if __name__ == "__main__":
    main()