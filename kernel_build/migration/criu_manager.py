"""
CRIU Manager for container checkpointing and restoration.

This module handles CRIU configuration, checkpoint creation, and validation
procedures for container migration.
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory, backup_file


@dataclass
class CheckpointConfig:
    """Configuration for CRIU checkpoint operations."""
    container_id: str
    checkpoint_dir: str
    leave_running: bool = False
    tcp_established: bool = True
    shell_job: bool = True
    ext_unix_sk: bool = True
    file_locks: bool = True


@dataclass
class CRIUStatus:
    """Status information for CRIU operations."""
    success: bool
    checkpoint_path: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class CRIUManager:
    """Manages CRIU integration for container checkpointing."""
    
    def __init__(self, criu_binary_path: str = "/data/local/tmp/criu", checkpoint_base_dir: str = None):
        """
        Initialize CRIU manager.
        
        Args:
            criu_binary_path: Path to CRIU binary on the device
            checkpoint_base_dir: Base directory for checkpoints (optional)
        """
        self.criu_binary = criu_binary_path
        self.logger = logging.getLogger(__name__)
        self.checkpoint_base_dir = checkpoint_base_dir or "/data/local/tmp/checkpoints"
    
    def configure_criu_environment(self) -> bool:
        """
        Configure CRIU environment and dependencies.
        
        Returns:
            bool: True if configuration successful, False otherwise
        """
        try:
            # Check if CRIU binary exists and is executable
            if not os.path.exists(self.criu_binary):
                self.logger.error(f"CRIU binary not found at {self.criu_binary}")
                return False
            
            # Make CRIU binary executable
            os.chmod(self.criu_binary, 0o755)
            
            # Check CRIU capabilities
            result = subprocess.run(
                [self.criu_binary, "check"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"CRIU check failed: {result.stderr}")
                return False
            
            self.logger.info("CRIU environment configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure CRIU environment: {e}")
            return False
    
    def validate_container_for_checkpoint(self, container_id: str) -> Tuple[bool, List[str]]:
        """
        Validate if container can be checkpointed.
        
        Args:
            container_id: Container ID to validate
            
        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []
        
        try:
            # Check if container exists and is running
            result = subprocess.run(
                ["docker", "inspect", container_id],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False, [f"Container {container_id} not found"]
            
            container_info = json.loads(result.stdout)[0]
            
            # Check container state
            if container_info["State"]["Status"] != "running":
                return False, [f"Container {container_id} is not running"]
            
            # Check for potentially problematic configurations
            config = container_info["Config"]
            host_config = container_info["HostConfig"]
            
            # Check for privileged mode
            if host_config.get("Privileged", False):
                warnings.append("Container is running in privileged mode")
            
            # Check for host network mode
            if host_config.get("NetworkMode") == "host":
                warnings.append("Container uses host networking")
            
            # Check for bind mounts
            if host_config.get("Binds"):
                warnings.append("Container has bind mounts")
            
            # Check for exposed ports
            if config.get("ExposedPorts"):
                warnings.append("Container has exposed ports")
            
            return True, warnings
            
        except Exception as e:
            self.logger.error(f"Failed to validate container: {e}")
            return False, [f"Validation error: {str(e)}"]
    
    def create_checkpoint(self, config: CheckpointConfig) -> CRIUStatus:
        """
        Create checkpoint of a container.
        
        Args:
            config: Checkpoint configuration
            
        Returns:
            CRIUStatus: Status of checkpoint operation
        """
        try:
            # Ensure base checkpoint directory exists
            ensure_directory(self.checkpoint_base_dir)
            
            # Validate container first
            is_valid, warnings = self.validate_container_for_checkpoint(config.container_id)
            if not is_valid:
                return CRIUStatus(
                    success=False,
                    error_message=f"Container validation failed: {warnings}"
                )
            
            # Create checkpoint directory
            checkpoint_path = os.path.join(self.checkpoint_base_dir, config.container_id)
            ensure_directory(checkpoint_path)
            
            # Get container PID
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Pid}}", config.container_id],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return CRIUStatus(
                    success=False,
                    error_message=f"Failed to get container PID: {result.stderr}"
                )
            
            container_pid = result.stdout.strip()
            
            # Build CRIU command
            criu_cmd = [
                self.criu_binary,
                "dump",
                "-t", container_pid,
                "-D", checkpoint_path,
                "-v4",
                "--log-file", os.path.join(checkpoint_path, "dump.log")
            ]
            
            # Add optional flags
            if config.leave_running:
                criu_cmd.append("--leave-running")
            if config.tcp_established:
                criu_cmd.append("--tcp-established")
            if config.shell_job:
                criu_cmd.append("--shell-job")
            if config.ext_unix_sk:
                criu_cmd.append("--ext-unix-sk")
            if config.file_locks:
                criu_cmd.append("--file-locks")
            
            # Execute CRIU dump
            self.logger.info(f"Creating checkpoint for container {config.container_id}")
            result = subprocess.run(criu_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return CRIUStatus(
                    success=False,
                    error_message=f"CRIU dump failed: {result.stderr}",
                    warnings=warnings
                )
            
            # Create checkpoint metadata
            metadata = {
                "container_id": config.container_id,
                "checkpoint_time": subprocess.run(["date", "-Iseconds"], capture_output=True, text=True).stdout.strip(),
                "architecture": "arm64",
                "kernel_version": subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip(),
                "docker_version": self._get_docker_version(),
                "warnings": warnings
            }
            
            with open(os.path.join(checkpoint_path, "metadata.json"), "w") as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Checkpoint created successfully at {checkpoint_path}")
            return CRIUStatus(
                success=True,
                checkpoint_path=checkpoint_path,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            return CRIUStatus(
                success=False,
                error_message=f"Checkpoint creation failed: {str(e)}"
            )
    
    def validate_checkpoint(self, checkpoint_path: str) -> CRIUStatus:
        """
        Validate checkpoint data integrity.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            
        Returns:
            CRIUStatus: Validation status
        """
        try:
            if not os.path.exists(checkpoint_path):
                return CRIUStatus(
                    success=False,
                    error_message=f"Checkpoint directory not found: {checkpoint_path}"
                )
            
            # Check for required files
            required_files = ["metadata.json", "dump.log"]
            missing_files = []
            
            for file_name in required_files:
                file_path = os.path.join(checkpoint_path, file_name)
                if not os.path.exists(file_path):
                    missing_files.append(file_name)
            
            if missing_files:
                return CRIUStatus(
                    success=False,
                    error_message=f"Missing checkpoint files: {missing_files}"
                )
            
            # Validate metadata
            metadata_path = os.path.join(checkpoint_path, "metadata.json")
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            required_metadata = ["container_id", "checkpoint_time", "architecture"]
            missing_metadata = [key for key in required_metadata if key not in metadata]
            
            if missing_metadata:
                return CRIUStatus(
                    success=False,
                    error_message=f"Missing metadata fields: {missing_metadata}"
                )
            
            # Check dump log for errors
            dump_log_path = os.path.join(checkpoint_path, "dump.log")
            with open(dump_log_path, "r") as f:
                log_content = f.read()
            
            warnings = []
            if "Error" in log_content:
                warnings.append("Errors found in dump log")
            if "Warning" in log_content:
                warnings.append("Warnings found in dump log")
            
            self.logger.info(f"Checkpoint validation successful: {checkpoint_path}")
            return CRIUStatus(
                success=True,
                checkpoint_path=checkpoint_path,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"Failed to validate checkpoint: {e}")
            return CRIUStatus(
                success=False,
                error_message=f"Checkpoint validation failed: {str(e)}"
            )
    
    def restore_checkpoint(self, checkpoint_path: str, container_id: str = None) -> CRIUStatus:
        """
        Restore container from checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            container_id: Optional new container ID
            
        Returns:
            CRIUStatus: Restore operation status
        """
        try:
            # Validate checkpoint first
            validation_status = self.validate_checkpoint(checkpoint_path)
            if not validation_status.success:
                return validation_status
            
            # Load metadata
            metadata_path = os.path.join(checkpoint_path, "metadata.json")
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            original_container_id = metadata["container_id"]
            target_container_id = container_id or original_container_id
            
            # Build CRIU restore command
            criu_cmd = [
                self.criu_binary,
                "restore",
                "-D", checkpoint_path,
                "-v4",
                "--log-file", os.path.join(checkpoint_path, "restore.log"),
                "--shell-job",
                "--ext-unix-sk",
                "--file-locks"
            ]
            
            # Execute CRIU restore
            self.logger.info(f"Restoring checkpoint from {checkpoint_path}")
            result = subprocess.run(criu_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return CRIUStatus(
                    success=False,
                    error_message=f"CRIU restore failed: {result.stderr}"
                )
            
            self.logger.info(f"Checkpoint restored successfully")
            return CRIUStatus(
                success=True,
                checkpoint_path=checkpoint_path
            )
            
        except Exception as e:
            self.logger.error(f"Failed to restore checkpoint: {e}")
            return CRIUStatus(
                success=False,
                error_message=f"Checkpoint restore failed: {str(e)}"
            )
    
    def _get_docker_version(self) -> str:
        """Get Docker version information."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"
    
    def list_checkpoints(self) -> List[Dict]:
        """
        List all available checkpoints.
        
        Returns:
            List of checkpoint information dictionaries
        """
        checkpoints = []
        
        try:
            if not os.path.exists(self.checkpoint_base_dir):
                return checkpoints
            
            for item in os.listdir(self.checkpoint_base_dir):
                checkpoint_path = os.path.join(self.checkpoint_base_dir, item)
                if os.path.isdir(checkpoint_path):
                    metadata_path = os.path.join(checkpoint_path, "metadata.json")
                    if os.path.exists(metadata_path):
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                        metadata["checkpoint_path"] = checkpoint_path
                        checkpoints.append(metadata)
            
            return checkpoints
            
        except Exception as e:
            self.logger.error(f"Failed to list checkpoints: {e}")
            return checkpoints
    
    def cleanup_checkpoint(self, checkpoint_path: str) -> bool:
        """
        Clean up checkpoint directory.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            
        Returns:
            bool: True if cleanup successful
        """
        try:
            if os.path.exists(checkpoint_path):
                subprocess.run(["rm", "-rf", checkpoint_path], check=True)
                self.logger.info(f"Checkpoint cleaned up: {checkpoint_path}")
                return True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup checkpoint: {e}")
            return False    

    def cleanup_checkpoint(self, checkpoint_path: str) -> bool:
        """
        Clean up checkpoint directory.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            
        Returns:
            bool: True if cleanup successful
        """
        try:
            if os.path.exists(checkpoint_path):
                subprocess.run(["rm", "-rf", checkpoint_path], check=True)
                self.logger.info(f"Checkpoint cleaned up: {checkpoint_path}")
                return True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup checkpoint: {e}")
            return False