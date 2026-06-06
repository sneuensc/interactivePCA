"""
Plotting functions for PCA visualization.
"""

import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from functools import lru_cache
from .utils import dict_of_dicts_to_tuple, tuple_to_dict_of_dicts


# Global DataFrame - set once at app initialization
_df = None


def _to_rgba(color: str, opacity: float) -> str:
    """Return an rgba() string that encodes *opacity* into *color*.

    Handles #rrggbb, #rgb, and named CSS colours that happen to be hex-safe.
    Falls back to the original colour string on parse failure.
    """
    try:
        c = color.strip().lstrip('#')
        if len(c) == 3:
            c = c[0]*2 + c[1]*2 + c[2]*2
        if len(c) == 6:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return f'rgba({r},{g},{b},{opacity})'
    except (ValueError, AttributeError):
        pass
    return color


def set_dataframe(df):
    """
    Set the global DataFrame for plotting functions.
    Call this once after loading data in create_app().
    
    Args:
        df: DataFrame with PCA and annotation data
    """
    global _df
    _df = df


def get_selected_df(selected_ids):
    """Get DataFrame subset with selected IDs."""
    if not selected_ids:
        return _df
    selected_mask = np.isin(_df['id'], selected_ids)
    return _df[selected_mask]


def get_unselected_df(selected_ids):
    """Get DataFrame subset with unselected IDs."""
    if not selected_ids:
        return _df.iloc[0:0]
    selected_mask = np.isin(_df['id'], selected_ids)
    return _df[~selected_mask]


def get_selected_df_both(selected_ids):
    """Get both selected and unselected DataFrames."""
    if not selected_ids:
        return _df, _df.iloc[0:0]
    selected_mask = np.isin(_df['id'], selected_ids)
    return _df[selected_mask], _df[~selected_mask]


def _ordered_group_iter(df, group, aesthetics_group):
    """Return (g, group_df) pairs in plotting order (Order 1 = last drawn = on top).

    Groups not listed in aesthetics['order'] are placed first (bottom layer).
    """
    pairs = list(df.groupby(group, sort=False))
    order = aesthetics_group.get('order')
    if order:
        # Reverse the order list so that index 0 (Order 1) maps to the highest
        # sort key and is therefore appended last → drawn last → on top.
        reversed_order = list(reversed(order))
        order_map = {v: i for i, v in enumerate(reversed_order)}
        # Unlisted groups get -1 → sort before everything → drawn first (bottom)
        pairs.sort(key=lambda pair: order_map.get(str(pair[0]), -1))
    return pairs


def get_marker_dict(group, aesthetics_group, df_subset=None, legend=True, continuous=False, unselected=False, mapplot=False):
    """
    Build a Plotly marker dict for different cases (categorical, continuous, unselected).
    
    Args:
        group: Group name
        aesthetics_group: Dictionary with aesthetic settings
        df_subset: Specific DataFrame subset (for continuous colors with filtered data)
        legend: Whether to show legend
        continuous: Whether the variable is continuous
        unselected: Whether these are unselected points
        mapplot: Whether this is for a map plot
    
    Returns:
        Dictionary with marker settings
    """
    point_color = aesthetics_group['color']
    point_size = aesthetics_group['size']
    point_opacity = aesthetics_group['opacity']
    point_symbol = aesthetics_group['symbol'] if not mapplot else aesthetics_group['symbol_map']

    if group == 'none':
        group = 'default'
    else:
        # Convert to string for consistent dictionary lookup
        group = str(group)

    # Unselected case
    if unselected:
        unsel_color   = point_color.get('unselected', point_color.get('default', '#cccccc'))
        unsel_opacity = point_opacity.get('unselected', point_opacity.get('default', 0.3))
        unsel_size    = point_size.get('unselected', point_size.get('default', 6))
        if mapplot:
            # Scattermap ignores unselected.marker.opacity — bake opacity into
            # the colour as an RGBA string so it is always respected.
            marker = dict(size=unsel_size, color=_to_rgba(unsel_color, unsel_opacity))
        else:
            marker = dict(size=unsel_size, color=unsel_color, opacity=unsel_opacity)
    # Continuous color scale
    elif continuous:
        # Use provided subset or global df
        df = df_subset if df_subset is not None else _df
        marker = dict(
            size=point_size.get(group, point_size['default']),
            opacity=point_opacity.get(group, point_opacity['default']),
            symbol=point_symbol.get(group, point_symbol['default']),
            color=df[group],  # numeric values needed for continuous coloring
            colorscale=point_color['colorscale'],
            colorbar=dict(title=group) if legend else None,
            showscale=legend
        )
    # Categorical color
    else:
        marker = dict(
            size=point_size.get(group, point_size['default']),
            opacity=point_opacity.get(group, point_opacity['default']),
            symbol=point_symbol.get(group, point_symbol['default']),
            color=point_color.get(group, point_color.get('default'))
        )

    return marker


