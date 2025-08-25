# Docker-Enabled Kernel Build System

Comprehensive automated build system for creating Docker-enabled Android kernels, specifically targeting the Redmi K20 Pro (raphael) with PixelExperience ROM compatibility.

## 🎯 System Overview

This build system provides complete automation for:
- **Kernel Configuration Management** - Docker-required kernel options
- **Patch Application System** - Automated patching with rollback
- **Cpuset Compatibility Handler** - Docker cpuset prefix restoration
- **Build Validation & Testing** - Comprehensive verification
- **Integration Workflow** - End-to-end automation

## 🏗️ Architecture Components

### 📁 Configuration Management (`config/`)
- `config_manager.py` - Main configuration orchestration
- `kernel_config.py` - Kernel config parsing and validation
- `applier.py` - Configuration application and merging
- `validator.py` - Docker compatibility validation

### 🔧 Patch System (`patch/`)
- `patch_engine.py` - Core patch application engine
- `patch_verifier.py` - Patch integrity verification
- `patch_rollback.py` - Rollback and snapshot management
- `cpuset_handler.py` - Docker cpuset compatibility fixes

### 🛠️ Command-Line Tools (`scripts/`)
- `config_tool.py` - Kernel configuration management
- `patch_tool.py` - Patch application and verification
- `cpuset_tool.py` - Cpuset modification tool
- `patch_integration.py` - **Unified workflow automation**

### 🧪 Testing Suite (`tests/`)
- `test_config.py` - Configuration system tests
- `test_patch_engine.py` - Patch system tests
- `test_cpuset_handler.py` - Cpuset handler tests

### 🔧 Utilities (`utils/`)
- `file_utils.py` - File operations and backup management

## 🚀 Quick Start

### One-Command Setup (Recommended)
```bash
# Apply all patches and modifications
python scripts/patch_integration.py apply-all

# Check status
python scripts/patch_integration.py status
```

### Individual Operations
```bash
# Kernel configuration
python scripts/config_tool.py apply ../files/raphael_defconfig

# Apply patches
python scripts/patch_tool.py apply ../files/kernel.diff ../files/aosp.diff

# Fix cpuset for Docker
python scripts/cpuset_tool.py modify

# Verify everything
python scripts/patch_tool.py verify ../files/kernel.diff
python scripts/cpuset_tool.py verify
```

## 📋 Docker-Required Modifications

### Kernel Configuration Options
- **Container Namespaces**: PID, NET, IPC, UTS, USER namespaces
- **Cgroup Subsystems**: memory, cpu, cpuset, devices, pids, etc.
- **Network Support**: Bridge, iptables, netfilter, VXLAN, MACVLAN
- **Storage Support**: Overlay FS, device mapper, thin provisioning
- **Security**: Checkpoint/restore, user namespaces, capabilities

### Cpuset Compatibility (Docker-Critical)
Restores 14 Docker-required cpuset control files:
- `cpuset.cpus`, `cpuset.mems`, `cpuset.effective_cpus`
- `cpuset.cpu_exclusive`, `cpuset.mem_exclusive`
- `cpuset.sched_load_balance`, `cpuset.memory_migrate`
- And 7 additional cpuset control interfaces

### Kernel Patches Applied
- **kernel.diff**: Docker-required kernel modifications
- **aosp.diff**: AOSP build system integration
- **Memory management**: Container-optimized memory handling
- **Cgroup fixes**: Docker-compatible cgroup interface restoration

## 📊 Build Outputs

### Generated Files
```
output/
├── docker_raphael_defconfig    # Final Docker-enabled configuration
├── applied_raphael_defconfig   # Applied configuration
├── merged_config              # Merged configuration file
└── exported_configs/          # Exported configurations

backups/
├── patches/                   # Patch backups and rollback data
├── cpuset/                    # Cpuset.c backups
└── config/                    # Configuration backups
```

### Verification Reports
- Configuration validation reports
- Patch application status
- Docker compatibility verification
- Build system integration status

## 🔍 ROM Compatibility

### ✅ Fully Compatible
- **PixelExperience (PE)** - Primary target ROM
- **LineageOS** - High compatibility
- **AOSP-based ROMs** - Standard compatibility

### ⚠️ May Need Adjustments
- **MIUI** - Heavily modified, requires testing
- **Custom ROMs** - Device-specific testing needed

## 🛡️ Error Handling & Recovery

### Automatic Backup System
- Pre-modification backups for all files
- Snapshot creation before major changes
- Rollback capabilities for failed operations

### Verification & Validation
- Patch integrity verification
- Configuration validation
- Docker compatibility testing
- Build system integration checks

### Recovery Options
```bash
# Rollback specific patch
python scripts/patch_tool.py rollback ../files/kernel.diff

# Restore cpuset.c
python scripts/cpuset_tool.py restore

# Complete system rollback
python scripts/patch_integration.py rollback-all
```

## 📈 Advanced Features

### Snapshot Management
```bash
# Create system snapshot
python scripts/patch_tool.py snapshot create pre-docker-build

# List snapshots
python scripts/patch_tool.py snapshot list

# Restore from snapshot
python scripts/patch_tool.py snapshot restore pre-docker-build
```

### Dry-Run Mode
```bash
# Test patches without applying
python scripts/patch_tool.py apply --dry-run ../files/kernel.diff

# Test complete workflow
python scripts/patch_integration.py apply-all --dry-run
```

### Verbose Debugging
```bash
# Enable detailed logging
python scripts/patch_integration.py --verbose apply-all
```

## 🔧 System Requirements

- **Python 3.6+** with standard libraries
- **Android kernel source** for Redmi K20 Pro (raphael)
- **Build environment** with proper toolchain
- **File system permissions** for kernel source modification

## 🎯 Integration with AOSP Build

The system integrates seamlessly with AOSP build processes:
1. **Pre-build**: Apply patches and configurations
2. **Build**: Use standard AOSP kernel build
3. **Post-build**: Verify Docker compatibility
4. **Deploy**: Flash kernel to device

## 📚 Documentation

- `patch/README.md` - Detailed patch system documentation
- Individual script `--help` options for usage
- Comprehensive error messages and logging
- Test suites for validation

## 🤝 Contributing

When modifying the build system:
1. **Add tests** for new functionality
2. **Update documentation** for changes
3. **Verify compatibility** with existing workflows
4. **Test rollback procedures** for new features

## 🔄 Legacy Configuration System

The original configuration management system is still available:

### Command Line Tool
```bash
# Validate existing kernel configuration
python scripts/config_tool.py validate --defconfig ../files/raphael_defconfig

# Generate Docker-enabled configuration
python scripts/config_tool.py generate --defconfig ../files/raphael_defconfig

# Show configuration summary
python scripts/config_tool.py summary --defconfig ../files/raphael_defconfig
```

### Python API
```python
from kernel_build.config.config_manager import ConfigurationManager

# Initialize configuration manager
config_manager = ConfigurationManager()

# Load and validate configuration
config_manager.load_kernel_config('../files/raphael_defconfig')
is_valid, report = config_manager.validate_configuration()
```

## 🧪 Testing

Run the comprehensive test suite:
```bash
# Run all tests
python tests/test_config.py
python tests/test_patch_engine.py
python tests/test_cpuset_handler.py

# Test individual components
python -c "from kernel_build.patch import PatchEngine; print('Patch system OK')"
python -c "from kernel_build.patch import CpusetHandler; print('Cpuset handler OK')"
```