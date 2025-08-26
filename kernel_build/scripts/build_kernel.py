#!/usr/bin/env python3
"""
Kernel Build Script for Docker-enabled K20 Pro Kernel

Command-line interface for automated kernel compilation with progress monitoring.
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build.kernel_builder import KernelBuilder, BuildConfig, BuildProgress

class ProgressDisplay:
    """Progress display for command-line interface"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.last_stage = ""
        self.start_time = None
    
    def update_progress(self, progress: BuildProgress):
        """Update progress display"""
        if self.start_time is None:
            self.start_time = progress.start_time
        
        # Clear line and show progress
        if not self.verbose:
            print(f"\r[{progress.stage.upper()}] {progress.message} - {progress.percentage:.1f}% ({progress.current_step}/{progress.total_steps})", end="", flush=True)
        else:
            if progress.stage != self.last_stage:
                print(f"\n=== {progress.stage.upper()} ===")
                self.last_stage = progress.stage
            print(f"  {progress.message} ({progress.current_step}/{progress.total_steps}) - {progress.percentage:.1f}%")
    
    def finish(self):
        """Finish progress display"""
        if not self.verbose:
            print()  # New line after progress

def print_banner():
    """Print build banner"""
    print("=" * 70)
    print("Docker-enabled K20 Pro Kernel - Automated Build System")
    print("=" * 70)
    print()

def create_default_config(args) -> BuildConfig:
    """Create default build configuration"""
    workspace_root = Path.cwd()
    
    # Default paths
    source_path = str(workspace_root / "kernel_source")
    output_path = str(workspace_root / "kernel_build" / "output" / "build")
    config_file = str(workspace_root / "kernel_build" / "output" / "docker_raphael_defconfig")
    toolchain_config = str(workspace_root / "kernel_build" / "build" / "config" / "toolchain_config.json")
    
    # Override with command line arguments
    if args.source:
        source_path = args.source
    if args.output:
        output_path = args.output
    if args.config_file:
        config_file = args.config_file
    if args.toolchain:
        toolchain_config = args.toolchain
    
    return BuildConfig(
        source_path=source_path,
        output_path=output_path,
        config_file=config_file,
        toolchain_config=toolchain_config,
        target_device=args.target,
        parallel_jobs=args.jobs,
        clean_build=args.clean,
        verbose=args.verbose
    )

