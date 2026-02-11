"""
Utility functions for text processing and data cleaning.
"""

import re
import json
import difflib
from collections import defaultdict
import pandas as pd


def make_unique_abbr(cur_list, max_length=3):
    """
    Abbreviate a list of strings to a maximum length, preserving uniqueness.
    
    Args:
        cur_list: List of strings to abbreviate
        max_length: Maximum length of abbreviations (default 3)
    
    Returns:
        List of unique abbreviations
    """
    clean_re = re.compile(r'[^a-zA-Z0-9 ]')
    space_re = re.compile(r' ')

    # Clean: remove special characters
    cleaned = [clean_re.sub('', str(elem)) for elem in cur_list]

    # Abbreviate: replace spaces with underscores and truncate
    abbreviated = [space_re.sub('_', elem[:max_length]).rstrip('_') for elem in cleaned]

    # Make unique using a counter
    counter = defaultdict(int)
    unique_abbr = []
    for abbr in abbreviated:
        new_abbr = abbr
        while new_abbr in counter:
            counter[abbr] += 1
            new_abbr = f"{abbr}{counter[abbr]}"
        counter[new_abbr] = 0
        unique_abbr.append(new_abbr)

    return unique_abbr


def make_unique_abbr_of_df(df, cols, max_length=3):
    """
    Abbreviate the values in the specified columns of a DataFrame.
    Each unique value in the column is replaced by a unique abbreviation.
    
    Args:
        df: DataFrame to modify
        cols: List of column names to abbreviate
        max_length: Maximum length of abbreviations
    
    Returns:
        Modified DataFrame
    """
    for col in cols:
        unique_vals = df[col].astype(str).unique()
        abbrs = make_unique_abbr(unique_vals, max_length)
        abbr_map = dict(zip(unique_vals, abbrs))
        df[col] = df[col].astype(str).map(abbr_map)
    return df


def get_abbr_of(target, lookup, returns=None):
    """
    Search for the best text match within a list of words.
    
    Args:
        target: Target string to find
        lookup: List of strings to search in
        returns: Optional list of return values corresponding to lookup
    
    Returns:
        Matched value from returns list, or matched lookup string if returns is None
    """
    closest = difflib.get_close_matches(target, lookup, n=1)
    if not closest:
        print(f"Warning: No match found for {target} in {lookup}")
        return None
    
    if returns is None:
        match = closest[0]
    else:
        match = returns[lookup.index(closest[0])]

    return match


def deduplicate_columns(df, columns, ignore_case=True, ignore_space=True):
    """
    De-duplicate columns ignoring capitalization and space differences (keep first version of each).
    
    Args:
        df: DataFrame to modify
        columns: List of column names to deduplicate
        ignore_case: Whether to ignore case differences
        ignore_space: Whether to ignore space differences
    
    Returns:
        Modified DataFrame
    """
    for col in columns:
        norm_col = f'_norm_{col}'
        series = df[col].astype(str)
        if ignore_case:
            series = series.str.lower()
        if ignore_space:
            series = series.str.replace(r'\s+', '', regex=True)
        df[norm_col] = series
        first_map = df.drop_duplicates(norm_col, keep='first').set_index(norm_col)[col]
        df[col] = df[norm_col].map(first_map)
        df.drop(columns=[norm_col], inplace=True)
    return df


def find_incrementing_prefix_series(columns):
    """
    Find automatically the PCA dimensions prefix.
    
    Args:
        columns: List of column names to search
    
    Returns:
        List of column names with incrementing prefix (e.g., ['PC1', 'PC2', 'PC3'])
    """
    pattern = re.compile(r'^([A-Za-z_]+)(\d+)$')
    prefix_groups = defaultdict(list)

    # Group columns by prefix
    for col in columns:
        match = pattern.match(col)
        if match:
            prefix, num = match.groups()
            prefix_groups[prefix].append(int(num))

    # Find prefixes with longest incrementing series
    longest_series = []
    for prefix, nums in prefix_groups.items():
        nums_sorted = sorted(nums)
        # Check if numbers form a consecutive sequence
        if nums_sorted == list(range(nums_sorted[0], nums_sorted[-1] + 1)):
            series = [f"{prefix}{n}" for n in nums_sorted]
            if len(series) > len(longest_series):
                longest_series = series

    return longest_series


def dict_of_dicts_to_tuple(d):
    """
    Convert a nested dict to a hashable tuple representation.
    
    Args:
        d: Dictionary to convert
    
    Returns:
        Tuple representation suitable for caching
    """
    if d is None:
        return tuple()

    def _normalize(val):
        if isinstance(val, dict):
            return tuple(
                (str(k), _normalize(v))
                for k, v in sorted(val.items(), key=lambda it: str(it[0]))
            )
        if isinstance(val, (list, tuple)):
            return tuple(_normalize(v) for v in val)
        if isinstance(val, (int, float, str, bool)) or val is None:
            return val
        return str(val)

    return tuple((str(k), _normalize(v)) for k, v in sorted(d.items(), key=lambda it: str(it[0])))


def tuple_to_dict_of_dicts(t):
    """
    Convert a tuple representation back to a nested dict.
    
    Args:
        t: Tuple to convert
    
    Returns:
        Nested dictionary
    """
    if not t:
        return {}

    def _denormalize(val):
        if isinstance(val, tuple) and all(isinstance(e, tuple) and len(e) == 2 for e in val):
            return {k: _denormalize(v) for k, v in val}
        if isinstance(val, tuple):
            return [_denormalize(v) for v in val]
        return val

    return {k: _denormalize(v) for k, v in t}


def save_dict_of_dicts_to_json(data, filename):
    """
    Save aesthetics dict to JSON file.
    
    Args:
        data: Dictionary to save
        filename: Output file path
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


def read_dict_of_dicts_from_json(filename):
    """
    Read aesthetics dict from JSON file.
    
    Args:
        filename: Input file path
    
    Returns:
        Dictionary loaded from file
    """
    with open(filename, 'r') as f:
        return json.load(f)


def is_notebook():
    """
    Detect if code is running in a Jupyter notebook environment.
    
    Returns:
        True if in notebook, False otherwise
    """
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except Exception:
        return False  # Probably standard Python interpreter


def strip_ansi(text):
    """
    Remove ANSI escape sequences from text.
    
    Args:
        text: String with ANSI codes
    
    Returns:
        String with ANSI codes removed
    """
    ansi_escape_re = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape_re.sub('', text)
