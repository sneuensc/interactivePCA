"""
Main Dash application factory for interactivePCA.
"""

import logging
import os
import pandas as pd
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output

from .data_loader import load_eigenvec, load_annotation, merge_data, resolve_annotation_columns
from .plots import set_dataframe
from .relaunch import schedule_relaunch
from .callbacks.setup import register_setup_callbacks, _compose_argv
from .layouts.setup import PRIMARY_ARGS
from .args import create_parser
from .components import load_aesthetics_file, merge_aesthetics, get_init_aesthetics, register_hover_update_callbacks
from .layouts import create_layout
from .callbacks import register_all_callbacks
from .callbacks.snapshot import register_snapshot_callback


def create_app(args):
    """
    Create and configure the Dash application.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        Configured Dash app instance
    """
    logging.info("Creating Dash application...")
    
    # Load data only when an eigenvec is given. Otherwise the app starts as a
    # tab shell whose PCA/Annotation tabs host the file loaders (see
    # create_layout and callbacks.setup); the data-dependent callbacks are then
    # skipped and registered only after the user loads a file (which relaunches).
    # --setup forces the loader shell even with data given (Restart uses it to
    # return to the loaders with the previous arguments prefilled).
    if args.setup or not args.eigenvec:
        df = None
        pcs = []
        annotation = None
        annotation_desc = None
        annotation_cols = {}
        ANNOTATION_TIME = ANNOTATION_LAT = ANNOTATION_LONG = None
        show_annotation_table = show_map_plot = show_time_plot = False
        init_selected_ids = []
        dropdown_group_list = ['none']
        dropdown_group_symbol_list = ['none']
        dropdown_list_continuous = []
        init_group = 'none'
        init_continuous = None
        init_aesthetics = {}
        has_embedded_annotation_cols = False
    else:
        logging.info("Loading data files...")

        # Load eigenvectors (required)
        eigenvec, pcs, eigenvec_id = load_eigenvec(args.eigenvec, args.eigenvecID, args.dim)

        # Load annotation
        annotation = None
        annotation_desc = None
        annotation_cols = {}
        # Whether the Annotation tab's "Use annotations from eigenvec file" button
        # has anything to offer — only relevant while that tab still shows its
        # loader (annotation_desc is None); stays False once real annotation data
        # (from either branch below) is actually loaded.
        has_embedded_annotation_cols = False

        if args.annotation:
            annotation, annotation_desc, annotation_cols = load_annotation(args.annotation, args)
            # The eigenvec file may itself carry extra (non-ID, non-dimension)
            # columns (e.g. it was also usable in single-file mode).
            dim_set = set(pcs)
            annot_cols = [c for c in eigenvec.columns if c != 'id' and c not in dim_set]
            if annot_cols and args.merge_embedded_annotation:
                # Add them alongside the annotation file's own columns instead of
                # discarding them — but a column already present in the file wins
                # over a same-named one embedded in the eigenvec, so the merge
                # below never sees a collision (which pandas would otherwise
                # silently resolve by suffixing both copies _x/_y).
                from .utils import make_unique_abbr
                abbrev = make_unique_abbr(annot_cols, max_length=args.col_abbrev)
                existing = set(annotation.columns)
                keep_cols = [c for c, ab in zip(annot_cols, abbrev) if ab not in existing]
                keep_abbrev = [ab for ab in abbrev if ab not in existing]
                skipped = [c for c in annot_cols if c not in keep_cols]
                if skipped:
                    logging.info(f"   Skipped {len(skipped)} eigenvec column(s) already present "
                                 f"in the annotation file: {', '.join(skipped)}.")
                if keep_cols:
                    eigenvec = eigenvec[['id'] + pcs + keep_cols]
                    eigenvec.rename(columns=dict(zip(keep_cols, keep_abbrev)), inplace=True)
                    extra_desc = pd.DataFrame({
                        'Abbreviation': keep_abbrev,
                        'Description': keep_cols,
                        'Type': ['continuous' if eigenvec[c].dtype.kind in 'fi' else 'categorical'
                                for c in keep_abbrev],
                        'N_levels': [eigenvec[c].nunique(dropna=False)
                                    if eigenvec[c].dtype.kind not in 'fi' else None
                                    for c in keep_abbrev]
                    })
                    extra_desc['Dropdown'] = [
                        'Yes' if ((typ == 'continuous') or
                                 ((typ == 'categorical') and (nlev <= args.max_factors)))
                        else ''
                        for typ, nlev in zip(extra_desc['Type'], extra_desc['N_levels'])
                    ]
                    annotation_desc = pd.concat([annotation_desc, extra_desc], ignore_index=True)
                    annotation_cols.update(resolve_annotation_columns(
                        annotation_desc, args, default_id=annotation_cols.get('id')
                    ))
                    logging.info(f"   Added {len(keep_cols)} eigenvec column(s) to the "
                                 f"annotation: {', '.join(keep_cols)}.")
                else:
                    eigenvec = eigenvec[['id'] + pcs]
            else:
                # Real annotation file only — drop the eigenvec's own extra
                # columns rather than merging them in — otherwise a same-named
                # column in both (e.g. "Region" in both the eigenvec file and
                # the annotation file) gets silently suffixed _x/_y by the join,
                # and every group/aesthetic/map lookup by that plain name breaks.
                eigenvec = eigenvec[['id'] + pcs]
        elif args.ignore_embedded_annotation:
            # The PCA tab's own "Load" button relaunches with this set, so a plain
            # eigenvec load stays coordinates-only even if the file has extra
            # columns — the Annotation tab is where the user opts into them.
            dim_set = set(pcs)
            annot_cols = [c for c in eigenvec.columns if c != 'id' and c not in dim_set]
            has_embedded_annotation_cols = bool(annot_cols)
            if annot_cols:
                logging.info(f"   {len(annot_cols)} extra column(s) in the eigenvec file were "
                             f"not loaded as annotation — use the Annotation tab to load them.")
        else:
            # Single-file mode: eigenvec already has annotation columns if they exist.
            # They live in the same table as the dimensions (one row per sample), so
            # there is nothing to merge — rename them to their abbreviations in place
            # and describe them the same way load_annotation() would. `annotation`
            # stays None: merge_data() then uses eigenvec as-is, avoiding a self-join
            # that would otherwise duplicate every annotation column as _x/_y.
            dim_set = set(pcs)
            annot_cols = [c for c in eigenvec.columns if c != 'id' and c not in dim_set]
            if annot_cols:
                from .utils import make_unique_abbr
                abbrev = make_unique_abbr(annot_cols, max_length=args.col_abbrev)
                # Create annotation_desc
                annotation_desc = pd.DataFrame({
                    'Abbreviation': abbrev,
                    'Description': annot_cols,
                    'Type': ['continuous' if eigenvec[c].dtype.kind in 'fi' else 'categorical'
                            for c in annot_cols],
                    'N_levels': [eigenvec[c].nunique(dropna=False) if eigenvec[c].dtype.kind not in 'fi'
                                else None for c in annot_cols]
                })
                annotation_desc['Dropdown'] = [
                    'Yes' if ((typ == 'continuous') or
                             ((typ == 'categorical') and (nlev <= args.max_factors)))
                    else ''
                    for typ, nlev in zip(annotation_desc['Type'], annotation_desc['N_levels'])
                ]
                eigenvec.rename(columns=dict(zip(annot_cols, abbrev)), inplace=True)
                annotation_cols.update(
                    resolve_annotation_columns(annotation_desc, args, default_id='id')
                )
                logging.info(f"   Extracted {len(annot_cols)} annotation columns from eigenvec file.")
                if 'longitude' in annotation_cols and 'latitude' in annotation_cols:
                    logging.info(f"   Found geographic coordinates: lat='{annotation_cols['latitude']}', "
                                 f"lon='{annotation_cols['longitude']}'.")
                if 'time' in annotation_cols:
                    logging.info(f"   Found time column: '{annotation_cols['time']}'.")

        # Merge data
        df = merge_data(
            eigenvec,
            annotation,
            eigenvec_id_col='id',
            annotation_id_col=annotation_cols.get('id'),
            time_col=annotation_cols.get('time'),
            invert_time=args.time_invert
        )

        # Set global DataFrame in plots module
        set_dataframe(df)

        # Get annotation columns
        ANNOTATION_TIME = annotation_cols.get('time')
        ANNOTATION_LAT = annotation_cols.get('latitude')
        ANNOTATION_LONG = annotation_cols.get('longitude')
        show_annotation_table = annotation_desc is not None
        show_map_plot = (
            show_annotation_table
            and ANNOTATION_LAT is not None
            and ANNOTATION_LONG is not None
            and ANNOTATION_LAT in df.columns
            and ANNOTATION_LONG in df.columns
        )
        show_time_plot = (
            show_annotation_table
            and ANNOTATION_TIME is not None
            and ANNOTATION_TIME in df.columns
        )

        # Initialize selected IDs
        if args.selectedID:
            if os.path.isfile(args.selectedID):
                with open(args.selectedID, 'r') as f:
                    init_selected_ids = [line.rstrip('\n') for line in f]
            else:
                init_selected_ids = args.selectedID.split(";")

            # Filter to valid IDs
            valid_ids = set(df['id'].tolist())
            init_selected_ids = [sid for sid in init_selected_ids if sid in valid_ids]
        else:
            init_selected_ids = df['id'].tolist()

        logging.info(f"Selected {len(init_selected_ids)} of {len(df)} samples")

        # Initialize grouping options
        dropdown_group_list = ['none']
        dropdown_group_symbol_list = ['none']
        if annotation_desc is not None:
            # Add columns suitable for grouping
            grouping_cols = annotation_desc.loc[
                annotation_desc['Dropdown'] == 'Yes',
                'Abbreviation'
            ].tolist()
            dropdown_group_list.extend(grouping_cols)
            # Shape grouping: categorical columns only (no PCs, no continuous)
            dropdown_group_symbol_list.extend(
                col for col in grouping_cols
                if col in df.columns and df[col].dtype.kind not in 'fi'
            )

        # Include PCs as grouping options (color only, not shape)
        for pc in pcs:
            if pc not in dropdown_group_list:
                dropdown_group_list.append(pc)

        init_group = args.group if args.group and args.group in dropdown_group_list else dropdown_group_list[0]

        # Initialize continuous variable options
        dropdown_list_continuous = []
        init_continuous = ANNOTATION_TIME
        if annotation_desc is not None:
            dropdown_list_continuous = annotation_desc.loc[
                annotation_desc['Type'] == 'continuous',
                'Abbreviation'
            ].tolist()
            if dropdown_list_continuous and ANNOTATION_TIME not in dropdown_list_continuous:
                init_continuous = dropdown_list_continuous[0] if dropdown_list_continuous else None

        # Initialize aesthetics from parameters
        init_aesthetics = get_init_aesthetics(args, init_group, df)

        # Load aesthetics from file if provided (overrides parameter defaults)
        if args.aesthetics_file:
            file_aesthetics = load_aesthetics_file(args.aesthetics_file)
            if file_aesthetics and init_group in file_aesthetics:
                # Merge file aesthetics with parameter-based defaults
                init_aesthetics = merge_aesthetics(init_aesthetics, file_aesthetics[init_group])
    
    # Create Dash app
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True
    )
    
    # Build layout
    layout_data = create_layout(
        args, df, pcs,
        annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
        init_selected_ids, init_group, init_continuous, init_aesthetics,
        dropdown_group_list, dropdown_list_continuous,
        dropdown_group_symbol_list=dropdown_group_symbol_list,
        has_embedded_annotation_cols=has_embedded_annotation_cols
    )
    app.layout = layout_data['layout']
    tab_content_map = layout_data['tab_content_map']
    
    # Register tab switching callback using clientside callback for better performance
    app.clientside_callback(
        """
        function(active_tab) {
            // Hide all tab content divs
            const tabs = ['pca_tab', 'annotation_tab', 'settings_tab', 'help_tab'];
            tabs.forEach(function(tab) {
                const el = document.getElementById(tab + '_content');
                if (el) {
                    el.style.display = (tab === active_tab) ? 'block' : 'none';
                }
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    
    # Register resizer functionality for draggable panes
    app.clientside_callback(
        """
        function() {
            // Initialize resizers on page load
            setTimeout(function() {
                const resizers = document.querySelectorAll('[id$="-resizer"]');
                
                resizers.forEach(function(resizer) {
                    if (resizer.dataset.initialized === 'true') return;
                    resizer.dataset.initialized = 'true';
                    
                    // Determine if this is a vertical or horizontal resizer
                    const isVertical = resizer.id.includes('vertical');
                    
                    resizer.addEventListener('mousedown', function(e) {
                        e.preventDefault();
                        const container = resizer.parentElement;
                        const children = Array.from(container.children);
                        const resizerIndex = children.indexOf(resizer);
                        
                        if (resizerIndex > 0 && resizerIndex < children.length - 1) {
                            const before = children[resizerIndex - 1];
                            const after = children[resizerIndex + 1];
                            
                            if (isVertical) {
                                // Handle vertical resizer (width-based)
                                let startX = e.clientX;
                                let startWidth = before.offsetWidth;
                                const containerWidth = container.offsetWidth;
                                const resizerWidth = 8;
                                
                                function handleMouseMove(moveEvent) {
                                    const deltaX = moveEvent.clientX - startX;
                                    const newWidth = startWidth + deltaX;
                                    const minSize = 10; // pixels minimum on each side
                                    const availableWidth = containerWidth - resizerWidth;
                                    // Constrain so both sides have at least minSize pixels
                                    const beforePx = Math.max(minSize, Math.min(availableWidth - minSize, newWidth));
                                    const beforePercent = (beforePx / availableWidth) * 100;
                                    const afterPercent = 100 - beforePercent;
                                    
                                    before.style.flex = `0 0 ${beforePercent}%`;
                                    after.style.flex = `0 0 ${afterPercent}%`;
                                }
                                
                                function handleMouseUp() {
                                    document.removeEventListener('mousemove', handleMouseMove);
                                    document.removeEventListener('mouseup', handleMouseUp);
                                }
                                
                                document.addEventListener('mousemove', handleMouseMove);
                                document.addEventListener('mouseup', handleMouseUp);
                            } else {
                                // Handle horizontal resizer (height-based)
                                let startY = e.clientY;
                                let startHeight = before.offsetHeight;
                                const containerHeight = container.offsetHeight;
                                const resizerHeight = 8;
                                
                                function handleMouseMove(moveEvent) {
                                    const deltaY = moveEvent.clientY - startY;
                                    const newHeight = startHeight + deltaY;
                                    const minSize = 10; // pixels minimum on each side
                                    const availableHeight = containerHeight - resizerHeight;
                                    // Constrain so both sides have at least minSize pixels
                                    const beforePx = Math.max(minSize, Math.min(availableHeight - minSize, newHeight));
                                    const beforePercent = (beforePx / availableHeight) * 100;
                                    const afterPercent = 100 - beforePercent;
                                    
                                    before.style.flex = `0 0 ${beforePercent}%`;
                                    after.style.flex = `0 0 ${afterPercent}%`;
                                }
                                
                                function handleMouseUp() {
                                    document.removeEventListener('mousemove', handleMouseMove);
                                    document.removeEventListener('mouseup', handleMouseUp);
                                }
                                
                                document.addEventListener('mousemove', handleMouseMove);
                                document.addEventListener('mouseup', handleMouseUp);
                            }
                        }
                    });
                });
            }, 100);
            
            return null;
        }
        """,
        Output('tabs-content', 'data-resizers-init', allow_duplicate=True),
        Input('tabs', 'value'),
        prevent_initial_call='initial_duplicate'
    )
    
    # ── Snapshot export ───────────────────────────────────────────────────
    register_snapshot_callback(app)

    # ── Restart ─────────────────────────────────────────────────────────────
    # Relaunch the process with no data (just the port) to return to the setup
    # tab shell. The reload poller is registered in register_setup_callbacks.
    @app.callback(
        Output('relaunch-store', 'data', allow_duplicate=True),
        Input('restart-btn', 'n_clicks'),
        prevent_initial_call=True,
    )
    def _restart(n_clicks):
        if not n_clicks:
            return dash.no_update
        port = getattr(args, 'server_port', 8050)
        # Relaunch into an empty loader shell — identical to starting the
        # server fresh with no data arguments (just the file-path inputs, no
        # prefilled columns/Load button). Non-data settings (port, --dev,
        # point styling, ...) carry over; only the eigenvec/annotation fields
        # are dropped.
        values = {a.dest: getattr(args, a.dest, None)
                  for a in create_parser()._actions
                  if a.option_strings and a.dest not in ('help', 'setup')
                  and a.dest not in PRIMARY_ARGS}
        argv = _compose_argv(values) + ['--setup']
        # Ensure server_port is always included in the relaunch
        if '--server-port' not in argv:
            argv.extend(['--server-port', str(port)])
        schedule_relaunch(argv)
        return {'go': True, 'port': port}

    # ── Map shape icons ─────────────────────────────────────────────────────
    # The MapLibre basemap ships no sprite, so non-'circle' marker symbols
    # (triangles, stars, …) cannot be drawn by default. This clientside
    # callback generates each symbol as an SDF icon on a canvas and registers
    # it on the underlying map, both proactively and via the styleimagemissing
    # event, so shape grouping renders on the map tinted by the group colour.
    # It degrades to a no-op (circles only) if the map internals are unavailable.
    if show_map_plot:
        app.clientside_callback(
            """
            function(_fig) {
                var NO_UPDATE = window.dash_clientside.no_update;
                try {
                    var el = document.getElementById('pca-map-plot');
                    if (!el) return NO_UPDATE;
                    var div = el.data ? el : (el.querySelector && el.querySelector('.js-plotly-plot'));
                    if (!div || !div._fullLayout) return NO_UPDATE;

                    // Plotly.react cannot reliably switch a graph between the
                    // 'map' (MapLibre) and 'geo' subplot systems in place, so the
                    // basemap toggle sometimes leaves the old subplot rendered.
                    // Detect that mismatch and force a clean redraw.
                    if (_fig && _fig.data) {
                        var wantGeo = _fig.data.some(function(t) { return t.type === 'scattergeo'; });
                        var wantMap = _fig.data.some(function(t) {
                            return t.type === 'scattermap' || t.type === 'scattermapbox'; });
                        var haveGeo = !!div._fullLayout.geo;
                        var haveMap = !!div._fullLayout.map;
                        if ((wantGeo && !haveGeo) || (wantMap && !haveMap)) {
                            Plotly.newPlot(div, _fig.data, _fig.layout, _fig.config || {});
                        }
                    }

                    if (!div._fullLayout.map || !div._fullLayout.map._subplot) return NO_UPDATE;
                    var map = div._fullLayout.map._subplot.map;
                    if (!map || !map.addImage) return NO_UPDATE;

                    var S = 64;
                    function draw(kind) {
                        var c = document.createElement('canvas'); c.width = S; c.height = S;
                        var x = c.getContext('2d'); x.clearRect(0, 0, S, S);
                        x.fillStyle = '#ffffff';
                        var m = S * 0.14, a = S - m, cx = S / 2, cy = S / 2;
                        x.beginPath();
                        if (kind === 'triangle-up') { x.moveTo(cx, m); x.lineTo(a, a); x.lineTo(m, a); x.closePath(); x.fill(); }
                        else if (kind === 'triangle-down') { x.moveTo(m, m); x.lineTo(a, m); x.lineTo(cx, a); x.closePath(); x.fill(); }
                        else if (kind === 'square') { x.fillRect(m, m, a - m, a - m); }
                        else if (kind === 'diamond') { x.moveTo(cx, m); x.lineTo(a, cy); x.lineTo(cx, a); x.lineTo(m, cy); x.closePath(); x.fill(); }
                        else if (kind === 'cross') { var t = S * 0.16; x.fillRect(cx - t, m, 2 * t, a - m); x.fillRect(m, cy - t, a - m, 2 * t); }
                        else if (kind === 'star') {
                            var spikes = 5, or = S * 0.42, ir = S * 0.18, rot = -Math.PI / 2, step = Math.PI / spikes;
                            x.moveTo(cx + Math.cos(rot) * or, cy + Math.sin(rot) * or);
                            for (var i = 0; i < spikes; i++) {
                                rot += step; x.lineTo(cx + Math.cos(rot) * ir, cy + Math.sin(rot) * ir);
                                rot += step; x.lineTo(cx + Math.cos(rot) * or, cy + Math.sin(rot) * or);
                            }
                            x.closePath(); x.fill();
                        } else { x.arc(cx, cy, S * 0.34, 0, 2 * Math.PI); x.fill(); }
                        var img = x.getImageData(0, 0, S, S);
                        return { width: S, height: S, data: new Uint8Array(img.data.buffer) };
                    }

                    // Plotly requests map icons as '<symbol>-15'.
                    var kinds = {
                        'circle-15': 'circle', 'square-15': 'square', 'diamond-15': 'diamond',
                        'triangle-up-15': 'triangle-up', 'triangle-down-15': 'triangle-down',
                        'star-15': 'star', 'cross-15': 'cross'
                    };
                    // pixelRatio makes the 64px canvas behave as a ~15px icon so
                    // Plotly's maki '-15' sizing renders icons at roughly the same
                    // pixel size as native 'circle' markers.
                    var PR = S / 15;
                    if (!map.__simIconsBound) {
                        map.__simIconsBound = true;
                        map.on('styleimagemissing', function(e) {
                            var id = e.id;
                            if (!kinds[id] || map.hasImage(id)) return;
                            map.addImage(id, draw(kinds[id]), { sdf: true, pixelRatio: PR });
                        });
                    }
                    // Register every icon proactively so future renders find them.
                    // The bound styleimagemissing handler covers anything still
                    // missing mid-render. We deliberately do NOT call
                    // Plotly.restyle here: mutating the Dash-managed graph outside
                    // Dash desyncs dcc.Graph and stops later figure updates (e.g.
                    // switching to a continuous colour scale) from being applied.
                    Object.keys(kinds).forEach(function(id) {
                        if (!map.hasImage(id)) { map.addImage(id, draw(kinds[id]), { sdf: true, pixelRatio: PR }); }
                    });
                } catch (err) { /* map internals unavailable — circles only */ }
                return NO_UPDATE;
            }
            """,
            Output('hover-sync-dummy', 'data', allow_duplicate=True),
            Input('pca-map-plot', 'figure'),
            prevent_initial_call='initial_duplicate',
        )

        # Capture the live map view as a lon/lat bounding box whenever it
        # changes, so it can be re-applied to the other basemap on toggle.
        # Tiles read the true visible bounds from the MapLibre map; geo reads
        # its axis ranges. A bounding box maps cleanly onto both basemaps
        # (geo axis ranges fill the pane; tiles centre + zoom).
        app.clientside_callback(
            """
            function(_relayout) {
                var NO_UPDATE = window.dash_clientside.no_update;
                try {
                    var el = document.getElementById('pca-map-plot');
                    if (!el) return NO_UPDATE;
                    var d = el.data ? el : (el.querySelector && el.querySelector('.js-plotly-plot'));
                    if (!d || !d._fullLayout) return NO_UPDATE;
                    var fl = d._fullLayout;
                    if (fl.map) {
                        var mb = fl.map._subplot && fl.map._subplot.map;
                        if (mb && mb.getBounds) {
                            var b = mb.getBounds();
                            return {lon0: b.getWest(), lat0: b.getSouth(),
                                    lon1: b.getEast(), lat1: b.getNorth()};
                        }
                        if (fl.map.center) {  // fallback from centre + zoom
                            var span = 360 / Math.pow(2, fl.map.zoom || 1);
                            return {lon0: fl.map.center.lon - span / 2, lon1: fl.map.center.lon + span / 2,
                                    lat0: fl.map.center.lat - span / 4, lat1: fl.map.center.lat + span / 4};
                        }
                    }
                    if (fl.geo) {
                        var lonR = fl.geo.lonaxis && fl.geo.lonaxis.range;
                        var latR = fl.geo.lataxis && fl.geo.lataxis.range;
                        if (lonR && latR) {
                            return {lon0: lonR[0], lat0: latR[0], lon1: lonR[1], lat1: latR[1]};
                        }
                    }
                } catch (err) { /* ignore */ }
                return NO_UPDATE;
            }
            """,
            Output('map-view-store', 'data'),
            Input('pca-map-plot', 'relayoutData'),
            prevent_initial_call=True,
        )

        # Fill the geo pane (scattergeo only). Equirectangular maps lon/lat
        # linearly, so a data range whose aspect (lonSpan/latSpan in degrees)
        # differs from the pane makes Plotly centre the map and letterbox.
        # Standard fit-bounds rule: keep the binding axis at the data range and
        # EXTEND the other so lonSpan/latSpan matches the pane aspect, filling
        # the space while keeping all data visible.
        #
        # The fill always recomputes from a stored BASE range (the data/preserved
        # range the server rendered) rather than the current — possibly already
        # extended — range, so repeated re-fits cannot drift. A ResizeObserver
        # re-renders Plotly and re-fits whenever the pane changes size (the pane
        # drag-resizers and window-ratio changes do not fire Plotly's own resize).
        app.clientside_callback(
            """
            function(_fig) {
                var NO_UPDATE = window.dash_clientside.no_update;
                try {
                    var el = document.getElementById('pca-map-plot');
                    if (!el) return NO_UPDATE;
                    var d = el.data ? el : (el.querySelector && el.querySelector('.js-plotly-plot'));
                    if (!d) return NO_UPDATE;

                    function geoRange() {
                        var g = d._fullLayout && d._fullLayout.geo;
                        if (!g || !g.lonaxis || !g.lataxis || !g.lonaxis.range || !g.lataxis.range) return null;
                        return {lon: g.lonaxis.range.slice(), lat: g.lataxis.range.slice()};
                    }
                    function fillFromBase() {
                        var base = d.__simBaseRange;
                        if (!base || !d._fullLayout || !d._fullLayout.geo) return;
                        var dom = d._fullLayout.geo.domain || {x: [0, 1], y: [0, 1]};
                        // Live container size — dcc.Graph's own autosize does not
                        // catch pane drag-resizes, so we drive the plot size here.
                        var rc = el.getBoundingClientRect();
                        var pxW = rc.width * (dom.x[1] - dom.x[0]);
                        var pxH = rc.height * (dom.y[1] - dom.y[0]);
                        if (!pxW || !pxH) return;
                        var paneAspect = pxW / pxH;
                        // Equirectangular: box aspect is lonSpan/latSpan in degrees.
                        var lonSpan = base.lon[1] - base.lon[0];
                        var latSpan = base.lat[1] - base.lat[0];
                        if (lonSpan <= 0 || latSpan <= 0) return;
                        // Centre a span of width `span` on `mid`, but keep it inside
                        // [-lim, lim]: if it would overflow one edge (e.g. past the
                        // north pole), shift it the other way so the extra space
                        // shows real land rather than blank beyond-pole ocean — and
                        // latitude never exceeds ±90, which would corrupt the
                        // equirectangular projection's scale.
                        function fit(mid, span, lim) {
                            if (span >= 2 * lim) return [-lim, lim];
                            var lo = mid - span / 2, hi = mid + span / 2;
                            if (hi > lim) { lo -= (hi - lim); hi = lim; }
                            if (lo < -lim) { hi += (-lim - lo); lo = -lim; }
                            return [lo, hi];
                        }
                        var newLon = base.lon.slice(), newLat = base.lat.slice();
                        if (lonSpan / latSpan < paneAspect) {
                            // Latitude binds → keep base latitude, extend longitude.
                            newLon = fit((base.lon[0] + base.lon[1]) / 2, latSpan * paneAspect, 180);
                        } else {
                            // Longitude binds → keep base longitude, extend latitude.
                            newLat = fit((base.lat[0] + base.lat[1]) / 2, lonSpan / paneAspect, 90);
                        }
                        // Skip if nothing changed (avoids churn; no resize loop
                        // since setting the plot size does not change the container).
                        var cur = geoRange();
                        var fl = d._fullLayout;
                        if (cur &&
                            Math.abs(cur.lon[0] - newLon[0]) < 0.05 && Math.abs(cur.lon[1] - newLon[1]) < 0.05 &&
                            Math.abs(cur.lat[0] - newLat[0]) < 0.05 && Math.abs(cur.lat[1] - newLat[1]) < 0.05 &&
                            Math.abs((fl.width || 0) - rc.width) < 1 && Math.abs((fl.height || 0) - rc.height) < 1) return;
                        Plotly.relayout(d, {
                            width: rc.width, height: rc.height,
                            'geo.lonaxis.range': newLon, 'geo.lataxis.range': newLat
                        });
                    }

                    if (!d._fullLayout || !d._fullLayout.geo) return NO_UPDATE;

                    // A figure update means the server rendered a fresh data/
                    // preserved range: adopt it as the base to fill from.
                    var r = geoRange();
                    if (r) d.__simBaseRange = r;

                    // Re-fit on any container resize (pane drag-resizers, window
                    // ratio changes) — these do not fire dcc.Graph's autosize.
                    if (!d.__simResizeObs && window.ResizeObserver) {
                        d.__simResizeObs = new ResizeObserver(function() {
                            window.requestAnimationFrame(fillFromBase);
                        });
                        d.__simResizeObs.observe(el);
                    }

                    fillFromBase();
                } catch (err) { /* ignore */ }
                return NO_UPDATE;
            }
            """,
            Output('map-fill-dummy', 'data'),
            Input('pca-map-plot', 'figure'),
            prevent_initial_call=True,
        )

    # Right-panel tab switching (Table / Details / Filter)
    app.clientside_callback(
        """
        function(active_tab) {
            var map = {
                'tab-table':   'right-tab-table-content',
                'tab-details': 'right-tab-details-content',
                'tab-filter':  'right-tab-filter-content'
            };
            Object.keys(map).forEach(function(tab) {
                var el = document.getElementById(map[tab]);
                if (!el) return;
                var isActive = (tab === active_tab);
                el.style.display = isActive
                    ? (tab === 'tab-filter' ? 'flex' : tab === 'tab-table' ? 'flex' : 'block')
                    : 'none';
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('right-panel-tabs-dummy', 'data'),
        Input('right-panel-tabs', 'value'),
        prevent_initial_call='initial_duplicate'
    )

    # File-loader callbacks (eigenvec / annotation loaders + Settings). Shown as
    # tab content wherever data is missing; each Load relaunches the process.
    register_setup_callbacks(
        app, args,
        show_eigenvec_loader=df is None,
        show_annotation_loader=annotation_desc is None,
        show_embedded_annotation_button=(has_embedded_annotation_cols or df is None),
    )

    # Data-dependent callbacks need the DataFrame; skip them until data is loaded.
    if df is not None:
        # Register hover update callbacks (factory pattern)
        register_hover_update_callbacks(
            app,
            args,
            df,
            annotation_desc,
            show_map_plot=show_map_plot,
            show_time_plot=show_time_plot,
            show_annotation_table=show_annotation_table,
        )

        # Register all application callbacks
        register_all_callbacks(
            app, args, df, pcs, annotation_desc,
            ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG
        )

    logging.info("Dash application created successfully")
    return app
