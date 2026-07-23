"""
Callbacks for the in-tab file loaders (eigenvec / annotation) and Settings.

These back the loader panels in ``layouts/setup.py``. Each Load/Apply composes a
CLI argument list from the current ``args`` (so already-loaded files are
preserved) overlaid with the relevant panel's fields, and relaunches the process
(``relaunch.schedule_relaunch``). A shared client-side poller reloads the browser
once the new server answers.
"""

import argparse
import logging
import os

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, ALL, ctx, html, no_update

from ..args import create_parser
from ..relaunch import schedule_relaunch, POLLER_JS
from ..layouts.setup import (
    ANNOTATION_DEPENDENT, EIGENVEC_FIELDS, ANNOTATION_FIELDS, settings_arg_names,
)


# ── Small helpers ────────────────────────────────────────────────────────────
def _read_columns(path, whitespace=False):
    sep = r"\s+" if whitespace else "\t"
    return list(pd.read_csv(path, sep=sep, nrows=0).columns)


def _guess(columns, *needles):
    """Case-insensitive best-guess column for a parameter (e.g. 'lat')."""
    lowered = {c.lower(): c for c in columns}
    for needle in needles:
        if needle in lowered:
            return lowered[needle]
    for needle in needles:
        for low, orig in lowered.items():
            if low.startswith(needle):
                return orig
    return None


def _entry_item(label, full_path, kind):
    return dbc.ListGroupItem(
        label, id={'type': 'file-entry', 'path': full_path, 'kind': kind},
        action=True, style={'cursor': 'pointer', 'padding': '0.35rem 0.75rem'},
    )


def _render_dir(path):
    """Return (ListGroup of entries, normalised path) for a directory."""
    path = os.path.abspath(path)
    try:
        names = sorted(os.listdir(path), key=str.lower)
    except OSError as exc:
        return dbc.Alert(f"Cannot open {path}: {exc}", color='danger'), path

    items = []
    if path != os.path.dirname(path):  # not filesystem root → offer parent
        items.append(_entry_item('📁  ..', os.path.dirname(path), 'dir'))
    dirs, files = [], []
    for name in names:
        if name.startswith('.'):
            continue
        full = os.path.join(path, name)
        (dirs if os.path.isdir(full) else files).append((name, full))
    for name, full in dirs:
        items.append(_entry_item(f'📁  {name}', full, 'dir'))
    for name, full in files:
        items.append(_entry_item(f'📄  {name}', full, 'file'))
    return dbc.ListGroup(items, flush=True), path


def _compose_argv(values_by_name):
    """CLI argument list for the values that differ from the parser defaults."""
    parser = create_parser()
    argv = []
    for action in parser._actions:
        if not action.option_strings or action.dest == 'help':
            continue
        val = values_by_name.get(action.dest)
        opt = action.option_strings[0]
        if isinstance(action, argparse._StoreTrueAction) or action.nargs == 0:
            if val:
                argv.append(opt)
            continue
        if val is None or (isinstance(val, str) and val.strip() == ''):
            continue
        if val == action.default:
            continue
        argv.extend([opt, str(val)])
    return argv


def _relaunch_from(args, dom_values, overlay_names):
    """Merge current args + the overlaid DOM fields → argv, and relaunch.

    Returns the port the relaunched server will use (for the reload poller).
    """
    allowed = set(overlay_names)
    merged = {}
    for action in create_parser()._actions:
        if action.option_strings and action.dest != 'help':
            merged[action.dest] = getattr(args, action.dest, None)
    for name, value in dom_values.items():
        if name in allowed:
            merged[name] = value
    # "Selected IDs" is a multi-select list; the CLI wants ";"-joined IDs.
    selected = merged.get('selectedID')
    if isinstance(selected, list):
        merged['selectedID'] = ';'.join(map(str, selected)) if selected else None

    port = merged.get('server_port') or getattr(args, 'server_port', 8050)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = getattr(args, 'server_port', 8050)

    schedule_relaunch(_compose_argv(merged))
    return port


def _starting_alert():
    return dbc.Alert(
        [dbc.Spinner(size='sm'),
         html.Span('  Starting… this page will reload automatically.')],
        color='info',
    )


