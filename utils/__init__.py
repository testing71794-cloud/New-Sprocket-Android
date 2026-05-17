"""Shared utilities (device names, path helpers)."""

from .device_utils import get_device_display_name, get_device_name, render_device_display
from .git_branch import detect_git_branch, write_git_branch_file

__all__ = [
    "detect_git_branch",
    "get_device_display_name",
    "get_device_name",
    "render_device_display",
    "write_git_branch_file",
]
