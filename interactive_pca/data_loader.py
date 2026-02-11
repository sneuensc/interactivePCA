"""
Data loading and preprocessing module.
"""

import logging
import os
import pandas as pd
from .utils import make_unique_abbr, get_abbr_of, deduplicate_columns, find_incrementing_prefix_series


def load_imiss(filepath):
    """
    Load PLINK imiss file (individual missing rate).
    
    Args:
        filepath: Path to imiss file
    
    Returns:
        DataFrame or None if not provided
    """
    if filepath is None:
        return None
    
    logging.info(f"Reading imiss file '{filepath}' ...")
    df_imiss = pd.read_csv(filepath, sep=r"\s+", skiprows=[1])
    logging.info(f"Reading imiss file '{filepath}' ... done.")
    return df_imiss


def load_lmiss(filepath):
    """
    Load PLINK lmiss file (SNP missing rate).
    
    Args:
        filepath: Path to lmiss file
    
    Returns:
        DataFrame or None if not provided
    """
    if filepath is None:
        return None
    
    logging.info(f"Reading lmiss file '{filepath}' ...")
    df_lmiss = pd.read_csv(filepath, sep=r"\s+", skiprows=[1], low_memory=False)
    logging.info(f"Reading lmiss file '{filepath}' ... done.")
    return df_lmiss


def load_frq(filepath):
    """
    Load PLINK frq file (allele frequency).
    
    Args:
        filepath: Path to frq file
    
    Returns:
        DataFrame or None if not provided
    """
    if filepath is None:
        return None
    
    logging.info(f"Reading frq file '{filepath}' ...")
    df_frq = pd.read_csv(filepath, sep=r"\s+")
    logging.info(f"Reading frq file '{filepath}' ... done.")
    return df_frq


def load_eigenval(filepath):
    """
    Load PLINK eigenval file (eigenvalues).
    
    Args:
        filepath: Path to eigenval file
    
    Returns:
        DataFrame with eigenvalues, or None if not provided
    """
    if filepath is None:
        return None
    
    logging.info(f"Reading eigenval file '{filepath}' ...")
    eigenval = pd.read_csv(filepath, sep="\t", header=None, names=["eigenvalue"])
    
    logging.info(f"   Found {len(eigenval)} eigenvalues.")
    
    # Compute variance explained
    eigenval["eigenvalue"] = eigenval["eigenvalue"] / eigenval["eigenvalue"].sum()
    
    # Add cumulative eigenvalues
    eigenval["cumulative"] = eigenval["eigenvalue"].cumsum()
    
    # Add index starting from 1
    eigenval["dimension"] = eigenval.index + 1
    
    # Reorder columns
    eigenval = eigenval[["dimension"] + [col for col in eigenval.columns if col != "dimension"]]
    
    logging.info(f"Reading eigenval file '{filepath}' ... done.")
    return eigenval


def load_eigenvec(filepath, id_column=None):
    """
    Load PLINK eigenvec file (eigenvectors).
    
    Args:
        filepath: Path to eigenvec file
        id_column: Name of ID column (default: first column)
    
    Returns:
        Tuple of (eigenvec_df, pc_list, id_column_name)
    """
    logging.info(f"Reading eigenvec file '{filepath}' ...")
    eigenvec = pd.read_csv(filepath, sep=r"\s+", header=0)
    
    # Determine ID column
    eigenvec_id = id_column if id_column is not None else eigenvec.columns[0]
    eigenvec.rename(columns={eigenvec_id: "id"}, inplace=True)
    
    # Find PC columns
    pcs = find_incrementing_prefix_series(eigenvec.columns)
    
    if len(pcs) < 2:
        logging.error(f'Not enough dimension columns found in the eigenvec file ({len(pcs)} found).')
        raise ValueError(f"Need at least 2 PCs, found {len(pcs)}")
    
    logging.info(f"   Found {len(pcs)} principal components ({', '.join(pcs[:2])}, ...).")
    
    # Scale PC columns (standard for PLINK output)
    nb_snp = 194926  # Number of SNPs - this should be configurable
    eigenvec[pcs] = eigenvec[pcs].div(nb_snp)
    
    logging.info(f"Reading eigenvec file '{filepath}' ... done.")
    return eigenvec, pcs, "id"


