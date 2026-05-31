"""
Command-line argument parser configuration.
"""

import argparse
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
                       help='Eigenvec file path (plink)')
    parser.add_argument('--eigenvecID', type=str, default=None, metavar="NAME",
                       help='Eigenvec ID column (default first column)')
    parser.add_argument('--selectedID', type=str, default=None, required=False, metavar="IDs",
                       help='Selected samples, given as comma separated IDs, or as a file with each ID on a line (default: all)')

    # Annotation
    parser.add_argument('--annotation', type=str, default=None, metavar="FILE",
                       help='Annotation file path')
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
    parser.add_argument('--show-all-legends', action='store_true', default=False,
                       help='Show the legends in all figures')

    return parser


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

    return parsed_args
