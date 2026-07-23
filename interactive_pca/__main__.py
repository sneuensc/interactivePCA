"""Enable ``python -m interactive_pca``.

This entry point exists so the setup wizard can relaunch the process with a
composed argument list via ``[sys.executable, "-m", "interactive_pca", ...]``,
independent of how the console script was originally invoked.
"""

from .cli import main

if __name__ == '__main__':
    main()
