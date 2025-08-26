#!/usr/bin/env python3
"""
CRIU Setup Script for Docker-enabled Android kernel.

This script configures CRIU for container checkpointing on Android devices.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.criu_manager import CRIUManager, CheckpointConfig
from migration.checkpoint_manager import CheckpointManager
from utils.file_utils import ensure_directory


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def install_criu_binary(target_path: str = "/data/local/tmp/criu") -> bool:
    """
    Install CRIU binary to target device.
    
    Args:
        target_path: Target path for CRIU binary
        
    Returns:
        bool: True if installation successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Check if CRIU binary exists in project
        criu_source = os.path.join(os.path.dirname(__file__), "..", "..", "criu", "criu")
        
        if not os.path.exists(criu_source):
            logger.error(f"CRIU binary not found at {criu_source}")
            return False
        
        # Push CRIU binary to device
        logger.info(f"Installing CRIU binary to {target_path}")
        result = subprocess.run(
            ["adb", "push", criu_source, target_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to push CRIU binary: {result.stderr}")
            return False
        
        # Make binary executable
        result = subprocess.run(
            ["adb", "shell", "chmod", "755", target_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to make CRIU executable: {result.stderr}")
            return False
        
        # Install required libraries
        lib_files = [
            "ld-musl-aarch64.so.1",
            "libbsd.so.0",
            "libffi.so.6",
            "libgmp.so.10",
            "libgnutls.so.30",
            "libhogweed.so.4",
            "libnet.so.1",
            "libnettle.so.6",
            "libnl-3.so.200",
            "libp11-kit.so.0",
            "libprotobuf-c.so.1",
            "libtasn1.so.6",
            "libunistring.so.2"
        ]
        
        criu_lib_dir = os.path.join(os.path.dirname(__file__), "..", "..", "criu")
        target_lib_dir = "/data/local/tmp/lib"
        
        # Create lib directory on device
        subprocess.run(
            ["adb", "shell", "mkdir", "-p", target_lib_dir],
            capture_output=True
        )
        
        for lib_file in lib_files:
            lib_source = os.path.join(criu_lib_dir, lib_file)
            if os.path.exists(lib_source):
                lib_target = f"{target_lib_dir}/{lib_file}"
                result = subprocess.run(
                    ["adb", "push", lib_source, lib_target],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    logger.warning(f"Failed to push library {lib_file}: {result.stderr}")
        
        logger.info("CRIU binary installation completed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to install CRIU binary: {e}")
        return False


def configure_criu_environment() -> bool:
    """Configure CRIU environment on device."""
    logger = logging.getLogger(__name__)
    
    try:
        # Create required directories
        directories = [
            "/data/local/tmp/checkpoints",
            "/data/local/tmp/migration",
            "/data/local/tmp/criu_work"
        ]
        
        for directory in directories:
            result = subprocess.run(
                ["adb", "shell", "mkdir", "-p", directory],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to create directory {directory}: {result.stderr}")
                return False
        
        # Set up environment variables
        env_setup = """
export LD_LIBRARY_PATH=/data/local/tmp/lib:$LD_LIBRARY_PATH
export PATH=/data/local/tmp:$PATH
"""
        
        # Write environment setup to device
        result = subprocess.run(
            ["adb", "shell", "echo", f"'{env_setup}'", ">", "/data/local/tmp/criu_env.sh"],
            capture_output=True,
            text=True
        )
        
        logger.info("CRIU environment configuration completed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure CRIU environment: {e}")
        return False


def test_criu_installation(criu_path: str = "/data/local/tmp/criu") -> bool:
    """Test CRIU installation."""
    logger = logging.getLogger(__name__)
    
    try:
        # Test CRIU check command
        logger.info("Testing CRIU installation...")
        result = subprocess.run(
            ["adb", "shell", f"cd /data/local/tmp && LD_LIBRARY_PATH=/data/local/tmp/lib {criu_path} check"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"CRIU check failed: {result.stderr}")
            logger.info("CRIU output: " + result.stdout)
            return False
        
        logger.info("CRIU installation test passed")
        logger.info("CRIU check output: " + result.stdout)
        return True
        
    except Exception as e:
        logger.error(f"Failed to test CRIU installation: {e}")
        return False


def create_sample_checkpoint_config() -> str:
    """Create sample checkpoint configuration file."""
    config = {
        "default_options": {
            "leave_running": False,
            "tcp_established": True,
            "shell_job": True,
            "ext_unix_sk": True,
            "file_locks": True
        },
        "checkpoint_dir": "/data/local/tmp/checkpoints",
        "work_dir": "/data/local/tmp/migration",
        "criu_binary": "/data/local/tmp/criu",
        "log_level": "info"
    }
    
    config_path = "/tmp/criu_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    return config_path


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Setup CRIU for container checkpointing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--criu-path", default="/data/local/tmp/criu", help="CRIU binary path on device")
    parser.add_argument("--install-only", action="store_true", help="Only install CRIU binary")
    parser.add_argument("--test-only", action="store_true", help="Only test CRIU installation")
    parser.add_argument("--config-only", action="store_true", help="Only configure environment")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting CRIU setup for Docker-enabled Android kernel")
    
    success = True
    
    if args.test_only:
        success = test_criu_installation(args.criu_path)
    elif args.install_only:
        success = install_criu_binary(args.criu_path)
    elif args.config_only:
        success = configure_criu_environment()
    else:
        # Full setup
        logger.info("Installing CRIU binary...")
        if not install_criu_binary(args.criu_path):
            success = False
        
        if success:
            logger.info("Configuring CRIU environment...")
            if not configure_criu_environment():
                success = False
        
        if success:
            logger.info("Testing CRIU installation...")
            if not test_criu_installation(args.criu_path):
                success = False
    
    if success:
        logger.info("CRIU setup completed successfully")
        
        # Create sample configuration
        config_path = create_sample_checkpoint_config()
        logger.info(f"Sample configuration created at: {config_path}")
        
        print("\nCRIU Setup Summary:")
        print(f"- CRIU binary installed at: {args.criu_path}")
        print("- Required libraries installed in: /data/local/tmp/lib")
        print("- Checkpoint directory: /data/local/tmp/checkpoints")
        print("- Migration work directory: /data/local/tmp/migration")
        print(f"- Sample configuration: {config_path}")
        print("\nTo use CRIU:")
        print("1. Source environment: source /data/local/tmp/criu_env.sh")
        print("2. Run CRIU check: criu check")
        print("3. Use CRIUManager class for checkpoint operations")
        
        return 0
    else:
        logger.error("CRIU setup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())