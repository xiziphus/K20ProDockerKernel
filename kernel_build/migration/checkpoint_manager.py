"""
Checkpoint Manager for container migration data management.

This module handles checkpoint data management, compression, transfer,
and validation for cross-architecture container migration.
"""

import os
import json
import tarfile
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory


@dataclass
class TransferConfig:
    """Configuration for checkpoint transfer operations."""
    source_path: str
    target_host: str
    target_path: str
    compression: bool = True
    verify_checksum: bool = True
    cleanup_source: bool = False


@dataclass
class CheckpointPackage:
    """Information about a packaged checkpoint."""
    package_path: str
    checksum: str
    size_bytes: int
    container_id: str
    metadata: Dict


class CheckpointManager:
    """Manages checkpoint data packaging, transfer, and validation."""
    
    def __init__(self, work_dir: str = "/data/local/tmp/migration"):
        """
        Initialize checkpoint manager.
        
        Args:
            work_dir: Working directory for checkpoint operations
        """
        self.work_dir = work_dir
        self.logger = logging.getLogger(__name__)
        
        # Ensure working directory exists
        ensure_directory(self.work_dir)
    
    def package_checkpoint(self, checkpoint_path: str, output_path: str = None) -> Optional[CheckpointPackage]:
        """
        Package checkpoint directory into transferable archive.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            output_path: Optional output path for package
            
        Returns:
            CheckpointPackage: Package information or None if failed
        """
        try:
            if not os.path.exists(checkpoint_path):
                self.logger.error(f"Checkpoint directory not found: {checkpoint_path}")
                return None
            
            # Load checkpoint metadata
            metadata_path = os.path.join(checkpoint_path, "metadata.json")
            if not os.path.exists(metadata_path):
                self.logger.error(f"Checkpoint metadata not found: {metadata_path}")
                return None
            
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            container_id = metadata.get("container_id", "unknown")
            
            # Generate package path if not provided
            if output_path is None:
                package_name = f"{container_id}_checkpoint.tar.gz"
                output_path = os.path.join(self.work_dir, package_name)
            
            # Create compressed archive
            self.logger.info(f"Packaging checkpoint: {checkpoint_path} -> {output_path}")
            
            with tarfile.open(output_path, "w:gz") as tar:
                # Add all files from checkpoint directory
                for root, dirs, files in os.walk(checkpoint_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, checkpoint_path)
                        tar.add(file_path, arcname=arcname)
            
            # Calculate checksum
            checksum = self._calculate_checksum(output_path)
            
            # Get package size
            size_bytes = os.path.getsize(output_path)
            
            # Create package info
            package = CheckpointPackage(
                package_path=output_path,
                checksum=checksum,
                size_bytes=size_bytes,
                container_id=container_id,
                metadata=metadata
            )
            
            # Save package metadata
            package_metadata = {
                "package_path": output_path,
                "checksum": checksum,
                "size_bytes": size_bytes,
                "container_id": container_id,
                "original_metadata": metadata,
                "package_time": subprocess.run(["date", "-Iseconds"], capture_output=True, text=True).stdout.strip()
            }
            
            metadata_file = output_path + ".metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(package_metadata, f, indent=2)
            
            self.logger.info(f"Checkpoint packaged successfully: {output_path}")
            return package
            
        except Exception as e:
            self.logger.error(f"Failed to package checkpoint: {e}")
            return None
    
    def unpack_checkpoint(self, package_path: str, output_dir: str = None) -> Optional[str]:
        """
        Unpack checkpoint archive to directory.
        
        Args:
            package_path: Path to checkpoint package
            output_dir: Optional output directory
            
        Returns:
            str: Path to unpacked checkpoint directory or None if failed
        """
        try:
            if not os.path.exists(package_path):
                self.logger.error(f"Package not found: {package_path}")
                return None
            
            # Verify package integrity
            if not self.verify_package_integrity(package_path):
                self.logger.error(f"Package integrity check failed: {package_path}")
                return None
            
            # Load package metadata
            metadata_file = package_path + ".metadata.json"
            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    package_metadata = json.load(f)
                container_id = package_metadata.get("container_id", "unknown")
            else:
                container_id = "unknown"
            
            # Generate output directory if not provided
            if output_dir is None:
                output_dir = os.path.join(self.work_dir, f"{container_id}_restored")
            
            ensure_directory(output_dir)
            
            # Extract archive
            self.logger.info(f"Unpacking checkpoint: {package_path} -> {output_dir}")
            
            with tarfile.open(package_path, "r:gz") as tar:
                tar.extractall(path=output_dir)
            
            self.logger.info(f"Checkpoint unpacked successfully: {output_dir}")
            return output_dir
            
        except Exception as e:
            self.logger.error(f"Failed to unpack checkpoint: {e}")
            return None
    
    def transfer_checkpoint(self, config: TransferConfig) -> bool:
        """
        Transfer checkpoint package to target host.
        
        Args:
            config: Transfer configuration
            
        Returns:
            bool: True if transfer successful
        """
        try:
            if not os.path.exists(config.source_path):
                self.logger.error(f"Source package not found: {config.source_path}")
                return False
            
            # Verify package integrity before transfer
            if config.verify_checksum and not self.verify_package_integrity(config.source_path):
                self.logger.error(f"Source package integrity check failed")
                return False
            
            # Build transfer command (using adb for Android device transfer)
            if config.target_host.startswith("adb:"):
                # Transfer to Android device via ADB
                device_id = config.target_host.replace("adb:", "")
                
                transfer_cmd = ["adb"]
                if device_id and device_id != "default":
                    transfer_cmd.extend(["-s", device_id])
                
                transfer_cmd.extend(["push", config.source_path, config.target_path])
                
                # Also transfer metadata file if it exists
                metadata_file = config.source_path + ".metadata.json"
                if os.path.exists(metadata_file):
                    metadata_target = config.target_path + ".metadata.json"
                    metadata_cmd = transfer_cmd[:-2] + [metadata_file, metadata_target]
                    
                    result = subprocess.run(metadata_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        self.logger.warning(f"Failed to transfer metadata: {result.stderr}")
            
            else:
                # Transfer to remote host via SCP
                transfer_cmd = [
                    "scp",
                    config.source_path,
                    f"{config.target_host}:{config.target_path}"
                ]
                
                # Also transfer metadata file if it exists
                metadata_file = config.source_path + ".metadata.json"
                if os.path.exists(metadata_file):
                    metadata_target = f"{config.target_host}:{config.target_path}.metadata.json"
                    metadata_cmd = ["scp", metadata_file, metadata_target]
                    
                    result = subprocess.run(metadata_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        self.logger.warning(f"Failed to transfer metadata: {result.stderr}")
            
            # Execute transfer
            self.logger.info(f"Transferring checkpoint: {config.source_path} -> {config.target_host}:{config.target_path}")
            result = subprocess.run(transfer_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Transfer failed: {result.stderr}")
                return False
            
            # Verify transfer if requested
            if config.verify_checksum:
                if not self._verify_remote_checksum(config):
                    self.logger.error("Remote checksum verification failed")
                    return False
            
            # Cleanup source if requested
            if config.cleanup_source:
                try:
                    os.remove(config.source_path)
                    metadata_file = config.source_path + ".metadata.json"
                    if os.path.exists(metadata_file):
                        os.remove(metadata_file)
                    self.logger.info(f"Source package cleaned up: {config.source_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup source: {e}")
            
            self.logger.info("Checkpoint transfer completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to transfer checkpoint: {e}")
            return False
    
    def verify_package_integrity(self, package_path: str) -> bool:
        """
        Verify package integrity using checksum.
        
        Args:
            package_path: Path to package file
            
        Returns:
            bool: True if integrity check passes
        """
        try:
            metadata_file = package_path + ".metadata.json"
            if not os.path.exists(metadata_file):
                self.logger.warning(f"No metadata file found for integrity check: {metadata_file}")
                return True  # Skip verification if no metadata
            
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
            
            expected_checksum = metadata.get("checksum")
            if not expected_checksum:
                self.logger.warning("No checksum found in metadata")
                return True
            
            actual_checksum = self._calculate_checksum(package_path)
            
            if actual_checksum != expected_checksum:
                self.logger.error(f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}")
                return False
            
            self.logger.info("Package integrity verification passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to verify package integrity: {e}")
            return False
    
    def get_package_info(self, package_path: str) -> Optional[Dict]:
        """
        Get information about a checkpoint package.
        
        Args:
            package_path: Path to package file
            
        Returns:
            Dict: Package information or None if failed
        """
        try:
            if not os.path.exists(package_path):
                return None
            
            info = {
                "package_path": package_path,
                "size_bytes": os.path.getsize(package_path),
                "checksum": self._calculate_checksum(package_path)
            }
            
            # Load metadata if available
            metadata_file = package_path + ".metadata.json"
            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                info.update(metadata)
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get package info: {e}")
            return None
    
    def list_packages(self, directory: str = None) -> List[Dict]:
        """
        List all checkpoint packages in directory.
        
        Args:
            directory: Directory to search (defaults to work_dir)
            
        Returns:
            List of package information dictionaries
        """
        packages = []
        search_dir = directory or self.work_dir
        
        try:
            if not os.path.exists(search_dir):
                return packages
            
            for item in os.listdir(search_dir):
                if item.endswith(".tar.gz") and not item.endswith(".metadata.json"):
                    package_path = os.path.join(search_dir, item)
                    package_info = self.get_package_info(package_path)
                    if package_info:
                        packages.append(package_info)
            
            return packages
            
        except Exception as e:
            self.logger.error(f"Failed to list packages: {e}")
            return packages
    
    def cleanup_package(self, package_path: str) -> bool:
        """
        Clean up checkpoint package and associated files.
        
        Args:
            package_path: Path to package file
            
        Returns:
            bool: True if cleanup successful
        """
        try:
            files_to_remove = [package_path]
            
            # Add metadata file if it exists
            metadata_file = package_path + ".metadata.json"
            if os.path.exists(metadata_file):
                files_to_remove.append(metadata_file)
            
            for file_path in files_to_remove:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.info(f"Removed file: {file_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup package: {e}")
            return False
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _verify_remote_checksum(self, config: TransferConfig) -> bool:
        """Verify checksum of transferred file on remote host."""
        try:
            # Get local checksum
            local_checksum = self._calculate_checksum(config.source_path)
            
            if config.target_host.startswith("adb:"):
                # Verify on Android device
                device_id = config.target_host.replace("adb:", "")
                
                cmd = ["adb"]
                if device_id and device_id != "default":
                    cmd.extend(["-s", device_id])
                
                cmd.extend(["shell", "sha256sum", config.target_path])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    return False
                
                remote_checksum = result.stdout.split()[0]
            
            else:
                # Verify on remote host via SSH
                cmd = [
                    "ssh",
                    config.target_host,
                    f"sha256sum {config.target_path}"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    return False
                
                remote_checksum = result.stdout.split()[0]
            
            return local_checksum == remote_checksum
            
        except Exception as e:
            self.logger.error(f"Failed to verify remote checksum: {e}")
            return False