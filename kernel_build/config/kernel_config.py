#!/usr/bin/env python3
"""
Kernel configuration parser and manager for Docker-enabled kernel build.
Handles parsing and validation of kernel configuration files.
"""

import re
import json
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path


class KernelConfigParser:
    """Parser for kernel configuration files (defconfig format)."""
    
    def __init__(self):
        self.config_options: Dict[str, str] = {}
        self.comments: List[str] = []
        
    def parse_defconfig(self, config_path: str) -> Dict[str, str]:
        """
        Parse a kernel defconfig file and return configuration options.
        
        Args:
            config_path: Path to the defconfig file
            
        Returns:
            Dictionary of configuration options
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        config_options = {}
        
        with open(config_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                    
                # Handle comments
                if line.startswith('#'):
                    # Check for disabled options (# CONFIG_OPTION is not set)
                    disabled_match = re.match(r'# (CONFIG_\w+) is not set', line)
                    if disabled_match:
                        config_options[disabled_match.group(1)] = 'n'
                    continue
                    
                # Handle configuration options
                if line.startswith('CONFIG_'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config_options[key] = value
                    else:
                        # Boolean option without explicit value
                        config_options[line] = 'y'
                        
        self.config_options = config_options
        return config_options
        
    def get_option(self, option_name: str) -> Optional[str]:
        """Get the value of a configuration option."""
        return self.config_options.get(option_name)
        
    def is_enabled(self, option_name: str) -> bool:
        """Check if a configuration option is enabled."""
        value = self.get_option(option_name)
        return value == 'y' or (value and value != 'n')
        
    def is_disabled(self, option_name: str) -> bool:
        """Check if a configuration option is explicitly disabled."""
        return self.get_option(option_name) == 'n'


class DockerRequirements:
    """Docker kernel configuration requirements."""
    
    # Essential Docker kernel requirements
    REQUIRED_OPTIONS = {
        # Namespaces
        'CONFIG_NAMESPACES': 'y',
        'CONFIG_UTS_NS': 'y',
        'CONFIG_IPC_NS': 'y',
        'CONFIG_PID_NS': 'y',
        'CONFIG_NET_NS': 'y',
        'CONFIG_USER_NS': 'y',
        
        # Cgroups
        'CONFIG_CGROUPS': 'y',
        'CONFIG_CGROUP_CPUACCT': 'y',
        'CONFIG_CGROUP_DEVICE': 'y',
        'CONFIG_CGROUP_FREEZER': 'y',
        'CONFIG_CGROUP_SCHED': 'y',
        'CONFIG_CPUSETS': 'y',
        'CONFIG_MEMCG': 'y',
        'CONFIG_CGROUP_PIDS': 'y',
        
        # Networking
        'CONFIG_NETFILTER': 'y',
        'CONFIG_NETFILTER_ADVANCED': 'y',
        'CONFIG_BRIDGE_NETFILTER': 'y',
        'CONFIG_IP_NF_FILTER': 'y',
        'CONFIG_IP_NF_TARGET_MASQUERADE': 'y',
        'CONFIG_NETFILTER_XT_MATCH_ADDRTYPE': 'y',
        'CONFIG_NETFILTER_XT_MATCH_CONNTRACK': 'y',
        'CONFIG_NETFILTER_XT_MATCH_IPVS': 'y',
        'CONFIG_IP_VS': 'y',
        'CONFIG_IP_VS_NFCT': 'y',
        'CONFIG_IP_VS_RR': 'y',
        'CONFIG_VXLAN': 'y',
        'CONFIG_BRIDGE': 'y',
        'CONFIG_VETH': 'y',
        
        # Storage
        'CONFIG_BLK_DEV_DM': 'y',
        'CONFIG_DM_THIN_PROVISIONING': 'y',
        'CONFIG_OVERLAY_FS': 'y',
        
        # Security
        'CONFIG_SECCOMP': 'y',
        'CONFIG_SECCOMP_FILTER': 'y',
        
        # Checkpoint/Restore
        'CONFIG_CHECKPOINT_RESTORE': 'y',
        
        # Misc
        'CONFIG_POSIX_MQUEUE': 'y',
        'CONFIG_DEVPTS_MULTIPLE_INSTANCES': 'y',
    }
    
    # Recommended options for better Docker performance
    RECOMMENDED_OPTIONS = {
        'CONFIG_MEMCG_SWAP': 'y',
        'CONFIG_MEMCG_SWAP_ENABLED': 'y',
        'CONFIG_BLK_CGROUP': 'y',
        'CONFIG_BLK_DEV_THROTTLING': 'y',
        'CONFIG_CGROUP_PERF': 'y',
        'CONFIG_CGROUP_HUGETLB': 'y',
        'CONFIG_NET_CLS_CGROUP': 'y',
        'CONFIG_CGROUP_NET_PRIO': 'y',
        'CONFIG_CFS_BANDWIDTH': 'y',
        'CONFIG_RT_GROUP_SCHED': 'y',
        'CONFIG_IP_VS_PROTO_TCP': 'y',
        'CONFIG_IP_VS_PROTO_UDP': 'y',
        'CONFIG_DUMMY': 'y',
        'CONFIG_MACVLAN': 'y',
        'CONFIG_IPVLAN': 'y',
    }
    
    @classmethod
    def get_all_requirements(cls) -> Dict[str, str]:
        """Get all Docker requirements (required + recommended)."""
        requirements = cls.REQUIRED_OPTIONS.copy()
        requirements.update(cls.RECOMMENDED_OPTIONS)
        return requirements


class BuildSettings:
    """Build configuration settings manager."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.settings = self._load_default_settings()
        if config_file:
            self.load_from_file(config_file)
            
    def _load_default_settings(self) -> Dict:
        """Load default build settings."""
        return {
            'target_device': 'raphael',
            'arch': 'arm64',
            'cross_compile': 'aarch64-linux-android-',
            'kernel_source_dir': 'kernel',
            'output_dir': 'out',
            'defconfig': 'raphael_defconfig',
            'make_jobs': 8,
            'compiler_flags': ['-O2', '-pipe'],
            'patches': [
                'files/kernel.diff',
                'files/aosp.diff'
            ],
            'docker_binaries_dir': 'docker',
            'criu_binaries_dir': 'criu',
            'migration_tools_dir': 'migration'
        }
        
    def load_from_file(self, config_file: str) -> None:
        """Load build settings from JSON file."""
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, 'r') as f:
                file_settings = json.load(f)
                self.settings.update(file_settings)
                
    def save_to_file(self, config_file: str) -> None:
        """Save current settings to JSON file."""
        with open(config_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
            
    def get(self, key: str, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)
        
    def set(self, key: str, value) -> None:
        """Set a setting value."""
        self.settings[key] = value
        
    def get_toolchain_env(self) -> Dict[str, str]:
        """Get environment variables for toolchain."""
        return {
            'ARCH': self.get('arch'),
            'CROSS_COMPILE': self.get('cross_compile'),
            'KBUILD_BUILD_USER': 'docker-kernel-builder',
            'KBUILD_BUILD_HOST': 'android-container'
        }


class CgroupConfig:
    """Cgroup configuration parser and manager."""
    
    def __init__(self):
        self.cgroup_config = {}
        
    def parse_cgroups_json(self, config_path: str) -> Dict:
        """Parse cgroups.json configuration file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Cgroups config not found: {config_path}")
            
        with open(config_path, 'r') as f:
            self.cgroup_config = json.load(f)
            
        return self.cgroup_config
        
    def get_cgroup_controllers(self) -> List[str]:
        """Get list of cgroup controllers."""
        controllers = []
        if 'Cgroups' in self.cgroup_config:
            for cgroup in self.cgroup_config['Cgroups']:
                if 'Controller' in cgroup:
                    controllers.append(cgroup['Controller'])
        return controllers
        
    def validate_docker_cgroups(self) -> Tuple[bool, List[str]]:
        """Validate that required cgroup controllers are present."""
        required_controllers = {
            'blkio', 'cpu', 'cpuacct', 'cpuset', 'devices', 
            'freezer', 'memory', 'pids'
        }
        
        available_controllers = set(self.get_cgroup_controllers())
        missing_controllers = required_controllers - available_controllers
        
        return len(missing_controllers) == 0, list(missing_controllers)