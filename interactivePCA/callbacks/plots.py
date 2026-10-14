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
from dash import Input, Output, State, callback_context

from ..plots import (
    generate_fig_scatter2d, generate_fig_scatter3d, create_geographical_map,
    generate_map_fig_scattergeo, build_symbol_legend_traces,
)
from ..utils import dict_of_dicts_to_tuple
from ..components import get_aesthetics_for_group, update_figure_hover_templates, get_symbol_map_for_group


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
        Input('dropdown-pc-x', 'value'),
        Input('dropdown-pc-y', 'value'),
        Input('dropdown-pc-z', 'value'),
        Input('dropdown-group', 'value'),
        Input('pca-3d-toggle', 'value'),
        Input('marker-aesthetics-store', 'data'),
        Input('settings2-legend-mode', 'value'),
        Input('dropdown-group-symbol', 'value'),
        Input('symbol-aesthetics-store', 'data'),
        Input('save-trigger-store', 'data'),
        Input('legend-target-store', 'data'),
        State('effective-hover-detailed', 'data'),
        State('selected-annotation-columns', 'data'),
        State('selection-store', 'data'),
        prevent_initial_call=False
    )
    def update_pca_plot_structure(pc_x, pc_y, pc_z, group, is_3d, aesthetics_store, legend_mode,
                                   group_symbol, symbol_store, _save_tick, legend_target,
                                   hover_detailed, selected_cols, selected_ids):
        """Regenerate PCA figure when any structural or aesthetic parameter changes."""
        import json
        from dash import callback_context

        # Get current aesthetics
        aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
        aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)

        # Symbol-group aesthetics (second dropdown)
        gs = group_symbol if group_symbol and group_symbol != 'none' else None
        sym_aest = get_symbol_map_for_group(gs, df, symbol_store) if gs else {}
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

        # The group-colour legend (or, for a continuous Color-by, the
        # colorbar) only ever shows on ONE active plot at a time (see
        # legend-target-store / callbacks/settings2.py:_register_legend_target)
        # — normally this one, but it relocates to the time or map plot if
        # this one is hidden. The Settings tab's Legend mode
        # (settings2-legend-mode) overrides that: 'none' suppresses it
        # everywhere, 'everywhere' bypasses the relocation and shows it on
        # every active plot at once, 'once' is the relocating default above.
        if legend_mode == 'none':
            is_legend_target = False
        elif legend_mode == 'everywhere':
            is_legend_target = True
        else:
            is_legend_target = legend_target in (None, 'pca')
        show_legend = False
        if is_categorical:
            show_legend = df[group].nunique() > 1 and is_legend_target
        elif is_continuous:
            show_legend = is_legend_target

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

        # ── Legend layout ─────────────────────────────────────────────────
        # A single legend on the right of the plot holds up to two titled
        # sections — one per active grouping (colour groups, then shape
        # groups). Group titles name the variable; groupclick='toggleitem'
        # keeps per-category show/hide working. Only the section(s) whose
        # grouping is active are present, so the legend adapts to color-only,
        # shape-only, both, or none.
        has_shape_legend = bool(
            gs and sym_aest and gs in df.columns and df[gs].dtype.kind not in 'fi'
        )
        has_color_legend = bool(is_categorical and show_legend)
        has_colorbar = bool(is_continuous and show_legend)
        any_legend = has_color_legend or has_shape_legend or has_colorbar
        _r_margin = 170 if any_legend else 20

        # When both sections are present, use grouped ordering with per-section
        # titles; otherwise a single section keeps its natural (reversed) order
        # and the legend title names the variable.
        _color_legend = dict(
            visible=has_color_legend or has_shape_legend,
            x=1.02,
            y=1.0,
            xanchor='left',
            yanchor='top',
            traceorder='grouped' if has_shape_legend else 'reversed',
            groupclick='toggleitem',
            font=dict(size=11),
            title=dict(text=group if (has_color_legend and not has_shape_legend) else ''),
        )
        _axis_fmt = dict(exponentformat='power', showexponent='all')
        if 'enable_3d' not in is_3d:
            fig.update_layout(
                autosize=True,
                uirevision=uirev,
                margin=dict(l=50, r=_r_margin, t=40, b=40),
                xaxis=_axis_fmt,
                yaxis=_axis_fmt,
                legend=_color_legend,
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
                margin=dict(l=20, r=_r_margin, t=40, b=20),
                legend=_color_legend,
                hovermode='closest',
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )

        # Apply hover formatting with current settings
        fig_dict = fig.to_dict()
        group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
        fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'pca', group_symbol=gs)

        # Shape-group legend section — appended to the single main legend as a
        # titled block below the colour groups.
        if has_shape_legend:
            _t = 'scatter3d' if 'enable_3d' in is_3d else ('scattergl' if len(df) > 3000 else 'scatter')
            _sz = aesthetics.get('size', {}).get('default', 8)
            color_entries = []
            if has_color_legend:
                # The real colour traces carry per-point symbols (dual mode), so
                # their legend swatch would show an arbitrary shape. Hide them
                # from the legend and add neutral circle swatches instead, so the
                # colour section encodes colour only. The real traces keep their
                # names, so legend clicks still toggle/hide points (legend_sync).
                color_map = aesthetics.get('color', {})
                order = aesthetics.get('order')
                seen = []
                for t in fig_dict['data']:
                    if (t.get('showlegend')
                            and t.get('name') != '__hover_highlight__'
                            and t.get('legendgroup') != 'grp_shape'):
                        t['showlegend'] = False
                        seen.append(t.get('name'))
                vals = [v for v in order if v in seen] if order else seen
                for i, val in enumerate(vals):
                    entry = {
                        'type': _t, 'mode': 'markers',
                        'marker': {'size': _sz, 'color': color_map.get(str(val), '#888888'),
                                   'symbol': 'circle'},
                        'name': str(val), 'legendgroup': 'grp_color',
                        'showlegend': True, 'hovertemplate': '<extra></extra>',
                    }
                    if i == 0:
                        entry['legendgrouptitle'] = {'text': group}
                    if _t == 'scatter3d':
                        entry['x'] = [None]; entry['y'] = [None]; entry['z'] = [None]
                    else:
                        entry['x'] = [None]; entry['y'] = [None]
                    color_entries.append(entry)
            sym_entries = build_symbol_legend_traces(gs, sym_aest, default_size=_sz, trace_type=_t)
            fig_dict['data'] = list(fig_dict['data']) + color_entries + sym_entries
            fig_dict['layout'].pop('legend2', None)

            # Continuous colour shows a colorbar rather than a colour legend, and
            # by default it occupies the same right-hand strip as the shape
            # legend. Shrink the colorbar to the top and drop the shape legend
            # below it so the two do not overlap.
            if is_continuous:
                for t in fig_dict['data']:
                    mk = t.get('marker') or {}
                    if mk.get('showscale') or mk.get('colorbar'):
                        cb = dict(mk.get('colorbar') or {})
                        cb.update({'len': 0.4, 'y': 1.0, 'yanchor': 'top',
                                   'x': 1.02, 'xanchor': 'left', 'thickness': 14})
                        mk['colorbar'] = cb
                        t['marker'] = mk
                _leg = fig_dict['layout'].setdefault('legend', {})
                _leg.update({'y': 0.55, 'yanchor': 'top'})

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

        return fig_dict
    
    if show_map_plot:
        @app.callback(
            Output('pca-map-plot', 'figure'),
            Input('dropdown-group', 'value'),
            Input('marker-aesthetics-store', 'data'),
            Input('dropdown-group-symbol', 'value'),
            Input('symbol-aesthetics-store', 'data'),
            Input('save-trigger-store', 'data'),
            Input('map-type-toggle', 'value'),
            Input('dropdown-map-x', 'value'),
            Input('dropdown-map-y', 'value'),
            Input('legend-target-store', 'data'),
            Input('settings2-legend-mode', 'value'),
            State('hover-detailed', 'data'),
            State('selected-annotation-columns', 'data'),
            State('selection-store', 'data'),
            State('map-view-store', 'data'),
        )
        def update_map_plot(group, aesthetics_store, group_symbol, symbol_store, _save_tick,
                            map_type, lon_col, lat_col, legend_target, legend_mode,
                            hover_detailed, selected_cols, selection_store, map_view):
            # dropdown-map-x/-y are prefilled from ANNOTATION_LONG/ANNOTATION_LAT
            # but start empty if those never resolved (no --latitude/--longitude
            # given) — the map panel can still exist (show_map_plot only needs
            # annotation data at all), so this is how the user picks real
            # coordinate columns live once annotation is loaded.
            lon_col = lon_col or ANNOTATION_LONG
            lat_col = lat_col or ANNOTATION_LAT
            aesthetics = get_aesthetics_for_group(args, group, df, aesthetics_store)
            aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
            gs = group_symbol if group_symbol and group_symbol != 'none' else None
            sym_aest = get_symbol_map_for_group(gs, df, symbol_store) if gs else {}
            sym_tuple = dict_of_dicts_to_tuple(sym_aest) if sym_aest else None
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
            # The group-colour legend (or, for a continuous Color-by, the
            # colorbar) only ever shows on ONE active plot at a time — this
            # one when legend-target-store points here (PCA, and possibly
            # time, hidden — see callbacks/settings2.py:_register_legend_target).
            # The Settings tab's Legend mode overrides that: 'none' suppresses
            # it everywhere, 'everywhere' bypasses the relocation and shows it
            # here regardless, 'once' is the relocating default above —
            # matching the PCA plot's own treatment (update_pca_plot_structure),
            # so a continuous colorbar never shows on both PCA and map at once.
            if legend_mode == 'none':
                is_map_legend_target = False
            elif legend_mode == 'everywhere':
                is_map_legend_target = True
            else:
                is_map_legend_target = legend_target == 'map'
            show_legend_here = bool(
                is_map_legend_target and (
                    is_continuous or (is_categorical and df[group].nunique() > 1)
                )
            )
            # 'tiles' → interactive Scattermap basemap; 'none' → the same
            # Scattergeo projection with every basemap layer switched off
            # (just the points, no geography); anything else (the default,
            # 'map') → Scattergeo with the full basemap.
            use_tiles = map_type == 'tiles'
            map_builder = create_geographical_map if use_tiles else generate_map_fig_scattergeo
            builder_kwargs = dict(
                group=group,
                aesthetics_tuple=aesthetics_tuple,
                legend=show_legend_here,
                lat_col=lat_col,
                lon_col=lon_col,
                group_symbol=gs,
                symbol_aest_tuple=sym_tuple,
            )
            if not use_tiles:
                builder_kwargs['blank'] = (map_type == 'none')
            fig = map_builder(**builder_kwargs)
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
                dragmode='select' if not use_tiles else 'lasso',
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

            # When the basemap was toggled, carry over the current geographic
            # view (a lon/lat bounding box) instead of refitting to the data,
            # so the scale/centre stays put across the switch. Other triggers
            # keep the data-fit default.
            triggered = {t['prop_id'].split('.')[0] for t in callback_context.triggered}
            if 'map-type-toggle' in triggered and map_view:
                lon0, lat0 = map_view.get('lon0'), map_view.get('lat0')
                lon1, lat1 = map_view.get('lon1'), map_view.get('lat1')
                if None not in (lon0, lat0, lon1, lat1):
                    if use_tiles:
                        import math
                        span = max(abs(lon1 - lon0), 0.01)
                        m = fig_dict['layout'].setdefault('map', {})
                        m['center'] = {'lon': (lon0 + lon1) / 2, 'lat': (lat0 + lat1) / 2}
                        m['zoom'] = math.log2(360 / span)
                    else:
                        g = fig_dict['layout'].setdefault('geo', {})
                        # Disable auto-fit so the preserved ranges take effect.
                        g['fitbounds'] = False
                        g['lonaxis'] = {**(g.get('lonaxis') or {}), 'range': [lon0, lon1]}
                        g['lataxis'] = {**(g.get('lataxis') or {}), 'range': [lat0, lat1]}

            return fig_dict

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
            Input('time-window-store', 'data'),
            Input('time-invert-toggle', 'value'),
            Input('time-rotate-toggle', 'value'),
            Input('time-group-mode', 'value'),
            Input('time-bin-size', 'value'),
            Input('legend-target-store', 'data'),
            Input('settings2-legend-mode', 'value'),
            State('hover-detailed', 'data'),
            State('selected-annotation-columns', 'data'),
            prevent_initial_call=False
        )
        def update_time_histogram(group, viz_mode, time_variable, selection_store, aesthetics_store,
                                   group_symbol, symbol_store, _save_tick, time_window, invert_axis, rotate,
                                   group_mode, bin_size, legend_target, legend_mode,
                                   hover_detailed, selected_cols):
            # 'No group' / 'Group' / 'Group with name' (Scatter/Violin only —
            # Distribution/Overlay never split or label by group).
            per_group = group_mode != 'none'
            show_group_names = group_mode == 'group_named'
            if time_variable is None or time_variable not in df.columns:
                return {}

            # The group-colour legend only ever shows on ONE active plot at a
            # time (see legend-target-store / callbacks/settings2.py's
            # _register_legend_target) — this relocates it here when the PCA
            # plot (its usual home) is hidden. The Settings tab's Legend mode
            # overrides that: 'none' suppresses it everywhere, 'everywhere'
            # bypasses the relocation and shows it here regardless, 'once' is
            # the relocating default above. Only meaningful in the two view
            # modes that actually draw one trace per category (scatter's "per
            # group" mode, violin's per-group mode); _has_category_legend
            # below tracks whether either used it.
            is_categorical_group = group != 'none' and group in df.columns and df[group].dtype.kind not in 'fi'
            if legend_mode == 'none':
                is_time_legend_target = False
            elif legend_mode == 'everywhere':
                is_time_legend_target = True
            else:
                is_time_legend_target = legend_target == 'time'
            show_legend_here = bool(
                is_time_legend_target and is_categorical_group and df[group].nunique() > 1
            )
            _has_category_legend = False

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
            sym_aest = get_symbol_map_for_group(gs, df, symbol_store) if gs else {}
            unsel_size_base = aesthetics['size'].get('default', 8)
            unsel_size      = aesthetics['size'].get('unselected', unsel_size_base)
            line_color_map  = aesthetics.get('line_color', {})
            unsel_lc        = line_color_map.get('unselected')
            # unselected.marker only accepts color/opacity/size — no 'line'
            _unsel_mk_dict  = dict(color=unsel_color, opacity=unsel_opacity, size=unsel_size)
            _unsel_marker   = dict(marker=_unsel_mk_dict)
            # Bin WIDTH (not count) drives Distribution/Overlay — 'Bin size' box
            # above the plot, defaulting to ~50 bins across the range (see
            # default_bin_size in layouts/__init__.py). Falls back to a fixed
            # bin count if left empty/invalid.
            _hist_kwargs = {'xbins': dict(size=bin_size)} if bin_size and bin_size > 0 else {'nbinsx': 50}

            if viz_mode == 'distribution':
                # Simple histogram
                fig.add_trace(go.Histogram(
                    x=time_vals,
                    **_hist_kwargs,
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
                    elif per_group:
                        # Categorical variable, "Per group" on — one horizontal strip per group
                        _cat_strip = True
                        _has_category_legend = show_legend_here
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
                                showlegend=show_legend_here
                            ))
                    else:
                        # Categorical variable, "Per group" off — keep one
                        # combined strip (no per-group row separation) but
                        # still color each point by its own group, same as
                        # the PCA/map plots always do regardless of this toggle.
                        jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
                        color_map = aesthetics.get('color', {})
                        point_colors = [color_map.get(str(v), default_color) for v in group_vals]
                        _grp_mk = dict(color=point_colors, size=default_size, opacity=default_opacity)
                        if gs and sym_aest and gs in df.columns:
                            _grp_mk['symbol'] = [sym_aest.get(str(v), sym_aest.get('default', 'circle'))
                                                 for v in df.loc[time_vals.index, gs]]
                        fig.add_trace(go.Scatter(
                            x=time_vals,
                            y=jitter,
                            mode='markers',
                            marker=_grp_mk,
                            unselected=_unsel_marker,
                            customdata=time_ids,
                            text=[str(v) for v in group_vals],
                            hovertemplate='<b>Group:</b> %{text}<br><b>ID:</b> %{customdata}<br><extra></extra>',
                            name='All samples',
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
                            showticklabels=bool(show_group_names),
                        ),
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

            elif viz_mode == 'violin':
                # Distribution shape per group (or across all data), time on x
                # to match every other view mode — no per-point selection here,
                # a violin is an aggregate density shape, not individual points.
                default_opacity = aesthetics['opacity'].get('default', 0.7)
                color_map = aesthetics.get('color', {})

                if (per_group and group != 'none' and group in df.columns
                        and df[group].dtype.kind not in 'fi'):
                    _has_category_legend = show_legend_here
                    group_vals = df.loc[time_vals.index, group]
                    unique_vals = [val for val in group_vals.unique() if not pd.isna(val)]
                    order = aesthetics.get('order')
                    if order:
                        rev = list(reversed(order))
                        omap = {v: i for i, v in enumerate(rev)}
                        unique_vals.sort(key=lambda v: omap.get(str(v), -1))
                    for val in unique_vals:
                        mask = group_vals == val
                        fig.add_trace(go.Violin(
                            x=time_vals[mask],
                            y=[str(val)] * int(mask.sum()),
                            orientation='h',
                            name=str(val),
                            line_color=color_map.get(str(val), default_color),
                            opacity=default_opacity,
                            box_visible=True,
                            meanline_visible=True,
                            points=False,
                            showlegend=show_legend_here,
                        ))
                    fig.update_layout(
                        xaxis_title=time_variable,
                        yaxis=dict(showgrid=True, zeroline=False, showticklabels=bool(show_group_names)),
                        autosize=True,
                        margin=dict(l=80, r=20, t=40, b=40),
                    )
                else:
                    # No grouping (or a continuous group, which a violin can't
                    # split into discrete shapes) — one violin across all data.
                    fig.add_trace(go.Violin(
                        x=time_vals,
                        orientation='h',
                        name='All samples',
                        line_color=default_color,
                        opacity=default_opacity,
                        box_visible=True,
                        meanline_visible=True,
                        points=False,
                        showlegend=False,
                    ))
                    fig.update_layout(
                        xaxis_title=time_variable,
                        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                        autosize=True,
                        margin=dict(l=50, r=20, t=40, b=40)
                    )

            elif viz_mode == 'overlay':
                # Overlapping histograms: all vs selected
                fig.add_trace(go.Histogram(
                    x=time_vals,
                    **_hist_kwargs,
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
                            **_hist_kwargs,
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

            # Widen the right margin and reserve the legend box exactly when a
            # branch above actually drew one (_has_category_legend) — mirrors
            # the PCA plot's own margin/legend handling. A plain dict() here
            # is harmless when no trace has showlegend=True: nothing renders.
            _r_margin = 170 if _has_category_legend else 20
            fig.update_layout(
                template='plotly_white',
                margin=dict(l=50, r=_r_margin, t=40, b=40),
                legend=dict(x=1.02, y=1.0, xanchor='left', yanchor='top',
                           traceorder='reversed', title=dict(text=group if _has_category_legend else '')),
                dragmode='lasso',
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )
            if invert_axis:
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

            # Shaded band showing where the time-slice window currently sits —
            # purely a visual anchor; the selection highlighting itself comes
            # from selection-store like any other selection source. Time sits
            # on the x-axis normally, the y-axis once rotated — add_hrect vs
            # add_vrect picks the matching axis directly, rather than relying
            # on the generic trace-data swap below (which only touches data
            # arrays, not shapes).
            if time_window and time_window.get('enabled') and time_window.get('lo') is not None:
                if rotate:
                    fig.add_hrect(y0=time_window['lo'], y1=time_window['hi'],
                                  fillcolor='LightSalmon', opacity=0.15,
                                  layer='below', line_width=0)
                else:
                    fig.add_vrect(x0=time_window['lo'], x1=time_window['hi'],
                                  fillcolor='LightSalmon', opacity=0.15,
                                  layer='below', line_width=0)

            # Apply hover text formatting
            fig_dict = fig.to_dict()
            group_colors = aesthetics_store.get(group, {}).get('color', {}) if aesthetics_store and group else {}
            fig_dict = update_figure_hover_templates(fig_dict, df, annotation_desc, group, hover_detailed, selected_cols, group_colors, 'time', group_symbol=gs)

            # "Rotate" — swap x/y on every trace and the xaxis/yaxis layout
            # dicts wholesale (so axis title, tick labels/range for the
            # per-group strip mode, and any autorange='reversed' from Invert
            # all move to the other axis together). Histogram infers its
            # orientation from which of x/y holds data when neither trace
            # sets it explicitly, so swapping the arrays alone rotates it;
            # Violin sets orientation explicitly and so needs it flipped too.
            if rotate:
                for trace in fig_dict.get('data', []):
                    trace['x'], trace['y'] = trace.get('y'), trace.get('x')
                    if trace.get('orientation'):
                        trace['orientation'] = 'h' if trace['orientation'] == 'v' else 'v'
                layout = fig_dict.setdefault('layout', {})
                layout['xaxis'], layout['yaxis'] = layout.get('yaxis', {}), layout.get('xaxis', {})

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

        _TIME_GROUP_MODE_VISIBLE = {'display': 'flex', 'alignItems': 'center'}
        _TIME_GROUP_MODE_HIDDEN = {'display': 'none', 'alignItems': 'center'}
        _TIME_BIN_SIZE_VISIBLE = {'display': 'flex', 'alignItems': 'center'}
        _TIME_BIN_SIZE_HIDDEN = {'display': 'none', 'alignItems': 'center'}

        @app.callback(
            Output('time-group-mode-container', 'style'),
            Output('time-bin-size-container', 'style'),
            Input('time-viz-mode', 'value'),
        )
        def toggle_time_view_controls(viz_mode):
            """Grouping applies to Scatter/Violin only; bin size to
            Distribution/Overlay only — each control shows for its own pair."""
            if viz_mode in ('scatter', 'violin'):
                return _TIME_GROUP_MODE_VISIBLE, _TIME_BIN_SIZE_HIDDEN
            return _TIME_GROUP_MODE_HIDDEN, _TIME_BIN_SIZE_VISIBLE
