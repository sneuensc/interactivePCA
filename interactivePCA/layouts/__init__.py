"""
Layout functions for the interactive PCA application.

Contains:
- create_layout: Main application layout with tabs and stores
- create_pca_tab: PCA visualization tab with plots and controls
- create_annotation_tab: Annotation description table tab
"""

import logging
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
from dash import html, dcc

from ..utils import strip_ansi, dict_of_dicts_to_tuple, nice_step, nice_bounds, get_abbr_of
from ..plots import (
    generate_fig_scatter2d, generate_fig_scatter3d,
    create_geographical_map, generate_map_fig_scattergeo,
)
from ..components import (
    create_checkbox_column_def,
    create_standard_column_def,
    load_aesthetics_file,
    merge_aesthetics,
    get_init_aesthetics
)
from .setup import (
    eigenvec_loader_panel,
    annotation_loader_panel,
    settings_panel,
    file_browser_modal,
    setup_stores,
)
from ..about import version_info


def about_modal():
    """The dialog behind the header logo: the mark at size, plus provenance."""
    info = version_info()
    rows = []
    if info['version']:
        rows.append(('Version', info['version']))
    if info['commit']:
        commit = info['commit'] + (' + local changes' if info['dirty'] else '')
        if info['branch'] and info['branch'] != 'HEAD':
            commit = f"{commit}  ({info['branch']})"
        rows.append(('Commit', commit))
    if info['commit_date']:
        rows.append(('Committed', info['commit_date']))
    if info['author']:
        rows.append(('Author', info['author']))
    if info['email']:
        rows.append(('Contact', html.A(info['email'], href=f"mailto:{info['email']}")))

    # Labels right-aligned against values left-aligned, so the pairs meet in the
    # middle and every value starts on the same column.
    table = html.Table(
        [html.Tr([
            html.Td(label, style={'paddingRight': '18px', 'color': '#6c757d',
                                  'verticalAlign': 'top', 'whiteSpace': 'nowrap',
                                  'textAlign': 'right'}),
            html.Td(value, style={'fontFamily': 'ui-monospace, SFMono-Regular, Menlo, monospace',
                                  'textAlign': 'left'}),
        ]) for label, value in rows],
        style={'margin': '0 auto', 'fontSize': '14px', 'borderCollapse': 'collapse',
               'lineHeight': '1.9'},
    )

    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle('interactivePCA')),
            dbc.ModalBody(
                html.Div(
                    [
                        html.Img(src='/assets/logo.svg',
                                 style={'width': '220px', 'height': '220px',
                                        'display': 'block', 'margin': '0 auto 18px'}),
                        table,
                    ],
                    style={'textAlign': 'center'},
                )
            ),
            dbc.ModalFooter(dbc.Button('Close', id='about-close', color='secondary', n_clicks=0)),
        ],
        id='about-modal', is_open=False, centered=True,
    )


