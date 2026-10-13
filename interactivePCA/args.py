"""
Command-line argument parser configuration.
"""

import argparse
import json
import logging
import os
from .utils import is_notebook
from .symbols import SHAPE_SYMBOLS

# Preset choices for the aesthetics CLI flags below — the same values already
# offered by the per-group Aesthetics editor's dropdown cell-editors
# (callbacks/aesthetics.py), so picking a default in Settings (where these
# render as dropdowns — see layouts/setup.py:_field_component) matches what
# editing a single group there already offers. Each list includes that flag's
# own default (0.9/0.3 aren't themselves "round" preset values) so the
# default is always a valid, selectable option.
_POINT_SIZES = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
_POINT_OPACITIES = [0.2, 0.3, 0.4, 0.6, 0.8, 0.9, 1.0]
_CONTINUOUS_COLORSCALES = [
    'Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 'Blues', 'Reds', 'Greens', 'YlOrRd', 'RdYlBu',
]


def float_0_1(value):
    """
    Validate that a float is between 0 and 1.

    Args:
        value: String representation of float

    Returns:
        Float value

    Raises:
        ArgumentTypeError if not in range [0, 1]
    """
    f = float(value)
    if f < 0 or f > 1:
        raise argparse.ArgumentTypeError(f"{value} is not in range [0, 1]")
    return f


