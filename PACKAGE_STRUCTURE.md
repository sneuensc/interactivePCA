# Package Structure Overview

## Directory Tree

```
interactivePCA/
│
├── 📄 README.md                 # Main documentation with features, installation, usage
├── 📄 GETTING_STARTED.md        # Quick start guide and examples
├── 📄 REFACTORING_SUMMARY.md    # Detailed refactoring overview
├── 📄 LICENSE                   # MIT License
├── 📄 setup.py                  # Legacy setuptools configuration
├── 📄 pyproject.toml            # Modern Python project configuration
├── 📄 requirements.txt          # Package dependencies
├── 📄 MANIFEST.in               # Package data manifest
├── 📄 .gitignore                # Git ignore patterns
│
├── 📁 interactive_pca/          # Main package directory
│   │
│   ├── 📄 __init__.py           # Package initialization
│   │                             # Exports: utils, args, data_loader
│   │
│   ├── 📄 utils.py              # Utility functions
│   │   ├── make_unique_abbr()
│   │   ├── make_unique_abbr_of_df()
│   │   ├── get_abbr_of()
│   │   ├── deduplicate_columns()
│   │   ├── find_incrementing_prefix_series()
│   │   ├── dict_of_dicts_to_tuple()
│   │   ├── tuple_to_dict_of_dicts()
│   │   ├── save_dict_of_dicts_to_json()
│   │   ├── read_dict_of_dicts_from_json()
│   │   ├── is_notebook()
│   │   └── strip_ansi()
│   │
│   ├── 📄 args.py               # Argument parsing
│   │   ├── float_0_1()
│   │   ├── create_parser()
│   │   └── parse_args()
│   │
│   ├── 📄 data_loader.py        # Data loading & preprocessing
│   │   ├── load_imiss()
│   │   ├── load_lmiss()
│   │   ├── load_frq()
│   │   ├── load_eigenval()
│   │   ├── load_eigenvec()
│   │   ├── load_annotation()
│   │   └── merge_data()
│   │
│   ├── 📄 cli.py                # Command-line interface
│   │   ├── setup_logging()
│   │   └── main()
│   │
│   ├── 📄 app.py                # [Future] Dash application factory
│   ├── 📄 callbacks.py          # [Future] Dash callbacks
│   └── 📄 plots.py              # [Future] Plotting functions
│
├── 📁 tests/                    # Test suite
│   ├── 📄 __init__.py
│   ├── 📄 conftest.py           # Pytest configuration & fixtures
│   └── 📄 test_utils.py         # Utility function tests
│
└── 📁 data/                     # [To create] Sample data files
    ├── samples.eigenvec         # Example eigenvector file
    ├── samples.anno             # Example annotation file
    ├── samples.eigenval         # Example eigenvalue file
    └── README.md                # Data format documentation
```

## Module Dependencies

```
interactive_pca/
├── utils.py
│   └── Dependencies: re, json, difflib, collections, pandas
├── args.py
│   ├── Dependencies: argparse, sys
│   └── Imports: utils.is_notebook
├── data_loader.py
│   ├── Dependencies: logging, os, pandas
│   └── Imports: utils functions
├── cli.py
│   ├── Dependencies: sys, logging
│   └── Imports: args.parse_args
├── app.py [Future]
│   └── Imports: all modules
└── tests/
    └── pytest fixtures and tests
```

## File Sizes (Estimated)

```
interactive_pca/
├── __init__.py          ~150 lines
├── utils.py             ~300 lines
├── args.py              ~200 lines
├── data_loader.py       ~350 lines
├── cli.py               ~100 lines
├── app.py               ~50 lines (placeholder)
├── callbacks.py         ~50 lines (placeholder)
└── plots.py             ~50 lines (placeholder)
                         --------
Total package code:      ~1,250 lines

Documentation:
├── README.md            ~250 lines
├── GETTING_STARTED.md   ~400 lines
├── REFACTORING_SUMMARY  ~400 lines
                         --------
Total documentation:     ~1,050 lines

Tests:
├── test_utils.py        ~100 lines
├── conftest.py          ~60 lines
                         --------
Total tests:             ~160 lines
```

## Key Components

### 1. Core Data Processing (`data_loader.py`)
- Loads PLINK format files (eigenvec, eigenval)
- Processes annotation files
- Automatic PC detection
- Data merging and preprocessing

### 2. Utilities (`utils.py`)
- Text processing functions
- Data serialization
- Environment detection
- Caching helpers

### 3. Configuration (`args.py`)
- CLI argument definitions
- Type validation
- Default values
- Help documentation

### 4. CLI Interface (`cli.py`)
- Entry point for command-line usage
- Logging setup
- Argument validation
- Server management

### 5. Documentation
- README: Features, installation, usage
- GETTING_STARTED: Quick examples
- REFACTORING_SUMMARY: Migration guide

### 6. Project Configuration
- `setup.py`: Traditional setup script
- `pyproject.toml`: Modern config (PEP 517/518)
- `requirements.txt`: Dependencies list
- `MANIFEST.in`: Package data
- `.gitignore`: Git configuration

## Usage Examples by Component

### Using utils.py
```python
from interactive_pca.utils import make_unique_abbr, is_notebook
abbrs = make_unique_abbr(['apple', 'application', 'apply'])
```

### Using args.py
```python
from interactive_pca.args import parse_args
args = parse_args(['--eigenvec', 'file.txt'])
```

### Using data_loader.py
```python
from interactive_pca.data_loader import load_eigenvec
eigenvec, pcs, id_col = load_eigenvec('file.eigenvec')
```

### Using cli.py
```bash
interactive-pca --eigenvec data.eigenvec --annotation data.anno
```

### Using as package
```python
from interactive_pca import load_eigenvec, load_annotation
```

## Development Workflow

1. **Modify code** → Edit files in `interactive_pca/`
2. **Test changes** → Run `pytest tests/`
3. **Check quality** → Run `black`, `flake8`, `isort`
4. **Build package** → `python -m build`
5. **Install locally** → `pip install -e .`
6. **Test CLI** → `interactive-pca --help`
7. **Deploy** → Push to GitHub/PyPI

## Next Steps

1. ✅ Core modules extracted
2. ✅ Package structure created
3. ✅ Setup files configured
4. ✅ Tests added
5. ⏳ Migrate Dash app from notebook
6. ⏳ Add missing type hints
7. ⏳ Increase test coverage
8. ⏳ Add CI/CD pipeline
9. ⏳ Deploy to PyPI

## Integration Points

The refactored package can integrate with:

- **Jupyter notebooks** (import and use functions)
- **Python scripts** (CLI or module import)
- **Web frameworks** (Dash, Flask, FastAPI)
- **Pipelines** (Nextflow, Snakemake, CWL)
- **Docker containers** (containerized deployment)
- **Cloud platforms** (AWS, GCP, Azure)

## Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [Setuptools Documentation](https://setuptools.pypa.io/)
- [PEP 517 - Build Backend](https://www.python.org/dev/peps/pep-0517/)
- [PEP 518 - Build Requirements](https://www.python.org/dev/peps/pep-0518/)
