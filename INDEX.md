# interactivePCA Documentation Index

## Start Here

1. [README.md](README.md) — Main usage, features, inputs, and package overview.
2. [GETTING_STARTED.md](GETTING_STARTED.md) — Practical install/run examples.
3. [PACKAGE_STRUCTURE.md](PACKAGE_STRUCTURE.md) — Current repository and module tree.

## Implementation Notes

- [APP_IMPLEMENTATION.md](APP_IMPLEMENTATION.md) — Implementation notes (historical context + current pointer).
- [PLOTS_FIXED.md](PLOTS_FIXED.md) — Plot-related progress notes (historical context + current pointer).
- [MAP_TAB_ADDED.md](MAP_TAB_ADDED.md) — Map feature history (historical context + current pointer).
- [REFACTORING_STATUS.md](REFACTORING_STATUS.md) — Refactoring progress notes (historical snapshot).
- [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) — Refactoring summary (historical snapshot).

## Current Package Modules

- `interactive_pca/app.py`: Dash app factory.
- `interactive_pca/layouts/__init__.py`: Main app/PCA tab layout.
- `interactive_pca/callbacks/`: Callback registration and behavior.
- `interactive_pca/components/`: Reusable helpers for tables/hover/aesthetics.
- `interactive_pca/plots.py`: Plot generation helpers.
- `interactive_pca/data_loader.py`: Input loading + merge.
- `interactive_pca/args.py`: CLI parser and options.
- `interactive_pca/cli.py`: `interactive-pca` command entry point.

## Testing

```bash
pytest tests/
```

Useful targeted tests:

```bash
pytest tests/test_app_basic.py
pytest tests/test_pca_map_layout.py
pytest tests/test_tabs_working.py
```
