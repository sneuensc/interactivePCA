"""
Reference panel: build it from high-coverage genotypes, save it, load it back.

A panel freezes everything a later projection needs to place new samples into
the *same* coordinate system: the SNP set with its allele orientation, the
per-SNP centring/scaling constants, the loadings, and the reference scores.

Nothing here is ever recomputed from the samples being projected — doing so
would move the space out from under them.

Layout on disk::

    panel_dir/
      manifest.json      provenance and every convention used
      snps.tsv.gz        chrom, pos, counted, other, mu, sigma
      loadings.npy       (n_snps, k) float32
      eigenvalues.tsv    one per line, descending
      scores.tsv         reference individuals x k  (U*S convention)
      annotation.tsv     id, population

Maths
-----
With ``X`` the normalised reference matrix (n_ref x m, missing entries zeroed
after centring), ``X = U S V'``.  We never form ``X`` in full: with m >> n it
is cheaper and exact to accumulate the Gram matrix ``C = X X'`` (n x n) in
blocks of SNPs, eigendecompose it (``C = U S^2 U'``) and recover the loadings
as ``V = X' U / S``.

Scores are stored as ``U * S``. That is the convention a least-squares fit
returns for a reference individual's own row, so projected samples land on the
same scale as the cloud they are projected into.
"""

import gzip
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .plink import iter_dosage_blocks, read_bim, read_fam

FORMAT = 'interactive-pca-refpanel'
FORMAT_VERSION = 1


def _snp_stats(prefix, n_samples, n_snps, block_size):
    """Per-SNP mean dosage and missing fraction, in one pass over the .bed."""
    mu = np.empty(n_snps, dtype=np.float64)
    missing = np.empty(n_snps, dtype=np.float64)
    for start, stop, block in iter_dosage_blocks(prefix, n_samples, n_snps, block_size):
        nan = np.isnan(block)
        n_obs = (~nan).sum(axis=0)
        with np.errstate(invalid='ignore', divide='ignore'):
            mu[start:stop] = np.nansum(block, axis=0) / np.maximum(n_obs, 1)
        mu[start:stop] = np.where(n_obs > 0, mu[start:stop], np.nan)
        missing[start:stop] = nan.sum(axis=0) / block.shape[0]
    return mu, missing


