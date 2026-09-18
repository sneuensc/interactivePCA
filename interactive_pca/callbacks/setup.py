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
from ..data_loader import auto_detect_dimensions, detect_eigenvec_sep, find_incrementing_prefix_series
from ..relaunch import schedule_relaunch, POLLER_JS
from ..layouts.setup import (
    ANNOTATION_DEPENDENT, EIGENVEC_FIELDS, ANNOTATION_FIELDS,
    settings_arg_names, all_arg_names,
)


# The loader panels' fields live under 'setup-arg'; the Settings tab mirrors
# every parameter under 'settings-arg'. A Load button takes its own panel's
# fields from the former and the remaining options from the latter.
_SETTINGS_STATE = (State({'type': 'settings-arg', 'name': ALL}, 'value'),
                   State({'type': 'settings-arg', 'name': ALL}, 'id'))


def _dom(values, ids):
    return {i['name']: v for i, v in zip(ids, values)}


# ── Small helpers ────────────────────────────────────────────────────────────
def _read_columns(path, whitespace=False):
    sep = r"\s+" if whitespace else "\t"
    return list(pd.read_csv(path, sep=sep, nrows=0).columns)


def _guess(columns, *needles):
    """Case-insensitive best-guess column for a parameter (e.g. 'lat') — only an
    exact name match (a column literally called "lat" or "Lat"), never a loose
    substring/prefix match. A prefix match risks guessing the wrong column
    (e.g. "latency" for 'lat', "timeout" for 'time') with no obvious way for
    the user to notice — better to leave it empty for them to pick than guess
    wrong silently.
    """
    lowered = {c.lower(): c for c in columns}
    for needle in needles:
        if needle in lowered:
            return lowered[needle]
    return None


def _guess_annotation_dependent(columns):
    """Best-guess latitude/longitude/time/group/annotationID from column
    names — shared by every place that reads a set of annotation columns
    (a separate file, or the eigenvec's own embedded ones).
    """
    return {
        'annotationID': _guess(columns, 'genetic id', 'id', 'sample', 'iid'),
        'latitude': _guess(columns, 'lat', 'latitude'),
        'longitude': _guess(columns, 'long', 'lon', 'longitude'),
        'time': _guess(columns, 'date', 'time', 'age', 'year'),
        'group': _guess(columns, 'group', 'region', 'population', 'pop'),
    }


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

    # Load/Apply always move forward out of the loader shell. Only the
    # header's Restart button (app.py:_restart) composes --setup deliberately;
    # without this, a process already running with --setup (e.g. after a
    # Restart) would carry it into every subsequent relaunch here and the app
    # would bounce straight back to the loader after every Load/Apply.
    merged['setup'] = False

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


