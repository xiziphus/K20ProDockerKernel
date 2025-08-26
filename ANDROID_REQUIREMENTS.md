# Android Requirements for Docker-Enabled K20 Pro Kernel

## 📱 Device & ROM Requirements

### Target Device
- **Device**: Redmi K20 Pro (raphael)
- **Chipset**: Snapdragon 855
- **Architecture**: ARM64 (aarch64)

### Recommended ROM Configurations

#### Option 1: PixelExperience Plus 11.0 (Recommended)
```bash
ROM: PixelExperience_Plus_raphael-11.0-20210915-1347-OFFICIAL.zip
Android Version: 11 (API 30)
Kernel Version: 4.14.x
Security Patch: 2021-09-05
```

**Download Links:**
- ROM: https://download.pixelexperience.org/raphael
- Recovery: TWRP 3.5.2 for raphael

#### Option 2: PixelExperience 12.1 (Alternative)
```bash
ROM: PixelExperience_raphael-12.1-20220315-0847-OFFICIAL.zip
Android Version: 12L (API 32)
Kernel Version: 4.14.x
Security Patch: 2022-03-05
```

#### Option 3: PixelExperience 10.0 (Stable Fallback)
```bash
ROM: PixelExperience_raphael-10.0-20201015-1205-OFFICIAL.zip
Android Version: 10 (API 29)
Kernel Version: 4.14.x
Security Patch: 2020-10-05
```

## 🔐 Root Access Requirements

### Why Root is Required

The Docker-enabled kernel **REQUIRES ROOT ACCESS** for the following operations:

1. **Docker Daemon Operations**:
   - Mount cgroup v1/v2 filesystems (`/sys/fs/cgroup/*`)
   - Create and manage network bridges (`docker0`, `br-*`)
   - Configure iptables rules for container networking
   - Access `/dev/mapper` for storage drivers

2. **Container Runtime Operations**:
   - Create and manage namespaces (PID, NET, IPC, UTS, USER, MNT)
   - Mount overlay filesystems for container layers
   - Configure resource limits via cgroups
   - Access device nodes (`/dev/null`, `/dev/zero`, etc.)

3. **System Integration**:
   - Load kernel modules (`overlay`, `br_netfilter`, `xt_conntrack`)
   - Modify system parameters (`/proc/sys/net/*`)
   - Integrate with Android's init system

### Root Solution: KernelSU (Recommended)

#### Why KernelSU over Magisk?

| Feature | KernelSU | Magisk |
|---------|----------|--------|
| **Kernel Integration** | ✅ Built into kernel | ❌ Boot image modification |
| **Docker Compatibility** | ✅ No namespace conflicts | ⚠️ May interfere with containers |
| **Container Isolation** | ✅ Clean separation | ⚠️ Systemless mounts may conflict |
| **Performance** | ✅ Lower overhead | ❌ Additional hooks and processes |
| **Stability** | ✅ Kernel-level stability | ⚠️ Userspace modifications |
| **Custom Kernel Support** | ✅ Native support | ❌ Requires boot image patching |

#### KernelSU Implementation

**Step 1: Integrate KernelSU into Kernel Build**
```bash
# Add KernelSU to kernel source
cd kernel_source
git submodule add https://github.com/tiann/KernelSU.git KernelSU
```

**Step 2: Kernel Configuration**
```bash
# Add to raphael_defconfig
CONFIG_KPROBES=y
CONFIG_HAVE_KPROBES=y
CONFIG_KPROBE_EVENTS=y
CONFIG_MODULES=y
CONFIG_MODULE_UNLOAD=y
```

**Step 3: Build Integration**
```makefile
# Add to kernel Makefile
obj-$(CONFIG_KSU) += KernelSU/
```

#### Alternative: Magisk (If KernelSU Not Viable)

If KernelSU integration proves problematic:

**Magisk Version**: 25.2 or later
**Installation Method**: 
1. Flash custom kernel first
2. Flash Magisk via recovery
3. Install Docker binaries via Magisk module

## 🔧 System Requirements

### Kernel Configuration Requirements

```bash
# Container Support
CONFIG_NAMESPACES=y
CONFIG_UTS_NS=y
CONFIG_IPC_NS=y
CONFIG_PID_NS=y
CONFIG_NET_NS=y
CONFIG_USER_NS=y
CONFIG_CGROUPS=y
CONFIG_CGROUP_CPUACCT=y
CONFIG_CGROUP_DEVICE=y
CONFIG_CGROUP_FREEZER=y
CONFIG_CGROUP_SCHED=y
CONFIG_CPUSETS=y
CONFIG_MEMCG=y

# Networking
CONFIG_NETFILTER=y
CONFIG_NETFILTER_ADVANCED=y
CONFIG_BRIDGE_NETFILTER=y
CONFIG_IP_NF_FILTER=y
CONFIG_IP_NF_TARGET_MASQUERADE=y
CONFIG_NETFILTER_XT_MATCH_ADDRTYPE=y
CONFIG_NETFILTER_XT_MATCH_CONNTRACK=y

# Storage
CONFIG_OVERLAY_FS=y
CONFIG_EXT4_FS=y
CONFIG_EXT4_FS_POSIX_ACL=y
CONFIG_EXT4_FS_SECURITY=y

# Security
CONFIG_SECURITY=y
CONFIG_SECURITY_NETWORK=y
CONFIG_SECURITY_SELINUX=y
CONFIG_DEFAULT_SECURITY_SELINUX=y
```

