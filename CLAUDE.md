# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`interactive-pca` is a Python package that serves a Dash web app for interactively exploring PCA/MDS results from population-genetics data. It links four panels — a 2D/3D PCA scatter plot, a geographic map, a time plot, and an annotation table — so selection, hover, legend toggles, and styling stay synchronized across all views. Primary use is ancient-DNA analysis (e.g. AADR-format eigenvec + annotation files).

## Commands

Development uses the in-repo `venv/` (Python 3.14). Install editable with dev extras:

```bash
pip install -e ".[dev]"
```

Run the app (opens on http://localhost:8050):

```bash
interactive-pca --eigenvec data/samples.eigenvec          # minimal (PCA only)
interactive-pca --eigenvec data/samples.eigenvec \
                --annotation data/samples.anno \
                --latitude Lat. --longitude Long. --time Date   # all panels
interactive-pca --help                                    # full option list
```

`--dev` enables Dash debug mode + DEBUG logging; `--open-browser` auto-opens the browser. See `test_commands.sh` for worked examples against `data/aadr2.*`.

Tests, coverage, and formatting:

```bash
pytest tests/                                    # all tests
pytest tests/test_utils.py                       # one file
pytest tests/test_plots_present.py::test_name    # single test
pytest tests/ --cov=interactive_pca --cov-report=html

black interactive_pca/    # line-length 100
isort interactive_pca/    # black profile
flake8 interactive_pca/
```

## Architecture

The flow is `cli.py:main` → `parse_args` (args.py) → `app.py:create_app` → `app.run`. `create_app` does all the heavy lifting up front, then registers callbacks. Understanding these cross-cutting patterns matters more than any single module:

**Data pipeline (data_loader.py).** `load_eigenvec` reads a PLINK-format whitespace file, renames the ID column to `id`, and auto-detects PC columns via `find_incrementing_prefix_series` (finds `PC1, PC2, ...`-style series). `load_annotation` reads a tab-separated file and builds a parallel `annotation_desc` DataFrame describing every column — its abbreviation (long names are shortened, controlled by `--col-abbrev`), inferred `Type` (`continuous` vs `categorical`), level count, and whether it is eligible for grouping dropdowns (`Dropdown` == `'Yes'`, gated by `--max-factors`). **Column abbreviations, not original names, are used as the working column names everywhere downstream** — `annotation_desc` is the lookup table between the two, and user-supplied `--latitude`/`--time`/etc. names are resolved through `get_abbr_of`. `merge_data` left-joins eigenvec + annotation on their ID columns and optionally negates the time column (`--time-invert`, for BP dates).

**Panel visibility is derived, not configured.** Which of the four panels appear is computed from what the data actually contains: the map needs resolved lat+long columns present in the merged df, the time plot needs a resolved time column, the table needs any annotation. These `show_map_plot` / `show_time_plot` / `show_annotation_table` booleans are recomputed identically in both `app.py:create_app` and `callbacks/__init__.py:register_all_callbacks` and threaded into layout and callback registration to conditionally wire things up.

**Global DataFrame in plots.py.** The merged df is stored as a module-level `_df` via `set_dataframe(df)`, called once in `create_app`. Plot helpers (`get_selected_df`, `get_unselected_df`, etc.) read this global instead of receiving the df as an argument. Do not assume df is passed in when working in `plots.py`.

**Callback organization (callbacks/).** `register_all_callbacks` fans out to focused registration functions, each in its own module: `selection.py` (largest — selection sync across panels + table filter), `plots.py` (rebuilds figures on selection/aesthetic changes), `aesthetics.py` (color/symbol/size/opacity controls), `hover_sync.py` + `hover_details.py` (cross-panel hover highlighting and the details pane), `legend_sync.py` (legend toggles hide/show groups everywhere), and `snapshot.py` (image export). Hover-update callbacks are built by a factory (`register_hover_update_callbacks` in `components/`) and registered separately in `create_app`.

**State lives in `dcc.Store` components, not Python globals.** Panels communicate through stores declared in `layouts/__init__.py` — key ones: `selected-ids` and `selected-source` (which panel drove the selection, to avoid feedback loops), `marker-aesthetics-store` / `symbol-aesthetics-store`, `hidden-groups-store` (legend toggles), `trace-pca` / `trace-map` / `trace-time`, and `hover-detailed`. When adding interactivity, route it through a store rather than sharing state directly between callbacks. Tab switching and the draggable pane resizers are implemented as clientside (JavaScript) callbacks in `app.py`.

**Layouts (layouts/__init__.py, ~1000 lines).** `create_layout` returns `{'layout': ..., 'tab_content_map': ...}` and builds the whole UI: main PCA/annotation/help tabs plus the right-side Table/Details/Filter panel. The plot components have ids `pca-plot`, `pca-map-plot`, `time-histogram`; the table is a `dash-ag-grid`.

## Gotchas

- Packaging is defined entirely in `pyproject.toml` (setuptools backend); there is no `setup.py`. Dependencies, metadata, entry point (`interactive-pca = interactive_pca.cli:main`), and package discovery (`interactive_pca*` only) all live there.
- **Data stays out of git.** `.gitignore` ignores everything matching `data*`, so `data/` (a symlink to `../interactivePCA/data/`), `data-lucas/`, and any other `data`-prefixed folder are excluded. Sample data is not present on a fresh checkout and must not be committed — name new analysis data directories with a `data` prefix to keep them off GitHub automatically.