def register_setup_callbacks(app, args, show_eigenvec_loader, show_annotation_loader):
    """Register the loader/settings callbacks that are relevant for this state."""
    show_browse = show_eigenvec_loader or show_annotation_loader

    # ── File-browser modal ───────────────────────────────────────────────────
    # Inputs/outputs are built for the loaders actually shown: a literal Input on
    # a missing Browse button would silently break the whole callback.
    if show_browse:
        targets = ([n for n, s in (('eigenvec', show_eigenvec_loader),
                                    ('annotation', show_annotation_loader)) if s])

        open_inputs = [Input('file-modal-cancel', 'n_clicks')]
        if show_eigenvec_loader:
            open_inputs.append(Input('browse-eigenvec', 'n_clicks'))
        if show_annotation_loader:
            open_inputs.append(Input('browse-annotation', 'n_clicks'))
        open_states = [State({'type': 'setup-arg', 'name': n}, 'value') for n in targets]

        @app.callback(
            Output('file-modal', 'is_open'),
            Output('file-browser', 'data'),
            Output('file-modal-list', 'children'),
            Output('file-modal-cwd', 'children'),
            *open_inputs,
            *open_states,
            prevent_initial_call=True,
        )
        def open_modal(*vals):
            if ctx.triggered_id == 'file-modal-cancel':
                return False, no_update, no_update, no_update
            target = 'eigenvec' if ctx.triggered_id == 'browse-eigenvec' else 'annotation'
            state_vals = dict(zip(targets, vals[len(open_inputs):]))
            current = state_vals.get(target)
            start = os.path.dirname(os.path.abspath(current)) if current else os.getcwd()
            if not os.path.isdir(start):
                start = os.getcwd()
            listing, cwd = _render_dir(start)
            return True, {'target': target, 'cwd': cwd}, listing, cwd

        entry_value_outputs = [Output({'type': 'setup-arg', 'name': n}, 'value',
                                       allow_duplicate=True) for n in targets]

        @app.callback(
            Output('file-modal-list', 'children', allow_duplicate=True),
            Output('file-modal-cwd', 'children', allow_duplicate=True),
            Output('file-modal', 'is_open', allow_duplicate=True),
            Output('file-browser', 'data', allow_duplicate=True),
            *entry_value_outputs,
            Input({'type': 'file-entry', 'path': ALL, 'kind': ALL}, 'n_clicks'),
            State('file-browser', 'data'),
            prevent_initial_call=True,
        )
        def on_entry(_clicks, data):
            n_extra = len(targets)
            entry = ctx.triggered_id
            triggered = ctx.triggered[0] if ctx.triggered else None
            if not entry or not triggered or not triggered.get('value'):
                return (no_update,) * (4 + n_extra)
            if entry['kind'] == 'dir':
                listing, cwd = _render_dir(entry['path'])
                return (listing, cwd, no_update, {**(data or {}), 'cwd': cwd}) \
                    + (no_update,) * n_extra
            target = (data or {}).get('target', 'eigenvec')
            values = tuple(entry['path'] if n == target else no_update for n in targets)
            return (no_update, no_update, False, no_update) + values

    # ── Eigenvec loader (PCA tab) ────────────────────────────────────────────
    if show_eigenvec_loader:
        @app.callback(
            Output({'type': 'setup-arg', 'name': 'eigenvecID'}, 'options'),
            Output({'type': 'setup-arg', 'name': 'eigenvecID'}, 'value'),
            Output('eigenvec-read-status', 'children'),
            Input('read-eigenvec-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': 'eigenvec'}, 'value'),
            prevent_initial_call=True,
        )
        def read_eigenvec(_n, path):
            if not path or not str(path).strip():
                return no_update, no_update, dbc.Alert('Enter the eigenvec file path.',
                                                       color='warning')
            if not os.path.isfile(path):
                return no_update, no_update, dbc.Alert(f"File not found: {path}",
                                                       color='danger')
            try:
                df = pd.read_csv(path, sep=r"\s+", nrows=None)
                cols = list(df.columns)
                n_samples = len(df)
            except Exception as exc:  # noqa: BLE001
                return no_update, no_update, dbc.Alert(f"Could not read: {exc}",
                                                       color='danger')
            options = [{'label': c, 'value': c} for c in cols]
            first = cols[0] if cols else None
            return options, first, dbc.Alert(
                f"Read {len(cols)} columns, {n_samples} samples.", color='success')

        @app.callback(
            Output({'type': 'setup-arg', 'name': 'selectedID'}, 'options'),
            Input({'type': 'setup-arg', 'name': 'eigenvecID'}, 'value'),
            State({'type': 'setup-arg', 'name': 'eigenvec'}, 'value'),
            prevent_initial_call=True,
        )
        def refresh_selected_ids(id_col, path):
            if not id_col or not path or not os.path.isfile(path):
                return no_update
            try:
                values = pd.read_csv(path, sep=r"\s+", usecols=[id_col])[id_col]
            except Exception as exc:  # noqa: BLE001
                logging.warning("Could not read sample IDs: %s", exc)
                return no_update
            seen, unique = set(), []
            for value in values.astype(str):
                if value not in seen:
                    seen.add(value)
                    unique.append(value)
            return [{'label': v, 'value': v} for v in unique]

        @app.callback(
            Output('relaunch-store', 'data', allow_duplicate=True),
            Output('pca-load-status', 'children'),
            Input('pca-load-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': ALL}, 'value'),
            State({'type': 'setup-arg', 'name': ALL}, 'id'),
            prevent_initial_call=True,
        )
        def pca_load(_n, values, ids):
            dom = {i['name']: v for i, v in zip(ids, values)}
            eigenvec = dom.get('eigenvec')
            if not eigenvec or not str(eigenvec).strip():
                return no_update, dbc.Alert('The eigenvec file is required.', color='danger')
            if not os.path.isfile(eigenvec):
                return no_update, dbc.Alert(f"Eigenvec file not found: {eigenvec}",
                                            color='danger')
            port = _relaunch_from(args, dom, EIGENVEC_FIELDS + settings_arg_names())
            return {'go': True, 'port': port}, _starting_alert()

    # ── Annotation loader (Annotation tab) ───────────────────────────────────
    if show_annotation_loader:
        @app.callback(
            [Output({'type': 'setup-arg', 'name': c}, 'options') for c in ANNOTATION_DEPENDENT]
            + [Output({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT]
            + [Output('annotation-read-status', 'children')],
            Input('read-annotation-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': 'annotation'}, 'value'),
            [State({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT],
            prevent_initial_call=True,
        )
        def read_annotation(_n, path, *current):
            n = len(ANNOTATION_DEPENDENT)
            if not path or not str(path).strip():
                msg = dbc.Alert('Enter the annotation file path.', color='warning')
                return [no_update] * (2 * n) + [msg]
            if not os.path.isfile(path):
                msg = dbc.Alert(f"File not found: {path}", color='danger')
                return [no_update] * (2 * n) + [msg]
            try:
                df = pd.read_csv(path, sep='\t', nrows=None)
                cols = list(df.columns)
                n_samples = len(df)
            except Exception as exc:  # noqa: BLE001
                msg = dbc.Alert(f"Could not read: {exc}", color='danger')
                return [no_update] * (2 * n) + [msg]
            options = [{'label': c, 'value': c} for c in cols]
            guesses = {
                'annotationID': _guess(cols, 'genetic id', 'id', 'sample', 'iid'),
                'latitude': _guess(cols, 'lat', 'latitude'),
                'longitude': _guess(cols, 'long', 'lon', 'longitude'),
                'time': _guess(cols, 'date', 'time', 'age', 'year'),
                'group': _guess(cols, 'group', 'region', 'population', 'pop'),
            }
            values = [cur if cur in cols else guesses.get(dest)
                      for dest, cur in zip(ANNOTATION_DEPENDENT, current)]
            msg = dbc.Alert(f"Read {len(cols)} columns, {n_samples} samples.", color='success')
            return [options] * n + values + [msg]

        @app.callback(
            Output('relaunch-store', 'data', allow_duplicate=True),
            Output('annotation-load-status', 'children'),
            Input('annotation-load-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': ALL}, 'value'),
            State({'type': 'setup-arg', 'name': ALL}, 'id'),
            prevent_initial_call=True,
        )
        def annotation_load(_n, values, ids):
            dom = {i['name']: v for i, v in zip(ids, values)}
            # Eigenvec must already be loaded (this loader lives in the running app).
            if not getattr(args, 'eigenvec', None):
                return no_update, dbc.Alert('Load the eigenvec first (PCA tab).',
                                            color='warning')
            annotation = dom.get('annotation')
            if not annotation or not str(annotation).strip():
                return no_update, dbc.Alert('The annotation file is required.',
                                            color='danger')
            if not os.path.isfile(annotation):
                return no_update, dbc.Alert(f"Annotation file not found: {annotation}",
                                            color='danger')
            port = _relaunch_from(args, dom, ANNOTATION_FIELDS + settings_arg_names())
            return {'go': True, 'port': port}, _starting_alert()

    # ── Settings (always) ────────────────────────────────────────────────────
    @app.callback(
        Output('relaunch-store', 'data', allow_duplicate=True),
        Output('settings-status', 'children'),
        Input('settings-apply-btn', 'n_clicks'),
        State({'type': 'setup-arg', 'name': ALL}, 'value'),
        State({'type': 'setup-arg', 'name': ALL}, 'id'),
        prevent_initial_call=True,
    )
    def settings_apply(_n, values, ids):
        dom = {i['name']: v for i, v in zip(ids, values)}
        port = _relaunch_from(args, dom, settings_arg_names())
        return {'go': True, 'port': port}, _starting_alert()

    # ── Reload poller (always) ───────────────────────────────────────────────
    app.clientside_callback(
        POLLER_JS,
        Output('relaunch-poll-dummy', 'data-poll'),
        Input('relaunch-store', 'data'),
        prevent_initial_call=True,
    )
