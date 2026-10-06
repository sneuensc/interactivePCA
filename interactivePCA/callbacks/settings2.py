"""
Callbacks for the experimental "Settings 2" tab: per-panel show/hide toggles
and axis pickers that act live on the running app (no relaunch), mirroring
and staying in sync with the equivalent controls already in the PCA tab.

Each axis dropdown pair (e.g. 'dropdown-pc-x' in the PCA tab and
'settings2-pc-x' here) is kept in sync by a single callback that takes BOTH
as Input and Output: whichever one changed is pushed onto the other, and the
one that triggered the callback is left as dash.no_update. A pair of
separate callbacks (one per direction) would form a circular dependency that
Dash refuses to register; one callback covering both directions does not,
since Dash only disallows cycles across distinct callbacks.
"""

import dash
from dash import Input, Output, State, ctx

from ..components import LAYOUT_CONFIG


def _sync_pair(app, live_id, mirror_id):
    """Register the live_id <-> mirror_id value-sync callback described above."""
    @app.callback(
        Output(live_id, 'value', allow_duplicate=True),
        Output(mirror_id, 'value', allow_duplicate=True),
        Input(live_id, 'value'),
        Input(mirror_id, 'value'),
        prevent_initial_call=True,
    )
    def _sync(live_val, mirror_val):
        if ctx.triggered_id == live_id:
            return dash.no_update, live_val
        return mirror_val, dash.no_update


def _toggle_visibility(app, checkbox_id, pane_id):
    """Show/hide an existing panel's wrapper div without touching its own
    layout-sizing style keys — only used when the panel has no sibling to
    redistribute space to (see register_settings2_callbacks).
    """
    @app.callback(
        Output(pane_id, 'style'),
        Input(checkbox_id, 'value'),
        State(pane_id, 'style'),
    )
    def _toggle(checked, style):
        style = dict(style or {})
        if checked:
            style.pop('display', None)
        else:
            style['display'] = 'none'
        return style


def _toggle_split(app, pane_a_id, pane_b_id, resizer_id, checkbox_a_ids, checkbox_b_ids, pct_a):
    """Keep a two-pane resizable split (and the drag-resizer between them) in
    sync with which side(s) currently have anything visible — per their own
    group of show/hide checkboxes (a side with more than one checkbox is
    non-empty as long as ANY of them is checked).

    When both sides have something visible, each pane gets back its normal
    pct_a / (100 - pct_a) flex-basis split and the resizer reappears. When
    only one side does, that side grows to fill the whole container (flex:
    1 1 auto) and the empty side + the resizer hide — a divider has nothing
    left to divide, and the lone visible plot should use the full space
    rather than stay capped at its old percentage. A hide/show cycle does
    not remember a mid-drag split (dragging needs the resizer itself, which
    is hidden exactly when a side is empty) — it resets to the layout's
    default pct_a split, which is an acceptable simplification here.
    """
    pct_b = 100 - pct_a
    all_ids = list(checkbox_a_ids) + list(checkbox_b_ids)
    n_a = len(checkbox_a_ids)

    @app.callback(
        Output(pane_a_id, 'style'),
        Output(pane_b_id, 'style'),
        Output(resizer_id, 'style'),
        [Input(cid, 'value') for cid in all_ids],
        State(pane_a_id, 'style'),
        State(pane_b_id, 'style'),
        State(resizer_id, 'style'),
    )
    def _toggle(*args):
        checks = args[:len(all_ids)]
        style_a, style_b, resizer_style = (dict(s or {}) for s in args[len(all_ids):])
        a_visible = any(checks[:n_a])
        b_visible = any(checks[n_a:])

        if a_visible:
            style_a.pop('display', None)
            style_a['flex'] = f'0 0 {pct_a}%' if b_visible else '1 1 auto'
        else:
            style_a['display'] = 'none'

        if b_visible:
            style_b.pop('display', None)
            style_b['flex'] = f'0 0 {pct_b}%' if a_visible else '1 1 auto'
        else:
            style_b['display'] = 'none'

        if a_visible and b_visible:
            resizer_style.pop('display', None)
        else:
            resizer_style['display'] = 'none'

        return style_a, style_b, resizer_style


def register_settings2_callbacks(app, show_map_plot=True, show_time_plot=True, show_annotation_table=True):
    """Register the Settings 2 tab's sync/visibility callbacks.

    A panel that was never loaded (e.g. no --latitude/--longitude resolved)
    has neither a live control nor a pane to toggle — its Settings 2 section
    shows a disabled checkbox and an explanatory note instead (see
    layouts/__init__.py:create_settings2_tab), so nothing is registered here
    for it.
    """
    _sync_pair(app, 'dropdown-pc-x', 'settings2-pc-x')
    _sync_pair(app, 'dropdown-pc-y', 'settings2-pc-y')
    _sync_pair(app, 'dropdown-pc-z', 'settings2-pc-z')

    # Lat/lon columns have no equivalent live picker in the PCA tab itself
    # (the map has never had a column-swap control) — settings2-map-lat/-lon
    # just feed straight into update_map_plot (callbacks/plots.py) as a new
    # Input, so there is nothing to sync here.

    if show_time_plot:
        _sync_pair(app, 'time-variable', 'settings2-time-var')

    # Left pane: PCA plot <-> time plot.
    if show_time_plot:
        pca_pct = int(LAYOUT_CONFIG['pca_time_split'] * 100)
        _toggle_split(
            app, 'pca-plot-pane', 'time-plot-pane', 'pca-time-resizer',
            ['settings2-show-pca'], ['settings2-show-time'], pct_a=pca_pct,
        )
    else:
        # No time plot at all (no annotation loaded) — PCA is the only thing
        # in the left pane, so there's no sibling to redistribute space to.
        _toggle_visibility(app, 'settings2-show-pca', 'pca-plot-pane')

    # Right pane: map <-> annotation table.
    if show_map_plot:
        map_pct = int(LAYOUT_CONFIG['map_table_split'] * 100)
        _toggle_split(
            app, 'map-plot-pane', 'table-plot-pane', 'map-table-resizer',
            ['settings2-show-map'], ['settings2-show-table'], pct_a=map_pct,
        )

    # Whole left pane (PCA + time) <-> whole right pane (map + table). Only
    # exists at all when the right pane does (show_annotation_table), same as
    # layouts/__init__.py.
    if show_annotation_table:
        _toggle_split(
            app, 'pca-left-pane', 'pca-right-pane', 'pca-vertical-resizer',
            ['settings2-show-pca', 'settings2-show-time'],
            ['settings2-show-map', 'settings2-show-table'],
            pct_a=50,
        )
