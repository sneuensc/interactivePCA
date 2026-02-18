"""
Aesthetics management for interactive PCA visualizations.
"""

import json
import logging
import copy
import plotly.express as px


def load_aesthetics_file(filepath):
    """
    Load aesthetics from a JSON file.
    
    Args:
        filepath: Path to JSON aesthetics file
    
    Returns:
        Dictionary with aesthetics, or empty dict if file not found
    """
    try:
        with open(filepath, 'r') as f:
            aesthetics = json.load(f)
        logging.info(f"Loaded aesthetics from {filepath}")
        return aesthetics
    except FileNotFoundError:
        logging.warning(f"Aesthetics file not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing aesthetics file {filepath}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error loading aesthetics file {filepath}: {e}")
        return {}


def merge_aesthetics(defaults, overrides):
    """
    Merge override aesthetics into defaults, keeping default structure intact.
    
    Args:
        defaults: Default aesthetics dictionary (from parameters)
        overrides: Aesthetics overrides from file
    
    Returns:
        Merged aesthetics dictionary
    """
    result = copy.deepcopy(defaults)
    
    if not overrides:
        return result
    
    # Merge color settings
    if 'color' in overrides:
        if isinstance(overrides['color'], dict):
            for key, val in overrides['color'].items():
                result['color'][key] = val
    
    # Merge size settings
    if 'size' in overrides:
        if isinstance(overrides['size'], dict):
            for key, val in overrides['size'].items():
                try:
                    result['size'][key] = int(val)
                except (ValueError, TypeError):
                    pass
    
    # Merge opacity settings
    if 'opacity' in overrides:
        if isinstance(overrides['opacity'], dict):
            for key, val in overrides['opacity'].items():
                try:
                    result['opacity'][key] = float(val)
                except (ValueError, TypeError):
                    pass
    
    # Merge symbol settings
    if 'symbol' in overrides:
        if isinstance(overrides['symbol'], dict):
            for key, val in overrides['symbol'].items():
                result['symbol'][key] = val
    
    # Merge symbol_map settings
    if 'symbol_map' in overrides:
        if isinstance(overrides['symbol_map'], dict):
            for key, val in overrides['symbol_map'].items():
                result['symbol_map'][key] = val
    
    return result


def get_init_aesthetics(args, group, df):
    """
    Initialize aesthetics for the given group.
    
    Args:
        args: Command-line arguments
        group: Grouping variable name
        df: DataFrame with data
    
    Returns:
        Dictionary with aesthetic settings
    """
    aesthetics = {
        'color': {
            'default': args.point_color,
            'unselected': args.point_color_unselected
        },
        'size': {
            'default': args.point_size,
            'unselected': args.point_size_unselected
        },
        'opacity': {
            'default': args.point_opacity,
            'unselected': args.point_opacity_unselected
        },
        'symbol': {
            'default': args.point_symbol,
            'unselected': args.point_symbol_unselected
        },
        'symbol_map': {
            'default': args.point_symbol if args.point_symbol in ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star'] else 'circle',
            'unselected': args.point_symbol_unselected if args.point_symbol_unselected in ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 'star'] else 'circle'
        }
    }
    
    # Add color map for categorical variables
    if group != 'none' and group in df.columns:
        if df[group].dtype.kind in 'fi':
            # Continuous variable
            aesthetics['color']['colorscale'] = args.color_schema_continuous
        else:
            # Categorical variable
            unique_values = df[group].dropna().unique()
            px_colors = px.colors.qualitative.Plotly
            for i, val in enumerate(unique_values):
                # Convert to string to ensure consistent key type
                aesthetics['color'][str(val)] = px_colors[i % len(px_colors)]
    
    return aesthetics


def get_aesthetics_for_group(args, group, df, store_data):
    """
    Get aesthetics for a specific group from store or generate defaults.
    
    Args:
        args: Command-line arguments
        group: Grouping variable name
        df: DataFrame with data
        store_data: Aesthetics store data
    
    Returns:
        Dictionary with aesthetic settings for the group
    """
    if not store_data:
        return get_init_aesthetics(args, group, df)
    if group in store_data:
        return store_data[group]
    return get_init_aesthetics(args, group, df)
