# interactivePCA

Interactive PCA visualization with Dash - a Python package for interactive exploration of PCA results.

## Features

- **Interactive 2D/3D PCA plots** with Plotly
- **Geographical visualization** of samples on maps
- **Time series plotting** with range selection
- **Data tables** with filtering and selection
- **Aesthetic customization** (colors, sizes, symbols)
- **Multiple data formats** support (PLINK eigenvec, annotation files)
- **Web-based dashboard** using Dash

## Installation

### From source

```bash
git clone https://github.com/yourusername/interactive-pca.git
cd interactive-pca
pip install -e .
```

### From PyPI (when available)

```bash
pip install interactive-pca
```

### Development installation

```bash
pip install -e ".[dev]"
```

## Quick Start

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

### Command-line interface

```bash
interactive-pca --eigenvec data/samples.eigenvec \
                 --annotation data/samples.anno \
                 --latitude Latitude \
                 --longitude Longitude \
                 --time Date \
                 --server_port 8050
```

Then open http://localhost:8050 in your web browser.

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

## Development

### Running tests

```bash
pytest tests/
```

### Code formatting

```bash
black interactive_pca/
isort interactive_pca/
```

### Linting

```bash
flake8 interactive_pca/
```

## License

MIT License - see LICENSE file for details

## Citation

If you use interactivePCA in your research, please cite:

```
[Your citation here]
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Run tests and linting
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Support

For issues and questions, please open an issue on GitHub or contact the maintainers.

## Authors

- Your Name (your.email@example.com)

## Acknowledgments

- PLINK project for eigenvector/eigenvalue format
- Plotly for interactive visualization
- Dash for the web framework