def create_layout(args, df, pcs,
                 annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
                 init_selected_ids, init_group, init_continuous, init_aesthetics,
                 dropdown_group_list, dropdown_list_continuous,
                 dropdown_group_symbol_list=None, has_embedded_annotation_cols=False,
                 init_session=None, map_initially_visible=False, time_initially_visible=False,
                 time_invert_columns=frozenset(), init_pc_x=None, init_pc_y=None,
                 init_time_viz_mode='scatter', init_time_bin_size=None,
                 time_rotate_columns=frozenset(), init_pc_z=None):
    """
    Create the main application layout.
    
    Args:
        args: Command-line arguments
        df: Main DataFrame
        pcs: List of PC column names
        annotation_desc: Annotation description DataFrame
        ANNOTATION_TIME: Time column name
        ANNOTATION_LAT: Latitude column name
        ANNOTATION_LONG: Longitude column name
        init_selected_ids: Initial selected sample IDs
        init_group: Initial grouping variable
        init_continuous: Initial continuous variable
        init_aesthetics: Initial aesthetic settings
        dropdown_group_list: List of grouping options
        dropdown_list_continuous: List of continuous variables
        init_session: Saved view (--session) to apply once the page loads,
            or None

    Returns:
        Dict with a 'layout' key
    """
    # Build tab list
    tab_configs = []
    
    # Determine annotation columns for table/checkboxes
    annotation_columns = None
    if annotation_desc is not None:
        if 'Abbreviation' in annotation_desc.columns:
            annotation_columns = annotation_desc['Abbreviation'].dropna().tolist()
        else:
            annotation_columns = [col for col in annotation_desc.columns]

    # Determine continuous variables for time/continuous plot
    continuous_columns = []
    if annotation_desc is not None and 'Type' in annotation_desc.columns and 'Abbreviation' in annotation_desc.columns:
        continuous_columns = annotation_desc.loc[
            annotation_desc['Type'] == 'continuous',
            'Abbreviation'
        ].dropna().tolist()
    # Include PCs as continuous variables
    continuous_columns.extend([pc for pc in pcs if pc not in continuous_columns])

    # Initial "Shape by" grouping from --group-shape (mirrors --group handling
    # in app.py — same raw-name-vs-abbreviation resolution, same reason).
    init_group_symbol = getattr(args, 'group_shape', None)
    _group_symbol_options = dropdown_group_symbol_list or []
    if (init_group_symbol and init_group_symbol not in _group_symbol_options
            and annotation_desc is not None):
        init_group_symbol = get_abbr_of(
            init_group_symbol, annotation_desc['Description'].tolist(),
            annotation_desc['Abbreviation'].tolist()
        )
    if not init_group_symbol or init_group_symbol not in _group_symbol_options:
        init_group_symbol = 'none'

    # Initial annotation columns shown in the table/hover — --annotation-columns
    # overrides the "first 10" default with an explicit, order-preserving list
    # (a set, like data_loader.resolve_column_set uses elsewhere, would lose
    # the order the table/hover display it in). Each token may be given as
    # the raw/full column name or already its abbreviated working name, same
    # resolution as --group (see app.py's own comment on that).
    init_selected_cols = []
    annotation_desc_extended = None
    if annotation_desc is not None:
        annotation_desc_extended = annotation_desc.copy()
        if pcs:
            pc_rows = pd.DataFrame({
                'Abbreviation': pcs,
                'Description': pcs,
                'Type': ['continuous'] * len(pcs),
                'N_levels': [None] * len(pcs),
                'Dropdown': ['Yes'] * len(pcs)
            })
            annotation_desc_extended = pd.concat([annotation_desc, pc_rows], ignore_index=True)

        raw_annotation_columns = getattr(args, 'annotation_columns', '') or ''
        if raw_annotation_columns.strip():
            descriptions = annotation_desc_extended['Description'].tolist()
            abbreviations = annotation_desc_extended['Abbreviation'].tolist()
            abbrev_set = set(abbreviations)
            for token in raw_annotation_columns.split(','):
                token = token.strip()
                if not token:
                    continue
                if token in abbrev_set:
                    init_selected_cols.append(token)
                else:
                    match = get_abbr_of(token, descriptions, abbreviations)
                    init_selected_cols.append(match if match else token)
        else:
            # Default: the first 10 abbreviations (matching the annotation
            # table's own default selection).
            first_10 = annotation_desc_extended.head(10)
            if 'Abbreviation' in first_10.columns:
                init_selected_cols = first_10['Abbreviation'].dropna().tolist()

    # PCA tab (always present): the plots, or the eigenvec loader if no data yet.
    tab_configs.append({
        'label': 'PCA',
        'value': 'pca_tab',
        'content': create_pca_tab(
            pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT,
            df, init_aesthetics, ANNOTATION_LONG, annotation_columns, continuous_columns, annotation_desc,
            init_selected_ids,
            dropdown_group_symbol_list=dropdown_group_symbol_list or dropdown_group_list,
            init_group_symbol=init_group_symbol,
            map_initially_visible=map_initially_visible,
            time_initially_visible=time_initially_visible,
            legend_mode=getattr(args, 'legend', 'Once'),
            time_invert_columns=time_invert_columns,
            time_rotate_columns=time_rotate_columns,
            init_pc_x=init_pc_x,
            init_pc_y=init_pc_y,
            init_pc_z=init_pc_z,
            init_time_viz_mode=init_time_viz_mode,
            init_time_bin_size=init_time_bin_size,
            init_3d=getattr(args, 'pca_3d', False),
            init_time_group_mode=getattr(args, 'time_group_mode', 'group'),
            init_map_type=getattr(args, 'map_type', 'map'),
        ) if df is not None else eigenvec_loader_panel(args)
    })

    # Annotation tab (always present): the table, or the annotation loader.
    tab_configs.append({
        'label': 'Annotation',
        'value': 'annotation_tab',
        'content': create_annotation_tab(annotation_desc, annotation_columns, pcs,
                                         init_selected_cols=init_selected_cols)
                   if annotation_desc is not None
                   else annotation_loader_panel(
                       args, show_embedded_option=(has_embedded_annotation_cols or df is None),
                       has_embedded_annotation_cols=has_embedded_annotation_cols,
                   )
    })

    # The map/time panels exist (show_map_plot/show_time_plot) whenever
    # annotation data is loaded at all — matching app.py/callbacks/__init__.py
    # — regardless of whether --latitude/--longitude/--time were given;
    # map_initially_visible/time_initially_visible (whether they were) only
    # decide the panel's/checkbox's starting state, not whether it exists.
    # Needed here (not just in create_pca_tab) for the Settings tab's own
    # panel show/hide checkboxes and Equivalent command section.
    show_map_plot = df is not None and annotation_desc is not None
    show_time_plot = df is not None and annotation_desc is not None

    # Raw eigenvec column names, for the Settings tab's eigenvecID dropdown
    # (layouts/setup.py:settings_panel) — the ID column itself gets renamed
    # to 'id' once loaded (data_loader.load_eigenvec), so its original name
    # isn't recoverable from df/pcs; a header-only reread is cheap and keeps
    # that dropdown showing the file's actual columns, like the eigenvec
    # loader's own picker does right after Read.
    eigenvec_columns = []
    if args.eigenvec and os.path.isfile(args.eigenvec):
        try:
            from ..data_loader import detect_eigenvec_sep
            eigenvec_columns = list(
                pd.read_csv(args.eigenvec, sep=detect_eigenvec_sep(args.eigenvec), nrows=0).columns
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning("Could not read eigenvec columns for Settings: %s", exc)

    # Settings tab (always present): the other CLI options.
    tab_configs.append({
        'label': 'Settings',
        'value': 'settings_tab',
        'content': settings_panel(
            args, show_map_plot=show_map_plot, show_time_plot=show_time_plot,
            show_annotation_table=annotation_desc is not None,
            map_initially_visible=map_initially_visible,
            time_initially_visible=time_initially_visible,
            eigenvec_columns=eigenvec_columns,
            annotation_desc=annotation_desc,
        )
    })

    # Help tab
    from ..args import create_parser
    parser = create_parser()
    
    # Same header style as the Annotation tab's "Annotation Description" title
    # (layouts/__init__.py:create_annotation_tab) — kept identical here for
    # a consistent look across the app's section titles.
    _title_style = {'marginBottom': '20px'}

    user_guide_panel = dbc.Card([
        dbc.CardBody([
            html.P([
                'interactivePCA is a Dash web app for interactively exploring PCA/MDS results from '
                'population-genetics data. It links four views — a 2D/3D PCA scatter plot, a geographic map, '
                'a time plot, and an annotation table — so selection, hover highlighting, and point styling '
                'stay synchronized across all of them.'
            ]),

            html.H3('Main features: the four panels', style=_title_style),

            html.H3('PCA plot', style=_title_style),
            html.P([
                'Pick any two (or three, in 3D) continuous columns for the X/Y/Z axes from the dropdowns above '
                'the plot. ', html.Strong('3D'), ' toggles a rotatable ', html.Code('Scatter3d'), ' view. The '
                'PCA plot isn\u2019t limited to PCs \u2014 it can visualize any 2D or 3D scatter of continuous columns.'
            ]),

            html.H3('Geographic map', style=_title_style),
            html.P([
                'Shown once latitude/longitude columns are resolved (via ', html.Code('--latitude'), '/',
                html.Code('--longitude'), ', or picked live from the ', html.Strong('X:'), '/', html.Strong('Y:'),
                ' dropdowns). ', html.Strong('Basemap'), ' switches between ', html.Code('map'),
                ' (world outline), ', html.Code('tiles'), ' (interactive street/satellite imagery), and ',
                html.Code('none'), ' (points only). Despite the name, this panel isn\u2019t limited to showing a '
                'geographic map \u2014 the same X:/Y: dropdowns can plot any two continuous columns as an '
                'ordinary 2D scatter.'
            ]),

            html.H3('Time plot', style=_title_style),
            html.P([
                'Plots any continuous column (not only the ', html.Code('--time'), ' column); the other axis is '
                'either a jitter of the samples or the column\u2019s distribution, depending on the view. ',
                html.Strong('View'), ' switches between Scatter, Violin, Distribution and Overlay. In Scatter '
                'and Violin, ', html.Strong('Grouping'), ' controls whether samples are split by group, when ',
                html.Strong('Color by'), ' is a categorical column. ', html.Strong('Bin size'), ' sets the '
                'histogram bin width (Distribution/Overlay only). Overlay adds the selected samples\u2019 own '
                'distribution on top of the full one, where Distribution only ever shows the full histogram. ',
                html.Strong('Invert'), ' flips the axis direction (useful for e.g. a BP date column), ',
                html.Strong('Rotate'), ' swaps X/Y, and ', html.Strong('Time slice'), ' adds a draggable window '
                'that selects only the samples falling inside it \u2014 drag it, or use the arrows beside it, to '
                'scroll through time and watch the selected samples change live in the PCA and map panels.'
            ]),

            html.H3('Annotation table', style=_title_style),
            html.P([
                'Lists every sample with the metadata columns. To improve readability, the columns shown can be '
                'chosen in the ', html.Strong('Annotation'), ' tab (or via ', html.Code('--annotation-columns'),
                '). The same selected columns are also shown when hovering over a sample. Detailed hover is the '
                'default and can be suppressed via the ', html.Strong('Hover detailed'), ' toggle in the '
                'Settings tab, or at launch with ', html.Code('--hover-minimal'), '. This panel also has two '
                'other sub-tabs: ', html.Strong('Details'), ', which shows the full hover information for the '
                'currently hovered sample, and ', html.Strong('Filter'), ', which doesn\u2019t hide any rows in '
                'the table \u2014 instead it sets the selection to the samples matching a pandas ',
                html.Code('query()'), ' expression (e.g. ', html.Code('Age > 1000 & Country == "Peru"'),
                '), exactly like any other selection method; the table\u2019s Status column, and every other '
                'panel, then reflects that selection.'
            ]),

            html.H3('Cross-panel synchronization', style=_title_style),
            html.P([
                'The group coloring and shape set by ', html.Strong('Color by'), ' and ', html.Strong('Shape by'),
                ' apply simultaneously to all plots.'
            ]),
            html.P([
                'Hovering any sample \u2014 in the PCA plot, the map, the time plot, or an annotation table row '
                '\u2014 highlights that same sample in the other panels, with a minimal \u201cID\u201d tooltip '
                'regardless of the ', html.Strong('Hover detailed'), ' setting.'
            ]),
            html.P([
                'The legend for color and shape is shown only once by default. This can be adjusted via ',
                html.Strong('Legend mode'), ' (Settings tab, or the live dropdown): ', html.Code('none'),
                ' hides it everywhere, ', html.Code('once'), ' shows it on a single active plot at a time, ',
                html.Code('everywhere'), ' shows it on every panel that has one, simultaneously.'
            ]),

            html.H3('Grouping / coloring and aesthetics', style=_title_style),
            html.P([
                html.Strong('Color by'), ' groups/colors by any continuous or categorical column, including the '
                'PCs. ', html.Strong('Shape by'), ' groups any categorical column by shape. The aesthetics of '
                'every grouping and coloring can be individually adapted, as well as the aesthetics of the '
                'unselected points. Click ', html.Strong('Aesthetics'), ' to open the editor for the current '
                'Color-by/Shape-by column:'
            ]),
            html.Ul([
                html.Li([html.Strong('Categorical group: '), 'a table with one row per category \u2014 edit '
                         'color, size, opacity and symbol per value, and drag rows to set the draw order '
                         '(row 1 draws last, i.e. on top).']),
                html.Li([html.Strong('Continuous group: '), 'pick a color scale (Viridis, Plasma, ...) instead '
                         'of per-value colors.']),
                html.Li([html.Strong('Shape-by'), ' (a second, independent grouping): assigned its own marker '
                         'symbols, shown as a second legend block.']),
            ]),
            html.P([
                'Changes apply immediately to all three plots. Save a configuration to a JSON file for reuse '
                'with ', html.Code('--aesthetics-file'), ', or set simple global defaults once via ',
                html.Code('--point-color'), ', ', html.Code('--point-size'), ', ', html.Code('--point-opacity'),
                ', ', html.Code('--point-symbol'), ' (and their ', html.Code('-unselected'),
                ' counterparts) at launch.'
            ]),

            html.H3('Selection', style=_title_style),
            html.P([
                'Sample selection can be made on any plot or the table, and the selected samples are '
                'immediately synchronized to the other plots and table. Selecting groups or samples can be '
                'done in several ways:'
            ]),
            html.Ul([
                html.Li([html.Strong('Legend: '), 'use Plotly\u2019s built-in legend \u2014 click (or '
                         'double-click) a legend entry to hide/show that group everywhere.']),
                html.Li([html.Strong('Lasso'), ' or ', html.Strong('box-select'), ' allows selecting multiple '
                         'samples in any of the figures.']),
                html.Li([html.Strong('Row selection'), ' in the table allows selecting one or multiple '
                         'samples.']),
                html.Li([html.Strong('Filter'), ' allows selecting samples using a pandas ', html.Code('query()'),
                         ' expression (e.g. ', html.Code('Age > 1000 & Country == "Peru"'), ').']),
                html.Li([html.Strong('Time slice'), ' in the time plot allows selecting samples within a given '
                         'time window, and dragging that window left/right to scroll through time.']),
            ]),
            html.P([
                'The ', html.Strong('Selection'), ' frame shows the number of selected samples and lets you ',
                html.Strong('Freeze'), ' the selection (so no other control \u2014 lasso, filter, time-slice, '
                'Reset \u2014 can change it until unfrozen) or ', html.Strong('Save selection'), ' as a '
                'plain-text file of sample IDs, for use outside the app. It also reports which method last '
                'produced the current selection, since each new selection \u2014 lasso, filter, row click, '
                'time-slice, etc. \u2014 replaces the previous one rather than combining with it.'
            ]),

            html.H3('Session', style=_title_style),
            html.P([
                'An ongoing session can be stored and picked up later. There are three different ways to do '
                'this, each keeping a different amount of state:'
            ]),
            html.Ul([
                html.Li([html.Strong('Save view: '), 'downloads a ', html.Code('session.json'), ' holding the '
                         'full launch configuration plus the current view \u2014 selection, aesthetics, axes, '
                         'pane sizes and zoom. Reload it with ', html.Code('--session file.json'), ' or the '
                         'setup wizard\u2019s \u201cOr load a saved session\u201d option to continue on the '
                         'exact same view next time.']),
                html.Li([html.Strong('Export Snapshot: '), 'downloads a self-contained ',
                         html.Code('interactivePCA_<timestamp>.html'), ' file \u2014 the current PCA, map and '
                         'time figures plus the annotation table and selection, built directly from what\u2019s '
                         'on screen, no server round-trip. It needs no running Dash server to open: hover sync, '
                         'legend-click sync, cross-plot lasso/box-select syncing, and a sortable/filterable '
                         'table all work standalone, ported to plain JavaScript (Plotly.js and AG Grid are '
                         'pulled from a CDN). Not included: the live aesthetics editor and the pandas filter '
                         'query, both unsafe/impractical to reproduce without a server \u2014 colors are frozen '
                         'as they appeared at export time, and AG Grid\u2019s own column sort/filter covers '
                         'narrowing rows instead. Handy for sharing a point-in-time view with colleagues who '
                         'don\u2019t run the app themselves.']),
                html.Li([html.Strong('Generate command: '), 'produces the ', html.Code('interactivePCA ...'),
                         ' command line for the current setup; the full variant lists every parameter, not '
                         'just non-defaults. It covers the data configuration \u2014 files, columns, axes, '
                         'grouping \u2014 but not aesthetics or zoom, so it suits sharing a setup with '
                         'colleagues or scripting a launch.']),
                html.Li([html.Strong('Restart'), ' (top-right of the header) returns to the setup wizard '
                         'without losing non-data settings like the server port.']),
            ]),

            html.H3('Launching interactivePCA', style=_title_style),
            html.P([
                'interactivePCA can be launched several different ways, depending on how much you specify up '
                'front \u2014 from nothing at all (a point-and-click setup wizard) to a fully explicit command '
                'line:'
            ]),
            html.Ul([
                html.Li([html.Strong('No arguments'), ' (', html.Code('interactivePCA'), '): opens a setup '
                         'wizard instead of the plots. The PCA tab lets you type or browse to an eigenvec file '
                         'and ', html.Strong('Read'), ' its columns, the Annotation tab does the same for an '
                         'annotation file, and ', html.Strong('Settings'), ' holds every other option; each '
                         'tab\u2019s ', html.Strong('Load'), '/', html.Strong('Apply'), ' button relaunches the '
                         'app with those settings composed into the command line, so the result is identical '
                         'to typing that full command yourself.']),
                html.Li([html.Strong([html.Code('--eigenvec'), ' only']), ': starts with the PCA plot already '
                         'showing; the Annotation tab still offers its loader, unless the eigenvec file itself '
                         'has extra columns (see below).']),
                html.Li([html.Strong('Annotation embedded in the eigenvec file'), ': if ', html.Code('--annotation'),
                         ' is omitted but the eigenvec file has extra, non-coordinate columns, the Annotation '
                         'tab offers \u201cUse annotations from eigenvec file\u201d to use them directly instead '
                         'of reading a separate file.']),
                html.Li([html.Strong('Fully specified'), ', e.g. ',
                         html.Code('--eigenvec samples.eigenvec --annotation samples.anno --latitude Lat. '
                                   '--longitude Long. --time Date'),
                         ': every panel resolves immediately, no wizard step needed \u2014 see the walkthrough '
                         'below.']),
                html.Li([html.Strong(html.Code('--session file.json')), ': resumes a previously saved session '
                         '(see ', html.Strong('Save view'), ' above) exactly where it left off, including '
                         'selection, aesthetics, axes, pane sizes and zoom.']),
                html.Li([html.Strong('Single PCA plot'), ': if no annotation is passed, or the columns for the '
                         'geographic map (', html.Code('--latitude'), '/', html.Code('--longitude'), ') or the '
                         'time plot (', html.Code('--time'), ') aren\u2019t defined, only the PCA plot is shown. '
                         'To add the geographic map or time plot during a session, enable it in the Settings '
                         'tab and then pick which columns to show.']),
                html.Li(['Useful regardless of the above: ', html.Code('--dev'), ' enables debug mode and '
                         'verbose logging, ', html.Code('--open-browser'), ' opens the app in a browser '
                         'automatically, and ', html.Code('--help'), ' lists every option.']),
            ]),

            html.H3('Quick-start walkthrough', style=_title_style),
            html.P('A worked example for an ancient-DNA dataset with coordinates and dates:'),
            html.Ol([
                html.Li([
                    html.P([html.Strong('Launch'), ' with everything resolved up front:']),
                    html.Pre(
                        'interactivePCA --eigenvec samples.eigenvec --annotation samples.anno \\\n'
                        '  --latitude Lat. --longitude Long. --time Date',
                        style={'backgroundColor': '#f8f9fa', 'padding': '8px', 'fontFamily': 'monospace',
                               'fontSize': '13px', 'whiteSpace': 'pre-wrap'}
                    ),
                    html.P(['Or launch with just ', html.Code('--eigenvec'), ' and use the setup wizard\u2019s ',
                            html.Strong('Read'), ' / ', html.Strong('Load'), ' buttons on the PCA and '
                            'Annotation tabs instead.']),
                ]),
                html.Li([html.Strong('Explore structure: '), 'on the PCA tab, set ', html.Strong('Color by'),
                         ' to a region/population column; open ', html.Strong('Aesthetics'), ' to assign '
                         'clearer colors and reorder overlapping groups.']),
                html.Li([html.Strong('Check geography: '), 'switch to the Map sub-panel; try the ',
                         html.Code('tiles'), ' basemap for a familiar street/satellite view.']),
                html.Li([html.Strong('Check chronology: '), 'on the Time plot, switch ', html.Strong('View'),
                         ' to Distribution and adjust ', html.Strong('Bin size'), '; enable ',
                         html.Strong('Time slice'), ' and drag the window to watch clusters appear/disappear '
                         'through time \u2014 the PCA and map panels highlight the same samples live.']),
                html.Li([html.Strong('Cross-check a sample: '), 'hover any sample in any panel \u2014 or click '
                         'its row in the Annotation table \u2014 to see it highlighted everywhere else.']),
                html.Li([html.Strong('Save your work: '), 'click ', html.Strong('Save view'), ' to download a ',
                         html.Code('session.json'), ' capturing the exact state (including aesthetics and '
                         'zoom), or use ', html.Strong('Generate command'), ' to copy a CLI command for '
                         'colleagues who just need the data configuration.']),
            ]),

            html.H3('Tips, troubleshooting and command-line reference', style=_title_style),
            html.Ul([
                html.Li('Use lasso or box selection on any plot to highlight the same samples everywhere, '
                        'including the annotation table.'),
                html.Li('The annotation table\u2019s \u201cStatus\u201d column (selected/unselected/hidden) can '
                        'also be edited directly to change selection or hide a row\u2019s group from the '
                        'legend.'),
                html.Li('Column names referencing annotation data can be given as either their original header '
                        'or their abbreviated working name \u2014 both resolve to the same column.'),
                html.Li(['A command rejected with \u201cinvalid choice\u201d for an aesthetics parameter '
                         '(point size/opacity/symbol, color scale) means the value isn\u2019t one of the '
                         'app\u2019s preset options; check ', html.Code('--help'), ' for the exact list.']),
                html.Li('If a relaunch (Refresh/Restart/Load) doesn\u2019t return, check the terminal/log \u2014 '
                        'it most likely crashed on a data-loading error and needs a fix before trying again.'),
            ]),
            html.P('For the complete, always-current list of parameters, run:'),
            html.Pre(
                'interactivePCA --help',
                style={'backgroundColor': '#f8f9fa', 'padding': '8px', 'fontFamily': 'monospace',
                       'fontSize': '13px', 'whiteSpace': 'pre-wrap'}
            ),
        ]),
    ], className='mb-3')

    params_panel = dbc.Card([
        dbc.CardBody([
            html.Pre(
                strip_ansi(parser.format_help()),
                style={
                    'backgroundColor': '#f8f9fa',
                    'padding': '10px',
                    'fontFamily': 'monospace',
                    'fontSize': '14px',
                    'whiteSpace': 'pre-wrap'
                }
            )
        ]),
    ], className='mb-3')

    # Same bounded-height + overflowY:'auto' pattern as the Settings tab
    # (layouts/setup.py:settings_panel) — each panel scrolls independently
    # within its own column, rather than the whole tab growing to fit
    # whichever panel (the parameter list, usually) is taller. The title sits
    # outside that scrolling area (a sibling above it, not inside the Card),
    # so it stays pinned in view while the panel's own content scrolls.
    _help_panel_col_style = {'flex': '1 1 0', 'minWidth': '0', 'display': 'flex', 'flexDirection': 'column'}
    _help_scroll_style = {'maxHeight': 'calc(100vh - 160px)', 'overflowY': 'auto'}
    # These titles sit outside the Card (see above), which otherwise left-aligns
    # them with the Card's own edge instead of the CardBody text inside it —
    # offset by Bootstrap's default card-body padding (--bs-card-spacer-x) to
    # line them up with that text.
    _help_title_style = {**_title_style, 'paddingLeft': '1.25rem'}
    help_content = html.Div(
        [
            html.Div([
                html.H3('User guide', style=_help_title_style),
                html.Div(user_guide_panel, style=_help_scroll_style),
            ], style=_help_panel_col_style),
            html.Div([
                html.H3('Command-line parameters', style=_help_title_style),
                html.Div(params_panel, style=_help_scroll_style),
            ], style=_help_panel_col_style),
        ],
        style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '16px', 'padding': '20px'},
    )

    tab_configs.append({
        'label': 'Help',
        'value': 'help_tab',
        'content': help_content
    })
    
    # Initialize store with all available aesthetics (from file + defaults for init_group)
    init_store_data = {}
    
    # Load all aesthetics from file if provided
    all_file_aesthetics = {}
    if args.aesthetics_file:
        all_file_aesthetics = load_aesthetics_file(args.aesthetics_file)
    
    # Add init_group with merged aesthetics
    init_store_data[init_group] = init_aesthetics
    
    # Add all other groups from file (if not already added)
    for group_name in all_file_aesthetics:
        if group_name != init_group:
            # Create base aesthetics for this group and merge with file
            base_aesthetics = get_init_aesthetics(args, group_name, df)
            init_store_data[group_name] = merge_aesthetics(base_aesthetics, all_file_aesthetics[group_name])
    
    # init_selected_cols is already computed above (--annotation-columns or
    # the first-10 default), shared with the Annotation tab's own table.

    # Main layout
    layout = html.Div([
        # Data stores
        dcc.Store(id='selected-ids', data=init_selected_ids),
        dcc.Store(id='selected-source', data='initial'),
        dcc.Store(id='marker-aesthetics-store', data=init_store_data),
        dcc.Store(id='selection-store', data=init_selected_ids),  # Selected IDs for cross-plot sync
        dcc.Store(id='hover-detailed', data=not getattr(args, 'hover_minimal', False)),  # Toggle for detailed hover information (detailed by default; seeded from --hover-minimal, see hover-detailed-toggle in Settings)
        dcc.Store(id='selected-annotation-columns', data=init_selected_cols),  # Selected columns from annotation table
        dcc.Store(id='hover-sync-dummy', data=None),  # Dummy output for hover-sync clientside callback
        dcc.Store(id='hidden-groups-store', data={}),  # Group values hidden via legend click
        dcc.Store(id='symbol-aesthetics-store', data={}),  # Symbol mappings for shape group
        dcc.Store(id='save-trigger-store', data=0),       # Incremented on every aesthetics save
        dcc.Store(id='right-panel-tabs-dummy', data=None),  # Dummy output for right-panel tab switching
        dcc.Store(id='effective-hover-detailed', data=False),  # hover-detailed overridden to False when Details tab active
        dcc.Store(id='map-view-store', data=None),  # Current map view bbox, preserved across basemap toggle
        dcc.Store(id='time-window-store', data={'enabled': False, 'lo': None, 'hi': None}),  # Time-slice window bounds, for the shaded band on the time plot
        dcc.Store(id='legend-target-store', data='pca'),  # Which plot ('pca'/'time'/'map') currently hosts the group-colour legend
        dcc.Store(id='selection-frozen', data=False),  # While True, every selection-store writer becomes a no-op
        dcc.Store(id='session-init-store', data=init_session),  # Saved --session view, applied once on load
        dcc.Store(id='session-restore-dummy', data=None),  # Dummy output for the session-restore clientside callback
        dcc.Store(id='pca-view-store', data=None),  # Current PCA plot zoom/pan/camera (relayoutData), for Save view
        dcc.Store(id='time-view-store', data=None),  # Current time plot zoom/pan (relayoutData), for Save view
        dcc.Store(id='pane-sizes-store', data={}),  # Draggable pane split percentages, keyed by resizer id
        dcc.Store(id='aesthetics-drag-dummy', data=None),  # Dummy output for the aesthetics-panel drag-init clientside callback
        dcc.Store(id='map-fill-dummy', data=None),  # Dummy output for the geo pane-fill clientside callback
        # File-loader stores + browser modal (Restart and the tab loaders relaunch through these)
        *setup_stores(),
        file_browser_modal(),
        about_modal(),
        dcc.Download(id='download-snapshot'),
        dcc.Download(id='download-session'),
        dcc.Download(id='download-selection'),

        # Header with tabs
        html.Div([
            html.Img(
                src='/assets/logo.svg',
                id='app-logo',
                title='About interactivePCA',
                n_clicks=0,
                style={
                    'height': '40px',
                    'width': '40px',
                    'marginLeft': '20px',
                    'marginRight': '12px',
                    'marginTop': '5px',
                    'marginBottom': '5px',
                    'verticalAlign': 'middle',
                    'cursor': 'pointer'
                }
            ),
            html.H2("interactivePCA", style={
                'display': 'inline-block',
                'margin': '0',
                'marginRight': '30px',
                'lineHeight': '60px',
                'fontSize': '24px',
                'verticalAlign': 'bottom'
            }),
            html.Div(
                dcc.Tabs(
                    id='tabs',
                    value='pca_tab',
                    children=[
                        dcc.Tab(
                            label=config['label'],
                            value=config['value'],
                            style={'padding': '10px 18px', 'minWidth': '120px'},
                            selected_style={'padding': '10px 18px', 'minWidth': '120px'}
                        )
                        for config in tab_configs
                    ]
                ),
                style={
                    'display': 'inline-block',
                    'verticalAlign': 'bottom'
                }
            ),
            # Restart → relaunch the process with no data → the setup wizard.
            dbc.Button(
                'Restart', id='restart-btn', color='danger', outline=True,
                n_clicks=0, title='Return to the setup page',
                style={'float': 'right', 'marginRight': '20px', 'marginTop': '14px',
                      'fontSize': '14px'},
            ),
            # Relaunching takes a couple of seconds (new process + the
            # poller waiting for it to come back up, see relaunch.py) with no
            # other visual change in the meantime — this is the only sign
            # anything happened until the page reloads itself.
            html.Div(id='restart-status', style={'float': 'right', 'marginRight': '8px', 'marginTop': '14px'}),
            html.Button(
                'Export snapshot',
                id='export-snapshot-btn',
                title='Save current figures as a standalone HTML file',
                style={
                    'float': 'right', 'marginRight': '8px', 'marginTop': '14px',
                    'padding': '6px 12px', 'fontSize': '14px',
                    'border': '1px solid #0066cc',
                    'borderRadius': '4px',
                    'backgroundColor': '#e8f0fe',
                    'color': '#0066cc',
                    'cursor': 'pointer'
                }
            ),
            html.Button(
                'Save view',
                id='save-view-btn',
                title="Save everything needed to reopen this exact run — eigenvec/"
                      "annotation/settings plus selection, grouping, aesthetics, "
                      "axes, map, time-plot and panel sizes — to a timestamped "
                      "session_<date>_<time>.json, downloaded via the browser "
                      "(so you pick where it lands) and also kept server-side "
                      "for --session/the eigenvec tab's 'Load session'.",
                style={
                    'float': 'right', 'marginRight': '8px', 'marginTop': '14px',
                    'padding': '6px 12px', 'fontSize': '14px',
                    'border': '1px solid #0066cc',
                    'borderRadius': '4px',
                    'backgroundColor': '#e8f0fe',
                    'color': '#0066cc',
                    'cursor': 'pointer'
                }
            ),
        ], style={
            'backgroundColor': '#f8f9fa',
            'borderBottom': '2px solid #dee2e6',
            'height': '60px',
            'whiteSpace': 'nowrap'
        }),
        
        # Tab content area - all tabs rendered, visibility toggled
        html.Div(
            id='tabs-content',
            style={
                'padding': '20px',
                'height': 'calc(100vh - 60px)',
                'overflow': 'hidden',
                'display': 'flex',
                'flexDirection': 'column'
            },
            children=[
                html.Div(
                    id=f"{config['value']}_content",
                    children=config['content'], 
                    style={
                        'display': 'block' if i == 0 else 'none',
                        'height': '100%'
                    }
                )
                for i, config in enumerate(tab_configs)
            ]
        )
    ], style={'height': '100vh', 'display': 'flex', 'flexDirection': 'column'})
    
    return {'layout': layout}


