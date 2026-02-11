# Getting Started with interactivePCA

## Installation

### Step 1: Install the package

```bash
cd /path/to/interactive-pca
pip install -e .
```

The `-e` flag installs the package in "editable" mode, allowing you to modify the code and see changes immediately.

## Using the Package

### Method 1: As a Python Module

Import and use the functions directly in your Python code:

```python
import logging
from interactive_pca import (
    load_eigenvec,
    load_annotation,
    parse_args,
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load eigenvector data
eigenvec, pcs, id_col = load_eigenvec('data/samples.eigenvec')
print(f"Loaded {len(eigenvec)} samples with {len(pcs)} principal components")
print(f"PC columns: {pcs[:5]}")

# Load annotation data
annotation, ann_desc, ann_cols = load_annotation('data/samples.anno')
print(f"Loaded annotation with {len(annotation.columns)} columns")
```

### Method 2: Command-Line Interface

Run the Dash app from the command line:

```bash
interactive-pca --eigenvec data/samples.eigenvec \
                 --annotation data/samples.anno \
                 --latitude Latitude \
                 --longitude Longitude \
                 --time Date \
                 --group Population \
                 --server_port 8050 \
                 --open_browser
```

Then open http://localhost:8050 in your browser.

### Method 3: Jupyter Notebook

Create a notebook and import the package:

```python
import pandas as pd
from interactive_pca import (
    load_eigenvec,
    load_annotation,
    load_eigenval,
)

# Load your data
eigenvec, pcs, id_col = load_eigenvec('data/samples.eigenvec')
annotation, ann_desc, ann_cols = load_annotation('data/samples.anno')
eigenval = load_eigenval('data/samples.eigenval')

# Work with your data
print(eigenvec.head())
print(annotation.head())
```

## Available Functions

### Data Loading

- `load_eigenvec(filepath, id_column)` - Load PLINK eigenvector file
- `load_annotation(filepath, args)` - Load annotation file
- `load_eigenval(filepath)` - Load eigenvalue file
- `load_imiss(filepath)` - Load individual missing rate file
- `load_lmiss(filepath)` - Load SNP missing rate file
- `load_frq(filepath)` - Load allele frequency file
- `merge_data(eigenvec, annotation, ...)` - Merge eigenvector and annotation

### Utilities

- `is_notebook()` - Detect if running in Jupyter
- `make_unique_abbr(list, max_length)` - Create unique abbreviations
- `find_incrementing_prefix_series(columns)` - Find PC column names
- `dict_of_dicts_to_tuple()` - Convert nested dicts to tuples (for caching)
- `tuple_to_dict_of_dicts()` - Convert tuples back to dicts

### Arguments

- `parse_args(args, dev_mode)` - Parse command-line arguments
- `create_parser(script_name)` - Create argument parser

## Example: Complete Workflow

```python
import logging
import pandas as pd
from interactive_pca import (
    load_eigenvec,
    load_annotation,
    merge_data,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Load eigenvector data
eigenvec, pcs, id_col = load_eigenvec(
    'data/samples.eigenvec',
    id_column='ID'
)

# Load annotation
annotation, ann_desc, ann_cols = load_annotation(
    'data/samples.anno',
)

# Merge data
df = merge_data(
    eigenvec,
    annotation,
    eigenvec_id_col=id_col,
    annotation_id_col=ann_cols.get('id'),
    time_col=ann_cols.get('time'),
    invert_time=True
)

print(f"Final merged data shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print("\nFirst few rows:")
print(df.head())
```

## Development

### Running Tests

```bash
pytest tests/
```

### Running Tests with Coverage

```bash
pytest tests/ --cov=interactive_pca --cov-report=html
```

### Code Quality

Format code with Black:
```bash
black interactive_pca/
```

Sort imports with isort:
```bash
isort interactive_pca/
```

Check with flake8:
```bash
flake8 interactive_pca/
```

## Architecture

The package is organized into modules:

- **utils.py** - Utility functions for text processing and data manipulation
- **args.py** - Command-line argument parser
- **data_loader.py** - Data loading and preprocessing functions
- **cli.py** - Command-line interface entry point
- **app.py** - (Future) Dash application factory
- **callbacks.py** - (Future) Dash callback handlers
- **plots.py** - (Future) Plotting functions

## Next Steps

1. **Explore the data**: Use the utilities to load and inspect your data
2. **Integrate the Dash app**: Check `interactive_pca/app.py` (when ready) for the web interface
3. **Customize**: Modify the code to add your own visualizations
4. **Contribute**: Submit improvements via pull requests

## Troubleshooting

### Module not found

Ensure the package is installed in editable mode:
```bash
pip install -e .
```

### Import errors

Check that all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Data loading errors

Ensure your input files are in the correct format. See README.md for format specifications.

## Support

For issues and questions:
1. Check the README.md
2. Look at example files in the `data/` directory
3. Open an issue on GitHub
4. Contact the maintainers
