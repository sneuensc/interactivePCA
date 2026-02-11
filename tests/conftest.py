"""
Pytest configuration and fixtures.
"""

import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_eigenvec():
    """Create sample eigenvector data."""
    data = {
        'id': ['sample1', 'sample2', 'sample3'],
        'PC1': [0.01, 0.02, 0.015],
        'PC2': [-0.02, -0.01, 0.005],
        'PC3': [0.003, 0.001, 0.002],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_annotation():
    """Create sample annotation data."""
    data = {
        'Genetic ID': ['sample1', 'sample2', 'sample3'],
        'Country': ['Germany', 'Sweden', 'Norway'],
        'Date': [2020, 2021, 2022],
        'Latitude': [51.5, 60.0, 60.5],
        'Longitude': [10.0, 15.0, 11.0],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_eigenval():
    """Create sample eigenvalue data."""
    data = {
        'eigenvalue': [0.0234, 0.0145, 0.0089, 0.0056],
    }
    return pd.DataFrame(data)
