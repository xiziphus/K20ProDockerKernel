#!/usr/bin/env python3
"""
Network Debugging Utilities
Provides network debugging tools for container connectivity issues
"""

import os
import sys
import json
import subprocess
import socket
import ipaddress
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class NetworkDebugger:
    """Network debugging utilities for container connectivity"""
    
    def __init__(self):
        self.reports_dir = Path("diagnostic_reports")
        self.reports_dir.mkdir(exist_ok=True)
        
    def check_network_interfaces(self) -> Dict:
        """Check network interfaces and their configuration"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "interfaces": {},
            "docker_interfaces": {},
            "bridge_interfaces": {},
            "issues": []
        }
        
        try:
            # Get all network interfaces
            result = subprocess.run(["ip", "addr", "show"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                current_interface = None
                
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    # Parse interface line
                    if line and line[0].isdigit():
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            interface_name = parts[1].split('@')[0]  # Remove @if suffix
                            current_interface = interface_name
                            
                            # Extract interface info
                            flags = []
                            if '<' in line and '>' in line:
                                flags_str = line[line.find('<')+1:line.find('>')]
                                flags = flags_str.split(',')
                            
                            status["interfaces"][interface_name] = {
                                "flags": flags,
                                "state": "UP" if "UP" in flags else "DOWN",
                                "addresses": [],
                                "mtu": None
                            }
                    
                    # Parse address lines
                    elif line.startswith("inet") and current_interface:
                        parts = line.split()
                        if len(parts) >= 2:
                            addr_info = {
                                "type": parts[0],  # inet or inet6
                                "address": parts[1],
                                "scope": None
                            }
                            
                            # Extract scope if present
                            if "scope" in line:
                                scope_idx = parts.index("scope")
                                if scope_idx + 1 < len(parts):
                                    addr_info["scope"] = parts[scope_idx + 1]
                            
                            status["interfaces"][current_interface]["addresses"].append(addr_info)
                    
                    # Parse MTU
                    elif "mtu" in line.lower() and current_interface:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.lower() == "mtu" and i + 1 < len(parts):
                                try:
                                    status["interfaces"][current_interface]["mtu"] = int(parts[i + 1])
                                except ValueError:
                                    pass
                                break
                
                # Identify Docker and bridge interfaces
                for interface_name, interface_info in status["interfaces"].items():
                    if interface_name.startswith("docker") or interface_name.startswith("br-"):
                        status["docker_interfaces"][interface_name] = interface_info
                    elif interface_name.startswith("br") or "bridge" in interface_name.lower():
                        status["bridge_interfaces"][interface_name] = interface_info
                
                # Check for common issues
                if "docker0" not in status["interfaces"]:
                    status["issues"].append("Docker bridge interface (docker0) not found")
                
                # Check if Docker interfaces are up
                for name, info in status["docker_interfaces"].items():
                    if info["state"] != "UP":
                        status["issues"].append(f"Docker interface {name} is down")
                
            else:
                status["issues"].append(f"Failed to get network interfaces: {result.stderr}")
        
        except Exception as e:
            status["issues"].append(f"Network interface check failed: {e}")
        
        return status
    
    def check_docker_networks(self) -> Dict:
        """Check Docker network configuration"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "networks": {},
            "network_drivers": {},
            "containers_network": {},
            "issues": []
        }
        
        try:
            # Get Docker networks
            result = subprocess.run(["docker", "network", "ls", "--format", "json"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                networks = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            networks.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                
                # Get detailed info for each network
                for network in networks:
                    network_id = network["ID"]
                    network_name = network["Name"]
                    
                    inspect_result = subprocess.run(
                        ["docker", "network", "inspect", network_id],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if inspect_result.returncode == 0:
                        try:
                            network_details = json.loads(inspect_result.stdout)[0]
                            
                            status["networks"][network_name] = {
                                "id": network_id[:12],
                                "driver": network_details.get("Driver"),
                                "scope": network_details.get("Scope"),
                                "ipam": network_details.get("IPAM", {}),
                                "containers": len(network_details.get("Containers", {})),
                                "options": network_details.get("Options", {}),
                                "labels": network_details.get("Labels", {})
                            }
                            
                            # Track network drivers
                            driver = network_details.get("Driver")
                            if driver:
                                if driver not in status["network_drivers"]:
                                    status["network_drivers"][driver] = 0
                                status["network_drivers"][driver] += 1
                            
                            # Check for issues
                            if not network_details.get("IPAM", {}).get("Config"):
                                status["issues"].append(f"Network {network_name} has no IPAM configuration")
                            
                        except json.JSONDecodeError:
                            status["issues"].append(f"Failed to parse network details for {network_name}")
                
                # Check for default networks
                expected_networks = ["bridge", "host", "none"]
                for expected in expected_networks:
                    if expected not in status["networks"]:
                        status["issues"].append(f"Default network '{expected}' not found")
                
            else:
                status["issues"].append(f"Failed to get Docker networks: {result.stderr}")
            
            # Get container network information
            container_result = subprocess.run(["docker", "ps", "-a", "--format", "json"], 
                                            capture_output=True, text=True, timeout=10)
            
            if container_result.returncode == 0:
                for line in container_result.stdout.strip().split('\n'):
                    if line:
                        try:
                            container = json.loads(line)
                            container_id = container["ID"]
                            container_name = container["Names"]
                            
                            # Get container network details
                            inspect_result = subprocess.run(
                                ["docker", "inspect", container_id],
                                capture_output=True, text=True, timeout=5
                            )
                            
                            if inspect_result.returncode == 0:
                                container_details = json.loads(inspect_result.stdout)[0]
                                network_settings = container_details.get("NetworkSettings", {})
                                
                                status["containers_network"][container_name] = {
                                    "id": container_id[:12],
                                    "networks": {},
                                    "ports": network_settings.get("Ports", {}),
                                    "ip_address": network_settings.get("IPAddress", ""),
                                    "gateway": network_settings.get("Gateway", "")
                                }
                                
                                # Get network details for container
                                networks = network_settings.get("Networks", {})
                                for net_name, net_info in networks.items():
                                    status["containers_network"][container_name]["networks"][net_name] = {
                                        "ip_address": net_info.get("IPAddress", ""),
                                        "gateway": net_info.get("Gateway", ""),
                                        "mac_address": net_info.get("MacAddress", ""),
                                        "network_id": net_info.get("NetworkID", "")[:12] if net_info.get("NetworkID") else ""
                                    }
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            status["issues"].append(f"Docker network check failed: {e}")
        
        return status
    
    def check_iptables_rules(self) -> Dict:
        """Check iptables rules for Docker networking"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "tables": {},
            "docker_rules": [],
            "issues": []
        }
        
        tables = ["filter", "nat", "mangle"]
        
        for table in tables:
            try:
                result = subprocess.run(["iptables", "-t", table, "-L", "-n", "-v"], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    status["tables"][table] = {
                        "available": True,
                        "rules": result.stdout,
                        "rule_count": len([line for line in result.stdout.split('\n') if line.strip() and not line.startswith('Chain') and not line.startswith('target')])
                    }
                    
                    # Look for Docker-related rules
                    for line in result.stdout.split('\n'):
                        if 'docker' in line.lower() or 'DOCKER' in line:
                            status["docker_rules"].append({
                                "table": table,
                                "rule": line.strip()
                            })
                
                else:
                    status["tables"][table] = {
                        "available": False,
                        "error": result.stderr or "Command failed"
                    }
                    
                    if "permission denied" in result.stderr.lower():
                        status["issues"].append(f"Permission denied accessing iptables {table} table - run as root")
            
            except Exception as e:
                status["tables"][table] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Check if Docker rules are present
        if not status["docker_rules"]:
            status["issues"].append("No Docker iptables rules found - Docker networking may not work")
        
        # Check for DOCKER-USER chain (Docker 17.06+)
        filter_rules = status["tables"].get("filter", {}).get("rules", "")
        if "DOCKER-USER" not in filter_rules:
            status["issues"].append("DOCKER-USER chain not found - custom iptables rules may not work properly")
        
        return status
    
    def test_container_connectivity(self, container_name: Optional[str] = None) -> Dict:
        """Test network connectivity for containers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "connectivity_matrix": {},
            "issues": []
        }
        
        try:
            # Get running containers
            result = subprocess.run(["docker", "ps", "--format", "json"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                status["issues"].append("Cannot get running containers")
                return status
            
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container = json.loads(line)
                        if not container_name or container_name in container["Names"]:
                            containers.append(container)
                    except json.JSONDecodeError:
                        continue
            
            if not containers:
                status["issues"].append("No running containers found for testing")
                return status
            
            # Test connectivity for each container
            for container in containers:
                container_id = container["ID"]
                container_name = container["Names"]
                
                container_tests = {
                    "id": container_id[:12],
                    "internet_connectivity": False,
                    "dns_resolution": False,
                    "container_to_host": False,
                    "ping_tests": {},
                    "port_tests": {},
                    "issues": []
                }
                
                # Test internet connectivity
                try:
                    ping_result = subprocess.run(
                        ["docker", "exec", container_id, "ping", "-c", "3", "-W", "5", "8.8.8.8"],
                        capture_output=True, text=True, timeout=20
                    )
                    container_tests["internet_connectivity"] = ping_result.returncode == 0
                    if ping_result.returncode != 0:
                        container_tests["issues"].append("No internet connectivity")
                except Exception as e:
                    container_tests["issues"].append(f"Internet connectivity test failed: {e}")
                
                # Test DNS resolution
                try:
                    dns_result = subprocess.run(
                        ["docker", "exec", container_id, "nslookup", "google.com"],
                        capture_output=True, text=True, timeout=15
                    )
                    container_tests["dns_resolution"] = dns_result.returncode == 0
                    if dns_result.returncode != 0:
                        container_tests["issues"].append("DNS resolution failed")
                except Exception as e:
                    container_tests["issues"].append(f"DNS test failed: {e}")
                
                # Test container to host connectivity
                try:
                    # Get host IP from container perspective
                    host_ip_result = subprocess.run(
                        ["docker", "exec", container_id, "ip", "route", "show", "default"],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if host_ip_result.returncode == 0:
                        # Extract gateway IP
                        for line in host_ip_result.stdout.split('\n'):
                            if 'default via' in line:
                                parts = line.split()
                                if len(parts) >= 3:
                                    gateway_ip = parts[2]
                                    
                                    ping_result = subprocess.run(
                                        ["docker", "exec", container_id, "ping", "-c", "2", "-W", "3", gateway_ip],
                                        capture_output=True, text=True, timeout=10
                                    )
                                    container_tests["container_to_host"] = ping_result.returncode == 0
                                    container_tests["ping_tests"]["gateway"] = {
                                        "target": gateway_ip,
                                        "success": ping_result.returncode == 0
                                    }
                                    break
                    
                    if not container_tests["container_to_host"]:
                        container_tests["issues"].append("Cannot reach host/gateway")
                
                except Exception as e:
                    container_tests["issues"].append(f"Host connectivity test failed: {e}")
                
                # Test exposed ports
                try:
                    inspect_result = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if inspect_result.returncode == 0:
                        container_details = json.loads(inspect_result.stdout)[0]
                        ports = container_details.get("NetworkSettings", {}).get("Ports", {})
                        
                        for container_port, host_bindings in ports.items():
                            if host_bindings:
                                for binding in host_bindings:
                                    host_port = binding.get("HostPort")
                                    host_ip = binding.get("HostIp", "0.0.0.0")
                                    
                                    if host_port:
                                        # Test if port is accessible
                                        try:
                                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                            sock.settimeout(3)
                                            
                                            test_ip = "127.0.0.1" if host_ip == "0.0.0.0" else host_ip
                                            result = sock.connect_ex((test_ip, int(host_port)))
                                            sock.close()
                                            
                                            container_tests["port_tests"][f"{container_port}->{host_port}"] = {
                                                "host_ip": host_ip,
                                                "host_port": host_port,
                                                "accessible": result == 0
                                            }
                                            
                                            if result != 0:
                                                container_tests["issues"].append(f"Port {host_port} not accessible")
                                        
                                        except Exception as e:
                                            container_tests["issues"].append(f"Port test failed for {host_port}: {e}")
                
                except Exception as e:
                    container_tests["issues"].append(f"Port inspection failed: {e}")
                
                status["tests"][container_name] = container_tests
            
            # Test container-to-container connectivity
            if len(containers) > 1:
                for i, container1 in enumerate(containers):
                    for j, container2 in enumerate(containers):
                        if i != j:
                            container1_name = container1["Names"]
                            container2_name = container2["Names"]
                            container1_id = container1["ID"]
                            
                            try:
                                # Try to ping container2 from container1
                                ping_result = subprocess.run(
                                    ["docker", "exec", container1_id, "ping", "-c", "2", "-W", "3", container2_name],
                                    capture_output=True, text=True, timeout=10
                                )
                                
                                connectivity_key = f"{container1_name} -> {container2_name}"
                                status["connectivity_matrix"][connectivity_key] = {
                                    "success": ping_result.returncode == 0,
                                    "method": "ping by name"
                                }
                                
                                if ping_result.returncode != 0:
                                    # Try by IP address
                                    container2_ip = self._get_container_ip(container2["ID"])
                                    if container2_ip:
                                        ip_ping_result = subprocess.run(
                                            ["docker", "exec", container1_id, "ping", "-c", "2", "-W", "3", container2_ip],
                                            capture_output=True, text=True, timeout=10
                                        )
                                        
                                        status["connectivity_matrix"][connectivity_key] = {
                                            "success": ip_ping_result.returncode == 0,
                                            "method": f"ping by IP ({container2_ip})"
                                        }
                            
                            except Exception as e:
                                connectivity_key = f"{container1_name} -> {container2_name}"
                                status["connectivity_matrix"][connectivity_key] = {
                                    "success": False,
                                    "error": str(e)
                                }
        
        except Exception as e:
            status["issues"].append(f"Connectivity test failed: {e}")
        
        return status
    
    def _get_container_ip(self, container_id: str) -> Optional[str]:
        """Get container IP address"""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_id],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                ip = result.stdout.strip()
                return ip if ip else None
        except Exception:
            pass
        
        return None
    
    def diagnose_network_issues(self) -> Dict:
        """Comprehensive network diagnostics"""
        print("🔍 Running network diagnostics...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_issues": 0,
                "critical_issues": 0,
                "network_interfaces": 0,
                "docker_networks": 0,
                "containers_tested": 0
            },
            "network_interfaces": self.check_network_interfaces(),
            "docker_networks": self.check_docker_networks(),
            "iptables_rules": self.check_iptables_rules(),
            "connectivity_tests": self.test_container_connectivity()
        }
        
        # Count issues and summary stats
        all_issues = []
        for section in ["network_interfaces", "docker_networks", "iptables_rules", "connectivity_tests"]:
            issues = report[section].get("issues", [])
            all_issues.extend(issues)
        
        report["summary"]["total_issues"] = len(all_issues)
        report["summary"]["network_interfaces"] = len(report["network_interfaces"].get("interfaces", {}))
        report["summary"]["docker_networks"] = len(report["docker_networks"].get("networks", {}))
        report["summary"]["containers_tested"] = len(report["connectivity_tests"].get("tests", {}))
        
        # Count critical issues
        critical_keywords = ["not found", "failed", "down", "no connectivity", "permission denied"]
        critical_issues = [
            issue for issue in all_issues 
            if any(keyword in issue.lower() for keyword in critical_keywords)
        ]
        report["summary"]["critical_issues"] = len(critical_issues)
        
        return report
    
    def save_report(self, report: Dict, filename: Optional[str] = None):
        """Save network diagnostic report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_diagnostics_{timestamp}.json"
        
        report_path = self.reports_dir / filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Network diagnostic report saved to {report_path}")
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
    
    def print_summary(self, report: Dict):
        """Print human-readable network diagnostic summary"""
        print("\n" + "="*60)

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Network Debugging Tool")
    parser.add_argument("--container", type=str, help="Test connectivity for specific container")
    parser.add_argument("--output", type=str, help="Output filename for report")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--interfaces", action="store_true", help="Check network interfaces only")
    parser.add_argument("--docker-networks", action="store_true", help="Check Docker networks only")
    parser.add_argument("--iptables", action="store_true", help="Check iptables rules only")
    parser.add_argument("--connectivity", action="store_true", help="Test container connectivity only")
    
    args = parser.parse_args()
    
    debugger = NetworkDebugger()
    
    if args.interfaces:
        print("🔍 Checking network interfaces...")
        report = debugger.check_network_interfaces()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.docker_networks:
        print("🔍 Checking Docker networks...")
        report = debugger.check_docker_networks()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.iptables:
        print("🔍 Checking iptables rules...")
        report = debugger.check_iptables_rules()
        if not args.quiet:
            print(json.dumps(report, indent=2))
    elif args.connectivity:
        print("🔍 Testing container connectivity...")
        report = debugger.test_container_connectivity(args.container)
        if not args.quiet:
            print(json.dumps(report, indent=2))
    else:
        print("🔍 Running comprehensive network diagnostics...")
        report = debugger.diagnose_network_issues()
        
        if not args.quiet:
            debugger.print_summary(report)
        
        debugger.save_report(report, args.output)

if __name__ == "__main__":
    main()