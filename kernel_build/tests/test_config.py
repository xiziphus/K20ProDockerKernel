#!/usr/bin/env python3
"""
Tests for kernel configuration management system.
"""

import unittest
import tempfile
import json
from pathlib import Path

from kernel_build.config.kernel_config import KernelConfigParser, DockerRequirements, BuildSettings, CgroupConfig
from kernel_build.config.validator import KernelConfigValidator, CgroupValidator
from kernel_build.config.config_manager import ConfigurationManager
from kernel_build.config.applier import ConfigApplier, ConfigMerger


class TestKernelConfigParser(unittest.TestCase):
    """Test kernel configuration parser."""
    
    def setUp(self):
        self.parser = KernelConfigParser()
        
    def test_parse_basic_config(self):
        """Test parsing basic kernel configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f:
            f.write("CONFIG_NAMESPACES=y\n")
            f.write("CONFIG_CGROUPS=y\n")
            f.write("# CONFIG_DEBUG is not set\n")
            f.write("CONFIG_MODULES=m\n")
            config_path = f.name
            
        try:
            config = self.parser.parse_defconfig(config_path)
            
            self.assertEqual(config['CONFIG_NAMESPACES'], 'y')
            self.assertEqual(config['CONFIG_CGROUPS'], 'y')
            self.assertEqual(config['CONFIG_DEBUG'], 'n')
            self.assertEqual(config['CONFIG_MODULES'], 'm')
            
        finally:
            Path(config_path).unlink()
            
    def test_is_enabled(self):
        """Test checking if options are enabled."""
        self.parser.config_options = {
            'CONFIG_NAMESPACES': 'y',
            'CONFIG_MODULES': 'm',
            'CONFIG_DEBUG': 'n'
        }
        
        self.assertTrue(self.parser.is_enabled('CONFIG_NAMESPACES'))
        self.assertTrue(self.parser.is_enabled('CONFIG_MODULES'))
        self.assertFalse(self.parser.is_enabled('CONFIG_DEBUG'))
        self.assertFalse(self.parser.is_enabled('CONFIG_NONEXISTENT'))


class TestDockerRequirements(unittest.TestCase):
    """Test Docker requirements definitions."""
    
    def test_required_options(self):
        """Test that required options are defined."""
        required = DockerRequirements.REQUIRED_OPTIONS
        
        # Check essential namespace options
        self.assertIn('CONFIG_NAMESPACES', required)
        self.assertIn('CONFIG_PID_NS', required)
        self.assertIn('CONFIG_NET_NS', required)
        
        # Check essential cgroup options
        self.assertIn('CONFIG_CGROUPS', required)
        self.assertIn('CONFIG_CPUSETS', required)
        self.assertIn('CONFIG_MEMCG', required)
        
    def test_get_all_requirements(self):
        """Test getting all requirements."""
        all_reqs = DockerRequirements.get_all_requirements()
        
        # Should include both required and recommended
        self.assertGreater(len(all_reqs), len(DockerRequirements.REQUIRED_OPTIONS))
        
        # Should contain required options
        for option in DockerRequirements.REQUIRED_OPTIONS:
            self.assertIn(option, all_reqs)


class TestKernelConfigValidator(unittest.TestCase):
    """Test kernel configuration validator."""
    
    def setUp(self):
        self.validator = KernelConfigValidator()
        self.parser = KernelConfigParser()
        
    def test_validate_missing_requirements(self):
        """Test validation with missing requirements."""
        # Empty configuration
        self.parser.config_options = {}
        
        results = self.validator.validate_config(self.parser)
        
        # Should have errors for missing required options
        errors = self.validator.get_errors()
        self.assertGreater(len(errors), 0)
        
        # Should report missing namespaces
        namespace_errors = [r for r in errors if 'NAMESPACE' in r.option]
        self.assertGreater(len(namespace_errors), 0)
        
    def test_validate_complete_config(self):
        """Test validation with complete Docker configuration."""
        # Set all Docker requirements
        self.parser.config_options = DockerRequirements.get_all_requirements()
        
        results = self.validator.validate_config(self.parser)
        
        # Should have no errors
        errors = self.validator.get_errors()
        self.assertEqual(len(errors), 0)


class TestBuildSettings(unittest.TestCase):
    """Test build settings management."""
    
    def test_default_settings(self):
        """Test default build settings."""
        settings = BuildSettings()
        
        self.assertEqual(settings.get('target_device'), 'raphael')
        self.assertEqual(settings.get('arch'), 'arm64')
        self.assertIsInstance(settings.get('patches'), list)
        
    def test_save_and_load(self):
        """Test saving and loading settings."""
        settings = BuildSettings()
        settings.set('custom_option', 'test_value')
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            settings_path = f.name
            
        try:
            settings.save_to_file(settings_path)
            
            new_settings = BuildSettings(settings_path)
            self.assertEqual(new_settings.get('custom_option'), 'test_value')
            
        finally:
            Path(settings_path).unlink()


class TestCgroupConfig(unittest.TestCase):
    """Test cgroup configuration management."""
    
    def setUp(self):
        self.cgroup_config = CgroupConfig()
        
    def test_parse_cgroups_json(self):
        """Test parsing cgroups.json file."""
        test_config = {
            "Cgroups": [
                {"Controller": "cpu", "Path": "/dev/cpu"},
                {"Controller": "memory", "Path": "/dev/memcg"},
                {"Controller": "devices", "Path": "/dev/devices"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name
            
        try:
            config = self.cgroup_config.parse_cgroups_json(config_path)
            
            self.assertEqual(config, test_config)
            
            controllers = self.cgroup_config.get_cgroup_controllers()
            self.assertIn('cpu', controllers)
            self.assertIn('memory', controllers)
            self.assertIn('devices', controllers)
            
        finally:
            Path(config_path).unlink()
            
    def test_validate_docker_cgroups(self):
        """Test Docker cgroup validation."""
        # Complete cgroup configuration
        self.cgroup_config.cgroup_config = {
            "Cgroups": [
                {"Controller": "blkio", "Path": "/dev/blkio"},
                {"Controller": "cpu", "Path": "/dev/cpu"},
                {"Controller": "cpuacct", "Path": "/dev/cpuacct"},
                {"Controller": "cpuset", "Path": "/dev/cpuset"},
                {"Controller": "devices", "Path": "/dev/devices"},
                {"Controller": "freezer", "Path": "/dev/freezer"},
                {"Controller": "memory", "Path": "/dev/memcg"},
                {"Controller": "pids", "Path": "/dev/pids"}
            ]
        }
        
        is_valid, missing = self.cgroup_config.validate_docker_cgroups()
        self.assertTrue(is_valid)
        self.assertEqual(len(missing), 0)


class TestConfigurationManager(unittest.TestCase):
    """Test main configuration manager."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigurationManager(self.temp_dir)
        
    def test_initialization(self):
        """Test configuration manager initialization."""
        # Should create required directories
        expected_dirs = [
            'kernel_build/config',
            'kernel_build/scripts',
            'kernel_build/utils',
            'kernel_build/tests'
        ]
        
        for directory in expected_dirs:
            dir_path = Path(self.temp_dir) / directory
            self.assertTrue(dir_path.exists())
            
    def test_configuration_summary(self):
        """Test configuration summary generation."""
        summary = self.config_manager.get_configuration_summary()
        
        self.assertIn('kernel_config_loaded', summary)
        self.assertIn('total_docker_requirements', summary)
        self.assertIn('satisfied_requirements', summary)
        self.assertIn('build_settings', summary)


