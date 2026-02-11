"""
Main Dash application factory for interactivePCA.
"""

import logging
import os
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
import plotly.express as px

from .data_loader import (
    load_eigenvec, load_annotation, load_eigenval,
    load_imiss, load_lmiss, load_frq, merge_data
)
from .utils import strip_ansi
from .plots import create_initial_pca_plot


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
    
    # Initialize aesthetics
    init_aesthetics = get_init_aesthetics(args, init_group, df)
    
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
    
    # Register tab switching callback
    @app.callback(
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    def render_tab_content(active_tab):
        if active_tab in tab_content_map:
            return tab_content_map[active_tab]
        return html.Div("Tab not found")
    
    # Register callbacks (would be imported from callbacks.py)
    # from .callbacks import register_callbacks
    # register_callbacks(app, df, pcs, ...)
    
    logging.info("Dash application created successfully")
    return app


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
    
    # PCA tab (always present)
    tab_configs.append({
        'label': 'PCA',
        'value': 'pca_tab',
        'content': create_pca_tab(pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT, df, init_aesthetics)
    })
    
    # Annotation tab
    if annotation_desc is not None:
        tab_configs.append({
            'label': 'Annotation',
            'value': 'annotation_tab',
            'content': create_annotation_tab(annotation_desc)
        })
    
    # Help tab
    from .args import create_parser
    parser = create_parser()
    tab_configs.append({
        'label': 'Help',
        'value': 'help_tab',
        'content': html.Pre(
            strip_ansi(parser.format_help()),
            style={
                'backgroundColor': '#f8f9fa',
                'padding': '10px',
                'fontFamily': 'monospace',
                'fontSize': '14px',
                'whiteSpace': 'pre-wrap'
            }
        )
    })
    
    # Store tab content map for callback
    tab_content_map = {config['value']: config['content'] for config in tab_configs}
    
    # Main layout
    layout = html.Div([
        # Data stores
        dcc.Store(id='selected-ids', data=init_selected_ids),
        dcc.Store(id='selected-source', data='initial'),
        dcc.Store(id='marker-aesthetics-store', data={init_group: init_aesthetics}),
        dcc.Store(id='trace-pca', data={}),
        dcc.Store(id='trace-map', data={}),
        dcc.Store(id='trace-time', data={}),
        
        # Header
        html.Div([
            html.H1("interactivePCA", style={
                'padding': '20px',
                'margin': '0',
                'backgroundColor': '#f8f9fa',
                'borderBottom': '2px solid #dee2e6'
            })
        ]),
        
        # Tabs
        dcc.Tabs(
            id='tabs',
            value='pca_tab',
            children=[dcc.Tab(label=config['label'], value=config['value']) for config in tab_configs],
            style={
                'borderBottom': '1px solid #dee2e6',
                'padding': '0 20px'
            }
        ),
        
        # Tab content area (will be updated by callback)
        html.Div(id='tabs-content', style={'padding': '20px'}, children=tab_configs[0]['content'])
    ])
    
    return {'layout': layout, 'tab_content_map': tab_content_map}


def create_pca_tab(pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT, df, aesthetics):
    """Create PCA tab layout."""
    # Generate initial PCA figure
    init_fig = create_initial_pca_plot(
        df=df,
        x_col='PC1',
        y_col='PC2',
        group=init_group,
        aesthetics_group=aesthetics
    )
    
    return html.Div([
        html.Div([
            html.Label('Group by:'),
            dcc.Dropdown(
                id='dropdown-group',
                options=[{'label': g, 'value': g} for g in dropdown_group_list],
                value=init_group,
                clearable=False
            ),
        ], style={'width': '300px', 'marginBottom': '10px'}),
        
        html.Div([
            html.Label('PC X:'),
            dcc.Dropdown(
                id='dropdown-pc-x',
                options=[{'label': pc, 'value': pc} for pc in pcs],
                value='PC1',
                clearable=False,
                style={'width': '150px', 'display': 'inline-block', 'marginRight': '10px'}
            ),
            html.Label('PC Y:'),
            dcc.Dropdown(
                id='dropdown-pc-y',
                options=[{'label': pc, 'value': pc} for pc in pcs],
                value='PC2',
                clearable=False,
                style={'width': '150px', 'display': 'inline-block'}
            ),
        ], style={'marginBottom': '10px'}),
        
        dcc.Graph(
            id='pca-plot',
            figure=init_fig,
            style={'height': '700px'}
        )
    ])


def create_annotation_tab(annotation_desc):
    """Create annotation tab layout."""
    import dash_ag_grid as dag
    
    # Convert annotation_desc DataFrame to dict format for AG Grid
    table_data = annotation_desc.to_dict('records')
    
    # Define columns for the table
    column_defs = [
        {'field': col, 'headerName': col, 'sortable': True, 'filter': True}
        for col in annotation_desc.columns
    ]
    
    return html.Div([
        html.H3("Annotation Description", style={'marginBottom': '20px'}),
        html.P(f"Total annotation columns: {len(annotation_desc)}", style={'marginBottom': '20px'}),
        
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
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False
            },
            style={'height': '600px', 'width': '100%'}
        )
    ])


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