def register_setup_callbacks(app, args, show_eigenvec_loader, show_annotation_loader,
                            show_embedded_annotation_button=False):
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
            Output({'type': 'setup-arg', 'name': 'dim'}, 'value'),
            Output('eigenvec-read-status', 'children'),
            Output('eigenvec-details', 'style'),
            Output('embedded-annotation-section', 'style'),
            Input('read-eigenvec-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': 'eigenvec'}, 'value'),
            prevent_initial_call=True,
        )
        def read_eigenvec(_n, path):
            import re
            from ..data_loader import auto_detect_dimensions

            if not path or not str(path).strip():
                return no_update, no_update, no_update, dbc.Alert(
                    'Enter the eigenvec file path.', color='warning'), no_update, no_update
            if not os.path.isfile(path):
                return no_update, no_update, no_update, dbc.Alert(
                    f"File not found: {path}", color='danger'), no_update, no_update
            try:
                df = pd.read_csv(path, sep=detect_eigenvec_sep(path), nrows=None)
                cols = list(df.columns)
                n_samples = len(df)
            except Exception as exc:  # noqa: BLE001
                return no_update, no_update, no_update, dbc.Alert(
                    f"Could not read: {exc}", color='danger'), no_update, no_update

            # Auto-detect dimensions from all columns (don't exclude any initially)
            # Find all columns matching PREFIX+number pattern
            prefix_groups = {}
            for col in cols:
                match = re.match(r'^([a-zA-Z]+)(\d+)$', col)
                if match:
                    prefix = match.group(1)
                    number = int(match.group(2))
                    if prefix not in prefix_groups:
                        prefix_groups[prefix] = []
                    prefix_groups[prefix].append((number, col))

            # Find the prefix with most consecutive numbers starting from 1
            best_prefix = None
            guessed_dims = []
            for prefix, number_cols in prefix_groups.items():
                number_cols.sort()
                numbers = [n for n, _ in number_cols]
                if numbers and numbers[0] == 1 and numbers == list(range(1, len(numbers) + 1)):
                    if len(number_cols) > len(guessed_dims):
                        best_prefix = prefix
                        guessed_dims = [col for _, col in number_cols]

            # Determine ID column based on where dimensions start
            if guessed_dims:
                first_dim_idx = cols.index(guessed_dims[0])
                if first_dim_idx == 1:
                    # Dimensions start in column 2 (index 1), so column 1 (index 0) is ID
                    id_col = cols[0]
                elif first_dim_idx == 0:
                    # Dimensions start in column 1 (index 0), so ID is first column after dims
                    last_dim_idx = cols.index(guessed_dims[-1])
                    id_col = cols[last_dim_idx + 1] if last_dim_idx + 1 < len(cols) else cols[0]
                else:
                    # Dimensions start later, assume first column is ID
                    id_col = cols[0]
            else:
                # No dimensions detected, use first column as ID
                id_col = cols[0]

            # Count annotation columns (all columns that aren't ID or dimensions)
            dim_set = set(guessed_dims)
            annotation_cols = [c for c in cols if c != id_col and c not in dim_set]
            n_annotations = len(annotation_cols)

            # Populate dim field only if there are annotations, otherwise leave empty
            dim_value = ','.join(guessed_dims) if n_annotations > 0 else None

            # Build status message
            status_parts = [f"Read {len(cols)} columns, {n_samples} samples."]
            status_parts.append(f"Guessed {len(guessed_dims)} dimensions, {n_annotations} annotations.")
            if n_annotations > 0:
                status_parts.append("Loading here gives you coordinates only — use the "
                                    "Annotation tab afterwards to load these as annotation.")
            status_msg = ' '.join(status_parts)

            options = [{'label': c, 'value': c} for c in cols]
            return (options, id_col, dim_value,
                    dbc.Alert(status_msg, color='success'), {},
                    {} if n_annotations > 0 else {'display': 'none'})

        @app.callback(
            Output({'type': 'setup-arg', 'name': 'selectedID'}, 'options'),
            Output({'type': 'setup-arg', 'name': 'selectedID'}, 'placeholder'),
            Input({'type': 'setup-arg', 'name': 'eigenvecID'}, 'value'),
            State({'type': 'setup-arg', 'name': 'eigenvec'}, 'value'),
            prevent_initial_call=True,
        )
        def refresh_selected_ids(id_col, path):
            if not id_col or not path or not os.path.isfile(path):
                return no_update, no_update
            try:
                values = pd.read_csv(path, sep=detect_eigenvec_sep(path), usecols=[id_col])[id_col]
            except Exception as exc:  # noqa: BLE001
                logging.warning("Could not read sample IDs: %s", exc)
                return no_update, no_update
            seen, unique = set(), []
            for value in values.astype(str):
                if value not in seen:
                    seen.add(value)
                    unique.append(value)
            return [{'label': v, 'value': v} for v in unique], 'all samples'

        @app.callback(
            Output('relaunch-store', 'data', allow_duplicate=True),
            Output('pca-load-status', 'children'),
            Input('pca-load-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': ALL}, 'value'),
            State({'type': 'setup-arg', 'name': ALL}, 'id'),
            *_SETTINGS_STATE,
            prevent_initial_call=True,
        )
        def pca_load(_n, values, ids, set_values, set_ids):
            dom = {**_dom(set_values, set_ids), **_dom(values, ids)}
            eigenvec = dom.get('eigenvec')
            if not eigenvec or not str(eigenvec).strip():
                return no_update, dbc.Alert('The eigenvec file is required.', color='danger')
            if not os.path.isfile(eigenvec):
                return no_update, dbc.Alert(f"Eigenvec file not found: {eigenvec}",
                                            color='danger')
            # Coordinates only — any extra columns in the file are left for the
            # Annotation tab to load explicitly (with lat/long/time chosen there).
            dom['ignore_embedded_annotation'] = True
            overlay = EIGENVEC_FIELDS + settings_arg_names() + ['ignore_embedded_annotation']
            port = _relaunch_from(args, dom, overlay)
            return {'go': True, 'port': port}, _starting_alert()

    # ── Annotation loader (Annotation tab) ───────────────────────────────────
    if show_annotation_loader:
        def _read_annotation_columns(path, current):
            """Shared by the 'extra file' and 'combine' buttons: validate + read
            the annotation file, guess lat/long/time/etc. Returns either
            ('error', alert) or ('ok', options_per_field, values, cols, n_samples)
            — callers build their own summary message from cols/n_samples since
            what counts as "duplicated" differs by mode.
            """
            n = len(ANNOTATION_DEPENDENT)
            if not path or not str(path).strip():
                return 'error', dbc.Alert('Enter the annotation file path.', color='warning')
            if not os.path.isfile(path):
                return 'error', dbc.Alert(f"File not found: {path}", color='danger')
            try:
                df = pd.read_csv(path, sep='\t', nrows=None)
                cols = list(df.columns)
                n_samples = len(df)
            except Exception as exc:  # noqa: BLE001
                return 'error', dbc.Alert(f"Could not read: {exc}", color='danger')
            options = [{'label': c, 'value': c} for c in cols]
            guesses = _guess_annotation_dependent(cols)
            values = [cur if cur in cols else guesses.get(dest)
                      for dest, cur in zip(ANNOTATION_DEPENDENT, current)]
            return 'ok', [options] * n, values, cols, n_samples

        def _summary_alert(n_eigenvec, n_annotation, n_duplicate, n_samples=None):
            """The 'x from eigenvec file, y from annotation file, n duplicated
            columns' summary shown after any of the three buttons succeeds.
            """
            parts = [f"{n_eigenvec} column(s) from the eigenvec file",
                    f"{n_annotation} from the annotation file"]
            if n_samples is not None:
                parts[-1] += f" ({n_samples} samples)"
            parts.append(f"{n_duplicate} duplicate(s)"
                        + (" skipped (kept from the annotation file)" if n_duplicate else ""))
            return dbc.Alert(', '.join(parts) + '.', color='success')

        # Without any chance of embedded annotation columns (the eigenvec is
        # loaded and confirmed to have none), the panel falls back to the
        # original plain flow: a single "Read" button, no mode buttons.
        # Otherwise the three buttons (rendered by annotation_loader_panel)
        # double as both the mode choice and the "Read" step.
        if show_embedded_annotation_button:
            @app.callback(
                [Output({'type': 'setup-arg', 'name': c}, 'options', allow_duplicate=True)
                 for c in ANNOTATION_DEPENDENT]
                + [Output({'type': 'setup-arg', 'name': c}, 'value', allow_duplicate=True)
                   for c in ANNOTATION_DEPENDENT]
                + [Output('embedded-annotation-status', 'children', allow_duplicate=True),
                   Output('annotation-details', 'style', allow_duplicate=True),
                   Output('annotation-source-store', 'data', allow_duplicate=True),
                   Output('annotationid-row', 'style', allow_duplicate=True)],
                Input('use-file-annotation-btn', 'n_clicks'),
                State({'type': 'setup-arg', 'name': 'annotation'}, 'value'),
                [State({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT],
                prevent_initial_call=True,
            )
            def choose_file_annotation(_n, path, *current):
                n = len(ANNOTATION_DEPENDENT)
                status, *rest = _read_annotation_columns(path, current)
                if status == 'error':
                    return [no_update] * (2 * n) + [rest[0], no_update, no_update, no_update]
                options, values, cols, n_samples = rest
                msg = _summary_alert(0, len(cols), 0, n_samples)
                return options + values + [msg, {}, 'file', {}]

            def _detect_embedded_columns(eigenvec_path, dim_value, id_value):
                """Columns in the eigenvec file that aren't the ID or dimension columns."""
                df = pd.read_csv(eigenvec_path, sep=detect_eigenvec_sep(eigenvec_path), nrows=None)
                cols = list(df.columns)
                id_col = id_value if id_value in cols else cols[0]
                if dim_value and str(dim_value).strip():
                    dims = [c.strip() for c in str(dim_value).split(',') if c.strip()]
                else:
                    dims = auto_detect_dimensions(cols, id_col) or \
                        find_incrementing_prefix_series(cols)
                dim_set = set(dims)
                return [c for c in cols if c != id_col and c not in dim_set]

            # The eigenvec path/dim/ID fields only exist in the DOM while the PCA
            # tab still shows its loader (show_eigenvec_loader). Once the PCA
            # tab's own Load has already happened (the normal path here — it
            # loads coordinates only, see pca_load), those fields are gone and
            # the same info is read straight from `args` instead.
            _embedded_eigenvec_states = (
                [State({'type': 'setup-arg', 'name': 'eigenvec'}, 'value'),
                 State({'type': 'setup-arg', 'name': 'dim'}, 'value'),
                 State({'type': 'setup-arg', 'name': 'eigenvecID'}, 'value')]
                if show_eigenvec_loader else []
            )

            @app.callback(
                [Output({'type': 'setup-arg', 'name': c}, 'options', allow_duplicate=True)
                 for c in ANNOTATION_DEPENDENT]
                + [Output({'type': 'setup-arg', 'name': c}, 'value', allow_duplicate=True)
                   for c in ANNOTATION_DEPENDENT]
                + [Output('embedded-annotation-status', 'children', allow_duplicate=True),
                   Output('annotation-details', 'style', allow_duplicate=True),
                   Output('annotation-source-store', 'data', allow_duplicate=True),
                   Output({'type': 'setup-arg', 'name': 'annotation'}, 'value',
                           allow_duplicate=True),
                   Output('annotationid-row', 'style', allow_duplicate=True)],
                Input('use-embedded-annotation-btn', 'n_clicks'),
                *_embedded_eigenvec_states,
                [State({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT],
                prevent_initial_call=True,
            )
            def use_embedded_annotation(_n, *rest):
                n = len(ANNOTATION_DEPENDENT)
                if show_eigenvec_loader:
                    eigenvec_path, dim_value, id_value = rest[0], rest[1], rest[2]
                    current = rest[3:]
                else:
                    eigenvec_path = getattr(args, 'eigenvec', None)
                    dim_value = getattr(args, 'dim', None)
                    id_value = getattr(args, 'eigenvecID', None)
                    current = rest
                no_change = [no_update] * (2 * n)
                if not eigenvec_path or not str(eigenvec_path).strip():
                    msg = dbc.Alert('Enter the eigenvec file path first (PCA tab).', color='warning')
                    return no_change + [msg, no_update, no_update, no_update, no_update]
                if not os.path.isfile(eigenvec_path):
                    msg = dbc.Alert(f"Eigenvec file not found: {eigenvec_path}", color='danger')
                    return no_change + [msg, no_update, no_update, no_update, no_update]
                try:
                    cols = _detect_embedded_columns(eigenvec_path, dim_value, id_value)
                except Exception as exc:  # noqa: BLE001
                    msg = dbc.Alert(f"Could not read: {exc}", color='danger')
                    return no_change + [msg, no_update, no_update, no_update, no_update]
                if not cols:
                    msg = dbc.Alert('No extra (non-dimension) columns found in the eigenvec file — '
                                    'read a separate annotation file below.', color='warning')
                    return no_change + [msg, no_update, no_update, no_update, no_update]
                options = [{'label': c, 'value': c} for c in cols]
                guesses = _guess_annotation_dependent(cols)
                values = [cur if cur in cols else guesses.get(dest)
                          for dest, cur in zip(ANNOTATION_DEPENDENT, current)]
                msg = _summary_alert(len(cols), 0, 0)
                return [options] * n + values + [msg, {}, 'embedded', '', {'display': 'none'}]

            @app.callback(
                [Output({'type': 'setup-arg', 'name': c}, 'options', allow_duplicate=True)
                 for c in ANNOTATION_DEPENDENT]
                + [Output({'type': 'setup-arg', 'name': c}, 'value', allow_duplicate=True)
                   for c in ANNOTATION_DEPENDENT]
                + [Output('embedded-annotation-status', 'children', allow_duplicate=True),
                   Output('annotation-details', 'style', allow_duplicate=True),
                   Output('annotation-source-store', 'data', allow_duplicate=True),
                   Output('annotationid-row', 'style', allow_duplicate=True)],
                Input('use-combine-annotation-btn', 'n_clicks'),
                *_embedded_eigenvec_states,
                State({'type': 'setup-arg', 'name': 'annotation'}, 'value'),
                [State({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT],
                prevent_initial_call=True,
            )
            def choose_combine_annotation(_n, *rest):
                n = len(ANNOTATION_DEPENDENT)
                if show_eigenvec_loader:
                    eigenvec_path, dim_value, id_value, path = rest[0], rest[1], rest[2], rest[3]
                    current = rest[4:]
                else:
                    eigenvec_path = getattr(args, 'eigenvec', None)
                    dim_value = getattr(args, 'dim', None)
                    id_value = getattr(args, 'eigenvecID', None)
                    path, *current = rest
                status, *file_rest = _read_annotation_columns(path, current)
                if status == 'error':
                    return [no_update] * (2 * n) + [file_rest[0], no_update, no_update, no_update]
                options, values, cols, n_samples = file_rest
                try:
                    embedded_cols = _detect_embedded_columns(eigenvec_path, dim_value, id_value) \
                        if eigenvec_path else []
                except Exception:  # noqa: BLE001
                    embedded_cols = []
                # Approximate preview: exact-name overlap. The actual Load step
                # compares abbreviated names (matching what app.py does), which
                # can occasionally differ for very long column names.
                file_cols = set(cols)
                n_duplicate = sum(1 for c in embedded_cols if c in file_cols)
                n_from_eigenvec = len(embedded_cols) - n_duplicate
                msg = _summary_alert(n_from_eigenvec, len(cols), n_duplicate, n_samples)
                return options + values + [msg, {}, 'combine', {}]
        else:
            @app.callback(
                [Output({'type': 'setup-arg', 'name': c}, 'options') for c in ANNOTATION_DEPENDENT]
                + [Output({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT]
                + [Output('embedded-annotation-status', 'children'),
                   Output('annotation-details', 'style')],
                Input('read-annotation-btn', 'n_clicks'),
                State({'type': 'setup-arg', 'name': 'annotation'}, 'value'),
                [State({'type': 'setup-arg', 'name': c}, 'value') for c in ANNOTATION_DEPENDENT],
                prevent_initial_call=True,
            )
            def read_annotation(_n, path, *current):
                n = len(ANNOTATION_DEPENDENT)
                status, *rest = _read_annotation_columns(path, current)
                if status == 'error':
                    return [no_update] * (2 * n) + [rest[0], no_update]
                options, values, cols, n_samples = rest
                msg = dbc.Alert(f"Read {len(cols)} columns, {n_samples} samples.", color='success')
                return options + values + [msg, {}]

        @app.callback(
            Output('relaunch-store', 'data', allow_duplicate=True),
            Output('annotation-load-status', 'children'),
            Input('annotation-load-btn', 'n_clicks'),
            State({'type': 'setup-arg', 'name': ALL}, 'value'),
            State({'type': 'setup-arg', 'name': ALL}, 'id'),
            State('annotation-source-store', 'data'),
            *_SETTINGS_STATE,
            prevent_initial_call=True,
        )
        def annotation_load(_n, values, ids, source, set_values, set_ids):
            dom = {**_dom(set_values, set_ids), **_dom(values, ids)}
            # Eigenvec must already be loaded (this loader lives in the running app).
            if not getattr(args, 'eigenvec', None):
                return no_update, dbc.Alert('Load the eigenvec first (PCA tab).',
                                            color='warning')
            if source == 'embedded':
                # Annotation columns live inside the eigenvec file itself. The PCA
                # tab's earlier Load set --ignore-embedded-annotation to get
                # coordinates only; clear it here so this relaunch actually
                # extracts them, omit --annotation so they come from the
                # eigenvec, and carry over the eigenvec fields too in case this
                # is somehow the first relaunch (before the PCA tab's own Load).
                dom['ignore_embedded_annotation'] = False
                overlay = (EIGENVEC_FIELDS + ANNOTATION_DEPENDENT + settings_arg_names()
                          + ['ignore_embedded_annotation'])
                port = _relaunch_from(args, dom, overlay)
                return {'go': True, 'port': port}, _starting_alert()
            annotation = dom.get('annotation')
            if not annotation or not str(annotation).strip():
                return no_update, dbc.Alert('The annotation file is required.',
                                            color='danger')
            if not os.path.isfile(annotation):
                return no_update, dbc.Alert(f"Annotation file not found: {annotation}",
                                            color='danger')
            # 'combine' merges in the eigenvec file's own columns too (deduplicated
            # against the annotation file's); plain 'file' (the default — reading a
            # file without picking a mode above) uses only the file, so explicitly
            # clear a stale True from an earlier 'combine' relaunch.
            dom['merge_embedded_annotation'] = (source == 'combine')
            port = _relaunch_from(args, dom, ANNOTATION_FIELDS + settings_arg_names())
            return {'go': True, 'port': port}, _starting_alert()

    # ── Settings (always) ────────────────────────────────────────────────────
    @app.callback(
        Output('relaunch-store', 'data', allow_duplicate=True),
        Output('settings-status', 'children'),
        Input('settings-apply-btn', 'n_clicks'),
        *_SETTINGS_STATE,
        prevent_initial_call=True,
    )
    def settings_apply(_n, values, ids):
        # Settings owns every parameter, so Refresh relaunches with exactly what
        # the tab shows — a field cleared here is dropped from the command line.
        port = _relaunch_from(args, _dom(values, ids), all_arg_names())
        return {'go': True, 'port': port}, _starting_alert()

    # ── Reload poller (always) ───────────────────────────────────────────────
    app.clientside_callback(
        POLLER_JS,
        Output('relaunch-poll-dummy', 'data-poll'),
        Input('relaunch-store', 'data'),
        prevent_initial_call=True,
    )
