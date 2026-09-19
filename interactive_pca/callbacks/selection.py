"""
Selection-related callbacks for interactive PCA application.

Handles selection sync across plots, tables, and stores.
"""

import os
import logging
import pandas as pd
import numpy as np
import dash
from dash import Input, Output, State, ctx

from ..utils import nice_step, nice_bounds


def register_selection_callbacks(app, df, annotation_desc, show_annotation_table=True, show_map_plot=True,
                                 show_time_plot=True, ANNOTATION_TIME=None):
    """
    Register all selection-related callbacks.

    Args:
        app: Dash app instance
        df: Main DataFrame
        annotation_desc: Annotation description DataFrame
        show_annotation_table: Whether annotation table UI is rendered
        show_map_plot: Whether map plot is rendered and should receive callbacks
        show_time_plot: Whether the time plot is rendered and should receive callbacks
        ANNOTATION_TIME: The actual --time column (or None) — its plot axis is
            reversed (layouts/__init__.py), so the time-slice slider mirrors it
    """
    
    @app.callback(
        Output('selection-counter', 'children'),
        Input('selection-store', 'data'),
        Input('hidden-groups-store', 'data'),
        State('dropdown-group', 'value'),
    )
    def update_selection_counter(selected_indexes, hidden_store, group):
        """Display count of selected / hidden samples.

        A point is either selected, hidden, or unselected — never two at once
        in the message.  Hidden points are excluded from the selected count.
        """
        n_total = len(df)
        sel_ids = set(str(sid) for sid in (selected_indexes or []))

        is_cat = group and group != 'none' and group in df.columns and df[group].dtype.kind not in 'fi'
        hidden_set = set(str(g) for g in (hidden_store or {}).get(group or '', [])) if is_cat else set()

        if hidden_set:
            n_hidden = int(df[group].astype(str).isin(hidden_set).sum())
            id_to_group = df.set_index('id')[group].astype(str).to_dict()
            n_selected = sum(1 for sid in sel_ids if id_to_group.get(sid, '') not in hidden_set)
            return f"Selected: {n_selected} / {n_total}  ({n_hidden} hidden)"

        return f"Selected: {len(sel_ids)} / {n_total}"

    @app.callback(
        Output('selection-source-label', 'children'),
        Input('selected-source', 'data'),
    )
    def show_selection_source(source):
        """Label next to the counter saying what last changed the selection."""
        if not source or source == 'initial':
            return ''
        return f"(via {source})"

    @app.callback(
        Output('hover-detailed', 'data'),
        Input('hover-detailed-toggle', 'value')
    )
    def update_hover_detailed(hover_toggle):
        """Toggle detailed hover information."""
        return 'hover_detailed' in hover_toggle
    
    if show_annotation_table:
        @app.callback(
            Output('selected-annotation-columns', 'data'),
            Input('annotation-table', 'cellValueChanged'),
            State('annotation-table', 'rowData'),
            prevent_initial_call=True
        )
        def update_selected_annotation_columns(_cell_change, row_data):
            """Update selected columns based on annotation table checkbox state."""
            if not row_data:
                return []
            selected_cols = [
                row['Abbreviation']
                for row in row_data
                if row.get('Selected', False) and 'Abbreviation' in row
            ]
            return selected_cols
    
    @app.callback(
        Input('save-selection', 'n_clicks'),
        State('selection-store', 'data'),
        prevent_initial_call=True
    )
    def save_selection(n_clicks, selected_ids):
        """Save selected sample IDs to a file."""
        if not n_clicks or not selected_ids:
            return
        
        # Save to file
        output_file = 'selected_samples.txt'
        with open(output_file, 'w') as f:
            for sid in selected_ids:
                f.write(f"{sid}\n")
        
        logging.info(f"Saved {len(selected_ids)} selected IDs to {output_file}")
    
    def _apply_all_selected(fig):
        """Set selectedpoints to all indices on every trace that has customdata,
        and clear any drawn lasso/box-select outline — otherwise a stale shape
        lingers on the plot even though every point is selected again."""
        if not fig:
            return fig
        all_ids = df['id'].tolist()
        selected_set = set(str(sid) for sid in all_ids)
        for trace in fig.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
            else:
                trace.pop('selectedpoints', None)
        if fig.get('layout', {}).get('selections'):
            fig['layout']['selections'] = []
        return fig

    if show_map_plot and show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('time-window-enabled', 'value'),
            Output('pca-plot', 'figure', allow_duplicate=True),
            Output('pca-map-plot', 'figure', allow_duplicate=True),
            Output('time-histogram', 'figure', allow_duplicate=True),
            Input('select-all-button', 'n_clicks'),
            State('pca-plot', 'figure'),
            State('pca-map-plot', 'figure'),
            State('time-histogram', 'figure'),
            prevent_initial_call=True
        )
        def select_all_samples(n_clicks, pca_fig, map_fig, time_fig):
            if not n_clicks:
                raise dash.exceptions.PreventUpdate
            all_ids = df['id'].tolist()
            # Also turn off an active time-slice — otherwise its own sync
            # callback would just overwrite this reset the next time it fires.
            return (all_ids, 'Reset', False, _apply_all_selected(pca_fig),
                    _apply_all_selected(map_fig), _apply_all_selected(time_fig))

    elif show_map_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('pca-plot', 'figure', allow_duplicate=True),
            Output('pca-map-plot', 'figure', allow_duplicate=True),
            Input('select-all-button', 'n_clicks'),
            State('pca-plot', 'figure'),
            State('pca-map-plot', 'figure'),
            prevent_initial_call=True
        )
        def select_all_samples(n_clicks, pca_fig, map_fig):
            if not n_clicks:
                raise dash.exceptions.PreventUpdate
            all_ids = df['id'].tolist()
            return all_ids, 'Reset', _apply_all_selected(pca_fig), _apply_all_selected(map_fig)

    elif show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('time-window-enabled', 'value'),
            Output('pca-plot', 'figure', allow_duplicate=True),
            Output('time-histogram', 'figure', allow_duplicate=True),
            Input('select-all-button', 'n_clicks'),
            State('pca-plot', 'figure'),
            State('time-histogram', 'figure'),
            prevent_initial_call=True
        )
        def select_all_samples(n_clicks, pca_fig, time_fig):
            if not n_clicks:
                raise dash.exceptions.PreventUpdate
            all_ids = df['id'].tolist()
            return all_ids, 'Reset', False, _apply_all_selected(pca_fig), _apply_all_selected(time_fig)

    else:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('pca-plot', 'figure', allow_duplicate=True),
            Input('select-all-button', 'n_clicks'),
            State('pca-plot', 'figure'),
            prevent_initial_call=True
        )
        def select_all_samples(n_clicks, pca_fig):
            if not n_clicks:
                raise dash.exceptions.PreventUpdate
            all_ids = df['id'].tolist()
            return all_ids, 'Reset', _apply_all_selected(pca_fig)
    
    if show_annotation_table:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('pca-filter-error-message', 'children'),
            Input('pca-filter-query', 'value'),
            prevent_initial_call=True
        )
        def filter_pca_table_and_sync_selection(query_string):
            """Filter samples based on pandas query and update selection."""
            if not query_string or query_string.strip() == '':
                return df['id'].tolist(), 'Reset', ""
            try:
                filtered_df = df.query(query_string)
                return filtered_df['id'].tolist(), 'query filter', ""
            except Exception as e:
                return dash.no_update, dash.no_update, f"Query error: {str(e)}"
    
    @app.callback(
        Output('legend-toggle-container', 'style'),
        Input('dropdown-group', 'value')
    )
    def update_legend_visibility(group):
        """Show/hide legend toggle based on grouping."""
        if group == 'none' or group not in df.columns:
            return {'display': 'none'}
        return {'display': 'flex', 'alignItems': 'center', 'marginRight': '12px'}
    
    if show_annotation_table:
        @app.callback(
            Output('pca-annotation-table', 'filterModel'),
            Input('status-filter-radio', 'value'),
        )
        def filter_table_by_status(filter_value):
            """Apply a Status filter to the annotation table via the radio buttons."""
            if not filter_value or filter_value == 'all':
                return {}
            return {'Status': {'filterType': 'text', 'type': 'equals', 'filter': filter_value}}

    if show_annotation_table:
        @app.callback(
            Output('pca-annotation-table', 'rowData'),
            Output('pca-annotation-table', 'columnDefs'),
            Input('selected-annotation-columns', 'data'),
            Input('hidden-groups-store', 'data'),
            Input('dropdown-group', 'value'),
            State('selection-store', 'data'),
            prevent_initial_call=False
        )
        def update_pca_annotation_table(selected_columns, hidden_store, group, selected_ids):
            """Update annotation table columns and selection state."""
            from ..components import create_standard_column_def

            cols = [col for col in (selected_columns or []) if col in df.columns]
            if not cols:
                cols = ['id']
            if 'id' not in cols:
                cols = ['id'] + cols

            row_data = df[cols].to_dict('records')

            selected_set = set(str(sid) for sid in (selected_ids or []))
            hidden_set = set()
            id_to_group = {}
            is_categorical = group and group != 'none' and group in df.columns and df[group].dtype.kind not in 'fi'
            if hidden_store and is_categorical:
                hidden_set = set(str(g) for g in hidden_store.get(group, []))
            if is_categorical:
                id_to_group = df.set_index('id')[group].astype(str).to_dict()

            for row in row_data:
                row_id = str(row.get('id', ''))
                gval = id_to_group.get(row_id, '')
                row['_group_val'] = gval
                if hidden_set and gval in hidden_set:
                    row['Status'] = 'hidden'
                elif row_id in selected_set:
                    row['Status'] = 'selected'
                else:
                    row['Status'] = 'unselected'

            status_col = {
                'field': 'Status',
                'headerName': 'Status',
                'editable': True,
                'width': 110,
                'pinned': 'left',
                'sortable': True,
                'filter': True,
                'singleClickEdit': True,
                'cellEditor': 'agSelectCellEditor',
                'cellEditorParams': {'values': ['selected', 'unselected', 'hidden']},
            }
            column_defs = [
                status_col,
                create_standard_column_def('id', 'id', hide=True),
                create_standard_column_def('_group_val', '_group_val', hide=True),
            ] + [
                create_standard_column_def(col, col)
                for col in cols
                if col != 'id'
            ]
            return row_data, column_defs
    
    if show_annotation_table:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Input('pca-annotation-table', 'filterModel'),
            State('pca-annotation-table', 'virtualRowData'),
            prevent_initial_call=True
        )
        def sync_table_filter_to_selection(filter_model, virtual_row_data):
            """Sync the table's column-filter result to selection-store and plots."""
            if filter_model is None:
                return dash.no_update, dash.no_update
            if not filter_model:
                # All filters cleared — restore full selection
                return df['id'].tolist(), 'Reset'
            if not virtual_row_data:
                return [], 'table filter'
            return sorted([str(row['id']) for row in virtual_row_data if 'id' in row]), 'table filter'

    if show_annotation_table:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('hidden-groups-store', 'data', allow_duplicate=True),
            Input('pca-annotation-table', 'cellValueChanged'),
            State('selection-store', 'data'),
            State('hidden-groups-store', 'data'),
            State('dropdown-group', 'value'),
            prevent_initial_call=True
        )
        def table_status_to_stores(cell_change, selected_ids, hidden_store, group):
            """Apply Status dropdown change to selection-store and hidden-groups-store."""
            if not cell_change or 'data' not in cell_change:
                return dash.no_update, dash.no_update, dash.no_update
            if cell_change.get('colId') != 'Status':
                return dash.no_update, dash.no_update, dash.no_update

            row = cell_change.get('data') or {}
            row_id = str(row.get('id', ''))
            new_status = row.get('Status', '')
            group_val = str(row.get('_group_val', ''))

            if not row_id or new_status not in ('selected', 'unselected', 'hidden'):
                return dash.no_update, dash.no_update, dash.no_update

            # ── selection-store ──────────────────────────────────────────────
            current_sel = set(str(sid) for sid in (selected_ids or []))
            new_sel = set(current_sel)
            if new_status == 'selected':
                new_sel.add(row_id)
            else:
                new_sel.discard(row_id)
            sel_out = sorted(new_sel) if new_sel != current_sel else dash.no_update
            source_out = 'table status edit' if sel_out is not dash.no_update else dash.no_update

            # ── hidden-groups-store ──────────────────────────────────────────
            is_categorical = group and group != 'none' and group in df.columns and df[group].dtype.kind not in 'fi'
            if not is_categorical or not group_val:
                return sel_out, source_out, dash.no_update

            new_hidden = dict(hidden_store or {})
            hidden_vals = set(str(g) for g in new_hidden.get(group, []))
            if new_status == 'hidden':
                hidden_vals.add(group_val)
            else:
                hidden_vals.discard(group_val)
            new_hidden[group] = sorted(hidden_vals)
            hidden_out = new_hidden if new_hidden.get(group) != (hidden_store or {}).get(group) else dash.no_update

            return sel_out, source_out, hidden_out
    
    if show_annotation_table:
        @app.callback(
            Output('pca-annotation-table', 'rowData', allow_duplicate=True),
            Input('selection-store', 'data'),
            State('pca-annotation-table', 'rowData'),
            State('hidden-groups-store', 'data'),
            State('dropdown-group', 'value'),
            prevent_initial_call=True
        )
        def update_table_selection(selected_ids, row_data, hidden_store, group):
            """Update Status column to reflect current selection (from lasso/box selection)."""
            if not row_data:
                return dash.no_update
            selected_set = set(str(sid) for sid in selected_ids)
            hidden_set = set()
            if hidden_store and group and group != 'none' and group in df.columns:
                hidden_set = set(str(g) for g in hidden_store.get(group, []))
            for row in row_data:
                row_id = str(row.get('id', ''))
                gval = str(row.get('_group_val', ''))
                if hidden_set and gval in hidden_set:
                    row['Status'] = 'hidden'
                elif row_id in selected_set:
                    row['Status'] = 'selected'
                else:
                    row['Status'] = 'unselected'
            return row_data
    
    # === Plot to selection store callbacks ===
    
    @app.callback(
        Output('selection-store', 'data'),
        Output('selected-source', 'data', allow_duplicate=True),
        Input('pca-plot', 'selectedData'),
        prevent_initial_call=True
    )
    def pca_plot_to_selection_store(selected_data):
        """Convert lasso/box selection on PCA plot to IDs.

        Returns no_update when selectedData is null/empty so that programmatic
        figure updates (group change, aesthetics change) that reset selectedData
        do NOT clear the active selection.  Use the 'Select all' button to reset.
        """
        if not selected_data or 'points' not in selected_data or not selected_data['points']:
            return dash.no_update, dash.no_update
        selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
        selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
        if not selected_ids:
            return dash.no_update, dash.no_update
        return sorted(list(set(selected_ids))), 'lasso on PCA plot'

    if show_map_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Input('pca-map-plot', 'selectedData'),
            prevent_initial_call=True
        )
        def map_plot_to_selection_store(selected_data):
            """Convert lasso/box selection on map to IDs. Returns no_update on empty."""
            if not selected_data or 'points' not in selected_data or not selected_data['points']:
                return dash.no_update, dash.no_update
            selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
            selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
            if not selected_ids:
                return dash.no_update, dash.no_update
            return sorted(list(set(selected_ids))), 'lasso on map'

    if show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Input('time-histogram', 'selectedData'),
            prevent_initial_call=True
        )
        def time_plot_to_selection_store(selected_data):
            """Convert lasso/box selection on time plot to IDs. Returns no_update on empty."""
            if not selected_data or 'points' not in selected_data or not selected_data['points']:
                return dash.no_update, dash.no_update
            selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
            selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
            if not selected_ids:
                return dash.no_update, dash.no_update
            return sorted(list(set(selected_ids))), 'lasso on time plot'

        @app.callback(
            Output('time-window-range', 'min'),
            Output('time-window-range', 'max'),
            Output('time-window-range', 'step'),
            Output('time-window-range', 'value', allow_duplicate=True),
            Output('time-window-size', 'step'),
            Output('time-window-size', 'value', allow_duplicate=True),
            Input('time-variable', 'value'),
            prevent_initial_call=True
        )
        def reset_time_window_range(time_col):
            """Re-derive the slider's bounds/defaults when the time panel switches
            to a different continuous column, so the window always matches
            whatever's currently shown."""
            if time_col not in df.columns:
                return dash.no_update
            time_vals = df[time_col].dropna()
            if time_vals.empty:
                return dash.no_update
            lo, hi = float(time_vals.min()), float(time_vals.max())
            span = hi - lo
            step = nice_step(span / 200) if span > 0 else 1
            default_size = nice_step(span / 10) if span > 0 else 1
            bound_lo, bound_hi = nice_bounds(lo, hi, step)
            default_hi = min(bound_lo + default_size, bound_hi)
            value = [bound_lo, default_hi]
            return bound_lo, bound_hi, step, value, step, default_size

        @app.callback(
            Output('time-invert-toggle', 'value'),
            Input('time-variable', 'value'),
            prevent_initial_call=True
        )
        def auto_set_time_invert_default(time_col):
            """Default 'Invert' to on for the actual --time column, off for any
            other variable — the user can still toggle it freely afterwards;
            switching variables again just re-applies this default."""
            return time_col == ANNOTATION_TIME

        @app.callback(
            Output('time-window-range', 'reverse'),
            Output('time-window-slider-wrap', 'className'),
            Output('time-window-prev-btn', 'children'),
            Output('time-window-next-btn', 'children'),
            Output('time-window-prev-btn', 'style'),
            Output('time-window-next-btn', 'style'),
            Input('time-invert-toggle', 'value'),
            prevent_initial_call=True
        )
        def apply_time_invert_style(inverted):
            """Mirror the time-slice slider to match the plot's axis direction
            whenever 'Invert' is on, for whichever variable is shown.

            The slider itself flips via its own `reverse` prop (a real
            Radix-slider feature, not a CSS hack — min/max/value stay in plain
            ascending order either way). Its built-in min/max number inputs
            don't reorder themselves though, so the className swap (see
            assets/time_slider.css) handles those. The prev/next arrows swap
            which physical side they sit on (flex order) to match, so each
            still points away from the slider in the direction it actually
            moves the window.
            """
            wrap_class = 'time-slider-reversed' if inverted else ''
            prev_label, next_label = ('▶', '◀') if inverted else ('◀', '▶')
            prev_order, next_order = (4, 2) if inverted else (2, 4)
            return (bool(inverted), wrap_class, prev_label, next_label,
                    {'order': prev_order}, {'order': next_order})

        @app.callback(
            Output('time-window-range', 'value', allow_duplicate=True),
            Input('time-window-prev-btn', 'n_clicks'),
            Input('time-window-next-btn', 'n_clicks'),
            State('time-window-range', 'value'),
            State('time-window-range', 'min'),
            State('time-window-range', 'max'),
            prevent_initial_call=True
        )
        def step_time_window(_prev, _next, range_val, true_min, true_max):
            """Jump the window forward/back by exactly one window size, keeping
            its width constant (bounced back into range at either end). 'Next'
            means forward in raw value regardless of the reversed-axis CSS
            mirror, which only affects rendering, never min/max/value order."""
            if not range_val or true_min is None or true_max is None:
                return dash.no_update
            lo, hi = range_val
            size = hi - lo
            delta = size if ctx.triggered_id == 'time-window-next-btn' else -size
            new_lo, new_hi = lo + delta, hi + delta
            if new_lo < true_min:
                shift = true_min - new_lo
                new_lo += shift
                new_hi += shift
            if new_hi > true_max:
                shift = new_hi - true_max
                new_lo -= shift
                new_hi -= shift
            return [new_lo, new_hi]

        _TIME_WINDOW_ROW_HIDDEN = {'display': 'none', 'alignItems': 'center'}
        _TIME_WINDOW_ROW_VISIBLE = {'display': 'flex', 'alignItems': 'center'}

        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('selected-source', 'data', allow_duplicate=True),
            Output('time-window-store', 'data'),
            Output('time-window-range', 'value', allow_duplicate=True),
            Output('time-window-size', 'value', allow_duplicate=True),
            Output('time-window-size', 'disabled'),
            Output('time-window-range', 'disabled'),
            Output('time-window-prev-btn', 'disabled'),
            Output('time-window-next-btn', 'disabled'),
            Output('time-window-controls-row', 'style'),
            Input('time-window-enabled', 'value'),
            Input('time-window-size', 'value'),
            Input('time-window-range', 'value'),
            State('time-variable', 'value'),
            prevent_initial_call=True
        )
        def sync_time_window_to_selection(enabled, size, range_val, time_col):
            """The time-slice controls are just another selection source — like a
            lasso or the query filter, moving the window overrides whatever was
            selected before. Turning it off restores the full selection.

            The range slider is the source of truth for [lo, hi]; typing a new
            size instead stretches/shrinks it from the left edge and pushes the
            result back into the slider. Dragging the slider (either handle, or
            the block between them to move both at once) just updates the size
            box to match, without feeding back into the slider itself.
            """
            if not enabled or time_col not in df.columns or not range_val:
                return (df['id'].tolist(), 'Reset', {'enabled': False, 'lo': None, 'hi': None},
                        dash.no_update, dash.no_update, True, True, True, True, _TIME_WINDOW_ROW_HIDDEN)
            lo, hi = range_val
            range_output = dash.no_update
            if ctx.triggered_id == 'time-window-size' and size is not None:
                col_max = float(df[time_col].max())
                hi = min(lo + size, col_max)
                range_output = [lo, hi]
            else:
                size = round(hi - lo, 6)
            ids = df.loc[df[time_col].between(lo, hi), 'id'].tolist()
            if not ids:
                # An empty list is the app-wide sentinel for "no filter, show
                # everything" (see update_pca_selection's `if not selected_ids`),
                # so a window that genuinely matches nothing would otherwise be
                # read as no selection at all. Use an id that can never match a
                # real point instead, so every panel correctly dims everything.
                ids = ['__time_window_empty__']
            return (ids, 'time slice', {'enabled': True, 'lo': lo, 'hi': hi}, range_output, size,
                    False, False, False, False, _TIME_WINDOW_ROW_VISIBLE)

    # === Selection store to plot callbacks ===
    
    @app.callback(
        Output('pca-plot', 'figure', allow_duplicate=True),
        Input('selection-store', 'data'),
        State('pca-plot', 'figure'),
        prevent_initial_call=True
    )
    def update_pca_selection(selected_ids, current_fig):
        """Update PCA plot to highlight selected rows."""
        if current_fig is None:
            return {}
        if not selected_ids:
            # No selection — remove selectedpoints so Plotly shows all points normally
            for trace in current_fig.get('data', []):
                trace.pop('selectedpoints', None)
            return current_fig
        selected_set = set(str(sid) for sid in selected_ids)
        for trace in current_fig.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
            else:
                trace.pop('selectedpoints', None)
        return current_fig
    
    if show_map_plot:
        @app.callback(
            Output('pca-map-plot', 'figure', allow_duplicate=True),
            Input('selection-store', 'data'),
            State('pca-map-plot', 'figure'),
            prevent_initial_call=True
        )
        def update_map_selection(selected_ids, current_fig):
            """Update map plot to highlight selected rows."""
            if current_fig is None:
                return {}
            if not selected_ids:
                for trace in current_fig.get('data', []):
                    trace.pop('selectedpoints', None)
                return current_fig
            selected_set = set(str(sid) for sid in selected_ids)
            for trace in current_fig.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
                else:
                    trace.pop('selectedpoints', None)
            return current_fig
    
    # NOTE: update_time_selection is intentionally absent.
    # update_time_histogram (plots.py) already has selection-store as an Input
    # and applies selectedpoints internally, so a separate patching callback
    # would race against it and produce incorrect results.
