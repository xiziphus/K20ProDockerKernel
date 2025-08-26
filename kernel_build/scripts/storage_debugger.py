#!/usr/bin/env python3
"""
Storage Debugging Tools
Provides debugging utilities for overlay filesystem and storage issues
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class StorageDebugger:
    """Storage and filesystem debugging utilities"""
    
    def __init__(self):
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        self.docker_root = self._get_docker_root()
        
    def _get_docker_root(self) -> str:
        """Get Docker root directory"""
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.DockerRootDir}}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Default locations
        for path in ["/var/lib/docker", "/var/lib/docker-engine"]:
            if os.path.exists(path):
                return path
        
        return "/var/lib/docker"
    
    def check_storage_drivers(self) -> Dict:
        """Check Docker storage driver configuration"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "current_driver": None,
            "available_drivers": [],
            "driver_info": {},
            "storage_options": {},
            "issues": []
        }
        
        try:
            # Get Docker system info
            result = subprocess.run(
                ["docker", "system", "info", "--format", "json"],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                status["current_driver"] = info.get("Driver")
                
                # Get driver status details
                driver_status = info.get("DriverStatus", [])
                driver_info = {}
                for item in driver_status:
                    if len(item) >= 2:
                        driver_info[item[0]] = item[1]
                status["driver_info"] = driver_info
                
                # Check for storage options
                if "DriverOptions" in info:
                    status["storage_options"] = info["DriverOptions"]
                
                # Check for warnings
                warnings = info.get("Warnings", [])
                for warning in warnings:
                    if "storage" in warning.lower() or "driver" in warning.lower():
                        status["issues"].append(f"Storage warning: {warning}")
                
                # Analyze driver efficiency
                current_driver = status["current_driver"]
                if current_driver == "vfs":
                    status["issues"].append("Using VFS driver - very inefficient, consider overlay2")
                elif current_driver == "devicemapper" and "direct-lvm" not in str(driver_info):
                    status["issues"].append("Using devicemapper with loopback - inefficient for production")
                elif current_driver == "aufs":
                    status["issues"].append("AUFS driver is deprecated, consider overlay2")
                
            else:
                status["issues"].append(f"Failed to get Docker info: {result.stderr}")
        
        except Exception as e:
            status["issues"].append(f"Storage driver check failed: {e}")
        
        # Check available storage drivers
        try:
            # Check kernel support for overlay
            if os.path.exists("/proc/filesystems"):
                with open("/proc/filesystems", "r") as f:
                    filesystems = f.read()
                    if "overlay" in filesystems:
                        status["available_drivers"].append("overlay2")
                    if "aufs" in filesystems:
                        status["available_drivers"].append("aufs")
            
            # Check for devicemapper
            if os.path.exists("/dev/mapper"):
                status["available_drivers"].append("devicemapper")
            
            # VFS is always available
            status["available_drivers"].append("vfs")
            
        except Exception as e:
            status["issues"].append(f"Available drivers check failed: {e}")
        
        return status
    
    def check_overlay_filesystem(self) -> Dict:
        """Check overlay filesystem support and configuration"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "kernel_support": {},
            "mount_points": {},
            "overlay_features": {},
            "docker_overlay": {},
            "issues": []
        }
        
        # Check kernel overlay support
        try:
            # Check /proc/filesystems
            if os.path.exists("/proc/filesystems"):
                with open("/proc/filesystems", "r") as f:
                    filesystems = f.read()
                    status["kernel_support"]["overlay_listed"] = "overlay" in filesystems
                    status["kernel_support"]["overlay2_support"] = True  # overlay2 is userspace
            
            # Check overlay module
            if os.path.exists("/sys/module/overlay"):
                status["kernel_support"]["overlay_module_loaded"] = True
                
                # Check overlay parameters
                params_dir = Path("/sys/module/overlay/parameters")
                if params_dir.exists():
                    for param_file in params_dir.glob("*"):
                        try:
                            with open(param_file, "r") as f:
                                value = f.read().strip()
                                status["overlay_features"][param_file.name] = value
                        except Exception:
                            pass
            else:
                status["kernel_support"]["overlay_module_loaded"] = False
                status["issues"].append("Overlay kernel module not loaded")
            
            # Check if overlay can be loaded
            if not status["kernel_support"].get("overlay_module_loaded"):
                try:
                    result = subprocess.run(["modprobe", "overlay"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        status["kernel_support"]["overlay_can_load"] = True
                    else:
                        status["kernel_support"]["overlay_can_load"] = False
                        status["issues"].append(f"Cannot load overlay module: {result.stderr}")
                except Exception as e:
                    status["issues"].append(f"Failed to test overlay module loading: {e}")
        
        except Exception as e:
            status["issues"].append(f"Kernel overlay check failed: {e}")
        
        # Check current overlay mounts
        try:
            result = subprocess.run(["mount", "-t", "overlay"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                mount_count = 0
                for line in result.stdout.split('\n'):
                    if line.strip() and "overlay" in line:
                        mount_count += 1
                        # Parse mount info
                        parts = line.split()
                        if len(parts) >= 3:
                            mount_point = parts[2]
                            status["mount_points"][mount_point] = {
                                "source": parts[0] if len(parts) > 0 else "unknown",
                                "options": parts[5] if len(parts) > 5 else ""
                            }
                
                status["kernel_support"]["active_overlay_mounts"] = mount_count
            
        except Exception as e:
            status["issues"].append(f"Overlay mount check failed: {e}")
        
        # Check Docker overlay usage
        if self.docker_root and os.path.exists(self.docker_root):
            overlay_dir = os.path.join(self.docker_root, "overlay2")
            if os.path.exists(overlay_dir):
                status["docker_overlay"]["overlay2_dir_exists"] = True
                
                try:
                    # Count overlay layers
                    layer_count = len([d for d in os.listdir(overlay_dir) 
                                     if os.path.isdir(os.path.join(overlay_dir, d))])
                    status["docker_overlay"]["layer_count"] = layer_count
                    
                    # Check disk usage
                    total_size = 0
                    for root, dirs, files in os.walk(overlay_dir):
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                total_size += os.path.getsize(file_path)
                            except (OSError, IOError):
                                pass
                    
                    status["docker_overlay"]["total_size_bytes"] = total_size
                    status["docker_overlay"]["total_size_gb"] = round(total_size / (1024**3), 2)
                    
                except Exception as e:
                    status["issues"].append(f"Docker overlay analysis failed: {e}")
            else:
                status["docker_overlay"]["overlay2_dir_exists"] = False
                if status.get("current_driver") == "overlay2":
                    status["issues"].append("Docker using overlay2 but directory not found")
        
        return status
    
    def check_disk_usage(self) -> Dict:
        """Check disk usage for Docker storage"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "docker_root_usage": {},
            "system_usage": {},
            "docker_system_df": {},
            "large_files": [],
            "issues": []
        }
        
        # Check Docker root directory usage
        if self.docker_root and os.path.exists(self.docker_root):
            try:
                total, used, free = shutil.disk_usage(self.docker_root)
                usage_percent = (used / total) * 100
                
                status["docker_root_usage"] = {
                    "path": self.docker_root,
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "usage_percent": round(usage_percent, 2)
                }
                
                # Check for low disk space
                if free < 1024**3:  # Less than 1GB
                    status["issues"].append(f"Low disk space: {round(free / (1024**3), 2)}GB free")
                
                if usage_percent > 90:
                    status["issues"].append(f"High disk usage: {usage_percent:.1f}%")
                
            except Exception as e:
                status["issues"].append(f"Docker root usage check failed: {e}")
        
        # Get Docker system disk usage
        try:
            result = subprocess.run(
                ["docker", "system", "df", "--format", "json"],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                df_data = json.loads(result.stdout)
                
                for item in df_data:
                    item_type = item.get("Type", "").lower()
                    status["docker_system_df"][item_type] = {
                        "total": item.get("Total", 0),
                        "active": item.get("Active", 0),
                        "size": item.get("Size", "0B"),
                        "reclaimable": item.get("Reclaimable", "0B")
                    }
                
                # Check for reclaimable space
                total_reclaimable = 0
                for item in df_data:
                    reclaimable_str = item.get("Reclaimable", "0B")
                    try:
                        if reclaimable_str.endswith("GB"):
                            total_reclaimable += float(reclaimable_str[:-2]) * 1024**3
                        elif reclaimable_str.endswith("MB"):
                            total_reclaimable += float(reclaimable_str[:-2]) * 1024**2
                    except ValueError:
                        pass
                
                if total_reclaimable > 1024**3:  # More than 1GB reclaimable
                    status["issues"].append(f"Large amount of reclaimable space: {round(total_reclaimable / (1024**3), 2)}GB")
            
        except Exception as e:
            status["issues"].append(f"Docker system df failed: {e}")
        
        # Find large files in Docker directory
        if self.docker_root and os.path.exists(self.docker_root):
            try:
                # Use find command to locate large files (>100MB)
                result = subprocess.run(
                    ["find", self.docker_root, "-type", "f", "-size", "+100M", "-exec", "ls", "-lh", "{}", "+"],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    large_files = []
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 9:
                                size = parts[4]
                                path = ' '.join(parts[8:])
                                large_files.append({
                                    "size": size,
                                    "path": path
                                })
                    
                    status["large_files"] = large_files[:20]  # Top 20 large files
                    
                    if len(large_files) > 10:
                        status["issues"].append(f"Found {len(large_files)} large files (>100MB)")
            
            except Exception as e:
                status["issues"].append(f"Large file search failed: {e}")
        
        return status
    
    def check_container_storage(self) -> Dict:
        """Check storage configuration for containers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "containers": {},
            "storage_summary": {
                "total_containers": 0,
                "containers_with_volumes": 0,
                "containers_with_mounts": 0,
                "total_volumes": 0
            },
            "issues": []
        }
        
        try:
            # Get all containers
            result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                
                status["storage_summary"]["total_containers"] = len(containers)
                
                # Analyze each container's storage
                for container in containers:
                    container_id = container["ID"]
                    container_name = container["Names"]
                    
                    # Get detailed container info
                    inspect_result = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if inspect_result.returncode == 0:
                        try:
                            container_details = json.loads(inspect_result.stdout)[0]
                            
                            container_storage = {
                                "id": container_id[:12],
                                "status": container["Status"],
                                "mounts": [],
                                "volumes": [],
                                "storage_driver": container_details.get("Driver"),
                                "storage_issues": []
                            }
                            
                            # Analyze mounts
                            mounts = container_details.get("Mounts", [])
                            for mount in mounts:
                                mount_info = {
                                    "type": mount.get("Type"),
                                    "source": mount.get("Source"),
                                    "destination": mount.get("Destination"),
                                    "mode": mount.get("Mode"),
                                    "rw": mount.get("RW", True),
                                    "propagation": mount.get("Propagation")
                                }
                                
                                container_storage["mounts"].append(mount_info)
                                
                                # Check for mount issues
                                if mount.get("Type") == "bind":
                                    source = mount.get("Source")
                                    if source and not os.path.exists(source):
                                        container_storage["storage_issues"].append(f"Bind mount source missing: {source}")
                                
                                elif mount.get("Type") == "volume":
                                    container_storage["volumes"].append(mount.get("Name", "unnamed"))
                            
                            # Check container size
                            try:
                                size_result = subprocess.run(
                                    ["docker", "container", "inspect", "--size", container_id],
                                    capture_output=True, text=True, timeout=10
                                )
                                
                                if size_result.returncode == 0:
                                    size_data = json.loads(size_result.stdout)[0]
                                    size_info = size_data.get("SizeRootFs", 0)
                                    size_rw = size_data.get("SizeRw", 0)
                                    
                                    container_storage["size_root_fs"] = size_info
                                    container_storage["size_rw"] = size_rw
                                    container_storage["size_total"] = size_info + size_rw
                                    
                                    # Check for large containers
                                    if size_info > 1024**3:  # > 1GB
                                        container_storage["storage_issues"].append(f"Large container size: {round(size_info / (1024**3), 2)}GB")
                            
                            except Exception as e:
                                container_storage["storage_issues"].append(f"Size check failed: {e}")
                            
                            # Update summary counters
                            if container_storage["mounts"]:
                                status["storage_summary"]["containers_with_mounts"] += 1
                            
                            if container_storage["volumes"]:
                                status["storage_summary"]["containers_with_volumes"] += 1
                                status["storage_summary"]["total_volumes"] += len(container_storage["volumes"])
                            
                            status["containers"][container_name] = container_storage
                            
                        except json.JSONDecodeError:
                            status["issues"].append(f"Failed to parse container details for {container_name}")
            
            else:
                status["issues"].append(f"Failed to get container list: {result.stderr}")
        
        except Exception as e:
            status["issues"].append(f"Container storage check failed: {e}")
        
        return status
    
    def check_volume_usage(self) -> Dict:
        """Check Docker volume usage and configuration"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "volumes": {},
            "volume_summary": {
                "total_volumes": 0,
                "used_volumes": 0,
                "unused_volumes": 0,
                "total_size_bytes": 0
            },
            "issues": []
        }
        
        try:
            # Get all volumes
            result = subprocess.run(["docker", "volume", "ls", "--format", "json"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                volumes = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            volumes.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                
                status["volume_summary"]["total_volumes"] = len(volumes)
                
                # Analyze each volume
                for volume in volumes:
                    volume_name = volume["Name"]
                    
                    # Get detailed volume info
                    inspect_result = subprocess.run(
                        ["docker", "volume", "inspect", volume_name],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if inspect_result.returncode == 0:
                        try:
                            volume_details = json.loads(inspect_result.stdout)[0]
                            
                            volume_info = {
                                "driver": volume_details.get("Driver"),
                                "mountpoint": volume_details.get("Mountpoint"),
                                "options": volume_details.get("Options", {}),
                                "labels": volume_details.get("Labels", {}),
                                "scope": volume_details.get("Scope"),
                                "size_bytes": 0,
                                "used_by_containers": [],
                                "issues": []
                            }
                            
                            # Check volume size
                            mountpoint = volume_details.get("Mountpoint")
                            if mountpoint and os.path.exists(mountpoint):
                                try:
                                    total_size = 0
                                    for root, dirs, files in os.walk(mountpoint):
                                        for file in files:
                                            try:
                                                file_path = os.path.join(root, file)
                                                total_size += os.path.getsize(file_path)
                                            except (OSError, IOError):
                                                pass
                                    
                                    volume_info["size_bytes"] = total_size
                                    status["volume_summary"]["total_size_bytes"] += total_size
                                    
                                except Exception as e:
                                    volume_info["issues"].append(f"Size calculation failed: {e}")
                            else:
                                volume_info["issues"].append("Mountpoint not accessible")
                            
                            status["volumes"][volume_name] = volume_info
                            
                        except json.JSONDecodeError:
                            status["issues"].append(f"Failed to parse volume details for {volume_name}")
                
                # Check which volumes are used by containers
                container_result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                                capture_output=True, text=True, timeout=10)
                
                if container_result.returncode == 0:
                    for line in container_result.stdout.strip().split('\n'):
                        if line:
                            try:
                                container = json.loads(line)
                                container_id = container["ID"]
                                container_name = container["Names"]
                                
                                # Get container mounts
                                inspect_result = subprocess.run(
                                    ["docker", "inspect", container_id],
                                    capture_output=True, text=True, timeout=5
                                )
                                
                                if inspect_result.returncode == 0:
                                    container_details = json.loads(inspect_result.stdout)[0]
                                    mounts = container_details.get("Mounts", [])
                                    
                                    for mount in mounts:
                                        if mount.get("Type") == "volume":
                                            volume_name = mount.get("Name")
                                            if volume_name in status["volumes"]:
                                                status["volumes"][volume_name]["used_by_containers"].append(container_name)
                            
                            except json.JSONDecodeError:
                                continue
                
                # Update usage summary
                for volume_name, volume_info in status["volumes"].items():
                    if volume_info["used_by_containers"]:
                        status["volume_summary"]["used_volumes"] += 1
                    else:
                        status["volume_summary"]["unused_volumes"] += 1
                
                # Check for unused volumes
                if status["volume_summary"]["unused_volumes"] > 0:
                    status["issues"].append(f"{status['volume_summary']['unused_volumes']} unused volumes found - consider cleanup")     
   
        except Exception as e:
            status["issues"].append(f"Volume usage check failed: {e}")
        
        return status
    
    def diagnose_storage_issues(self) -> Dict:
        """Comprehensive storage diagnostics"""
        print("🔍 Running storage diagnostics...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_issues": 0,
                "critical_issues": 0,
                "storage_driver": "unknown",
                "total_containers": 0,
                "total_volumes": 0,
                "disk_usage_percent": 0
            },
            "storage_drivers": self.check_storage_drivers(),
            "overlay_filesystem": self.check_overlay_filesystem(),
            "disk_usage": self.check_disk_usage(),
            "container_storage": self.check_container_storage(),
            "volume_usage": self.check_volume_usage()
        }
        
        # Count issues and summary stats
        all_issues = []
        for section in ["storage_drivers", "overlay_filesystem", "disk_usage", "container_storage", "volume_usage"]:
            issues = report[section].get("issues", [])
            all_issues.extend(issues)
        
        report["summary"]["total_issues"] = len(all_issues)
        report["summary"]["storage_driver"] = report["storage_drivers"].get("current_driver", "unknown")
        report["summary"]["total_containers"] = report["container_storage"]["storage_summary"]["total_containers"]
        report["summary"]["total_volumes"] = report["volume_usage"]["volume_summary"]["total_volumes"]
        
        # Get disk usage percentage
        docker_usage = report["disk_usage"].get("docker_root_usage", {})
        if docker_usage:
            report["summary"]["disk_usage_percent"] = docker_usage.get("usage_percent", 0)
        
        # Count critical issues
        critical_keywords = ["failed", "error", "not found", "missing", "full", "no space"]
        critical_issues = [
            issue for issue in all_issues 
            if any(keyword in issue.lower() for keyword in critical_keywords)
        ]
        report["summary"]["critical_issues"] = len(critical_issues)
        
        return report
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save storage diagnostic report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"storage_diagnostics_{timestamp}.json"
        
        report_path = self.reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Storage diagnostic report saved to {report_path}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
    
    def print_summary(self, report: Dict):
        """Print human-readable storage diagnostic summary"""
        print("\n" + "="*60)
        print("💾 STORAGE DIAGNOSTICS SUMMARY")
        print("="*60)
        
        summary = report["summary"]
        print(f"Total Issues: {summary['total_issues']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Storage Driver: {summary['storage_driver']}")
        print(f"Containers: {summary['total_containers']}")
        print(f"Volumes: {summary['total_volumes']}")
        print(f"Disk Usage: {summary['disk_usage_percent']:.1f}%")
        
        # Storage driver info
        print(f"\n💿 STORAGE DRIVER")
        driver_info = report["storage_drivers"]
        current_driver = driver_info.get("current_driver", "unknown")
        available_drivers = driver_info.get("available_drivers", [])
        print(f"Current: {current_driver}")
        print(f"Available: {', '.join(available_drivers)}")
        
        # Overlay filesystem
        print(f"\n📁 OVERLAY FILESYSTEM")
        overlay_info = report["overlay_filesystem"]
        kernel_support = overlay_info.get("kernel_support", {})
        overlay_loaded = kernel_support.get("overlay_module_loaded", False)
        overlay_mounts = kernel_support.get("active_overlay_mounts", 0)
        print(f"Kernel Module: {'✅ Loaded' if overlay_loaded else '❌ Not loaded'}")
        print(f"Active Mounts: {overlay_mounts}")
        
        # Disk usage
        print(f"\n💽 DISK USAGE")
        disk_info = report["disk_usage"]
        docker_usage = disk_info.get("docker_root_usage", {})
        if docker_usage:
            print(f"Docker Root: {docker_usage.get('used_gb', 0):.1f}GB / {docker_usage.get('total_gb', 0):.1f}GB")
            print(f"Free Space: {docker_usage.get('free_gb', 0):.1f}GB")
        
        # Container storage
        print(f"\n🐳 CONTAINER STORAGE")
        container_info = report["container_storage"]
        storage_summary = container_info.get("storage_summary", {})
        print(f"With Volumes: {storage_summary.get('containers_with_volumes', 0)}")
        print(f"With Mounts: {storage_summary.get('containers_with_mounts', 0)}")
        
        # Volume usage
        print(f"\n📦 VOLUME USAGE")
        volume_info = report["volume_usage"]
        volume_summary = volume_info.get("volume_summary", {})
        total_size_gb = volume_summary.get("total_size_bytes", 0) / (1024**3)
        print(f"Used Volumes: {volume_summary.get('used_volumes', 0)}")
        print(f"Unused Volumes: {volume_summary.get('unused_volumes', 0)}")
        print(f"Total Size: {total_size_gb:.2f}GB")
        
        # All issues
        all_issues = []
        for section in ["storage_drivers", "overlay_filesystem", "disk_usage", "container_storage", "volume_usage"]:
            issues = report[section].get("issues", [])
            all_issues.extend([(section, issue) for issue in issues])
        
        if all_issues:
            print(f"\n⚠️  STORAGE ISSUES ({len(all_issues)})")
            for section, issue in all_issues[:10]:  # Show first 10
                print(f"  • [{section}] {issue}")
            
            if len(all_issues) > 10:
                print(f"  ... and {len(all_issues) - 10} more issues")
        else:
            print(f"\n✅ No storage issues detected")
        
        print("\n" + "="*60)

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Storage Debugging Tool")
    parser.add_argument("--output", type=str, help="Output filename for report")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--drivers", action="store_true", help="Check storage drivers only")
    parser.add_argument("--overlay", action="store_true", help="Check overlay filesystem only")
    parser.add_argument("--disk", action="store_true", help="Check disk usage only")
    parser.add_argument("--containers", action="store_true", help="Check container storage only")
    parser.add_argument("--volumes", action="store_true", help="Check volume usage only")
    
    args = parser.parse_args()
    
    debugger = StorageDebugger()
    
    if args.drivers:
        print("🔍 Checking storage drivers...")
        report = debugger.check_storage_drivers()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.overlay:
        print("🔍 Checking overlay filesystem...")
        report = debugger.check_overlay_filesystem()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.disk:
        print("🔍 Checking disk usage...")
        report = debugger.check_disk_usage()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.containers:
        print("🔍 Checking container storage...")
        report = debugger.check_container_storage()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.volumes:
        print("🔍 Checking volume usage...")
        report = debugger.check_volume_usage()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    else:
        print("🔍 Running comprehensive storage diagnostics...")
        report = debugger.diagnose_storage_issues()
        
        if not args.quiet:
            debugger.print_summary(report)
        
        debugger.save_report(report, args.output)

if __name__ == "__main__":
    main()