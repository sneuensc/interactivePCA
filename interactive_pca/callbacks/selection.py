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


def register_selection_callbacks(app, df, annotation_desc):
    """
    Register all selection-related callbacks.
    
    Args:
        app: Dash app instance
        df: Main DataFrame
        annotation_desc: Annotation description DataFrame
    """
    
    @app.callback(
        Output('selection-counter', 'children'),
        Input('selection-store', 'data')
    )
    def update_selection_counter(selected_indexes):
        """Display count of selected samples."""
        return f"Selected: {len(selected_indexes) if selected_indexes else 0} / {len(df)}"
    
    @app.callback(
        Output('hover-detailed', 'data'),
        Input('hover-detailed-toggle', 'value')
    )
    def update_hover_detailed(hover_toggle):
        """Toggle detailed hover information."""
        return 'detailed' in hover_toggle
    
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
        """Select all samples."""
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        
        all_ids = df['id'].tolist()
        selected_set = set(str(sid) for sid in all_ids)
        
        # Update PCA figure
        if pca_fig:
            for trace in pca_fig.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
        
        # Update map figure
        if map_fig:
            for trace in map_fig.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
        
        return all_ids, pca_fig, map_fig
    
    @app.callback(
        Output('selection-store', 'data', allow_duplicate=True),
        Output('pca-filter-error-message', 'children'),
        Input('pca-filter-query', 'value'),
        prevent_initial_call=True
    )
    def filter_pca_table_and_sync_selection(query_string):
        """Filter samples based on pandas query and update selection."""
        # If no query, select all
        if not query_string or query_string.strip() == '':
            return df['id'].tolist(), ""
        
        # Try to apply the query
        try:
            filtered_df = df.query(query_string)
            selected_ids = filtered_df['id'].tolist()
            return selected_ids, ""
        except Exception as e:
            # Keep current selection and show error
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
    
    @app.callback(
        Output('pca-annotation-table', 'rowData'),
        Output('pca-annotation-table', 'columnDefs'),
        Input('selected-annotation-columns', 'data'),
        State('selection-store', 'data'),
        prevent_initial_call=False
    )
    def update_pca_annotation_table(selected_columns, selected_ids):
        """Update annotation table columns and selection state."""
        from ..components import create_checkbox_column_def, create_standard_column_def
        
        if not selected_columns:
            cols = []
        else:
            cols = [col for col in selected_columns if col in df.columns]
        
        if not cols:
            cols = ['id']
        if 'id' not in cols:
            cols = ['id'] + cols
        row_data = df[cols].to_dict('records')
        selected_set = set(str(sid) for sid in (selected_ids or []))
        for row in row_data:
            row['Selected'] = str(row.get('id')) in selected_set
        column_defs = [
            create_checkbox_column_def(),
            create_standard_column_def('id', 'id', hide=True)
        ] + [
            create_standard_column_def(col, col)
            for col in cols
            if col != 'id'
        ]
        return row_data, column_defs
    
    @app.callback(
        Output('selection-store', 'data', allow_duplicate=True),
        Input('pca-annotation-table', 'cellValueChanged'),
        State('selection-store', 'data'),
        prevent_initial_call=True
    )
    def table_to_selection_store(cell_change, selected_ids):
        """Convert selected rows in table to IDs with circular update prevention."""
        if not cell_change or 'data' not in cell_change:
            return dash.no_update
        row = cell_change.get('data') or {}
        row_id = row.get('id')
        if row_id is None:
            return dash.no_update
        
        # Get current selection as set for comparison
        current_selection = set(str(sid) for sid in (selected_ids or []))
        new_selection = set(current_selection)
        
        # Update selection based on checkbox change
        if row.get('Selected'):
            new_selection.add(str(row_id))
        else:
            new_selection.discard(str(row_id))
        
        # Prevent update if selection hasn't actually changed (prevents circular callbacks)
        if new_selection == current_selection:
            return dash.no_update
        
        return sorted(new_selection)
    
    @app.callback(
        Output('pca-annotation-table', 'rowData', allow_duplicate=True),
        Input('selection-store', 'data'),
        State('pca-annotation-table', 'rowData'),
        prevent_initial_call=True
    )
    def update_table_selection(selected_ids, row_data):
        """Update table checkbox state to reflect current selection."""
        if not row_data:
            return dash.no_update
        selected_set = set(str(sid) for sid in selected_ids)
        for row in row_data:
            row['Selected'] = str(row.get('id')) in selected_set
        return row_data
    
    # === Plot to selection store callbacks ===
    
    @app.callback(
        Output('selection-store', 'data'),
        Input('pca-plot', 'selectedData'),
        prevent_initial_call=True
    )
    def pca_plot_to_selection_store(selected_data):
        """Convert clicked/lasso points on PCA plot to IDs."""
        if not selected_data or 'points' not in selected_data or not selected_data['points']:
            return []
        
        # Extract IDs from customdata and convert to strings
        selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
        selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
        return sorted(list(set(selected_ids)))
    
    @app.callback(
        Output('selection-store', 'data', allow_duplicate=True),
        Input('pca-map-plot', 'selectedData'),
        prevent_initial_call=True
    )
    def map_plot_to_selection_store(selected_data):
        """Convert clicked/lasso points on map to IDs."""
        if not selected_data or 'points' not in selected_data or not selected_data['points']:
            return []
        
        # Extract IDs from customdata and convert to strings
        selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
        selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
        return sorted(list(set(selected_ids)))
    
    @app.callback(
        Output('selection-store', 'data', allow_duplicate=True),
        Input('time-histogram', 'selectedData'),
        prevent_initial_call=True
    )
    def time_plot_to_selection_store(selected_data):
        """Convert selected points in time scatter to IDs."""
        if not selected_data or 'points' not in selected_data or not selected_data['points']:
            return []
        
        # Extract IDs from customdata and convert to strings
        selected_ids = [str(pt.get('customdata')) for pt in selected_data['points']]
        selected_ids = [sid for sid in selected_ids if sid and sid != 'None']
        return sorted(list(set(selected_ids)))
    
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
        
        # Mark selected points in all traces using customdata (IDs)
        selected_set = set(str(sid) for sid in selected_ids) if selected_ids else set()
        
        for trace in current_fig.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0 and selected_set:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
            else:
                trace['selectedpoints'] = []
        
        return current_fig
    
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
        
        # Mark selected points in all traces using customdata (IDs)
        selected_set = set(str(sid) for sid in selected_ids) if selected_ids else set()
        
        for trace in current_fig.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0 and selected_set:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
            else:
                trace['selectedpoints'] = []
        
        return current_fig
    
    @app.callback(
        Output('time-histogram', 'figure', allow_duplicate=True),
        Input('selection-store', 'data'),
        State('time-histogram', 'figure'),
        prevent_initial_call=True
    )
    def update_time_selection(selected_ids, current_fig):
        """Update time histogram to highlight selected rows."""
        if current_fig is None:
            return {}
        
        # Mark selected points in all traces using customdata (IDs)
        selected_set = set(str(sid) for sid in selected_ids) if selected_ids else set()
        
        for trace in current_fig.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0 and selected_set:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
            else:
                trace['selectedpoints'] = []
        
        return current_fig
