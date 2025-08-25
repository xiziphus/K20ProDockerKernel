# Container Migration System

This module provides comprehensive container migration capabilities for the Docker-enabled Android kernel project. It enables cross-architecture migration of containers from x86 to ARM64 platforms using CRIU (Checkpoint/Restore In Userspace) technology.

## Features

- **CRIU Integration**: Complete CRIU setup and management for container checkpointing
- **Cross-Architecture Migration**: Migrate containers from x86 to ARM64 Android devices
- **Checkpoint Management**: Package, transfer, and validate checkpoint data
- **Compatibility Checking**: Validate container compatibility before migration
- **Rollback Support**: Automatic rollback on migration failure
- **Progress Tracking**: Monitor active migrations and their status

## Components

### 1. CRIU Manager (`criu_manager.py`)

Handles CRIU integration for container checkpointing and restoration.

**Key Features:**
- CRIU environment configuration and validation
- Container checkpoint creation with validation
- Checkpoint restoration with error handling
- Container compatibility checking for CRIU operations

**Usage:**
```python
from migration.criu_manager import CRIUManager, CheckpointConfig

manager = CRIUManager("/data/local/tmp/criu")
config = CheckpointConfig(
    container_id="my_container",
    checkpoint_dir="/data/local/tmp/checkpoints"
)

# Create checkpoint
status = manager.create_checkpoint(config)
if status.success:
    print(f"Checkpoint created at: {status.checkpoint_path}")
```

### 2. Checkpoint Manager (`checkpoint_manager.py`)

Manages checkpoint data packaging, transfer, and validation.

**Key Features:**
- Checkpoint packaging into transferable archives
- Secure transfer via ADB or SSH
- Checksum verification for data integrity
- Checkpoint unpacking and validation

**Usage:**
```python
from migration.checkpoint_manager import CheckpointManager, TransferConfig

manager = CheckpointManager()

# Package checkpoint
package = manager.package_checkpoint("/path/to/checkpoint")

# Transfer to target device
config = TransferConfig(
    source_path=package.package_path,
    target_host="adb:device_id",
    target_path="/data/local/tmp/checkpoint.tar.gz"
)
success = manager.transfer_checkpoint(config)
```

### 3. Migration Orchestrator (`migration_orchestrator.py`)

Orchestrates the complete migration process from source to target.

**Key Features:**
- End-to-end migration orchestration
- Prerequisites validation
- Container compatibility assessment
- Migration progress tracking
- Automatic rollback on failure

**Usage:**
```python
from migration.migration_orchestrator import MigrationOrchestrator, MigrationConfig

orchestrator = MigrationOrchestrator()
config = MigrationConfig(
    container_id="my_container",
    source_host="localhost",
    target_host="adb:device_id"
)

# Perform migration
result = orchestrator.migrate_container(config)
if result.success:
    print("Migration completed successfully!")
```

## Command Line Interface

The migration system includes a comprehensive CLI tool for container migration operations.

### Installation and Setup

1. **Install CRIU on target device:**
```bash
python kernel_build/scripts/criu_setup.py --verbose
```

2. **Verify CRIU installation:**
```bash
python kernel_build/scripts/criu_setup.py --test-only
```

### Migration Commands

#### Check Container Compatibility
```bash
python kernel_build/scripts/migrate_container.py check my_container
```

#### Perform Migration (Dry Run)
```bash
python kernel_build/scripts/migrate_container.py migrate my_container adb:device_id --dry-run
```

#### Perform Actual Migration
```bash
python kernel_build/scripts/migrate_container.py migrate my_container adb:device_id
```

#### List Active Migrations
```bash
python kernel_build/scripts/migrate_container.py list
```

#### Cancel Migration
```bash
python kernel_build/scripts/migrate_container.py cancel my_container
```

### Advanced Options

- `--source-arch`: Source architecture (default: x86_64)
- `--target-arch`: Target architecture (default: aarch64)
- `--no-preserve-networking`: Don't preserve network configuration
- `--no-preserve-volumes`: Don't preserve volume mounts
- `--no-rollback`: Don't rollback on failure
- `--verbose`: Enable detailed logging

