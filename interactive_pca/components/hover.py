"""
Hover text management for interactive PCA plots.
"""

import pandas as pd
from dash import Input, Output, State


def build_hover_text(df, annotation_desc, group=None, detailed=False, selected_columns=None,
                     group_color_map=None, group_symbol=None):
    """
    Build hover text for points in plots.

    Args:
        df: DataFrame with data
        annotation_desc: DataFrame describing annotation columns
        group: Color-group column name
        detailed: If True, include all annotation columns
        selected_columns: Columns to display in detailed hover
        group_color_map: Dict mapping group values to colors
        group_symbol: Shape-group column name (second grouping variable)

    Returns:
        List of hover text strings with HTML formatting
    """
    hover_texts = []
    show_symbol = bool(group_symbol and group_symbol != 'none' and group_symbol in df.columns)

    if not detailed or annotation_desc is None:
        # Minimal hover — ID, colour group, shape group
        for _, row in df.iterrows():
            text_parts = [f"<b>ID:</b> {row['id']}"]
            if group and group != 'none' and group in df.columns:
                group_val = row[group]
                if pd.notna(group_val):
                    color = None
                    if group_color_map:
                        color = group_color_map.get(str(group_val)) or group_color_map.get(group_val)
                    if color:
                        text_parts.append(f"<span style='color:{color}'><b>{group}:</b> {group_val}</span>")
                    else:
                        text_parts.append(f"<b>{group}:</b> {group_val}")
            if show_symbol:
                sym_val = row[group_symbol]
                if pd.notna(sym_val):
                    text_parts.append(f"<b>{group_symbol}:</b> {sym_val}")
            hover_texts.append("<br>".join(text_parts))
        return hover_texts

    # Detailed hover
    if selected_columns:
        display_cols = [col for col in selected_columns if col in df.columns]
    else:
        display_cols = []
        if annotation_desc is not None:
            if 'Abbreviation' in annotation_desc.columns:
                display_cols = annotation_desc['Abbreviation'].dropna().tolist()
            else:
                display_cols = [col for col in annotation_desc.columns if col != 'id']
        display_cols = [col for col in display_cols if col in df.columns]
    display_cols = [col for col in display_cols if col.lower() != 'id']

    skip_cols = {group, group_symbol} - {None, 'none'}

    for _, row in df.iterrows():
        text_parts = [f"<b>ID:</b> {row['id']}"]
        if group and group != 'none' and group in df.columns:
            group_val = row[group]
            if pd.notna(group_val):
                color = None
                if group_color_map:
                    color = group_color_map.get(str(group_val)) or group_color_map.get(group_val)
                if color:
                    text_parts.append(f"<span style='color:{color}'><b>{group}:</b> {group_val}</span>")
                else:
                    text_parts.append(f"<b>{group}:</b> {group_val}")
        if show_symbol:
            sym_val = row[group_symbol]
            if pd.notna(sym_val):
                text_parts.append(f"<b>{group_symbol}:</b> {sym_val}")
        for col in display_cols:
            if col not in skip_cols:
                val = row[col]
                if pd.notna(val):
                    text_parts.append(f"<b>{col}:</b> {val}")
        hover_texts.append("<br>".join(text_parts))

    return hover_texts


def update_figure_hover_templates(fig, df, annotation_desc, group=None, detailed=False, selected_columns=None,
                                  group_color_map=None, plot_type='pca', group_symbol=None):
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
    all_hover_texts = build_hover_text(df, annotation_desc, group, detailed, selected_columns,
                                       group_color_map, group_symbol=group_symbol)
    
    # Create a mapping from ID to hover text
    id_to_hover = dict(zip(df['id'], all_hover_texts))
    
    # Update each trace with hover text based on its customdata (which contains IDs)
    for trace in fig.get('data', []):
        customdata = trace.get('customdata', [])
        
        if customdata is None or len(customdata) == 0:
            continue
        
        # Match hover texts to this trace's customdata (IDs)
        trace_hover_texts = [id_to_hover.get(cdata, f"<b>ID:</b> {cdata}") for cdata in customdata]
        
        # Store hover text and drive it via hovertemplate only.
        # Do NOT set hoverinfo='text' — that causes Plotly to bypass
        # hovertemplate and render hovertext directly, which prevents
        # the temporary minTpl override in hover_sync from taking effect.
        trace['hovertext'] = trace_hover_texts
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


def register_hover_update_callbacks(app, args, df, annotation_desc,
                                    show_map_plot=True, show_time_plot=True,
                                    show_annotation_table=True):
    """
    Register hover update callbacks for all three plots.

    Also registers a combiner that writes 'effective-hover-detailed':
    forced False when the Details tab is active, otherwise equals hover-detailed.
    All figure-update callbacks read from effective-hover-detailed so the
    in-plot tooltip is always minimal while the Details panel is open.
    """
    # --- effective-hover-detailed combiner -----------------------------------
    if show_annotation_table:
        @app.callback(
            Output('effective-hover-detailed', 'data'),
            Input('hover-detailed', 'data'),
            Input('right-panel-tabs', 'value'),
        )
        def compute_effective_detailed(hover_detailed, tab_value):
            return hover_detailed and (tab_value != 'tab-details')
    else:
        @app.callback(
            Output('effective-hover-detailed', 'data'),
            Input('hover-detailed', 'data'),
        )
        def compute_effective_detailed(hover_detailed):
            return hover_detailed

    # --- per-plot hover template callbacks -----------------------------------
    plots = [('pca-plot', 'pca')]
    if show_map_plot:
        plots.append(('pca-map-plot', 'map'))
    if show_time_plot:
        plots.append(('time-histogram', 'time'))

    for plot_id, plot_type in plots:
        # triggered by hover-detailed / tab change (via effective-hover-detailed)
        @app.callback(
            Output(plot_id, 'figure', allow_duplicate=True),
            Input('effective-hover-detailed', 'data'),
            State(plot_id, 'figure'),
            State('dropdown-group', 'value'),
            State('selected-annotation-columns', 'data'),
            State('marker-aesthetics-store', 'data'),
            prevent_initial_call=True
        )
        def update_hover(effective_detailed, current_fig, group, selected_cols,
                         aesthetics_store, pt=plot_type):
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            return update_figure_hover_templates(
                current_fig, df, annotation_desc, group,
                effective_detailed, selected_cols, group_colors, pt)

        # triggered by column selection change
        @app.callback(
            Output(plot_id, 'figure', allow_duplicate=True),
            Input('selected-annotation-columns', 'data'),
            State(plot_id, 'figure'),
            State('dropdown-group', 'value'),
            State('effective-hover-detailed', 'data'),
            State('marker-aesthetics-store', 'data'),
            prevent_initial_call=True
        )
        def update_hover_columns(selected_cols, current_fig, group, effective_detailed,
                                 aesthetics_store, pt=plot_type):
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            return update_figure_hover_templates(
                current_fig, df, annotation_desc, group,
                effective_detailed, selected_cols, group_colors, pt)

        # NOTE: no separate update_hover_group callback.
        # update_pca_plot_structure / update_map_plot / update_time_histogram all call
        # update_figure_hover_templates internally when the group changes, so a
        # dedicated callback here would race against them and restore the old figure.
