#!/usr/bin/env python3
"""
Network Manager for Docker-enabled Android kernel.

This module handles network configuration, bridge setup, iptables rules,
and network namespace management for Docker container networking.
"""

import os
import subprocess
import json
import logging
import ipaddress
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """Configuration for Docker bridge network."""
    name: str = "docker0"
    subnet: str = "172.17.0.0/16"
    gateway: str = "172.17.0.1"
    mtu: int = 1500
    enable_icc: bool = True  # Inter-container communication
    enable_ip_masquerade: bool = True


@dataclass
class NetworkConfig:
    """Network configuration for Docker."""
    bridge: BridgeConfig
    enable_ipv6: bool = False
    ipv6_subnet: Optional[str] = None
    dns_servers: List[str] = None
    
    def __post_init__(self):
        if self.dns_servers is None:
            self.dns_servers = ["8.8.8.8", "8.8.4.4"]


class NetworkManager:
    """Manages Docker network configuration and setup."""
    
    # Required kernel modules for networking
    REQUIRED_MODULES = [
        "bridge", "br_netfilter", "xt_nat", "xt_conntrack",
        "xt_MASQUERADE", "iptable_nat", "iptable_filter"
    ]
    
    # Required kernel features
    REQUIRED_FEATURES = [
        "/proc/sys/net/bridge/bridge-nf-call-iptables",
        "/proc/sys/net/bridge/bridge-nf-call-ip6tables", 
        "/proc/sys/net/ipv4/ip_forward",
        "/proc/sys/net/ipv4/conf/all/forwarding"
    ]
    
    def __init__(self, config: Optional[NetworkConfig] = None):
        """
        Initialize network manager.
        
        Args:
            config: Network configuration object
        """
        self.config = config or NetworkConfig(bridge=BridgeConfig())
        
    def validate_kernel_support(self) -> Tuple[bool, List[str]]:
        """
        Validate kernel networking support for Docker.
        
        Returns:
            Tuple of (success, list of missing features)
        """
        missing_features = []
        
        try:
            # Check required kernel features
            for feature in self.REQUIRED_FEATURES:
                if not os.path.exists(feature):
                    missing_features.append(f"Missing kernel feature: {feature}")
                    
            # Check if iptables is available
            try:
                subprocess.run(["iptables", "--version"], 
                             capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing_features.append("iptables not available")
                
            # Check if ip command is available
            try:
                subprocess.run(["ip", "link", "show"], 
                             capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing_features.append("ip command not available")
                
            return len(missing_features) == 0, missing_features
            
        except Exception as e:
            logger.error(f"Failed to validate kernel support: {e}")
            return False, [str(e)]
            
    def load_kernel_modules(self) -> bool:
        """
        Load required kernel modules for networking.
        
        Returns:
            True if modules loaded successfully, False otherwise
        """
        try:
            success = True
            
            for module in self.REQUIRED_MODULES:
                try:
                    result = subprocess.run(
                        ["modprobe", module], 
                        capture_output=True, text=True, check=True
                    )
                    logger.info(f"Loaded kernel module: {module}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to load module {module}: {e.stderr}")
                    # Don't fail completely, some modules might already be loaded
                    
            return success
            
        except Exception as e:
            logger.error(f"Failed to load kernel modules: {e}")
            return False
            
    def enable_ip_forwarding(self) -> bool:
        """
        Enable IP forwarding for container networking.
        
        Returns:
            True if IP forwarding enabled successfully, False otherwise
        """
        try:
            # Enable IPv4 forwarding
            forwarding_files = [
                "/proc/sys/net/ipv4/ip_forward",
                "/proc/sys/net/ipv4/conf/all/forwarding",
                "/proc/sys/net/ipv4/conf/default/forwarding"
            ]
            
            for file_path in forwarding_files:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'w') as f:
                            f.write("1")
                        logger.info(f"Enabled IP forwarding: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to enable forwarding in {file_path}: {e}")
                        
            # Enable IPv6 forwarding if configured
            if self.config.enable_ipv6:
                ipv6_files = [
                    "/proc/sys/net/ipv6/conf/all/forwarding",
                    "/proc/sys/net/ipv6/conf/default/forwarding"
                ]
                
                for file_path in ipv6_files:
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'w') as f:
                                f.write("1")
                            logger.info(f"Enabled IPv6 forwarding: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to enable IPv6 forwarding in {file_path}: {e}")
                            
            # Enable bridge netfilter
            bridge_files = [
                "/proc/sys/net/bridge/bridge-nf-call-iptables",
                "/proc/sys/net/bridge/bridge-nf-call-ip6tables"
            ]
            
            for file_path in bridge_files:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'w') as f:
                            f.write("1")
                        logger.info(f"Enabled bridge netfilter: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to enable bridge netfilter in {file_path}: {e}")
                        
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable IP forwarding: {e}")
            return False
            
    def create_bridge_interface(self) -> bool:
        """
        Create Docker bridge interface.
        
        Returns:
            True if bridge created successfully, False otherwise
        """
        try:
            bridge_name = self.config.bridge.name
            
            # Check if bridge already exists
            result = subprocess.run(
                ["ip", "link", "show", bridge_name],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Bridge {bridge_name} already exists")
                return True
                
            # Create bridge interface
            subprocess.run(
                ["ip", "link", "add", "name", bridge_name, "type", "bridge"],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Created bridge interface: {bridge_name}")
            
            # Set bridge MTU
            subprocess.run(
                ["ip", "link", "set", "dev", bridge_name, "mtu", str(self.config.bridge.mtu)],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Set bridge MTU to {self.config.bridge.mtu}")
            
            # Assign IP address to bridge
            subprocess.run(
                ["ip", "addr", "add", f"{self.config.bridge.gateway}/{self._get_subnet_prefix()}", 
                 "dev", bridge_name],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Assigned IP {self.config.bridge.gateway} to bridge")
            
            # Bring bridge interface up
            subprocess.run(
                ["ip", "link", "set", "dev", bridge_name, "up"],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Brought bridge {bridge_name} up")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create bridge interface: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to create bridge interface: {e}")
            return False
            
    def _get_subnet_prefix(self) -> int:
        """Get subnet prefix length from CIDR notation."""
        try:
            network = ipaddress.IPv4Network(self.config.bridge.subnet, strict=False)
            return network.prefixlen
        except Exception:
            return 16  # Default fallback
            
    def setup_iptables_rules(self) -> bool:
        """
        Setup iptables rules for Docker networking.
        
        Returns:
            True if iptables rules setup successfully, False otherwise
        """
        try:
            bridge_name = self.config.bridge.name
            subnet = self.config.bridge.subnet
            
            # Create DOCKER chain if it doesn't exist
            self._ensure_iptables_chain("filter", "DOCKER")
            self._ensure_iptables_chain("nat", "DOCKER")
            self._ensure_iptables_chain("filter", "DOCKER-ISOLATION-STAGE-1")
            self._ensure_iptables_chain("filter", "DOCKER-ISOLATION-STAGE-2")
            
            # Setup NAT rules for outbound traffic
            if self.config.bridge.enable_ip_masquerade:
                nat_rules = [
                    # MASQUERADE traffic from containers to external networks
                    ["-t", "nat", "-A", "POSTROUTING", "-s", subnet, "!", "-o", bridge_name, "-j", "MASQUERADE"],
                    # MASQUERADE traffic between containers on different networks
                    ["-t", "nat", "-A", "POSTROUTING", "-s", subnet, "-d", subnet, "-j", "MASQUERADE"]
                ]
                
                for rule in nat_rules:
                    try:
                        # Check if rule already exists
                        check_rule = rule.copy()
                        check_rule[2] = "-C"  # Change -A to -C for check
                        result = subprocess.run(["iptables"] + check_rule, capture_output=True)
                        
                        if result.returncode != 0:  # Rule doesn't exist, add it
                            subprocess.run(["iptables"] + rule, capture_output=True, check=True)
                            logger.info(f"Added iptables NAT rule: {' '.join(rule)}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Failed to add NAT rule: {e}")
                        
            # Setup filter rules
            filter_rules = [
                # Allow established connections
                ["-A", "FORWARD", "-o", bridge_name, "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                # Allow traffic from bridge
                ["-A", "FORWARD", "-i", bridge_name, "!", "-o", bridge_name, "-j", "ACCEPT"],
                # Handle inter-container communication
                ["-A", "FORWARD", "-i", bridge_name, "-o", bridge_name, "-j", "ACCEPT"] if self.config.bridge.enable_icc else 
                ["-A", "FORWARD", "-i", bridge_name, "-o", bridge_name, "-j", "DROP"]
            ]
            
            for rule in filter_rules:
                try:
                    # Check if rule already exists
                    check_rule = rule.copy()
                    check_rule[0] = "-C"  # Change -A to -C for check
                    result = subprocess.run(["iptables"] + check_rule, capture_output=True)
                    
                    if result.returncode != 0:  # Rule doesn't exist, add it
                        subprocess.run(["iptables"] + rule, capture_output=True, check=True)
                        logger.info(f"Added iptables filter rule: {' '.join(rule)}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to add filter rule: {e}")
                    
            # Setup Docker isolation rules
            isolation_rules = [
                ["-A", "DOCKER-ISOLATION-STAGE-1", "-i", bridge_name, "!", "-o", bridge_name, "-j", "DOCKER-ISOLATION-STAGE-2"],
                ["-A", "DOCKER-ISOLATION-STAGE-2", "-o", bridge_name, "-j", "DROP"],
                ["-A", "DOCKER-ISOLATION-STAGE-1", "-j", "RETURN"],
                ["-A", "DOCKER-ISOLATION-STAGE-2", "-j", "RETURN"]
            ]
            
            for rule in isolation_rules:
                try:
                    check_rule = rule.copy()
                    check_rule[0] = "-C"
                    result = subprocess.run(["iptables"] + check_rule, capture_output=True)
                    
                    if result.returncode != 0:
                        subprocess.run(["iptables"] + rule, capture_output=True, check=True)
                        logger.info(f"Added Docker isolation rule: {' '.join(rule)}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to add isolation rule: {e}")
                    
            # Insert jump rules to Docker chains in main chains
            jump_rules = [
                ["-I", "FORWARD", "1", "-j", "DOCKER-ISOLATION-STAGE-1"],
                ["-I", "FORWARD", "2", "-o", bridge_name, "-j", "DOCKER"],
                ["-I", "FORWARD", "3", "-o", bridge_name, "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                ["-I", "FORWARD", "4", "-i", bridge_name, "!", "-o", bridge_name, "-j", "ACCEPT"],
                ["-I", "FORWARD", "5", "-i", bridge_name, "-o", bridge_name, "-j", "ACCEPT"] if self.config.bridge.enable_icc else None
            ]
            
            for rule in jump_rules:
                if rule is None:
                    continue
                try:
                    check_rule = rule.copy()
                    check_rule[0] = "-C"
                    check_rule.remove("1")  # Remove position for check
                    result = subprocess.run(["iptables"] + check_rule, capture_output=True)
                    
                    if result.returncode != 0:
                        subprocess.run(["iptables"] + rule, capture_output=True, check=True)
                        logger.info(f"Added jump rule: {' '.join(rule)}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to add jump rule: {e}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup iptables rules: {e}")
            return False
            
    def _ensure_iptables_chain(self, table: str, chain: str) -> bool:
        """
        Ensure iptables chain exists.
        
        Args:
            table: iptables table (filter, nat, mangle, raw)
            chain: chain name
            
        Returns:
            True if chain exists or was created, False otherwise
        """
        try:
            # Check if chain exists
            result = subprocess.run(
                ["iptables", "-t", table, "-L", chain],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                return True  # Chain already exists
                
            # Create chain
            subprocess.run(
                ["iptables", "-t", table, "-N", chain],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Created iptables chain: {table}/{chain}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to ensure iptables chain {table}/{chain}: {e.stderr}")
            return False
            
    def setup_routing_rules(self) -> bool:
        """
        Setup IP routing rules for Docker networking.
        
        Returns:
            True if routing rules setup successfully, False otherwise
        """
        try:
            # Add routing rules with different priorities
            routing_rules = [
                ["ip", "rule", "add", "pref", "1", "from", "all", "lookup", "main"],
                ["ip", "rule", "add", "pref", "2", "from", "all", "lookup", "default"],
                ["ip", "rule", "add", "pref", "100", "from", self.config.bridge.subnet, "lookup", "main"]
            ]
            
            for rule in routing_rules:
                try:
                    # Try to add the rule (will fail if it already exists)
                    result = subprocess.run(rule, capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.info(f"Added routing rule: {' '.join(rule)}")
                    else:
                        logger.debug(f"Routing rule already exists or failed: {result.stderr}")
                except Exception as e:
                    logger.debug(f"Failed to add routing rule: {e}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup routing rules: {e}")
            return False
            
    def create_network_namespace(self, name: str) -> bool:
        """
        Create a network namespace for container isolation.
        
        Args:
            name: namespace name
            
        Returns:
            True if namespace created successfully, False otherwise
        """
        try:
            # Check if namespace already exists
            result = subprocess.run(
                ["ip", "netns", "list"],
                capture_output=True, text=True
            )
            
            if name in result.stdout:
                logger.info(f"Network namespace {name} already exists")
                return True
                
            # Create namespace
            subprocess.run(
                ["ip", "netns", "add", name],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Created network namespace: {name}")
            
            # Bring up loopback interface in namespace
            subprocess.run(
                ["ip", "netns", "exec", name, "ip", "link", "set", "lo", "up"],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Brought up loopback in namespace {name}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create network namespace {name}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to create network namespace {name}: {e}")
            return False
            
    def delete_network_namespace(self, name: str) -> bool:
        """
        Delete a network namespace.
        
        Args:
            name: namespace name
            
        Returns:
            True if namespace deleted successfully, False otherwise
        """
        try:
            subprocess.run(
                ["ip", "netns", "delete", name],
                capture_output=True, text=True, check=True
            )
            logger.info(f"Deleted network namespace: {name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete network namespace {name}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete network namespace {name}: {e}")
            return False
            
    def setup_dns_configuration(self) -> bool:
        """
        Setup DNS configuration for containers.
        
        Returns:
            True if DNS setup successfully, False otherwise
        """
        try:
            # Create resolv.conf for containers
            resolv_conf_path = "/etc/docker/resolv.conf"
            os.makedirs(os.path.dirname(resolv_conf_path), exist_ok=True)
            
            with open(resolv_conf_path, 'w') as f:
                for dns_server in self.config.dns_servers:
                    f.write(f"nameserver {dns_server}\n")
                f.write("options ndots:0\n")
                
            logger.info(f"Created DNS configuration: {resolv_conf_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup DNS configuration: {e}")
            return False
            
    def validate_network_connectivity(self) -> Tuple[bool, List[str]]:
        """
        Validate network connectivity and configuration.
        
        Returns:
            Tuple of (success, list of issues)
        """
        issues = []
        
        try:
            bridge_name = self.config.bridge.name
            
            # Check if bridge interface exists and is up
            result = subprocess.run(
                ["ip", "link", "show", bridge_name],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                issues.append(f"Bridge interface {bridge_name} does not exist")
            elif "state UP" not in result.stdout:
                issues.append(f"Bridge interface {bridge_name} is not up")
                
            # Check if bridge has correct IP address
            result = subprocess.run(
                ["ip", "addr", "show", bridge_name],
                capture_output=True, text=True
            )
            
            if self.config.bridge.gateway not in result.stdout:
                issues.append(f"Bridge {bridge_name} does not have correct IP address")
                
            # Check IP forwarding
            forwarding_files = ["/proc/sys/net/ipv4/ip_forward"]
            for file_path in forwarding_files:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        if f.read().strip() != "1":
                            issues.append(f"IP forwarding not enabled: {file_path}")
                            
            # Check iptables rules
            result = subprocess.run(
                ["iptables", "-t", "nat", "-L", "POSTROUTING"],
                capture_output=True, text=True
            )
            
            if "MASQUERADE" not in result.stdout:
                issues.append("NAT masquerading rules not found")
                
            # Test DNS resolution
            for dns_server in self.config.dns_servers:
                try:
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "2", dns_server],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode != 0:
                        issues.append(f"Cannot reach DNS server {dns_server}")
                except subprocess.TimeoutExpired:
                    issues.append(f"Timeout reaching DNS server {dns_server}")
                except Exception:
                    issues.append(f"Failed to test DNS server {dns_server}")
                    
            return len(issues) == 0, issues
            
        except Exception as e:
            logger.error(f"Failed to validate network connectivity: {e}")
            return False, [str(e)]
            
    def cleanup_network_configuration(self) -> bool:
        """
        Clean up Docker network configuration.
        
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            bridge_name = self.config.bridge.name
            
            # Remove iptables rules
            logger.info("Cleaning up iptables rules...")
            
            # Remove jump rules from main chains
            cleanup_rules = [
                ["-D", "FORWARD", "-j", "DOCKER-ISOLATION-STAGE-1"],
                ["-D", "FORWARD", "-o", bridge_name, "-j", "DOCKER"],
                ["-D", "FORWARD", "-o", bridge_name, "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                ["-D", "FORWARD", "-i", bridge_name, "!", "-o", bridge_name, "-j", "ACCEPT"],
                ["-D", "FORWARD", "-i", bridge_name, "-o", bridge_name, "-j", "ACCEPT"]
            ]
            
            for rule in cleanup_rules:
                try:
                    subprocess.run(["iptables"] + rule, capture_output=True)
                except Exception:
                    pass  # Rule might not exist
                    
            # Flush and delete custom chains
            chains_to_cleanup = [
                ("filter", "DOCKER"),
                ("filter", "DOCKER-ISOLATION-STAGE-1"),
                ("filter", "DOCKER-ISOLATION-STAGE-2"),
                ("nat", "DOCKER")
            ]
            
            for table, chain in chains_to_cleanup:
                try:
                    subprocess.run(["iptables", "-t", table, "-F", chain], capture_output=True)
                    subprocess.run(["iptables", "-t", table, "-X", chain], capture_output=True)
                except Exception:
                    pass  # Chain might not exist
                    
            # Remove NAT rules
            nat_cleanup_rules = [
                ["-t", "nat", "-D", "POSTROUTING", "-s", self.config.bridge.subnet, "!", "-o", bridge_name, "-j", "MASQUERADE"],
                ["-t", "nat", "-D", "POSTROUTING", "-s", self.config.bridge.subnet, "-d", self.config.bridge.subnet, "-j", "MASQUERADE"]
            ]
            
            for rule in nat_cleanup_rules:
                try:
                    subprocess.run(["iptables"] + rule, capture_output=True)
                except Exception:
                    pass
                    
            # Remove bridge interface
            try:
                subprocess.run(
                    ["ip", "link", "delete", bridge_name],
                    capture_output=True, text=True, check=True
                )
                logger.info(f"Removed bridge interface: {bridge_name}")
            except subprocess.CalledProcessError:
                logger.debug(f"Bridge {bridge_name} does not exist or already removed")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup network configuration: {e}")
            return False
            
    def setup_complete_networking(self) -> bool:
        """
        Complete setup of Docker networking.
        
        Returns:
            True if networking setup successfully, False otherwise
        """
        logger.info("Setting up complete Docker networking...")
        
        # Validate kernel support
        supported, missing = self.validate_kernel_support()
        if not supported:
            logger.error(f"Kernel networking support validation failed: {missing}")
            # Continue anyway, some features might be optional
            
        # Load kernel modules
        if not self.load_kernel_modules():
            logger.warning("Some kernel modules failed to load, continuing...")
            
        # Enable IP forwarding
        if not self.enable_ip_forwarding():
            logger.error("Failed to enable IP forwarding")
            return False
            
        # Create bridge interface
        if not self.create_bridge_interface():
            logger.error("Failed to create bridge interface")
            return False
            
        # Setup iptables rules
        if not self.setup_iptables_rules():
            logger.error("Failed to setup iptables rules")
            return False
            
        # Setup routing rules
        if not self.setup_routing_rules():
            logger.error("Failed to setup routing rules")
            return False
            
        # Setup DNS configuration
        if not self.setup_dns_configuration():
            logger.error("Failed to setup DNS configuration")
            return False
            
        # Validate configuration
        valid, issues = self.validate_network_connectivity()
        if not valid:
            logger.warning(f"Network validation issues: {issues}")
            # Don't fail completely, some issues might be expected
            
        logger.info("Docker networking setup completed successfully")
        return True


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Docker Network Manager for Android")
    parser.add_argument("--bridge-name", default="docker0", help="Bridge interface name")
    parser.add_argument("--subnet", default="172.17.0.0/16", help="Bridge subnet")
    parser.add_argument("--gateway", default="172.17.0.1", help="Bridge gateway IP")
    parser.add_argument("--mtu", type=int, default=1500, help="Bridge MTU")
    parser.add_argument("--dns", action="append", help="DNS servers (can be used multiple times)")
    parser.add_argument("--setup", "-s", action="store_true", help="Setup complete networking")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate network configuration")
    parser.add_argument("--cleanup", "-c", action="store_true", help="Cleanup network configuration")
    parser.add_argument("--create-namespace", help="Create network namespace")
    parser.add_argument("--delete-namespace", help="Delete network namespace")
    
    args = parser.parse_args()
    
    # Create configuration
    bridge_config = BridgeConfig(
        name=args.bridge_name,
        subnet=args.subnet,
        gateway=args.gateway,
        mtu=args.mtu
    )
    
    network_config = NetworkConfig(
        bridge=bridge_config,
        dns_servers=args.dns or ["8.8.8.8", "8.8.4.4"]
    )
    
    manager = NetworkManager(network_config)
    
    if args.validate:
        supported, missing = manager.validate_kernel_support()
        if supported:
            print("Kernel networking support validation passed")
        else:
            print(f"Kernel networking support validation failed: {missing}")
            
        valid, issues = manager.validate_network_connectivity()
        if valid:
            print("Network connectivity validation passed")
        else:
            print(f"Network connectivity validation failed: {issues}")
            
        return 0 if supported and valid else 1
        
    elif args.setup:
        if manager.setup_complete_networking():
            print("Docker networking setup completed successfully")
        else:
            print("Docker networking setup failed")
            return 1
            
    elif args.cleanup:
        if manager.cleanup_network_configuration():
            print("Network configuration cleanup completed")
        else:
            print("Network configuration cleanup failed")
            return 1
            
    elif args.create_namespace:
        if manager.create_network_namespace(args.create_namespace):
            print(f"Network namespace {args.create_namespace} created successfully")
        else:
            print(f"Failed to create network namespace {args.create_namespace}")
            return 1
            
    elif args.delete_namespace:
        if manager.delete_network_namespace(args.delete_namespace):
            print(f"Network namespace {args.delete_namespace} deleted successfully")
        else:
            print(f"Failed to delete network namespace {args.delete_namespace}")
            return 1
            
    else:
        parser.print_help()
        
    return 0


if __name__ == "__main__":
    exit(main())