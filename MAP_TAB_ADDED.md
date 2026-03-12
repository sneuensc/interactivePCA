# Map Feature History

This file is kept as a historical milestone note.

## Historical milestone

A dedicated map tab was introduced during an earlier phase of the app.

## Current behavior (March 2026)

The app no longer relies on a dedicated map tab:

- Map rendering is integrated in the main PCA layout.
- The map panel is shown only when `--annotation`, `--latitude`, and `--longitude` are provided.
- When map coordinates are missing, the map panel is suppressed.

For current implementation details, see:

- `interactive_pca/layouts/__init__.py`
- `interactive_pca/callbacks/plots.py`
- `README.md`
