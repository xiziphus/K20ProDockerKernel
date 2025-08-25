# Kernel Patching System

This module provides a comprehensive patching system for Docker-enabled kernel builds. It includes patch application, verification, rollback capabilities, and specialized cpuset.c modification for Docker compatibility.

## Components

### 1. PatchEngine (`patch_engine.py`)
Handles the application of kernel patches with conflict detection and rollback capabilities.

**Features:**
- Apply multiple patches with dry-run support
- Automatic backup creation before applying patches
- Conflict detection and resolution
- Patch application verification
- Applied patches tracking

**Usage:**
```python
from kernel_build.patch import PatchEngine

engine = PatchEngine("path/to/kernel/source", "backup/directory")
results = engine.apply_patches(["kernel.diff", "aosp.diff"])
```

### 2. PatchVerifier (`patch_verifier.py`)
Provides verification functionality for patch application integrity.

**Features:**
- Patch file integrity verification
- Applied patch verification
- Baseline creation and verification
- File checksum validation

**Usage:**
```python
from kernel_build.patch import PatchVerifier

verifier = PatchVerifier("path/to/kernel/source")
result = verifier.verify_patch_application("kernel.diff")
```

### 3. PatchRollback (`patch_rollback.py`)
Manages rollback operations for applied patches and system state management.

**Features:**
- Individual patch rollback
- Bulk patch rollback
- Snapshot creation and restoration
- Multiple rollback methods (reverse patch, backup restore)

**Usage:**
```python
from kernel_build.patch import PatchRollback

rollback = PatchRollback("path/to/kernel/source", "backup/directory")
result = rollback.rollback_patch("kernel.diff")
```

### 4. CpusetHandler (`cpuset_handler.py`)
Specialized handler for modifying `kernel/cgroup/cpuset.c` to restore Docker-compatible cpuset prefixes.

**Features:**
- Automatic cpuset.c modification for Docker compatibility
- Backup and restore functionality
- Docker compatibility verification
- Required cpuset entries validation

**Usage:**
```python
from kernel_build.patch import CpusetHandler

handler = CpusetHandler("path/to/kernel/source")
result = handler.modify_cpuset_file()
```

## Command-Line Tools

### 1. Patch Tool (`scripts/patch_tool.py`)
General-purpose patch application tool.

```bash
# Apply patches
python kernel_build/scripts/patch_tool.py apply kernel.diff aosp.diff

# Verify patches
python kernel_build/scripts/patch_tool.py verify kernel.diff

# Rollback patches
python kernel_build/scripts/patch_tool.py rollback kernel.diff

# List applied patches
python kernel_build/scripts/patch_tool.py list

# Create snapshot
python kernel_build/scripts/patch_tool.py snapshot create my-snapshot
```

### 2. Cpuset Tool (`scripts/cpuset_tool.py`)
Specialized tool for cpuset.c modifications.

```bash
# Modify cpuset.c for Docker compatibility
python kernel_build/scripts/cpuset_tool.py modify

# Verify Docker compatibility
python kernel_build/scripts/cpuset_tool.py verify

# Show status
python kernel_build/scripts/cpuset_tool.py status

# Restore from backup
python kernel_build/scripts/cpuset_tool.py restore
```

### 3. Integration Tool (`scripts/patch_integration.py`)
Unified tool for complete Docker kernel patching workflow.

```bash
# Apply all patches and modifications
python kernel_build/scripts/patch_integration.py apply-all

# Show comprehensive status
python kernel_build/scripts/patch_integration.py status

# Rollback everything
python kernel_build/scripts/patch_integration.py rollback-all
```

## Docker-Required Modifications

### Kernel Configuration
The system applies the following Docker-required kernel configurations:
- Container namespaces (PID, NET, IPC, UTS, USER)
- Cgroup subsystems (memory, cpu, cpuset, devices, etc.)
- Network filtering and bridge support
- Overlay filesystem support
- Checkpoint/restore functionality

### Cpuset Modifications
The cpuset handler adds the following Docker-compatible entries to `kernel/cgroup/cpuset.c`:
- `cpuset.cpus` - CPU assignment control
- `cpuset.mems` - Memory node assignment
- `cpuset.effective_cpus` - Effective CPU list
- `cpuset.effective_mems` - Effective memory nodes
- `cpuset.cpu_exclusive` - CPU exclusivity control
- `cpuset.mem_exclusive` - Memory exclusivity control
- And other required cpuset control files

## Error Handling

The system provides comprehensive error handling:
- **Patch Application Errors**: Conflict detection, rollback on failure
- **File System Errors**: Permission issues, missing files
- **Verification Errors**: Checksum mismatches, missing entries
- **Backup Errors**: Backup creation/restoration failures

## Testing

Run tests using:
```bash
python kernel_build/tests/test_patch_engine.py
python kernel_build/tests/test_cpuset_handler.py
```

## Requirements Mapping

This implementation addresses the following requirements:
- **1.1**: Docker-required kernel configurations
- **1.2**: Container isolation and resource management
- **1.3**: Cgroup resource management and cpuset configuration
- **4.3**: CPU affinity and cpuset functionality
- **6.2**: Kernel patches and AOSP integration
- **7.1**: Android compatibility with Docker functionality

## Directory Structure

```
kernel_build/patch/
├── __init__.py              # Module initialization
├── patch_engine.py          # Main patch application engine
├── patch_verifier.py        # Patch verification system
├── patch_rollback.py        # Rollback and snapshot management
├── cpuset_handler.py        # Cpuset.c modification handler
└── README.md               # This documentation

kernel_build/scripts/
├── patch_tool.py           # General patch tool
├── cpuset_tool.py          # Cpuset modification tool
└── patch_integration.py    # Integrated workflow tool

kernel_build/tests/
├── test_patch_engine.py    # Patch engine tests
└── test_cpuset_handler.py  # Cpuset handler tests
```

## Best Practices

1. **Always create backups** before applying patches
2. **Use dry-run mode** to test patches before applying
3. **Verify patches** after application
4. **Create snapshots** before major modifications
5. **Test rollback procedures** in development environments
6. **Monitor logs** for detailed operation information

## Troubleshooting

### Common Issues

1. **Patch conflicts**: Use the conflict detection to identify issues
2. **Permission errors**: Ensure proper file system permissions
3. **Missing files**: Verify kernel source directory structure
4. **Backup failures**: Check disk space and permissions

### Debug Mode

Enable verbose logging for detailed information:
```bash
python kernel_build/scripts/patch_tool.py --verbose apply kernel.diff
```

## Integration with Build System

The patch system integrates with the broader kernel build system:
- Uses shared utilities from `kernel_build.utils`
- Follows the same logging and error handling patterns
- Compatible with the configuration management system
- Supports the automated build pipeline