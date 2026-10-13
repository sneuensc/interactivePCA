# interactivePCA

**Interactive PCA visualization with Dash - a Python package for interactive exploration of PCA results.**

interactivePCA is a Dash web app for interactively exploring PCA/MDS results from population-genetics data. It links four views — a 2D/3D PCA scatter plot, a geographic map, a time plot, and an annotation table — so selection, hover highlighting, and point styling stay synchronized across all of them.

## Installation

Requires Python >= 3.8.

### From source

```bash
git clone https://github.com/sneuensc/interactivePCA.git
cd interactivePCA
pip install -e .
```

### Development install

Installs the package editable plus the test/lint tooling (pytest, black, isort, flake8):

```bash
pip install -e ".[dev]"
```

### Verify

```bash
interactivePCA --help
```

This should print the full list of command-line options. If it doesn't, see the Troubleshooting section below.

## User manual

### Main features: the four panels

#### PCA plot

Pick any two (or three, in 3D) continuous columns for the X/Y/Z axes from the dropdowns above the plot. **3D** toggles a rotatable `Scatter3d` view. The PCA plot isn't limited to PCs — it can visualize any 2D or 3D scatter of continuous columns.

#### Geographic map

Shown once latitude/longitude columns are resolved (via `--latitude`/`--longitude`, or picked live from the **X:**/**Y:** dropdowns). **Basemap** switches between `map` (world outline), `tiles` (interactive street/satellite imagery), and `none` (points only). Despite the name, this panel isn't limited to showing a geographic map — the same X:/Y: dropdowns can plot any two continuous columns as an ordinary 2D scatter.

#### Time plot

Plots any continuous column (not only the `--time` column); the other axis is either a jitter of the samples or the column's distribution, depending on the view. **View** switches between Scatter, Violin, Distribution and Overlay. In Scatter and Violin, **Grouping** controls whether samples are split by group, when **Color by** is a categorical column. **Bin size** sets the histogram bin width (Distribution/Overlay only). Overlay adds the selected samples' own distribution on top of the full one, where Distribution only ever shows the full histogram. **Invert** flips the axis direction (useful for e.g. a BP date column), **Rotate** swaps X/Y, and **Time slice** adds a draggable window that selects only the samples falling inside it — drag it, or use the arrows beside it, to scroll through time and watch the selected samples change live in the PCA and map panels.

#### Annotation table

Lists every sample with the metadata columns. To improve readability, the columns shown can be chosen in the **Annotation** tab (or via `--annotation-columns`). The same selected columns are also shown when hovering over a sample. Detailed hover is the default and can be suppressed via the **Hover detailed** toggle in the Settings tab, or at launch with `--hover-minimal`. This panel also has two other sub-tabs: **Details**, which shows the full hover information for the currently hovered sample, and **Filter**, which doesn't hide any rows in the table — instead it sets the selection to the samples matching a pandas `query()` expression (e.g. `Age > 1000 & Country == "Peru"`), exactly like any other selection method; the table's Status column, and every other panel, then reflects that selection.

### Cross-panel synchronization

The group coloring and shape set by **Color by** and **Shape by** apply simultaneously to all plots.

Hovering any sample — in the PCA plot, the map, the time plot, or an annotation table row — highlights that same sample in the other panels, with a minimal "ID" tooltip regardless of the **Hover detailed** setting.

The legend for color and shape is shown only once by default. This can be adjusted via **Legend mode** (Settings tab, or the live dropdown): `none` hides it everywhere, `once` shows it on a single active plot at a time, `everywhere` shows it on every panel that has one, simultaneously.

### Grouping / coloring and aesthetics

**Color by** groups/colors by any continuous or categorical column, including the PCs. **Shape by** groups any categorical column by shape. The aesthetics of every grouping and coloring can be individually adapted, as well as the aesthetics of the unselected points. Click **Aesthetics** to open the editor for the current Color-by/Shape-by column:

- **Categorical group:** a table with one row per category — edit color, size, opacity and symbol per value, and drag rows to set the draw order (row 1 draws last, i.e. on top).
- **Continuous group:** pick a color scale (Viridis, Plasma, ...) instead of per-value colors.
- **Shape-by** (a second, independent grouping): assigned its own marker symbols, shown as a second legend block.

Changes apply immediately to all three plots. Save a configuration to a JSON file for reuse with `--aesthetics-file`, or set simple global defaults once via `--point-color`, `--point-size`, `--point-opacity`, `--point-symbol` (and their `-unselected` counterparts) at launch.

### Selection

Sample selection can be made on any plot or the table, and the selected samples are immediately synchronized to the other plots and table. Selecting groups or samples can be done in several ways:

- **Legend:** use Plotly's built-in legend — click (or double-click) a legend entry to hide/show that group everywhere.
- **Lasso** or **box-select** allows selecting multiple samples in any of the figures.
- **Row selection** in the table allows selecting one or multiple samples.
- **Filter** allows selecting samples using a pandas `query()` expression (e.g. `Age > 1000 & Country == "Peru"`).
- **Time slice** in the time plot allows selecting samples within a given time window, and dragging that window left/right to scroll through time.

The **Selection** frame shows the number of selected samples and lets you **Freeze** the selection (so no other control — lasso, filter, time-slice, Reset — can change it until unfrozen) or **Save selection** as a plain-text file of sample IDs, for use outside the app. It also reports which method last produced the current selection, since each new selection — lasso, filter, row click, time-slice, etc. — replaces the previous one rather than combining with it.

### Session

An ongoing session can be stored and picked up later. There are three different ways to do this, each keeping a different amount of state:

- **Save view:** downloads a `session.json` holding the full launch configuration plus the current view — selection, aesthetics, axes, pane sizes and zoom. Reload it with `--session file.json` or the setup wizard's "Or load a saved session" option to continue on the exact same view next time.
- **Export Snapshot:** downloads a self-contained `interactivePCA_<timestamp>.html` file — the current PCA, map and time figures plus the annotation table and selection, built directly from what's on screen, no server round-trip. It needs no running Dash server to open: hover sync, legend-click sync, cross-plot lasso/box-select syncing, and a sortable/filterable table all work standalone, ported to plain JavaScript (Plotly.js and AG Grid are pulled from a CDN). Not included: the live aesthetics editor and the pandas filter query, both unsafe/impractical to reproduce without a server — colors are frozen as they appeared at export time, and AG Grid's own column sort/filter covers narrowing rows instead. Handy for sharing a point-in-time view with colleagues who don't run the app themselves.
- **Generate command:** produces the `interactivePCA ...` command line for the current setup; the full variant lists every parameter, not just non-defaults. It covers the data configuration — files, columns, axes, grouping — but not aesthetics or zoom, so it suits sharing a setup with colleagues or scripting a launch.
- **Restart** (top-right of the header) returns to the setup wizard without losing non-data settings like the server port.

### Launching interactivePCA

interactivePCA can be launched several different ways, depending on how much you specify up front — from nothing at all (a point-and-click setup wizard) to a fully explicit command line:

- **No arguments** (`interactivePCA`): opens a setup wizard instead of the plots. The PCA tab lets you type or browse to an eigenvec file and **Read** its columns, the Annotation tab does the same for an annotation file, and **Settings** holds every other option; each tab's **Load**/**Apply** button relaunches the app with those settings composed into the command line, so the result is identical to typing that full command yourself.
- **`--eigenvec` only**: starts with the PCA plot already showing; the Annotation tab still offers its loader, unless the eigenvec file itself has extra columns (see below).
- **Annotation embedded in the eigenvec file**: if `--annotation` is omitted but the eigenvec file has extra, non-coordinate columns, the Annotation tab offers "Use annotations from eigenvec file" to use them directly instead of reading a separate file.
- **Fully specified**, e.g. `--eigenvec samples.eigenvec --annotation samples.anno --latitude Lat. --longitude Long. --time Date`: every panel resolves immediately, no wizard step needed — see the walkthrough below.
- **`--session file.json`**: resumes a previously saved session (see **Save view** above) exactly where it left off, including selection, aesthetics, axes, pane sizes and zoom.
- **Single PCA plot**: if no annotation is passed, or the columns for the geographic map (`--latitude`/`--longitude`) or the time plot (`--time`) aren't defined, only the PCA plot is shown. To add the geographic map or time plot during a session, enable it in the Settings tab and then pick which columns to show.
- Useful regardless of the above: `--dev` enables debug mode and verbose logging, `--open-browser` opens the app in a browser automatically, and `--help` lists every option.

### Quick-start walkthrough

A worked example for an ancient-DNA dataset with coordinates and dates:

1. **Launch** with everything resolved up front:

   ```bash
   interactivePCA --eigenvec samples.eigenvec --annotation samples.anno \
     --latitude Lat. --longitude Long. --time Date
   ```

   Or launch with just `--eigenvec` and use the setup wizard's **Read** / **Load** buttons on the PCA and Annotation tabs instead.
2. **Explore structure:** on the PCA tab, set **Color by** to a region/population column; open **Aesthetics** to assign clearer colors and reorder overlapping groups.
3. **Check geography:** switch to the Map sub-panel; try the `tiles` basemap for a familiar street/satellite view.
4. **Check chronology:** on the Time plot, switch **View** to Distribution and adjust **Bin size**; enable **Time slice** and drag the window to watch clusters appear/disappear through time — the PCA and map panels highlight the same samples live.
5. **Cross-check a sample:** hover any sample in any panel — or click its row in the Annotation table — to see it highlighted everywhere else.
6. **Save your work:** click **Save view** to download a `session.json` capturing the exact state (including aesthetics and zoom), or use **Generate command** to copy a CLI command for colleagues who just need the data configuration.

### Tips, troubleshooting and command-line reference

- Use lasso or box selection on any plot to highlight the same samples everywhere, including the annotation table.
- The annotation table's "Status" column (selected/unselected/hidden) can also be edited directly to change selection or hide a row's group from the legend.
- Column names referencing annotation data can be given as either their original header or their abbreviated working name — both resolve to the same column.
- A command rejected with "invalid choice" for an aesthetics parameter (point size/opacity/symbol, color scale) means the value isn't one of the app's preset options; check `--help` for the exact list.
- If a relaunch (Refresh/Restart/Load) doesn't return, check the terminal/log — it most likely crashed on a data-loading error and needs a fix before trying again.

For the complete, always-current list of parameters, run:

```bash
interactivePCA --help
```

## Input files

### Eigenvector file (PLINK format)

```text
FID IID PC1 PC2 PC3 ...
pop1 sample1 0.01 -0.02 0.003 ...
pop1 sample2 0.02 -0.01 0.001 ...
```

### Annotation file (tab-separated)

```text
Genetic ID   Country   Date   Latitude   Longitude   Group
sample1      Germany   2020   51.5       10.0        modern
sample2      Sweden    2021   60.0       15.0        modern
```

Annotation can also be embedded directly in the eigenvec file as extra columns instead of a separate file — see **Launching interactivePCA** above.

## Package structure

```text
interactivePCA/
├── __init__.py              # Package exports
├── cli.py                   # interactivePCA entry point
├── app.py                   # Dash app factory
├── args.py                  # CLI/parser arguments
├── data_loader.py           # Input loading + merge helpers
├── plots.py                 # Plot generation helpers
├── relaunch.py              # Relaunch-on-port / reload-poller mechanism
├── utils.py                 # Generic utility functions
├── callbacks/
│   ├── __init__.py          # Callback registration
│   ├── selection.py         # Selection sync + table filter callbacks
│   ├── plots.py              # Figure rebuild callbacks
│   ├── aesthetics.py        # Color/symbol/size/opacity callbacks
│   ├── hover_sync.py        # Cross-panel hover highlighting
│   ├── hover_details.py     # Hover details pane
│   ├── legend_sync.py       # Legend toggle sync
│   ├── session.py           # Save view / load session
│   ├── setup.py             # Setup-wizard loader callbacks
│   ├── settings2.py         # Settings-tab callbacks
│   └── snapshot.py          # Export Snapshot (standalone HTML)
├── components/
│   ├── __init__.py          # Component exports
│   ├── aesthetics.py        # Aesthetics data helpers
│   ├── config.py            # Layout config constants
│   ├── hover.py             # Hover text + hover callback factory
│   └── tables.py            # AG Grid column helper builders
└── layouts/
    ├── __init__.py          # Main layout + PCA/Help tab layouts
    └── setup.py             # Setup-wizard + Settings-tab layouts
```

## License

MIT — see [LICENSE](LICENSE).

## Support

For issues and questions, please open an issue on GitHub or contact the maintainers.

## Author

Samuel Neuenschwander (<samuel.neuenschwander@unil.ch>)