def validate_build_prerequisites(config: BuildConfig) -> bool:
    """Validate build prerequisites"""
    print("Validating build prerequisites...")
    
    errors = []
    
    # Check source directory
    if not Path(config.source_path).exists():
        errors.append(f"Kernel source directory not found: {config.source_path}")
    
    # Check configuration file
    if not Path(config.config_file).exists():
        errors.append(f"Kernel configuration file not found: {config.config_file}")
    
    # Check toolchain configuration
    if not Path(config.toolchain_config).exists():
        errors.append(f"Toolchain configuration not found: {config.toolchain_config}")
    
    # Check if source looks like a kernel source tree
    if Path(config.source_path).exists():
        essential_files = ["Makefile", "Kconfig", "arch", "kernel", "drivers"]
        missing_files = []
        
        for file_path in essential_files:
            if not (Path(config.source_path) / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            errors.append(f"Source directory doesn't look like kernel source. Missing: {missing_files}")
    
    if errors:
        print("❌ Prerequisites validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("✅ Prerequisites validation passed")
    return True

def show_build_summary(config: BuildConfig):
    """Show build configuration summary"""
    print("Build Configuration:")
    print("-" * 50)
    print(f"Source Path:      {config.source_path}")
    print(f"Output Path:      {config.output_path}")
    print(f"Config File:      {config.config_file}")
    print(f"Toolchain Config: {config.toolchain_config}")
    print(f"Target Device:    {config.target_device}")
    print(f"Parallel Jobs:    {config.parallel_jobs if config.parallel_jobs > 0 else 'auto-detect'}")
    print(f"Clean Build:      {'Yes' if config.clean_build else 'No'}")
    print(f"Verbose:          {'Yes' if config.verbose else 'No'}")
    print()

def build_kernel_interactive(args):
    """Interactive kernel build"""
    print_banner()
    
    # Create configuration
    if args.build_config:
        print(f"Loading build configuration from: {args.build_config}")
        builder = KernelBuilder()
        config = builder.load_build_config(args.build_config)
        
        # Override with command line arguments
        if args.clean:
            config.clean_build = True
        if args.verbose:
            config.verbose = True
        if args.jobs > 0:
            config.parallel_jobs = args.jobs
    else:
        config = create_default_config(args)
    
    # Show configuration
    show_build_summary(config)
    
    # Validate prerequisites
    if not validate_build_prerequisites(config):
        return False
    
    # Confirm build
    if not args.yes:
        response = input("Proceed with kernel build? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Build cancelled.")
            return False
    
    print("\nStarting kernel build...")
    print("=" * 50)
    
    # Setup progress display
    progress_display = ProgressDisplay(config.verbose)
    
    # Create builder and set progress callback
    builder = KernelBuilder()
    builder.set_progress_callback(progress_display.update_progress)
    
    # Start build
    start_time = time.time()
    result = builder.build_kernel(config)
    build_time = time.time() - start_time
    
    # Finish progress display
    progress_display.finish()
    
    # Show results
    print("\n" + "=" * 50)
    print("BUILD RESULTS")
    print("=" * 50)
    
    if result.success:
        print("✅ Build completed successfully!")
    else:
        print("❌ Build failed!")
    
    print(f"Build Time: {result.build_time:.1f} seconds")
    
    if result.output_files:
        print(f"\nOutput Files ({len(result.output_files)}):")
        for artifact in result.output_files:
            file_size = Path(artifact).stat().st_size if Path(artifact).exists() else 0
            print(f"  ✓ {artifact} ({file_size:,} bytes)")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors:
            print(f"  ❌ {error}")
    
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")
    
    if result.log_file:
        print(f"\nDetailed log: {result.log_file}")
    
    return result.success

def save_build_config_interactive(args):
    """Save build configuration interactively"""
    config = create_default_config(args)
    
    print("Creating build configuration...")
    show_build_summary(config)
    
    # Save configuration
    config_file = args.save_config
    builder = KernelBuilder()
    builder.save_build_config(config, config_file)
    
    print(f"✅ Build configuration saved to: {config_file}")
    return True

def show_build_info(args):
    """Show build environment information"""
    print_banner()
    
    builder = KernelBuilder()
    
    print("Build Environment Information:")
    print("-" * 50)
    
    # CPU information
    cpu_count = builder.detect_cpu_count()
    print(f"Detected CPU cores: {cpu_count}")
    
    # Check toolchain
    toolchain_config = args.toolchain or str(Path.cwd() / "kernel_build" / "build" / "config" / "toolchain_config.json")
    
    if Path(toolchain_config).exists():
        print(f"Toolchain config: {toolchain_config}")
        
        toolchain = builder.toolchain_manager.load_toolchain_config(toolchain_config)
        if toolchain:
            print(f"Toolchain: {toolchain.name} ({toolchain.version})")
            print(f"Architecture: {toolchain.arch}")
            print(f"Validated: {'✅' if toolchain.validated else '❌'}")
    else:
        print("❌ Toolchain configuration not found")
        print("   Run: python toolchain_setup.py setup")
    
    # Check kernel source
    source_path = args.source or str(Path.cwd() / "kernel_source")
    if Path(source_path).exists():
        print(f"✅ Kernel source: {source_path}")
    else:
        print(f"❌ Kernel source not found: {source_path}")
    
    return True

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Automated Kernel Build System for Docker-enabled K20 Pro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build kernel with default configuration
  python build_kernel.py build

  # Build with custom paths
  python build_kernel.py build --source /path/to/kernel --output /path/to/output

  # Clean build with 8 parallel jobs
  python build_kernel.py build --clean --jobs 8

  # Save build configuration
  python build_kernel.py save-config --save-config build_config.json

  # Show build environment info
  python build_kernel.py info
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Build kernel')
    build_parser.add_argument('--source', help='Kernel source directory')
    build_parser.add_argument('--output', help='Build output directory')
    build_parser.add_argument('--config-file', help='Kernel configuration file')
    build_parser.add_argument('--toolchain', help='Toolchain configuration file')
    build_parser.add_argument('--target', default='raphael', help='Target device (default: raphael)')
    build_parser.add_argument('--jobs', type=int, default=0, help='Number of parallel jobs (0=auto)')
    build_parser.add_argument('--clean', action='store_true', help='Clean build')
    build_parser.add_argument('--verbose', action='store_true', help='Verbose output')
    build_parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    build_parser.add_argument('--build-config', help='Load build configuration from file')
    
    # Save config command
    save_parser = subparsers.add_parser('save-config', help='Save build configuration')
    save_parser.add_argument('--save-config', required=True, help='Configuration file to save')
    save_parser.add_argument('--source', help='Kernel source directory')
    save_parser.add_argument('--output', help='Build output directory')
    save_parser.add_argument('--config-file', help='Kernel configuration file')
    save_parser.add_argument('--toolchain', help='Toolchain configuration file')
    save_parser.add_argument('--target', default='raphael', help='Target device')
    save_parser.add_argument('--jobs', type=int, default=0, help='Number of parallel jobs')
    save_parser.add_argument('--clean', action='store_true', help='Clean build by default')
    save_parser.add_argument('--verbose', action='store_true', help='Verbose output by default')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show build environment information')
    info_parser.add_argument('--source', help='Kernel source directory to check')
    info_parser.add_argument('--toolchain', help='Toolchain configuration file to check')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    success = False
    
    try:
        if args.command == 'build':
            success = build_kernel_interactive(args)
        elif args.command == 'save-config':
            success = save_build_config_interactive(args)
        elif args.command == 'info':
            success = show_build_info(args)
        
        if success:
            print("\n✅ Operation completed successfully!")
        else:
            print("\n❌ Operation failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()