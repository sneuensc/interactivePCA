# interactivePCA Refactoring Summary

This document summarizes the current refactored state of the project.

## Result

The original monolithic notebook workflow has been split into a modular Python package:

- `interactive_pca/app.py` for app creation
- `interactive_pca/layouts/` for layout construction
- `interactive_pca/callbacks/` for callback logic
- `interactive_pca/components/` for reusable UI/helpers
- `interactive_pca/data_loader.py` and `interactive_pca/plots.py` for data/plot logic

## Key improvements

- Clear separation of concerns between layout, callbacks, components, and data logic.
- Reusable importable package API in `interactive_pca/__init__.py`.
- CLI entry point via `interactive_pca/cli.py` (`interactive-pca`).
- Test suite available under `tests/`.

## Current UI behavior highlights

- PCA plot is always shown when `--eigenvec` is provided.
- Annotation table/map/time panels are conditionally shown based on provided annotation and column arguments.
- Callback registration is also conditional to avoid wiring callbacks to missing UI elements.

## Source of truth

For up-to-date implementation details, use:

- `README.md`
- `GETTING_STARTED.md`
- `PACKAGE_STRUCTURE.md`
- `interactive_pca/` source files
