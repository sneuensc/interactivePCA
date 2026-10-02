"""
Minimal PLINK 1 binary (.bed/.bim/.fam) reader.

Only what the reference/projection pipeline needs: SNP metadata, sample
metadata, and dosages streamed in blocks of SNPs so a 1.2M-SNP panel never
has to be held in memory at once.

Dosage convention
-----------------
Dosages count the **A1 allele** (column 5 of the .bim), matching
``plink --recode A``. The two-bit codes in a .bed are

    0b00 -> 2  (homozygous A1)
    0b01 -> missing
    0b10 -> 1  (heterozygous)
    0b11 -> 0  (homozygous A2)

and samples are packed four to a byte, low bits first, SNP-major.
"""

import numpy as np
import pandas as pd

# code -> dosage of A1; 3 is 0b11 (hom A2), 1 is 0b01 (missing)
_CODE_TO_DOSAGE = np.array([2.0, np.nan, 1.0, 0.0], dtype=np.float32)

_BIM_COLUMNS = ['chrom', 'snp', 'cm', 'pos', 'a1', 'a2']
_FAM_COLUMNS = ['fid', 'iid', 'pid', 'mid', 'sex', 'pheno']


def read_bim(prefix):
    """SNP table: chrom, snp, cm, pos, a1, a2 (a1 is the counted allele)."""
    bim = pd.read_csv(f'{prefix}.bim', sep=r'\s+', header=None,
                      names=_BIM_COLUMNS, dtype={'chrom': str, 'a1': str, 'a2': str})
    bim['a1'] = bim['a1'].str.upper()
    bim['a2'] = bim['a2'].str.upper()
    return bim


def read_fam(prefix):
    """Sample table: fid, iid, pid, mid, sex, pheno."""
    return pd.read_csv(f'{prefix}.fam', sep=r'\s+', header=None,
                       names=_FAM_COLUMNS, dtype={'fid': str, 'iid': str})


def _check_magic(fh):
    magic = fh.read(3)
    if magic[:2] != b'\x6c\x1b':
        raise ValueError('Not a PLINK .bed file (bad magic bytes).')
    if magic[2:3] != b'\x01':
        raise ValueError('Individual-major .bed files are not supported; '
                         're-save with a recent PLINK.')


def iter_dosage_blocks(prefix, n_samples, n_snps, block_size=20000):
    """Yield ``(start, stop, dosages)`` with dosages shaped (n_samples, stop-start).

    Missing genotypes are NaN. Blocks are read straight off disk, so peak
    memory is ``n_samples * block_size`` floats regardless of panel size.
    """
    bytes_per_snp = (n_samples + 3) // 4
    with open(f'{prefix}.bed', 'rb') as fh:
        _check_magic(fh)
        for start in range(0, n_snps, block_size):
            stop = min(start + block_size, n_snps)
            raw = fh.read(bytes_per_snp * (stop - start))
            if len(raw) < bytes_per_snp * (stop - start):
                raise ValueError('.bed file is shorter than its .bim implies.')
            buf = np.frombuffer(raw, dtype=np.uint8).reshape(stop - start, bytes_per_snp)
            # Unpack 4 two-bit codes per byte, low bits first.
            codes = np.empty((stop - start, bytes_per_snp * 4), dtype=np.uint8)
            for i in range(4):
                codes[:, i::4] = (buf >> (2 * i)) & 0b11
            dosages = _CODE_TO_DOSAGE[codes[:, :n_samples]]
            yield start, stop, dosages.T


def read_dosages(prefix, n_samples, n_snps, snp_index=None):
    """Read dosages for selected SNPs into one (n_samples, n_selected) array.

    ``snp_index`` is an array of .bim row numbers (ascending); None reads all.
    Intended for the projection side, where only the panel's SNPs are needed.
    """
    if snp_index is None:
        snp_index = np.arange(n_snps)
    snp_index = np.asarray(snp_index)
    out = np.empty((n_samples, len(snp_index)), dtype=np.float32)
    wanted = np.zeros(n_snps, dtype=bool)
    wanted[snp_index] = True
    # Position of each wanted SNP within the output columns.
    dest = np.cumsum(wanted) - 1
    for start, stop, block in iter_dosage_blocks(prefix, n_samples, n_snps):
        mask = wanted[start:stop]
        if mask.any():
            out[:, dest[start:stop][mask]] = block[:, mask]
    return out
