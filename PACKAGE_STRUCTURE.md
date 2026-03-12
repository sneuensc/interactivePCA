# Package Structure Overview

This document reflects the current structure of the `interactive-pca` repository.

## Repository Tree

```text
interactive-pca/
├── README.md
├── GETTING_STARTED.md
├── INDEX.md
├── PACKAGE_STRUCTURE.md
├── APP_IMPLEMENTATION.md
├── PLOTS_FIXED.md
├── MAP_TAB_ADDED.md
├── REFACTORING_STATUS.md
├── REFACTORING_SUMMARY.md
├── LICENSE
├── MANIFEST.in
├── setup.py
├── pyproject.toml
├── requirements.txt
├── run_sample_app.py
├── data/
├── tests/
└── interactive_pca/
    ├── __init__.py
    ├── app.py
    ├── args.py
    ├── cli.py
    ├── data_loader.py
    ├── plots.py
    ├── utils.py
    ├── assets/
    ├── callbacks/
    │   ├── __init__.py
    │   ├── aesthetics.py
    │   ├── plots.py
    │   └── selection.py
    ├── components/
    │   ├── __init__.py
    │   ├── aesthetics.py
    │   ├── config.py
    │   ├── hover.py
    │   └── tables.py
    └── layouts/
        └── __init__.py
```

## Runtime Modules

- `interactive_pca/cli.py`: CLI entry point (`interactive-pca`).
- `interactive_pca/app.py`: App factory (`create_app`) that loads data, builds layout, and registers callbacks.
- `interactive_pca/layouts/__init__.py`: Main Dash layout and PCA tab composition.
- `interactive_pca/callbacks/`: Callback modules split by concern (`selection`, `plots`, `aesthetics`).
- `interactive_pca/components/`: Reusable UI/helper logic (tables, hover, aesthetics config).
- `interactive_pca/data_loader.py`: Input file loading and merge logic.
- `interactive_pca/plots.py`: Plot construction helpers.
- `interactive_pca/args.py`: CLI argument parser.
- `interactive_pca/utils.py`: General utility helpers.

## Notes on Conditional Panels

Current UI behavior in `create_pca_tab`:

- If `--annotation` is missing: annotation table, map, and time plot are suppressed.
- If `--latitude`/`--longitude` are missing: map panel is suppressed.
- If `--time` is missing: time plot is suppressed.
