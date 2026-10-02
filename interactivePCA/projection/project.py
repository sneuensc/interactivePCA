"""
Least-squares projection of new samples onto a stored reference panel.

Why least squares
-----------------
Plain projection (``b = V' x``) assumes ``V_O' V_O = I`` for the observed SNP
subset ``O``. That holds only when nothing is missing. Ancient samples are
missing most of the panel, so plain projection pulls them systematically
toward the origin. Solving

    b = argmin || x_O - V_O b ||^2

instead fits each sample using only the SNPs it actually has, which is what
smartpca's ``lsqproject: YES`` does.

Allele orientation is the other half of the job: a genotype only means the
same thing as the reference if it counts the same allele, so every SNP is
matched on position *and* allele pair, flipped where needed, and dropped when
it cannot be resolved.
"""

import logging

import numpy as np
import pandas as pd

from .plink import read_bim, read_dosages, read_fam

_COMPLEMENT = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}
_AMBIGUOUS = {frozenset({'A', 'T'}), frozenset({'C', 'G'})}

# Below this many overlapping SNPs the fit is too ill-determined to report.
MIN_SNPS = 1000


def _complement(allele):
    return _COMPLEMENT.get(allele, allele)


def harmonise(panel, bim, keep_ambiguous=False):
    """Match a target .bim against the panel's SNPs.

    Returns ``(panel_rows, bim_rows, flip, report)``: parallel index arrays of
    the SNPs usable in both, a boolean array marking those whose dosages must
    be flipped (``2 - d``), and a dict of per-reason counts.
    """
    panel_snps = panel.snps.reset_index().rename(columns={'index': 'panel_row'})
    target = bim.reset_index().rename(columns={'index': 'bim_row'})
    merged = panel_snps.merge(
        target[['bim_row', 'chrom', 'pos', 'a1', 'a2']],
        on=['chrom', 'pos'], how='inner',
    )

    report = {'panel_snps': len(panel.snps), 'target_snps': len(bim),
              'position_matches': len(merged)}

    counted = merged['counted'].to_numpy()
    other = merged['other'].to_numpy()
    a1 = merged['a1'].to_numpy()
    a2 = merged['a2'].to_numpy()

    same = (a1 == counted) & (a2 == other)
    swapped = (a1 == other) & (a2 == counted)
    comp1 = np.array([_complement(x) for x in a1])
    comp2 = np.array([_complement(x) for x in a2])
    same_c = (comp1 == counted) & (comp2 == other)
    swapped_c = (comp1 == other) & (comp2 == counted)

    ambiguous = np.array([frozenset({c, o}) in _AMBIGUOUS
                          for c, o in zip(counted, other)])
    # On an ambiguous site the complement rules are indistinguishable from the
    # direct ones, so strand cannot be inferred; only a direct match is safe.
    usable_direct = same | swapped
    usable_comp = (same_c | swapped_c) & ~ambiguous
    if not keep_ambiguous:
        usable_direct = usable_direct & ~ambiguous
    usable = usable_direct | usable_comp
    flip = (swapped | (swapped_c & ~ambiguous)) & usable

    report.update({
        'ambiguous_dropped': int((ambiguous & (same | swapped | same_c | swapped_c)
                                  & ~usable).sum()),
        'allele_mismatch': int((~(same | swapped | same_c | swapped_c)).sum()),
        'flipped': int(flip[usable].sum()),
        'used': int(usable.sum()),
    })
    return (merged.loc[usable, 'panel_row'].to_numpy(),
            merged.loc[usable, 'bim_row'].to_numpy(),
            flip[usable], report)


def project_dosages(panel, dosages, panel_rows, flip, ridge=0.0):
    """Least-squares scores for each sample.

    Args:
        dosages: (n_samples, n_matched) A1 dosages, NaN where missing, already
            restricted and ordered to match ``panel_rows``.
        panel_rows: panel SNP indices for those columns.
        flip: boolean array marking columns needing ``2 - d``.
        ridge: optional L2 penalty, for samples with very few SNPs.

    Returns:
        ``(scores, n_used)`` — (n_samples, k) and the per-sample SNP count.
    """
    d = np.where(flip[None, :], 2.0 - dosages, dosages)
    mu = panel.snps['mu'].to_numpy()[panel_rows]
    sigma = panel.snps['sigma'].to_numpy()[panel_rows]
    V = panel.loadings[panel_rows]

    x = (d - mu) / sigma
    observed = np.isfinite(x)
    scores = np.full((dosages.shape[0], panel.k), np.nan)
    n_used = observed.sum(axis=1)

    for i in range(dosages.shape[0]):
        obs = observed[i]
        if obs.sum() < MIN_SNPS:
            logging.warning('Sample %d: only %d usable SNPs (minimum %d) — not projected.',
                            i, obs.sum(), MIN_SNPS)
            continue
        Vo, xo = V[obs], x[i, obs]
        if ridge > 0:
            gram = Vo.T @ Vo + ridge * np.eye(panel.k)
            scores[i] = np.linalg.solve(gram, Vo.T @ xo)
        else:
            scores[i] = np.linalg.lstsq(Vo, xo, rcond=None)[0]
    return scores, n_used


def project_plink(panel, prefix, keep_ambiguous=False, ridge=0.0):
    """Project every sample in a PLINK fileset onto ``panel``.

    Returns ``(DataFrame of id + PC scores + n_snps, report)``.
    """
    bim, fam = read_bim(prefix), read_fam(prefix)
    panel_rows, bim_rows, flip, report = harmonise(panel, bim, keep_ambiguous)
    if len(panel_rows) < MIN_SNPS:
        raise ValueError(
            f'Only {len(panel_rows)} SNPs overlap the panel (minimum {MIN_SNPS}). '
            'Check that both datasets use the same genome build and SNP panel.')

    order = np.argsort(bim_rows)
    panel_rows, bim_rows, flip = panel_rows[order], bim_rows[order], flip[order]
    dosages = read_dosages(prefix, len(fam), len(bim), bim_rows)

    scores, n_used = project_dosages(panel, dosages, panel_rows, flip, ridge)
    out = pd.DataFrame(scores, columns=panel.pcs)
    out.insert(0, 'id', fam['iid'].values)
    out['n_snps'] = n_used
    return out, report


def combine(panel, projected, reference_label='reference', target_label='projected'):
    """Stack reference scores and projected scores into one annotated table.

    The result is a single headed file carrying ids, dimensions and annotation
    columns — exactly what ``interactivePCA`` reads without a second file.
    """
    ref = panel.scores.copy()
    ref['set'] = reference_label
    if panel.annotation is not None:
        ref = ref.merge(panel.annotation, on='id', how='left')

    new = projected.copy()
    new['set'] = target_label
    combined = pd.concat([ref, new], ignore_index=True, sort=False)

    lead = ['id'] + panel.pcs + ['set']
    rest = [c for c in combined.columns if c not in lead]
    return combined[lead + rest]