@lru_cache(maxsize=32)
def generate_fig_scatter2d(x_col, y_col, group, aesthetics_tuple, legend=True, xlab=True, ylab=True):
    """
    Generate 2D scatter plot (cached for performance).
    
    Args:
        x_col: X-axis column name
        y_col: Y-axis column name
        group: Grouping column name
        aesthetics_tuple: Tuple representation of aesthetics (for caching)
        legend: Whether to show legend
        xlab: Whether to show x-axis label
        ylab: Whether to show y-axis label
    
    Returns:
        Plotly Figure object
    
    Note:
        For datasets > 3000 points, scattergl (WebGL) is used for better performance.
        Uses global _df DataFrame.
    """
    aesthetics_group = tuple_to_dict_of_dicts(aesthetics_tuple)
    traces = []
    
    # Use WebGL for large datasets for better performance
    use_gl = len(_df) > 3000
    scatter_trace = go.Scattergl if use_gl else go.Scatter

    if group == 'none':
        traces.append(scatter_trace(
            x=_df[x_col],
            y=_df[y_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group),
            unselected=dict(marker=get_marker_dict(group, aesthetics_group, unselected=True)),
            name=str(group),
            customdata=_df['id'],
            text=group,
            hovertemplate="<b>ID:</b> %{customdata}<br><extra></extra>",
            showlegend=legend
        ))
    elif _df[group].dtype.kind in 'fi':
        # Continuous variable
        traces.append(scatter_trace(
            x=_df[x_col],
            y=_df[y_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group, df_subset=_df, legend=legend, continuous=True),
            unselected=dict(marker=get_marker_dict(group, aesthetics_group, unselected=True)),
            name=group,
            customdata=_df['id'],
            text=_df[group],
            hovertemplate="<b>Group:</b> %{text}<br><b>ID:</b> %{customdata}<br><extra></extra>",
            showlegend=False
        ))
    else:
        # Categorical
        for g, group_df in _ordered_group_iter(_df, group, aesthetics_group):
            traces.append(scatter_trace(
                x=group_df[x_col],
                y=group_df[y_col],
                mode='markers',
                marker=get_marker_dict(g, aesthetics_group),
                unselected=dict(marker=get_marker_dict(g, aesthetics_group, unselected=True)),
                name=str(g),
                customdata=group_df['id'],
                text=group_df[group],
                hovertemplate="<b>Group:</b> %{text}<br><b>ID:</b> %{customdata}<br><extra></extra>",
                showlegend=legend
            ))

    traces.append(scatter_trace(
        x=[], y=[],
        mode='markers',
        marker=dict(
            size=16,
            color='rgba(0,0,0,0)',
            symbol='circle-open',
            line=dict(width=2.5, color='black')
        ),
        name='__hover_highlight__',
        showlegend=False,
        hovertemplate='<extra></extra>'
    ))

    fig = go.Figure(traces)
    fig.update_layout(
        xaxis_title=x_col if xlab else '',
        yaxis_title=y_col if ylab else '',
    )
    return fig


