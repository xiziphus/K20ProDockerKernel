#!/usr/bin/env python3
"""
Volume and bind mount manager for Docker containers.

This module handles volume management, bind mount configuration,
and storage cleanup for Docker container data persistence.
"""

import os
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.file_utils import ensure_directory, backup_file, make_executable


class VolumeManager:
    """Manages Docker volumes and bind mounts."""
    
    def __init__(self, base_path: str = "/data/docker"):
        """
        Initialize volume manager.
        
        Args:
            base_path: Base directory for Docker storage
        """
        self.base_path = Path(base_path)
        self.volumes_path = self.base_path / "volumes"
        self.bind_mounts_config = self.base_path / "bind-mounts.json"
        self.logger = logging.getLogger(__name__)
        
        # Security settings for bind mounts
        self.allowed_host_paths = [
            "/data",
            "/sdcard", 
            "/storage",
            "/mnt/media_rw",
            "/tmp"
        ]
        
        # Default volume driver settings
        self.volume_drivers = {
            "local": {
                "mountpoint": str(self.volumes_path),
                "options": ["rw", "relatime"]
            }
        }
    
    def setup_volume_support(self) -> bool:
        """
        Set up volume management support.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            self.logger.info("Setting up volume management support")
            
            # Create volume directories
            if not self._create_volume_directories():
                return False
            
            # Set up volume permissions
            if not self._setup_volume_permissions():
                return False
            
            # Initialize volume metadata
            if not self._initialize_volume_metadata():
                return False
            
            # Configure bind mount security
            if not self._configure_bind_mount_security():
                return False
            
            self.logger.info("Volume support setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup volume support: {e}")
            return False
    
    def _create_volume_directories(self) -> bool:
        """Create required volume directories."""
        try:
            directories = [
                self.volumes_path,
                self.volumes_path / "metadata",
                self.base_path / "bind-mounts",
                self.base_path / "tmp-mounts"
            ]
            
            for directory in directories:
                ensure_directory(str(directory))
                self.logger.debug(f"Created volume directory: {directory}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create volume directories: {e}")
            return False
    
    def _setup_volume_permissions(self) -> bool:
        """Set up proper permissions for volume directories."""
        try:
            # Set permissions for volumes directory
            os.chmod(self.volumes_path, 0o755)
            
            # Set permissions for metadata directory
            metadata_dir = self.volumes_path / "metadata"
            os.chmod(metadata_dir, 0o700)
            
            # Set permissions for bind mounts directory
            bind_mounts_dir = self.base_path / "bind-mounts"
            os.chmod(bind_mounts_dir, 0o755)
            
            self.logger.info("Set up volume permissions")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup volume permissions: {e}")
            return False
    
    def _initialize_volume_metadata(self) -> bool:
        """Initialize volume metadata storage."""
        try:
            metadata_file = self.volumes_path / "metadata" / "volumes.json"
            
            if not metadata_file.exists():
                initial_metadata = {
                    "volumes": {},
                    "created": str(Path(__file__).stat().st_mtime),
                    "version": "1.0"
                }
                
                with open(metadata_file, 'w') as f:
                    json.dump(initial_metadata, f, indent=2)
            
            self.logger.info("Initialized volume metadata")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize volume metadata: {e}")
            return False
    
    def _configure_bind_mount_security(self) -> bool:
        """Configure bind mount security settings."""
        try:
            security_config = {
                "allowed_host_paths": self.allowed_host_paths,
                "default_options": ["rw", "relatime", "nodev", "nosuid"],
                "restricted_options": ["noexec"],
                "validation_enabled": True
            }
            
            with open(self.bind_mounts_config, 'w') as f:
                json.dump(security_config, f, indent=2)
            
            self.logger.info("Configured bind mount security")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure bind mount security: {e}")
            return False
    
    def create_volume(self, volume_name: str, driver: str = "local", 
                     options: Optional[Dict[str, str]] = None) -> bool:
        """
        Create a Docker volume.
        
        Args:
            volume_name: Name of the volume
            driver: Volume driver to use
            options: Driver-specific options
            
        Returns:
            bool: True if volume created successfully
        """
        try:
            if not self._validate_volume_name(volume_name):
                return False
            
            volume_path = self.volumes_path / volume_name
            if volume_path.exists():
                self.logger.warning(f"Volume {volume_name} already exists")
                return True
            
            # Create volume directory
            ensure_directory(str(volume_path))
            os.chmod(volume_path, 0o755)
            
            # Create volume metadata
            metadata = {
                "name": volume_name,
                "driver": driver,
                "mountpoint": str(volume_path),
                "created": str(Path(__file__).stat().st_mtime),
                "options": options or {}
            }
            
            if not self._save_volume_metadata(volume_name, metadata):
                return False
            
            self.logger.info(f"Created volume: {volume_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create volume {volume_name}: {e}")
            return False
    
    def remove_volume(self, volume_name: str, force: bool = False) -> bool:
        """
        Remove a Docker volume.
        
        Args:
            volume_name: Name of the volume to remove
            force: Force removal even if volume is in use
            
        Returns:
            bool: True if volume removed successfully
        """
        try:
            volume_path = self.volumes_path / volume_name
            if not volume_path.exists():
                self.logger.warning(f"Volume {volume_name} does not exist")
                return True
            
            # Check if volume is in use (simplified check)
            if not force and self._is_volume_in_use(volume_name):
                self.logger.error(f"Volume {volume_name} is in use")
                return False
            
            # Remove volume directory
            subprocess.run(["rm", "-rf", str(volume_path)], check=True)
            
            # Remove volume metadata
            self._remove_volume_metadata(volume_name)
            
            self.logger.info(f"Removed volume: {volume_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove volume {volume_name}: {e}")
            return False
    
    def create_bind_mount(self, host_path: str, container_path: str,
                         options: Optional[List[str]] = None) -> bool:
        """
        Create a bind mount configuration.
        
        Args:
            host_path: Path on host system
            container_path: Path in container
            options: Mount options
            
        Returns:
            bool: True if bind mount configured successfully
        """
        try:
            if not self._validate_bind_mount_path(host_path):
                return False
            
            host_path_obj = Path(host_path)
            if not host_path_obj.exists():
                self.logger.error(f"Host path does not exist: {host_path}")
                return False
            
            # Ensure host path has proper permissions
            if not self._setup_bind_mount_permissions(host_path):
                return False
            
            # Create bind mount metadata
            bind_mount_id = f"{hash(host_path + container_path)}"
            metadata = {
                "id": bind_mount_id,
                "host_path": host_path,
                "container_path": container_path,
                "options": options or ["rw", "relatime"],
                "created": str(Path(__file__).stat().st_mtime)
            }
            
            if not self._save_bind_mount_metadata(bind_mount_id, metadata):
                return False
            
            self.logger.info(f"Created bind mount: {host_path} -> {container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create bind mount: {e}")
            return False
    
    def _validate_volume_name(self, volume_name: str) -> bool:
        """Validate volume name."""
        if not volume_name or len(volume_name) > 255:
            self.logger.error("Invalid volume name length")
            return False
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in volume_name for char in invalid_chars):
            self.logger.error("Volume name contains invalid characters")
            return False
        
        return True
    
    def _validate_bind_mount_path(self, host_path: str) -> bool:
        """Validate bind mount host path for security."""
        host_path_obj = Path(host_path).resolve()
        
        # Check if path is in allowed directories
        for allowed_path in self.allowed_host_paths:
            if str(host_path_obj).startswith(allowed_path):
                return True
        
        self.logger.error(f"Host path not allowed for bind mount: {host_path}")
        return False
    
    def _setup_bind_mount_permissions(self, host_path: str) -> bool:
        """Set up proper permissions for bind mount host path."""
        try:
            host_path_obj = Path(host_path)
            
            # Ensure path is readable
            current_mode = host_path_obj.stat().st_mode
            if not (current_mode & 0o444):
                os.chmod(host_path_obj, current_mode | 0o644)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup bind mount permissions: {e}")
            return False
    
    def _save_volume_metadata(self, volume_name: str, metadata: Dict) -> bool:
        """Save volume metadata."""
        try:
            metadata_file = self.volumes_path / "metadata" / "volumes.json"
            
            # Load existing metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    all_metadata = json.load(f)
            else:
                all_metadata = {"volumes": {}, "version": "1.0"}
            
            # Add new volume metadata
            all_metadata["volumes"][volume_name] = metadata
            
            # Save updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(all_metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save volume metadata: {e}")
            return False
    
    def _remove_volume_metadata(self, volume_name: str) -> bool:
        """Remove volume metadata."""
        try:
            metadata_file = self.volumes_path / "metadata" / "volumes.json"
            
            if not metadata_file.exists():
                return True
            
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            
            if volume_name in all_metadata.get("volumes", {}):
                del all_metadata["volumes"][volume_name]
                
                with open(metadata_file, 'w') as f:
                    json.dump(all_metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove volume metadata: {e}")
            return False
    
    def _save_bind_mount_metadata(self, bind_mount_id: str, metadata: Dict) -> bool:
        """Save bind mount metadata."""
        try:
            bind_mounts_file = self.base_path / "bind-mounts" / "mounts.json"
            
            # Load existing metadata
            if bind_mounts_file.exists():
                with open(bind_mounts_file, 'r') as f:
                    all_metadata = json.load(f)
            else:
                all_metadata = {"bind_mounts": {}, "version": "1.0"}
                ensure_directory(str(bind_mounts_file.parent))
            
            # Add new bind mount metadata
            all_metadata["bind_mounts"][bind_mount_id] = metadata
            
            # Save updated metadata
            with open(bind_mounts_file, 'w') as f:
                json.dump(all_metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save bind mount metadata: {e}")
            return False
    
    def _is_volume_in_use(self, volume_name: str) -> bool:
        """Check if volume is currently in use (simplified check)."""
        # In a real implementation, this would check with Docker daemon
        # For now, just return False to allow removal
        return False
    
    def list_volumes(self) -> List[Dict]:
        """
        List all volumes.
        
        Returns:
            List of volume metadata dictionaries
        """
        try:
            metadata_file = self.volumes_path / "metadata" / "volumes.json"
            
            if not metadata_file.exists():
                return []
            
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            
            return list(all_metadata.get("volumes", {}).values())
            
        except Exception as e:
            self.logger.error(f"Failed to list volumes: {e}")
            return []
    
    def list_bind_mounts(self) -> List[Dict]:
        """
        List all bind mounts.
        
        Returns:
            List of bind mount metadata dictionaries
        """
        try:
            bind_mounts_file = self.base_path / "bind-mounts" / "mounts.json"
            
            if not bind_mounts_file.exists():
                return []
            
            with open(bind_mounts_file, 'r') as f:
                all_metadata = json.load(f)
            
            return list(all_metadata.get("bind_mounts", {}).values())
            
        except Exception as e:
            self.logger.error(f"Failed to list bind mounts: {e}")
            return []
    
    def cleanup_volumes(self, remove_unused: bool = False) -> bool:
        """
        Clean up volume storage.
        
        Args:
            remove_unused: Whether to remove unused volumes
            
        Returns:
            bool: True if cleanup successful
        """
        try:
            self.logger.info("Starting volume cleanup")
            
            # Clean up temporary mount points
            tmp_mounts_dir = self.base_path / "tmp-mounts"
            if tmp_mounts_dir.exists():
                subprocess.run(["rm", "-rf", str(tmp_mounts_dir)], check=True)
                ensure_directory(str(tmp_mounts_dir))
            
            if remove_unused:
                # Get list of volumes
                volumes = self.list_volumes()
                
                for volume in volumes:
                    volume_name = volume.get("name")
                    if volume_name and not self._is_volume_in_use(volume_name):
                        self.logger.info(f"Removing unused volume: {volume_name}")
                        self.remove_volume(volume_name, force=True)
            
            self.logger.info("Volume cleanup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup volumes: {e}")
            return False
    
    def validate_volume_setup(self) -> Dict[str, bool]:
        """
        Validate volume management setup.
        
        Returns:
            Dict[str, bool]: Validation results for each component
        """
        results = {}
        
        try:
            # Check directories exist
            results["directories"] = all([
                self.volumes_path.exists(),
                (self.volumes_path / "metadata").exists(),
                (self.base_path / "bind-mounts").exists()
            ])
            
            # Check permissions
            results["permissions"] = (
                oct(self.volumes_path.stat().st_mode)[-3:] == "755" and
                oct((self.volumes_path / "metadata").stat().st_mode)[-3:] == "700"
            )
            
            # Check metadata files
            metadata_file = self.volumes_path / "metadata" / "volumes.json"
            results["metadata"] = metadata_file.exists()
            
            # Check bind mount config
            results["bind_mount_config"] = self.bind_mounts_config.exists()
            
            # Test volume creation
            results["volume_creation"] = self._test_volume_creation()
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def _test_volume_creation(self) -> bool:
        """Test volume creation capability."""
        try:
            test_volume = "test-volume-validation"
            
            # Create test volume
            if not self.create_volume(test_volume):
                return False
            
            # Check if volume exists
            volume_path = self.volumes_path / test_volume
            if not volume_path.exists():
                return False
            
            # Remove test volume
            self.remove_volume(test_volume, force=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Volume creation test failed: {e}")
            return False
    
    def get_volume_info(self) -> Dict[str, any]:
        """
        Get volume management information.
        
        Returns:
            Dict containing volume information
        """
        info = {
            "volumes_path": str(self.volumes_path),
            "bind_mounts_config": str(self.bind_mounts_config),
            "total_volumes": 0,
            "total_bind_mounts": 0,
            "allowed_host_paths": self.allowed_host_paths
        }
        
        try:
            # Count volumes
            volumes = self.list_volumes()
            info["total_volumes"] = len(volumes)
            
            # Count bind mounts
            bind_mounts = self.list_bind_mounts()
            info["total_bind_mounts"] = len(bind_mounts)
            
            # Get storage usage
            if self.volumes_path.exists():
                statvfs = os.statvfs(self.volumes_path)
                info["storage_total"] = statvfs.f_frsize * statvfs.f_blocks
                info["storage_available"] = statvfs.f_frsize * statvfs.f_bavail
                info["storage_used"] = info["storage_total"] - info["storage_available"]
            
        except Exception as e:
            self.logger.error(f"Failed to get volume info: {e}")
            info["error"] = str(e)
        
        return info