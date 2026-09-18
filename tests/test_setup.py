"""Tests for the in-tab file loaders / no-data startup."""

import pandas as pd

from interactive_pca.args import parse_args
from interactive_pca.app import create_app
from interactive_pca.callbacks.setup import _compose_argv


def test_app_builds_without_data():
    """create_app builds the tab shell when no eigenvec is given."""
    app = create_app(parse_args([]))
    assert app.layout is not None


def _write_eigenvec(path, extra_cols=None):
    data = {'id': ['s1', 's2', 's3'],
            'PC1': [0.01, 0.02, 0.03],
            'PC2': [-0.01, -0.02, -0.03]}
    data.update(extra_cols or {})
    pd.DataFrame(data).to_csv(path, sep=' ', index=False)


def test_annotation_loader_plain_read_without_embedded_columns(tmp_path):
    """Regression: an eigenvec file with NO extra columns must keep the
    original single 'Read' button in the Annotation tab. Don't let a future
    change to the embedded-annotation feature silently swap this back to the
    three mode buttons, which only make sense when there's something to
    choose between.
    """
    path = tmp_path / "plain.eigenvec"
    _write_eigenvec(path)
    app = create_app(parse_args(['--eigenvec', str(path), '--ignore-embedded-annotation']))
    layout_str = str(app.layout)
    assert 'read-annotation-btn' in layout_str
    assert 'use-file-annotation-btn' not in layout_str
    assert 'use-embedded-annotation-btn' not in layout_str
    assert 'use-combine-annotation-btn' not in layout_str


def test_annotation_loader_three_buttons_with_embedded_columns(tmp_path):
    """An eigenvec file that DOES carry extra columns should offer the three
    annotation-loading buttons instead of the plain Read button.
    """
    path = tmp_path / "with_extra.eigenvec"
    _write_eigenvec(path, {'region': ['A', 'B', 'C']})
    app = create_app(parse_args(['--eigenvec', str(path), '--ignore-embedded-annotation']))
    layout_str = str(app.layout)
    assert 'read-annotation-btn' not in layout_str
    assert 'use-file-annotation-btn' in layout_str
    assert 'use-embedded-annotation-btn' in layout_str
    assert 'use-combine-annotation-btn' in layout_str


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