## Migration Process

The migration process follows these steps:

1. **Prerequisites Validation**
   - Verify container exists and is running
   - Check CRIU environment configuration
   - Validate target host connectivity

2. **Compatibility Assessment**
   - Check architecture compatibility
   - Validate kernel feature requirements
   - Assess runtime configuration compatibility

3. **Checkpoint Creation**
   - Create CRIU checkpoint of running container
   - Validate checkpoint integrity
   - Package checkpoint for transfer

4. **Transfer to Target**
   - Securely transfer checkpoint package
   - Verify transfer integrity with checksums
   - Prepare target environment

5. **Restoration on Target**
   - Unpack checkpoint on target device
   - Restore container using CRIU
   - Validate successful restoration

6. **Migration Validation**
   - Verify container is running on target
   - Validate application functionality
   - Complete migration or trigger rollback

## Compatibility Requirements

### Container Requirements
- Container must be running on source system
- No privileged mode (recommended)
- Bridge or custom networking (not host networking)
- Minimal device dependencies
- Standard filesystem usage

### System Requirements
- CRIU installed and configured on both systems
- Docker daemon running on target
- Network connectivity between source and target
- Sufficient storage space for checkpoints

### Architecture Support
- **Source**: x86_64 (Intel/AMD)
- **Target**: aarch64 (ARM64)
- **Images**: Multi-architecture or architecture-neutral

## Error Handling and Rollback

The migration system includes comprehensive error handling:

- **Automatic Rollback**: Failed migrations can automatically restore the original container
- **Detailed Logging**: Complete operation logs for troubleshooting
- **Status Tracking**: Real-time migration status monitoring
- **Recovery Procedures**: Manual recovery options for edge cases

## Testing

The migration system includes comprehensive unit tests:

```bash
# Test CRIU manager
python kernel_build/tests/test_criu_manager.py

# Test checkpoint manager
python kernel_build/tests/test_checkpoint_manager.py

# Test migration orchestrator
python kernel_build/tests/test_migration_orchestrator.py
```

## Configuration Files

### CRIU Configuration (`criu_config.json`)
```json
{
  "default_options": {
    "leave_running": false,
    "tcp_established": true,
    "shell_job": true,
    "ext_unix_sk": true,
    "file_locks": true
  },
  "checkpoint_dir": "/data/local/tmp/checkpoints",
  "work_dir": "/data/local/tmp/migration",
  "criu_binary": "/data/local/tmp/criu",
  "log_level": "info"
}
```

## Troubleshooting

### Common Issues

1. **CRIU Check Fails**
   - Verify kernel supports required features
   - Check CRIU binary permissions
   - Ensure all dependencies are installed

2. **Container Not Compatible**
   - Remove privileged mode
   - Change from host to bridge networking
   - Minimize device dependencies

3. **Transfer Fails**
   - Check network connectivity
   - Verify target device storage space
   - Validate ADB/SSH connectivity

4. **Restore Fails**
   - Check target kernel compatibility
   - Verify Docker daemon is running
   - Review CRIU restore logs

### Debug Mode

Enable verbose logging for detailed troubleshooting:
```bash
python kernel_build/scripts/migrate_container.py migrate my_container adb:device_id --verbose
```

## Performance Considerations

- **Checkpoint Size**: Depends on container memory usage and filesystem changes
- **Transfer Time**: Varies with network speed and checkpoint size
- **Restore Time**: Typically faster than checkpoint creation
- **Downtime**: Brief interruption during checkpoint and restore phases

## Security Considerations

- **Checkpoint Data**: Contains complete container state including sensitive data
- **Transfer Security**: Use secure channels (SSH) for remote transfers
- **Access Control**: Restrict access to checkpoint directories
- **Cleanup**: Automatically clean up temporary files after migration

## Future Enhancements

- Support for additional architectures
- Live migration with minimal downtime
- Incremental checkpoint transfers
- Migration scheduling and automation
- Integration with container orchestration platforms