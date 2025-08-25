#!/usr/bin/env python3
"""
File utilities for kernel build system.
Provides common file operations and path management.
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import List, Optional, Dict


def ensure_directory(path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to create
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def backup_file(file_path: str, backup_suffix: str = ".backup") -> Optional[str]:
    """
    Create a backup of a file.
    
    Args:
        file_path: Path to file to backup
        backup_suffix: Suffix to add to backup file
        
    Returns:
        Path to backup file, or None if original doesn't exist
    """
    source_path = Path(file_path)
    if not source_path.exists():
        return None
        
    backup_path = source_path.with_suffix(source_path.suffix + backup_suffix)
    shutil.copy2(source_path, backup_path)
    return str(backup_path)


def restore_file(backup_path: str, original_path: Optional[str] = None) -> bool:
    """
    Restore a file from backup.
    
    Args:
        backup_path: Path to backup file
        original_path: Path to restore to (defaults to backup path without suffix)
        
    Returns:
        True if restore successful, False otherwise
    """
    backup_file_path = Path(backup_path)
    if not backup_file_path.exists():
        return False
        
    if original_path is None:
        # Remove backup suffix to get original path
        original_path = str(backup_file_path).replace('.backup', '')
        
    original_file_path = Path(original_path)
    shutil.copy2(backup_file_path, original_file_path)
    return True


def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm to use
        
    Returns:
        Hex digest of file hash
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
            
    return hash_obj.hexdigest()


def find_files(directory: str, pattern: str = "*", recursive: bool = True) -> List[str]:
    """
    Find files matching a pattern in a directory.
    
    Args:
        directory: Directory to search in
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []
        
    if recursive:
        matches = dir_path.rglob(pattern)
    else:
        matches = dir_path.glob(pattern)
        
    return [str(match) for match in matches if match.is_file()]


def copy_with_permissions(source: str, destination: str) -> bool:
    """
    Copy file preserving permissions and metadata.
    
    Args:
        source: Source file path
        destination: Destination file path
        
    Returns:
        True if copy successful, False otherwise
    """
    try:
        shutil.copy2(source, destination)
        return True
    except (IOError, OSError):
        return False


def make_executable(file_path: str) -> bool:
    """
    Make a file executable.
    
    Args:
        file_path: Path to file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        current_mode = os.stat(file_path).st_mode
        os.chmod(file_path, current_mode | 0o755)
        return True
    except (IOError, OSError):
        return False


def read_file_lines(file_path: str, strip_whitespace: bool = True) -> List[str]:
    """
    Read all lines from a file.
    
    Args:
        file_path: Path to file
        strip_whitespace: Whether to strip whitespace from lines
        
    Returns:
        List of lines from file
    """
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        if strip_whitespace:
            lines = [line.strip() for line in lines]
            
        return lines
    except (IOError, OSError):
        return []


def write_file_lines(file_path: str, lines: List[str], append: bool = False) -> bool:
    """
    Write lines to a file.
    
    Args:
        file_path: Path to file
        lines: Lines to write
        append: Whether to append to existing file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        mode = 'a' if append else 'w'
        with open(file_path, mode) as f:
            for line in lines:
                f.write(line + '\n')
        return True
    except (IOError, OSError):
        return False


def get_file_info(file_path: str) -> Optional[Dict]:
    """
    Get information about a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file information, or None if file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        return None
        
    stat = path.stat()
    
    return {
        'path': str(path.absolute()),
        'size': stat.st_size,
        'modified': stat.st_mtime,
        'permissions': oct(stat.st_mode)[-3:],
        'is_executable': os.access(path, os.X_OK),
        'hash': calculate_file_hash(file_path)
    }