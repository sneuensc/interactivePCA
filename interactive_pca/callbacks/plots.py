"""
Plot-related callbacks for PCA visualizations.

Handles callbacks for:
- PCA plot structure updates (axes, grouping, 3D toggle)
- Map plot updates
- Time histogram updates  
- Legend visibility toggling
- Z-axis visibility toggling
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State

from ..plots import generate_fig_scatter2d, generate_fig_scatter3d, create_geographical_map
from ..utils import dict_of_dicts_to_tuple
from ..components import get_aesthetics_for_group, update_figure_hover_templates


def register_plot_callbacks(app, args, df, ANNOTATION_LAT, ANNOTATION_LONG, ANNOTATION_TIME, annotation_desc):
    """
    Register all plot-related callbacks.
    
    Args:
        app: Dash app instance
        args: Command-line arguments
        df: Main DataFrame with PCA and annotation data
        ANNOTATION_LAT: Latitude column name (or None)
        ANNOTATION_LONG: Longitude column name (or None)
        ANNOTATION_TIME: Time column name (or None)
        annotation_desc: Annotation description DataFrame
    """
    
    # Callback to show/hide Z-axis dropdown based on 3D toggle
    @app.callback(
        Output('z-axis-container', 'style'),
        Input('pca-3d-toggle', 'value')
    )
    def toggle_z_axis_visibility(is_3d):
        """Show Z-axis dropdown when 3D is enabled."""
        display_style = {'display': 'flex', 'alignItems': 'center', 'marginRight': '12px'}
        hidden_style = {'display': 'none', 'alignItems': 'center', 'marginRight': '12px'}
        return display_style if 'enable_3d' in is_3d else hidden_style
    
    # Callback for PCA plot regeneration (only when axes, grouping, or 3D toggle changes)
    @app.callback(
        Output('pca-plot', 'figure'),
        Output('trace-map', 'data'),
        Input('dropdown-pc-x', 'value'),
        Input('dropdown-pc-y', 'value'),
        Input('dropdown-pc-z', 'value'),
        Input('dropdown-group', 'value'),
        Input('pca-3d-toggle', 'value'),
        State('marker-aesthetics-store', 'data'),
        State('pca-legend-toggle', 'value'),
        State('hover-detailed', 'data'),
        State('selected-annotation-columns', 'data'),
        State('selection-store', 'data'),
        prevent_initial_call=False
    )
    def update_pca_plot_structure(pc_x, pc_y, pc_z, group, is_3d, aesthetics_store, legend_toggle, hover_detailed, selected_cols, selected_ids):
        """Regenerate PCA figure only when structure changes (axes, grouping, 3D mode)."""
        import json
        
        # Get current aesthetics
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
        
        # Determine if legend should be shown
        is_categorical = (
            group != 'none'
            and group in df.columns
            and df[group].dtype.kind not in 'fi'
        )
        is_continuous = (
            group != 'none'
            and group in df.columns
            and df[group].dtype.kind in 'fi'
        )
        
        show_legend = False
        if is_categorical:
            n_unique = df[group].nunique()
            show_legend = n_unique > 1
            if legend_toggle is not None:
                show_legend = show_legend and ('show_legend' in legend_toggle)
        elif is_continuous:
            show_legend = True
        
        # Create 3D or 2D plot based on toggle
        if 'enable_3d' in is_3d:
            # Convert selected_ids to tuple for caching
            selected_tuple = tuple(selected_ids) if selected_ids else None
            fig = generate_fig_scatter3d(
                x_col=pc_x,
                y_col=pc_y,
                z_col=pc_z,
                group=group,
                aesthetics_tuple=aesthetics_tuple,
                legend=show_legend,
                selected_ids_tuple=selected_tuple
            )
            fig.update_layout(
                template='plotly_white',
                clickmode='event+select',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title="",
                margin={'l': 20, 'r': 20, 't': 40, 'b': 20},
                legend_title=group,
                height=700
            )
        else:
            fig = generate_fig_scatter2d(
                x_col=pc_x,
                y_col=pc_y,
                group=group,
                aesthetics_tuple=aesthetics_tuple,
                legend=show_legend
            )
            fig.update_layout(
                template='plotly_white',
                clickmode='event+select',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title="",
                margin={'l': 20, 'r': 20, 't': 40, 'b': 20},
                dragmode='lasso',
                legend_title=group
            )
        
        # Update layout
        if 'enable_3d' not in is_3d:
            fig.update_layout(
                autosize=True,
                margin=dict(l=50, r=140 if (is_categorical and show_legend) else 20, t=40, b=40),
                legend=dict(
                    visible=show_legend,
                    x=1.02 if is_categorical else 0.02,
                    y=1 if is_categorical else 0.98,
                    xanchor='left',
                    yanchor='top'
                ),
                dragmode='lasso',
                hovermode='closest',
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )
        else:
            fig.update_layout(
                autosize=True,
                legend=dict(
                    visible=show_legend,
                    x=1.02 if is_categorical else 0.02,
                    y=1 if is_categorical else 0.98,
                    xanchor='left',
                    yanchor='top'
                ),
                hovermode='closest',
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )
        
        # Store trace map for fast updates: trace_name -> index
        trace_map = {trace.name: i for i, trace in enumerate(fig.data)}
        
        # Apply hover formatting with current settings
        fig_dict = fig.to_dict()
        group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
        fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'pca')
        
        # Preserve selection when regenerating figure
        if selected_ids:
            # Convert all IDs to strings for consistent comparison
            selected_set = set(str(sid) for sid in selected_ids)
            for trace in fig_dict.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0 and selected_set:
                    # Convert customdata to strings and use NumPy for faster lookup
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
        
        return fig_dict, trace_map
    
    @app.callback(
        Output('pca-plot', 'figure', allow_duplicate=True),
        Input('pca-legend-toggle', 'value'),
        State('pca-plot', 'figure'),
        prevent_initial_call=True
    )
    def update_pca_legend_visibility(show_legend, current_fig):
        """Fast update of legend visibility without regenerating figure."""
        if current_fig is None:
            return current_fig
        
        show_legend_flag = 'show_legend' in show_legend
        
        # Get margin from current layout or default
        try:
            legend_title = current_fig.get('layout', {}).get('legend', {}).get('title')
            if isinstance(legend_title, dict):
                legend_title = legend_title.get('text')
            is_categorical = legend_title not in (None, 'none', '')
        except Exception:
            is_categorical = False
        
        # Adjust right margin based on legend visibility
        r_margin = 140 if is_categorical and show_legend_flag else 20
        
        if 'layout' not in current_fig:
            current_fig['layout'] = {}
        if 'legend' not in current_fig['layout']:
            current_fig['layout']['legend'] = {}
        if 'margin' not in current_fig['layout']:
            current_fig['layout']['margin'] = {}
        current_fig['layout']['legend']['visible'] = show_legend_flag
        current_fig['layout']['margin']['r'] = r_margin

        if is_categorical:
            for trace in current_fig.get('data', []):
                trace['showlegend'] = show_legend_flag
        
        return current_fig
    
    @app.callback(
        Output('pca-map-plot', 'figure'),
        Input('dropdown-group', 'value'),
        Input('marker-aesthetics-store', 'data'),
        State('hover-detailed', 'data'),
        State('selected-annotation-columns', 'data')
    )
    def update_map_plot(group, aesthetics_store, hover_detailed, selected_cols):
        if ANNOTATION_LAT is None or ANNOTATION_LONG is None:
            return {}
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
        fig = create_geographical_map(
            group=group,
            aesthetics_tuple=aesthetics_tuple,
            legend=False,
            lat_col=ANNOTATION_LAT,
            lon_col=ANNOTATION_LONG
        )
        is_categorical = (
            group != 'none'
            and group in df.columns
            and df[group].dtype.kind not in 'fi'
        )
        fig.update_layout(
            autosize=True,
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(
                x=1.02 if is_categorical else 0.02,
                y=1 if is_categorical else 0.98,
                xanchor='left',
                yanchor='top'
            ),
            dragmode='lasso',
            hoverlabel=dict(
                bgcolor='white',
                font_color='#333',
                namelength=-1
            )
        )
        
        # Apply hover formatting with current settings
        fig_dict = fig.to_dict()
        group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
        fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'map')
        
        return fig_dict
    
    # Callback for time histogram updates (grouping, mode, and selection)
    @app.callback(
        Output('time-histogram', 'figure'),
        Input('dropdown-group', 'value'),
        Input('time-viz-mode', 'value'),
        Input('time-variable', 'value'),
        Input('pca-plot', 'selectedData'),
        Input('marker-aesthetics-store', 'data'),
        State('hover-detailed', 'data'),
        State('selected-annotation-columns', 'data'),
        prevent_initial_call=False
    )
    def update_time_histogram(group, viz_mode, time_variable, selected_data, aesthetics_store, hover_detailed, selected_cols):
        if time_variable is None or time_variable not in df.columns:
            return {}
        
        time_vals = df[time_variable].dropna()
        if time_vals.empty:
            return {}
        
        # Get IDs corresponding to the time values
        time_ids = df.loc[time_vals.index, 'id'].tolist()
        
        # Get selected IDs if any
        selected_ids = []
        if selected_data and 'points' in selected_data:
            selected_ids = [point.get('customdata', [point.get('pointIndex')])[0] 
                          if point.get('customdata') else point.get('pointIndex') 
                          for point in selected_data['points']]
        
        fig = go.Figure()
        
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        default_color = aesthetics['color'].get('default', 'steelblue')
        
        if viz_mode == 'distribution':
            # Simple histogram
            fig.add_trace(go.Histogram(
                x=time_vals, 
                nbinsx=50, 
                marker=dict(color=default_color),
                name='All samples',
                showlegend=False
            ))
            fig.update_layout(
                xaxis_title=time_variable,
                yaxis_title="Count",
                autosize=True
            )
            
        elif viz_mode == 'scatter':
            # Scatter plot with jitter
            np.random.seed(42)
            jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
            default_size = aesthetics['size'].get('default', 8)
            default_opacity = aesthetics['opacity'].get('default', 0.7)
            
            if group != 'none' and group in df.columns:
                group_vals = df.loc[time_vals.index, group]
                if df[group].dtype.kind in 'fi':
                    # Continuous variable - use colorscale
                    colorscale = aesthetics['color'].get('colorscale', 'Viridis')
                    fig.add_trace(go.Scatter(
                        x=time_vals,
                        y=jitter,
                        mode='markers',
                        marker=dict(
                            color=group_vals,
                            colorscale=colorscale,
                            size=default_size,
                            opacity=default_opacity,
                            symbol=aesthetics['symbol'].get('default', 'circle'),
                            showscale=False
                        ),
                        customdata=time_ids,
                        hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                        name='All samples',
                        showlegend=False
                    ))
                else:
                    # Categorical variable - use group colors
                    color_map = aesthetics.get('color', {})
                    size_map = aesthetics.get('size', {})
                    opacity_map = aesthetics.get('opacity', {})
                    symbol_map = aesthetics.get('symbol', {})
                    unique_vals = [val for val in group_vals.unique() if not pd.isna(val)]
                    for val in unique_vals:
                        mask = group_vals == val
                        subset_ids = [time_ids[i] for i in range(len(time_ids)) if mask.iloc[i]]
                        fig.add_trace(go.Scatter(
                            x=time_vals[mask],
                            y=jitter[mask.to_numpy()],
                            mode='markers',
                            marker=dict(
                                color=color_map.get(str(val), default_color),
                                size=size_map.get(str(val), default_size),
                                opacity=opacity_map.get(str(val), default_opacity),
                                symbol=symbol_map.get(str(val), aesthetics['symbol'].get('default', 'circle'))
                            ),
                            customdata=subset_ids,
                            hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                            name=str(val),
                            showlegend=False
                        ))
            else:
                fig.add_trace(go.Scatter(
                    x=time_vals,
                    y=jitter,
                    mode='markers',
                    marker=dict(color=default_color, size=default_size, opacity=default_opacity),
                    customdata=time_ids,
                    hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                    name='All samples',
                    showlegend=False
                ))
            fig.update_layout(
                xaxis_title=time_variable,
                yaxis_title="",
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                autosize=True,
                dragmode='lasso',
                margin=dict(
                    l=50,
                    r=20,
                    t=40,
                    b=40
                )
            )
            
        elif viz_mode == 'overlay':
            # Overlapping histograms: all vs selected (from notebook approach)
            # All samples (gray)
            fig.add_trace(go.Histogram(
                x=time_vals,
                nbinsx=50,
                marker_color='lightgray',
                opacity=0.6,
                name='All',
                showlegend=False
            ))
            
            # Selected samples (color)
            if selected_ids and len(selected_ids) > 0:
                if 'id' in df.columns:
                    selected_time = df[df['id'].isin(selected_ids)][time_variable].dropna()
                else:
                    selected_indices = [i for i in selected_ids if i < len(df)]
                    selected_time = df.iloc[selected_indices][time_variable].dropna()
                
                if not selected_time.empty:
                    fig.add_trace(go.Histogram(
                        x=selected_time,
                        nbinsx=50,
                        marker_color='#1F77B4',
                        opacity=0.9,
                        name='Selected',
                        showlegend=False
                    ))
            
            fig.update_layout(
                barmode='overlay',
                yaxis_title='Count',
                xaxis_title=time_variable,
                autosize=True
            )
        
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=50, r=20, t=40, b=40),
            dragmode='lasso',
            hoverlabel=dict(
                bgcolor='white',
                font_color='#333',
                namelength=-1
            )
        )
        if time_variable == ANNOTATION_TIME:
            fig.update_xaxes(autorange='reversed')
        
        # Apply hover text formatting (same as hover callbacks do)
        # Convert Figure to dict before updating hover templates
        fig_dict = fig.to_dict()
        group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
        fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'time')
        
        return fig_dict