def _normalise(block, mu, sigma):
    """Centre, scale, and zero out missing entries (the standard convention)."""
    x = (block - mu) / sigma
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def build_panel(prefix, out_dir, k=20, maf=0.01, max_missing=0.05,
                block_size=20000, name=None, build=None, ploidy='diploid',
                annotation=None):
    """Compute a reference panel from PLINK genotypes and write it to ``out_dir``.

    Args:
        prefix: PLINK prefix (``<prefix>.bed/.bim/.fam``) of the reference set.
        out_dir: directory to create.
        k: number of components to retain.
        maf: minor-allele-frequency threshold applied to the reference.
        max_missing: maximum per-SNP missing fraction in the reference.
        name / build / ploidy: recorded in the manifest.
        annotation: optional DataFrame with an ``id`` column to store instead
            of the .fam-derived one.

    Returns:
        The manifest dict.
    """
    bim, fam = read_bim(prefix), read_fam(prefix)
    n_snps, n_samples = len(bim), len(fam)
    if k >= n_samples:
        raise ValueError(f'k={k} must be smaller than the {n_samples} reference samples.')

    mu, missing = _snp_stats(prefix, n_samples, n_snps, block_size)
    p = mu / 2.0
    sigma = np.sqrt(p * (1.0 - p))
    keep = (
        np.isfinite(mu)
        & (missing <= max_missing)
        & (sigma > 0)
        & (np.minimum(p, 1.0 - p) >= maf)
    )
    if keep.sum() <= k:
        raise ValueError(f'Only {keep.sum()} SNPs pass QC; need more than k={k}.')

    # Pass 2: Gram matrix over the retained SNPs.
    gram = np.zeros((n_samples, n_samples), dtype=np.float64)
    for start, stop, block in iter_dosage_blocks(prefix, n_samples, n_snps, block_size):
        mask = keep[start:stop]
        if not mask.any():
            continue
        x = _normalise(block[:, mask], mu[start:stop][mask], sigma[start:stop][mask])
        gram += x.astype(np.float64) @ x.astype(np.float64).T

    eigvals, eigvecs = np.linalg.eigh(gram)          # ascending
    order = np.argsort(eigvals)[::-1][:k]
    eigvals, U = eigvals[order], eigvecs[:, order]
    if np.any(eigvals <= 0):
        raise ValueError('Reference matrix is rank-deficient for the requested k.')
    S = np.sqrt(eigvals)

    # Pass 3: loadings V = X' U / S, written in SNP blocks.
    loadings = np.zeros((int(keep.sum()), k), dtype=np.float32)
    kept_before = np.cumsum(keep) - 1
    for start, stop, block in iter_dosage_blocks(prefix, n_samples, n_snps, block_size):
        mask = keep[start:stop]
        if not mask.any():
            continue
        x = _normalise(block[:, mask], mu[start:stop][mask], sigma[start:stop][mask])
        rows = kept_before[start:stop][mask]
        loadings[rows] = (x.T.astype(np.float64) @ U / S).astype(np.float32)

    os.makedirs(out_dir, exist_ok=True)
    snps = pd.DataFrame({
        'chrom': bim.loc[keep, 'chrom'].values,
        'pos': bim.loc[keep, 'pos'].values,
        'counted': bim.loc[keep, 'a1'].values,
        'other': bim.loc[keep, 'a2'].values,
        'mu': mu[keep],
        'sigma': sigma[keep],
    })
    with gzip.open(os.path.join(out_dir, 'snps.tsv.gz'), 'wt') as fh:
        snps.to_csv(fh, sep='\t', index=False)
    np.save(os.path.join(out_dir, 'loadings.npy'), loadings)
    np.savetxt(os.path.join(out_dir, 'eigenvalues.tsv'), eigvals, fmt='%.10g')

    pcs = [f'PC{i + 1}' for i in range(k)]
    scores = pd.DataFrame(U * S, columns=pcs)
    scores.insert(0, 'id', fam['iid'].values)
    scores.to_csv(os.path.join(out_dir, 'scores.tsv'), sep='\t', index=False)

    if annotation is None:
        annotation = pd.DataFrame({'id': fam['iid'].values,
                                   'population': fam['fid'].values})
    annotation.to_csv(os.path.join(out_dir, 'annotation.tsv'), sep='\t', index=False)

    manifest = {
        'format': FORMAT,
        'format_version': FORMAT_VERSION,
        'name': name or os.path.basename(os.path.abspath(out_dir)),
        'build': build,
        'ploidy': ploidy,
        'normalization': 'patterson',
        'counted_allele': 'a1',
        'n_reference_samples': int(n_samples),
        'n_snps': int(keep.sum()),
        'n_snps_input': int(n_snps),
        'k': int(k),
        'maf': maf,
        'max_missing': max_missing,
        'variance_explained': (eigvals / np.trace(gram)).tolist(),
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source_prefix': os.path.abspath(prefix),
    }
    with open(os.path.join(out_dir, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


class Panel:
    """A loaded reference panel."""

    def __init__(self, manifest, snps, loadings, eigenvalues, scores, annotation):
        self.manifest = manifest
        self.snps = snps
        self.loadings = loadings
        self.eigenvalues = eigenvalues
        self.scores = scores
        self.annotation = annotation

    @property
    def k(self):
        return self.loadings.shape[1]

    @property
    def pcs(self):
        return [f'PC{i + 1}' for i in range(self.k)]


def load_panel(panel_dir):
    """Read a panel written by :func:`build_panel`."""
    with open(os.path.join(panel_dir, 'manifest.json')) as fh:
        manifest = json.load(fh)
    if manifest.get('format') != FORMAT:
        raise ValueError(f'{panel_dir} is not an {FORMAT} directory.')
    if manifest.get('format_version') != FORMAT_VERSION:
        raise ValueError(f"Panel format version {manifest.get('format_version')} "
                         f'is not supported (expected {FORMAT_VERSION}).')
    snps = pd.read_csv(os.path.join(panel_dir, 'snps.tsv.gz'), sep='\t',
                       dtype={'chrom': str, 'counted': str, 'other': str})
    annotation_path = os.path.join(panel_dir, 'annotation.tsv')
    return Panel(
        manifest=manifest,
        snps=snps,
        loadings=np.load(os.path.join(panel_dir, 'loadings.npy')),
        eigenvalues=np.loadtxt(os.path.join(panel_dir, 'eigenvalues.tsv'), ndmin=1),
        scores=pd.read_csv(os.path.join(panel_dir, 'scores.tsv'), sep='\t'),
        annotation=(pd.read_csv(annotation_path, sep='\t')
                    if os.path.exists(annotation_path) else None),
    )
