# App Implementation Summary

## Current implementation

The Dash application is implemented around a modular factory architecture:

- `interactive_pca/app.py` creates and configures the Dash app.
- `interactive_pca/layouts/__init__.py` builds UI layout and panel composition.
- `interactive_pca/callbacks/` contains interaction logic split by domain:
  - `selection.py`
  - `plots.py`
  - `aesthetics.py`
- `interactive_pca/components/` contains reusable helper logic.

## App flow

1. Parse args (`interactive_pca/args.py`).
2. Load and merge data (`interactive_pca/data_loader.py`).
3. Build layout (`interactive_pca/layouts/__init__.py`).
4. Register callbacks (`interactive_pca/callbacks/__init__.py`).
5. Serve app (`interactive_pca/cli.py`).

## Conditional UI behavior

- Annotation missing: table/map/time panels are suppressed.
- Latitude/longitude missing: map panel suppressed.
- Time column missing: time panel suppressed.

This behavior is matched by conditional callback registration to avoid missing-component callback errors.
