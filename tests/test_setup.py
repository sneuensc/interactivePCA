"""Tests for the in-tab file loaders / no-data startup."""

from interactive_pca.args import parse_args
from interactive_pca.app import create_app
from interactive_pca.callbacks.setup import _compose_argv


def test_app_builds_without_data():
    """create_app builds the tab shell when no eigenvec is given."""
    app = create_app(parse_args([]))
    assert app.layout is not None


def test_compose_argv_values_and_flags():
    """Composed argv includes set values/flags and omits unchanged defaults."""
    argv = _compose_argv({
        'eigenvec': 'data/x.eigenvec',
        'annotation': 'data/x.anno',
        'latitude': 'lat',
        'time_invert': True,       # store_true flag
        'point_size': 8,           # equals default -> omitted
        'point_symbol': 'square',  # differs from default 'circle'
    })
    assert '--eigenvec' in argv and 'data/x.eigenvec' in argv
    assert '--latitude' in argv and 'lat' in argv
    assert '--time-invert' in argv           # flag emitted, no value
    assert '--point-size' not in argv         # default value omitted
    assert '--point-symbol' in argv and 'square' in argv


def test_compose_argv_skips_empty():
    """Empty strings and None are not emitted."""
    argv = _compose_argv({'eigenvec': 'e', 'annotation': '', 'group': None})
    assert '--annotation' not in argv
    assert '--group' not in argv
