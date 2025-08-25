#!/usr/bin/env python3
"""
Overlay filesystem manager for Docker container storage.

This module handles overlay filesystem setup, storage driver configuration,
and filesystem permission management for Docker containers.
"""

import os
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.file_utils import ensure_directory, backup_file


class OverlayManager:
    """Manages overlay filesystem setup for Docker containers."""
    
    def __init__(self, base_path: str = "/data/docker"):
        """
        Initialize overlay manager.
        
        Args:
            base_path: Base directory for Docker storage
        """
        self.base_path = Path(base_path)
        self.overlay_path = self.base_path / "overlay2"
        self.driver_config_path = self.base_path / "daemon.json"
        self.logger = logging.getLogger(__name__)
        
        # Required overlay filesystem kernel modules
        self.required_modules = [
            "overlay",
            "overlayfs"
        ]
        
        # Required mount options for overlay
        self.mount_options = [
            "rw",
            "relatime",
            "lowerdir",
            "upperdir", 
            "workdir"
        ]
    
    def setup_overlay_filesystem(self) -> bool:
        """
        Set up overlay filesystem support for Docker.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            self.logger.info("Setting up overlay filesystem for Docker")
            
            # Create base directories
            if not self._create_storage_directories():
                return False
            
            # Verify kernel support
            if not self._verify_kernel_support():
                return False
            
            # Configure storage driver
            if not self._configure_storage_driver():
                return False
            
            # Set up filesystem permissions
            if not self._setup_filesystem_permissions():
                return False
            
            # Create mount points
            if not self._create_mount_points():
                return False
            
            self.logger.info("Overlay filesystem setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup overlay filesystem: {e}")
            return False
    
    def _create_storage_directories(self) -> bool:
        """Create required storage directories."""
        try:
            directories = [
                self.base_path,
                self.overlay_path,
                self.overlay_path / "l",  # Link directory
                self.base_path / "containers",
                self.base_path / "image" / "overlay2",
                self.base_path / "volumes",
                self.base_path / "tmp"
            ]
            
            for directory in directories:
                ensure_directory(str(directory))
                self.logger.debug(f"Created directory: {directory}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create storage directories: {e}")
            return False
    
    def _verify_kernel_support(self) -> bool:
        """Verify kernel supports overlay filesystem."""
        try:
            # Check if overlay module is loaded or available
            proc_filesystems = Path("/proc/filesystems")
            if proc_filesystems.exists():
                with open(proc_filesystems, 'r') as f:
                    filesystems = f.read()
                    if "overlay" in filesystems:
                        self.logger.info("Overlay filesystem support detected in kernel")
                        return True
            
            # Try to load overlay module
            try:
                subprocess.run(["modprobe", "overlay"], 
                             check=True, capture_output=True)
                self.logger.info("Loaded overlay kernel module")
                return True
            except subprocess.CalledProcessError:
                pass
            
            # Check for overlayfs (older name)
            try:
                subprocess.run(["modprobe", "overlayfs"], 
                             check=True, capture_output=True)
                self.logger.info("Loaded overlayfs kernel module")
                return True
            except subprocess.CalledProcessError:
                pass
            
            self.logger.error("Overlay filesystem not supported by kernel")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to verify kernel support: {e}")
            return False
    
    def _configure_storage_driver(self) -> bool:
        """Configure Docker daemon to use overlay2 storage driver."""
        try:
            daemon_config = {
                "storage-driver": "overlay2",
                "storage-opts": [
                    "overlay2.override_kernel_check=true"
                ],
                "data-root": str(self.base_path)
            }
            
            # Backup existing config if it exists
            if self.driver_config_path.exists():
                backup_file(str(self.driver_config_path))
            
            # Write new daemon configuration
            with open(self.driver_config_path, 'w') as f:
                json.dump(daemon_config, f, indent=2)
            
            self.logger.info(f"Configured storage driver at {self.driver_config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure storage driver: {e}")
            return False
    
    def _setup_filesystem_permissions(self) -> bool:
        """Set up proper filesystem permissions for Docker storage."""
        try:
            # Set permissions for Docker data directory
            os.chmod(self.base_path, 0o700)
            
            # Set permissions for overlay directory
            os.chmod(self.overlay_path, 0o700)
            
            # Ensure proper ownership (root:root for Android)
            try:
                subprocess.run(["chown", "-R", "root:root", str(self.base_path)],
                             check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Could not set ownership: {e}")
            
            self.logger.info("Set up filesystem permissions")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup filesystem permissions: {e}")
            return False
    
    def _create_mount_points(self) -> bool:
        """Create mount points for overlay filesystem."""
        try:
            mount_points = [
                self.base_path / "mnt",
                self.base_path / "overlay-mounts"
            ]
            
            for mount_point in mount_points:
                ensure_directory(str(mount_point))
                os.chmod(mount_point, 0o755)
            
            self.logger.info("Created overlay mount points")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create mount points: {e}")
            return False
    
    def validate_overlay_setup(self) -> Dict[str, bool]:
        """
        Validate overlay filesystem setup.
        
        Returns:
            Dict[str, bool]: Validation results for each component
        """
        results = {}
        
        try:
            # Check directories exist
            results["directories"] = all([
                self.base_path.exists(),
                self.overlay_path.exists(),
                (self.overlay_path / "l").exists()
            ])
            
            # Check kernel support
            results["kernel_support"] = self._verify_kernel_support()
            
            # Check daemon config
            results["daemon_config"] = self.driver_config_path.exists()
            
            # Check permissions
            results["permissions"] = (
                oct(self.base_path.stat().st_mode)[-3:] == "700" and
                oct(self.overlay_path.stat().st_mode)[-3:] == "700"
            )
            
            # Test overlay mount capability
            results["mount_capability"] = self._test_overlay_mount()
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def _test_overlay_mount(self) -> bool:
        """Test overlay mount capability."""
        try:
            test_dir = self.base_path / "test-overlay"
            lower_dir = test_dir / "lower"
            upper_dir = test_dir / "upper" 
            work_dir = test_dir / "work"
            merged_dir = test_dir / "merged"
            
            # Create test directories
            for directory in [test_dir, lower_dir, upper_dir, work_dir, merged_dir]:
                ensure_directory(str(directory))
            
            # Create test file in lower layer
            test_file = lower_dir / "test.txt"
            test_file.write_text("overlay test")
            
            # Try overlay mount
            mount_cmd = [
                "mount", "-t", "overlay", "overlay",
                "-o", f"lowerdir={lower_dir},upperdir={upper_dir},workdir={work_dir}",
                str(merged_dir)
            ]
            
            result = subprocess.run(mount_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Test successful, unmount
                subprocess.run(["umount", str(merged_dir)], capture_output=True)
                
                # Cleanup test directories
                subprocess.run(["rm", "-rf", str(test_dir)], capture_output=True)
                
                self.logger.info("Overlay mount test successful")
                return True
            else:
                self.logger.warning(f"Overlay mount test failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Overlay mount test error: {e}")
            return False
    
    def get_storage_info(self) -> Dict[str, any]:
        """
        Get storage information and statistics.
        
        Returns:
            Dict containing storage information
        """
        info = {
            "base_path": str(self.base_path),
            "overlay_path": str(self.overlay_path),
            "driver_config": str(self.driver_config_path),
            "directories_exist": self.base_path.exists(),
            "total_size": 0,
            "used_size": 0,
            "available_size": 0
        }
        
        try:
            if self.base_path.exists():
                # Get disk usage
                statvfs = os.statvfs(self.base_path)
                info["total_size"] = statvfs.f_frsize * statvfs.f_blocks
                info["available_size"] = statvfs.f_frsize * statvfs.f_bavail
                info["used_size"] = info["total_size"] - info["available_size"]
                
                # Get directory count
                overlay_dirs = list(self.overlay_path.glob("*")) if self.overlay_path.exists() else []
                info["overlay_directories"] = len(overlay_dirs)
                
        except Exception as e:
            self.logger.error(f"Failed to get storage info: {e}")
            info["error"] = str(e)
        
        return info
    
    def cleanup_overlay_storage(self) -> bool:
        """
        Clean up overlay storage (use with caution).
        
        Returns:
            bool: True if cleanup successful
        """
        try:
            self.logger.warning("Cleaning up overlay storage - this will remove all container data")
            
            # Stop any running containers first (this would be handled by Docker daemon)
            
            # Remove overlay directories
            if self.overlay_path.exists():
                subprocess.run(["rm", "-rf", str(self.overlay_path)], check=True)
            
            # Recreate clean overlay structure
            self._create_storage_directories()
            self._setup_filesystem_permissions()
            
            self.logger.info("Overlay storage cleanup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup overlay storage: {e}")
            return False