def load_annotation(filepath, args=None):
    """
    Load and process annotation file.
    
    Args:
        filepath: Path to annotation file
        args: Arguments namespace with annotation processing options
    
    Returns:
        Tuple of (annotation_df, annotation_desc_df, annotation_columns_dict)
    """
    if filepath is None:
        return None, None, {}
    
    logging.info(f"Reading annotation file '{filepath}' ...")
    annotation = pd.read_csv(filepath, sep='\t', na_values='..', low_memory=False)
    
    if annotation.empty:
        logging.warning(f"Warning: Annotation file '{filepath}' is empty.")
        return None, None, {}
    
    # Set defaults if args not provided
    if args is None:
        args = type('obj', (object,), {
            'annotationID': 'Genetic ID',
            'col_abbrev': 15,
            'legend_abbrev': 0,
            'max_factors': 400,
            'ignore_case': False,
            'ignore_space': False,
            'longitude': None,
            'latitude': None,
            'time': None,
            'group': None
        })()
    
    # Create abbreviation_desc dataframe
    annotation_desc = pd.DataFrame({
        'Abbreviation': make_unique_abbr(annotation.columns, max_length=args.col_abbrev),
        'Description': annotation.columns,
        'Type': ['continuous' if annotation[col].dtype.kind in 'fi' else 'categorical' 
                for col in annotation.columns],
        'N_levels': [annotation[col].nunique(dropna=False) if annotation[col].dtype.kind not in 'fi' 
                    else None for col in annotation.columns]
    })
    
    # Add 'Dropdown' column
    annotation_desc['Dropdown'] = [
        'Yes' if ((typ == 'continuous') or 
                 ((typ == 'categorical') and (nlev <= args.max_factors))) 
        else ''
        for typ, nlev in zip(annotation_desc['Type'], annotation_desc['N_levels'])
    ]
    
    # Rename columns with abbreviations
    annotation.columns = annotation_desc['Abbreviation']
    
    # Get annotation column names
    annotation_columns = {}
    
    # ID column
    if args.annotationID is not None:
        annotation_id = get_abbr_of(args.annotationID, 
                                   annotation_desc['Description'].to_list(), 
                                   annotation_desc['Abbreviation'].to_list())
        if annotation_id is None or annotation_id not in annotation.columns:
            logging.info(f"Warning: Specified annotationID '{args.annotationID}' not found. Using first column.")
            annotation_id = annotation.columns[0]
    else:
        annotation_id = annotation.columns[0]
    
    annotation_columns['id'] = annotation_id
    
    # Time column
    if args.time is not None:
        annotation_time = get_abbr_of(args.time, 
                                     annotation_desc['Description'].to_list(), 
                                     annotation_desc['Abbreviation'].to_list())
        if annotation_time and annotation_time in annotation.columns:
            annotation_columns['time'] = annotation_time
        else:
            logging.warning(f"Warning: Specified time '{args.time}' not found. Time graph disabled.")
    
    # Longitude column
    if args.longitude is not None:
        annotation_long = get_abbr_of(args.longitude, 
                                     annotation_desc['Description'].to_list(), 
                                     annotation_desc['Abbreviation'].to_list())
        if annotation_long and annotation_long in annotation.columns:
            annotation_columns['longitude'] = annotation_long
        else:
            logging.warning(f"Warning: Specified longitude '{args.longitude}' not found. Map disabled.")
    
    # Latitude column
    if args.latitude is not None:
        annotation_lat = get_abbr_of(args.latitude, 
                                    annotation_desc['Description'].to_list(), 
                                    annotation_desc['Abbreviation'].to_list())
        if annotation_lat and annotation_lat in annotation.columns:
            annotation_columns['latitude'] = annotation_lat
        else:
            logging.warning(f"Warning: Specified latitude '{args.latitude}' not found. Map disabled.")
    
    # Clean categorical columns if needed
    exclude_abbr = [v for k, v in annotation_columns.items() if k != 'id']
    categorical_cols = annotation_desc.loc[
        (annotation_desc['Type'] == 'categorical') &
        (annotation_desc['Dropdown'] == 'Yes') &
        (~annotation_desc['Abbreviation'].isin(exclude_abbr)),
        'Abbreviation'
    ].tolist()
    
    if len(categorical_cols) > 0:
        if args.ignore_case or args.ignore_space:
            if args.ignore_case:
                logging.info("   Ignoring case differences.")
            if args.ignore_space:
                logging.info("   Ignoring space differences.")
            annotation = deduplicate_columns(annotation, categorical_cols, 
                                            args.ignore_case, args.ignore_space)
        
        if args.legend_abbrev > 0:
            logging.info(f"   Shortening legend text to max {args.legend_abbrev} characters.")
            annotation = make_unique_abbr_of_df(annotation, categorical_cols, args.legend_abbrev)
    
    # Logging
    logging.info(f"   Found {(annotation_desc['Type'] == 'categorical').sum()} categorical columns in total.")
    logging.info(f"   Found {len(categorical_cols)} categorical columns used for grouping/coloring.")
    logging.info(f"   Found {(annotation_desc['Type'] == 'continuous').sum()} continuous columns.")
    
    if 'longitude' in annotation_columns and 'latitude' in annotation_columns:
        logging.info(f"   Found geographic coordinates: lat='{annotation_columns['latitude']}', lon='{annotation_columns['longitude']}'.")
    if 'time' in annotation_columns:
        logging.info(f"   Found time column: '{annotation_columns['time']}'.")
    
    logging.info(f"Reading annotation file '{filepath}' ... done.")
    
    return annotation, annotation_desc, annotation_columns


def merge_data(eigenvec, annotation, eigenvec_id_col='id', annotation_id_col=None, time_col=None, invert_time=False):
    """
    Merge eigenvector and annotation data.
    
    Args:
        eigenvec: Eigenvector DataFrame
        annotation: Annotation DataFrame (optional)
        eigenvec_id_col: ID column name in eigenvec
        annotation_id_col: ID column name in annotation
        time_col: Time column name to invert (optional)
        invert_time: Whether to negate time values
    
    Returns:
        Merged DataFrame
    """
    if annotation is not None and annotation_id_col is not None:
        df = eigenvec.merge(
            annotation,
            left_on=eigenvec_id_col,
            right_on=annotation_id_col,
            how="left"
        )
        
        if invert_time and time_col is not None and time_col in df.columns:
            df[time_col] = -df[time_col]
    else:
        df = eigenvec.copy()
    
    # Ensure 'id' column is first
    if df.columns[0] != 'id':
        df = df[['id'] + [c for c in df.columns if c != 'id']]
    
    return df
