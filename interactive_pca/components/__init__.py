"""
Components module for interactive PCA application.

This module provides reusable UI components and utilities.
"""

from .tables import create_checkbox_column_def, create_standard_column_def
from .aesthetics import (
    load_aesthetics_file,
    merge_aesthetics,
    get_init_aesthetics,
    get_aesthetics_for_group
)
from .hover import (
    build_hover_text,
    update_figure_hover_templates,
    register_hover_update_callbacks
)
from .config import LAYOUT_CONFIG

__all__ = [
    'create_checkbox_column_def',
    'create_standard_column_def',
    'load_aesthetics_file',
    'merge_aesthetics',
    'get_init_aesthetics',
    'get_aesthetics_for_group',
    'build_hover_text',
    'update_figure_hover_templates',
    'register_hover_update_callbacks',
    'LAYOUT_CONFIG',
]