def create_parser(script_name='Script'):
    """
    Create the argument parser for interactivePCA.

    Args:
        script_name: Name of the script (used in help text)

    Returns:
        ArgumentParser instance
    """
    parser = argparse.ArgumentParser(description=f"{script_name} parameters")

    # Eigenvectors
    parser.add_argument('--eigenvec', type=str, default=None, required=False, metavar="FILE",
                       help='Data file path. Can contain: ID column (1st col, e.g. Sample), '
                            'dimension columns (e.g. PC1, PC2, PC3), and annotation columns (e.g. Region, Date).')
    parser.add_argument('--eigenvecID', type=str, default=None, metavar="COL",
                       help='ID column name (e.g. Sample, IID). Default is first column.')
    parser.add_argument('--dim', type=str, default=None, metavar="COLS",
                       help='Dimension column names, comma-separated (e.g. PC1,PC2,PC3). '
                            'If not provided, auto-detects columns with a prefix followed by increasing numbers.')
    parser.add_argument('--pc-x', type=str, default=None, metavar="COL",
                       help='Initial PCA plot X-axis column (default: the first dimension)')
    parser.add_argument('--pc-y', type=str, default=None, metavar="COL",
                       help='Initial PCA plot Y-axis column (default: the second dimension)')
    parser.add_argument('--pc-z', type=str, default=None, metavar="COL",
                       help='Initial PCA plot Z-axis column, used when 3D is enabled '
                            '(default: the third dimension)')
    parser.add_argument('--pca-3d', action='store_true', default=False,
                       help='Start the PCA plot in 3D (default: 2D)')
    parser.add_argument('--selectedID', type=str, default=None, required=False, metavar="IDs",
                       help='Which samples start selected: ";"- or ","-separated IDs or '
                            'wildcard patterns (e.g. "S1;S2" or "*.SG"; prefix a token with '
                            '"!" to exclude it, e.g. "!*.DG" for everyone but *.DG), or a '
                            'file with each ID on a line (default: all)')
    parser.add_argument('--subsetID', type=str, default=None, required=False, metavar="IDs",
                       help='Restrict which samples are loaded at all (everything else is '
                            'skipped entirely, not just left unselected): ";"- or ","-separated '
                            'IDs or wildcard patterns (e.g. "S1;S2" or "*.SG"; prefix a token '
                            'with "!" to exclude it, e.g. "!*.DG" for everyone but *.DG), or '
                            'a file with each ID on a line (default: load all)')

    # Annotation
    parser.add_argument('--annotation', type=str, default=None, metavar="FILE",
                       help='Annotation file path')
    # Internal: set only by the PCA tab's own "Load" button (never by plain CLI use
    # or shown in --help/Settings). By default, extra (non-ID, non-dimension)
    # columns in --eigenvec are used as annotation whenever --annotation is empty.
    # This skips that for one specific relaunch, so loading via the PCA tab gives
    # coordinates only; the Annotation tab's "Use annotations from eigenvec file"
    # clears it again on its own relaunch.
    parser.add_argument('--ignore-embedded-annotation', action='store_true',
                       default=False, help=argparse.SUPPRESS)
    parser.add_argument('--merge-embedded-annotation', action='store_true', default=False,
                       help='When --eigenvec has its own extra (non-ID, non-dimension) columns '
                            'and --annotation is also given, combine both as annotation instead '
                            'of using only the annotation file. A column already present in the '
                            'annotation file takes precedence over one of the same name embedded '
                            'in --eigenvec.')
    parser.add_argument('--annotationID', type=str, default='Genetic ID', metavar="COL",
                       help='Annotation ID column (default first column)')
    parser.add_argument('--annotation-columns', type=str, default='', metavar="COLS",
                       help='Comma-separated annotation columns initially shown in the table/hover '
                            '(default: the first 10)')
    parser.add_argument('--longitude', type=str, default=None, metavar="COL",
                       help='Longitude column name')
    parser.add_argument('--latitude', type=str, default=None, metavar="COL",
                       help='Latitude column name')
    parser.add_argument('--map-type', type=str, choices=['map', 'tiles', 'none'], default='map',
                       help="Initial map basemap, matching the Basemap dropdown's own options: "
                            "'map', 'tiles', or 'none' (default: map)")
    parser.add_argument('--time', type=str, default=None, metavar="COL",
                       help='Time column name')
    parser.add_argument('--group', type=str, default=None, metavar="COL",
                       help='Grouping/coloring column name')
    parser.add_argument('--group-shape', type=str, default=None, metavar="COL",
                       help='Grouping/shape column name')

    # Text handling
    parser.add_argument('--ignore-case', action='store_true', default=False,
                       help='Ignore case differences in annotation')
    parser.add_argument('--ignore-space', action='store_true', default=False,
                       help='Ignore space differences in annotation')
    parser.add_argument('--col-abbrev', type=int, default=15, metavar="N",
                       help='Abbreviate column names to this length (0 for no abbreviation)')
    parser.add_argument('--legend-abbrev', type=int, default=30, metavar="N",
                       help='Abbreviate legend text to this length (0 for no abbreviation)')
    parser.add_argument('--max-factors', type=int, default=400, metavar="N",
                       help='Maximum number of different elements in factorial columns to be included')

    # Aesthetics
    parser.add_argument('--aesthetics-file', type=str, default=None, metavar="FILE",
                       help='JSON file with stored aesthetics (default none)')
    parser.add_argument('--session', type=str, default=None, metavar="FILE",
                       help="JSON file with a saved run: the full CLI args (eigenvec, "
                            "annotation, every setting) plus the view (selection, "
                            "grouping, aesthetics, axes, map, time-plot, panel sizes) — "
                            "reopens showing exactly that, on its own with no other flag "
                            "needed (an arg also passed on this command line still wins "
                            "over the saved one). Created by the app's own 'Save view' "
                            "button (default none)")
    parser.add_argument('--color-schema-continuous', type=str, default='Viridis', metavar="NAME",
                       choices=_CONTINUOUS_COLORSCALES,
                       help='Color schema for continuous variables (default Viridis)')
    parser.add_argument('--point-color', type=str, default="#000000", metavar="COLOR",
                       help='Default point color for selected points (default #000000)')
    parser.add_argument('--point-color-unselected', type=str, default='#cccccc', metavar="COLOR",
                       help='Default point color for unselected points (default #cccccc)')
    parser.add_argument('--point-size', type=int, default=8, metavar="N", choices=_POINT_SIZES,
                       help='Default point size (default 8)')
    parser.add_argument('--point-size-unselected', type=int, default=8, metavar="N", choices=_POINT_SIZES,
                       help='Default point size for unselected points (default 8)')
    parser.add_argument('--point-opacity', type=float_0_1, default=0.9, metavar="FLOAT",
                       choices=_POINT_OPACITIES,
                       help='Default opacity (default 0.9)')
    parser.add_argument('--point-opacity-unselected', type=float_0_1, default=0.3, metavar="FLOAT",
                       choices=_POINT_OPACITIES,
                       help='Default opacity for unselected points (default 0.3)')
    parser.add_argument('--point-symbol', type=str, default='circle', metavar="SYMBOL",
                       choices=SHAPE_SYMBOLS,
                       help='Default point symbol (default circle)')
    parser.add_argument('--point-symbol-unselected', type=str, default='circle', metavar="SYMBOL",
                       choices=SHAPE_SYMBOLS,
                       help='Default point symbol for unselected points (default circle)')

    # Time figure
    parser.add_argument('--time-viz-mode', type=str,
                       choices=['scatter', 'violin', 'distribution', 'overlay'], default='scatter',
                       help="Initial time-plot view mode (default: scatter)")
    parser.add_argument('--time-group-mode', type=str,
                       choices=['none', 'group', 'group_named'], default='group',
                       help="Initial time-plot grouping (Scatter/Violin only): 'none' (one combined "
                            "strip), 'group' (one per group), 'group_named' (one per group, labelled) "
                            "(default: group)")
    parser.add_argument('--time-bin-size', type=float, default=None, metavar="N",
                       help='Initial time-plot histogram bin width, for Distribution/Overlay '
                            '(default: ~50 bins across the data range)')
    parser.add_argument('--time-invert-columns', type=str, default='', metavar="COLS",
                       help="Comma-separated continuous columns whose time-plot x-axis starts "
                            "reversed by default (e.g. BP dates) — defaults to just the --time "
                            "column if omitted; 'Invert' can still be toggled per-column at runtime")
    parser.add_argument('--time-rotate-columns', type=str, default='', metavar="COLS",
                       help="Comma-separated continuous columns whose time-plot starts with x/y "
                            "swapped by default; 'Rotate' can still be toggled per-column at runtime")

    # Plot settings
    parser.add_argument('--hover-minimal', action='store_true', default=False,
                       help='Show minimal information when hovering points '
                            '(default: detailed)')
    parser.add_argument('--legend', type=str, choices=['none', 'once', 'everywhere'],
                       default='once',
                       help="Legend display mode: 'none' never shows it, 'once' shows it on "
                            "a single active plot at a time, 'everywhere' shows it on every "
                            "plot that has one (default: once)")
    parser.add_argument('--open-browser', action='store_true', default=False,
                       help='Open directly the dash server in a web browser')
    parser.add_argument('--server-port', type=int, default=8050, metavar="N",
                       help='Port for the dash server (default 8050)')

    # Development
    parser.add_argument('--dev', action='store_true', default=False,
                       help='Use development parameters')
    parser.add_argument('--setup', action='store_true', default=False,
                       help='Force the setup loader shell even if data is given '
                            '(used by the Restart button to prefill the loaders)')

    return parser