class TestConfigApplier(unittest.TestCase):
    """Test configuration applier."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.applier = ConfigApplier(self.temp_dir)
        
    def test_apply_docker_config(self):
        """Test applying Docker configuration to defconfig."""
        # Create test defconfig
        test_config = [
            "CONFIG_NAMESPACES=y",
            "CONFIG_CGROUPS=y",
            "# CONFIG_USER_NS is not set"
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f:
            f.write('\n'.join(test_config))
            config_path = f.name
            
        try:
            success, message = self.applier.apply_docker_config(
                config_path,
                backup=False,
                merge_mode='replace'
            )
            
            self.assertTrue(success)
            self.assertIn("applied", message.lower())
            
            # Verify Docker requirements were applied
            is_valid, missing = self.applier.validate_applied_config(config_path)
            # Should have fewer missing requirements than before
            self.assertLess(len(missing), 20)  # Some requirements should be satisfied
            
        finally:
            Path(config_path).unlink()
            
    def test_backup_and_restore(self):
        """Test backup and restore functionality."""
        # Create test config file
        test_content = "CONFIG_TEST=y\nCONFIG_EXAMPLE=m\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f:
            f.write(test_content)
            config_path = f.name
            
        try:
            # Apply configuration with backup
            success, message = self.applier.apply_docker_config(
                config_path,
                backup=True,
                merge_mode='replace'
            )
            
            self.assertTrue(success)
            
            # Check that backup was created
            backups = self.applier.list_backups()
            self.assertGreater(len(backups), 0)
            
            # Restore from backup
            backup_name = backups[0]['name']
            restore_path = config_path + '.restored'
            
            success, message = self.applier.restore_from_backup(backup_name, restore_path)
            self.assertTrue(success)
            
            # Verify restored content
            with open(restore_path, 'r') as f:
                restored_content = f.read()
                
            self.assertIn('CONFIG_TEST=y', restored_content)
            self.assertIn('CONFIG_EXAMPLE=m', restored_content)
            
            # Cleanup
            Path(restore_path).unlink()
            
        finally:
            Path(config_path).unlink()
            
    def test_merge_modes(self):
        """Test different merge modes."""
        # Create test config with some Docker options already set
        test_config = [
            "CONFIG_NAMESPACES=y",
            "CONFIG_CGROUPS=y",
            "CONFIG_MODULES=m",  # This should be preserved in smart merge
            "# CONFIG_USER_NS is not set"
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f:
            f.write('\n'.join(test_config))
            config_path = f.name
            
        try:
            # Test append mode
            success, message = self.applier.apply_docker_config(
                config_path,
                backup=False,
                merge_mode='append'
            )
            
            self.assertTrue(success)
            
            # Verify that existing options were preserved
            parser = KernelConfigParser()
            config = parser.parse_defconfig(config_path)
            
            self.assertEqual(config.get('CONFIG_NAMESPACES'), 'y')
            self.assertEqual(config.get('CONFIG_CGROUPS'), 'y')
            self.assertEqual(config.get('CONFIG_MODULES'), 'm')
            
        finally:
            Path(config_path).unlink()


class TestConfigMerger(unittest.TestCase):
    """Test configuration merger."""
    
    def setUp(self):
        self.merger = ConfigMerger()
        
    def test_merge_configs(self):
        """Test merging multiple configuration files."""
        # Create test config files
        config1_content = "CONFIG_A=y\nCONFIG_B=m\n"
        config2_content = "CONFIG_B=y\nCONFIG_C=n\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f1:
            f1.write(config1_content)
            config1_path = f1.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f2:
            f2.write(config2_content)
            config2_path = f2.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f3:
            output_path = f3.name
            
        try:
            success, message = self.merger.merge_configs(
                [config1_path, config2_path],
                output_path
            )
            
            self.assertTrue(success)
            
            # Verify merged configuration
            parser = KernelConfigParser()
            merged_config = parser.parse_defconfig(output_path)
            
            self.assertEqual(merged_config.get('CONFIG_A'), 'y')
            self.assertEqual(merged_config.get('CONFIG_B'), 'y')  # config2 should override
            self.assertEqual(merged_config.get('CONFIG_C'), 'n')
            
        finally:
            Path(config1_path).unlink()
            Path(config2_path).unlink()
            Path(output_path).unlink()
            
    def test_diff_configs(self):
        """Test configuration diff functionality."""
        config1_content = "CONFIG_A=y\nCONFIG_B=m\n"
        config2_content = "CONFIG_A=y\nCONFIG_B=y\nCONFIG_C=n\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f1:
            f1.write(config1_content)
            config1_path = f1.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as f2:
            f2.write(config2_content)
            config2_path = f2.name
            
        try:
            differences = self.merger.diff_configs(config1_path, config2_path)
            
            # Check differences
            self.assertIn('CONFIG_C', differences['added'])
            self.assertEqual(differences['added']['CONFIG_C'], 'n')
            
            self.assertIn('CONFIG_B', differences['changed'])
            self.assertEqual(differences['changed']['CONFIG_B']['from'], 'm')
            self.assertEqual(differences['changed']['CONFIG_B']['to'], 'y')
            
            self.assertIn('CONFIG_A', differences['unchanged'])
            self.assertEqual(differences['unchanged']['CONFIG_A'], 'y')
            
        finally:
            Path(config1_path).unlink()
            Path(config2_path).unlink()


if __name__ == '__main__':
    unittest.main()