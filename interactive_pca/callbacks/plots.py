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

from ..plots import generate_fig_scatter2d, generate_fig_scatter3d, create_geographical_map, build_symbol_legend_traces
from ..utils import dict_of_dicts_to_tuple
from ..components import get_aesthetics_for_group, update_figure_hover_templates


def register_plot_callbacks(app, args, df, ANNOTATION_LAT, ANNOTATION_LONG, ANNOTATION_TIME, annotation_desc, show_map_plot=True, show_time_plot=True):
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
    
    # Auto-check Show Legend when switching to a multi-value or continuous group
    @app.callback(
        Output('pca-legend-toggle', 'value'),
        Input('dropdown-group', 'value'),
        prevent_initial_call=True
    )
    def auto_set_legend(group):
        if group == 'none' or group not in df.columns:
            return []
        if df[group].dtype.kind in 'fi':          # continuous variable
            return ['show_legend']
        return ['show_legend'] if df[group].nunique() > 1 else []

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
    
    # Callback for PCA plot regeneration
    @app.callback(
        Output('pca-plot', 'figure'),
        Output('trace-map', 'data'),
        Input('dropdown-pc-x', 'value'),
        Input('dropdown-pc-y', 'value'),
        Input('dropdown-pc-z', 'value'),
        Input('dropdown-group', 'value'),
        Input('pca-3d-toggle', 'value'),
        Input('marker-aesthetics-store', 'data'),
        Input('pca-legend-toggle', 'value'),   # promoted from State so auto_set_legend is seen immediately
        Input('dropdown-group-symbol', 'value'),
        Input('symbol-aesthetics-store', 'data'),
        Input('save-trigger-store', 'data'),
        State('effective-hover-detailed', 'data'),
        State('selected-annotation-columns', 'data'),
        State('selection-store', 'data'),
        prevent_initial_call=False
    )
    def update_pca_plot_structure(pc_x, pc_y, pc_z, group, is_3d, aesthetics_store, legend_toggle,
                                   group_symbol, symbol_store, _save_tick,
                                   hover_detailed, selected_cols, selected_ids):
        """Regenerate PCA figure when any structural or aesthetic parameter changes."""
        import json
        from dash import callback_context

        # Get current aesthetics
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)

        # Symbol-group aesthetics (second dropdown)
        gs = group_symbol if group_symbol and group_symbol != 'none' else None
        sym_aest = (symbol_store or {}).get(gs, {}) if gs else {}
        sym_tuple = dict_of_dicts_to_tuple(sym_aest) if sym_aest else None

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
                selected_ids_tuple=selected_tuple,
                group_symbol=gs,
                symbol_aest_tuple=sym_tuple,
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
                legend=show_legend,
                group_symbol=gs,
                symbol_aest_tuple=sym_tuple,
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
        
        # uirevision: changing this clears Plotly UI state (zoom, lasso selection).
        # Deliberately excludes group so that changing the grouping variable does
        # not fire plotly_deselect and wipe the active selection from selection-store.
        # The correct selectedpoints are reapplied server-side by this callback when
        # structure_changed is True, so highlights remain correct regardless.
        mode_str = '3d' if 'enable_3d' in is_3d else '2d'
        uirev = f'{pc_x}-{pc_y}-{pc_z}-{mode_str}'

        # Update layout
        dual_legend = bool(gs and sym_aest)
        _r_margin = 180 if (is_categorical and show_legend and dual_legend) else \
                    140 if (is_categorical and show_legend) else 20
        _axis_fmt = dict(exponentformat='power', showexponent='all')
        if 'enable_3d' not in is_3d:
            fig.update_layout(
                autosize=True,
                uirevision=uirev,
                margin=dict(l=50, r=_r_margin, t=40, b=40),
                xaxis=_axis_fmt,
                yaxis=_axis_fmt,
                legend=dict(
                    visible=show_legend,
                    x=1.02 if is_categorical else 0.02,
                    y=1 if is_categorical else 0.98,
                    xanchor='left',
                    yanchor='top',
                    traceorder='reversed',
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
                uirevision=uirev,
                legend=dict(
                    visible=show_legend,
                    x=1.02 if is_categorical else 0.02,
                    y=1 if is_categorical else 0.98,
                    xanchor='left',
                    yanchor='top',
                    traceorder='reversed',
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
        fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'pca', group_symbol=gs)

        # Shape-group legend — independent legend2 box below the colour legend.
        # Traces carry legend='legend2' so they never appear in legend1.
        if gs and sym_aest:
            _t = 'scatter3d' if 'enable_3d' in is_3d else ('scattergl' if len(df) > 3000 else 'scatter')
            _sz = aesthetics.get('size', {}).get('default', 8)
            sym_entries = build_symbol_legend_traces(gs, sym_aest, default_size=_sz, trace_type=_t)
            fig_dict['data'] = list(fig_dict['data']) + sym_entries  # append, order irrelevant
            try:
                leg = fig_dict['layout'].get('legend', {})
                fig_dict['layout']['legend']['visible'] = True
                # Position legend2 below legend1; each entry ≈ 0.04 normalised units
                n_color = sum(1 for t in fig_dict['data']
                              if t.get('showlegend') and t.get('legend', '') != 'legend2')
                leg2_y = max(0.02, 1.0 - (n_color + 0.5) * 0.04)
                fig_dict['layout']['legend2'] = {
                    'x': leg.get('x', 1.02),
                    'xanchor': 'left',
                    'y': leg2_y,
                    'yanchor': 'top',
                    'traceorder': 'normal',
                }
            except (KeyError, TypeError):
                pass

        # Determine what triggered this callback.
        # For aesthetics/legend-only changes the structural layout is unchanged,
        # so uirevision will preserve the client-side lasso selection — we must
        # NOT override selectedpoints here or Plotly will fire plotly_deselect
        # and wipe the selection.  Only set selectedpoints when the axes, group,
        # or 3D mode changed (i.e. a structural change that resets the view).
        structural_inputs = {
            'dropdown-pc-x', 'dropdown-pc-y', 'dropdown-pc-z',
            'dropdown-group', 'pca-3d-toggle'
        }
        triggered_ids = {t['prop_id'].split('.')[0]
                         for t in callback_context.triggered}
        structure_changed = bool(triggered_ids & structural_inputs)

        if selected_ids:
            selected_set = set(str(sid) for sid in selected_ids)
            for trace in fig_dict.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0 and selected_set:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()

        return fig_dict, trace_map
    
    if show_map_plot:
        @app.callback(
            Output('pca-map-plot', 'figure'),
            Input('dropdown-group', 'value'),
            Input('marker-aesthetics-store', 'data'),
            Input('dropdown-group-symbol', 'value'),
            Input('symbol-aesthetics-store', 'data'),
            Input('save-trigger-store', 'data'),
            State('hover-detailed', 'data'),
            State('selected-annotation-columns', 'data'),
            State('selection-store', 'data'),
        )
        def update_map_plot(group, aesthetics_store, group_symbol, symbol_store, _save_tick,
                            hover_detailed, selected_cols, selection_store):
            if ANNOTATION_LAT is None or ANNOTATION_LONG is None:
                return {}
            aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
            aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
            gs = group_symbol if group_symbol and group_symbol != 'none' else None
            sym_aest = (symbol_store or {}).get(gs, {}) if gs else {}
            sym_tuple = dict_of_dicts_to_tuple(sym_aest) if sym_aest else None
            fig = create_geographical_map(
                group=group,
                aesthetics_tuple=aesthetics_tuple,
                legend=False,
                lat_col=ANNOTATION_LAT,
                lon_col=ANNOTATION_LONG,
                group_symbol=gs,
                symbol_aest_tuple=sym_tuple,
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
                    yanchor='top',
                    traceorder='reversed',
                ),
                dragmode='lasso',
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )

            fig_dict = fig.to_dict()
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'map', group_symbol=gs)

            # Reapply selection so it survives group/aesthetics changes
            if selection_store:
                selected_set = set(str(sid) for sid in selection_store)
                for trace in fig_dict.get('data', []):
                    customdata = trace.get('customdata', [])
                    if len(customdata) > 0:
                        customdata_str = np.array([str(cd) for cd in customdata])
                        mask = np.isin(customdata_str, list(selected_set))
                        trace['selectedpoints'] = np.where(mask)[0].tolist()

            return fig_dict

    show_time_plot = show_time_plot and ANNOTATION_TIME is not None and ANNOTATION_TIME in df.columns

    # Callback for time histogram updates (grouping, mode, and selection)
    if show_time_plot:
        @app.callback(
            Output('time-histogram', 'figure'),
            Input('dropdown-group', 'value'),
            Input('time-viz-mode', 'value'),
            Input('time-variable', 'value'),
            Input('selection-store', 'data'),
            Input('marker-aesthetics-store', 'data'),
            Input('dropdown-group-symbol', 'value'),
            Input('symbol-aesthetics-store', 'data'),
            Input('save-trigger-store', 'data'),
            State('hover-detailed', 'data'),
            State('selected-annotation-columns', 'data'),
            prevent_initial_call=False
        )
        def update_time_histogram(group, viz_mode, time_variable, selection_store, aesthetics_store,
                                   group_symbol, symbol_store, _save_tick,
                                   hover_detailed, selected_cols):
            if time_variable is None or time_variable not in df.columns:
                return {}

            time_vals = df[time_variable].dropna()
            if time_vals.empty:
                return {}

            # Get IDs corresponding to the time values
            time_ids = df.loc[time_vals.index, 'id'].tolist()

            # Selected IDs come from the app-level selection store
            # (holds all IDs by default, a subset after a lasso selection)
            selected_ids = selection_store or []

            fig = go.Figure()

            aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
            default_color   = aesthetics['color'].get('default', 'steelblue')
            unsel_color     = aesthetics['color'].get('unselected', '#cccccc')
            unsel_opacity   = aesthetics['opacity'].get('unselected', 0.3)
            gs = group_symbol if group_symbol and group_symbol != 'none' else None
            sym_aest = (symbol_store or {}).get(gs, {}) if gs else {}
            unsel_size_base = aesthetics['size'].get('default', 8)
            unsel_size      = aesthetics['size'].get('unselected', unsel_size_base)
            line_color_map  = aesthetics.get('line_color', {})
            unsel_lc        = line_color_map.get('unselected')
            # unselected.marker only accepts color/opacity/size — no 'line'
            _unsel_mk_dict  = dict(color=unsel_color, opacity=unsel_opacity, size=unsel_size)
            _unsel_marker   = dict(marker=_unsel_mk_dict)

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
                default_size = aesthetics['size'].get('default', 8)
                default_opacity = aesthetics['opacity'].get('default', 0.7)
                _cat_strip = False   # whether we drew per-group y-bands

                if group != 'none' and group in df.columns:
                    group_vals = df.loc[time_vals.index, group]
                    if df[group].dtype.kind in 'fi':
                        # Continuous variable — single strip with colorscale
                        jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
                        colorscale = aesthetics['color'].get('colorscale', 'Viridis')
                        _cont_mk = dict(
                            color=group_vals,
                            colorscale=colorscale,
                            size=default_size,
                            opacity=default_opacity,
                            symbol=aesthetics['symbol'].get('default', 'circle'),
                            showscale=False
                        )
                        _lc = line_color_map.get('default')
                        if _lc:
                            _cont_mk['line'] = dict(color=_lc, width=1)
                        if gs and sym_aest and gs in df.columns:
                            _cont_mk['symbol'] = [sym_aest.get(str(v), sym_aest.get('default', 'circle'))
                                                  for v in df.loc[time_vals.index, gs]]
                        fig.add_trace(go.Scatter(
                            x=time_vals,
                            y=jitter,
                            mode='markers',
                            marker=_cont_mk,
                            unselected=_unsel_marker,
                            customdata=time_ids,
                            hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                            name='All samples',
                            showlegend=False
                        ))
                    else:
                        # Categorical variable — one horizontal strip per group
                        _cat_strip = True
                        color_map = aesthetics.get('color', {})
                        size_map = aesthetics.get('size', {})
                        opacity_map = aesthetics.get('opacity', {})
                        symbol_map = aesthetics.get('symbol', {})
                        unique_vals = [val for val in group_vals.unique() if not pd.isna(val)]
                        order = aesthetics.get('order')
                        if order:
                            rev = list(reversed(order))
                            omap = {v: i for i, v in enumerate(rev)}
                            unique_vals.sort(key=lambda v: omap.get(str(v), -1))
                        n_groups = len(unique_vals)
                        for i, val in enumerate(unique_vals):
                            mask = group_vals == val
                            n_pts = int(mask.sum())
                            subset_ids = [time_ids[j] for j in range(len(time_ids)) if mask.iloc[j]]
                            y_pos = i + np.random.uniform(-0.35, 0.35, size=n_pts)
                            if gs and sym_aest and gs in df.columns:
                                per_sym = [sym_aest.get(str(v), sym_aest.get('default', 'circle'))
                                           for v in df.loc[time_vals.index[mask.to_numpy()], gs]]
                            else:
                                per_sym = symbol_map.get(str(val), aesthetics['symbol'].get('default', 'circle'))
                            _cat_mk = dict(
                                color=color_map.get(str(val), default_color),
                                size=size_map.get(str(val), default_size),
                                opacity=opacity_map.get(str(val), default_opacity),
                                symbol=per_sym
                            )
                            _lc = line_color_map.get(str(val), line_color_map.get('default'))
                            if _lc:
                                _cat_mk['line'] = dict(color=_lc, width=1)
                            fig.add_trace(go.Scatter(
                                x=time_vals[mask],
                                y=y_pos,
                                mode='markers',
                                marker=_cat_mk,
                                unselected=_unsel_marker,
                                customdata=subset_ids,
                                hovertemplate='<b>Group:</b> ' + str(val) + '<br><b>ID:</b> %{customdata}<br><extra></extra>',
                                name=str(val),
                                showlegend=False
                            ))
                else:
                    # No grouping — single strip (per-point symbols from shape group if active)
                    jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
                    _none_mk = dict(color=default_color, size=default_size, opacity=default_opacity)
                    _lc = line_color_map.get('default')
                    if _lc:
                        _none_mk['line'] = dict(color=_lc, width=1)
                    if gs and sym_aest and gs in df.columns:
                        _none_mk['symbol'] = [sym_aest.get(str(v), sym_aest.get('default', 'circle'))
                                               for v in df.loc[time_vals.index, gs]]
                    fig.add_trace(go.Scatter(
                        x=time_vals,
                        y=jitter,
                        mode='markers',
                        marker=_none_mk,
                        unselected=_unsel_marker,
                        customdata=time_ids,
                        hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                        name='All samples',
                        showlegend=False
                    ))

                if _cat_strip:
                    fig.update_layout(
                        xaxis_title=time_variable,
                        yaxis=dict(
                            tickmode='array',
                            tickvals=list(range(n_groups)),
                            ticktext=[str(v) for v in unique_vals],
                            range=[-0.5, n_groups - 0.5],
                            showgrid=True,
                            zeroline=False,
                            showticklabels=False,
                        ),
                        showlegend=False,
                        autosize=True,
                        dragmode='lasso',
                        margin=dict(l=50, r=20, t=40, b=40),
                    )
                else:
                    fig.update_layout(
                        xaxis_title=time_variable,
                        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                        autosize=True,
                        dragmode='lasso',
                        margin=dict(l=50, r=20, t=40, b=40)
                    )

            elif viz_mode == 'overlay':
                # Overlapping histograms: all vs selected
                fig.add_trace(go.Histogram(
                    x=time_vals,
                    nbinsx=50,
                    marker_color='lightgray',
                    opacity=0.6,
                    name='All',
                    showlegend=False
                ))

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

            fig.add_trace(go.Scatter(
                x=[], y=[],
                mode='markers',
                marker=dict(size=18, color='rgba(0,0,0,0)', symbol='circle-open',
                            line=dict(width=2.5, color='black')),
                name='__hover_highlight__',
                showlegend=False,
                hovertemplate='<extra></extra>'
            ))

            # Apply hover text formatting
            fig_dict = fig.to_dict()
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'time', group_symbol=gs)

            # Apply selectedpoints for scatter mode (histogram bins don't support it).
            # Done here rather than in a separate callback to avoid a race condition
            # since update_time_histogram already re-renders on selection-store changes.
            if viz_mode == 'scatter':
                if selection_store:
                    selected_set = set(str(s) for s in selection_store)
                    for trace in fig_dict.get('data', []):
                        cd = trace.get('customdata', [])
                        if cd:
                            mask = np.isin(np.array([str(c) for c in cd]), list(selected_set))
                            trace['selectedpoints'] = np.where(mask)[0].tolist()
                        else:
                            trace.pop('selectedpoints', None)
                else:
                    for trace in fig_dict.get('data', []):
                        trace.pop('selectedpoints', None)

            return fig_dict
