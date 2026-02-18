"""
Layout functions for the interactive PCA application.

Contains:
- create_layout: Main application layout with tabs and stores
- create_pca_tab: PCA visualization tab with plots and controls
- create_annotation_tab: Annotation description table tab
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import html, dcc

from .utils import strip_ansi, dict_of_dicts_to_tuple
from .plots import generate_fig_scatter2d, generate_fig_scatter3d, create_geographical_map
from .components import (
    create_checkbox_column_def,
    create_standard_column_def,
    load_aesthetics_file,
    merge_aesthetics,
    get_init_aesthetics
)


def create_layout(args, df, pcs,
                 annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
                 init_selected_ids, init_group, init_continuous, init_aesthetics,
                 dropdown_group_list, dropdown_list_continuous):
    """
    Create the main application layout.
    
    Args:
        args: Command-line arguments
        df: Main DataFrame
        pcs: List of PC column names
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
        Dict with 'layout' and 'tab_content_map' keys
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
            df, init_aesthetics, ANNOTATION_LONG, annotation_columns, continuous_columns, annotation_desc,
            init_selected_ids
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
    
    help_content = html.Div([
        # User guide section
        html.Div([
            html.H3('Interactive PCA Visualization - User Guide', style={'marginBottom': '20px'}),
            
            html.H4('Overview', style={'marginTop': '20px'}),
            html.P([
                'This application provides interactive visualization of Principal Component Analysis (PCA) results ',
                'with support for geographical mapping, temporal data, and rich annotations.'
            ]),
            
            html.H4('Key Features', style={'marginTop': '20px'}),
            html.Ul([
                html.Li([html.Strong('PCA Plot: '), 'Visualize samples in PC space with 2D or 3D views. Select PC axes, group samples by variables, and use lasso/box selection.']),
                html.Li([html.Strong('Geographical Map: '), 'View sample locations on an interactive map (requires latitude/longitude data).']),
                html.Li([html.Strong('Time Plot: '), 'Explore temporal distributions with scatter, histogram, or overlay views.']),
                html.Li([html.Strong('Annotation Table: '), 'Browse and filter sample metadata. Select visible columns to customize hover information.']),
            ]),
            
            html.H4('Interactive Controls', style={'marginTop': '20px'}),
            html.Ul([
                html.Li([html.Strong('Group by: '), 'Color and group samples by any categorical or continuous variable.']),
                html.Li([html.Strong('Hover detailed: '), 'Toggle between minimal hover info (ID + group) and detailed info (all selected annotation columns).']),
                html.Li([html.Strong('Lasso selection: '), 'Select samples across all plots simultaneously.']),
                html.Li([html.Strong('3D toggle: '), 'Switch between 2D and 3D PCA views.']),
                html.Li([html.Strong('Legend toggle: '), 'Show/hide legends for categorical groupings.']),
            ]),
            
            html.H4('Hover Information', style={'marginTop': '20px'}),
            html.P([
                'Hover over any point to see sample information. Use the "Hover detailed" checkbox in the PCA tab to toggle between:',
            ]),
            html.Ul([
                html.Li([html.Strong('Minimal: '), 'Shows sample ID and group (colored by group).']),
                html.Li([html.Strong('Detailed: '), 'Shows ID, group, and all columns selected in the Annotation table.']),
            ]),
            html.P([
                'The columns displayed in detailed mode match your selection in the Annotation table. ',
                'Select/deselect rows to customize which metadata appears in hover tooltips.'
            ]),
            
            html.H4('Aesthetics', style={'marginTop': '20px'}),
            html.P([
                'Click "Aesthetics" in the PCA tab to customize colors, sizes, shapes, and opacity for each group value. ',
                'For continuous variables, choose a color scale. For categorical variables, edit individual group aesthetics.'
            ]),
            
            html.H4('Tips', style={'marginTop': '20px'}),
            html.Ul([
                html.Li('Use lasso or box selection to highlight samples across all plots simultaneously.'),
                html.Li('The annotation table updates to show only selected samples.'),
                html.Li('Export selections by filtering the annotation table and copying data.'),
                html.Li('Customize hover information by selecting specific annotation columns in the table.'),
                html.Li('Save aesthetic configurations to a JSON file for reuse with --aesthetics-file.'),
            ]),
            
        ], style={
            'backgroundColor': 'white',
            'padding': '20px',
            'marginBottom': '20px',
            'borderRadius': '5px',
            'border': '1px solid #dee2e6'
        }),
        
        # Command-line parameters section
        html.H3('Command-line Parameters', style={'marginBottom': '10px'}),
        html.Pre(
            strip_ansi(parser.format_help()),
            style={
                'backgroundColor': '#f8f9fa',
                'padding': '10px',
                'fontFamily': 'monospace',
                'fontSize': '14px',
                'whiteSpace': 'pre-wrap'
            }
        )
    ], style={'height': '100%', 'overflow': 'auto', 'padding': '20px'})
    
    tab_configs.append({
        'label': 'Help',
        'value': 'help_tab',
        'content': help_content
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
    
    # Calculate initial selected annotation columns (first 10 rows, same as annotation table default)
    init_selected_cols = []
    if annotation_desc is not None:
        annotation_desc_extended = annotation_desc.copy()
        if pcs:
            pc_rows = pd.DataFrame({
                'Abbreviation': pcs,
                'Description': pcs,
                'Type': ['continuous'] * len(pcs),
                'N_levels': [None] * len(pcs),
                'Dropdown': ['Yes'] * len(pcs)
            })
            annotation_desc_extended = pd.concat([annotation_desc, pc_rows], ignore_index=True)
        
        # Get the first 10 abbreviations (matching the annotation table default selection)
        first_10 = annotation_desc_extended.head(10)
        if 'Abbreviation' in first_10.columns:
            init_selected_cols = first_10['Abbreviation'].dropna().tolist()
    
    # Main layout
    layout = html.Div([
        # Data stores
        dcc.Store(id='selected-ids', data=init_selected_ids),
        dcc.Store(id='selected-source', data='initial'),
        dcc.Store(id='marker-aesthetics-store', data=init_store_data),
        dcc.Store(id='trace-pca', data={}),
        dcc.Store(id='trace-map', data={}),
        dcc.Store(id='trace-time', data={}),
        dcc.Store(id='selection-store', data=init_selected_ids),  # Selected IDs for cross-plot sync
        dcc.Store(id='hover-detailed', data=False),  # Toggle for detailed hover information
        dcc.Store(id='selected-annotation-columns', data=init_selected_cols),  # Selected columns from annotation table
        
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
            ),
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
                   df, aesthetics, ANNOTATION_LONG=None, annotation_columns=None, continuous_columns=None, annotation_desc=None, init_selected_ids=None):
    """Create PCA tab layout with map on the right and extra panels below."""
    # Determine if legend should be shown initially (only if group has multiple unique values)
    init_show_legend = []
    init_legend = False
    if init_group != 'none' and init_group in df.columns:
        n_unique = df[init_group].nunique()
        if n_unique > 1:
            init_show_legend = ['show_legend']
            init_legend = True
    
    # Generate initial PCA figure
    aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
    init_fig = generate_fig_scatter2d(
        x_col=pcs[0],
        y_col=pcs[1],
        group=init_group,
        aesthetics_tuple=aesthetics_tuple,
        legend=init_legend
    )
    init_fig.update_layout(
        template='plotly_white',
        clickmode='event+select',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        title="",
        margin={'l': 20, 'r': 20, 't': 40, 'b': 20},
        dragmode='lasso',
        legend_title=init_group
    )
    
    # Generate initial map figure (if coordinates available)
    init_map_fig = None
    if ANNOTATION_LAT is not None and ANNOTATION_LONG is not None:
        init_map_fig = create_geographical_map(
            group=init_group,
            aesthetics_tuple=aesthetics_tuple,
            legend=False,
            lat_col=ANNOTATION_LAT,
            lon_col=ANNOTATION_LONG
        )
        # Apply layout settings to prevent rescaling when callback fires
        is_categorical = (
            init_group != 'none'
            and init_group in df.columns
            and df[init_group].dtype.kind not in 'fi'
        )
        init_map_fig.update_layout(
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
    
    # Apply initial selection to figures if provided
    if init_selected_ids:
        # Convert all IDs to strings for consistent comparison
        selected_set = set(str(sid) for sid in init_selected_ids)
        
        # Apply to PCA figure
        init_fig_dict = init_fig.to_dict()
        for trace in init_fig_dict.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0 and selected_set:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
        init_fig = init_fig_dict
        
        # Apply to map figure if available
        if init_map_fig is not None:
            init_map_dict = init_map_fig.to_dict() if hasattr(init_map_fig, 'to_dict') else init_map_fig
            for trace in init_map_dict.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0 and selected_set:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
            init_map_fig = init_map_dict
    
    # Control section (PCA controls + selection actions)
    control_section = html.Div([
        # Left side controls
        html.Div([
            html.Div([
                html.Label('X:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='dropdown-pc-x',
                    options=[{'label': pc, 'value': pc} for pc in pcs],
                    value=pcs[0],
                    clearable=False,
                    style={'width': '100px'}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '12px'}),
            html.Div([
                html.Label('Y:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='dropdown-pc-y',
                    options=[{'label': pc, 'value': pc} for pc in pcs],
                    value=pcs[1],
                    clearable=False,
                    style={'width': '100px'}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '12px'}),
            html.Div([
                html.Label('Z:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='dropdown-pc-z',
                    options=[{'label': pc, 'value': pc} for pc in pcs],
                    value=pcs[2] if len(pcs) > 2 else pcs[0],
                    clearable=False,
                    style={'width': '100px'}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '12px', 'display': 'none'}, id='z-axis-container'),
            html.Div([
                dcc.Checklist(
                    id='pca-3d-toggle',
                    options=[{'label': ' 3D', 'value': 'enable_3d'}],
                    value=[],
                    style={'marginRight': '0px'},
                    labelStyle={'marginBottom': '0px', 'whiteSpace': 'nowrap'}
                )
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
            html.Div([
                dcc.Checklist(
                    id='pca-legend-toggle',
                    options=[{'label': ' Show Legend', 'value': 'show_legend'}],
                    value=init_show_legend,
                    style={'marginRight': '0px'},
                    labelStyle={'marginBottom': '0px', 'whiteSpace': 'nowrap'}
                )
            ], id='legend-toggle-container', style={'display': 'none' if not init_show_legend else 'flex', 'alignItems': 'center', 'marginRight': '16px'}),
            html.Div([
                dcc.Checklist(
                    id='hover-detailed-toggle',
                    options=[{'label': ' Hover detailed', 'value': 'hover_detailed'}],
                    value=[],
                    style={'marginRight': '0px'},
                    labelStyle={'marginBottom': '0px', 'whiteSpace': 'nowrap'}
                )
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
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}),
        
        # Right side controls
        html.Div([
            html.Div(
                id='selection-counter',
                children='Selected: 0',
                style={
                    'marginRight': '16px',
                    'fontSize': '13px',
                    'color': '#333',
                    'fontWeight': 'bold'
                }
            ),
            html.Button(
                'Select all',
                id='select-all-button',
                style={
                    'padding': '6px 12px',
                    'border': '1px solid #ccc',
                    'borderRadius': '4px',
                    'backgroundColor': '#ffffff',
                    'cursor': 'pointer',
                    'marginRight': '8px'
                }
            ),
            html.Button(
                'Save selection',
                id='save-selection',
                style={
                    'padding': '6px 12px',
                    'border': '1px solid #ccc',
                    'borderRadius': '4px',
                    'backgroundColor': '#ffffff',
                    'cursor': 'pointer'
                }
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}),
    ], style={
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'space-between',
        'marginBottom': '20px',
        'padding': '12px 15px',
        'backgroundColor': '#f8f9fa',
        'borderRadius': '5px'
    })
    
    # PCA plot (left side)
    pca_plot = dcc.Graph(
        id='pca-plot',
        figure=init_fig,
        style={'height': '100%'}
    )

    # Time/continuous plot below PCA plot
    time_hist = html.Div()
    continuous_columns = continuous_columns or []
    default_continuous = ANNOTATION_TIME if ANNOTATION_TIME in continuous_columns else (continuous_columns[0] if continuous_columns else None)
    if default_continuous is not None and default_continuous in df.columns:
        time_vals = df[default_continuous].dropna()
        if time_vals.empty:
            time_hist = html.Div(
                f"No valid values in {default_continuous} for distribution.",
                style={'padding': '10px', 'color': '#666'}
            )
        else:
            # Create initial scatter figure with jitter (matching default 'scatter' mode)
            fig_time = go.Figure()
            time_ids = df.loc[time_vals.index, 'id'].tolist()
            np.random.seed(42)
            jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
            
            # Get default aesthetics from the initial settings passed in
            default_color = aesthetics['color'].get('default', 'steelblue')
            default_size = aesthetics['size'].get('default', 8)
            default_opacity = aesthetics['opacity'].get('default', 0.7)
            
            fig_time.add_trace(go.Scatter(
                x=time_vals,
                y=jitter,
                mode='markers',
                marker=dict(color=default_color, size=default_size, opacity=default_opacity),
                customdata=time_ids,
                hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                name='All samples',
                showlegend=False
            ))
            
            fig_time.update_layout(
                xaxis_title=default_continuous,
                yaxis_title="",
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                template='plotly_white',
                autosize=True,
                dragmode='lasso',
                margin=dict(l=50, r=20, t=40, b=40),
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )
            
            if default_continuous == ANNOTATION_TIME:
                fig_time.update_xaxes(autorange='reversed')
            
            time_hist = html.Div([
                html.Div([
                    html.Label('Variable:', style={'marginRight': '8px', 'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='time-variable',
                        options=[{'label': col, 'value': col} for col in continuous_columns],
                        value=default_continuous,
                        clearable=False,
                        style={'width': '180px', 'fontSize': '13px'}
                    ),
                    html.Label('View:', style={'marginRight': '8px', 'marginLeft': '16px', 'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='time-viz-mode',
                        options=[
                            {'label': 'Scatter', 'value': 'scatter'},
                            {'label': 'Distribution', 'value': 'distribution'},
                            {'label': 'Overlay', 'value': 'overlay'}
                        ],
                        value='scatter',
                        clearable=False,
                        style={'width': '160px', 'fontSize': '13px'}
                    ),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px', 'padding': '8px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
                dcc.Graph(
                    id='time-histogram',
                    figure=fig_time,
                    style={'height': '100%'}
                )
            ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})
    
    # Create left pane with PCA plot and time histogram (with vertical resizer)
    from .components import LAYOUT_CONFIG
    pca_split = int(LAYOUT_CONFIG["pca_time_split"] * 100)
    time_split = 100 - pca_split
    
    left_pane = html.Div([
        html.Div(pca_plot, style={'flex': f'0 0 {pca_split}%', 'overflow': 'hidden'}),
        html.Div(
            id='pca-time-resizer',
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
            title='Drag to resize panes'
        ),
        html.Div(time_hist, style={'flex': f'0 0 {time_split}%', 'overflow': 'hidden'})
    ], style={'display': 'flex', 'flexDirection': 'column', 'height': '100%', 'gap': '0'})
    
    # Map plot (top right) + Annotation table (bottom right)
    map_plot = html.Div()
    if ANNOTATION_LAT is not None and ANNOTATION_LONG is not None and init_map_fig is not None:
        map_plot = dcc.Graph(
            id='pca-map-plot',
            figure=init_map_fig,
            style={'height': '100%'}
        )
    else:
        map_plot = html.Div('No geographical coordinates available',
                           style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'color': '#999', 'height': '100%'})
    
    # Annotation table
    table_data = []
    if annotation_columns:
        table_cols = ['id'] + [col for col in annotation_columns if col in df.columns]
        table_data = df[table_cols].to_dict('records')
    
    column_defs = []
    if table_data:
        for col in table_data[0].keys():
            if col == 'id':
                column_defs.append(create_standard_column_def(col, col, width=120, pinned='left'))
            else:
                column_defs.append(create_standard_column_def(col, col, minWidth=100))
    
    annotation_table = dag.AgGrid(
        id='pca-annotation-table',
        rowData=table_data,
        columnDefs=column_defs,
        defaultColDef={'resizable': True, 'sortable': True, 'filter': True},
        dashGridOptions={
            'pagination': True,
            'paginationPageSize': 20,
            'animateRows': False
        },
        style={'height': '100%', 'width': '100%'}
    )
    
    query_field = dcc.Textarea(
        id='query-field',
        placeholder='Enter pandas query (e.g. Age > 1000 & Country == "Peru")',
        style={
            'width': '100%',
            'height': f'{LAYOUT_CONFIG["query_field_height"]}px',
            'fontFamily': 'monospace',
            'fontSize': '12px',
            'resize': 'vertical'
        }
    )
    
    # Right pane with map (top), table (middle), and filter textarea (bottom)
    map_split = int(LAYOUT_CONFIG["map_table_split"] * 100)
    table_split = 100 - map_split
    
    map_section = html.Div([
        html.Div(map_plot, style={'flex': f'0 0 {map_split}%', 'overflow': 'hidden'}),
        html.Div(
            id='map-table-resizer',
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
            title='Drag to resize panes'
        ),
        html.Div([
            annotation_table
        ], style={'flex': f'0 0 {table_split}%', 'overflow': 'hidden'}),
        html.Div([
            html.Div('Filter:', style={'fontWeight': 'bold', 'marginBottom': '5px', 'fontSize': '13px', 'padding': '0 12px', 'paddingTop': '12px'}),
            query_field,
            html.Button(
                'Apply Filter',
                id='apply-query-button',
                style={
                    'marginTop': '8px',
                    'marginLeft': '12px',
                    'marginRight': '12px',
                    'marginBottom': '12px',
                    'padding': '6px 12px',
                    'border': '1px solid #0066cc',
                    'borderRadius': '4px',
                    'backgroundColor': '#0066cc',
                    'color': '#ffffff',
                    'cursor': 'pointer',
                    'fontSize': '12px'
                }
            )
        ], style={'flex': '0 0 auto', 'minHeight': '0', 'overflow': 'auto', 'borderTop': '1px solid #dee2e6'})
    ], style={'display': 'flex', 'flexDirection': 'column', 'height': '100%', 'gap': '0'})
    
    # Aesthetics modal
    return html.Div([
        control_section,
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Edit Marker Aesthetics")),
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
    if 'Selected' not in annotation_desc_extended.columns:
        for row in table_data:
            row['Selected'] = False
    for row in table_data[:10]:
        row['Selected'] = True
    
    # Define columns for the table (checkbox column instead of row selection)
    column_defs = [
        create_checkbox_column_def(),
        create_standard_column_def('Abbreviation', 'Abbreviation', minWidth=100),
        create_standard_column_def('Description', 'Description', flex=1, minWidth=200),
        create_standard_column_def('Type', 'Type', minWidth=80),
        create_standard_column_def('N_levels', 'N_levels', minWidth=80),
        create_standard_column_def('Dropdown', 'Dropdown', minWidth=80)
    ]
    
    return html.Div([
        html.H3("Annotation Description", style={'marginBottom': '20px'}),
        html.P("Select rows to display those columns in the PCA tab annotation table", 
               style={'color': '#666', 'marginBottom': '15px'}),
        
        dag.AgGrid(
            id='annotation-table',
            rowData=table_data,
            columnDefs=column_defs,
            defaultColDef={
                'resizable': True,
            },
            dashGridOptions={
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False,
                'suppressRowClickSelection': True,
                'suppressColumnVirtualisation': True,
                'autoSizeStrategy': {
                    'type': 'fitCellContents',
                    'skipHeader': False
                }
            },
            style={'flex': '1', 'width': '100%'}
        )
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})
