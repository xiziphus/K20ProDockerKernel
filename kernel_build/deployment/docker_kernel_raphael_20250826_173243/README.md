# Docker-Enabled Kernel for K20 Pro

Created: 2025-08-26 17:32:44

## Overview

This package contains a Docker-enabled kernel for the Redmi K20 Pro (raphael) device.
The kernel includes all necessary features for running Linux containers.

## Contents

- `fastboot_package/` - Fastboot-compatible kernel images
- `flash_kernel.sh` - Linux/macOS flashing script
- `flash_kernel.bat` - Windows flashing script
- `deployment_metadata.json` - Package metadata and checksums

## Installation

⚠️ **WARNING**: Flashing a custom kernel will void your warranty and may brick your device!

### Prerequisites

1. Unlocked bootloader
2. Fastboot tools installed
3. Device drivers installed
4. Backup of current kernel (recommended)

### Steps

1. Boot device into fastboot mode:
   ```
   adb reboot bootloader
   ```

2. Run the appropriate flashing script:
   - Linux/macOS: `./flash_kernel.sh`
   - Windows: `flash_kernel.bat`

3. Wait for device to reboot

4. Verify installation:
   ```
   adb shell uname -a
   ```

## Docker Setup

After flashing the kernel, you'll need to install Docker binaries and configure the runtime.
Refer to the main project documentation for Docker setup instructions.

## Support

This is experimental software. Use at your own risk.
