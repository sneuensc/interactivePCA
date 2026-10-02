"""
Canonical marker-symbol definitions shared across the scatter, map and
aesthetics editor.

Three figures render points and each supports a different symbol vocabulary:

* 2D PCA scatter (go.Scatter/Scattergl) — supports the full set below.
* Geographic map (go.Scattermap, MapLibre) — 'circle' is drawn natively; every
  other symbol is rendered from a generated SDF icon (see app.py). The set we
  can draw is MAP_SYMBOLS; anything else falls back to a circle on the map.
* 3D PCA scatter (go.Scatter3d) — only a small set is valid; the rest are
  remapped (plots._SCATTER3D_SYMBOL_MAP), so they do not render faithfully.

SHAPE_SYMBOLS is the list offered in the shape-grouping editor.
"""

# Symbols offered for categorical shape grouping (2D scatter vocabulary).
# Order matters: categories are assigned symbols by cycling through this list,
# so keep it stable across the app (scatter, map, aesthetics editor).
SHAPE_SYMBOLS = [
    'circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star',
]

# Symbols the map can render (natively for 'circle', via generated SDF icons for
# the rest). Kept in sync with the icon generator in app.py.
MAP_SYMBOLS = {
    'circle', 'square', 'diamond', 'triangle-up', 'triangle-down', 'star', 'cross',
}

# Symbols that render faithfully in the 3D scatter without being remapped.
# (plots._SCATTER3D_SYMBOL_MAP remaps triangle-up/-down/star to other shapes.)
SCATTER3D_SYMBOLS = {'circle', 'square', 'diamond', 'cross', 'x'}


def is_map_compatible(symbol):
    """Whether *symbol* renders as itself on the geographic map."""
    return symbol in MAP_SYMBOLS


def is_3d_compatible(symbol):
    """Whether *symbol* renders as itself in the 3D scatter (not remapped)."""
    return symbol in SCATTER3D_SYMBOLS
