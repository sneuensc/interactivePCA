# interactivePCA

**Interactive PCA visualization with Dash - a Python package for interactive exploration of PCA results.**

The interactivePCA allows users to visualize PCA or MDS scatter plots together with linked geographical and temporal dimensions, making it easy to explore population structure across space and time through interactive selection, zooming, and annotation-aware highlighting.

**Main features**
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

```bash
interactive-pca --eigenvec data/samples.eigenvec \
                 --annotation data/samples.anno \
                 --latitude Latitude \
                 --longitude Longitude \
                 --time Date
```

Then open http://localhost:8050 in your web browser.

### Minimal command-line interface
Showing only PCA scatter plot

```bash
interactive-pca --eigenvec data/samples.eigenvec
```

Then open http://localhost:8050 in your web browser.


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
```
FID IID PC1 PC2 PC3 ...
pop1 sample1 0.01 -0.02 0.003 ...
pop1 sample2 0.02 -0.01 0.001 ...
```

### Annotation file (tab-separated)
```
Genetic ID	Country	Date	Latitude	Longitude	Group
sample1	Germany	2020	51.5	10.0	modern
sample2	Sweden	2021	60.0	15.0	modern
```



## Package Structure

```
interactive_pca/
├── __init__.py           # Package initialization
├── utils.py              # Utility functions
├── args.py               # Argument parser
├── data_loader.py        # Data loading functions
├── plots.py              # Plotting functions (future)
├── callbacks.py          # Dash callbacks (future)
├── cli.py                # Command-line interface (future)
└── app.py                # Main Dash app (future)
```

## License

Not yet set


## Support

For issues and questions, please open an issue on GitHub or contact the maintainers.

## Author

  Samuel Neuenschwander (samuel.neuenschwander@unil.ch)

