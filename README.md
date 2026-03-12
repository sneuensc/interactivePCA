# interactivePCA

**Interactive PCA visualization with Dash - a Python package for interactive exploration of PCA results.**

The interactivePCA allows users to visualize PCA or MDS scatter plots together with linked geographical and temporal dimensions, making it easy to explore population structure across space and time through interactive selection, zooming, and annotation-aware highlighting.

## Main features

- **3 plots + 1 table**
  - Interactive 2D/3D PCA or MDS scatter plot
  - Geographic map view of sample locations
  - Time plot for chronological exploration
  - Annotation table linked to all views
- **Interactive plots**
  - Zoom, pan, and drag navigation
  - Point selection and cross-highlighting
  - Rich hover tooltips
  - Customizable point styling (color, symbol, size, opacity)
- **Interactive table**
  - Row-based sample selection
  - Flexible annotation/column display

## Installation

### From source

```bash
git clone https://github.com/yourusername/interactive-pca.git
cd interactive-pca
pip install -e .
```

## Quick Start

### Command-line interface

Showing all features (PCA plot, map plot, time plot, annotation table)

```bash
## activate python environment if needed
# source .venv/bin/activate

interactive-pca --eigenvec data/samples.eigenvec \
                 --annotation data/samples.anno \
                 --latitude Latitude \
                 --longitude Longitude \
                 --time Date
```

Then open <http://localhost:8050> in your web browser.

### Minimal command-line interface

Showing only PCA scatter plot

```bash
interactive-pca --eigenvec data/samples.eigenvec
```

Then open <http://localhost:8050> in your web browser.

### List of all parameters

```bash
interactive-pca --help
```

### As a Python module

```python
from interactive_pca import load_eigenvec, load_annotation, parse_args

# Parse arguments
args = parse_args(['--eigenvec', 'data/samples.eigenvec', 
                   '--annotation', 'data/samples.anno'])

# Load data
eigenvec, pcs, id_col = load_eigenvec(args.eigenvec)
annotation, ann_desc, ann_cols = load_annotation(args.annotation, args)

# Your analysis here
```

## Requirements

- Python >= 3.8
- pandas >= 1.3.0
- numpy >= 1.20.0
- plotly >= 5.0.0
- dash >= 2.0.0
- dash-bootstrap-components >= 1.0.0
- dash-ag-grid >= 2.0.0

## Input Files

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

## Package Structure

```text
interactive_pca/
├── __init__.py              # Package exports
├── app.py                   # Dash app factory
├── args.py                  # CLI/parser arguments
├── cli.py                   # interactive-pca entry point
├── data_loader.py           # Input loading + merge helpers
├── plots.py                 # Plot generation helpers
├── utils.py                 # Generic utility functions
├── callbacks/
│   ├── __init__.py          # Callback registration
│   ├── aesthetics.py        # Aesthetics-related callbacks
│   ├── plots.py             # Plot update callbacks
│   └── selection.py         # Selection sync callbacks
├── components/
│   ├── __init__.py          # Component exports
│   ├── aesthetics.py        # Aesthetics data helpers
│   ├── config.py            # Layout config constants
│   ├── hover.py             # Hover text + hover callback factory
│   └── tables.py            # AG Grid column helper builders
└── layouts/
  └── __init__.py          # Main layout + PCA tab layout
```

## License

Not yet set

## Support

For issues and questions, please open an issue on GitHub or contact the maintainers.

## Author

  Samuel Neuenschwander (<samuel.neuenschwander@unil.ch>)
