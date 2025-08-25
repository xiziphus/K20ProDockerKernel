"""
Storage and filesystem support for Docker-enabled kernel.

This module provides overlay filesystem setup, volume management,
and bind mount support for container storage requirements.
"""

from .overlay_manager import OverlayManager
from .volume_manager import VolumeManager

__all__ = ['OverlayManager', 'VolumeManager']