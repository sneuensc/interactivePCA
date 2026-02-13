"""
Main Dash application factory for interactivePCA.
"""

import logging
import os
import json
import copy
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, ALL
import plotly.express as px

from .data_loader import (
    load_eigenvec, load_annotation, load_eigenval,
    load_imiss, load_lmiss, load_frq, merge_data
)
from .utils import strip_ansi
from .plots import create_initial_pca_plot, create_geographical_map


def create_app(args):
    """
    Create and configure the Dash application.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        Configured Dash app instance
    """
    logging.info("Creating Dash application...")
    
    # Load data
    logging.info("Loading data files...")
    
    # Load eigenvectors (required)
    eigenvec, pcs, eigenvec_id = load_eigenvec(args.eigenvec, args.eigenvecID)
    
    # Load optional files
    eigenval = load_eigenval(args.eigenval) if args.eigenval else None
    df_imiss = load_imiss(args.imiss) if args.imiss else None
    df_lmiss = load_lmiss(args.lmiss) if args.lmiss else None
    df_frq = load_frq(args.frq) if args.frq else None
    
    # Load annotation
    annotation = None
    annotation_desc = None
    annotation_cols = {}
    
    if args.annotation:
        annotation, annotation_desc, annotation_cols = load_annotation(args.annotation, args)
    
    # Merge data
    df = merge_data(
        eigenvec,
        annotation,
        eigenvec_id_col='id',
        annotation_id_col=annotation_cols.get('id'),
        time_col=annotation_cols.get('time'),
        invert_time=args.time_invert
    )
    
    # Get annotation columns
    ANNOTATION_TIME = annotation_cols.get('time')
    ANNOTATION_LAT = annotation_cols.get('latitude')
    ANNOTATION_LONG = annotation_cols.get('longitude')
    
    # Initialize selected IDs
    if args.selectedID:
        if os.path.isfile(args.selectedID):
            with open(args.selectedID, 'r') as f:
                init_selected_ids = [line.rstrip('\n') for line in f]
        else:
            init_selected_ids = args.selectedID.split(";")
        
        # Filter to valid IDs
        valid_ids = set(df['id'].tolist())
        init_selected_ids = [sid for sid in init_selected_ids if sid in valid_ids]
    else:
        init_selected_ids = df['id'].tolist()
    
    logging.info(f"Selected {len(init_selected_ids)} of {len(df)} samples")
    
    # Initialize grouping options
    dropdown_group_list = ['none']
    if annotation_desc is not None:
        # Add columns suitable for grouping
        grouping_cols = annotation_desc.loc[
            annotation_desc['Dropdown'] == 'Yes',
            'Abbreviation'
        ].tolist()
        dropdown_group_list.extend(grouping_cols)

    # Include PCs as grouping options
    for pc in pcs:
        if pc not in dropdown_group_list:
            dropdown_group_list.append(pc)
    
    init_group = args.group if args.group and args.group in dropdown_group_list else dropdown_group_list[0]
    
    # Initialize continuous variable options
    dropdown_list_continuous = []
    init_continuous = ANNOTATION_TIME
    if annotation_desc is not None:
        dropdown_list_continuous = annotation_desc.loc[
            annotation_desc['Type'] == 'continuous',
            'Abbreviation'
        ].tolist()
        if dropdown_list_continuous and ANNOTATION_TIME not in dropdown_list_continuous:
            init_continuous = dropdown_list_continuous[0] if dropdown_list_continuous else None
    
    # Initialize aesthetics from parameters
    init_aesthetics = get_init_aesthetics(args, init_group, df)
    
    # Load aesthetics from file if provided (overrides parameter defaults)
    if args.aesthetics_file:
        file_aesthetics = load_aesthetics_file(args.aesthetics_file)
        if file_aesthetics and init_group in file_aesthetics:
            # Merge file aesthetics with parameter-based defaults
            init_aesthetics = merge_aesthetics(init_aesthetics, file_aesthetics[init_group])
    
    # Create Dash app
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True
    )
    
    # Build layout
    layout_data = create_layout(
        args, df, pcs, eigenval, df_imiss, df_lmiss, df_frq,
        annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
        init_selected_ids, init_group, init_continuous, init_aesthetics,
        dropdown_group_list, dropdown_list_continuous
    )
    app.layout = layout_data['layout']
    tab_content_map = layout_data['tab_content_map']
    
    # Register tab switching callback using clientside callback for better performance
    # This toggles visibility instead of replacing content
    app.clientside_callback(
        """
        function(active_tab) {
            // Hide all tab content divs
            const tabs = ['pca_tab', 'annotation_tab', 'help_tab'];
            tabs.forEach(function(tab) {
                const el = document.getElementById(tab + '_content');
                if (el) {
                    el.style.display = (tab === active_tab) ? 'block' : 'none';
                }
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    
    # Callback to update PCA annotation table based on selected rows in annotation table
    @app.callback(
        Output('pca-annotation-table', 'rowData'),
        Output('pca-annotation-table', 'columnDefs'),
        Input('annotation-table', 'selectedRows'),
        prevent_initial_call=False
    )
    def update_pca_annotation_table(selected_rows):
        logging.info(f"PCA annotation table callback triggered with {len(selected_rows) if selected_rows else 0} selected rows")
        if not selected_rows:
            logging.warning("No rows selected in annotation table")
            return [], []
        # Extract 'Abbreviation' field from selected rows
        selected_columns = [row.get('Abbreviation') for row in selected_rows if row.get('Abbreviation')]
        logging.info(f"Selected columns: {selected_columns}")
        cols = [c for c in selected_columns if c in df.columns]
        if not cols:
            logging.warning(f"None of the selected columns found in df. Available columns: {df.columns.tolist()[:10]}")
            return [], []
        logging.info(f"Updating PCA annotation table with {len(cols)} columns: {cols}")
        row_data = df[cols].to_dict('records')
        column_defs = [
            {
                'headerName': '',
                'checkboxSelection': True,
                'headerCheckboxSelection': True,
                'headerCheckboxSelectionFilteredOnly': True,
                'width': 40,
                'pinned': 'left'
            }
        ] + [
            {'field': col, 'headerName': col, 'sortable': True, 'filter': True}
            for col in cols
        ]
        return row_data, column_defs
    
    # Callback for PCA plot updates (PC axes and grouping)
    @app.callback(
        Output('pca-plot', 'figure'),
        Input('dropdown-pc-x', 'value'),
        Input('dropdown-pc-y', 'value'),
        Input('dropdown-group', 'value'),
        Input('marker-aesthetics-store', 'data')
    )
    def update_pca_plot(pc_x, pc_y, group, aesthetics_store):
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        fig = create_initial_pca_plot(
            df=df,
            x_col=pc_x,
            y_col=pc_y,
            group=group,
            aesthetics_group=aesthetics
        )
        is_categorical = (
            group != 'none'
            and group in df.columns
            and df[group].dtype.kind not in 'fi'
        )
        fig.update_layout(
            autosize=True,
            margin=dict(l=50, r=140 if is_categorical else 20, t=40, b=40),
            legend=dict(
                x=1.02 if is_categorical else 0.02,
                y=1 if is_categorical else 0.98,
                xanchor='left',
                yanchor='top'
            )
        )
        return fig
    
    # Callback for map plot updates (grouping only)
    @app.callback(
        Output('pca-map-plot', 'figure'),
        Input('dropdown-group', 'value'),
        Input('marker-aesthetics-store', 'data')
    )
    def update_map_plot(group, aesthetics_store):
        if ANNOTATION_LAT is None or ANNOTATION_LONG is None:
            return {}
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        fig = create_geographical_map(
            df=df,
            group=group,
            aesthetics_group=aesthetics,
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
            margin=dict(l=50, r=140 if is_categorical else 20, t=40, b=40),
            legend=dict(
                x=1.02 if is_categorical else 0.02,
                y=1 if is_categorical else 0.98,
                xanchor='left',
                yanchor='top'
            )
        )
        return fig
    
    # Callback for time histogram updates (grouping, mode, and selection)
    @app.callback(
        Output('time-histogram', 'figure'),
        Input('dropdown-group', 'value'),
        Input('time-viz-mode', 'value'),
        Input('time-variable', 'value'),
        Input('pca-plot', 'selectedData'),
        Input('marker-aesthetics-store', 'data')
    )
    def update_time_histogram(group, viz_mode, time_variable, selected_data, aesthetics_store):
        import plotly.graph_objects as go
        import numpy as np
        import pandas as pd
        
        if time_variable is None or time_variable not in df.columns:
            return {}
        
        time_vals = df[time_variable].dropna()
        if time_vals.empty:
            return {}
        
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
                name='All samples'
            ))
            fig.update_layout(
                xaxis_title=time_variable,
                yaxis_title="Count",
                showlegend=False,
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
                            showscale=True,
                            colorbar=dict(title=group)
                        ),
                        name='All samples'
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
                            name=str(val),
                            showlegend=True
                        ))
            else:
                fig.add_trace(go.Scatter(
                    x=time_vals,
                    y=jitter,
                    mode='markers',
                    marker=dict(color=default_color, size=default_size, opacity=default_opacity),
                    name='All samples'
                ))
            fig.update_layout(
                xaxis_title=time_variable,
                yaxis_title="",
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                showlegend=(
                    group != 'none'
                    and group in df.columns
                    and df[group].dtype.kind not in 'fi'
                ),
                autosize=True,
                legend=dict(
                    x=1.02,
                    y=1,
                    xanchor='left',
                    yanchor='top'
                ) if (
                    group != 'none'
                    and group in df.columns
                    and df[group].dtype.kind not in 'fi'
                ) else dict(x=0.02, y=0.98, xanchor='left', yanchor='top'),
                margin=dict(
                    l=50,
                    r=140 if (
                        group != 'none'
                        and group in df.columns
                        and df[group].dtype.kind not in 'fi'
                    ) else 20,
                    t=40,
                    b=40
                )
            )
            
        elif viz_mode == 'overlay':
            # Overlapping histograms: selected vs all
            unselected_color = aesthetics['color'].get('unselected', 'lightgray')
            selected_color = default_color
            
            if selected_ids and len(selected_ids) > 0:
                # All samples (unselected style)
                fig.add_trace(go.Histogram(
                    x=time_vals,
                    nbinsx=50,
                    marker=dict(color=unselected_color, line=dict(color='gray', width=1)),
                    name='All samples',
                    opacity=0.6
                ))
                
                # Selected samples (default style)
                if 'id' in df.columns:
                    selected_time = df[df['id'].isin(selected_ids)][time_variable].dropna()
                else:
                    selected_indices = [i for i in selected_ids if i < len(df)]
                    selected_time = df.iloc[selected_indices][time_variable].dropna()
                
                if not selected_time.empty:
                    fig.add_trace(go.Histogram(
                        x=selected_time,
                        nbinsx=50,
                        marker=dict(color=selected_color, line=dict(color=selected_color, width=1)),
                        name='Selected samples',
                        opacity=0.8
                    ))
                
                fig.update_layout(
                    xaxis_title=time_variable,
                    yaxis_title="Count",
                    barmode='overlay',
                    showlegend=True,
                    legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)'),
                    autosize=True
                )
            else:
                # No selection, show all
                fig.add_trace(go.Histogram(
                    x=time_vals,
                    nbinsx=50,
                    marker=dict(color=default_color),
                    name='All samples'
                ))
                fig.update_layout(
                    xaxis_title=time_variable,
                    yaxis_title="Count",
                    showlegend=False,
                    autosize=True
                )
        
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=50, r=20, t=40, b=40)
        )
        if time_variable == ANNOTATION_TIME:
            fig.update_xaxes(autorange='reversed')
        return fig
    
    # Register callbacks (would be imported from callbacks.py)
    # from .callbacks import register_callbacks
    # register_callbacks(app, df, pcs, ...)
    
    # Callback to open aesthetics modal
    @app.callback(
        Output('aesthetics-modal', 'is_open'),
        [Input('open-aesthetics', 'n_clicks'), Input('cancel-aesthetics', 'n_clicks'), Input('save-aesthetics', 'n_clicks')],
        [State('aesthetics-modal', 'is_open')],
        prevent_initial_call=True
    )
    def toggle_aesthetics_modal(n_open, n_cancel, n_save, is_open):
        """Toggle modal on open, cancel, or after save"""
        if n_open or n_cancel or n_save:
            return not is_open
        return is_open
    
    # Callback to populate aesthetics table when modal opens or group changes
    @app.callback(
        Output('aesthetics-table-container', 'children'),
        [Input('dropdown-group', 'value'), Input('marker-aesthetics-store', 'data')]
    )
    def update_aesthetics_table(group, aesthetics_store):
        import dash_ag_grid as dag
        import dash_bootstrap_components as dbc
        
        try:
            logging.debug(f"update_aesthetics_table called with group={group}")
            
            if not group or aesthetics_store is None:
                return html.Div("No data available", style={'color': '#999', 'padding': '12px'})
            
            aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
            
            # Determine if group is continuous
            is_continuous = group != 'none' and group in df.columns and df[group].dtype.kind in 'fi'
            
            # Always create colorscale dropdown (to avoid callback error), but hide for categorical
            colorscale = aesthetics['color'].get('colorscale', 'Viridis')
            colorscale_dropdown = dcc.Dropdown(
                id='colorscale-dropdown-modal',
                options=[{'label': cs, 'value': cs} for cs in ['Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 'Blues', 'Reds', 'Greens', 'YlOrRd', 'RdYlBu']],
                value=colorscale,
                clearable=False,
                style={'width': '200px', 'display': 'none' if not is_continuous else 'block'}
            )
            
            if is_continuous:
                # Continuous: show Group and Color in left column, Size/Opacity/Symbol in right grid
                default_size = aesthetics['size']['default']
                default_opacity = aesthetics['opacity']['default']
                default_symbol = aesthetics['symbol']['default']
                unselected_color = aesthetics['color'].get('unselected', '#cccccc')
                colorscale = aesthetics['color'].get('colorscale', 'Viridis')
                
                # Build table rows for default and unselected (only Size, Opacity, Symbol in AG Grid)
                rows = []
                rows.append({
                    'Size': default_size,
                    'Opacity': default_opacity,
                    'Symbol': default_symbol
                })
                rows.append({
                    'Size': aesthetics['size'].get('unselected', default_size),
                    'Opacity': aesthetics['opacity'].get('unselected', default_opacity),
                    'Symbol': aesthetics['symbol'].get('unselected', default_symbol)
                })
                
                # Column definitions (no Group, no Color)
                columnDefs = [
                    {
                        'field': 'Size',
                        'headerName': 'Size',
                        'editable': True,
                        'width': 90,
                        'singleClickEdit': True,
                        'cellEditor': 'agSelectCellEditor',
                        'cellEditorParams': {'values': [4, 6, 8, 10, 12, 14, 16, 18, 20]}
                    },
                    {
                        'field': 'Opacity',
                        'headerName': 'Opacity',
                        'editable': True,
                        'width': 100,
                        'singleClickEdit': True,
                        'cellEditor': 'agSelectCellEditor',
                        'cellEditorParams': {'values': [0.2, 0.4, 0.6, 0.8, 1.0]}
                    },
                    {
                        'field': 'Symbol',
                        'headerName': 'Symbol',
                        'editable': True,
                        'width': 150,
                        'singleClickEdit': True,
                        'cellEditor': 'agSelectCellEditor',
                        'cellEditorParams': {'values': ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star']}
                    }
                ]
                
                table = dag.AgGrid(
                    id='aesthetics-edit-table',
                    rowData=rows,
                    columnDefs=columnDefs,
                    defaultColDef={'flex': 1, 'minWidth': 80, 'resizable': True},
                    dashGridOptions={'rowSelection': 'single', 'headerHeight': 40, 'rowHeight': 40},
                    style={'height': '120px', 'width': '100%'}
                )
                
                # Create left column with Group and Color (in proper order)
                left_column_groups_colors = []
                
                # Header row with "Group" and "Color" labels
                left_column_groups_colors.append(
                    html.Div([
                        html.Div('Group', style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'fontWeight': 'bold',
                            'fontSize': '14px',
                            'borderRight': '1px solid #dee2e6',
                            'backgroundColor': '#f8f9fa'
                        }),
                        html.Div('Color', style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'fontWeight': 'bold',
                            'fontSize': '14px',
                            'backgroundColor': '#f8f9fa'
                        })
                    ], style={'display': 'flex', 'borderBottom': '2px solid #dee2e6'})
                )
                
                # Default row: "default" | colorscale dropdown
                left_column_groups_colors.append(
                    html.Div([
                        html.Div('default', style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'borderRight': '1px solid #dee2e6',
                            'fontSize': '12px',
                            'backgroundColor': 'white'
                        }),
                        html.Div([
                            dcc.Dropdown(
                                id={'type': 'colorscale-dropdown-modal', 'index': 'default'},
                                options=[
                                    {'label': 'Viridis', 'value': 'Viridis'},
                                    {'label': 'Plasma', 'value': 'Plasma'},
                                    {'label': 'Blues', 'value': 'Blues'},
                                    {'label': 'Reds', 'value': 'Reds'},
                                    {'label': 'Greens', 'value': 'Greens'},
                                    {'label': 'Purples', 'value': 'Purples'},
                                    {'label': 'RdYlBu', 'value': 'RdYlBu'},
                                    {'label': 'RdYlGn', 'value': 'RdYlGn'},
                                ],
                                value=colorscale,
                                clearable=False,
                                style={'width': '100%', 'fontSize': '12px'}
                            )
                        ], style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'padding': '0 8px',
                            'backgroundColor': 'white'
                        })
                    ], style={'display': 'flex', 'borderBottom': '1px solid #dee2e6'})
                )
                
                # Unselected row: "unselected" | color picker
                left_column_groups_colors.append(
                    html.Div([
                        html.Div('unselected', style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'borderRight': '1px solid #dee2e6',
                            'fontSize': '12px',
                            'backgroundColor': 'white'
                        }),
                        html.Div([
                            dbc.Input(
                                type="color",
                                id={'type': 'color-input-modal', 'index': 'unselected'},
                                value=unselected_color,
                                style={
                                    'width': '40px',
                                    'height': '32px',
                                    'padding': '0',
                                    'border': '1px solid #ced4da',
                                    'cursor': 'pointer',
                                    'borderRadius': '3px'
                                }
                            )
                        ], style={
                            'flex': 1,
                            'height': '40px',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'backgroundColor': 'white'
                        })
                    ], style={'display': 'flex'})
                )
                
                # Create integrated table layout: Group+Color | Size, Opacity, Symbol
                integrated_table = html.Div([
                    html.Div(
                        left_column_groups_colors,
                        style={
                            'width': '220px',
                            'flexShrink': 0,
                            'borderRight': '1px solid #dee2e6',
                            'backgroundColor': 'white'
                        }
                    ),
                    html.Div(
                        table,
                        style={'flex': 1, 'overflow': 'hidden'}
                    )
                ], style={
                    'display': 'flex',
                    'border': '1px solid #dee2e6',
                    'borderRadius': '4px',
                    'overflow': 'hidden',
                    'height': '120px'
                })
                
                return integrated_table

            
            # Categorical: build AG Grid table with editable colors
            default_size = aesthetics['size']['default']
            default_opacity = aesthetics['opacity']['default']
            default_symbol = aesthetics['symbol']['default']
            
            # Build table rows
            rows = []
            
            for key, color_val in aesthetics['color'].items():
                size_val = aesthetics['size'].get(key, default_size)
                opacity_val = aesthetics['opacity'].get(key, default_opacity)
                symbol_val = aesthetics['symbol'].get(key, default_symbol)
                
                # Show "-" if equals default (except for "default" row itself)
                size_display = "-" if (size_val == default_size and key != 'default') else str(size_val)
                opacity_display = "-" if (opacity_val == default_opacity and key != 'default') else str(opacity_val)
                symbol_display = "-" if (symbol_val == default_symbol and key != 'default') else symbol_val
                
                rows.append({
                    'Group': key,
                    'Size': size_display,
                    'Opacity': opacity_display,
                    'Symbol': symbol_display
                })
            
            # Column definitions
            columnDefs = [
                {
                    'field': 'Group',
                    'headerName': 'Group',
                    'editable': False,
                    'width': 130,
                    'pinned': 'left'
                },
                {
                    'field': 'Size',
                    'headerName': 'Size',
                    'editable': True,
                    'width': 90,
                    'singleClickEdit': True,
                    'cellEditor': 'agSelectCellEditor',
                    'cellEditorParams': {'values': ['-', '4', '6', '8', '10', '12', '14', '16', '18', '20']}
                },
                {
                    'field': 'Opacity',
                    'headerName': 'Opacity',
                    'editable': True,
                    'width': 100,
                    'singleClickEdit': True,
                    'cellEditor': 'agSelectCellEditor',
                    'cellEditorParams': {'values': ['-', '0.0', '0.2', '0.4', '0.6', '0.8', '1.0']}
                },
                {
                    'field': 'Symbol',
                    'headerName': 'Symbol',
                    'editable': True,
                    'type': 'text',
                    'width': 150,
                    'singleClickEdit': True,
                    'cellEditor': 'agSelectCellEditor',
                    'cellEditorParams': {'values': ['-', 'circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star']}
                }
            ]
            
            table = dag.AgGrid(
                id='aesthetics-edit-table',
                rowData=rows,
                columnDefs=columnDefs,
                defaultColDef={'flex': 1, 'minWidth': 80, 'resizable': True},
                dashGridOptions={'rowSelection': 'single', 'headerHeight': 40, 'rowHeight': 40},
                style={'height': '350px', 'width': '100%'}
            )
            
            # Create color pickers aligned with table rows (including header)
            color_picker_column = [
                # Header
                html.Div('Color', style={
                    'height': '40px',
                    'display': 'flex',
                    'alignItems': 'center',
                    'justifyContent': 'center',
                    'fontWeight': 'bold',
                    'fontSize': '14px',
                    'borderBottom': '2px solid #dee2e6',
                    'backgroundColor': '#f8f9fa'
                })
            ]
            
            # Color picker for each row
            for key, color_val in aesthetics['color'].items():
                color_picker_column.append(
                    html.Div([
                        dbc.Input(
                            type="color",
                            id={'type': 'color-input-modal', 'index': str(key)},
                            value=color_val,
                            style={
                                'width': '40px',
                                'height': '32px',
                                'padding': '0',
                                'border': '1px solid #ced4da',
                                'cursor': 'pointer',
                                'borderRadius': '3px'
                            }
                        )
                    ], style={
                        'height': '40px',
                        'display': 'flex',
                        'alignItems': 'center',
                        'justifyContent': 'center',
                        'borderBottom': '1px solid #dee2e6'
                    })
                )
            
            # Create integrated table layout
            integrated_table = html.Div([
                html.Div(
                    color_picker_column,
                    style={
                        'width': '80px',
                        'flexShrink': 0,
                        'borderRight': '1px solid #dee2e6',
                        'backgroundColor': 'white'
                    }
                ),
                html.Div(
                    table,
                    style={'flex': 1, 'overflow': 'hidden'}
                )
            ], style={
                'display': 'flex',
                'border': '1px solid #dee2e6',
                'borderRadius': '4px',
                'overflow': 'hidden',
                'height': '350px'
            })
            
            return integrated_table
            
        except Exception as e:
            logging.error(f"Error in update_aesthetics_table: {e}", exc_info=True)
            return html.Div(
                f"Error loading table: {str(e)}",
                style={'color': '#cc0000', 'padding': '12px', 'fontFamily': 'monospace', 'fontSize': '11px'}
            )
    
    
    # Callback to save aesthetics when Save button is clicked
    @app.callback(
        Output('marker-aesthetics-store', 'data'),
        [Input('save-aesthetics', 'n_clicks')],
        [
            State('marker-aesthetics-store', 'data'),
            State('dropdown-group', 'value'),
            State({'type': 'color-input-modal', 'index': ALL}, 'value'),
            State({'type': 'color-input-modal', 'index': ALL}, 'id'),
            State('aesthetics-edit-table', 'rowData'),
            State({'type': 'colorscale-dropdown-modal', 'index': ALL}, 'value')
        ],
        prevent_initial_call=True
    )
    def save_aesthetics_edits(n_clicks, aesthetics_store, group, color_values, color_ids, row_data, colorscale_values):
        """Save aesthetics edits to store when Save button is clicked"""
        if not n_clicks or not aesthetics_store or not group:
            raise dash.exceptions.PreventUpdate
        
        # Get current group aesthetics
        if group not in aesthetics_store:
            group_aesthetics = get_init_aesthetics(args, group, df)
        else:
            group_aesthetics = aesthetics_store[group]
        
        # Check if continuous (colorscale only)
        is_continuous = group != 'none' and group in df.columns and df[group].dtype.kind in 'fi'
        
        if is_continuous:
            # For continuous, update colorscale from dropdown and unselected color from color picker
            
            # Update colorscale from pattern-matched dropdown
            if colorscale_values and len(colorscale_values) > 0:
                group_aesthetics['color']['colorscale'] = colorscale_values[0]
            
            # Update unselected color from pattern-matched color picker
            if color_values and color_ids:
                for val, id_dict in zip(color_values, color_ids):
                    key = id_dict['index']
                    if key == 'unselected':
                        group_aesthetics['color']['unselected'] = val
            
            # Update size/opacity/symbol from AG Grid rowData for default and unselected
            # Row 0 = 'default', Row 1 = 'unselected'
            if row_data:
                for idx, row in enumerate(row_data):
                    key = 'default' if idx == 0 else 'unselected'
                    
                    # Size
                    size_val = row.get('Size')
                    if size_val and size_val != '':
                        try:
                            group_aesthetics['size'][key] = int(size_val)
                        except (ValueError, TypeError):
                            pass
                    
                    # Opacity
                    opacity_val = row.get('Opacity')
                    if opacity_val and opacity_val != '':
                        try:
                            group_aesthetics['opacity'][key] = float(opacity_val)
                        except (ValueError, TypeError):
                            pass
                    
                    # Symbol: skip if "-" (means use default)
                    symbol_val = row.get('Symbol')
                    if symbol_val and symbol_val != '' and symbol_val != '-':
                        group_aesthetics['symbol'][key] = symbol_val
                        # Keep map symbols in sync for continuous groups
                        if 'symbol_map' in group_aesthetics:
                            group_aesthetics['symbol_map'][key] = symbol_val
        else:
            # For categorical, update colors from color pickers and size/opacity/symbol from AG Grid
            default_size = group_aesthetics['size']['default']
            default_opacity = group_aesthetics['opacity']['default']
            default_symbol = group_aesthetics['symbol']['default']
            
            # Update colors from pattern-matched color pickers
            if color_values and color_ids:
                for val, id_dict in zip(color_values, color_ids):
                    key = id_dict['index']
                    # Handle type conversion
                    if key not in group_aesthetics['color']:
                        for existing_key in group_aesthetics['color'].keys():
                            if str(existing_key) == str(key):
                                key = existing_key
                                break
                    group_aesthetics['color'][key] = val
            
            # Update size/opacity/symbol from AG Grid rowData
            if row_data:
                for row in row_data:
                    key = row['Group']
                    
                    # Handle type conversion - AG Grid may serialize numeric keys as strings
                    if key not in group_aesthetics['size']:
                        for existing_key in group_aesthetics['size'].keys():
                            if str(existing_key) == str(key):
                                key = existing_key
                                break
                    
                    # Size
                    size_val = row.get('Size')
                    if size_val == '-' or size_val == '' or size_val is None:
                        group_aesthetics['size'][key] = default_size
                    else:
                        try:
                            group_aesthetics['size'][key] = int(size_val)
                        except (ValueError, TypeError):
                            group_aesthetics['size'][key] = default_size
                    
                    # Opacity
                    opacity_val = row.get('Opacity')
                    if opacity_val == '-' or opacity_val == '' or opacity_val is None:
                        group_aesthetics['opacity'][key] = default_opacity
                    else:
                        try:
                            group_aesthetics['opacity'][key] = float(opacity_val)
                        except (ValueError, TypeError):
                            group_aesthetics['opacity'][key] = default_opacity
                    
                    # Symbol
                    symbol_val = row.get('Symbol')
                    if symbol_val == '-' or symbol_val == '' or symbol_val is None:
                        group_aesthetics['symbol'][key] = default_symbol
                    else:
                        group_aesthetics['symbol'][key] = symbol_val
        
        # Update store
        aesthetics_store[group] = group_aesthetics
        logging.info(f"Aesthetics saved for group '{group}'")
        return aesthetics_store
    
    # Callback to export aesthetics to JSON file
    @app.callback(
        Output('download-aesthetics', 'data'),
        [Input('export-aesthetics-btn', 'n_clicks')],
        [State('marker-aesthetics-store', 'data')],
        prevent_initial_call=True
    )
    def export_aesthetics(n_clicks, aesthetics_store):
        """Export aesthetics store to JSON file for --aesthetics_file"""
        if not n_clicks or not aesthetics_store:
            raise dash.exceptions.PreventUpdate
        
        import json
        
        # Filter aesthetics to only include non-default values
        filtered_aesthetics = {}
        
        for group, group_data in aesthetics_store.items():
            filtered_group = {
                'color': {},
                'size': {},
                'opacity': {},
                'symbol': {},
                'symbol_map': {}
            }
            
            # Always include defaults and unselected
            for key in ['default', 'unselected']:
                if key in group_data['color']:
                    filtered_group['color'][key] = group_data['color'][key]
                if key in group_data['size']:
                    filtered_group['size'][key] = group_data['size'][key]
                if key in group_data['opacity']:
                    filtered_group['opacity'][key] = group_data['opacity'][key]
                if key in group_data['symbol']:
                    filtered_group['symbol'][key] = group_data['symbol'][key]
                if key in group_data['symbol_map']:
                    filtered_group['symbol_map'][key] = group_data['symbol_map'][key]
            
            # Include colorscale for continuous variables
            if 'colorscale' in group_data['color']:
                filtered_group['color']['colorscale'] = group_data['color']['colorscale']
            
            # Get defaults for comparison
            default_size = group_data['size'].get('default', args.point_size)
            default_opacity = group_data['opacity'].get('default', args.point_opacity)
            default_symbol = group_data['symbol'].get('default', args.point_symbol)
            
            # Include only non-default category values
            for key in group_data['color'].keys():
                if key not in ['default', 'unselected', 'colorscale']:
                    # Check if any aesthetic differs from default
                    has_non_default = False
                    
                    if key in group_data['size'] and group_data['size'][key] != default_size:
                        filtered_group['size'][key] = group_data['size'][key]
                        has_non_default = True
                    
                    if key in group_data['opacity'] and group_data['opacity'][key] != default_opacity:
                        filtered_group['opacity'][key] = group_data['opacity'][key]
                        has_non_default = True
                    
                    if key in group_data['symbol'] and group_data['symbol'][key] != default_symbol:
                        filtered_group['symbol'][key] = group_data['symbol'][key]
                        has_non_default = True
                    
                    # Always include color for categories (it's always defined)
                    if key in group_data['color']:
                        filtered_group['color'][key] = group_data['color'][key]
                        has_non_default = True
                    
                    # Include symbol_map if present
                    if key in group_data.get('symbol_map', {}):
                        filtered_group['symbol_map'][key] = group_data['symbol_map'][key]
            
            filtered_aesthetics[group] = filtered_group
        
        # Create JSON string
        json_str = json.dumps(filtered_aesthetics, indent=2)
        
        # Return download data
        return dict(content=json_str, filename='aesthetics.json')
    
    # Removed: color-hex-display callback (no longer needed)
    
    logging.info("Dash application created successfully")
    return app


def load_aesthetics_file(filepath):
    """
    Load aesthetics from a JSON file.
    
    Args:
        filepath: Path to JSON aesthetics file
    
    Returns:
        Dictionary with aesthetics, or empty dict if file not found
    """
    try:
        with open(filepath, 'r') as f:
            aesthetics = json.load(f)
        logging.info(f"Loaded aesthetics from {filepath}")
        return aesthetics
    except FileNotFoundError:
        logging.warning(f"Aesthetics file not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing aesthetics file {filepath}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error loading aesthetics file {filepath}: {e}")
        return {}


def merge_aesthetics(defaults, overrides):
    """
    Merge override aesthetics into defaults, keeping default structure intact.
    
    Args:
        defaults: Default aesthetics dictionary (from parameters)
        overrides: Aesthetics overrides from file
    
    Returns:
        Merged aesthetics dictionary
    """
    result = copy.deepcopy(defaults)
    
    if not overrides:
        return result
    
    # Merge color settings
    if 'color' in overrides:
        if isinstance(overrides['color'], dict):
            for key, val in overrides['color'].items():
                result['color'][key] = val
    
    # Merge size settings
    if 'size' in overrides:
        if isinstance(overrides['size'], dict):
            for key, val in overrides['size'].items():
                try:
                    result['size'][key] = int(val)
                except (ValueError, TypeError):
                    pass
    
    # Merge opacity settings
    if 'opacity' in overrides:
        if isinstance(overrides['opacity'], dict):
            for key, val in overrides['opacity'].items():
                try:
                    result['opacity'][key] = float(val)
                except (ValueError, TypeError):
                    pass
    
    # Merge symbol settings
    if 'symbol' in overrides:
        if isinstance(overrides['symbol'], dict):
            for key, val in overrides['symbol'].items():
                result['symbol'][key] = val
    
    # Merge symbol_map settings
    if 'symbol_map' in overrides:
        if isinstance(overrides['symbol_map'], dict):
            for key, val in overrides['symbol_map'].items():
                result['symbol_map'][key] = val
    
    return result


def get_init_aesthetics(args, group, df):
    """
    Initialize aesthetics for the given group.
    
    Args:
        args: Command-line arguments
        group: Grouping variable name
        df: DataFrame with data
    
    Returns:
        Dictionary with aesthetic settings
    """
    aesthetics = {
        'color': {
            'default': args.point_color,
            'unselected': args.point_color_unselected
        },
        'size': {
            'default': args.point_size,
            'unselected': args.point_size_unselected
        },
        'opacity': {
            'default': args.point_opacity,
            'unselected': args.point_opacity_unselected
        },
        'symbol': {
            'default': args.point_symbol,
            'unselected': args.point_symbol_unselected
        },
        'symbol_map': {
            'default': args.point_symbol if args.point_symbol in ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star'] else 'circle',
            'unselected': args.point_symbol_unselected if args.point_symbol_unselected in ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star'] else 'circle'
        }
    }
    
    # Add color map for categorical variables
    if group != 'none' and group in df.columns:
        if df[group].dtype.kind in 'fi':
            # Continuous variable
            aesthetics['color']['colorscale'] = args.color_schema_continuous
        else:
            # Categorical variable
            unique_values = df[group].dropna().unique()
            px_colors = px.colors.qualitative.Plotly
            for i, val in enumerate(unique_values):
                aesthetics['color'][val] = px_colors[i % len(px_colors)]
    
    return aesthetics




def get_aesthetics_for_group(args, group, df, store_data):
    if not store_data:
        return get_init_aesthetics(args, group, df)
    if group in store_data:
        return store_data[group]
    return get_init_aesthetics(args, group, df)


def create_layout(args, df, pcs, eigenval, df_imiss, df_lmiss, df_frq,
                 annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
                 init_selected_ids, init_group, init_continuous, init_aesthetics,
                 dropdown_group_list, dropdown_list_continuous):
    """
    Create the main application layout.
    
    Args:
        args: Command-line arguments
        df: Main DataFrame
        pcs: List of PC column names
        eigenval: Eigenvalue DataFrame
        df_imiss: Individual missing rate DataFrame
        df_lmiss: SNP missing rate DataFrame
        df_frq: Frequency DataFrame
        annotation_desc: Annotation description DataFrame
        ANNOTATION_TIME: Time column name
        ANNOTATION_LAT: Latitude column name
        ANNOTATION_LONG: Longitude column name
        init_selected_ids: Initial selected sample IDs
        init_group: Initial grouping variable
        init_continuous: Initial continuous variable
        init_aesthetics: Initial aesthetic settings
        dropdown_group_list: List of grouping options
        dropdown_list_continuous: List of continuous variables
    
    Returns:
        Dash HTML layout
    """
    # Build tab list
    tab_configs = []
    
    # Determine annotation columns for table/checkboxes
    annotation_columns = None
    if annotation_desc is not None:
        if 'Abbreviation' in annotation_desc.columns:
            annotation_columns = annotation_desc['Abbreviation'].dropna().tolist()
        else:
            annotation_columns = [col for col in annotation_desc.columns]

    # Determine continuous variables for time/continuous plot
    continuous_columns = []
    if annotation_desc is not None and 'Type' in annotation_desc.columns and 'Abbreviation' in annotation_desc.columns:
        continuous_columns = annotation_desc.loc[
            annotation_desc['Type'] == 'continuous',
            'Abbreviation'
        ].dropna().tolist()
    # Include PCs as continuous variables
    continuous_columns.extend([pc for pc in pcs if pc not in continuous_columns])

    # PCA tab (always present)
    tab_configs.append({
        'label': 'PCA',
        'value': 'pca_tab',
        'content': create_pca_tab(
            pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT,
            df, init_aesthetics, ANNOTATION_LONG, annotation_columns, continuous_columns
        )
    })
    
    # Annotation tab
    if annotation_desc is not None:
        tab_configs.append({
            'label': 'Annotation',
            'value': 'annotation_tab',
            'content': create_annotation_tab(annotation_desc, annotation_columns, pcs)
        })
    
    # Help tab
    from .args import create_parser
    parser = create_parser()
    tab_configs.append({
        'label': 'Help',
        'value': 'help_tab',
        'content': html.Div(
            html.Pre(
                strip_ansi(parser.format_help()),
                style={
                    'backgroundColor': '#f8f9fa',
                    'padding': '10px',
                    'fontFamily': 'monospace',
                    'fontSize': '14px',
                    'whiteSpace': 'pre-wrap'
                }
            ),
            style={'height': '100%', 'overflow': 'auto'}
        )
    })
    
    # Store tab content map for callback
    tab_content_map = {config['value']: config['content'] for config in tab_configs}
    
    # Initialize store with all available aesthetics (from file + defaults for init_group)
    init_store_data = {}
    
    # Load all aesthetics from file if provided
    all_file_aesthetics = {}
    if args.aesthetics_file:
        all_file_aesthetics = load_aesthetics_file(args.aesthetics_file)
    
    # Add init_group with merged aesthetics
    init_store_data[init_group] = init_aesthetics
    
    # Add all other groups from file (if not already added)
    for group_name in all_file_aesthetics:
        if group_name != init_group:
            # Create base aesthetics for this group and merge with file
            base_aesthetics = get_init_aesthetics(args, group_name, df)
            init_store_data[group_name] = merge_aesthetics(base_aesthetics, all_file_aesthetics[group_name])
    
    # Main layout
    layout = html.Div([
        # Data stores
        dcc.Store(id='selected-ids', data=init_selected_ids),
        dcc.Store(id='selected-source', data='initial'),
        dcc.Store(id='marker-aesthetics-store', data=init_store_data),
        dcc.Store(id='trace-pca', data={}),
        dcc.Store(id='trace-map', data={}),
        dcc.Store(id='trace-time', data={}),
        
        # Header with tabs
        html.Div([
            html.Img(
                src='/assets/dbc_logo_400x400.jpg',
                style={
                    'height': '40px',
                    'width': '40px',
                    'marginLeft': '20px',
                    'marginRight': '12px',
                    'marginTop': '5px',
                    'marginBottom': '5px',
                    'verticalAlign': 'middle'
                }
            ),
            html.H2("interactivePCA", style={
                'display': 'inline-block',
                'margin': '0',
                'marginRight': '30px',
                'lineHeight': '60px',
                'fontSize': '24px',
                'verticalAlign': 'bottom'
            }),
            html.Div(
                dcc.Tabs(
                    id='tabs',
                    value='pca_tab',
                    children=[
                        dcc.Tab(
                            label=config['label'],
                            value=config['value'],
                            style={'padding': '10px 18px', 'minWidth': '120px'},
                            selected_style={'padding': '10px 18px', 'minWidth': '120px'}
                        )
                        for config in tab_configs
                    ]
                ),
                style={
                    'display': 'inline-block',
                    'verticalAlign': 'bottom'
                }
            )
        ], style={
            'backgroundColor': '#f8f9fa',
            'borderBottom': '2px solid #dee2e6',
            'height': '60px',
            'whiteSpace': 'nowrap'
        }),
        
        # Tab content area - all tabs rendered, visibility toggled
        html.Div(
            id='tabs-content',
            style={
                'padding': '20px',
                'height': 'calc(100vh - 60px)',
                'overflow': 'hidden',
                'display': 'flex',
                'flexDirection': 'column'
            },
            children=[
                html.Div(
                    id=f"{config['value']}_content",
                    children=config['content'], 
                    style={
                        'display': 'block' if i == 0 else 'none',
                        'height': '100%'
                    }
                )
                for i, config in enumerate(tab_configs)
            ]
        )
    ], style={'height': '100vh', 'display': 'flex', 'flexDirection': 'column'})
    
    return {'layout': layout, 'tab_content_map': tab_content_map}


def create_pca_tab(pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT,
                   df, aesthetics, ANNOTATION_LONG=None, annotation_columns=None, continuous_columns=None):
    """Create PCA tab layout with map on the right and extra panels below."""
    # Generate initial PCA figure
    init_fig = create_initial_pca_plot(
        df=df,
        x_col=pcs[0],
        y_col=pcs[1],
        group=init_group,
        aesthetics_group=aesthetics
    )
    
    # Generate initial map figure (if coordinates available)
    init_map_fig = None
    if ANNOTATION_LAT is not None and ANNOTATION_LONG is not None:
        init_map_fig = create_geographical_map(
            df=df,
            group=init_group,
            aesthetics_group=aesthetics,
            lat_col=ANNOTATION_LAT,
            lon_col=ANNOTATION_LONG
        )
    
    # Control dropdowns
    control_section = html.Div([
        html.Div([
            html.Label('X:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='dropdown-pc-x',
                options=[{'label': pc, 'value': pc} for pc in pcs],
                value=pcs[0],
                clearable=False,
                style={'width': '140px'}
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '16px'}),
        html.Div([
            html.Label('Y:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='dropdown-pc-y',
                options=[{'label': pc, 'value': pc} for pc in pcs],
                value=pcs[1],
                clearable=False,
                style={'width': '140px'}
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '16px'}),
        html.Div([
            html.Label('Group by:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='dropdown-group',
                options=[{'label': g, 'value': g} for g in dropdown_group_list],
                value=init_group,
                clearable=False,
                style={'width': '220px'}
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '16px'}),
        html.Button(
            'Aesthetics',
            id='open-aesthetics',
            style={
                'padding': '6px 12px',
                'border': '1px solid #ccc',
                'borderRadius': '4px',
                'backgroundColor': '#ffffff',
                'cursor': 'pointer'
            }
        ),
    ], style={
        'display': 'flex',
        'alignItems': 'center',
        'gap': '8px',
        'marginBottom': '20px',
        'padding': '12px 15px',
        'backgroundColor': '#f8f9fa',
        'borderRadius': '5px',
        'flexWrap': 'wrap'
    })
    
    # PCA plot (left side)
    pca_plot = dcc.Graph(
        id='pca-plot',
        figure=init_fig,
        style={'height': '100%'}
    )

    # Time/continuous plot below PCA plot (inverse axis)
    time_hist = html.Div()
    continuous_columns = continuous_columns or []
    default_continuous = ANNOTATION_TIME if ANNOTATION_TIME in continuous_columns else (continuous_columns[0] if continuous_columns else None)
    if default_continuous is not None and default_continuous in df.columns:
        import plotly.graph_objects as go
        time_vals = df[default_continuous].dropna()
        if time_vals.empty:
            time_hist = html.Div(
                f"No valid values in {default_continuous} for distribution.",
                style={'padding': '10px', 'color': '#666'}
            )
        else:
            fig_time = go.Figure()
            fig_time.add_trace(go.Histogram(x=time_vals, nbinsx=50, marker=dict(color='steelblue')))
            fig_time.update_layout(
                xaxis_title=default_continuous,
                yaxis_title="Count",
                height=250,
                template='plotly_white'
            )
            if default_continuous == ANNOTATION_TIME:
                fig_time.update_xaxes(autorange='reversed')
            
            time_hist = html.Div([
                html.Div([
                    html.Label('Variable:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='time-variable',
                        options=[{'label': c, 'value': c} for c in continuous_columns],
                        value=default_continuous,
                        clearable=False,
                        style={'width': '200px'}
                    ),
                    html.Label('Visualization mode:', style={'marginRight': '10px', 'fontWeight': 'bold'}),
                    dcc.RadioItems(
                        id='time-viz-mode',
                        options=[
                            {'label': 'Scatter (jittered)', 'value': 'scatter'},
                            {'label': 'Distribution', 'value': 'distribution'},
                            {'label': 'Distribution with selection', 'value': 'overlay'}
                        ],
                        value='scatter',
                        inline=True,
                        inputStyle={'marginRight': '5px'},
                        labelStyle={'marginRight': '15px'}
                    )
                ], style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'gap': '10px',
                    'flexWrap': 'wrap',
                    'marginBottom': '10px',
                    'padding': '8px',
                    'backgroundColor': '#f8f9fa',
                    'borderRadius': '3px',
                    'flex': '0 0 auto'
                }),
                dcc.Graph(
                    id='time-histogram',
                    figure=fig_time,
                    style={'flex': '1', 'minHeight': 0}
                )
            ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column', 'minHeight': 0})
    else:
        time_hist = html.Div(
            "Time column not available for histogram."
            if default_continuous is None else
            f"Column '{default_continuous}' not found.",
            style={'padding': '10px', 'color': '#666'}
        )

    pca_section = html.Div([
        pca_plot,
        time_hist
    ], style={'flex': '1', 'minWidth': '400px', 'marginRight': '10px'})
    
    # Build left pane (PCA + Time Histogram) with horizontal split
    left_pane = html.Div(
        id='pca-left-container',
        children=[
            html.Div(
                id='pca-plot-pane',
                children=pca_plot,
                style={
                    'flex': '0 0 60%',
                    'overflow': 'hidden',
                    'position': 'relative',
                    'display': 'flex',
                    'flexDirection': 'column'
                },
                **{'data-pane': 'top'}
            ),
            html.Div(
                id='pca-left-horizontal-resizer',
                style={
                    'height': '8px',
                    'backgroundColor': '#bbb',
                    'cursor': 'row-resize',
                    'userSelect': 'none',
                    'flex': '0 0 8px',
                        'transition': 'background-color 0.2s',
                        'position': 'relative',
                        'zIndex': 5,
                        'pointerEvents': 'auto'
                },
                title='Drag to resize'
            ),
            html.Div(
                id='pca-time-pane',
                children=time_hist,
                style={
                    'flex': '0 0 40%',
                    'overflow': 'hidden',
                    'display': 'flex',
                    'flexDirection': 'column',
                    'minHeight': '0'
                },
                **{'data-pane': 'bottom'}
            )
        ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'gap': '0',
            'flex': '1',
            'minWidth': '350px',
            'marginRight': '10px',
            'height': '100%',
            'minHeight': '0'
        }
    )
    
    # Map plot (right side) - if available
    import dash_ag_grid as dag
    if init_map_fig is not None:
        # Build initial column list: annotation columns + PC columns
        initial_columns = []
        if annotation_columns:
            initial_columns.extend(annotation_columns)
        initial_columns.extend(pcs)
        
        # Select first 10 columns as default
        default_table_columns = initial_columns[:10] if len(initial_columns) >= 10 else initial_columns
        table_columns = [c for c in default_table_columns if c in df.columns]
        table_data = df[table_columns].to_dict('records') if table_columns else []
        column_defs = [
            {
                'headerName': '',
                'checkboxSelection': True,
                'headerCheckboxSelection': True,
                'headerCheckboxSelectionFilteredOnly': True,
                'width': 40,
                'pinned': 'left'
            }
        ] + [
            {'field': col, 'headerName': col, 'sortable': True, 'filter': True}
            for col in table_columns
        ]

        map_plot = dcc.Graph(
            id='pca-map-plot',
            figure=init_map_fig,
            style={'height': '100%'}
        )

        annotation_table = dag.AgGrid(
            id='pca-annotation-table',
            rowData=table_data,
            columnDefs=column_defs,
            defaultColDef={
                'flex': 1,
                'minWidth': 150,
                'resizable': True,
                'sortable': True,
                'filter': True
            },
            dashGridOptions={
                'rowSelection': 'multiple',
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False
            },
            style={'flex': '1', 'width': '100%'}
        )

        map_section = html.Div(
            id='pca-right-container',
            children=[
                html.Div(
                    id='pca-map-pane',
                    children=map_plot,
                    style={
                        'flex': '0 0 60%',
                        'overflow': 'hidden',
                        'position': 'relative',
                        'display': 'flex',
                        'flexDirection': 'column'
                    },
                    **{'data-pane': 'top'}
                ),
                html.Div(
                    id='pca-right-horizontal-resizer',
                    style={
                        'height': '8px',
                        'backgroundColor': '#bbb',
                        'cursor': 'row-resize',
                        'userSelect': 'none',
                        'flex': '0 0 8px',
                        'transition': 'background-color 0.2s',
                        'position': 'relative',
                        'zIndex': 5,
                        'pointerEvents': 'auto'
                    },
                    title='Drag to resize'
                ),
                html.Div(
                    id='pca-table-pane',
                    children=[
                        html.H4("Annotation Table", style={'marginTop': '0', 'marginBottom': '10px'}),
                        annotation_table
                    ],
                    style={
                        'flex': '0 0 40%',
                        'overflow': 'hidden',
                        'display': 'flex',
                        'flexDirection': 'column'
                    },
                    **{'data-pane': 'bottom'}
                )
            ],
            style={
                'display': 'flex',
                'flexDirection': 'column',
                'gap': '0',
                'flex': '1',
                'minWidth': '350px',
                'height': '100%',
                'minHeight': '0'
            }
        )
    else:
        # Only PCA plot (map unavailable); keep hidden table for callbacks
        empty_table = dag.AgGrid(
            id='pca-annotation-table',
            rowData=[],
            columnDefs=[],
            defaultColDef={
                'flex': 1,
                'minWidth': 150,
                'resizable': True,
                'sortable': True,
                'filter': True
            },
            dashGridOptions={
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False
            },
            style={'display': 'none'}
        )
        map_section = html.Div(empty_table, style={'display': 'none'})
    
    # Main container with vertical split pane
    return html.Div([
        control_section,
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Aesthetics Editor")),
                dbc.ModalBody([
                    html.P(
                        "Edit values per group. Use '-' to keep default value.",
                        style={'color': '#666', 'marginBottom': '12px'}
                    ),
                    html.Div(
                        id='aesthetics-table-container',
                        style={
                            'overflowX': 'auto',
                            'overflowY': 'auto',
                            'maxHeight': '60vh'
                        }
                    )
                ], style={'maxHeight': '70vh', 'overflowY': 'auto'}),
                dbc.ModalFooter([
                    html.Button(
                        'Export to File',
                        id='export-aesthetics-btn',
                        style={
                            'padding': '8px 16px',
                            'border': '1px solid #28a745',
                            'borderRadius': '4px',
                            'backgroundColor': '#28a745',
                            'color': '#ffffff',
                            'cursor': 'pointer',
                            'marginRight': 'auto'
                        }
                    ),
                    html.Button(
                        'Cancel',
                        id='cancel-aesthetics',
                        style={
                            'padding': '8px 16px',
                            'border': '1px solid #ccc',
                            'borderRadius': '4px',
                            'backgroundColor': '#ffffff',
                            'cursor': 'pointer',
                            'marginRight': '8px'
                        }
                    ),
                    html.Button(
                        'Save Changes',
                        id='save-aesthetics',
                        style={
                            'padding': '8px 16px',
                            'border': '1px solid #0066cc',
                            'borderRadius': '4px',
                            'backgroundColor': '#0066cc',
                            'color': '#ffffff',
                            'cursor': 'pointer'
                        }
                    )
                ])
            ],
            id='aesthetics-modal',
            is_open=False,
            size='lg'
        ),
        dcc.Download(id='download-aesthetics'),
        html.Div(
            id='pca-plots-container',
            children=[
                html.Div(
                    id='pca-left-pane',
                    children=left_pane,
                    style={
                        'flex': '0 0 50%',
                        'minWidth': '350px',
                        'overflow': 'hidden',
                        'position': 'relative'
                    },
                    **{'data-pane': 'left'}
                ),
                html.Div(
                    id='pca-vertical-resizer',
                    style={
                        'width': '8px',
                        'backgroundColor': '#bbb',
                        'cursor': 'col-resize',
                        'userSelect': 'none',
                        'flex': '0 0 8px',
                        'transition': 'background-color 0.2s',
                        'position': 'relative',
                        'zIndex': 5,
                        'pointerEvents': 'auto'
                    },
                    title='Drag to resize panes'
                ),
                html.Div(
                    id='pca-right-pane',
                    children=map_section,
                    style={
                        'flex': '0 0 50%',
                        'minWidth': '350px',
                        'overflow': 'hidden'
                    },
                    **{'data-pane': 'right'}
                )
            ],
            style={
                'display': 'flex',
                'gap': '0',
                'marginBottom': '0',
                'flex': '1',
                'minHeight': '0',
                'height': '100%'
            }
        )
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})


def create_annotation_tab(annotation_desc, annotation_columns=None, pcs=None):
    """Create annotation tab layout."""
    import dash_ag_grid as dag
    import pandas as pd
    
    # Extend annotation_desc with PC columns
    if pcs:
        pc_rows = pd.DataFrame({
            'Abbreviation': pcs,
            'Description': pcs,
            'Type': ['continuous'] * len(pcs),
            'N_levels': [None] * len(pcs),
            'Dropdown': ['Yes'] * len(pcs)
        })
        annotation_desc_extended = pd.concat([annotation_desc, pc_rows], ignore_index=True)
    else:
        annotation_desc_extended = annotation_desc
    
    # Convert annotation_desc DataFrame to dict format for AG Grid
    table_data = annotation_desc_extended.to_dict('records')
    
    # Define columns for the table (dedicated checkbox selection as first column)
    column_defs = [
        {
            'headerName': '',
            'checkboxSelection': True,
            'headerCheckboxSelection': True,
            'headerCheckboxSelectionFilteredOnly': True,
            'width': 40,
            'pinned': 'left'
        }
    ] + [
        {'field': col, 'headerName': col, 'sortable': True, 'filter': True}
        for col in annotation_desc_extended.columns
    ]
    
    # Select first 10 rows as default
    row_indices_to_select = list(range(min(10, len(table_data))))
    
    return html.Div([
        html.H3("Annotation Description", style={'marginBottom': '20px'}),
        html.P("Select rows to display those columns in the PCA tab annotation table", 
               style={'color': '#666', 'marginBottom': '15px'}),
        
        dag.AgGrid(
            id='annotation-table',
            rowData=table_data,
            columnDefs=column_defs,
            defaultColDef={
                'flex': 1,
                'minWidth': 150,
                'resizable': True,
                'sortable': True,
                'filter': True
            },
            dashGridOptions={
                'rowSelection': 'multiple',
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False
            },
            selectedRows=table_data[:10] if len(table_data) >= 10 else table_data,
            style={'flex': '1', 'width': '100%'}
        )
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})


def create_eigenvalues_tab(eigenval, args):
    """Create eigenvalues tab layout."""
    # Create eigenvalue scree plot
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Calculate variance explained
    total = eigenval.sum()
    variance_explained = (eigenval / total * 100).values
    pc_names = [f'PC{i+1}' for i in range(len(eigenval))]
    
    # Determine how many PCs to show
    n_show = min(args.eigenval_top_n if hasattr(args, 'eigenval_top_n') and args.eigenval_top_n else 20, len(eigenval))
    
    fig.add_trace(go.Bar(
        x=pc_names[:n_show],
        y=variance_explained[:n_show],
        marker=dict(color='steelblue')
    ))
    
    fig.update_layout(
        title='Variance Explained by Principal Components',
        xaxis_title='Principal Component',
        yaxis_title='Variance Explained (%)',
        height=600,
        hovermode='x',
        template='plotly_white'
    )
    
    return html.Div([
        html.H3("Eigenvalues"),
        dcc.Graph(figure=fig),
        html.P(f"Total variance: {total:.2f}"),
        html.P(f"Showing top {n_show} of {len(eigenval)} components")
    ])


def create_statistics_tab(df_imiss, df_lmiss, df_frq):
    """Create statistics tab layout."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    plots = []
    
    # Individual missing rate histogram
    if df_imiss is not None:
        fig_imiss = go.Figure()
        fig_imiss.add_trace(go.Histogram(
            x=df_imiss['F_MISS'],
            nbinsx=50,
            marker=dict(color='steelblue')
        ))
        fig_imiss.update_layout(
            title='Individual Missing Rate Distribution',
            xaxis_title='Missing Rate',
            yaxis_title='Count',
            height=400,
            template='plotly_white'
        )
        plots.append(html.Div([
            html.H4(f"Individual Missing Rate ({len(df_imiss)} samples)"),
            dcc.Graph(figure=fig_imiss)
        ]))
    
    # SNP missing rate histogram
    if df_lmiss is not None:
        fig_lmiss = go.Figure()
        fig_lmiss.add_trace(go.Histogram(
            x=df_lmiss['F_MISS'],
            nbinsx=50,
            marker=dict(color='coral')
        ))
        fig_lmiss.update_layout(
            title='SNP Missing Rate Distribution',
            xaxis_title='Missing Rate',
            yaxis_title='Count',
            height=400,
            template='plotly_white'
        )
        plots.append(html.Div([
            html.H4(f"SNP Missing Rate ({len(df_lmiss)} SNPs)"),
            dcc.Graph(figure=fig_lmiss)
        ]))
    
    # Allele frequency histogram
    if df_frq is not None:
        fig_frq = go.Figure()
        fig_frq.add_trace(go.Histogram(
            x=df_frq['MAF'],
            nbinsx=50,
            marker=dict(color='seagreen')
        ))
        fig_frq.update_layout(
            title='Minor Allele Frequency Distribution',
            xaxis_title='MAF',
            yaxis_title='Count',
            height=400,
            template='plotly_white'
        )
        plots.append(html.Div([
            html.H4(f"Allele Frequencies ({len(df_frq)} SNPs)"),
            dcc.Graph(figure=fig_frq)
        ]))
    
    return html.Div([
        html.H3("Statistics"),
        *plots
    ])
