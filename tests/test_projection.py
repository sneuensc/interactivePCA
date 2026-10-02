"""
End-to-end tests for the reference panel and least-squares projection.

The key correctness check is that projecting a reference individual with all
its SNPs reproduces the score it got when the panel was built, and that
projecting the same individual with most SNPs masked still lands close to it —
which is the whole point of fitting by least squares rather than by a plain
dot product.
"""

import numpy as np
import pandas as pd
import pytest

from interactive_pca.projection import (
    build_panel, combine, harmonise, load_panel, project_plink,
)
from interactive_pca.projection.plink import read_bim, read_dosages

# dosage of A1 -> 2-bit code (inverse of plink._CODE_TO_DOSAGE)
_DOSAGE_TO_CODE = {2: 0b00, 1: 0b10, 0: 0b11, -9: 0b01}


def write_plink(prefix, dosages, chroms, positions, a1, a2, iids, fids):
    """Write a PLINK 1 fileset; dosages is (n_samples, n_snps), NaN = missing."""
    n_samples, n_snps = dosages.shape
    pd.DataFrame({
        'chrom': chroms, 'snp': [f'rs{i}' for i in range(n_snps)],
        'cm': 0, 'pos': positions, 'a1': a1, 'a2': a2,
    }).to_csv(f'{prefix}.bim', sep='\t', header=False, index=False)
    pd.DataFrame({
        'fid': fids, 'iid': iids, 'pid': 0, 'mid': 0, 'sex': 0, 'pheno': -9,
    }).to_csv(f'{prefix}.fam', sep=' ', header=False, index=False)

    bytes_per_snp = (n_samples + 3) // 4
    with open(f'{prefix}.bed', 'wb') as fh:
        fh.write(bytes([0x6c, 0x1b, 0x01]))
        for j in range(n_snps):
            buf = bytearray(bytes_per_snp)
            for i in range(n_samples):
                d = dosages[i, j]
                code = _DOSAGE_TO_CODE[-9 if np.isnan(d) else int(d)]
                buf[i // 4] |= code << (2 * (i % 4))
            fh.write(bytes(buf))


@pytest.fixture
def reference(tmp_path):
    """A structured reference set: two groups with different allele frequencies."""
    rng = np.random.default_rng(0)
    # Enough SNPs that a heavily masked sample still clears MIN_SNPS.
    n_per_group, n_snps = 40, 6000
    freqs_a = rng.uniform(0.1, 0.9, n_snps)
    shift = rng.normal(0, 0.12, n_snps)
    freqs_b = np.clip(freqs_a + shift, 0.05, 0.95)

    blocks = [rng.binomial(2, f, size=(n_per_group, n_snps)).astype(float)
              for f in (freqs_a, freqs_b)]
    dosages = np.vstack(blocks)

    prefix = str(tmp_path / 'ref')
    write_plink(
        prefix, dosages,
        chroms=['1'] * n_snps, positions=np.arange(1, n_snps + 1),
        a1=['A'] * n_snps, a2=['G'] * n_snps,
        iids=[f'ref{i}' for i in range(2 * n_per_group)],
        fids=['popA'] * n_per_group + ['popB'] * n_per_group,
    )
    return prefix, dosages, tmp_path


def test_build_panel_writes_everything(reference, tmp_path):
    prefix, _, _ = reference
    panel_dir = str(tmp_path / 'panel')
    manifest = build_panel(prefix, panel_dir, k=5, maf=0.01, build='hg19',
                           name='test-panel')

    assert manifest['k'] == 5
    assert manifest['n_reference_samples'] == 80
    assert manifest['build'] == 'hg19'

    panel = load_panel(panel_dir)
    assert panel.loadings.shape == (manifest['n_snps'], 5)
    assert len(panel.scores) == 80
    assert list(panel.annotation['population'].unique()) == ['popA', 'popB']
    # Eigenvalues descending, variance explained sums to <= 1.
    assert np.all(np.diff(panel.eigenvalues) <= 0)
    assert sum(manifest['variance_explained']) <= 1.0 + 1e-9


def test_complete_sample_reproduces_its_reference_score(reference, tmp_path):
    """A reference individual, re-projected with every SNP, returns its own score."""
    prefix, dosages, _ = reference
    panel_dir = str(tmp_path / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)

    scores, report = project_plink(panel, prefix)
    assert report['used'] == panel.manifest['n_snps']

    expected = panel.scores[panel.pcs].to_numpy()
    got = scores[panel.pcs].to_numpy()
    assert np.allclose(got, expected, atol=1e-3)


def test_least_squares_beats_plain_projection_on_missing_data(reference, tmp_path):
    """With 70% of SNPs missing, least squares keeps the scale; dot product shrinks."""
    prefix, dosages, tmp = reference
    panel_dir = str(tmp / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)

    rng = np.random.default_rng(1)
    sparse = dosages.copy()
    mask = rng.random(sparse.shape) < 0.70
    sparse[mask] = np.nan

    sparse_prefix = str(tmp / 'sparse')
    bim = read_bim(prefix)
    write_plink(
        sparse_prefix, sparse,
        chroms=bim['chrom'], positions=bim['pos'], a1=bim['a1'], a2=bim['a2'],
        iids=[f'ref{i}' for i in range(sparse.shape[0])],
        fids=['target'] * sparse.shape[0],
    )

    lsq, _ = project_plink(panel, sparse_prefix)
    truth = panel.scores[panel.pcs].to_numpy()
    lsq_scores = lsq[panel.pcs].to_numpy()

    # Plain projection of the same data, for comparison.
    panel_rows = np.arange(panel.manifest['n_snps'])
    d = read_dosages(sparse_prefix, sparse.shape[0], len(bim), panel_rows)
    mu = panel.snps['mu'].to_numpy()
    sigma = panel.snps['sigma'].to_numpy()
    x = np.nan_to_num((d - mu) / sigma, nan=0.0)
    plain = x @ panel.loadings

    def scale(a, b):
        """Regression slope of a on b: 1.0 means no shrinkage."""
        return float((a * b).sum() / (b * b).sum())

    lsq_scale = scale(lsq_scores[:, :2], truth[:, :2])
    plain_scale = scale(plain[:, :2], truth[:, :2])

    assert plain_scale < 0.5, 'plain projection should shrink badly'
    assert lsq_scale > 0.8, f'least squares should keep the scale, got {lsq_scale}'
    assert abs(1 - lsq_scale) < abs(1 - plain_scale)


def test_harmonise_flips_swapped_alleles_and_drops_mismatches(reference, tmp_path):
    prefix, dosages, tmp = reference
    panel_dir = str(tmp / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)

    bim = read_bim(prefix).copy()
    n = len(bim)
    # First third swapped (A/G -> G/A). Second third a genuine mismatch: C/A
    # is neither A/G, nor its swap, nor either complement (C/T *would* be a
    # valid complement-swap of A/G, so it is not a mismatch at all).
    bim.loc[: n // 3, ['a1', 'a2']] = ['G', 'A']
    bim.loc[n // 3: 2 * n // 3, ['a1', 'a2']] = ['C', 'A']

    panel_rows, bim_rows, flip, report = harmonise(panel, bim)
    assert report['flipped'] > 0
    assert report['allele_mismatch'] > 0
    assert len(panel_rows) == len(bim_rows) == len(flip) == report['used']


def test_flipped_alleles_give_the_same_scores(reference, tmp_path):
    """Swapping A1/A2 and the dosages must not move a sample."""
    prefix, dosages, tmp = reference
    panel_dir = str(tmp / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)
    baseline, _ = project_plink(panel, prefix)

    bim = read_bim(prefix)
    flipped_prefix = str(tmp / 'flipped')
    write_plink(
        flipped_prefix, 2 - dosages,
        chroms=bim['chrom'], positions=bim['pos'],
        a1=bim['a2'], a2=bim['a1'],              # alleles swapped too
        iids=[f'ref{i}' for i in range(dosages.shape[0])],
        fids=['target'] * dosages.shape[0],
    )
    flipped, report = project_plink(panel, flipped_prefix)
    assert report['flipped'] == report['used']
    assert np.allclose(flipped[panel.pcs].to_numpy(),
                       baseline[panel.pcs].to_numpy(), atol=1e-3)


def test_ambiguous_sites_are_dropped_by_default(reference, tmp_path):
    prefix, dosages, tmp = reference
    panel_dir = str(tmp / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)

    # Make the panel's own alleles ambiguous for the comparison.
    panel.snps.loc[:, 'counted'] = 'A'
    panel.snps.loc[:, 'other'] = 'T'
    bim = read_bim(prefix).copy()
    bim.loc[:, ['a1', 'a2']] = ['A', 'T']

    _, _, _, dropped = harmonise(panel, bim, keep_ambiguous=False)
    _, _, _, kept = harmonise(panel, bim, keep_ambiguous=True)
    assert dropped['used'] == 0
    assert kept['used'] > 0


def test_combine_produces_a_single_loadable_table(reference, tmp_path):
    prefix, dosages, tmp = reference
    panel_dir = str(tmp / 'panel')
    build_panel(prefix, panel_dir, k=5, maf=0.01)
    panel = load_panel(panel_dir)
    scores, _ = project_plink(panel, prefix)

    table = combine(panel, scores)
    assert list(table.columns[:7]) == ['id'] + panel.pcs + ['set']
    assert set(table['set'].unique()) == {'reference', 'projected'}
    assert len(table) == len(panel.scores) + len(scores)
    assert 'population' in table.columns
