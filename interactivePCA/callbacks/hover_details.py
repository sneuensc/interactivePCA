"""
Callback that populates the 'Details' tab with annotation data for the
currently hovered point, using only the columns selected in the annotation table.
"""

import pandas as pd
from dash import Input, Output, State, html, callback_context, no_update


def register_hover_details_callback(app, df, annotation_desc,
                                    show_map_plot=True, show_time_plot=True):
    hover_inputs = [Input('pca-plot', 'hoverData')]
    input_ids = ['pca-plot']
    if show_map_plot:
        hover_inputs.append(Input('pca-map-plot', 'hoverData'))
        input_ids.append('pca-map-plot')
    if show_time_plot:
        hover_inputs.append(Input('time-histogram', 'hoverData'))
        input_ids.append('time-histogram')

    n_hover = len(input_ids)

    @app.callback(
        Output('hover-details-content', 'children'),
        *hover_inputs,
        State('selected-annotation-columns', 'data'),
        prevent_initial_call=True
    )
    def update_details(*args):
        hover_args   = args[:n_hover]
        selected_cols = args[n_hover]  # from State

        ctx = callback_context
        if not ctx.triggered:
            return no_update

        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        hover_data = None
        for i, pid in enumerate(input_ids):
            if pid == triggered_id:
                hover_data = hover_args[i]
                break

        if not hover_data or not hover_data.get('points'):
            return no_update

        point = hover_data['points'][0]
        hovered_id = point.get('customdata')
        if hovered_id is None:
            return no_update
        if isinstance(hovered_id, list):
            hovered_id = hovered_id[0]
        hovered_id_str = str(hovered_id)
        if hovered_id_str in ('undefined', 'null', 'None', ''):
            return no_update

        mask = df['id'].astype(str) == hovered_id_str
        if not mask.any():
            return no_update

        row = df[mask].iloc[0]

        # Determine columns: use selected_cols if set, else fall back to annotation_desc
        if selected_cols:
            cols = [c for c in selected_cols if c in df.columns and c != 'id']
        elif annotation_desc is not None and 'Abbreviation' in annotation_desc.columns:
            cols = [c for c in annotation_desc['Abbreviation'].dropna()
                    if c in df.columns and c != 'id']
        else:
            cols = [c for c in df.columns if c != 'id']

        th_style = {
            'textAlign': 'left', 'padding': '3px 10px 3px 0',
            'whiteSpace': 'nowrap',
            'color': '#555', 'fontWeight': 'bold', 'verticalAlign': 'top',
            'width': '1px',   # shrink to fit content; td gets the rest
        }
        td_style = {
            'padding': '3px 0',
            'wordBreak': 'break-word', 'verticalAlign': 'top',
            'width': '100%',  # take all remaining space
        }

        rows = [html.Tr([
            html.Th('ID', style={**th_style, 'borderBottom': '1px solid #dee2e6'}),
            html.Td(str(row['id']), style={**td_style, 'borderBottom': '1px solid #dee2e6'})
        ])]
        for col in cols:
            val = row[col]
            if pd.notna(val):
                rows.append(html.Tr([
                    html.Th(col, style=th_style),
                    html.Td(str(val), style=td_style)
                ]))

        return html.Table(
            rows,
            style={'width': '100%', 'borderCollapse': 'collapse', 'tableLayout': 'auto'}
        )
