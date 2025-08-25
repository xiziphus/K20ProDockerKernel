#!/usr/bin/env python3
"""
Kernel configuration applier for Docker-enabled kernel build.
Handles applying Docker configurations to defconfig files with backup and restore functionality.
"""

import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .kernel_config import KernelConfigParser, DockerRequirements
from kernel_build.utils.file_utils import backup_file, ensure_directory


class ConfigApplier:
    """Applies Docker kernel configurations to defconfig files."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "kernel_build" / "backups"
        ensure_directory(self.backup_dir)
        
    def apply_docker_config(self, 
                           defconfig_path: str, 
                           output_path: Optional[str] = None,
                           backup: bool = True,
                           merge_mode: str = "replace") -> Tuple[bool, str]:
        """
        Apply Docker kernel configurations to a defconfig file.
        
        Args:
            defconfig_path: Path to input defconfig file
            output_path: Path to output file (defaults to input path)
            backup: Whether to create backup before applying changes
            merge_mode: How to merge configs ("replace", "merge", "append")
            
        Returns:
            Tuple of (success, message)
        """
        try:
            defconfig_path = Path(defconfig_path)
            if not defconfig_path.exists():
                return False, f"Defconfig file not found: {defconfig_path}"
                
            output_path = Path(output_path) if output_path else defconfig_path
            
            # Create backup if requested
            backup_path = None
            if backup:
                backup_path = self._create_backup(defconfig_path)
                
            # Parse existing configuration
            parser = KernelConfigParser()
            existing_config = parser.parse_defconfig(str(defconfig_path))
            
            # Get Docker requirements
            docker_requirements = DockerRequirements.get_all_requirements()
            
            # Apply merge strategy
            if merge_mode == "replace":
                final_config = self._merge_replace(existing_config, docker_requirements)
            elif merge_mode == "merge":
                final_config = self._merge_smart(existing_config, docker_requirements)
            elif merge_mode == "append":
                final_config = self._merge_append(existing_config, docker_requirements)
            else:
                return False, f"Unknown merge mode: {merge_mode}"
                
            # Write new configuration
            success = self._write_config(final_config, output_path, defconfig_path)
            
            if success:
                applied_count = len([k for k in docker_requirements.keys() 
                                   if existing_config.get(k) != docker_requirements[k]])
                message = f"Successfully applied {applied_count} Docker configurations"
                if backup_path:
                    message += f" (backup: {backup_path.name})"
                return True, message
            else:
                return False, "Failed to write configuration file"
                
        except Exception as e:
            return False, f"Error applying Docker config: {str(e)}"
            
    def restore_from_backup(self, backup_name: str, target_path: str) -> Tuple[bool, str]:
        """
        Restore configuration from backup.
        
        Args:
            backup_name: Name of backup file
            target_path: Path to restore to
            
        Returns:
            Tuple of (success, message)
        """
        try:
            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                return False, f"Backup not found: {backup_name}"
                
            shutil.copy2(backup_path, target_path)
            return True, f"Configuration restored from {backup_name}"
            
        except Exception as e:
            return False, f"Error restoring backup: {str(e)}"
            
    def list_backups(self) -> List[Dict[str, str]]:
        """
        List available backup files.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_file in self.backup_dir.glob("*.backup"):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'path': str(backup_file),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
            
        return sorted(backups, key=lambda x: x['created'], reverse=True)
        
    def merge_additional_config(self, 
                               base_config_path: str,
                               additional_config: Dict[str, str],
                               output_path: str) -> Tuple[bool, str]:
        """
        Merge additional configuration options with base config.
        
        Args:
            base_config_path: Path to base configuration file
            additional_config: Additional config options to merge
            output_path: Path to write merged configuration
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Parse base configuration
            parser = KernelConfigParser()
            base_config = parser.parse_defconfig(base_config_path)
            
            # Merge configurations
            merged_config = base_config.copy()
            merged_config.update(additional_config)
            
            # Write merged configuration
            success = self._write_config(merged_config, Path(output_path), Path(base_config_path))
            
            if success:
                return True, f"Successfully merged {len(additional_config)} additional options"
            else:
                return False, "Failed to write merged configuration"
                
        except Exception as e:
            return False, f"Error merging configuration: {str(e)}"
            
    def validate_applied_config(self, config_path: str) -> Tuple[bool, List[str]]:
        """
        Validate that Docker configurations were properly applied.
        
        Args:
            config_path: Path to configuration file to validate
            
        Returns:
            Tuple of (is_valid, list_of_missing_options)
        """
        try:
            parser = KernelConfigParser()
            config = parser.parse_defconfig(config_path)
            
            docker_requirements = DockerRequirements.get_all_requirements()
            missing_options = []
            
            for option, expected_value in docker_requirements.items():
                actual_value = config.get(option)
                if actual_value != expected_value:
                    missing_options.append(f"{option}={expected_value} (got: {actual_value or 'not set'})")
                    
            return len(missing_options) == 0, missing_options
            
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
            
    def _create_backup(self, config_path: Path) -> Path:
        """Create backup of configuration file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{config_path.stem}_{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(config_path, backup_path)
        return backup_path
        
    def _merge_replace(self, existing_config: Dict[str, str], 
                      docker_requirements: Dict[str, str]) -> Dict[str, str]:
        """Replace existing options with Docker requirements."""
        final_config = existing_config.copy()
        final_config.update(docker_requirements)
        return final_config
        
    def _merge_smart(self, existing_config: Dict[str, str], 
                    docker_requirements: Dict[str, str]) -> Dict[str, str]:
        """Smart merge that preserves compatible existing settings."""
        final_config = existing_config.copy()
        
        for option, required_value in docker_requirements.items():
            existing_value = existing_config.get(option)
            
            # If option doesn't exist or is disabled, apply requirement
            if not existing_value or existing_value == 'n':
                final_config[option] = required_value
            # If existing value is compatible (e.g., 'm' for module), keep it
            elif existing_value in ['y', 'm'] and required_value == 'y':
                # Keep existing value (module loading is acceptable)
                pass
            else:
                # Apply requirement for other cases
                final_config[option] = required_value
                
        return final_config
        
    def _merge_append(self, existing_config: Dict[str, str], 
                     docker_requirements: Dict[str, str]) -> Dict[str, str]:
        """Append Docker requirements without modifying existing options."""
        final_config = existing_config.copy()
        
        for option, required_value in docker_requirements.items():
            if option not in existing_config:
                final_config[option] = required_value
                
        return final_config
        
    def _write_config(self, config: Dict[str, str], output_path: Path, original_path: Path) -> bool:
        """Write configuration to file with proper formatting."""
        try:
            # Read original file to preserve comments and structure
            original_lines = []
            if original_path.exists():
                with open(original_path, 'r') as f:
                    original_lines = f.readlines()
                    
            # Track which options we've written
            written_options = set()
            
            with open(output_path, 'w') as f:
                # Write header
                f.write("# Docker-enabled kernel configuration\n")
                f.write(f"# Generated from: {original_path.name}\n")
                f.write(f"# Generated on: {datetime.now().isoformat()}\n\n")
                
                # Process original lines, updating with new values
                for line in original_lines:
                    line = line.strip()
                    
                    # Skip empty lines and comments in original processing
                    if not line or line.startswith('#'):
                        # Check for disabled options
                        if line.startswith('# CONFIG_'):
                            disabled_match = line.split(' is not set')[0].replace('# ', '')
                            if disabled_match in config:
                                # Write updated value instead of disabled comment
                                value = config[disabled_match]
                                if value == 'n':
                                    f.write(f"# {disabled_match} is not set\n")
                                else:
                                    f.write(f"{disabled_match}={value}\n")
                                written_options.add(disabled_match)
                            else:
                                f.write(line + "\n")
                        else:
                            f.write(line + "\n")
                        continue
                        
                    # Handle configuration options
                    if line.startswith('CONFIG_'):
                        if '=' in line:
                            option = line.split('=')[0]
                        else:
                            option = line
                            
                        if option in config:
                            # Write updated value
                            value = config[option]
                            if value == 'n':
                                f.write(f"# {option} is not set\n")
                            else:
                                f.write(f"{option}={value}\n")
                            written_options.add(option)
                        else:
                            # Keep original line
                            f.write(line + "\n")
                    else:
                        f.write(line + "\n")
                        
                # Write any new options that weren't in the original file
                new_options = set(config.keys()) - written_options
                if new_options:
                    f.write("\n# Additional Docker requirements\n")
                    for option in sorted(new_options):
                        value = config[option]
                        if value == 'n':
                            f.write(f"# {option} is not set\n")
                        else:
                            f.write(f"{option}={value}\n")
                            
            return True
            
        except Exception as e:
            print(f"Error writing config file: {e}")
            return False


class ConfigMerger:
    """Handles merging multiple configuration sources."""
    
    def __init__(self):
        self.parser = KernelConfigParser()
        
    def merge_configs(self, config_files: List[str], output_path: str, 
                     priority_order: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Merge multiple configuration files.
        
        Args:
            config_files: List of configuration file paths
            output_path: Path to write merged configuration
            priority_order: Order of priority for conflicting options
            
        Returns:
            Tuple of (success, message)
        """
        try:
            merged_config = {}
            
            # If priority order is specified, process files in that order
            if priority_order:
                ordered_files = []
                for priority_file in priority_order:
                    if priority_file in config_files:
                        ordered_files.append(priority_file)
                # Add remaining files
                for config_file in config_files:
                    if config_file not in ordered_files:
                        ordered_files.append(config_file)
                config_files = ordered_files
                
            # Merge configurations
            for config_file in config_files:
                config = self.parser.parse_defconfig(config_file)
                merged_config.update(config)
                
            # Write merged configuration
            applier = ConfigApplier()
            success = applier._write_config(merged_config, Path(output_path), Path(config_files[0]))
            
            if success:
                return True, f"Successfully merged {len(config_files)} configuration files"
            else:
                return False, "Failed to write merged configuration"
                
        except Exception as e:
            return False, f"Error merging configurations: {str(e)}"
            
    def diff_configs(self, config1_path: str, config2_path: str) -> Dict[str, Dict[str, str]]:
        """
        Compare two configuration files and return differences.
        
        Args:
            config1_path: Path to first configuration file
            config2_path: Path to second configuration file
            
        Returns:
            Dictionary with differences categorized by type
        """
        config1 = self.parser.parse_defconfig(config1_path)
        config2 = self.parser.parse_defconfig(config2_path)
        
        all_options = set(config1.keys()) | set(config2.keys())
        
        differences = {
            'added': {},      # Options in config2 but not config1
            'removed': {},    # Options in config1 but not config2
            'changed': {},    # Options with different values
            'unchanged': {}   # Options with same values
        }
        
        for option in all_options:
            value1 = config1.get(option)
            value2 = config2.get(option)
            
            if value1 is None and value2 is not None:
                differences['added'][option] = value2
            elif value1 is not None and value2 is None:
                differences['removed'][option] = value1
            elif value1 != value2:
                differences['changed'][option] = {'from': value1, 'to': value2}
            else:
                differences['unchanged'][option] = value1
                
        return differences