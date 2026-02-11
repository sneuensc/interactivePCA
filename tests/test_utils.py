"""
Tests for interactive_pca package.
"""

import pytest
from interactive_pca.utils import (
    make_unique_abbr,
    find_incrementing_prefix_series,
    is_notebook,
    strip_ansi,
)


class TestUtils:
    """Test utility functions."""
    
    def test_make_unique_abbr_basic(self):
        """Test basic abbreviation."""
        result = make_unique_abbr(['apple', 'application', 'apply'])
        assert len(result) == len(['apple', 'application', 'apply'])
        assert len(set(result)) == len(result)  # All unique
    
    def test_make_unique_abbr_with_length(self):
        """Test abbreviation with custom length."""
        result = make_unique_abbr(['test', 'team', 'terror'], max_length=2)
        assert all(len(abbr) <= 2 for abbr in result)
    
    def test_find_incrementing_prefix_series(self):
        """Test finding PC columns."""
        columns = ['PC1', 'PC2', 'PC3', 'PC4', 'other']
        result = find_incrementing_prefix_series(columns)
        assert result == ['PC1', 'PC2', 'PC3', 'PC4']
    
    def test_find_incrementing_prefix_series_with_gaps(self):
        """Test finding PC columns with gaps."""
        columns = ['PC1', 'PC3', 'PC5']
        result = find_incrementing_prefix_series(columns)
        assert result == []  # No consecutive sequence
    
    def test_is_notebook(self):
        """Test notebook detection."""
        result = is_notebook()
        assert isinstance(result, bool)
    
    def test_strip_ansi(self):
        """Test ANSI stripping."""
        text = "Hello \x1B[31mWorld\x1B[0m"
        result = strip_ansi(text)
        assert result == "Hello World"


if __name__ == '__main__':
    pytest.main([__file__])
