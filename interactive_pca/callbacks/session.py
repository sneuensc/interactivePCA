"""
Save/restore the current session — the full CLI args (eigenvec, annotation,
every setting) plus the "view" (selection, grouping, aesthetics, PCA axes,
map, time-plot settings, table filter, plot zoom, pane sizes) — as a single
JSON file. --session <file> (or the eigenvec tab's "Load session" button,
see callbacks/setup.py:load_session_direct) reopens showing exactly that, no
other field needed: args.py:_merge_session_args fills in any CLI arg not
explicitly passed on that command line from the file's embedded 'args'.

Not restored: a couple of fields that another callback auto-derives from one
of these (pca-legend-toggle from dropdown-group, time-invert-toggle and the
time-window's own bounds from time-variable) — setting them here would just
race that callback and lose. They re-derive sensible values on their own once
the driving field above them is restored.

Plot zoom/pan and pane sizes live outside this module's Output-list mechanism:
they're plain DOM/Plotly state with no Dash prop that would "just" re-apply
them, so restoring those two is done by a clientside callback further down
that calls Plotly.relayout() and sets pane flex-basis directly — see
apply_saved_session (the props this module CAN restore this way) vs.
_register_view_restore_clientside (the two it can't).
"""

import json
import logging
from datetime import datetime

import dash
from dash import Input, Output, State

from ..args import _SESSION_ARGS_EXCLUDE


def _session_filename():
    """A fresh, timestamped name for every save, so successive saves don't
    silently overwrite each other and it's clear which snapshot is which."""
    return f'session_{datetime.now():%Y%m%d_%H%M%S}.json'


def _session_fields(show_map_plot, show_time_plot, show_annotation_table):
    """(component_id, prop, session_key) triples for every plain-prop field
    the session file covers — shared by the save and restore callbacks so
    they can never drift out of sync with each other."""
    fields = [
        ('selection-store', 'data', 'selection'),
        ('dropdown-group', 'value', 'group'),
        ('dropdown-group-symbol', 'value', 'group_symbol'),
        ('hover-detailed-toggle', 'value', 'hover_detailed'),
        ('marker-aesthetics-store', 'data', 'marker_aesthetics'),
        ('symbol-aesthetics-store', 'data', 'symbol_aesthetics'),
        ('hidden-groups-store', 'data', 'hidden_groups'),
        ('dropdown-pc-x', 'value', 'pc_x'),
        ('dropdown-pc-y', 'value', 'pc_y'),
        ('dropdown-pc-z', 'value', 'pc_z'),
        ('pca-3d-toggle', 'value', 'is_3d'),
    ]
    if show_map_plot:
        fields += [
            ('map-type-toggle', 'value', 'map_type'),
            ('map-view-store', 'data', 'map_view'),
        ]
    if show_time_plot:
        fields += [
            ('time-variable', 'value', 'time_variable'),
            ('time-viz-mode', 'value', 'time_viz_mode'),
            ('time-per-group-toggle', 'value', 'time_per_group'),
            ('time-window-enabled', 'value', 'time_window_enabled'),
        ]
    if show_annotation_table:
        fields += [
            ('selected-annotation-columns', 'data', 'selected_annotation_columns'),
            ('pca-filter-query', 'value', 'filter_query'),
        ]
    return fields


def _view_fields(show_time_plot):
    """(component_id, prop, session_key) triples for the plot-zoom/pane-size
    fields — save-side only (State), restored via Plotly.relayout()/direct
    flex-basis instead of a plain Output, see _register_view_restore_clientside."""
    fields = [('pca-view-store', 'data', 'pca_view')]
    if show_time_plot:
        fields.append(('time-view-store', 'data', 'time_view'))
    fields.append(('pane-sizes-store', 'data', 'pane_sizes'))
    return fields


