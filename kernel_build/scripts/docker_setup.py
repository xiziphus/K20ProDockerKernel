#!/usr/bin/env python3
"""
Docker daemon setup script for Docker-enabled Android kernel.

This script provides a command-line interface for managing Docker daemon
setup, configuration, and lifecycle on Android devices.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.docker_daemon import DockerDaemonManager, main

if __name__ == "__main__":
    exit(main())