@lru_cache(maxsize=32)
def generate_fig_scatter3d(x_col, y_col, z_col, group, aesthetics_tuple, legend=True, 
                          xlab=True, ylab=True, zlab=True, selected_ids_tuple=None):
    """
    Generate 3D scatter plot (cached for performance).
    
    Args:
        x_col: X-axis column name
        y_col: Y-axis column name
        z_col: Z-axis column name
        group: Grouping column name
        aesthetics_tuple: Tuple representation of aesthetics (for caching)
        legend: Whether to show legend
        xlab: Whether to show x-axis label
        ylab: Whether to show y-axis label
        zlab: Whether to show z-axis label
        selected_ids_tuple: Tuple of selected IDs

    Note:
        Scatter3d does not have selected/unselected styling, so we handle this by creating separate traces for selected and unselected points.
        Uses global _df DataFrame.
    
    Returns:
        Plotly Figure object
    """
    aesthetics_group = tuple_to_dict_of_dicts(aesthetics_tuple)
    selected_ids = list(selected_ids_tuple) if selected_ids_tuple else []
    
    traces = []
    
    # Split into selected and unselected
    df_selected, df_unselected = get_selected_df_both(selected_ids)

    if not df_unselected.empty:
        traces.append(go.Scatter3d(
            x=df_unselected[x_col],
            y=df_unselected[y_col],
            z=df_unselected[z_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group, unselected=True),
            name='Unselected',
            customdata=df_unselected['id'],
            showlegend=False,
            hoverinfo='skip'
        ))

    if group == 'none':
        traces.append(go.Scatter3d(
            x=df_selected[x_col],
            y=df_selected[y_col],
            z=df_selected[z_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group),
            name=str(group),
            customdata=df_selected['id'],
            text=group,
            showlegend=legend
        ))
    elif _df[group].dtype.kind in 'fi':
        traces.append(go.Scatter3d(
            x=df_selected[x_col],
            y=df_selected[y_col],
            z=df_selected[z_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group, df_subset=df_selected, legend=legend, continuous=True),
            name=group,
            customdata=df_selected['id'],
            text=df_selected[group],
            showlegend=False
        ))
    else:
        for g, group_df in _ordered_group_iter(df_selected, group, aesthetics_group):
            if group_df.empty:
                continue
            traces.append(go.Scatter3d(
                x=group_df[x_col],
                y=group_df[y_col],
                z=group_df[z_col],
                mode='markers',
                marker=get_marker_dict(g, aesthetics_group),
                name=str(g),
                customdata=group_df['id'],
                text=group_df[group],
                showlegend=legend
            ))

    traces.append(go.Scatter3d(
        x=[], y=[], z=[],
        mode='markers',
        marker=dict(size=10, color='rgba(0,0,0,0)', line=dict(width=3, color='black')),
        name='__hover_highlight__',
        showlegend=False,
        hovertemplate='<extra></extra>'
    ))

    fig = go.Figure(traces)
    fig.update_layout(
        scene=dict(
            xaxis_title=x_col if xlab else '',
            yaxis_title=y_col if ylab else '',
            zaxis_title=z_col if zlab else ''
        ),
        legend=dict(title=group)
    )
    return fig


@lru_cache(maxsize=32)
def generate_map_fig_scattermap(group, aesthetics_tuple, legend=True, lat_col=None, lon_col=None):
    """
    Generate map figure using Scattermap (cached for performance).
    
    Args:
        group: Grouping variable
        aesthetics_tuple: Tuple representation of aesthetics (for caching)
        legend: Whether to show legend
        lat_col: Latitude column name
        lon_col: Longitude column name
    
    Returns:
        Plotly Figure object
        
    Note:
        Uses global _df DataFrame.
    """
    aesthetics_group = tuple_to_dict_of_dicts(aesthetics_tuple)
    traces = []

    if lat_col is None or lon_col is None or lat_col not in _df.columns or lon_col not in _df.columns:
        # Return empty figure if coordinates not available
        return go.Figure().add_annotation(
            text="Geographic coordinates not available",
            showarrow=False,
            font={'size': 20}
        )
    
    # Remove rows with missing coordinates
    df_map = _df.dropna(subset=[lat_col, lon_col])
    
    if df_map.empty:
        return go.Figure().add_annotation(
            text="No valid geographic coordinates found",
            showarrow=False,
            font={'size': 20}
        )
    
    if group == 'none':
        traces.append(go.Scattermap(
            lat=df_map[lat_col],
            lon=df_map[lon_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group, df_subset=df_map, mapplot=True),
            unselected=dict(marker=get_marker_dict(group, aesthetics_group, unselected=True, mapplot=True)),
            name=group,
            customdata=df_map['id'],
            text=str(group),
            showlegend=legend,
        ))
    elif df_map[group].dtype.kind in 'fi':
        traces.append(go.Scattermap(
            lat=df_map[lat_col],
            lon=df_map[lon_col],
            mode='markers',
            marker=get_marker_dict(group, aesthetics_group, df_subset=df_map, legend=legend, continuous=True, mapplot=True),
            unselected=dict(marker=get_marker_dict(group, aesthetics_group, unselected=True, mapplot=True)),
            name=group,
            customdata=df_map['id'],
            text=df_map[group],
            showlegend=legend,
        ))
    else:
        for g, group_df in _ordered_group_iter(df_map, group, aesthetics_group):
            if group_df.empty:
                continue
            traces.append(go.Scattermap(
                lat=group_df[lat_col],
                lon=group_df[lon_col],
                mode='markers',
                marker=get_marker_dict(g, aesthetics_group, df_subset=df_map, mapplot=True),
                unselected=dict(marker=get_marker_dict(g, aesthetics_group, unselected=True, mapplot=True)),
                name=str(g),
                customdata=group_df['id'],
                text=group_df[group],
                showlegend=legend,
            ))

    traces.append(go.Scattermap(
        lat=[], lon=[],
        mode='markers',
        marker=dict(size=20, color='black', opacity=0.4),
        name='__hover_highlight__',
        showlegend=False,
        hovertemplate='<extra></extra>'
    ))

    fig = go.Figure(traces)

    # Auto-zoom/center to data bounds
    import math as _math
    lats = df_map[lat_col].dropna()
    lons = df_map[lon_col].dropna()
    if not lats.empty:
        center_lat = float(lats.mean())
        center_lon = float(lons.mean())
        lat_range = max(float(lats.max() - lats.min()), 0.01)
        lon_range = max(float(lons.max() - lons.min()), 0.01)
        max_range = max(lat_range, lon_range)
        zoom = max(1, min(13, _math.floor(_math.log2(360 / max_range)) - 1))
        fig.update_layout(map=dict(center=dict(lat=center_lat, lon=center_lon), zoom=zoom))

    return fig

