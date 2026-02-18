"""
Aesthetics-related callbacks for marker customization.

Handles callbacks for:
- Aesthetics modal toggling
- Aesthetics table population and updates
- Saving aesthetics edits to store
- Exporting aesthetics to JSON file
"""

import json
import logging
import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, ALL

from ..components import get_aesthetics_for_group, get_init_aesthetics


def register_aesthetics_callbacks(app, args, df, annotation_desc):
    """
    Register all aesthetics-related callbacks.
    
    Args:
        app: Dash app instance
        args: Command-line arguments
        df: Main DataFrame with PCA and annotation data
        annotation_desc: Annotation description DataFrame
    """
    
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
