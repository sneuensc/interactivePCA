# Plot Status

This file reflects the current plot status of the app.

## Current state (March 2026)

- PCA plot is implemented and always available with `--eigenvec`.
- Map panel is implemented and conditionally displayed when annotation + latitude/longitude are provided.
- Time plot is implemented and conditionally displayed when annotation + `--time` are provided.
- Annotation table is implemented and shown only when annotation data is provided.

## Where plot logic lives

- Plot construction: `interactive_pca/plots.py`
- Layout placement: `interactive_pca/layouts/__init__.py`
- Plot callbacks: `interactive_pca/callbacks/plots.py`
- Selection sync: `interactive_pca/callbacks/selection.py`
- Hover updates: `interactive_pca/components/hover.py`
