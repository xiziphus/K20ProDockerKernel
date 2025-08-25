#!/system/bin/sh
#
# Enhanced Docker daemon startup script for Android
# This script integrates with the Python Docker daemon manager
#

# Set script directory
SCRIPT_DIR="$(dirname "$0")"
KERNEL_BUILD_DIR="$(dirname "$SCRIPT_DIR")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a /data/docker_setup.log
}

log "Starting enhanced Docker daemon setup..."

# Check if Python is available
if ! command -v python3 >/dev/null 2>&1; then
    log "ERROR: Python3 not found, falling back to basic setup"
    exec "$SCRIPT_DIR/../files/dockerd.sh"
fi

# Check if our Python manager is available
if [ -f "$KERNEL_BUILD_DIR/runtime/docker_daemon.py" ]; then
    log "Using Python Docker daemon manager"
    
    # Set Python path
    export PYTHONPATH="$KERNEL_BUILD_DIR:$PYTHONPATH"
    
    # Run the Python manager
    python3 "$KERNEL_BUILD_DIR/scripts/docker_setup.py" --setup --start --source "$KERNEL_BUILD_DIR/../docker"
    
    if [ $? -eq 0 ]; then
        log "Docker daemon started successfully via Python manager"
        exit 0
    else
        log "Python manager failed, falling back to basic setup"
    fi
fi

log "Falling back to basic Docker setup..."

# Basic setup (fallback)
mount -o rw,remount /

# Create required directories
log "Creating required directories..."
mkdir -p /system/etc/docker
mkdir -p /var /run /tmp /opt /usr
mkdir -p /data/var /data/run /data/tmp /data/opt /data/etc/docker

# Clean up old run directory
rm -rf /data/var/run 2>/dev/null

# Setup bind mounts
log "Setting up bind mounts..."
mount --bind /data/etc/docker /etc/docker 2>/dev/null
mount --bind /data/var /var 2>/dev/null
mount --bind /data/run /run 2>/dev/null
mount --bind /data/tmp /tmp 2>/dev/null
mount --bind /data/opt /opt 2>/dev/null

# Setup cgroups
log "Setting up cgroups..."
if ! mountpoint -q /sys/fs/cgroup; then
    mount tmpfs /sys/fs/cgroup -t tmpfs -o size=1G
fi

# Create cgroup directories
mkdir -p /sys/fs/cgroup/{blkio,cpu,cpuacct,cpuset,devices,freezer,hugetlb,memory,net_cls,net_prio,perf_event,pids,rdma,schedtune,systemd}

# Mount cgroup controllers
log "Mounting cgroup controllers..."
mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd 2>/dev/null
mount -t cgroup -o blkio,nodev,noexec,nosuid cgroup /sys/fs/cgroup/blkio 2>/dev/null
mount -t cgroup -o cpu,nodev,noexec,nosuid cgroup /sys/fs/cgroup/cpu 2>/dev/null
mount -t cgroup -o cpuacct,nodev,noexec,nosuid cgroup /sys/fs/cgroup/cpuacct 2>/dev/null
mount -t cgroup -o cpuset,nodev,noexec,nosuid cgroup /sys/fs/cgroup/cpuset 2>/dev/null
mount -t cgroup -o devices,nodev,noexec,nosuid cgroup /sys/fs/cgroup/devices 2>/dev/null
mount -t cgroup -o freezer,nodev,noexec,nosuid cgroup /sys/fs/cgroup/freezer 2>/dev/null
mount -t cgroup -o hugetlb,nodev,noexec,nosuid cgroup /sys/fs/cgroup/hugetlb 2>/dev/null
mount -t cgroup -o memory,nodev,noexec,nosuid cgroup /sys/fs/cgroup/memory 2>/dev/null
mount -t cgroup -o net_cls,nodev,noexec,nosuid cgroup /sys/fs/cgroup/net_cls 2>/dev/null
mount -t cgroup -o net_prio,nodev,noexec,nosuid cgroup /sys/fs/cgroup/net_prio 2>/dev/null
mount -t cgroup -o perf_event,nodev,noexec,nosuid cgroup /sys/fs/cgroup/perf_event 2>/dev/null
mount -t cgroup -o pids,nodev,noexec,nosuid cgroup /sys/fs/cgroup/pids 2>/dev/null
mount -t cgroup -o rdma,nodev,noexec,nosuid cgroup /sys/fs/cgroup/rdma 2>/dev/null
mount -t cgroup -o schedtune,nodev,noexec,nosuid cgroup /sys/fs/cgroup/schedtune 2>/dev/null

# Setup networking
log "Setting up networking..."
ip rule add pref 1 from all lookup main 2>/dev/null
ip rule add pref 2 from all lookup default 2>/dev/null

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null

# Load br_netfilter module
modprobe br_netfilter 2>/dev/null

# Disable SELinux
setenforce 0 2>/dev/null

# Create Docker daemon configuration
log "Creating Docker daemon configuration..."
cat > /etc/docker/daemon.json << EOF
{
  "registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"],
  "experimental": true,
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Set environment variables
export DOCKER_RAMDISK=true

# Start Docker daemon
log "Starting Docker daemon..."
dockerd --add-runtime crun=/bin/crun -H tcp://0.0.0.0:2375 -H unix:///var/run/docker.sock &

DOCKERD_PID=$!
log "Docker daemon started with PID: $DOCKERD_PID"

# Simple monitoring loop
while kill -0 $DOCKERD_PID 2>/dev/null; do
    sleep 10
done

log "Docker daemon process has stopped"
exit 1