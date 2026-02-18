"""
Callbacks module for interactive PCA application.

This module organizes all Dash callbacks by functionality.
"""

from .selection import register_selection_callbacks
from .plots import register_plot_callbacks
from .aesthetics import register_aesthetics_callbacks


def register_all_callbacks(app, args, df, pcs, annotation_desc, 
                           ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG):
    """
    Register all callbacks for the application.
    
    Args:
        app: Dash app instance
        args: Command-line arguments
        df: Main DataFrame
        pcs: List of PC column names
        annotation_desc: Annotation description DataFrame
        ANNOTATION_TIME: Time column name
        ANNOTATION_LAT: Latitude column name
        ANNOTATION_LONG: Longitude column name
    """
    register_selection_callbacks(app, df, annotation_desc)
    register_plot_callbacks(app, args, df, ANNOTATION_LAT, ANNOTATION_LONG, ANNOTATION_TIME, annotation_desc)
    register_aesthetics_callbacks(app, args, df, annotation_desc)


__all__ = [
    'register_all_callbacks',
    'register_selection_callbacks',
    'register_plot_callbacks',
    'register_aesthetics_callbacks',
]