def _pca_axis_columns(pcs, continuous_columns):
    """Columns offered on the PCA plot's X/Y/Z axes: the PCA dimensions first
    (the common case and the defaults), then any other continuous column not
    already among them.
    """
    return list(pcs) + [c for c in (continuous_columns or []) if c not in pcs]


def _dropdown_width(labels, min_px=90, char_px=7.2, padding_px=50):
    """Width sized to the longest option actually offered, rather than a
    guessed fixed pixel value — column names are already bounded by
    --col-abbrev, so the longest one is known here."""
    longest = max((len(str(l)) for l in labels), default=0)
    return f'{max(min_px, round(longest * char_px + padding_px))}px'


def create_pca_tab(pcs, dropdown_group_list, init_group, ANNOTATION_TIME, ANNOTATION_LAT,
                   df, aesthetics, ANNOTATION_LONG=None, annotation_columns=None, continuous_columns=None, annotation_desc=None, init_selected_ids=None,
                   dropdown_group_symbol_list=None, init_group_symbol='none',
                   map_initially_visible=False, time_initially_visible=False, legend_mode='Once',
                   time_invert_columns=frozenset(), init_pc_x=None, init_pc_y=None,
                   init_time_viz_mode='scatter', init_time_bin_size=None,
                   time_rotate_columns=frozenset(), init_pc_z=None,
                   init_3d=False, init_time_group_mode='group', init_map_type='map'):
    """Create PCA tab layout with map on the right and extra panels below."""
    # Determine if legend should be shown initially (only if group has multiple
    # unique values and --legend doesn't start out suppressing it entirely —
    # see settings2-legend-mode in the Settings tab for the live control).
    init_legend = False
    if legend_mode != 'None' and init_group != 'none' and init_group in df.columns:
        n_unique = df[init_group].nunique()
        if n_unique > 1:
            init_legend = True

    # --pc-x/--pc-y/--pc-z (any axis column, not just a PC — see
    # _pca_axis_columns) seed the PCA plot's initial X/Y/Z, falling back to
    # the first three PCs when unset or invalid, same convention as
    # dropdown-pc-x/-y/-z further below.
    axis_columns = _pca_axis_columns(pcs, continuous_columns)
    pc_x_value = init_pc_x if init_pc_x in axis_columns else pcs[0]
    pc_y_value = init_pc_y if init_pc_y in axis_columns else pcs[1]
    pc_z_value = init_pc_z if init_pc_z in axis_columns else (pcs[2] if len(pcs) > 2 else pcs[0])

    # Generate initial PCA figure
    aesthetics_tuple = dict_of_dicts_to_tuple(aesthetics)
    init_fig = generate_fig_scatter2d(
        x_col=pc_x_value,
        y_col=pc_y_value,
        group=init_group,
        aesthetics_tuple=aesthetics_tuple,
        legend=init_legend
    )
    init_fig.update_layout(
        template='plotly_white',
        clickmode='event+select',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        title="",
        margin={'l': 20, 'r': 20, 't': 40, 'b': 20},
        dragmode='lasso',
        legend_title=init_group
    )
    
    # Generate initial map figure whenever annotation is loaded at all — if
    # ANNOTATION_LAT/ANNOTATION_LONG are None (no --latitude/--longitude
    # resolved yet), generate_map_fig_scattergeo already degrades gracefully
    # to a "coordinates not available" placeholder, so the panel still exists
    # (just hidden initially — see map_initially_visible) for Settings 2 to
    # populate live.
    init_map_fig = None
    if annotation_desc is not None:
        # Default to the Scattergeo map (consistent with the PCA/time plots);
        # a toggle lets the user switch to the tiled Scattermap at runtime.
        init_map_fig = generate_map_fig_scattergeo(
            group=init_group,
            aesthetics_tuple=aesthetics_tuple,
            legend=False,
            lat_col=ANNOTATION_LAT,
            lon_col=ANNOTATION_LONG
        )
        # Apply layout settings to prevent rescaling when callback fires
        is_categorical = (
            init_group != 'none'
            and init_group in df.columns
            and df[init_group].dtype.kind not in 'fi'
        )
        init_map_fig.update_layout(
            autosize=True,
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(
                x=1.02 if is_categorical else 0.02,
                y=1 if is_categorical else 0.98,
                xanchor='left',
                yanchor='top'
            ),
            dragmode='lasso',
            hoverlabel=dict(
                bgcolor='white',
                font_color='#333',
                namelength=-1
            )
        )
    
    # Apply initial selection to figures if provided
    if init_selected_ids:
        # Convert all IDs to strings for consistent comparison
        selected_set = set(str(sid) for sid in init_selected_ids)
        
        # Apply to PCA figure
        init_fig_dict = init_fig.to_dict()
        for trace in init_fig_dict.get('data', []):
            customdata = trace.get('customdata', [])
            if len(customdata) > 0 and selected_set:
                customdata_str = np.array([str(cd) for cd in customdata])
                mask = np.isin(customdata_str, list(selected_set))
                trace['selectedpoints'] = np.where(mask)[0].tolist()
        init_fig = init_fig_dict
        
        # Apply to map figure if available
        if init_map_fig is not None:
            init_map_dict = init_map_fig.to_dict() if hasattr(init_map_fig, 'to_dict') else init_map_fig
            for trace in init_map_dict.get('data', []):
                customdata = trace.get('customdata', [])
                if len(customdata) > 0 and selected_set:
                    customdata_str = np.array([str(cd) for cd in customdata])
                    mask = np.isin(customdata_str, list(selected_set))
                    trace['selectedpoints'] = np.where(mask)[0].tolist()
            init_map_fig = init_map_dict
    
    # Control section (grouping + selection actions — axis controls live above the PCA plot)
    control_section = html.Div([
        # Left side controls — same bordered "notch" box pattern as the
        # Selection box on the right (see its own comment below for why a
        # plain Div + absolutely-positioned title is used instead of
        # html.Fieldset/Legend).
        html.Div([
            html.Span('Grouping / coloring', style={
                'position': 'absolute', 'top': '-9px', 'left': '10px',
                'backgroundColor': '#f8f9fa', 'padding': '0 6px',
                'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555',
            }),
            html.Div([
                html.Div([
                    html.Label('Color by:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='dropdown-group',
                        options=[{'label': g, 'value': g} for g in dropdown_group_list],
                        value=init_group,
                        clearable=False,
                        style={'width': '200px'}
                    ),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '8px'}),
                html.Div([
                    html.Label('Shape by:', style={'marginRight': '8px', 'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='dropdown-group-symbol',
                        options=[{'label': g, 'value': g} for g in (dropdown_group_symbol_list or dropdown_group_list)],
                        value=init_group_symbol,
                        clearable=False,
                        style={'width': '200px'}
                    ),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '16px'}),
                html.Button(
                    'Aesthetics',
                    id='open-aesthetics',
                    style={
                        'padding': '6px 12px',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'backgroundColor': '#ffffff',
                        'cursor': 'pointer'
                    }
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}),
        ], style={
            'position': 'relative', 'border': '1px solid #ccc', 'borderRadius': '4px',
            'padding': '10px 12px 8px', 'margin': '0', 'marginTop': '8px'
        }),

        # Right side controls
        # A plain bordered box with the title overlapping the top border,
        # rather than html.Fieldset/Legend — Bootstrap's own CSS overrides
        # <legend> to a full-width block, which kills the browser's native
        # "notch" that normally breaks the border behind the text, leaving
        # the line running right through it. The absolute-positioned title
        # + a background matching the surrounding control_section (#f8f9fa)
        # fakes that same notch instead.
        html.Div([
            html.Span('Selection', style={
                'position': 'absolute', 'top': '-9px', 'left': '10px',
                'backgroundColor': '#f8f9fa', 'padding': '0 6px',
                'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555',
            }),
            html.Div([
                html.Div(
                    id='selection-counter',
                    children='Selected: 0',
                    style={
                        'marginRight': '8px',
                        'fontSize': '13px',
                        'color': '#333',
                        'fontWeight': 'bold'
                    }
                ),
                html.Div(
                    id='selection-source-label',
                    children='',
                    title='What last changed the current selection',
                    style={
                        'marginRight': '8px',
                        'fontSize': '12px',
                        'color': '#777',
                        'fontStyle': 'italic'
                    }
                ),
                html.Button(
                    'Reset',
                    id='select-all-button',
                    title='Clear the current selection/time-slice and select every sample',
                    style={
                        'padding': '6px 12px',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'backgroundColor': '#ffffff',
                        'cursor': 'pointer'
                    }
                ),
                html.Button(
                    'Freeze',
                    id='freeze-selection-button',
                    title='Lock the current selection — every other selection control '
                          '(lasso, filters, time-slice, Reset) is ignored until unfrozen',
                    style={
                        'padding': '6px 12px',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'backgroundColor': '#ffffff',
                        'cursor': 'pointer'
                    }
                ),
                html.Button(
                    'Save selection',
                    id='save-selection',
                    style={
                        'padding': '6px 12px',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'backgroundColor': '#ffffff',
                        'cursor': 'pointer'
                    }
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}),
        ], style={
            'position': 'relative', 'border': '1px solid #ccc', 'borderRadius': '4px',
            'padding': '10px 12px 8px', 'margin': '0', 'marginTop': '8px'
        }),
    ], style={
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'space-between',
        'marginBottom': '20px',
        'padding': '12px 15px',
        'backgroundColor': '#f8f9fa',
        'borderRadius': '5px'
    })
    
    # PCA plot with axis control bar above it (mirrors the time-plot pattern)
    _lbl = {'fontWeight': 'bold', 'fontSize': '13px', 'marginRight': '6px'}
    _lbl_ml = {**_lbl, 'marginLeft': '12px'}
    # Axes are not restricted to the PCA dimensions: any continuous column can
    # go on X/Y/Z, so a PC can be plotted against age, latitude, coverage, etc.
    # (axis_columns/pc_x_value/pc_y_value already computed above, for the
    # initial figure.)
    _axis_options = [{'label': c, 'value': c} for c in axis_columns]
    _axis_style = {'width': _dropdown_width(axis_columns), 'fontSize': '13px'}
    pca_plot = html.Div([
        html.Div([
            html.Label('X:', style=_lbl),
            dcc.Dropdown(
                id='dropdown-pc-x',
                options=_axis_options,
                value=pc_x_value,
                clearable=False,
                style=_axis_style
            ),
            html.Label('Y:', style=_lbl_ml),
            dcc.Dropdown(
                id='dropdown-pc-y',
                options=_axis_options,
                value=pc_y_value,
                clearable=False,
                style=_axis_style
            ),
            html.Div([
                html.Label('Z:', style=_lbl_ml),
                dcc.Dropdown(
                    id='dropdown-pc-z',
                    options=_axis_options,
                    value=pc_z_value,
                    clearable=False,
                    style=_axis_style
                ),
            ], id='z-axis-container', style={'display': 'none', 'alignItems': 'center'}),
            dcc.Checklist(
                id='pca-3d-toggle',
                options=[{'label': ' 3D', 'value': 'enable_3d'}],
                value=['enable_3d'] if init_3d else [],
                style={'marginLeft': '12px'},
                labelStyle={'whiteSpace': 'nowrap', 'fontSize': '13px'}
            ),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'flex': '0 0 auto',
            'padding': '6px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px',
            'marginBottom': '4px'
        }),
        dcc.Graph(
            id='pca-plot',
            figure=init_fig,
            style={'flex': '1 1 0', 'minHeight': '0'},
            clear_on_unhover=True
        ),
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})

    # Optional panels — the map/time panels (and their callbacks) exist
    # whenever annotation data is loaded at all, not only once --latitude/
    # --longitude/--time happen to already resolve to real columns; whether
    # they START OUT visible is the separate map_initially_visible/
    # time_initially_visible flags (app.py), applied further down to the
    # panes' initial style. This lets the Settings 2 tab assign those columns
    # — and reveal the panel — live, with no restart.
    show_annotation_table = annotation_desc is not None
    show_map_plot = show_annotation_table
    show_time_plot = show_annotation_table

    # Time/continuous plot below PCA plot
    time_hist = html.Div()
    continuous_columns = continuous_columns or []
    # Natural (no-CLI-override) default for the time-plot bin size — only set
    # once a continuous column with actual values is found below; stays None
    # otherwise (e.g. no annotation at all), which is itself the correct
    # "nothing to default" answer for settings2-natural-defaults further down.
    default_bin_size = None
    # Prefer the resolved --time column; otherwise fall back to the first
    # available continuous column so the panel has *something* to show even
    # before the user assigns a real time column via Settings 2.
    if ANNOTATION_TIME is not None and ANNOTATION_TIME in df.columns:
        default_continuous = ANNOTATION_TIME
    else:
        default_continuous = continuous_columns[0] if continuous_columns else None
    if default_continuous is not None and default_continuous in df.columns:
        time_vals = df[default_continuous].dropna()
        if time_vals.empty:
            time_hist = html.Div(
                f"No valid values in {default_continuous} for distribution.",
                style={'padding': '10px', 'color': '#666'}
            )
        else:
            # Create initial scatter figure with jitter (matching default 'scatter' mode)
            fig_time = go.Figure()
            time_ids = df.loc[time_vals.index, 'id'].tolist()
            np.random.seed(42)
            jitter = np.random.uniform(-0.3, 0.3, size=len(time_vals))
            
            # Get default aesthetics from the initial settings passed in
            default_color = aesthetics['color'].get('default', 'steelblue')
            default_size = aesthetics['size'].get('default', 8)
            default_opacity = aesthetics['opacity'].get('default', 0.7)
            
            fig_time.add_trace(go.Scatter(
                x=time_vals,
                y=jitter,
                mode='markers',
                marker=dict(color=default_color, size=default_size, opacity=default_opacity),
                customdata=time_ids,
                hovertemplate='<b>ID:</b> %{customdata}<br><extra></extra>',
                name='All samples',
                showlegend=False
            ))
            
            fig_time.update_layout(
                xaxis_title=default_continuous,
                yaxis_title="",
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                template='plotly_white',
                autosize=True,
                dragmode='lasso',
                margin=dict(l=50, r=20, t=40, b=40),
                hoverlabel=dict(
                    bgcolor='white',
                    font_color='#333',
                    namelength=-1
                )
            )
            
            time_is_reversed = default_continuous in time_invert_columns
            if time_is_reversed:
                fig_time.update_xaxes(autorange='reversed')
            time_is_rotated = default_continuous in time_rotate_columns

            # Time-slice slider: bounds/defaults from the initial time-variable's
            # range; callbacks/selection.py recomputes these when the user
            # switches which continuous column the panel shows.
            time_min = float(time_vals.min())
            time_max = float(time_vals.max())
            time_span = time_max - time_min
            default_window_size = nice_step(time_span / 10) if time_span > 0 else 1
            slider_step = nice_step(time_span / 200) if time_span > 0 else 1
            # Distribution/Overlay histogram bin width — ~50 bins across the
            # range by default, rounded to a nice step (same convention as
            # the time-slice window above).
            default_bin_size = nice_step(time_span / 50) if time_span > 0 else 1
            # Round the bounds themselves outward to the nearest step too — a
            # step of 100 but bounds of 1450/13282 would still put every
            # position off the round grid (1450, 1550, ...). Widening is
            # always safe; it never excludes real data.
            bound_lo, bound_hi = nice_bounds(time_min, time_max, slider_step)
            default_hi = min(bound_lo + default_window_size, bound_hi)
            slider_min, slider_max = bound_lo, bound_hi
            slider_value = [bound_lo, default_hi]
            # min/max/value always stay in plain ascending order — rc-slider
            # maps them straight onto aria-valuemin/aria-valuemax, and a
            # swapped (min > max) config makes some browsers reject edits with
            # a native validation warning. The reversed-axis look (larger
            # values on the left, matching the graph) instead comes from the
            # RangeSlider's own `reverse` prop (a real Radix-slider feature —
            # `inverted` under the hood — not a CSS hack). Its built-in min/max
            # number inputs don't reorder themselves though, so
            # assets/time_slider.css swaps them via this className. The
            # prev/next arrows point away from the slider on whichever side
            # they end up on — reversed swaps which button (by id, since each
            # id's callback always moves the window the same raw direction)
            # lands on which side, via flex order, not by moving them in the DOM.
            prev_label, next_label = ('▶', '◀') if time_is_reversed else ('◀', '▶')
            prev_order, next_order = (4, 2) if time_is_reversed else (2, 4)
            slider_wrap_class = 'time-slider-reversed' if time_is_reversed else ''

            # Every control in this row shares one font (size + family) and is
            # wrapped in its own flex-centered group with the same spacing, so
            # labels/dropdowns/checkboxes/input all sit on one baseline instead
            # of drifting with each component's own default line-height —
            # dcc.Dropdown in particular doesn't otherwise inherit the page's
            # (Bootstrap) font the way dbc.Checkbox/html.Label do.
            _TF = {
                'fontSize': '13px',
                'fontFamily': ('-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
                              'Helvetica, Arial, sans-serif'),
            }
            _time_ctrl_group_style = {'display': 'flex', 'alignItems': 'center', 'marginRight': '16px'}

            def _time_ctrl_group(children, div_id=None, title=None, **extra_style):
                style = dict(_time_ctrl_group_style)
                style.update(extra_style)
                kwargs = {'style': style}
                if div_id is not None:
                    kwargs['id'] = div_id
                if title is not None:
                    kwargs['title'] = title
                return html.Div(children, **kwargs)

            _view_mode_labels = ['Scatter', 'Violin', 'Distribution', 'Overlay']
            _group_mode_labels = ['No group', 'Group', 'Group with name']

            time_hist = html.Div([
                html.Div([
                    html.Div(
                        [
                            _time_ctrl_group([
                                html.Label('Variable:', style={**_TF, 'marginRight': '8px', 'fontWeight': 'bold'}),
                                dcc.Dropdown(
                                    id='time-variable',
                                    options=[{'label': col, 'value': col} for col in continuous_columns],
                                    value=default_continuous,
                                    clearable=False,
                                    style={**_TF, 'width': _dropdown_width(continuous_columns)}
                                ),
                            ], marginRight='0'),
                            # Invert + Rotate + Time slice side by side below
                            # Variable. marginBottom: '0' overrides dbc.Checkbox's
                            # own default .form-check spacing (inline style
                            # always wins over its Bootstrap class), so they sit
                            # close together.
                            html.Div(
                                [
                                    # dbc.Checkbox has no `title` prop of its own — wrap it.
                                    html.Div(
                                        dbc.Checkbox(
                                            id='time-invert-toggle', value=time_is_reversed, label='Invert',
                                            style={**_TF, 'whiteSpace': 'nowrap', 'marginBottom': '0'},
                                        ),
                                        title='Reverse the axis direction. Set automatically for '
                                              'the actual --time column; change freely for any variable.',
                                    ),
                                    html.Div(
                                        dbc.Checkbox(
                                            id='time-rotate-toggle', value=time_is_rotated, label='Rotate',
                                            style={**_TF, 'whiteSpace': 'nowrap', 'marginBottom': '0'},
                                        ),
                                        title='Swap the x and y axes. Set automatically for columns '
                                              'listed in --time-rotate-columns; change freely for any variable.',
                                    ),
                                    dbc.Checkbox(
                                        id='time-window-enabled', value=False, label='Time slice',
                                        style={**_TF, 'whiteSpace': 'nowrap', 'marginBottom': '0'},
                                    ),
                                ],
                                style={'display': 'flex', 'flexDirection': 'row', 'alignItems': 'center', 'gap': '12px'},
                            ),
                        ],
                        style={'display': 'flex', 'flexDirection': 'column', 'alignItems': 'flex-start',
                              'gap': '4px', 'marginRight': '16px'},
                    ),
                    _time_ctrl_group([
                        html.Label('View:', style={**_TF, 'marginRight': '8px', 'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='time-viz-mode',
                            options=[{'label': l, 'value': l.lower()} for l in _view_mode_labels],
                            value=init_time_viz_mode,
                            clearable=False, searchable=False,
                            style={**_TF, 'width': _dropdown_width(_view_mode_labels)}
                        ),
                    ]),
                    # Revealed only for Scatter/Violin (see toggle_time_view_controls).
                    _time_ctrl_group(
                        [
                            html.Label('Grouping:', style={**_TF, 'marginRight': '8px', 'fontWeight': 'bold'}),
                            dcc.Dropdown(
                                id='time-group-mode',
                                options=[
                                    {'label': 'No group', 'value': 'none'},
                                    {'label': 'Group', 'value': 'group'},
                                    {'label': 'Group with name', 'value': 'group_named'},
                                ],
                                value=init_time_group_mode,
                                clearable=False, searchable=False,
                                style={**_TF, 'width': _dropdown_width(_group_mode_labels)},
                            ),
                        ],
                        div_id='time-group-mode-container',
                        title="'No group': one combined strip, still colored by group. "
                              "'Group': one strip per group (Scatter) or one violin per "
                              "group. 'Group with name': same, with the group name shown.",
                    ),
                    # Revealed only for Distribution/Overlay (see toggle_time_view_controls).
                    _time_ctrl_group(
                        [
                            html.Label('Bin size:', style={**_TF, 'marginRight': '8px', 'whiteSpace': 'nowrap'}),
                            dbc.Input(
                                id='time-bin-size', type='number',
                                value=init_time_bin_size if init_time_bin_size is not None else default_bin_size,
                                min=0, debounce=True,
                                style={**_TF, 'width': '90px'}
                            ),
                        ],
                        div_id='time-bin-size-container',
                        display='none',
                    ),
                ], style={**_TF, 'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px', 'padding': '8px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
                dcc.Graph(
                    id='time-histogram',
                    figure=fig_time,
                    style={'flex': '1', 'minHeight': '0'},
                    clear_on_unhover=True
                ),
                # Revealed only once "Time slice" above is checked (see
                # callbacks/selection.py:sync_time_window_to_selection).
                html.Div([
                    html.Label('Window size:', style={'marginRight': '8px', 'fontSize': '13px', 'whiteSpace': 'nowrap'}),
                    dbc.Input(
                        id='time-window-size', type='number', value=default_window_size,
                        step=slider_step, disabled=True, debounce=True,
                        style={'width': '110px', 'marginRight': '20px', 'fontSize': '13px'}
                    ),
                    dbc.Button(prev_label, id='time-window-prev-btn', size='sm', color='light',
                              disabled=True, className='me-2', style={'order': prev_order}),
                    html.Div(
                        dcc.RangeSlider(
                            id='time-window-range',
                            min=slider_min, max=slider_max, step=slider_step,
                            value=slider_value, reverse=time_is_reversed,
                            allowCross=False, marks={}, updatemode='mouseup', disabled=True,
                            tooltip={'placement': 'bottom', 'always_visible': False},
                        ),
                        id='time-window-slider-wrap',
                        className=slider_wrap_class,
                        style={'flex': '1', 'order': 3}
                    ),
                    dbc.Button(next_label, id='time-window-next-btn', size='sm', color='light',
                              disabled=True, className='ms-2', style={'order': next_order}),
                ], id='time-window-controls-row', className='p-2 mt-2 bg-light rounded',
                   style={'display': 'none', 'alignItems': 'center'}),
            ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})
    
    # Create left pane with optional time plot
    from ..components import LAYOUT_CONFIG
    if show_time_plot:
        pca_split = int(LAYOUT_CONFIG["pca_time_split"] * 100)
        time_split = 100 - pca_split

        left_pane = html.Div([
            html.Div(pca_plot, id='pca-plot-pane', style={'flex': f'0 0 {pca_split}%', 'overflow': 'hidden', 'padding': '5px'}),
            html.Div(
                id='pca-time-resizer',
                style={
                    'height': '8px',
                    'backgroundColor': '#bbb',
                    'cursor': 'row-resize',
                    'userSelect': 'none',
                    'flex': '0 0 8px',
                    'marginLeft': '5px',
                    'marginRight': '5px',
                    'transition': 'background-color 0.2s',
                    'position': 'relative',
                    'zIndex': 5,
                    'pointerEvents': 'auto',
                    **({'display': 'none'} if not time_initially_visible else {}),
                },
                title='Drag to resize panes'
            ),
            html.Div(time_hist, id='time-plot-pane', style={
                'flex': f'0 0 {time_split}%', 'overflow': 'hidden', 'padding': '5px',
                **({'display': 'none'} if not time_initially_visible else {}),
            })
        ], style={'display': 'flex', 'flexDirection': 'column', 'height': '100%', 'gap': '0'})
    else:
        left_pane = html.Div([
            html.Div(pca_plot, id='pca-plot-pane', style={'flex': '1 1 auto', 'overflow': 'hidden', 'padding': '5px'})
        ], style={'display': 'flex', 'flexDirection': 'column', 'height': '100%', 'gap': '0'})
    
    # Map plot (top right) + Annotation table (bottom right)
    map_plot = html.Div()
    if show_map_plot:
        # Lon/lat columns offered on the map's X/Y: same continuous columns the
        # PCA plot's axes offer, minus the PC dimensions themselves (a PC isn't
        # a coordinate) — prefilled from ANNOTATION_LONG/ANNOTATION_LAT, or
        # empty if --latitude/--longitude never resolved (the map panel exists
        # whenever annotation data is loaded at all, see show_map_plot above;
        # these dropdowns are then how the user picks real coordinate columns
        # live, no restart needed).
        geo_axis_columns = [c for c in (continuous_columns or []) if c not in pcs]
        _geo_axis_options = [{'label': c, 'value': c} for c in geo_axis_columns]
        _geo_axis_style = {'width': _dropdown_width(geo_axis_columns), 'fontSize': '13px'}
        _basemap_options = [{'label': c, 'value': c} for c in ('map', 'tiles', 'none')]
        map_controls = html.Div([
            html.Label('X:', style=_lbl),
            dcc.Dropdown(
                id='dropdown-map-x',
                options=_geo_axis_options,
                value=ANNOTATION_LONG,
                clearable=False,
                placeholder='(not set)',
                style=_geo_axis_style
            ),
            html.Label('Y:', style=_lbl_ml),
            dcc.Dropdown(
                id='dropdown-map-y',
                options=_geo_axis_options,
                value=ANNOTATION_LAT,
                clearable=False,
                placeholder='(not set)',
                style=_geo_axis_style
            ),
            html.Label('Basemap:', style=_lbl_ml),
            dcc.Dropdown(
                id='map-type-toggle',
                options=_basemap_options,
                value=init_map_type,
                clearable=False, searchable=False,
                style={'width': _dropdown_width([o['label'] for o in _basemap_options]), 'fontSize': '13px'}
            ),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'flex': '0 0 auto',
            'padding': '6px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px',
            'marginBottom': '4px'
        })
        map_plot = html.Div(
            [
                map_controls,
                dcc.Graph(
                    id='pca-map-plot',
                    figure=init_map_fig,
                    style={'flex': '1 1 auto', 'minHeight': 0},
                    clear_on_unhover=True,
                ),
            ],
            style={'display': 'flex', 'flexDirection': 'column', 'height': '100%'},
        )
    
    # Annotation table
    table_data = []
    if annotation_columns:
        table_cols = ['id'] + [col for col in annotation_columns if col in df.columns]
        table_data = df[table_cols].to_dict('records')
    
    column_defs = []
    if annotation_columns:
        for col in table_cols:
            if col == 'id':
                column_defs.append(create_standard_column_def(col, col, width=120, pinned='left'))
            else:
                column_defs.append(create_standard_column_def(col, col, minWidth=100))
    
    annotation_table = None
    if show_annotation_table:
        annotation_table = dag.AgGrid(
            id='pca-annotation-table',
            rowData=table_data,
            columnDefs=column_defs,
            defaultColDef={'resizable': True, 'sortable': True, 'filter': True},
            getRowId='params.data.id',
            dashGridOptions={
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False
            },
            style={'height': '100%', 'width': '100%'}
        )
    
    query_field = None
    if show_annotation_table:
        query_field = dcc.Textarea(
            id='pca-filter-query',
            placeholder='Enter pandas query (e.g. Age > 1000 & Country == "Peru")',
            style={
                'width': '100%',
                'flex': '1 1 0',
                'minHeight': '0',
                'fontFamily': 'monospace',
                'resize': 'none',
                'boxSizing': 'border-box'
            }
        )
    
    # Right pane: map (top, resizable) + 3-tab panel (Table / Details / Filter)
    tab_style = {'padding': '4px 12px', 'fontSize': '12px'}
    tab_selected_style = {'padding': '4px 12px', 'fontSize': '12px', 'fontWeight': 'bold'}

    def make_tab_panel(flex_style):
        """Build the 3-tab panel (Table / Details / Filter)."""
        return html.Div(id='table-plot-pane', children=[
            dcc.Tabs(
                id='right-panel-tabs',
                value='tab-table',
                children=[
                    dcc.Tab(label='Table',   value='tab-table',
                            style=tab_style, selected_style=tab_selected_style),
                    dcc.Tab(label='Details', value='tab-details',
                            style=tab_style, selected_style=tab_selected_style),
                    dcc.Tab(label='Filter',  value='tab-filter',
                            style=tab_style, selected_style=tab_selected_style),
                ],
                style={'flex': '0 0 auto'}
            ),
            # Table tab
            html.Div(
                annotation_table,
                id='right-tab-table-content',
                style={'flex': '1 1 0', 'minHeight': '0', 'overflow': 'hidden',
                       'padding': '5px', 'display': 'flex', 'flexDirection': 'column'}
            ),
            # Details tab
            html.Div(
                html.Div(
                    id='hover-details-content',
                    children='Hover over a point to see details.',
                    style={'padding': '10px', 'color': '#555'}
                ),
                id='right-tab-details-content',
                style={'flex': '1 1 0', 'minHeight': '0', 'overflow': 'auto', 'display': 'none'}
            ),
            # Filter tab
            html.Div([
                html.Div('Filter query (pandas syntax):',
                         style={'fontWeight': 'bold',
                                'padding': '8px 5px 5px 5px', 'flex': '0 0 auto'}),
                query_field,
                html.Div(id='pca-filter-error-message',
                         style={'color': 'red',
                                'padding': '0 5px', 'marginTop': '5px', 'flex': '0 0 auto'})
            ], id='right-tab-filter-content',
               style={'flex': '1 1 0', 'minHeight': '0', 'display': 'none',
                      'flexDirection': 'column', 'padding': '5px', 'overflow': 'hidden'}),
        ], style={**flex_style, 'display': 'flex', 'flexDirection': 'column', 'minHeight': '0', 'overflow': 'hidden'})

    map_section = None
    if show_annotation_table:
        if show_map_plot:
            map_split = int(LAYOUT_CONFIG["map_table_split"] * 100)
            table_split = 100 - map_split

            map_section = html.Div([
                html.Div(map_plot, id='map-plot-pane', style={
                    'flex': f'0 0 {map_split}%', 'overflow': 'hidden', 'padding': '5px',
                    **({'display': 'none'} if not map_initially_visible else {}),
                }),
                html.Div(
                    id='map-table-resizer',
                    style={
                        'height': '8px',
                        'backgroundColor': '#bbb',
                        'cursor': 'row-resize',
                        'userSelect': 'none',
                        'flex': '0 0 8px',
                        'marginLeft': '5px',
                        'marginRight': '5px',
                        'transition': 'background-color 0.2s',
                        'position': 'relative',
                        'zIndex': 5,
                        'pointerEvents': 'auto',
                        **({'display': 'none'} if not map_initially_visible else {}),
                    },
                    title='Drag to resize panes'
                ),
                make_tab_panel({'flex': f'0 0 {table_split}%'}),
            ], style={'display': 'flex', 'flexDirection': 'column', 'height': '100%', 'gap': '0'})
        else:
            map_section = make_tab_panel({'flex': '1 1 auto', 'height': '100%'})
    
    # What each live-linked Settings field would be if nothing overrode it —
    # read by the Equivalent-command generator (callbacks/settings2.py) so
    # "Generate command" can tell "still at its natural default" (omit) apart
    # from "user picked something else" (include), which comparing against
    # the CLI's own argparse default (always None for these) cannot do.
    natural_defaults = {
        'pc_x': pcs[0],
        'pc_y': pcs[1] if len(pcs) > 1 else pcs[0],
        'pc_z': pcs[2] if len(pcs) > 2 else pcs[0],
        'longitude': ANNOTATION_LONG,
        'latitude': ANNOTATION_LAT,
        'time': default_continuous,
        'time_bin_size': default_bin_size,
        # The *only* column time-invert-columns/time-rotate-columns default to
        # (ignoring any CLI override) — see data_loader.resolve_column_set's
        # own fallback_columns. Single column (or None), not a full set, since
        # that's all the merge logic in callbacks/settings2.py needs.
        'time_invert_columns_natural': ANNOTATION_TIME,
        'time_rotate_columns_natural': None,
    }

    # Aesthetics modal
    return html.Div([
        control_section,
        dcc.Store(id='settings2-natural-defaults', data=natural_defaults),
        # A plain draggable panel instead of a centered/fixed Bootstrap modal —
        # drag by the title bar (see app.py's clientside drag-init callback,
        # triggered off this component's className). Visibility is toggled via
        # className (assets/draggable_panel.css: .draggable-panel is hidden,
        # .panel-open shows it) rather than an inline style, specifically so
        # the drag handler's direct DOM position (style.left/top) is never
        # clobbered by a later Dash-side style update.
        html.Div(
            [
                html.Div(
                    [
                        html.Span("Edit Marker Aesthetics", style={'fontWeight': 'bold', 'fontSize': '16px'}),
                        html.Button(
                            '✕', id='aesthetics-modal-close-x', n_clicks=0,
                            title='Close',
                            style={
                                'border': 'none', 'background': 'none', 'fontSize': '18px',
                                'lineHeight': '1', 'padding': '4px 8px', 'cursor': 'pointer',
                                'color': '#666',
                            }
                        ),
                    ],
                    id='aesthetics-modal-titlebar',
                    style={
                        'cursor': 'move', 'padding': '10px 16px',
                        'backgroundColor': '#f8f9fa', 'borderBottom': '1px solid #dee2e6',
                        'borderRadius': '6px 6px 0 0', 'display': 'flex',
                        'justifyContent': 'space-between', 'alignItems': 'center',
                        'userSelect': 'none', 'flex': '0 0 auto',
                    },
                ),
                html.Div(
                    [
                        html.P(
                            "Edit values per group. Use '-' to keep default value.",
                            style={'color': '#666', 'marginBottom': '12px'}
                        ),
                        html.Div(
                            id='aesthetics-table-container',
                            style={
                                'overflowX': 'auto',
                                'overflowY': 'auto',
                                'maxHeight': '55vh'
                            }
                        )
                    ],
                    style={'padding': '16px', 'overflowY': 'auto', 'flex': '1 1 auto'},
                ),
                html.Div(
                    [
                        html.Button(
                            'Export to File',
                            id='export-aesthetics-btn',
                            style={
                                'padding': '8px 16px',
                                'border': '1px solid #28a745',
                                'borderRadius': '4px',
                                'backgroundColor': '#28a745',
                                'color': '#ffffff',
                                'cursor': 'pointer',
                                'marginRight': 'auto'
                            }
                        ),
                        html.Button(
                            'Cancel',
                            id='cancel-aesthetics',
                            style={
                                'padding': '8px 16px',
                                'border': '1px solid #ccc',
                                'borderRadius': '4px',
                                'backgroundColor': '#ffffff',
                                'cursor': 'pointer',
                                'marginRight': '8px'
                            }
                        ),
                        html.Button(
                            'Save Changes',
                            id='save-aesthetics',
                            style={
                                'padding': '8px 16px',
                                'border': '1px solid #0066cc',
                                'borderRadius': '4px',
                                'backgroundColor': '#0066cc',
                                'color': '#ffffff',
                                'cursor': 'pointer'
                            }
                        )
                    ],
                    style={
                        'padding': '12px 16px', 'borderTop': '1px solid #dee2e6',
                        'display': 'flex', 'alignItems': 'center', 'flex': '0 0 auto',
                    },
                ),
            ],
            id='aesthetics-modal',
            className='draggable-panel',
            style={
                'position': 'fixed', 'top': '80px', 'left': '50%',
                'transform': 'translateX(-50%)', 'width': 'min(900px, 90vw)',
                'maxHeight': '85vh', 'flexDirection': 'column',
                'backgroundColor': 'white', 'borderRadius': '6px',
                'boxShadow': '0 4px 24px rgba(0,0,0,0.3)', 'zIndex': 1050,
            },
        ),
        dcc.Download(id='download-aesthetics'),
        html.Div(
            id='pca-plots-container',
            children=(
                [
                    html.Div(
                        id='pca-left-pane',
                        children=left_pane,
                        style={
                            'flex': '0 0 50%',
                            'overflow': 'hidden',
                            'position': 'relative'
                        },
                        **{'data-pane': 'left'}
                    ),
                    html.Div(
                        id='pca-vertical-resizer',
                        style={
                            'width': '8px',
                            'backgroundColor': '#bbb',
                            'cursor': 'col-resize',
                            'userSelect': 'none',
                            'flex': '0 0 8px',
                            'transition': 'background-color 0.2s',
                            'position': 'relative',
                            'zIndex': 5,
                            'pointerEvents': 'auto'
                        },
                        title='Drag to resize panes'
                    ),
                    html.Div(
                        id='pca-right-pane',
                        children=map_section,
                        style={
                            'flex': '0 0 50%',
                            'overflow': 'hidden'
                        },
                        **{'data-pane': 'right'}
                    )
                ]
                if show_annotation_table else
                [
                    html.Div(
                        id='pca-left-pane',
                        children=left_pane,
                        style={
                            'flex': '1 1 auto',
                            'overflow': 'hidden',
                            'position': 'relative'
                        },
                        **{'data-pane': 'left'}
                    )
                ]
            ),
            style={
                'display': 'flex',
                'gap': '0',
                'marginBottom': '0',
                'flex': '1',
                'minHeight': '0',
                'height': '100%'
            }
        )
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})


def create_annotation_tab(annotation_desc, annotation_columns=None, pcs=None, init_selected_cols=None):
    """Create annotation tab layout."""
    # Extend annotation_desc with PC columns
    if pcs:
        pc_rows = pd.DataFrame({
            'Abbreviation': pcs,
            'Description': pcs,
            'Type': ['continuous'] * len(pcs),
            'N_levels': [None] * len(pcs),
            'Dropdown': ['Yes'] * len(pcs)
        })
        annotation_desc_extended = pd.concat([annotation_desc, pc_rows], ignore_index=True)
    else:
        annotation_desc_extended = annotation_desc
    
    # Convert annotation_desc DataFrame to dict format for AG Grid
    table_data = annotation_desc_extended.to_dict('records')
    if 'Selected' not in annotation_desc_extended.columns:
        for row in table_data:
            row['Selected'] = False
    if init_selected_cols:
        selected_set = set(init_selected_cols)
        for row in table_data:
            if row.get('Abbreviation') in selected_set:
                row['Selected'] = True
    else:
        for row in table_data[:10]:
            row['Selected'] = True

    # Define columns for the table (checkbox column instead of row selection)
    # Narrow columns use a fixed width + suppressSizeToFit so they never shrink
    # below their content; Description absorbs all remaining space via flex.
    column_defs = [
        create_checkbox_column_def(),
        create_standard_column_def('Abbreviation', 'Abbreviation', width=130, suppressSizeToFit=True),
        create_standard_column_def('Description', 'Description', flex=1, minWidth=200),
        create_standard_column_def('Type', 'Type', width=120, suppressSizeToFit=True),
        create_standard_column_def('N_levels', 'N_levels', width=100, suppressSizeToFit=True),
        create_standard_column_def('Dropdown', 'Dropdown', width=100, suppressSizeToFit=True),
    ]
    
    return html.Div([
        html.H3("Annotation Description", style={'marginBottom': '20px'}),
        html.P("Select rows to display those columns in the PCA tab annotation table", 
               style={'color': '#666', 'marginBottom': '15px'}),
        
        dag.AgGrid(
            id='annotation-table',
            rowData=table_data,
            columnDefs=column_defs,
            defaultColDef={
                'resizable': True,
            },
            dashGridOptions={
                'pagination': True,
                'paginationPageSize': 20,
                'animateRows': False,
                'suppressRowClickSelection': True,
                'suppressColumnVirtualisation': True,
            },
            style={'flex': '1', 'width': '100%'}
        )
    ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})
