"""
Command-line argument parser configuration.
"""

import argparse
import json
import logging
import os
from .utils import is_notebook


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
    parser.add_argument('--eigenvecID', type=str, default=None, metavar="NAME",
                       help='ID column name (e.g. Sample, IID). Default is first column.')
    parser.add_argument('--dim', type=str, default=None, metavar="COLS",
                       help='Dimension column names, comma-separated (e.g. PC1,PC2,PC3). '
                            'If not provided, auto-detects columns with a prefix followed by increasing numbers.')
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
    parser.add_argument('--annotationID', type=str, default='Genetic ID', metavar="NAME",
                       help='Annotation ID column (default first column)')
    parser.add_argument('--longitude', type=str, default=None, metavar="NAME",
                       help='Longitude column name')
    parser.add_argument('--latitude', type=str, default=None, metavar="NAME",
                       help='Latitude column name')
    parser.add_argument('--time', type=str, default=None, metavar="NAME",
                       help='Time column name')
    parser.add_argument('--group', type=str, default=None, metavar="NAME",
                       help='Grouping/coloring column name')
    parser.add_argument('--group-shape', type=str, default=None, metavar="NAME",
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
                       help='Json file with stored aesthetics (default none)')
    parser.add_argument('--session', type=str, default=None, metavar="FILE",
                       help="Json file with a saved run: the full CLI args (eigenvec, "
                            "annotation, every setting) plus the view (selection, "
                            "grouping, aesthetics, axes, map, time-plot, panel sizes) — "
                            "reopens showing exactly that, on its own with no other flag "
                            "needed (an arg also passed on this command line still wins "
                            "over the saved one). Created by the app's own 'Save view' "
                            "button (default none)")
    parser.add_argument('--color-schema-continuous', type=str, default='Viridis', metavar="NAME",
                       help='Color schema for continuous variables (default Viridis)')
    parser.add_argument('--point-color', type=str, default="#000000", metavar="COLOR",
                       help='Default point color for selected points (default #000000)')
    parser.add_argument('--point-color-unselected', type=str, default='#cccccc', metavar="COLOR",
                       help='Default point color for unselected points (default #cccccc)')
    parser.add_argument('--point-size', type=int, default=8, metavar="N",
                       help='Default point size (default 8)')
    parser.add_argument('--point-size-unselected', type=int, default=8, metavar="N",
                       help='Default point size for unselected points (default 8)')
    parser.add_argument('--point-opacity', type=float_0_1, default=0.9, metavar="FLOAT",
                       help='Default opacity (default 0.9)')
    parser.add_argument('--point-opacity-unselected', type=float_0_1, default=0.3, metavar="FLOAT",
                       help='Default opacity for unselected points (default 0.3)')
    parser.add_argument('--point-symbol', type=str, default='circle', metavar="SYMBOL",
                       help='Default point symbol (default circle)')
    parser.add_argument('--point-symbol-unselected', type=str, default='circle', metavar="SYMBOL",
                       help='Default point symbol for unselected points (default circle)')

    # Time figure
    parser.add_argument('--time-plot-type', type=int, choices=[0, 1, 2], default=0,
                       help='Time plot type: 0=scatter, 1=histogram with selection, 2=histogram simple')
    parser.add_argument('--time-hist-nbins', type=int, default=100, metavar="N",
                       help='Number of bins for the time histogram (100)')
    parser.add_argument('--time-invert', action='store_true', default=False,
                       help='Invert time axis (for BP data)')

    # Plot settings
    parser.add_argument('--hover-minimal', action='store_true', default=False,
                       help='Show minimal information when hovering points')
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
    parser.add_argument('--show-all-legends', action='store_true', default=False,
                       help='Show the legends in all figures')

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


def parse_args(args=None, dev_mode=False):
    """
    Parse command-line arguments.

    Args:
        args: List of argument strings. If None, uses sys.argv
        dev_mode: If True, use development defaults

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
