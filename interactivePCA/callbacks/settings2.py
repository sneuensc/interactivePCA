"""
Callbacks backing the Settings tab's panel show/hide checkboxes and
Equivalent command section (the "settings2-*" ids predate this — they were
built for a since-removed "Settings 2" tab that reorganized the PCA tab's
plotting controls; the controls themselves were moved back to the PCA tab,
but the panel-visibility feature and the command generator were kept and
relocated into the regular Settings tab instead of being deleted with it).
"""

import dash
from dash import Input, Output, State, ctx

from ..components import LAYOUT_CONFIG


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


def _toggle_split(app, pane_a_id, pane_b_id, resizer_id, checkbox_a_ids, checkbox_b_ids, pct_a,
                  extra_style_a=None, extra_style_b=None):
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

    extra_style_a/extra_style_b: style keys that pane must always carry while
    visible, beyond plain flex-sizing — e.g. table-plot-pane's own 'display':
    'flex'/'flexDirection': 'column' (needed to lay out its Tabs + AG Grid
    children, not merely an artifact of some earlier hide/show). Without
    this, visible just meant "no 'display' key at all" for every pane, which
    silently dropped table-plot-pane's own required display:flex and
    collapsed the annotation table to nothing.
    """
    pct_b = 100 - pct_a
    extra_a = extra_style_a or {}
    extra_b = extra_style_b or {}
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
            style_a.update(extra_a)
            style_a['flex'] = f'0 0 {pct_a}%' if b_visible else '1 1 auto'
        else:
            style_a['display'] = 'none'

        if b_visible:
            style_b.pop('display', None)
            style_b.update(extra_b)
            style_b['flex'] = f'0 0 {pct_b}%' if a_visible else '1 1 auto'
        else:
            style_b['display'] = 'none'

        if a_visible and b_visible:
            resizer_style.pop('display', None)
        else:
            resizer_style['display'] = 'none'

        return style_a, style_b, resizer_style


def _register_legend_target(app, show_time_plot, show_map_plot):
    """Decide which ONE active plot currently hosts the group-colour legend,
    by priority PCA > time > map, and keep it in legend-target-store.

    The PCA plot normally shows this legend (see update_pca_plot_structure).
    If it is hidden, there is otherwise nowhere to see which colour means
    which group at all — this relocates it to the next visible plot that can
    show one (update_time_histogram / update_map_plot each check this store
    and only draw the legend when they are the current target), so hiding
    everything but one plot never loses the ability to read the colours.
    """
    show_ids = ['settings2-show-pca']
    targets = ['pca']
    if show_time_plot:
        show_ids.append('settings2-show-time')
        targets.append('time')
    if show_map_plot:
        show_ids.append('settings2-show-map')
        targets.append('map')

    @app.callback(
        Output('legend-target-store', 'data'),
        [Input(cid, 'value') for cid in show_ids],
    )
    def _compute_target(*checks):
        for checked, target in zip(checks, targets):
            if checked:
                return target
        return None  # nothing visible at all — no plot to put a legend on


def _register_command_generator(app, session_args, show_map_plot, show_time_plot):
    """Generate-on-click rather than live: most Settings controls have no
    CLI flag at all (panel visibility, 3D, ...), so an Input wired to every
    one of them would mostly fire for nothing — only the fields in
    live_fields below have a live equivalent control, so those are the only
    values layered onto the launch-time args here.

    Two buttons share this one callback (rather than each getting its own,
    which would need allow_duplicate=True on the shared Output): "full" lists
    every parameter — falling back to its default where nothing overrides it
    — via _compose_argv_full; the plain one only lists what differs from
    default, via _compose_argv, same as the relaunch mechanism itself uses.
    """
    import shlex
    from ..args import create_parser
    from .setup import _compose_argv, _compose_argv_full

    # (component id, CLI dest, live value -> CLI value)
    live_fields = [
        ('dropdown-group', 'group', lambda v: None if v == 'none' else v),
        ('dropdown-group-symbol', 'group_shape', lambda v: None if v == 'none' else v),
        ('dropdown-pc-x', 'pc_x', lambda v: v),
        ('dropdown-pc-y', 'pc_y', lambda v: v),
        ('dropdown-pc-z', 'pc_z', lambda v: v),
        ('pca-3d-toggle', 'pca_3d', lambda v: bool(v and 'enable_3d' in v)),
        ('settings2-legend-mode', 'legend', lambda v: v),
        # hover-detailed-toggle is the positive-sense live control; --hover-minimal
        # is its negated CLI flag (detailed is the default — see _hover_detailed_row).
        ('hover-detailed-toggle', 'hover_minimal', lambda v: not bool(v and 'hover_detailed' in v)),
    ]
    if show_map_plot:
        live_fields += [
            ('dropdown-map-x', 'longitude', lambda v: v),
            ('dropdown-map-y', 'latitude', lambda v: v),
            ('map-type-toggle', 'map_type', lambda v: v),
        ]
    if show_time_plot:
        live_fields += [
            ('time-variable', 'time', lambda v: v),
            ('time-viz-mode', 'time_viz_mode', lambda v: v),
            ('time-group-mode', 'time_group_mode', lambda v: v),
            ('time-bin-size', 'time_bin_size', lambda v: v),
            # Handled specially below (needs the current time-variable too,
            # not just its own value) — the transform here is a placeholder.
            ('time-invert-toggle', '_time_invert_toggle', lambda v: v),
            ('time-rotate-toggle', '_time_rotate_toggle', lambda v: v),
        ]

    def _merge_column_toggle(values, dest, toggled_on, current_col, natural_col, is_full):
        """--time-invert-columns/--time-rotate-columns are sets, but their
        live checkbox only ever speaks for whichever ONE column is currently
        shown — toggling it adds/removes just that column from the
        launch-time set (see data_loader.resolve_column_set), leaving every
        other column's membership as it was at launch.

        natural_col is the single column this set defaults to with no CLI
        override at all (None for time_rotate_columns, which has none). If
        the merged result matches that exactly, it's reset to '' (the
        argparse default) for the plain command, same reasoning as the
        pc_x/longitude/etc. natural-default comparison below — otherwise
        "Generate command" would always list it, defeating "only what the
        user actually changed".
        """
        base_cols = set(
            c.strip() for c in (getattr(session_args, dest, '') or '').split(',') if c.strip()
        )
        if current_col:
            if toggled_on:
                base_cols.add(current_col)
            else:
                base_cols.discard(current_col)
        natural_cols = {natural_col} if natural_col else set()
        if not is_full and base_cols == natural_cols:
            values[dest] = ''
        else:
            values[dest] = ','.join(sorted(base_cols))

    @app.callback(
        Output('settings2-command-output', 'value'),
        Output('settings2-command-modal', 'is_open'),
        Input('settings2-gen-command-btn', 'n_clicks'),
        Input('settings2-gen-command-full-btn', 'n_clicks'),
        [State(cid, 'value') for cid, _, _ in live_fields],
        State('settings2-natural-defaults', 'data'),
        prevent_initial_call=True,
    )
    def _generate(_n_clicks, _n_clicks_full, *rest):
        *live_values, natural_defaults = rest
        natural_defaults = natural_defaults or {}
        is_full = ctx.triggered_id == 'settings2-gen-command-full-btn'
        parser = create_parser()
        values = {a.dest: getattr(session_args, a.dest, None)
                  for a in parser._actions if a.option_strings}
        for (_cid, dest, transform), val in zip(live_fields, live_values):
            values[dest] = transform(val)
        if show_time_plot:
            current_time_col = values.get('time')
            _merge_column_toggle(values, 'time_invert_columns',
                                 bool(values.pop('_time_invert_toggle')), current_time_col,
                                 natural_defaults.get('time_invert_columns_natural'), is_full)
            _merge_column_toggle(values, 'time_rotate_columns',
                                 bool(values.pop('_time_rotate_toggle')), current_time_col,
                                 natural_defaults.get('time_rotate_columns_natural'), is_full)
        if not is_full:
            # pc_x/pc_y/pc_z/longitude/latitude/time/time_bin_size never
            # literally equal the CLI's own argparse default (always None)
            # once resolved to a real column/number — compare against each
            # one's actual natural (no-override) default instead, computed
            # once at render time (layouts/__init__.py's
            # settings2-natural-defaults Store), so "Generate command" only
            # lists what the user genuinely changed from that natural state.
            defaults_by_dest = {a.dest: a.default for a in parser._actions if a.option_strings}
            for dest, natural in natural_defaults.items():
                if dest in values and values[dest] == natural:
                    values[dest] = defaults_by_dest.get(dest)
        compose = _compose_argv_full if is_full else _compose_argv
        argv = compose(values)
        command = 'interactivePCA ' + ' '.join(shlex.quote(str(tok)) for tok in argv)
        return command, True


def register_settings2_callbacks(app, args, show_map_plot=True, show_time_plot=True, show_annotation_table=True):
    """Register the panel show/hide checkboxes' effects (Settings tab) and
    the legend-relocation/command-generator logic they drive.

    A panel that was never loaded (e.g. no --latitude/--longitude resolved)
    has neither a live checkbox nor a pane to toggle — its Settings section
    shows a disabled checkbox instead (see layouts/setup.py:settings_panel),
    so nothing is registered here for it.
    """
    _register_legend_target(app, show_time_plot, show_map_plot)
    _register_command_generator(app, args, show_map_plot, show_time_plot)

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

    # Right pane: map <-> annotation table. table-plot-pane (built by
    # make_tab_panel in layouts/__init__.py) needs 'display: flex' /
    # 'flexDirection: column' to lay out its Tabs + AG Grid — not optional.
    if show_map_plot:
        map_pct = int(LAYOUT_CONFIG['map_table_split'] * 100)
        _toggle_split(
            app, 'map-plot-pane', 'table-plot-pane', 'map-table-resizer',
            ['settings2-show-map'], ['settings2-show-table'], pct_a=map_pct,
            extra_style_b={'display': 'flex', 'flexDirection': 'column'},
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
