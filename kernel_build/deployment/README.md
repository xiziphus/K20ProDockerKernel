# Kernel Deployment Tools

This directory contains tools for deploying Docker-enabled kernels to Redmi K20 Pro (raphael) devices with automated flashing, validation, and rollback capabilities.

## 🚀 Quick Start

### Deploy a Kernel
```bash
# Deploy kernel with full validation
./deploy.sh deploy boot.img

# Deploy without backup (faster, but riskier)
python3 kernel_build/scripts/deploy_kernel.py deploy boot.img --skip-backup

# Deploy without validation
python3 kernel_build/scripts/deploy_kernel.py deploy boot.img --skip-validation
```

### Check Device Status
```bash
# Check device and tools
./deploy.sh check

# Validate current deployment
./deploy.sh validate
```

### Backup and Rollback
```bash
# Backup current kernel
./deploy.sh backup

# Rollback to previous kernel
./deploy.sh rollback kernel_build/backups/kernels/boot_backup_20250825_120000.img
```

## 📋 Prerequisites

### Required Tools
- **fastboot** - Android SDK Platform Tools
- **Python 3.6+** - For deployment scripts
- **adb** (optional) - For validation and advanced features

### Device Requirements
- **Redmi K20 Pro (raphael)** or **Redmi K20 Pro India (raphaelin)**
- **Unlocked bootloader**
- **USB debugging enabled** (for validation)
- **Device in fastboot mode** (for kernel flashing)

### Installation
```bash
# Run automated setup
./setup.sh

# Or install manually
# Ubuntu/Debian:
sudo apt-get install android-tools-fastboot android-tools-adb

# macOS with Homebrew:
brew install android-platform-tools
```

## 🛠️ Deployment Process

### 1. Pre-Deployment Checks
- ✅ Verify fastboot availability
- ✅ Detect and validate target device
- ✅ Check kernel image integrity
- ✅ Create kernel backup (if possible)

### 2. Kernel Flashing
- ⚡ Flash kernel to boot partition
- 🔄 Automatic device reboot
- ⏳ Wait for device to come online

### 3. Post-Deployment Validation
- 🔍 Verify kernel version
- 🐳 Check Docker kernel features
- 📊 Validate cgroup subsystems
- 🔒 Test namespace support
- 💾 Verify overlay filesystem

## 📁 File Structure

```
kernel_build/
├── scripts/
│   ├── deploy_kernel.py      # Main deployment script
│   ├── validate_deployment.py # Validation script
│   └── install_setup.py      # Setup script
├── config/
│   └── deployment_config.json # Deployment configuration
├── backups/
│   └── kernels/              # Kernel backups
└── logs/
    ├── deployment.log        # Deployment history
    └── validation_report.txt # Latest validation report
```

## ⚙️ Configuration

### Device Profiles
The deployment system supports multiple device profiles in `deployment_config.json`:

```json
{
  "device_profiles": {
    "raphael": {
      "codename": "raphael",
      "model": "Redmi K20 Pro",
      "fastboot_id": "raphael",
      "partitions": {
        "boot": "boot",
        "recovery": "recovery"
      }
    }
  }
}
```

### Safety Settings
```json
{
  "safety_checks": {
    "require_backup": true,
    "confirm_device_compatibility": true,
    "validate_kernel_image": true
  }
}
```

## 🔍 Validation Features

### Docker Kernel Features
- `/proc/cgroups` - Cgroup subsystems
- `/sys/fs/cgroup` - Cgroup filesystem
- `/proc/sys/kernel/ns_last_pid` - Namespace support

### Cgroup Subsystems
- `memory` - Memory control
- `cpu` - CPU control
- `cpuset` - CPU affinity
- `devices` - Device access control
- `pids` - Process limit control
- `freezer` - Container freezing

### Namespace Support
- `pid` - Process isolation
- `net` - Network isolation
- `ipc` - IPC isolation
- `uts` - Hostname isolation
- `user` - User namespace
- `mnt` - Mount namespace

## 🚨 Troubleshooting

### Common Issues

#### Device Not Detected
```bash
# Check fastboot
fastboot devices

# Check ADB
adb devices

# Ensure device is in fastboot mode
adb reboot bootloader
```

#### Kernel Flashing Failed
```bash
# Check kernel image
file boot.img

# Verify device compatibility
python3 kernel_build/scripts/deploy_kernel.py check

# Try manual flash
fastboot flash boot boot.img
```

#### Validation Failed
```bash
# Run detailed validation
python3 kernel_build/scripts/validate_deployment.py --verbose

# Check specific features
adb shell cat /proc/cgroups
adb shell ls /sys/fs/cgroup
```

### Recovery Procedures

#### Boot Loop Recovery
1. Boot into fastboot mode (Vol Down + Power)
2. Flash stock kernel or previous backup
3. Reboot and investigate issues

#### Rollback to Previous Kernel
```bash
# List available backups
ls kernel_build/backups/kernels/

# Rollback to specific backup
./deploy.sh rollback kernel_build/backups/kernels/boot_backup_TIMESTAMP.img
```

## 📊 Deployment Reports

### Deployment Log
Each deployment is logged with:
- Timestamp
- Kernel path
- Device information
- Success/failure status
- Backup information

### Validation Report
Comprehensive validation includes:
- Kernel information
- Android version
- Docker feature availability
- Cgroup subsystem status
- Namespace support
- Overall compatibility score

## 🔐 Security Considerations

### Backup Strategy
- Automatic kernel backup before flashing
- Backup retention for 30 days
- JSON records for non-root devices

### Device Safety
- Device compatibility verification
- Kernel image validation
- Battery level checks (optional)
- Confirmation prompts for risky operations

### Rollback Protection
- Automatic rollback on validation failure
- Manual rollback capabilities
- Backup integrity verification

## 🎯 Advanced Usage

### Custom Deployment Profiles
```bash
# Deploy with custom configuration
python3 kernel_build/scripts/deploy_kernel.py deploy boot.img --config custom_config.json
```

### Batch Deployment
```bash
# Deploy to multiple devices (if supported)
for device in device1 device2; do
    fastboot -s $device flash boot boot.img
done
```

### Integration with Build System
```bash
# Complete build and deploy workflow
python3 kernel_build/scripts/patch_integration.py apply-all
make -j$(nproc) # Your kernel build command
./deploy.sh deploy out/arch/arm64/boot/Image.gz-dtb
```

## 📚 API Reference

### DeploymentManager Class
```python
from kernel_build.scripts.deploy_kernel import KernelDeploymentManager

deployer = KernelDeploymentManager()

# Deploy kernel
success = deployer.deploy_kernel(
    kernel_path=Path("boot.img"),
    skip_backup=False,
    skip_validation=False
)
```

### ValidationManager Class
```python
from kernel_build.scripts.validate_deployment import DeploymentValidator

validator = DeploymentValidator()

# Run validation
success = validator.run_full_validation()
```

## 🤝 Contributing

When contributing to deployment tools:
1. Test on actual K20 Pro hardware
2. Verify compatibility with different Android versions
3. Add comprehensive error handling
4. Update documentation for new features
5. Ensure rollback procedures work correctly

## ⚠️ Disclaimers

- **Device-Specific**: Only for Redmi K20 Pro (raphael/raphaelin)
- **Bootloader**: Requires unlocked bootloader
- **Risk**: Kernel flashing can brick devices if done incorrectly
- **Backup**: Always backup before flashing custom kernels
- **Testing**: Test thoroughly before daily use

---

**These deployment tools provide a safe and automated way to deploy Docker-enabled kernels to K20 Pro devices with comprehensive validation and rollback capabilities.**