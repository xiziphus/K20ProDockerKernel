#!/usr/bin/env python3
"""
Storage setup script for Docker-enabled kernel.

This script configures overlay filesystem support and storage drivers
for Docker container storage on Android devices.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.overlay_manager import OverlayManager
from storage.volume_manager import VolumeManager


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('storage_setup.log')
        ]
    )


def main():
    """Main function for storage setup."""
    parser = argparse.ArgumentParser(
        description="Set up overlay filesystem for Docker containers"
    )
    parser.add_argument(
        "--base-path", 
        default="/data/docker",
        help="Base path for Docker storage (default: /data/docker)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing setup, don't create new"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true", 
        help="Clean up existing overlay storage (WARNING: removes all data)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting storage setup for Docker-enabled kernel")
    
    # Initialize managers
    overlay_manager = OverlayManager(args.base_path)
    volume_manager = VolumeManager(args.base_path)
    
    try:
        if args.cleanup:
            logger.warning("Cleaning up storage...")
            overlay_success = overlay_manager.cleanup_overlay_storage()
            volume_success = volume_manager.cleanup_volumes(remove_unused=True)
            
            if overlay_success and volume_success:
                logger.info("Storage cleanup completed successfully")
            else:
                logger.error("Storage cleanup failed")
                return 1
        
        if args.validate_only:
            logger.info("Validating storage setup...")
            
            # Validate overlay filesystem
            overlay_results = overlay_manager.validate_overlay_setup()
            print("\n=== Overlay Filesystem Validation Results ===")
            for component, status in overlay_results.items():
                status_str = "✓ PASS" if status else "✗ FAIL"
                print(f"{component:20}: {status_str}")
            
            # Validate volume management
            volume_results = volume_manager.validate_volume_setup()
            print("\n=== Volume Management Validation Results ===")
            for component, status in volume_results.items():
                status_str = "✓ PASS" if status else "✗ FAIL"
                print(f"{component:20}: {status_str}")
            
            # Show storage information
            storage_info = overlay_manager.get_storage_info()
            volume_info = volume_manager.get_volume_info()
            
            print(f"\n=== Storage Information ===")
            print(f"Base Path: {storage_info['base_path']}")
            print(f"Overlay Path: {storage_info['overlay_path']}")
            print(f"Volumes Path: {volume_info['volumes_path']}")
            print(f"Total Volumes: {volume_info['total_volumes']}")
            print(f"Total Bind Mounts: {volume_info['total_bind_mounts']}")
            
            if storage_info.get('total_size', 0) > 0:
                total_gb = storage_info['total_size'] / (1024**3)
                used_gb = storage_info['used_size'] / (1024**3)
                avail_gb = storage_info['available_size'] / (1024**3)
                print(f"Total Size: {total_gb:.2f} GB")
                print(f"Used Size: {used_gb:.2f} GB")
                print(f"Available Size: {avail_gb:.2f} GB")
            
            # Return non-zero if any validation failed
            all_results = {**overlay_results, **volume_results}
            if not all(all_results.values()):
                return 1
        else:
            logger.info("Setting up storage systems...")
            
            # Setup overlay filesystem
            overlay_success = overlay_manager.setup_overlay_filesystem()
            if overlay_success:
                logger.info("Overlay filesystem setup completed successfully")
            else:
                logger.error("Overlay filesystem setup failed")
                return 1
            
            # Setup volume management
            volume_success = volume_manager.setup_volume_support()
            if volume_success:
                logger.info("Volume management setup completed successfully")
            else:
                logger.error("Volume management setup failed")
                return 1
            
            # Validate the complete setup
            overlay_results = overlay_manager.validate_overlay_setup()
            volume_results = volume_manager.validate_volume_setup()
            
            all_results = {**overlay_results, **volume_results}
            if all(all_results.values()):
                logger.info("Complete storage setup validation passed")
            else:
                logger.warning("Storage setup validation found issues")
                for component, status in all_results.items():
                    if not status:
                        logger.warning(f"Validation failed for: {component}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())