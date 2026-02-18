"""
Hover text management for interactive PCA plots.
"""

import pandas as pd
from dash import Input, Output, State


def build_hover_text(df, annotation_desc, group=None, detailed=False, selected_columns=None, group_color_map=None):
    """
    Build hover text for points in plots.
    
    Args:
        df: DataFrame with data
        annotation_desc: DataFrame describing annotation columns
        group: Currently selected group column (for displaying in minimal hover)
        detailed: If True, include all annotation columns; if False, only include id and group
        selected_columns: List of specific columns to display in detailed hover (from annotation table)
        group_color_map: Dictionary mapping group values to colors for coloring group text
    
    Returns:
        List of hover text strings with HTML formatting
    """
    hover_texts = []
    
    if not detailed or annotation_desc is None:
        # Minimal hover - show ID and group (if available and selected)
        for idx, row in df.iterrows():
            text_parts = [f"<b>ID:</b> {row['id']}"]
            if group and group != 'none' and group in df.columns:
                group_val = row[group]
                if pd.notna(group_val):
                    # Color both group name and value if color map is available
                    # Try both str(group_val) and group_val as keys
                    color = None
                    if group_color_map:
                        color = group_color_map.get(str(group_val)) or group_color_map.get(group_val)
                    
                    if color:
                        text_parts.append(f"<span style='color:{color}'><b>{group}:</b> {group_val}</span>")
                    else:
                        text_parts.append(f"<b>{group}:</b> {group_val}")
            hover_texts.append("<br>".join(text_parts))
        return hover_texts
    
    # Build detailed hover text from selected columns or annotation columns
    if selected_columns:
        # Use only the selected columns from the annotation table
        display_cols = [col for col in selected_columns if col in df.columns]
    else:
        # Fallback: use all from annotation_desc
        display_cols = []
        if 'Abbreviation' in annotation_desc.columns:
            display_cols = annotation_desc['Abbreviation'].dropna().tolist()
        else:
            display_cols = [col for col in annotation_desc.columns if col != 'id']
        display_cols = [col for col in display_cols if col in df.columns]
    
    for idx, row in df.iterrows():
        text_parts = [f"<b>ID:</b> {row['id']}"]
        # Always add group first if available (for detailed hover)
        if group and group != 'none' and group in df.columns:
            group_val = row[group]
            if pd.notna(group_val):
                # Color both group name and value if color map is available
                # Try both str(group_val) and group_val as keys
                color = None
                if group_color_map:
                    color = group_color_map.get(str(group_val)) or group_color_map.get(group_val)
                
                if color:
                    text_parts.append(f"<span style='color:{color}'><b>{group}:</b> {group_val}</span>")
                else:
                    text_parts.append(f"<b>{group}:</b> {group_val}")
        for col in display_cols:
            val = row[col]
            if pd.notna(val):
                text_parts.append(f"<b>{col}:</b> {val}")
        hover_texts.append("<br>".join(text_parts))
    
    return hover_texts


def update_figure_hover_templates(fig, df, annotation_desc, group=None, detailed=False, selected_columns=None, group_color_map=None, plot_type='pca'):
    """
    Update hover text in a figure based on detailed flag.
    
    Args:
        fig: Plotly figure object or dict
        df: DataFrame with data
        annotation_desc: DataFrame describing annotation columns
        group: Currently selected group column (for displaying in minimal hover)
        detailed: If True, use detailed hover; otherwise minimal
        selected_columns: List of columns to display in detailed hover
        group_color_map: Dictionary mapping group values to colors
        plot_type: Type of plot ('pca', 'map', or 'time')
    
    Returns:
        Updated figure (dict)
    """
    if fig is None or not fig.get('data'):
        return fig
    
    # Build hover text for all points in the dataframe
    all_hover_texts = build_hover_text(df, annotation_desc, group, detailed, selected_columns, group_color_map)
    
    # Create a mapping from ID to hover text
    id_to_hover = dict(zip(df['id'], all_hover_texts))
    
    # Update each trace with hover text based on its customdata (which contains IDs)
    for trace in fig.get('data', []):
        customdata = trace.get('customdata', [])
        
        if customdata is None or len(customdata) == 0:
            continue
        
        # Match hover texts to this trace's customdata (IDs)
        trace_hover_texts = [id_to_hover.get(cdata, f"<b>ID:</b> {cdata}") for cdata in customdata]
        
        # Set hovertext and override hovertemplate
        trace['hovertext'] = trace_hover_texts
        trace['hoverinfo'] = 'text'
        trace['hovertemplate'] = '%{hovertext}<extra></extra>'
    
    # Add consistent hoverlabel styling to all plots
    if 'layout' not in fig:
        fig['layout'] = {}
    fig['layout']['hoverlabel'] = dict(
        bgcolor='white',
        font_color='#333',
        namelength=-1
    )
    return fig


def register_hover_update_callbacks(app, df, annotation_desc):
    """
    Register hover update callbacks for all three plots.
    
    This factory function creates 6 callbacks (2 per plot):
    - Update hover on 'hover-detailed' toggle
    - Update hover on 'selected-annotation-columns' change
    
    Args:
        app: Dash app instance
        df: DataFrame with sample data
        annotation_desc: DataFrame describing annotation columns
    """
    plots = [
        ('pca-plot', 'pca'),
        ('pca-map-plot', 'map'),
        ('time-histogram', 'time')
    ]
    
    for plot_id, plot_type in plots:
        # Callback for hover-detailed toggle
        @app.callback(
            Output(plot_id, 'figure', allow_duplicate=True),
            Input('hover-detailed', 'data'),
            State(plot_id, 'figure'),
            State('dropdown-group', 'value'),
            State('selected-annotation-columns', 'data'),
            State('marker-aesthetics-store', 'data'),
            prevent_initial_call=True
        )
        def update_hover(hover_detailed, current_fig, group, selected_cols, aesthetics_store, pt=plot_type):
            """Update plot hover templates based on detailed flag."""
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            return update_figure_hover_templates(current_fig, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, pt)
        
        # Callback for selected columns change
        @app.callback(
            Output(plot_id, 'figure', allow_duplicate=True),
            Input('selected-annotation-columns', 'data'),
            State(plot_id, 'figure'),
            State('dropdown-group', 'value'),
            State('hover-detailed', 'data'),
            State('marker-aesthetics-store', 'data'),
            prevent_initial_call=True
        )
        def update_hover_columns(selected_cols, current_fig, group, hover_detailed, aesthetics_store, pt=plot_type):
            """Update plot hover when selected columns change."""
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            return update_figure_hover_templates(current_fig, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, pt)
