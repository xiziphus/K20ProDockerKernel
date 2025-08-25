#!/usr/bin/env python3
"""
Cgroup Configuration Manager for Docker-enabled Android kernel.

This module handles cgroup subsystem configuration, mounting, and validation
required for Docker container runtime on Android devices.
"""

import json
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CgroupConfig:
    """Configuration for a single cgroup subsystem."""
    controller: str
    path: str
    uid: str = "root"
    gid: str = "root"
    mode: str = "0755"


@dataclass
class CgroupV2Config:
    """Configuration for cgroup v2."""
    path: str
    uid: str = "root"
    gid: str = "root"
    mode: str = "0755"


class CgroupManager:
    """Manages cgroup configuration and mounting for Docker support."""
    
    # Docker required cgroup controllers
    DOCKER_REQUIRED_CONTROLLERS = [
        "blkio", "cpu", "cpuacct", "cpuset", "memory", 
        "devices", "freezer", "pids", "net_cls", "net_prio"
    ]
    
    # Default cgroup mount points
    DEFAULT_CGROUP_ROOT = "/sys/fs/cgroup"
    DEFAULT_CGROUP2_ROOT = "/sys/fs/cgroup/unified"
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize cgroup manager.
        
        Args:
            config_file: Path to cgroups.json configuration file
        """
        self.config_file = config_file or "files/cgroups.json"
        self.cgroup_configs: List[CgroupConfig] = []
        self.cgroup2_config: Optional[CgroupV2Config] = None
        
    def load_config(self) -> bool:
        """
        Load cgroup configuration from JSON file.
        
        Returns:
            True if configuration loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.config_file):
                logger.error(f"Configuration file not found: {self.config_file}")
                return False
                
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                
            # Parse cgroup v1 configurations
            if "Cgroups" in config_data:
                for cgroup_data in config_data["Cgroups"]:
                    config = CgroupConfig(
                        controller=cgroup_data["Controller"],
                        path=cgroup_data["Path"],
                        uid=cgroup_data.get("UID", "root"),
                        gid=cgroup_data.get("GID", "root"),
                        mode=cgroup_data.get("Mode", "0755")
                    )
                    self.cgroup_configs.append(config)
                    
            # Parse cgroup v2 configuration
            if "Cgroups2" in config_data:
                cgroup2_data = config_data["Cgroups2"]
                self.cgroup2_config = CgroupV2Config(
                    path=cgroup2_data["Path"],
                    uid=cgroup2_data.get("UID", "root"),
                    gid=cgroup2_data.get("GID", "root"),
                    mode=cgroup2_data.get("Mode", "0755")
                )
                
            logger.info(f"Loaded {len(self.cgroup_configs)} cgroup v1 configurations")
            if self.cgroup2_config:
                logger.info("Loaded cgroup v2 configuration")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cgroup configuration: {e}")
            return False
            
    def generate_default_config(self) -> Dict[str, Any]:
        """
        Generate default cgroup configuration for Docker.
        
        Returns:
            Dictionary containing default cgroup configuration
        """
        cgroups = []
        
        # Generate configurations for Docker required controllers
        controller_paths = {
            "blkio": "/dev/blkio",
            "cpu": "/dev/cpu", 
            "cpuacct": "/dev/cpuacct",
            "cpuset": "/dev/cpuset",
            "memory": "/dev/memcg",
            "devices": "/dev/devices",
            "freezer": "/dev/freezer",
            "pids": "/dev/pids",
            "net_cls": "/dev/net_cls",
            "net_prio": "/dev/net_prio",
            "perf_event": "/dev/perf_event",
            "hugetlb": "/dev/hugetlb",
            "rdma": "/dev/rdma"
        }
        
        for controller, path in controller_paths.items():
            cgroup_config = {
                "Controller": controller,
                "Path": path,
                "UID": "system" if controller in ["blkio", "cpu", "cpuset", "memory"] else "root",
                "GID": "system" if controller in ["blkio", "cpu", "cpuset", "memory"] else "root", 
                "Mode": "0755"
            }
            cgroups.append(cgroup_config)
            
        # Add cgroup v2 configuration
        cgroups2_config = {
            "Path": "/dev/cg2_bpf",
            "UID": "root",
            "GID": "root", 
            "Mode": "0755"
        }
        
        return {
            "Cgroups": cgroups,
            "Cgroups2": cgroups2_config
        }
        
    def save_config(self, config_data: Dict[str, Any], output_file: Optional[str] = None) -> bool:
        """
        Save cgroup configuration to JSON file.
        
        Args:
            config_data: Configuration data to save
            output_file: Output file path (defaults to self.config_file)
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            output_path = output_file or self.config_file
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(config_data, f, indent=2)
                
            logger.info(f"Cgroup configuration saved to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cgroup configuration: {e}")
            return False
            
    def validate_cgroup_support(self) -> Tuple[bool, List[str]]:
        """
        Validate that the kernel supports required cgroup controllers.
        
        Returns:
            Tuple of (success, list of missing controllers)
        """
        missing_controllers = []
        
        try:
            # Check /proc/cgroups for available controllers
            if os.path.exists("/proc/cgroups"):
                with open("/proc/cgroups", 'r') as f:
                    available_controllers = []
                    for line in f.readlines()[1:]:  # Skip header
                        parts = line.strip().split()
                        if len(parts) >= 4 and parts[3] == "1":  # Controller is enabled
                            available_controllers.append(parts[0])
                            
                # Check for missing required controllers
                for controller in self.DOCKER_REQUIRED_CONTROLLERS:
                    if controller not in available_controllers:
                        missing_controllers.append(controller)
                        
            else:
                logger.warning("/proc/cgroups not found - cannot validate controller support")
                return False, ["Cannot access /proc/cgroups"]
                
            if missing_controllers:
                logger.warning(f"Missing cgroup controllers: {missing_controllers}")
                return False, missing_controllers
            else:
                logger.info("All required cgroup controllers are available")
                return True, []
                
        except Exception as e:
            logger.error(f"Failed to validate cgroup support: {e}")
            return False, [str(e)]
            
    def create_cgroup_hierarchy(self) -> bool:
        """
        Create cgroup hierarchy and mount points for Docker.
        
        Returns:
            True if hierarchy created successfully, False otherwise
        """
        try:
            success = True
            
            # Create mount points for each cgroup controller
            for config in self.cgroup_configs:
                mount_point = config.path
                
                # Create mount point directory
                os.makedirs(mount_point, exist_ok=True)
                
                # Set permissions
                try:
                    # Convert mode string to octal
                    mode = int(config.mode, 8)
                    os.chmod(mount_point, mode)
                    
                    # Set ownership (requires root privileges)
                    if os.geteuid() == 0:  # Running as root
                        import pwd, grp
                        try:
                            uid = pwd.getpwnam(config.uid).pw_uid
                            gid = grp.getgrnam(config.gid).gr_gid
                            os.chown(mount_point, uid, gid)
                        except KeyError:
                            logger.warning(f"User/group not found: {config.uid}/{config.gid}")
                    else:
                        logger.warning("Not running as root - cannot set ownership")
                        
                except Exception as e:
                    logger.error(f"Failed to set permissions for {mount_point}: {e}")
                    success = False
                    
                logger.info(f"Created cgroup mount point: {mount_point}")
                
            # Create cgroup v2 mount point if configured
            if self.cgroup2_config:
                mount_point = self.cgroup2_config.path
                os.makedirs(mount_point, exist_ok=True)
                
                try:
                    mode = int(self.cgroup2_config.mode, 8)
                    os.chmod(mount_point, mode)
                    
                    if os.geteuid() == 0:
                        import pwd, grp
                        try:
                            uid = pwd.getpwnam(self.cgroup2_config.uid).pw_uid
                            gid = grp.getgrnam(self.cgroup2_config.gid).gr_gid
                            os.chown(mount_point, uid, gid)
                        except KeyError:
                            logger.warning(f"User/group not found: {self.cgroup2_config.uid}/{self.cgroup2_config.gid}")
                            
                except Exception as e:
                    logger.error(f"Failed to set permissions for cgroup v2 mount point: {e}")
                    success = False
                    
                logger.info(f"Created cgroup v2 mount point: {mount_point}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to create cgroup hierarchy: {e}")
            return False
            
    def mount_cgroups(self) -> bool:
        """
        Mount cgroup filesystems for Docker support.
        
        Returns:
            True if all cgroups mounted successfully, False otherwise
        """
        try:
            success = True
            
            # Mount cgroup v1 controllers
            for config in self.cgroup_configs:
                mount_point = config.path
                controller = config.controller
                
                # Check if already mounted
                if self._is_mounted(mount_point):
                    logger.info(f"Cgroup {controller} already mounted at {mount_point}")
                    continue
                    
                # Mount the cgroup controller
                mount_cmd = [
                    "mount", "-t", "cgroup", 
                    "-o", controller,
                    controller, mount_point
                ]
                
                try:
                    result = subprocess.run(mount_cmd, capture_output=True, text=True, check=True)
                    logger.info(f"Mounted cgroup {controller} at {mount_point}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to mount cgroup {controller}: {e.stderr}")
                    success = False
                    
            # Mount cgroup v2 if configured
            if self.cgroup2_config:
                mount_point = self.cgroup2_config.path
                
                if not self._is_mounted(mount_point):
                    mount_cmd = [
                        "mount", "-t", "cgroup2",
                        "cgroup2", mount_point
                    ]
                    
                    try:
                        result = subprocess.run(mount_cmd, capture_output=True, text=True, check=True)
                        logger.info(f"Mounted cgroup v2 at {mount_point}")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to mount cgroup v2: {e.stderr}")
                        success = False
                else:
                    logger.info(f"Cgroup v2 already mounted at {mount_point}")
                    
            return success
            
        except Exception as e:
            logger.error(f"Failed to mount cgroups: {e}")
            return False
            
    def _is_mounted(self, mount_point: str) -> bool:
        """
        Check if a filesystem is already mounted at the given mount point.
        
        Args:
            mount_point: Path to check
            
        Returns:
            True if mounted, False otherwise
        """
        try:
            with open("/proc/mounts", 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == mount_point:
                        return True
            return False
        except Exception:
            return False
            
    def validate_mounts(self) -> Tuple[bool, List[str]]:
        """
        Validate that all required cgroups are properly mounted.
        
        Returns:
            Tuple of (success, list of unmounted controllers)
        """
        unmounted = []
        
        try:
            # Check cgroup v1 mounts
            for config in self.cgroup_configs:
                if not self._is_mounted(config.path):
                    unmounted.append(config.controller)
                    
            # Check cgroup v2 mount
            if self.cgroup2_config and not self._is_mounted(self.cgroup2_config.path):
                unmounted.append("cgroup2")
                
            if unmounted:
                logger.warning(f"Unmounted cgroups: {unmounted}")
                return False, unmounted
            else:
                logger.info("All cgroups are properly mounted")
                return True, []
                
        except Exception as e:
            logger.error(f"Failed to validate mounts: {e}")
            return False, [str(e)]
            
    def setup_docker_cgroups(self) -> bool:
        """
        Complete setup of cgroups for Docker support.
        
        Returns:
            True if setup completed successfully, False otherwise
        """
        logger.info("Setting up cgroups for Docker support...")
        
        # Load configuration
        if not self.load_config():
            logger.info("Generating default cgroup configuration...")
            default_config = self.generate_default_config()
            if not self.save_config(default_config):
                return False
            if not self.load_config():
                return False
                
        # Validate kernel support
        supported, missing = self.validate_cgroup_support()
        if not supported:
            logger.error(f"Kernel missing required cgroup support: {missing}")
            return False
            
        # Create hierarchy
        if not self.create_cgroup_hierarchy():
            logger.error("Failed to create cgroup hierarchy")
            return False
            
        # Mount cgroups
        if not self.mount_cgroups():
            logger.error("Failed to mount cgroups")
            return False
            
        # Validate mounts
        mounted, unmounted = self.validate_mounts()
        if not mounted:
            logger.error(f"Some cgroups failed to mount: {unmounted}")
            return False
            
        logger.info("Cgroup setup completed successfully")
        return True


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cgroup Configuration Manager for Docker")
    parser.add_argument("--config", "-c", help="Path to cgroups.json configuration file")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate default configuration")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate cgroup support")
    parser.add_argument("--setup", "-s", action="store_true", help="Setup cgroups for Docker")
    parser.add_argument("--output", "-o", help="Output file for generated configuration")
    
    args = parser.parse_args()
    
    manager = CgroupManager(args.config)
    
    if args.generate:
        config = manager.generate_default_config()
        output_file = args.output or "cgroups.json"
        if manager.save_config(config, output_file):
            print(f"Default configuration generated: {output_file}")
        else:
            print("Failed to generate configuration")
            return 1
            
    elif args.validate:
        supported, missing = manager.validate_cgroup_support()
        if supported:
            print("All required cgroup controllers are supported")
        else:
            print(f"Missing cgroup controllers: {missing}")
            return 1
            
    elif args.setup:
        if manager.setup_docker_cgroups():
            print("Cgroup setup completed successfully")
        else:
            print("Cgroup setup failed")
            return 1
    else:
        parser.print_help()
        
    return 0


if __name__ == "__main__":
    exit(main())