"""
Selection-related callbacks for interactive PCA application.

Handles selection sync across plots, tables, and stores.
"""

import os
import logging
import pandas as pd
import numpy as np
import dash
from dash import Input, Output, State


def register_selection_callbacks(app, df, annotation_desc, show_annotation_table=True, show_map_plot=True, show_time_plot=True):
    """
    Register all selection-related callbacks.
    
    Args:
        app: Dash app instance
        df: Main DataFrame
        annotation_desc: Annotation description DataFrame
        show_annotation_table: Whether annotation table UI is rendered
        show_map_plot: Whether map plot is rendered and should receive callbacks
        show_time_plot: Whether the time plot is rendered and should receive callbacks
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
        """Set selectedpoints to all indices on every trace that has customdata."""
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
        return fig

    if show_map_plot and show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
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
            return all_ids, _apply_all_selected(pca_fig), _apply_all_selected(map_fig), _apply_all_selected(time_fig)

    elif show_map_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
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
            return all_ids, _apply_all_selected(pca_fig), _apply_all_selected(map_fig)

    elif show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
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
            return all_ids, _apply_all_selected(pca_fig), _apply_all_selected(time_fig)

    else:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('pca-plot', 'figure', allow_duplicate=True),
            Input('select-all-button', 'n_clicks'),
            State('pca-plot', 'figure'),
            prevent_initial_call=True
        )
        def select_all_samples(n_clicks, pca_fig):
            if not n_clicks:
                raise dash.exceptions.PreventUpdate
            all_ids = df['id'].tolist()
            return all_ids, _apply_all_selected(pca_fig)
    
    if show_annotation_table:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Output('pca-filter-error-message', 'children'),
            Input('pca-filter-query', 'value'),
            prevent_initial_call=True
        )
        def filter_pca_table_and_sync_selection(query_string):
            """Filter samples based on pandas query and update selection."""
            if not query_string or query_string.strip() == '':
                return df['id'].tolist(), ""
            try:
                filtered_df = df.query(query_string)
                return filtered_df['id'].tolist(), ""
            except Exception as e:
                return dash.no_update, f"Query error: {str(e)}"
    
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
            Input('pca-annotation-table', 'filterModel'),
            State('pca-annotation-table', 'virtualRowData'),
            prevent_initial_call=True
        )
        def sync_table_filter_to_selection(filter_model, virtual_row_data):
            """Sync the table's column-filter result to selection-store and plots."""
            if filter_model is None:
                return dash.no_update
            if not filter_model:
                # All filters cleared — restore full selection
                return df['id'].tolist()
            if not virtual_row_data:
                return []
            return sorted([str(row['id']) for row in virtual_row_data if 'id' in row])

    if show_annotation_table:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
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
                return dash.no_update, dash.no_update
            if cell_change.get('colId') != 'Status':
                return dash.no_update, dash.no_update

            row = cell_change.get('data') or {}
            row_id = str(row.get('id', ''))
            new_status = row.get('Status', '')
            group_val = str(row.get('_group_val', ''))

            if not row_id or new_status not in ('selected', 'unselected', 'hidden'):
                return dash.no_update, dash.no_update

            # ── selection-store ──────────────────────────────────────────────
            current_sel = set(str(sid) for sid in (selected_ids or []))
            new_sel = set(current_sel)
            if new_status == 'selected':
                new_sel.add(row_id)
            else:
                new_sel.discard(row_id)
            sel_out = sorted(new_sel) if new_sel != current_sel else dash.no_update

            # ── hidden-groups-store ──────────────────────────────────────────
            is_categorical = group and group != 'none' and group in df.columns and df[group].dtype.kind not in 'fi'
            if not is_categorical or not group_val:
                return sel_out, dash.no_update

            new_hidden = dict(hidden_store or {})
            hidden_vals = set(str(g) for g in new_hidden.get(group, []))
            if new_status == 'hidden':
                hidden_vals.add(group_val)
            else:
                hidden_vals.discard(group_val)
            new_hidden[group] = sorted(hidden_vals)
            hidden_out = new_hidden if new_hidden.get(group) != (hidden_store or {}).get(group) else dash.no_update

            return sel_out, hidden_out
    
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
            return dash.no_update
        selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
        selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
        return sorted(list(set(selected_ids))) if selected_ids else dash.no_update
    
    if show_map_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Input('pca-map-plot', 'selectedData'),
            prevent_initial_call=True
        )
        def map_plot_to_selection_store(selected_data):
            """Convert lasso/box selection on map to IDs. Returns no_update on empty."""
            if not selected_data or 'points' not in selected_data or not selected_data['points']:
                return dash.no_update
            selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
            selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
            return sorted(list(set(selected_ids))) if selected_ids else dash.no_update
    
    if show_time_plot:
        @app.callback(
            Output('selection-store', 'data', allow_duplicate=True),
            Input('time-histogram', 'selectedData'),
            prevent_initial_call=True
        )
        def time_plot_to_selection_store(selected_data):
            """Convert lasso/box selection on time plot to IDs. Returns no_update on empty."""
            if not selected_data or 'points' not in selected_data or not selected_data['points']:
                return dash.no_update
            selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
            selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
            return sorted(list(set(selected_ids))) if selected_ids else dash.no_update
    
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
