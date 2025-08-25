#!/usr/bin/env python3
"""
Docker Daemon Integration for Docker-enabled Android kernel.

This module handles Docker daemon startup, configuration, health monitoring,
and integration with Android system components.
"""

import os
import subprocess
import json
import time
import logging
import signal
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DockerConfig:
    """Docker daemon configuration."""
    registry_mirrors: List[str]
    experimental: bool = True
    storage_driver: str = "overlay2"
    log_driver: str = "json-file"
    log_opts: Dict[str, str] = None
    insecure_registries: List[str] = None
    
    def __post_init__(self):
        if self.log_opts is None:
            self.log_opts = {"max-size": "10m", "max-file": "3"}
        if self.insecure_registries is None:
            self.insecure_registries = []


class DockerDaemonManager:
    """Manages Docker daemon lifecycle and integration."""
    
    # Docker binary paths
    DOCKER_BINARIES = [
        "dockerd", "docker", "docker-init", "docker-proxy", 
        "containerd", "containerd-shim", "runc", "ctr"
    ]
    
    # Required directories
    REQUIRED_DIRS = [
        "/var", "/run", "/tmp", "/opt", "/usr",
        "/data/var", "/data/run", "/data/tmp", "/data/opt", 
        "/data/etc", "/data/etc/docker", "/system/etc/docker"
    ]
    
    # Cgroup mount points
    CGROUP_ROOT = "/sys/fs/cgroup"
    CGROUP_CONTROLLERS = [
        "blkio", "cpu", "cpuacct", "cpuset", "devices", 
        "freezer", "hugetlb", "memory", "net_cls", "net_prio",
        "perf_event", "pids", "rdma", "schedtune", "systemd"
    ]
    
    def __init__(self, docker_path: str = "/system/bin", config_path: str = "/etc/docker"):
        """
        Initialize Docker daemon manager.
        
        Args:
            docker_path: Path to Docker binaries
            config_path: Path to Docker configuration directory
        """
        self.docker_path = Path(docker_path)
        self.config_path = Path(config_path)
        self.daemon_process: Optional[subprocess.Popen] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        self.should_monitor = False
        
    def validate_environment(self) -> Tuple[bool, List[str]]:
        """
        Validate that the environment is ready for Docker daemon.
        
        Returns:
            Tuple of (success, list of issues)
        """
        issues = []
        
        try:
            # Check for Docker binaries
            missing_binaries = []
            for binary in self.DOCKER_BINARIES:
                binary_path = self.docker_path / binary
                if not binary_path.exists():
                    # Also check in PATH
                    if not self._find_binary(binary):
                        missing_binaries.append(binary)
                        
            if missing_binaries:
                issues.append(f"Missing Docker binaries: {missing_binaries}")
                
            # Check kernel support
            if not self._check_kernel_support():
                issues.append("Kernel missing Docker support features")
                
            # Check cgroup support
            if not self._check_cgroup_support():
                issues.append("Cgroup subsystems not properly configured")
                
            # Check permissions
            if os.geteuid() != 0:
                issues.append("Docker daemon requires root privileges")
                
            return len(issues) == 0, issues
            
        except Exception as e:
            logger.error(f"Failed to validate environment: {e}")
            return False, [str(e)]
            
    def _find_binary(self, binary_name: str) -> Optional[str]:
        """Find binary in PATH."""
        try:
            result = subprocess.run(["which", binary_name], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
        
    def _check_kernel_support(self) -> bool:
        """Check if kernel supports Docker features."""
        required_features = [
            "/proc/sys/net/bridge/bridge-nf-call-iptables",
            "/proc/sys/net/ipv4/ip_forward"
        ]
        
        for feature in required_features:
            if not os.path.exists(feature):
                logger.warning(f"Missing kernel feature: {feature}")
                return False
                
        return True
        
    def _check_cgroup_support(self) -> bool:
        """Check if cgroup subsystems are available."""
        try:
            if not os.path.exists("/proc/cgroups"):
                return False
                
            with open("/proc/cgroups", 'r') as f:
                available_controllers = []
                for line in f.readlines()[1:]:  # Skip header
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[3] == "1":  # Controller is enabled
                        available_controllers.append(parts[0])
                        
            required_controllers = ["cpu", "memory", "devices", "freezer", "pids"]
            for controller in required_controllers:
                if controller not in available_controllers:
                    logger.warning(f"Missing cgroup controller: {controller}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to check cgroup support: {e}")
            return False
            
    def setup_directories(self) -> bool:
        """
        Create required directories for Docker daemon.
        
        Returns:
            True if directories created successfully, False otherwise
        """
        try:
            # Remount root as read-write
            subprocess.run(["mount", "-o", "rw,remount", "/"], check=False)
            
            # Create required directories
            for directory in self.REQUIRED_DIRS:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
                
            # Set up bind mounts for persistent storage
            bind_mounts = [
                ("/data/etc/docker", "/etc/docker"),
                ("/data/var", "/var"),
                ("/data/run", "/run"),
                ("/data/tmp", "/tmp"),
                ("/data/opt", "/opt")
            ]
            
            for source, target in bind_mounts:
                if os.path.exists(source) and os.path.exists(target):
                    try:
                        subprocess.run(["mount", "--bind", source, target], check=True)
                        logger.info(f"Bind mounted {source} to {target}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Failed to bind mount {source} to {target}: {e}")
                        
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup directories: {e}")
            return False
            
    def setup_cgroups(self) -> bool:
        """
        Setup cgroup filesystem for Docker.
        
        Returns:
            True if cgroups setup successfully, False otherwise
        """
        try:
            # Mount tmpfs for cgroup root
            if not self._is_mounted(self.CGROUP_ROOT):
                subprocess.run([
                    "mount", "tmpfs", self.CGROUP_ROOT, 
                    "-t", "tmpfs", "-o", "size=1G"
                ], check=True)
                logger.info(f"Mounted tmpfs at {self.CGROUP_ROOT}")
                
            # Create cgroup controller directories
            for controller in self.CGROUP_CONTROLLERS:
                controller_path = f"{self.CGROUP_ROOT}/{controller}"
                os.makedirs(controller_path, exist_ok=True)
                
            # Mount cgroup controllers
            for controller in self.CGROUP_CONTROLLERS:
                controller_path = f"{self.CGROUP_ROOT}/{controller}"
                
                if not self._is_mounted(controller_path):
                    if controller == "systemd":
                        mount_cmd = [
                            "mount", "-t", "cgroup", 
                            "-o", "none,name=systemd",
                            "cgroup", controller_path
                        ]
                    else:
                        mount_cmd = [
                            "mount", "-t", "cgroup",
                            "-o", f"{controller},nodev,noexec,nosuid",
                            "cgroup", controller_path
                        ]
                        
                    try:
                        subprocess.run(mount_cmd, check=True)
                        logger.info(f"Mounted cgroup controller: {controller}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Failed to mount cgroup {controller}: {e}")
                        
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup cgroups: {e}")
            return False
            
    def _is_mounted(self, mount_point: str) -> bool:
        """Check if filesystem is mounted at given point."""
        try:
            with open("/proc/mounts", 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == mount_point:
                        return True
            return False
        except Exception:
            return False
            
    def setup_networking(self) -> bool:
        """
        Setup networking configuration for Docker.
        
        Returns:
            True if networking setup successfully, False otherwise
        """
        try:
            # Setup IP routing rules
            routing_commands = [
                ["ip", "rule", "add", "pref", "1", "from", "all", "lookup", "main"],
                ["ip", "rule", "add", "pref", "2", "from", "all", "lookup", "default"]
            ]
            
            for cmd in routing_commands:
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    logger.info(f"Applied routing rule: {' '.join(cmd)}")
                except subprocess.CalledProcessError as e:
                    # Rule might already exist
                    logger.debug(f"Routing rule command failed (may already exist): {e}")
                    
            # Enable IP forwarding
            try:
                with open("/proc/sys/net/ipv4/ip_forward", 'w') as f:
                    f.write("1")
                logger.info("Enabled IP forwarding")
            except Exception as e:
                logger.warning(f"Failed to enable IP forwarding: {e}")
                
            # Load br_netfilter module if available
            try:
                subprocess.run(["modprobe", "br_netfilter"], check=False, capture_output=True)
                logger.info("Loaded br_netfilter module")
            except Exception:
                logger.debug("br_netfilter module not available or already loaded")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup networking: {e}")
            return False
            
    def create_daemon_config(self, config: DockerConfig) -> bool:
        """
        Create Docker daemon configuration file.
        
        Args:
            config: Docker configuration object
            
        Returns:
            True if configuration created successfully, False otherwise
        """
        try:
            config_data = {
                "registry-mirrors": config.registry_mirrors,
                "experimental": config.experimental,
                "storage-driver": config.storage_driver,
                "log-driver": config.log_driver,
                "log-opts": config.log_opts
            }
            
            if config.insecure_registries:
                config_data["insecure-registries"] = config.insecure_registries
                
            # Ensure config directory exists
            os.makedirs(self.config_path, exist_ok=True)
            
            config_file = self.config_path / "daemon.json"
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
            logger.info(f"Created Docker daemon configuration: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create daemon configuration: {e}")
            return False
            
    def deploy_binaries(self, source_path: str) -> bool:
        """
        Deploy Docker binaries to system location.
        
        Args:
            source_path: Path to Docker binaries
            
        Returns:
            True if binaries deployed successfully, False otherwise
        """
        try:
            source_dir = Path(source_path)
            if not source_dir.exists():
                logger.error(f"Source directory not found: {source_path}")
                return False
                
            # Ensure target directory exists
            os.makedirs(self.docker_path, exist_ok=True)
            
            # Copy binaries
            for binary in self.DOCKER_BINARIES:
                source_file = source_dir / binary
                target_file = self.docker_path / binary
                
                if source_file.exists():
                    try:
                        # Copy binary
                        subprocess.run(["cp", str(source_file), str(target_file)], check=True)
                        
                        # Set executable permissions
                        os.chmod(target_file, 0o755)
                        
                        logger.info(f"Deployed binary: {binary}")
                    except Exception as e:
                        logger.error(f"Failed to deploy {binary}: {e}")
                        return False
                else:
                    logger.warning(f"Binary not found in source: {binary}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to deploy binaries: {e}")
            return False
            
    def start_daemon(self, host_binds: List[str] = None, additional_args: List[str] = None) -> bool:
        """
        Start Docker daemon process.
        
        Args:
            host_binds: List of host bind addresses (e.g., ["tcp://0.0.0.0:2375"])
            additional_args: Additional arguments for dockerd
            
        Returns:
            True if daemon started successfully, False otherwise
        """
        try:
            if self.daemon_process and self.daemon_process.poll() is None:
                logger.warning("Docker daemon is already running")
                return True
                
            # Disable SELinux enforcement
            try:
                subprocess.run(["setenforce", "0"], check=False, capture_output=True)
                logger.info("Disabled SELinux enforcement")
            except Exception:
                logger.debug("Could not disable SELinux (may not be available)")
                
            # Set environment variables
            env = os.environ.copy()
            env["DOCKER_RAMDISK"] = "true"
            
            # Build dockerd command
            dockerd_cmd = ["dockerd"]
            
            # Add runtime support
            dockerd_cmd.extend(["--add-runtime", "crun=/bin/crun"])
            
            # Add host binds
            if host_binds:
                for bind in host_binds:
                    dockerd_cmd.extend(["-H", bind])
            else:
                # Default binds
                dockerd_cmd.extend(["-H", "tcp://0.0.0.0:2375"])
                dockerd_cmd.extend(["-H", "unix:///var/run/docker.sock"])
                
            # Add additional arguments
            if additional_args:
                dockerd_cmd.extend(additional_args)
                
            logger.info(f"Starting Docker daemon: {' '.join(dockerd_cmd)}")
            
            # Start daemon process
            self.daemon_process = subprocess.Popen(
                dockerd_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait a moment to check if process started successfully
            time.sleep(2)
            
            if self.daemon_process.poll() is None:
                logger.info(f"Docker daemon started successfully (PID: {self.daemon_process.pid})")
                
                # Start monitoring thread
                self.should_monitor = True
                self.monitoring_thread = threading.Thread(target=self._monitor_daemon)
                self.monitoring_thread.daemon = True
                self.monitoring_thread.start()
                
                return True
            else:
                stdout, stderr = self.daemon_process.communicate()
                logger.error(f"Docker daemon failed to start: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Docker daemon: {e}")
            return False
            
    def _monitor_daemon(self):
        """Monitor Docker daemon health and restart if necessary."""
        restart_count = 0
        max_restarts = 3
        
        while self.should_monitor:
            try:
                time.sleep(10)  # Check every 10 seconds
                
                if self.daemon_process and self.daemon_process.poll() is not None:
                    logger.warning("Docker daemon process has stopped")
                    
                    if restart_count < max_restarts:
                        logger.info(f"Attempting to restart daemon (attempt {restart_count + 1})")
                        restart_count += 1
                        
                        # Try to restart
                        if self.start_daemon():
                            logger.info("Docker daemon restarted successfully")
                            restart_count = 0  # Reset counter on successful restart
                        else:
                            logger.error("Failed to restart Docker daemon")
                    else:
                        logger.error("Maximum restart attempts reached, stopping monitoring")
                        break
                        
                # Check daemon health via socket
                elif not self._check_daemon_health():
                    logger.warning("Docker daemon health check failed")
                    
            except Exception as e:
                logger.error(f"Error in daemon monitoring: {e}")
                
    def _check_daemon_health(self) -> bool:
        """Check if Docker daemon is responding."""
        try:
            # Try to connect to Docker socket
            import socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect("/var/run/docker.sock")
            sock.close()
            return True
        except Exception:
            return False
            
    def stop_daemon(self) -> bool:
        """
        Stop Docker daemon process.
        
        Returns:
            True if daemon stopped successfully, False otherwise
        """
        try:
            self.should_monitor = False
            
            if self.daemon_process and self.daemon_process.poll() is None:
                logger.info("Stopping Docker daemon...")
                
                # Send SIGTERM to process group
                os.killpg(os.getpgid(self.daemon_process.pid), signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    self.daemon_process.wait(timeout=30)
                    logger.info("Docker daemon stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("Docker daemon did not stop gracefully, forcing termination")
                    os.killpg(os.getpgid(self.daemon_process.pid), signal.SIGKILL)
                    self.daemon_process.wait()
                    
                self.daemon_process = None
                
            # Wait for monitoring thread to finish
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Docker daemon: {e}")
            return False
            
    def get_daemon_status(self) -> Dict[str, Any]:
        """
        Get Docker daemon status information.
        
        Returns:
            Dictionary containing daemon status
        """
        status = {
            "running": False,
            "pid": None,
            "uptime": None,
            "health": "unknown"
        }
        
        try:
            if self.daemon_process and self.daemon_process.poll() is None:
                status["running"] = True
                status["pid"] = self.daemon_process.pid
                
                # Get process info
                if PSUTIL_AVAILABLE:
                    try:
                        process = psutil.Process(self.daemon_process.pid)
                        status["uptime"] = time.time() - process.create_time()
                    except Exception:
                        pass
                    
                # Check health
                if self._check_daemon_health():
                    status["health"] = "healthy"
                else:
                    status["health"] = "unhealthy"
                    
        except Exception as e:
            logger.error(f"Failed to get daemon status: {e}")
            
        return status
        
    def setup_complete_environment(self, docker_source_path: str = "docker") -> bool:
        """
        Complete setup of Docker environment.
        
        Args:
            docker_source_path: Path to Docker binaries source
            
        Returns:
            True if setup completed successfully, False otherwise
        """
        logger.info("Setting up complete Docker environment...")
        
        # Validate environment
        valid, issues = self.validate_environment()
        if not valid:
            logger.error(f"Environment validation failed: {issues}")
            # Continue anyway, some issues might be resolved during setup
            
        # Setup directories
        if not self.setup_directories():
            logger.error("Failed to setup directories")
            return False
            
        # Setup cgroups
        if not self.setup_cgroups():
            logger.error("Failed to setup cgroups")
            return False
            
        # Setup networking
        if not self.setup_networking():
            logger.error("Failed to setup networking")
            return False
            
        # Deploy binaries if source path provided
        if docker_source_path and os.path.exists(docker_source_path):
            if not self.deploy_binaries(docker_source_path):
                logger.warning("Failed to deploy binaries, continuing with existing binaries")
                
        # Create default daemon configuration
        default_config = DockerConfig(
            registry_mirrors=["https://docker.mirrors.ustc.edu.cn"],
            experimental=True
        )
        
        if not self.create_daemon_config(default_config):
            logger.error("Failed to create daemon configuration")
            return False
            
        logger.info("Docker environment setup completed successfully")
        return True


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Docker Daemon Manager for Android")
    parser.add_argument("--docker-path", "-d", default="/system/bin", help="Path to Docker binaries")
    parser.add_argument("--config-path", "-c", default="/etc/docker", help="Path to Docker configuration")
    parser.add_argument("--setup", "-s", action="store_true", help="Setup complete Docker environment")
    parser.add_argument("--start", action="store_true", help="Start Docker daemon")
    parser.add_argument("--stop", action="store_true", help="Stop Docker daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate environment")
    parser.add_argument("--source", help="Source path for Docker binaries")
    parser.add_argument("--host", action="append", help="Host bind addresses (can be used multiple times)")
    
    args = parser.parse_args()
    
    manager = DockerDaemonManager(args.docker_path, args.config_path)
    
    if args.validate:
        valid, issues = manager.validate_environment()
        if valid:
            print("Environment validation passed")
        else:
            print(f"Environment validation failed: {issues}")
            return 1
            
    elif args.setup:
        source_path = args.source or "docker"
        if manager.setup_complete_environment(source_path):
            print("Docker environment setup completed successfully")
        else:
            print("Docker environment setup failed")
            return 1
            
    elif args.start:
        if manager.setup_complete_environment(args.source or "docker"):
            if manager.start_daemon(args.host):
                print("Docker daemon started successfully")
                # Keep running to monitor daemon
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping Docker daemon...")
                    manager.stop_daemon()
            else:
                print("Failed to start Docker daemon")
                return 1
        else:
            print("Failed to setup Docker environment")
            return 1
            
    elif args.stop:
        if manager.stop_daemon():
            print("Docker daemon stopped successfully")
        else:
            print("Failed to stop Docker daemon")
            return 1
            
    elif args.status:
        status = manager.get_daemon_status()
        print(f"Docker daemon status: {json.dumps(status, indent=2)}")
        
    else:
        parser.print_help()
        
    return 0


if __name__ == "__main__":
    exit(main())