# Alias for backward compatibility
create_geographical_map = generate_map_fig_scattermap


def generate_map_fig_scattergeo(group='none', aesthetics_group=None, legend=True, lat_col=None, lon_col=None):
    """
    Create a geographical map scatter plot.
    
    Args:
        group: Grouping variable
        aesthetics_group: Dictionary with aesthetic settings
        legend: Whether to show legend
        lat_col: Latitude column name
        lon_col: Longitude column name
    
    Returns:
        Plotly Figure object
        
    Note:
        Uses global _df DataFrame.
    """
    if lat_col is None or lon_col is None or lat_col not in _df.columns or lon_col not in _df.columns:
        # Return empty figure if coordinates not available
        return go.Figure().add_annotation(
            text="Geographic coordinates not available",
            showarrow=False,
            font={'size': 20}
        )
    
    # Remove rows with missing coordinates
    df_map = _df.dropna(subset=[lat_col, lon_col])
    
    if df_map.empty:
        return go.Figure().add_annotation(
            text="No valid geographic coordinates found",
            showarrow=False,
            font={'size': 20}
        )
    
    traces = []
    
    if group == 'none':
        # Single group
        trace = go.Scattergeo(
            lat=df_map[lat_col],
            lon=df_map[lon_col],
            mode='markers',
            marker=dict(
                size=aesthetics_group['size'].get('default', 8),
                color=aesthetics_group['color'].get('default', 'steelblue'),
                opacity=aesthetics_group['opacity'].get('default', 0.7)
            ),
            text=df_map['id'],
            customdata=df_map['id'],
            hovertemplate='<b>ID:</b> %{customdata}<br><b>Lat:</b> %{lat:.2f}<br><b>Lon:</b> %{lon:.2f}<extra></extra>',
            name='Samples',
            showlegend=legend
        )
        traces.append(trace)
    elif df_map[group].dtype.kind in 'fi':
        # Continuous variable - use color scale
        trace = go.Scattergeo(
            lat=df_map[lat_col],
            lon=df_map[lon_col],
            mode='markers',
            marker=dict(
                size=aesthetics_group['size'].get('default', 8),
                color=df_map[group],
                colorscale=aesthetics_group['color'].get('colorscale', 'Viridis'),
                opacity=aesthetics_group['opacity'].get('default', 0.7),
                symbol=aesthetics_group.get('symbol_map', {}).get('default', 'circle'),
                colorbar=dict(title=group),
                showscale=True
            ),
            text=df_map[group],
            customdata=df_map['id'],
            hovertemplate='<b>ID:</b> %{customdata}<br><b>' + group + ':</b> %{text:.2f}<br><b>Lat:</b> %{lat:.2f}<br><b>Lon:</b> %{lon:.2f}<extra></extra>',
            name=group,
            showlegend=legend
        )
        traces.append(trace)
    else:
        # Categorical variable - use colors for each group
        for group_val in df_map[group].unique():
            if pd.isna(group_val):
                continue
            
            df_group = df_map[df_map[group] == group_val]
            
            color = aesthetics_group['color'].get(str(group_val), 'steelblue')
            size = aesthetics_group['size'].get(str(group_val), 8)
            opacity = aesthetics_group['opacity'].get(str(group_val), 0.7)
            symbol = aesthetics_group['symbol'].get(str(group_val), aesthetics_group['symbol'].get('default', 'circle'))
            
            trace = go.Scattergeo(
                lat=df_group[lat_col],
                lon=df_group[lon_col],
                mode='markers',
                marker=dict(
                    size=size,
                    color=color,
                    opacity=opacity,
                    symbol=symbol
                ),
                text=[str(group_val)] * len(df_group),
                customdata=df_group['id'],
                hovertemplate='<b>ID:</b> %{customdata}<br><b>' + group + ':</b> %{text}<br><b>Lat:</b> %{lat:.2f}<br><b>Lon:</b> %{lon:.2f}<extra></extra>',
                name=str(group_val),
                showlegend=legend
            )
            traces.append(trace)
    
    fig = go.Figure(traces)
    
    fig.update_layout(
        geo=dict(
            projection_type='natural earth',
            showland=True,
            landcolor='rgb(243, 243, 243)',
            coastlinecolor='rgb(204, 204, 204)',
            showocean=True,
            oceancolor='rgb(204, 229, 255)',
            showcountries=True,
            countrywidth=0.5
        ),
        #title=f'Geographic Distribution (grouped by {group})',
        height=700,
        hovermode='closest',
        template='plotly_white'
    )
    
    return fig


