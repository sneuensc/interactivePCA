"""
Callbacks module for interactive PCA application.

This module organizes all Dash callbacks by functionality.
"""

from .selection import register_selection_callbacks
from .plots import register_plot_callbacks
from .aesthetics import register_aesthetics_callbacks
from .hover_sync import register_hover_sync_callbacks
from .hover_details import register_hover_details_callback
from .legend_sync import register_legend_sync_callbacks
from .session import register_session_callbacks
from .settings2 import register_settings2_callbacks
from ..data_loader import resolve_column_set


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
    # The map/time panels (and their callbacks) exist whenever annotation data
    # is loaded, regardless of whether --latitude/--longitude/--time happen to
    # already resolve — see app.py's matching comment. Which columns actually
    # feed them, if any, is a live pick via the Settings 2 tab.
    show_annotation_table = annotation_desc is not None
    show_map_plot = show_annotation_table
    show_time_plot = show_annotation_table

    # Which continuous columns' time-plot x-axis starts reversed — defaults to
    # just the resolved --time column unless --time-invert-columns opts into
    # an explicit list (see data_loader.resolve_column_set / app.py's own
    # identical resolution for the initial figure).
    time_invert_columns = resolve_column_set(
        args.time_invert_columns, annotation_desc, fallback_columns=(ANNOTATION_TIME,)
    )
    # Which continuous columns' time-plot starts with x/y swapped — no
    # implicit default, just whatever --time-rotate-columns explicitly lists.
    time_rotate_columns = resolve_column_set(args.time_rotate_columns, annotation_desc)

    register_selection_callbacks(
        app,
        df,
        annotation_desc,
        show_annotation_table=show_annotation_table,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
        time_invert_columns=time_invert_columns,
        time_rotate_columns=time_rotate_columns,
    )
    register_plot_callbacks(
        app,
        args,
        df,
        ANNOTATION_LAT,
        ANNOTATION_LONG,
        ANNOTATION_TIME,
        annotation_desc,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
    )
    register_aesthetics_callbacks(app, args, df, annotation_desc)
    register_hover_sync_callbacks(
        app,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
    )
    register_legend_sync_callbacks(
        app,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
    )
    register_session_callbacks(
        app,
        args,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
        show_annotation_table=show_annotation_table,
    )
    register_settings2_callbacks(
        app,
        args,
        show_map_plot=show_map_plot,
        show_time_plot=show_time_plot,
        show_annotation_table=show_annotation_table,
    )
    if show_annotation_table:
        register_hover_details_callback(
            app, df, annotation_desc,
            show_map_plot=show_map_plot,
            show_time_plot=show_time_plot,
        )


__all__ = [
    'register_all_callbacks',
    'register_selection_callbacks',
    'register_plot_callbacks',
    'register_aesthetics_callbacks',
    'register_hover_sync_callbacks',
]
