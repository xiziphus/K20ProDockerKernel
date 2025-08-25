"""
Migration Orchestrator for cross-architecture container migration.

This module handles the orchestration of container migration from x86 to ARM64
platforms, including state validation, compatibility checking, and restore procedures.
"""

import os
import json
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_utils import ensure_directory

from .criu_manager import CRIUManager, CheckpointConfig, CRIUStatus
from .checkpoint_manager import CheckpointManager, TransferConfig


class MigrationStatus(Enum):
    """Migration status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationConfig:
    """Configuration for container migration."""
    container_id: str
    source_host: str
    target_host: str
    source_arch: str = "x86_64"
    target_arch: str = "aarch64"
    preserve_networking: bool = True
    preserve_volumes: bool = True
    rollback_on_failure: bool = True
    validation_timeout: int = 300  # seconds


@dataclass
class MigrationResult:
    """Result of migration operation."""
    success: bool
    status: MigrationStatus
    container_id: str
    source_checkpoint_path: Optional[str] = None
    target_checkpoint_path: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = None
    migration_time: Optional[float] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class CompatibilityCheck:
    """Container compatibility check result."""
    is_compatible: bool
    architecture_compatible: bool
    kernel_compatible: bool
    runtime_compatible: bool
    issues: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []


class MigrationOrchestrator:
    """Orchestrates cross-architecture container migration."""
    
    def __init__(self, work_dir: str = "/data/local/tmp/migration"):
        """
        Initialize migration orchestrator.
        
        Args:
            work_dir: Working directory for migration operations
        """
        self.work_dir = work_dir
        self.logger = logging.getLogger(__name__)
        
        # Initialize managers
        self.criu_manager = CRIUManager()
        self.checkpoint_manager = CheckpointManager(work_dir)
        
        # Migration state tracking
        self.active_migrations: Dict[str, MigrationResult] = {}
        
        # Ensure working directory exists
        ensure_directory(self.work_dir)
    
    def validate_migration_prerequisites(self, config: MigrationConfig) -> Tuple[bool, List[str]]:
        """
        Validate prerequisites for migration.
        
        Args:
            config: Migration configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Check if container exists on source
            result = subprocess.run(
                ["docker", "inspect", config.container_id],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                errors.append(f"Container {config.container_id} not found on source")
                return False, errors
            
            # Check container state
            container_info = json.loads(result.stdout)[0]
            if container_info["State"]["Status"] != "running":
                errors.append(f"Container {config.container_id} is not running")
            
            # Check CRIU availability
            if not self.criu_manager.configure_criu_environment():
                errors.append("CRIU environment not properly configured")
            
            # Check target host connectivity
            if config.target_host.startswith("adb:"):
                # Check ADB connectivity
                device_id = config.target_host.replace("adb:", "")
                adb_cmd = ["adb"]
                if device_id and device_id != "default":
                    adb_cmd.extend(["-s", device_id])
                adb_cmd.extend(["shell", "echo", "test"])
                
                result = subprocess.run(adb_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    errors.append(f"Cannot connect to target device: {config.target_host}")
            else:
                # Check SSH connectivity
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=10", config.target_host, "echo", "test"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    errors.append(f"Cannot connect to target host: {config.target_host}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Prerequisites validation failed: {str(e)}")
            return False, errors
    
    def check_container_compatibility(self, container_id: str, target_arch: str = "aarch64") -> CompatibilityCheck:
        """
        Check container compatibility for cross-architecture migration.
        
        Args:
            container_id: Container ID to check
            target_arch: Target architecture
            
        Returns:
            CompatibilityCheck: Compatibility assessment
        """
        try:
            # Get container information
            result = subprocess.run(
                ["docker", "inspect", container_id],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return CompatibilityCheck(
                    is_compatible=False,
                    architecture_compatible=False,
                    kernel_compatible=False,
                    runtime_compatible=False,
                    issues=[f"Container {container_id} not found"]
                )
            
            container_info = json.loads(result.stdout)[0]
            config = container_info["Config"]
            host_config = container_info["HostConfig"]
            
            issues = []
            recommendations = []
            
            # Check architecture compatibility
            architecture_compatible = True
            image_arch = config.get("Architecture", "unknown")
            if image_arch not in ["amd64", "arm64", "unknown"]:
                architecture_compatible = False
                issues.append(f"Unsupported image architecture: {image_arch}")
            
            # Check kernel compatibility
            kernel_compatible = True
            if host_config.get("Privileged", False):
                kernel_compatible = False
                issues.append("Privileged containers may not migrate properly")
                recommendations.append("Consider running without privileged mode")
            
            # Check runtime compatibility
            runtime_compatible = True
            
            # Check for host networking
            if host_config.get("NetworkMode") == "host":
                runtime_compatible = False
                issues.append("Host networking mode not compatible with migration")
                recommendations.append("Use bridge or custom network mode")
            
            # Check for device mounts
            devices = host_config.get("Devices", [])
            if devices:
                runtime_compatible = False
                issues.append("Device mounts may not be available on target")
                recommendations.append("Remove device dependencies or ensure target compatibility")
            
            # Check for volume mounts
            binds = host_config.get("Binds", [])
            if binds:
                issues.append("Host bind mounts may not exist on target")
                recommendations.append("Ensure bind mount paths exist on target or use volumes")
            
            # Check for capabilities
            cap_add = host_config.get("CapAdd", [])
            if cap_add:
                issues.append("Additional capabilities may not be available on target")
                recommendations.append("Verify capability support on target kernel")
            
            # Overall compatibility assessment
            is_compatible = architecture_compatible and kernel_compatible and runtime_compatible
            
            return CompatibilityCheck(
                is_compatible=is_compatible,
                architecture_compatible=architecture_compatible,
                kernel_compatible=kernel_compatible,
                runtime_compatible=runtime_compatible,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Failed to check container compatibility: {e}")
            return CompatibilityCheck(
                is_compatible=False,
                architecture_compatible=False,
                kernel_compatible=False,
                runtime_compatible=False,
                issues=[f"Compatibility check failed: {str(e)}"]
            )
    
    def migrate_container(self, config: MigrationConfig) -> MigrationResult:
        """
        Migrate container from source to target architecture.
        
        Args:
            config: Migration configuration
            
        Returns:
            MigrationResult: Migration operation result
        """
        import time
        start_time = time.time()
        
        # Initialize migration result
        result = MigrationResult(
            success=False,
            status=MigrationStatus.PENDING,
            container_id=config.container_id
        )
        
        # Track active migration
        self.active_migrations[config.container_id] = result
        
        try:
            self.logger.info(f"Starting migration of container {config.container_id}")
            result.status = MigrationStatus.IN_PROGRESS
            
            # Step 1: Validate prerequisites
            self.logger.info("Validating migration prerequisites...")
            is_valid, errors = self.validate_migration_prerequisites(config)
            if not is_valid:
                result.error_message = f"Prerequisites validation failed: {errors}"
                result.status = MigrationStatus.FAILED
                return result
            
            # Step 2: Check compatibility
            self.logger.info("Checking container compatibility...")
            compatibility = self.check_container_compatibility(config.container_id, config.target_arch)
            if not compatibility.is_compatible:
                result.error_message = f"Container not compatible: {compatibility.issues}"
                result.status = MigrationStatus.FAILED
                return result
            
            # Add compatibility warnings
            if compatibility.issues:
                result.warnings.extend(compatibility.issues)
            
            # Step 3: Create checkpoint on source
            self.logger.info("Creating checkpoint on source...")
            checkpoint_config = CheckpointConfig(
                container_id=config.container_id,
                checkpoint_dir=os.path.join(self.work_dir, "source_checkpoints"),
                leave_running=False,
                tcp_established=True,
                shell_job=True,
                ext_unix_sk=True,
                file_locks=True
            )
            
            checkpoint_status = self.criu_manager.create_checkpoint(checkpoint_config)
            if not checkpoint_status.success:
                result.error_message = f"Checkpoint creation failed: {checkpoint_status.error_message}"
                result.status = MigrationStatus.FAILED
                return result
            
            result.source_checkpoint_path = checkpoint_status.checkpoint_path
            result.warnings.extend(checkpoint_status.warnings)
            
            # Step 4: Package checkpoint
            self.logger.info("Packaging checkpoint for transfer...")
            package = self.checkpoint_manager.package_checkpoint(checkpoint_status.checkpoint_path)
            if not package:
                result.error_message = "Failed to package checkpoint"
                result.status = MigrationStatus.FAILED
                return result
            
            # Step 5: Transfer checkpoint to target
            self.logger.info("Transferring checkpoint to target...")
            transfer_config = TransferConfig(
                source_path=package.package_path,
                target_host=config.target_host,
                target_path=f"/data/local/tmp/migration/{config.container_id}_checkpoint.tar.gz",
                compression=True,
                verify_checksum=True,
                cleanup_source=False
            )
            
            if not self.checkpoint_manager.transfer_checkpoint(transfer_config):
                result.error_message = "Failed to transfer checkpoint to target"
                result.status = MigrationStatus.FAILED
                return result
            
            # Step 6: Restore container on target
            self.logger.info("Restoring container on target...")
            target_checkpoint_path = f"/data/local/tmp/migration/{config.container_id}_restored"
            
            # Unpack checkpoint on target
            if config.target_host.startswith("adb:"):
                device_id = config.target_host.replace("adb:", "")
                unpack_cmd = ["adb"]
                if device_id and device_id != "default":
                    unpack_cmd.extend(["-s", device_id])
                unpack_cmd.extend([
                    "shell",
                    f"cd /data/local/tmp/migration && tar -xzf {config.container_id}_checkpoint.tar.gz -C {config.container_id}_restored"
                ])
            else:
                unpack_cmd = [
                    "ssh", config.target_host,
                    f"cd /data/local/tmp/migration && tar -xzf {config.container_id}_checkpoint.tar.gz -C {config.container_id}_restored"
                ]
            
            unpack_result = subprocess.run(unpack_cmd, capture_output=True, text=True)
            if unpack_result.returncode != 0:
                result.error_message = f"Failed to unpack checkpoint on target: {unpack_result.stderr}"
                result.status = MigrationStatus.FAILED
                return result
            
            # Restore using CRIU on target
            if config.target_host.startswith("adb:"):
                device_id = config.target_host.replace("adb:", "")
                restore_cmd = ["adb"]
                if device_id and device_id != "default":
                    restore_cmd.extend(["-s", device_id])
                restore_cmd.extend([
                    "shell",
                    f"cd /data/local/tmp && LD_LIBRARY_PATH=/data/local/tmp/lib /data/local/tmp/criu restore -D {target_checkpoint_path} -v4 --shell-job --ext-unix-sk --file-locks"
                ])
            else:
                restore_cmd = [
                    "ssh", config.target_host,
                    f"cd /data/local/tmp && criu restore -D {target_checkpoint_path} -v4 --shell-job --ext-unix-sk --file-locks"
                ]
            
            restore_result = subprocess.run(restore_cmd, capture_output=True, text=True)
            if restore_result.returncode != 0:
                result.error_message = f"Failed to restore container on target: {restore_result.stderr}"
                result.status = MigrationStatus.FAILED
                
                # Attempt rollback if configured
                if config.rollback_on_failure:
                    self.logger.info("Attempting rollback...")
                    self._rollback_migration(config, result)
                
                return result
            
            result.target_checkpoint_path = target_checkpoint_path
            
            # Step 7: Validate migration success
            self.logger.info("Validating migration success...")
            if self._validate_migration_success(config, result):
                result.success = True
                result.status = MigrationStatus.COMPLETED
                result.migration_time = time.time() - start_time
                
                self.logger.info(f"Migration completed successfully in {result.migration_time:.2f} seconds")
            else:
                result.error_message = "Migration validation failed"
                result.status = MigrationStatus.FAILED
                
                # Attempt rollback if configured
                if config.rollback_on_failure:
                    self.logger.info("Attempting rollback...")
                    self._rollback_migration(config, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Migration failed with exception: {e}")
            result.error_message = f"Migration failed: {str(e)}"
            result.status = MigrationStatus.FAILED
            
            # Attempt rollback if configured
            if config.rollback_on_failure:
                self.logger.info("Attempting rollback...")
                self._rollback_migration(config, result)
            
            return result
        
        finally:
            # Clean up active migration tracking
            if config.container_id in self.active_migrations:
                del self.active_migrations[config.container_id]
    
    def _validate_migration_success(self, config: MigrationConfig, result: MigrationResult) -> bool:
        """
        Validate that migration was successful.
        
        Args:
            config: Migration configuration
            result: Migration result to update
            
        Returns:
            bool: True if validation successful
        """
        try:
            # Check if container is running on target
            if config.target_host.startswith("adb:"):
                device_id = config.target_host.replace("adb:", "")
                check_cmd = ["adb"]
                if device_id and device_id != "default":
                    check_cmd.extend(["-s", device_id])
                check_cmd.extend(["shell", "docker", "ps", "-q", "--filter", f"name={config.container_id}"])
            else:
                check_cmd = ["ssh", config.target_host, "docker", "ps", "-q", "--filter", f"name={config.container_id}"]
            
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if check_result.returncode == 0 and check_result.stdout.strip():
                self.logger.info("Container is running on target")
                return True
            else:
                self.logger.warning("Container not found running on target")
                result.warnings.append("Container validation failed - not running on target")
                return False
                
        except Exception as e:
            self.logger.error(f"Migration validation failed: {e}")
            result.warnings.append(f"Validation error: {str(e)}")
            return False
    
    def _rollback_migration(self, config: MigrationConfig, result: MigrationResult):
        """
        Rollback migration by restarting original container.
        
        Args:
            config: Migration configuration
            result: Migration result to update
        """
        try:
            self.logger.info("Rolling back migration...")
            
            # Restart original container if checkpoint was created with leave_running=False
            if result.source_checkpoint_path:
                # Try to restore from checkpoint on source
                restore_status = self.criu_manager.restore_checkpoint(result.source_checkpoint_path)
                if restore_status.success:
                    result.status = MigrationStatus.ROLLED_BACK
                    result.warnings.append("Migration rolled back successfully")
                    self.logger.info("Migration rolled back successfully")
                else:
                    result.warnings.append(f"Rollback failed: {restore_status.error_message}")
                    self.logger.error(f"Rollback failed: {restore_status.error_message}")
            else:
                result.warnings.append("No checkpoint available for rollback")
                
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            result.warnings.append(f"Rollback failed: {str(e)}")
    
    def get_migration_status(self, container_id: str) -> Optional[MigrationResult]:
        """
        Get status of active migration.
        
        Args:
            container_id: Container ID
            
        Returns:
            MigrationResult: Current migration status or None if not found
        """
        return self.active_migrations.get(container_id)
    
    def list_active_migrations(self) -> List[MigrationResult]:
        """
        List all active migrations.
        
        Returns:
            List of active migration results
        """
        return list(self.active_migrations.values())
    
    def cancel_migration(self, container_id: str) -> bool:
        """
        Cancel active migration.
        
        Args:
            container_id: Container ID
            
        Returns:
            bool: True if cancellation successful
        """
        if container_id in self.active_migrations:
            migration = self.active_migrations[container_id]
            migration.status = MigrationStatus.FAILED
            migration.error_message = "Migration cancelled by user"
            
            # Attempt cleanup
            try:
                if migration.source_checkpoint_path:
                    self.criu_manager.cleanup_checkpoint(migration.source_checkpoint_path)
                
                del self.active_migrations[container_id]
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to cleanup cancelled migration: {e}")
                return False
        
        return False