### Runtime Requirements

```bash
# Required Android Properties
ro.config.low_ram=false
ro.config.zram=false
persist.sys.dalvik.vm.lib.2=libart.so

# SELinux Permissive (for development)
# Note: Should be enforcing in production
ro.boot.selinux=permissive
```

### Storage Requirements

- **Minimum Free Space**: 4GB for Docker images and containers
- **Recommended**: 8GB+ for development and testing
- **Partition**: `/data` partition with sufficient space

## 🚀 Installation Process

### Pre-Installation Checklist

1. **Device Preparation**:
   - [ ] Bootloader unlocked
   - [ ] TWRP recovery installed
   - [ ] ADB and Fastboot working
   - [ ] Device drivers installed on PC

2. **ROM Installation**:
   - [ ] Download recommended PixelExperience ROM
   - [ ] Perform full device backup
   - [ ] Flash ROM via TWRP
   - [ ] Complete initial Android setup

3. **Root Preparation**:
   - [ ] Choose root method (KernelSU recommended)
   - [ ] Prepare root installation files
   - [ ] Verify root access with root checker app

### Installation Steps

```bash
# 1. Flash ROM
adb reboot recovery
# Flash ROM zip in TWRP

# 2. Boot and setup Android
# Complete initial setup

# 3. Flash custom Docker kernel
adb reboot bootloader
fastboot flash boot docker_kernel_raphael.img
fastboot reboot

# 4. Install root solution
# For KernelSU: Already integrated in kernel
# For Magisk: Flash Magisk zip in recovery

# 5. Install Docker binaries
adb push docker_binaries.tar.gz /sdcard/
adb shell
su
cd /data/local/tmp
tar -xzf /sdcard/docker_binaries.tar.gz
./install_docker.sh
```

## 🔍 Verification Steps

### Post-Installation Verification

```bash
# 1. Verify root access
adb shell su -c "id"
# Should show: uid=0(root) gid=0(root)

# 2. Check kernel version
adb shell cat /proc/version
# Should show custom kernel with Docker patches

# 3. Verify cgroup support
adb shell mount | grep cgroup
# Should show cgroup filesystems mounted

# 4. Test Docker daemon
adb shell su -c "dockerd --version"
# Should show Docker daemon version

# 5. Run test container
adb shell su -c "docker run hello-world"
# Should successfully run test container
```

## ⚠️ Important Notes

### Security Considerations

1. **SELinux**: May need to be set to permissive during development
2. **Root Access**: Increases security risk - use only for development
3. **Container Isolation**: Ensure proper namespace configuration
4. **Network Security**: Configure iptables rules carefully

### Performance Considerations

1. **Memory Usage**: Docker daemon uses ~100-200MB RAM
2. **Storage Overhead**: Container images can be large
3. **CPU Impact**: Container operations may affect Android performance
4. **Battery Life**: May be reduced due to additional background processes

### Compatibility Notes

1. **Android Apps**: Should continue working normally
2. **OTA Updates**: Will be disabled with custom kernel
3. **Banking Apps**: May detect root and refuse to work
4. **DRM Content**: May not work with unlocked bootloader

## 🛠️ Troubleshooting

### Common Issues

1. **Boot Loop**: 
   - Flash stock kernel to recover
   - Check kernel configuration compatibility

2. **Docker Daemon Won't Start**:
   - Verify cgroup mounts: `mount | grep cgroup`
   - Check SELinux status: `getenforce`
   - Review kernel config: `zcat /proc/config.gz | grep -i docker`

3. **Container Creation Fails**:
   - Check namespace support: `ls /proc/self/ns/`
   - Verify overlay filesystem: `mount | grep overlay`
   - Test basic functionality: `docker info`

4. **Network Issues**:
   - Check bridge creation: `ip link show docker0`
   - Verify iptables rules: `iptables -L -n`
   - Test connectivity: `docker run --rm alpine ping -c 1 8.8.8.8`

### Recovery Procedures

```bash
# Emergency recovery to stock
fastboot flash boot stock_boot.img
fastboot reboot

# Restore from TWRP backup
adb reboot recovery
# Restore backup in TWRP

# Factory reset (last resort)
fastboot -w
fastboot reboot
```