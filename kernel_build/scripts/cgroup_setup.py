#!/usr/bin/env python3
"""
Cgroup setup script for Docker-enabled Android kernel.

This script provides a command-line interface for managing cgroup configuration
and setup required for Docker container runtime.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.cgroup_manager import CgroupManager, main

if __name__ == "__main__":
    exit(main())