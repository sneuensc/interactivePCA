"""
Utility functions for text processing and data cleaning.
"""

import re
import json
import math
import difflib
import fnmatch
from collections import defaultdict
import pandas as pd


def split_id_tokens(text):
    """Split a ";"- or ","-separated list of IDs/patterns, trimming whitespace
    around each token (so "*.AG, *.SG" and "*.AG;*.SG" both work).
    """
    return [t.strip() for t in re.split(r'[;,]', text) if t.strip()]


def resolve_id_pattern(pattern_str, all_ids):
    """Resolve a comma/semicolon-separated list of fnmatch-style ID patterns
    against all_ids. A token prefixed with "!" excludes its matches instead
    of including them (e.g. "!*.DG" drops *.DG samples); if only "!" tokens
    are given, the base set is everyone (so "!*.DG" alone means "all but
    *.DG", no need to also spell out a catch-all "*").
    """
    tokens = split_id_tokens(pattern_str)
    includes = [t for t in tokens if not t.startswith('!')]
    excludes = [t[1:] for t in tokens if t.startswith('!') and t[1:]]
    if includes:
        keep = set()
        for tok in includes:
            keep.update(fnmatch.filter(all_ids, tok))
    else:
        keep = set(all_ids)
    for tok in excludes:
        keep.difference_update(fnmatch.filter(all_ids, tok))
    return keep


def nice_step(x):
    """
    Round x up to a 'nice' number for a slider step or default window size —
    1, 2, or 5 times a power of 10 (the same convention plotting libraries use
    for axis tick spacing), so users see round numbers like 1000 or 50 instead
    of a raw fraction of the data range like 1183.2 or 59.16.
    """
    if x <= 0:
        return 1
    exponent = math.floor(math.log10(x))
    fraction = x / (10 ** exponent)
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    step = nice_fraction * (10 ** exponent)
    return int(step) if step >= 1 else step


def nice_bounds(lo, hi, step):
    """
    Round a [lo, hi] range outward to the nearest multiple of `step` — floor
    for lo, ceil for hi — so slider positions land on round numbers (e.g.
    1400/13300 instead of the raw data extremes 1450/13282) without ever
    excluding real data (widening the range is always safe, narrowing isn't).
    """
    if step <= 0:
        return lo, hi
    return math.floor(lo / step) * step, math.ceil(hi / step) * step


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

    # Clean: remove special characters, then replace spaces with underscores
    cleaned = [space_re.sub('_', clean_re.sub('', str(elem))) for elem in cur_list]

    # Base abbreviation: truncate to max_length.
    bases = [elem[:max_length].rstrip('_') for elem in cleaned]

    # Make unique while never exceeding max_length: when a numeric suffix is
    # needed to disambiguate, the prefix is shortened so that
    # len(prefix) + len(suffix) <= max_length.
    used = set()
    unique_abbr = []
    for base in bases:
        if base not in used:
            unique_abbr.append(base)
            used.add(base)
            continue
        n = 1
        while True:
            suffix = str(n)
            prefix_len = max(0, max_length - len(suffix))
            candidate = (base[:prefix_len].rstrip('_') + suffix)
            if candidate not in used:
                break
            n += 1
        unique_abbr.append(candidate)
        used.add(candidate)

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
