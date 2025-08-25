#!/usr/bin/env python3
"""
Command-line tool for kernel configuration management.
Provides interface for validating and managing Docker kernel configurations.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kernel_build.config.config_manager import ConfigurationManager
from kernel_build.config.applier import ConfigApplier, ConfigMerger


def main():
    """Main entry point for configuration tool."""
    parser = argparse.ArgumentParser(
        description="Docker-enabled kernel configuration management tool"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate kernel configuration')
    validate_parser.add_argument('--defconfig', required=True, help='Path to kernel defconfig file')
    validate_parser.add_argument('--cgroups', help='Path to cgroups.json file')
    validate_parser.add_argument('--output', help='Output file for validation report')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate Docker-enabled configuration')
    generate_parser.add_argument('--defconfig', required=True, help='Path to input defconfig file')
    generate_parser.add_argument('--output', required=True, help='Path to output Docker-enabled defconfig')
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show configuration summary')
    summary_parser.add_argument('--defconfig', required=True, help='Path to kernel defconfig file')
    summary_parser.add_argument('--cgroups', help='Path to cgroups.json file')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export all configurations')
    export_parser.add_argument('--defconfig', required=True, help='Path to kernel defconfig file')
    export_parser.add_argument('--cgroups', help='Path to cgroups.json file')
    export_parser.add_argument('--output-dir', required=True, help='Output directory for exported files')
    
    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply Docker configurations to defconfig')
    apply_parser.add_argument('--defconfig', required=True, help='Path to kernel defconfig file')
    apply_parser.add_argument('--output', help='Output path (defaults to input file)')
    apply_parser.add_argument('--backup', action='store_true', default=True, help='Create backup before applying')
    apply_parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    apply_parser.add_argument('--merge-mode', choices=['replace', 'merge', 'append'], default='replace',
                             help='How to merge configurations')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore configuration from backup')
    restore_parser.add_argument('--backup', required=True, help='Backup file name')
    restore_parser.add_argument('--target', required=True, help='Target file to restore to')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Manage configuration backups')
    backup_parser.add_argument('--list', action='store_true', help='List available backups')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge multiple configuration files')
    merge_parser.add_argument('--configs', nargs='+', required=True, help='Configuration files to merge')
    merge_parser.add_argument('--output', required=True, help='Output path for merged configuration')
    merge_parser.add_argument('--priority', nargs='*', help='Priority order for conflicting options')
    
    # Diff command
    diff_parser = subparsers.add_parser('diff', help='Compare two configuration files')
    diff_parser.add_argument('--config1', required=True, help='First configuration file')
    diff_parser.add_argument('--config2', required=True, help='Second configuration file')
    diff_parser.add_argument('--output', help='Output file for diff report')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
        
    # Initialize configuration manager
    config_manager = ConfigurationManager()
    
    try:
        if args.command == 'validate':
            return handle_validate(config_manager, args)
        elif args.command == 'generate':
            return handle_generate(config_manager, args)
        elif args.command == 'summary':
            return handle_summary(config_manager, args)
        elif args.command == 'export':
            return handle_export(config_manager, args)
        elif args.command == 'apply':
            return handle_apply(args)
        elif args.command == 'restore':
            return handle_restore(args)
        elif args.command == 'backup':
            return handle_backup(args)
        elif args.command == 'merge':
            return handle_merge(args)
        elif args.command == 'diff':
            return handle_diff(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    return 0


def handle_validate(config_manager: ConfigurationManager, args) -> int:
    """Handle validate command."""
    print("Loading kernel configuration...")
    config_manager.load_kernel_config(args.defconfig)
    
    if args.cgroups:
        print("Loading cgroup configuration...")
        config_manager.load_cgroup_config(args.cgroups)
        
    print("Validating configuration against Docker requirements...")
    is_valid, report = config_manager.validate_configuration()
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Validation report written to: {args.output}")
    else:
        print("\n" + report)
        
    if is_valid:
        print("\n✅ Configuration is valid for Docker!")
        return 0
    else:
        print("\n❌ Configuration has issues that need to be addressed.")
        return 1


def handle_generate(config_manager: ConfigurationManager, args) -> int:
    """Handle generate command."""
    print("Loading kernel configuration...")
    config_manager.load_kernel_config(args.defconfig)
    
    print("Generating Docker-enabled configuration...")
    success = config_manager.generate_docker_config(args.output)
    
    if success:
        print(f"✅ Docker-enabled configuration written to: {args.output}")
        
        # Show what was added
        missing = config_manager.get_missing_requirements()
        if missing:
            print(f"\nAdded {len(missing)} Docker requirements:")
            for req in missing[:10]:  # Show first 10
                print(f"  + {req}")
            if len(missing) > 10:
                print(f"  ... and {len(missing) - 10} more")
        else:
            print("\nNo additional requirements needed - configuration already Docker-ready!")
            
        return 0
    else:
        print("❌ Failed to generate Docker configuration")
        return 1


def handle_summary(config_manager: ConfigurationManager, args) -> int:
    """Handle summary command."""
    print("Loading kernel configuration...")
    config_manager.load_kernel_config(args.defconfig)
    
    if args.cgroups:
        print("Loading cgroup configuration...")
        config_manager.load_cgroup_config(args.cgroups)
        
    summary = config_manager.get_configuration_summary()
    
    print("\n=== Configuration Summary ===")
    print(f"Kernel config loaded: {'✅' if summary['kernel_config_loaded'] else '❌'}")
    print(f"Docker requirements: {summary['satisfied_requirements']}/{summary['total_docker_requirements']} " +
          f"({summary['satisfaction_percentage']:.1f}%)")
    
    if summary['cgroup_controllers_count'] > 0:
        print(f"Cgroup controllers: {summary['cgroup_controllers_count']}")
        print(f"Cgroup config valid: {'✅' if summary['cgroup_config_valid'] else '❌'}")
        
        if summary['missing_cgroup_controllers']:
            print(f"Missing cgroup controllers: {', '.join(summary['missing_cgroup_controllers'])}")
            
    print(f"\nBuild settings:")
    build_settings = summary['build_settings']
    print(f"  Target device: {build_settings.get('target_device', 'unknown')}")
    print(f"  Architecture: {build_settings.get('arch', 'unknown')}")
    print(f"  Cross compile: {build_settings.get('cross_compile', 'unknown')}")
    
    return 0


def handle_export(config_manager: ConfigurationManager, args) -> int:
    """Handle export command."""
    print("Loading kernel configuration...")
    config_manager.load_kernel_config(args.defconfig)
    
    if args.cgroups:
        print("Loading cgroup configuration...")
        config_manager.load_cgroup_config(args.cgroups)
        
    print(f"Exporting configurations to: {args.output_dir}")
    success = config_manager.export_configuration(args.output_dir)
    
    if success:
        print("✅ Configuration export completed!")
        print(f"\nExported files:")
        export_path = Path(args.output_dir)
        for file_path in export_path.glob('*'):
            if file_path.is_file():
                print(f"  📄 {file_path.name}")
        return 0
    else:
        print("❌ Configuration export failed")
        return 1


def handle_apply(args) -> int:
    """Handle apply command."""
    applier = ConfigApplier()
    
    backup = args.backup and not args.no_backup
    
    print(f"Applying Docker configurations to: {args.defconfig}")
    if backup:
        print("Creating backup before applying changes...")
        
    success, message = applier.apply_docker_config(
        args.defconfig,
        args.output,
        backup=backup,
        merge_mode=args.merge_mode
    )
    
    if success:
        print(f"✅ {message}")
        
        # Validate applied configuration
        target_path = args.output or args.defconfig
        is_valid, missing = applier.validate_applied_config(target_path)
        
        if is_valid:
            print("✅ All Docker requirements successfully applied!")
        else:
            print(f"⚠️  Some requirements may not have been applied correctly:")
            for missing_opt in missing[:5]:  # Show first 5
                print(f"  - {missing_opt}")
            if len(missing) > 5:
                print(f"  ... and {len(missing) - 5} more")
                
        return 0
    else:
        print(f"❌ {message}")
        return 1


def handle_restore(args) -> int:
    """Handle restore command."""
    applier = ConfigApplier()
    
    print(f"Restoring configuration from backup: {args.backup}")
    success, message = applier.restore_from_backup(args.backup, args.target)
    
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def handle_backup(args) -> int:
    """Handle backup command."""
    applier = ConfigApplier()
    
    if args.list:
        backups = applier.list_backups()
        
        if not backups:
            print("No backups found.")
            return 0
            
        print(f"\nAvailable backups ({len(backups)}):")
        print("-" * 80)
        print(f"{'Name':<40} {'Size':<10} {'Created':<20}")
        print("-" * 80)
        
        for backup in backups:
            size_kb = backup['size'] // 1024
            created = backup['created'][:19].replace('T', ' ')
            print(f"{backup['name']:<40} {size_kb:>7} KB {created}")
            
        return 0
    else:
        print("Use --list to show available backups")
        return 1


def handle_merge(args) -> int:
    """Handle merge command."""
    merger = ConfigMerger()
    
    print(f"Merging {len(args.configs)} configuration files...")
    for config in args.configs:
        print(f"  - {config}")
        
    success, message = merger.merge_configs(
        args.configs,
        args.output,
        args.priority
    )
    
    if success:
        print(f"✅ {message}")
        print(f"Merged configuration written to: {args.output}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def handle_diff(args) -> int:
    """Handle diff command."""
    merger = ConfigMerger()
    
    print(f"Comparing configurations:")
    print(f"  Config 1: {args.config1}")
    print(f"  Config 2: {args.config2}")
    
    try:
        differences = merger.diff_configs(args.config1, args.config2)
        
        # Generate diff report
        report_lines = []
        report_lines.append("=== Configuration Diff Report ===\n")
        
        if differences['added']:
            report_lines.append(f"ADDED ({len(differences['added'])}):")
            for option, value in sorted(differences['added'].items()):
                report_lines.append(f"  + {option}={value}")
            report_lines.append("")
            
        if differences['removed']:
            report_lines.append(f"REMOVED ({len(differences['removed'])}):")
            for option, value in sorted(differences['removed'].items()):
                report_lines.append(f"  - {option}={value}")
            report_lines.append("")
            
        if differences['changed']:
            report_lines.append(f"CHANGED ({len(differences['changed'])}):")
            for option, change in sorted(differences['changed'].items()):
                report_lines.append(f"  ~ {option}: {change['from']} → {change['to']}")
            report_lines.append("")
            
        report_lines.append(f"UNCHANGED: {len(differences['unchanged'])} options")
        
        report = "\n".join(report_lines)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Diff report written to: {args.output}")
        else:
            print("\n" + report)
            
        return 0
        
    except Exception as e:
        print(f"❌ Error comparing configurations: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())