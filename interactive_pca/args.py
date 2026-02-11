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
    parser.add_argument('--eigenvec', type=str, default=None, required=False, 
                       help='Eigenvec file path (plink)')
    parser.add_argument('--eigenvecID', type=str, default=None, 
                       help='Eigenvec ID column (default first column)')
    parser.add_argument('--selectedID', type=str, default=None, required=False, 
                       help='Selected samples, given as comma separated IDs, or as a file with each ID on a line (default: all)')

    # Eigenvalues
    parser.add_argument('--eigenval', type=str, default=None, required=False, 
                       help='Eigenval file path (plink)')
    parser.add_argument('--nb_eigenvalues', type=int, default=10, 
                       help='Number of eigenvalues to show (0 for all)')

    # Statistics
    parser.add_argument('--imiss', type=str, default=None, 
                       help='Imiss file path (plink)')
    parser.add_argument('--lmiss', type=str, default=None, 
                       help='Lmiss file path (plink)')
    parser.add_argument('--frq', type=str, default=None, 
                       help='Frq file path (plink)')

    # Annotation
    parser.add_argument('--annotation', type=str, default=None, 
                       help='Annotation file path')
    parser.add_argument('--annotationID', type=str, default='Genetic ID', 
                       help='Annotation ID column (default first column)')
    parser.add_argument('--longitude', type=str, default=None, 
                       help='Longitude column name')
    parser.add_argument('--latitude', type=str, default=None, 
                       help='Latitude column name')
    parser.add_argument('--time', type=str, default=None, 
                       help='Time column name')
    parser.add_argument('--group', type=str, default=None, 
                       help='Grouping/coloring column name')

    # Text handling
    parser.add_argument('--ignore_case', action='store_true', default=False, 
                       help='Ignore case differences in annotation')
    parser.add_argument('--ignore_space', action='store_true', default=False, 
                       help='Ignore space differences in annotation')
    parser.add_argument('--col_abbrev', type=int, default=15, 
                       help='Abbreviate column names to this length (0 for no abbreviation)')
    parser.add_argument('--legend_abbrev', type=int, default=0, 
                       help='Abbreviate legend text to this length (0 for no abbreviation)')
    parser.add_argument('--max_factors', type=int, default=400, 
                       help='Maximum number of different elements in factorial columns to be included')

    # Aesthetics
    parser.add_argument('--aesthetics_file', type=str, default=None, 
                       help='Json file with stored aesthetics (default none)')
    parser.add_argument('--color_schema_continuous', type=str, default='Viridis', 
                       help='Color schema for continuous variables (default Viridis)')
    parser.add_argument('--point_color', type=str, default="#000000", 
                       help='Default point color for selected points (default #000000)')
    parser.add_argument('--point_color_unselected', type=str, default='#cccccc', 
                       help='Default point color for unselected points (default #cccccc)')
    parser.add_argument('--point_size', type=int, default=8, 
                       help='Default point size (default 8)')
    parser.add_argument('--point_size_unselected', type=int, default=8, 
                       help='Default point size for unselected points (default 8)')
    parser.add_argument('--point_opacity', type=float_0_1, default=0.9, 
                       help='Default opacity (default 0.9)')
    parser.add_argument('--point_opacity_unselected', type=float_0_1, default=0.3, 
                       help='Default opacity for unselected points (default 0.3)')
    parser.add_argument('--point_symbol', type=str, default='circle', 
                       help='Default point symbol (default circle)')
    parser.add_argument('--point_symbol_unselected', type=str, default='circle', 
                       help='Default point symbol for unselected points (default circle)')

    # Time figure
    parser.add_argument('--time_plot_type', type=int, choices=[0, 1, 2], default=0, 
                       help='Time plot type: 0=scatter, 1=histogram with selection, 2=histogram simple')
    parser.add_argument('--time_hist_nbins', type=int, default=100, 
                       help='Number of bins for the time histogram (100)')
    parser.add_argument('--time_invert', action='store_true', default=False, 
                       help='Invert time axis (for BP data)')

    # Plot settings
    parser.add_argument('--hover_minimal', action='store_true', default=False, 
                       help='Show minimal information when hovering points')
    parser.add_argument('--open_browser', action='store_true', default=False, 
                       help='Open directly the dash server in a web browser')
    parser.add_argument('--server_port', type=int, default=8050, 
                       help='Port for the dash server (default 8050)')

    # Development
    parser.add_argument('--dev', action='store_true', default=False, 
                       help='Use development parameters')
    parser.add_argument('--show_all_legends', action='store_true', default=False, 
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
