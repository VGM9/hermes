"""
Data models package.

All models are immutable (frozen dataclasses) to ensure functional purity.
"""

from .approval_request import ApprovalRequest, WindowInfo, UIElement

__all__ = [
    'ApprovalRequest',
    'WindowInfo',
    'UIElement',
]
