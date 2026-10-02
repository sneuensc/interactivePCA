"""
Reference-panel PCA and least-squares projection.

Two halves, matching the two command-line entry points:

``build_panel`` / ``interactive-pca-refbuild``
    Compute a PCA from high-coverage reference genotypes once, and freeze
    everything a later projection needs (SNPs with allele orientation,
    per-SNP centring and scaling, loadings, reference scores).

``project_plink`` / ``interactive-pca-project``
    Place new — typically low-coverage, pseudo-haploid — samples into that
    fixed space by least squares, using only the SNPs each sample has.

The combined output is a single headed table that ``interactive-pca`` reads
directly, with a ``set`` column separating reference from projected samples.
"""

from .panel import Panel, build_panel, load_panel
from .project import combine, harmonise, project_dosages, project_plink

__all__ = [
    'Panel', 'build_panel', 'load_panel',
    'combine', 'harmonise', 'project_dosages', 'project_plink',
]
