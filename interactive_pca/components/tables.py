"""
Table component helpers for AG Grid configuration.
"""

from .config import LAYOUT_CONFIG


def create_checkbox_column_def():
    """Create standardized checkbox column definition for tables."""
    return {
        'headerName': '',
        'field': 'Selected',
        'editable': True,
        'cellEditor': 'agCheckboxCellEditor',
        'cellRenderer': 'agCheckboxCellRenderer',
        'width': LAYOUT_CONFIG['checkbox_column_width'],
        'suppressMenu': True,
        'pinned': 'left'
    }


def create_standard_column_def(field, header_name=None, **kwargs):
    """Create a standard column definition with common defaults."""
    return {
        'field': field,
        'headerName': header_name or field,
        'sortable': True,
        'filter': True,
        **kwargs
    }
