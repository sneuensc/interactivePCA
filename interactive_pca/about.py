"""
Provenance shown in the About dialog: who wrote it, which release, which commit.

The commit is resolved from the working tree when the package is used from a
checkout (the usual case here, since it is installed with ``pip install -e``).
An installed wheel has no ``.git`` alongside it, so the commit is simply absent
rather than wrong — every lookup degrades to None instead of raising.
"""

import functools
import os
import subprocess

try:                                     # Python 3.8+
    from importlib import metadata as _metadata
except ImportError:                      # pragma: no cover - very old runtimes
    _metadata = None

DIST = 'interactivePCA'
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args):
    """Run a git command in the package's own tree; None if that isn't possible."""
    try:
        out = subprocess.run(
            ('git', '-C', _ROOT) + args,
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


@functools.lru_cache(maxsize=1)
def version_info():
    """Return ``{version, author, email, commit, commit_date, dirty}``.

    Cached: the values cannot change while the process runs, and the git calls
    should not be repeated every time the dialog opens.
    """
    version = author = email = None
    if _metadata is not None:
        try:
            meta = _metadata.metadata(DIST)
            version = meta.get('Version')
            author = meta.get('Author')
            raw = meta.get('Author-email')          # "Name <addr>" or just "addr"
            if raw and '<' in raw:
                name, _, addr = raw.partition('<')
                author = author or name.strip() or None
                email = addr.rstrip('>').strip()
            elif raw:
                email = raw.strip()
        except Exception:                            # noqa: BLE001 - not installed
            pass

    commit = _git('rev-parse', '--short', 'HEAD')
    return {
        'version': version,
        'author': author,
        'email': email,
        'commit': commit,
        'commit_date': _git('log', '-1', '--format=%cs') if commit else None,
        'branch': _git('rev-parse', '--abbrev-ref', 'HEAD') if commit else None,
        # A non-empty diff means the running code is ahead of the named commit.
        'dirty': bool(_git('status', '--porcelain')) if commit else False,
    }