def _register_view_capture(app, show_time_plot):
    """Mirror the map's own view-tracking store (already fed by relayoutData)
    for the PCA and time plots: just remember the latest relayoutData verbatim
    — Plotly.relayout() accepts that exact flat-key shape back, so no
    transform is needed to reapply it on restore."""
    @app.callback(
        Output('pca-view-store', 'data'),
        Input('pca-plot', 'relayoutData'),
        prevent_initial_call=True,
    )
    def capture_pca_view(relayout_data):
        return relayout_data

    if show_time_plot:
        @app.callback(
            Output('time-view-store', 'data'),
            Input('time-histogram', 'relayoutData'),
            prevent_initial_call=True,
        )
        def capture_time_view(relayout_data):
            return relayout_data


def _register_view_restore_clientside(app):
    """Re-apply pca_view/time_view (Plotly zoom/pan/camera) and pane_sizes
    (draggable pane flex-basis) from a restored session — see the module
    docstring for why these two can't go through apply_saved_session."""
    app.clientside_callback(
        """
        function(sessionData) {
            if (!sessionData) { return window.dash_clientside.no_update; }
            try {
                var sizes = sessionData.pane_sizes || {};
                Object.keys(sizes).forEach(function(resizerId) {
                    var resizer = document.getElementById(resizerId);
                    if (!resizer) return;
                    var container = resizer.parentElement;
                    var children = Array.from(container.children);
                    var idx = children.indexOf(resizer);
                    if (idx <= 0 || idx >= children.length - 1) return;
                    var beforePercent = sizes[resizerId];
                    children[idx - 1].style.flex = '0 0 ' + beforePercent + '%';
                    children[idx + 1].style.flex = '0 0 ' + (100 - beforePercent) + '%';
                });
            } catch (e) {}
            // Panes may still be resizing/graphs still mounting right after
            // load — give the DOM a moment before touching Plotly's zoom.
            setTimeout(function() {
                try {
                    if (sessionData.pca_view && window.Plotly &&
                            document.getElementById('pca-plot')) {
                        Plotly.relayout('pca-plot', sessionData.pca_view);
                    }
                    if (sessionData.time_view && window.Plotly &&
                            document.getElementById('time-histogram')) {
                        Plotly.relayout('time-histogram', sessionData.time_view);
                    }
                } catch (e) {}
            }, 400);
            return window.dash_clientside.no_update;
        }
        """,
        Output('session-restore-dummy', 'data'),
        Input('session-init-store', 'data'),
        prevent_initial_call='initial_duplicate',
    )


def register_session_callbacks(app, args, show_map_plot=True, show_time_plot=True,
                               show_annotation_table=True):
    fields = _session_fields(show_map_plot, show_time_plot, show_annotation_table)
    view_fields = _view_fields(show_time_plot)
    all_fields = fields + view_fields

    # Fixed for this process's lifetime (it's whatever this server was
    # launched with) — captured once rather than re-read on every save.
    saved_args = {k: v for k, v in vars(args).items() if k not in _SESSION_ARGS_EXCLUDE}

    _register_view_capture(app, show_time_plot)
    _register_view_restore_clientside(app)

    @app.callback(
        Output('download-session', 'data'),
        Input('save-view-btn', 'n_clicks'),
        [State(comp_id, prop) for comp_id, prop, _ in all_fields],
        prevent_initial_call=True,
    )
    def save_view(n_clicks, *values):
        """Dump the current session (full CLI args + view) to a timestamped
        file server-side (for --session / the eigenvec tab's "Load session"
        — both need a server-visible path) and also hand it to the browser
        as a download, so the user can save/move/share a copy from there."""
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        session_data = {key: value for (_, _, key), value in zip(all_fields, values)}
        session_data['args'] = saved_args
        json_str = json.dumps(session_data, indent=2)
        filename = _session_filename()
        with open(filename, 'w') as f:
            f.write(json_str)
        logging.info(f"Saved current session to {filename}")
        return dict(content=json_str, filename=filename)

    @app.callback(
        [Output(comp_id, prop, allow_duplicate=True) for comp_id, prop, _ in fields],
        Input('session-init-store', 'data'),
        prevent_initial_call='initial_duplicate',
    )
    def apply_saved_session(session_data):
        """Apply a --session file's saved values once, right after page load."""
        if not session_data:
            raise dash.exceptions.PreventUpdate
        return tuple(
            session_data[key] if key in session_data else dash.no_update
            for _, _, key in fields
        )