# Internal/self-referential dests never pulled from a --session file's own
# saved args (mirrors layouts.setup._INTERNAL_ARGS, duplicated here to avoid
# a circular import — that module imports from this one).
_SESSION_ARGS_EXCLUDE = {'session', 'setup', 'ignore_embedded_annotation'}


def _merge_session_args(parsed_args, parser):
    """Fill in any CLI arg not explicitly set on this command line from a
    --session file's own saved args (callbacks/session.py:save_view embeds
    the full CLI args alongside the view), so --session alone — no separate
    --eigenvec/--annotation/etc. — can fully reproduce a saved run. An arg
    actually passed on this command line always wins over the saved one.
    """
    if not parsed_args.session or not os.path.isfile(parsed_args.session):
        return parsed_args
    try:
        with open(parsed_args.session, 'r') as f:
            session_data = json.load(f)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Could not read session file '%s': %s", parsed_args.session, exc)
        return parsed_args

    saved_args = session_data.get('args') or {}
    defaults = {a.dest: a.default for a in parser._actions if a.option_strings}
    for dest, value in saved_args.items():
        if dest in _SESSION_ARGS_EXCLUDE or not hasattr(parsed_args, dest):
            continue
        # "Still at the parser's default" is the same heuristic already used
        # to detect explicit-vs-default fields when composing relaunch argv
        # (callbacks/setup.py:_compose_argv) — a false positive only if the
        # user happens to explicitly pass a flag equal to its own default.
        if getattr(parsed_args, dest) == defaults.get(dest):
            setattr(parsed_args, dest, value)
    return parsed_args


def parse_args(args=None):
    """
    Parse command-line arguments.

    Args:
        args: List of argument strings. If None, uses sys.argv

    Returns:
        Parsed arguments namespace
    """
    import sys

    script_name = sys.argv[0] if not is_notebook() else 'Script'
    parser = create_parser(script_name)

    if is_notebook():
        parsed_args = parser.parse_args([])
    else:
        parsed_args = parser.parse_args(args)

    parsed_args = _merge_session_args(parsed_args, parser)

    return parsed_args
