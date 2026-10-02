"""
Command-line entry points for the reference panel and the projection.

``interactive-pca-refbuild``  build a panel from high-coverage genotypes (rare,
                              heavy — needs the full reference genotypes)
``interactive-pca-project``   project new samples onto a panel (routine, light)
"""

import argparse
import json
import logging
import sys

from .panel import build_panel, load_panel
from .project import combine, project_plink


def _setup_logging(verbose):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )


def refbuild_main(argv=None):
    parser = argparse.ArgumentParser(
        prog='interactive-pca-refbuild',
        description='Build a reference PCA panel from high-coverage genotypes.')
    parser.add_argument('--bfile', required=True, metavar='PREFIX',
                        help='PLINK prefix of the reference set (.bed/.bim/.fam).')
    parser.add_argument('--out', required=True, metavar='DIR',
                        help='Panel directory to create.')
    parser.add_argument('-k', '--components', type=int, default=20,
                        help='Number of components to retain (default: 20).')
    parser.add_argument('--maf', type=float, default=0.01,
                        help='Minor allele frequency threshold (default: 0.01).')
    parser.add_argument('--max-missing', type=float, default=0.05,
                        help='Maximum per-SNP missing fraction (default: 0.05).')
    parser.add_argument('--block-size', type=int, default=20000,
                        help='SNPs read per block (default: 20000).')
    parser.add_argument('--name', help='Panel name recorded in the manifest.')
    parser.add_argument('--build', help='Genome build, e.g. hg19. Recorded in the '
                                        'manifest and worth setting — projecting '
                                        'across builds silently fails to match.')
    parser.add_argument('--ploidy', default='diploid', choices=['diploid', 'pseudo-haploid'],
                        help='Ploidy of the reference genotypes (default: diploid).')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    logging.info('Building panel from %s ...', args.bfile)
    manifest = build_panel(
        args.bfile, args.out, k=args.components, maf=args.maf,
        max_missing=args.max_missing, block_size=args.block_size,
        name=args.name, build=args.build, ploidy=args.ploidy,
    )
    logging.info('Kept %d of %d SNPs, %d reference samples, k=%d.',
                 manifest['n_snps'], manifest['n_snps_input'],
                 manifest['n_reference_samples'], manifest['k'])
    var = manifest['variance_explained']
    logging.info('Variance explained: PC1 %.2f%%, PC2 %.2f%%.',
                 100 * var[0], 100 * var[1] if len(var) > 1 else float('nan'))
    logging.info('Panel written to %s', args.out)
    return 0


def project_main(argv=None):
    parser = argparse.ArgumentParser(
        prog='interactive-pca-project',
        description='Project samples onto a reference panel by least squares.')
    parser.add_argument('--panel', required=True, metavar='DIR',
                        help='Panel directory from interactive-pca-refbuild.')
    parser.add_argument('--bfile', required=True, metavar='PREFIX',
                        help='PLINK prefix of the samples to project.')
    parser.add_argument('--out', required=True, metavar='FILE',
                        help='Output table, ready for interactive-pca.')
    parser.add_argument('--ridge', type=float, default=0.0,
                        help='L2 penalty for samples with few SNPs (default: 0).')
    parser.add_argument('--keep-ambiguous', action='store_true',
                        help='Keep strand-ambiguous A/T and C/G sites, assuming '
                             'both datasets are on the same strand.')
    parser.add_argument('--projected-only', action='store_true',
                        help='Write only the projected samples, without the '
                             'reference cloud.')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    panel = load_panel(args.panel)
    logging.info("Panel '%s': %d SNPs, %d reference samples, k=%d, build=%s",
                 panel.manifest['name'], panel.manifest['n_snps'],
                 panel.manifest['n_reference_samples'], panel.k,
                 panel.manifest.get('build') or 'unspecified')

    scores, report = project_plink(panel, args.bfile,
                                   keep_ambiguous=args.keep_ambiguous,
                                   ridge=args.ridge)
    logging.info('Harmonisation: %d of %d panel SNPs matched by position, '
                 '%d usable (%d flipped, %d allele mismatch, %d ambiguous dropped).',
                 report['position_matches'], report['panel_snps'], report['used'],
                 report['flipped'], report['allele_mismatch'],
                 report['ambiguous_dropped'])

    n_failed = int(scores[panel.pcs[0]].isna().sum())
    if n_failed:
        logging.warning('%d of %d samples had too few SNPs and were not projected.',
                        n_failed, len(scores))
    logging.info('SNPs per projected sample: min %d, median %d, max %d.',
                 scores['n_snps'].min(), int(scores['n_snps'].median()),
                 scores['n_snps'].max())

    out = scores if args.projected_only else combine(panel, scores)
    out.to_csv(args.out, sep='\t', index=False, na_rep='NA')
    logging.info('Wrote %d rows to %s', len(out), args.out)
    logging.info('Load it with:  interactive-pca --eigenvec %s', args.out)
    return 0


def _report_json(report):  # pragma: no cover - debugging helper
    return json.dumps(report, indent=2)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(project_main())
