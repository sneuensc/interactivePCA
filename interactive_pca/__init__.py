"""
interactivePCA - Interactive PCA visualization with Dash

A Python package for interactive exploration of PCA results with support for
multiple visualization types including 2D/3D scatter plots, geographical maps,
and time series data.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__license__ = "MIT"

from .utils import (
    is_notebook,
    strip_ansi,
    make_unique_abbr,
    find_incrementing_prefix_series,
    dict_of_dicts_to_tuple,
    tuple_to_dict_of_dicts,
)

from .args import create_parser, parse_args, float_0_1

from .data_loader import (
    load_eigenvec,
    load_annotation,
    load_eigenval,
    load_imiss,
    load_lmiss,
    load_frq,
    merge_data,
)

from .app import create_app

__all__ = [
    # Utils
    "is_notebook",
    "strip_ansi",
    "make_unique_abbr",
    "find_incrementing_prefix_series",
    "dict_of_dicts_to_tuple",
    "tuple_to_dict_of_dicts",
    # Args
    "create_parser",
    "parse_args",
    "float_0_1",
    # Data loader
    "load_eigenvec",
    "load_annotation",
    "load_eigenval",
    "load_imiss",
    "load_lmiss",
    "load_frq",
    "merge_data",
    # App
    "create_app",
]