def generate_time_histogram(df, df_selected, var_continuous, nbins=100):
    """
    Generate time histogram with selection overlay.
    
    Args:
        df: Full DataFrame
        df_selected: Selected DataFrame
        var_continuous: Continuous variable column name
        nbins: Number of bins
    
    Returns:
        Plotly Figure object
    """
    trace_all = go.Histogram(
        x=df[var_continuous],
        nbinsx=nbins,
        marker_color='lightgray',
        opacity=0.6,
        name='All'
    )
    traces = [trace_all]

    if not df_selected.empty:
        trace_selected = go.Histogram(
            x=df_selected[var_continuous],
            nbinsx=nbins,
            marker_color='#1F77B4',
            opacity=0.9,
            name='Selected'
        )
        traces.append(trace_selected)

    fig = go.Figure(traces)
    fig.update_layout(
        barmode='overlay',
        yaxis_title='Count',
        xaxis_title=var_continuous,
        showlegend=True
    )
    return fig


def generate_time_histogram_simple(df, var_continuous, nbins=100):
    """
    Generate simple time histogram.
    
    Args:
        df: DataFrame
        var_continuous: Continuous variable column name
        nbins: Number of bins
    
    Returns:
        Plotly Figure object
    """
    fig = px.histogram(df, x=var_continuous, nbins=nbins, title="", 
                      color_discrete_sequence=['#1F77B4'])
    fig.update_layout(yaxis_title='Count')
    return fig


def update_figure_selection_fast(selected_ids, fig, trace_map):
    """
    Update figure selection without recreating the entire figure.
    
    Args:
        selected_ids: List of selected IDs
        fig: Plotly Figure object
        trace_map: Dictionary mapping trace names to indices
    
    Returns:
        Updated Figure object
    """
    if not selected_ids:
        for trace_idx in trace_map.values():
            fig.data[trace_idx].selectedpoints = None
        return fig

    selected_set = set(selected_ids)

    for name, trace_idx in trace_map.items():
        trace = fig.data[trace_idx]
        ids = getattr(trace, "customdata", None)
        if ids is None:
            continue

        trace.selectedpoints = [
            j for j, idv in enumerate(ids) if idv in selected_set
        ]

    return fig


def get_selected_ids(selection):
    """Extract selected IDs from selection dict."""
    return [p['customdata'] for p in selection['points'] if 'customdata' in p]


