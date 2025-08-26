#!/usr/bin/env python3
"""
Network setup script for Docker-enabled Android kernel.

This script provides a command-line interface for managing Docker network
configuration, bridge setup, and iptables rules on Android devices.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.network_manager import NetworkManager, main

if __name__ == "__main__":
    exit(main())