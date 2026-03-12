"""
Main entry point and CLI for interactivePCA.
"""

import sys
import logging
from . import parse_args


def setup_logging(args):
    """
    Configure logging based on arguments.
    
    Args:
        args: Parsed arguments namespace
    """
    if args.dev:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    logging.getLogger().setLevel(level)

    # Suppress noisy Flask/Dash startup messages unless in dev mode
    if not args.dev:
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('dash').setLevel(logging.ERROR)


def print_banner(parsed_args):
    """Print a startup banner summarising the active panels."""
    url = f"http://localhost:{parsed_args.server_port}"
    sep = "=" * 60

    panels = ["• PCA scatter plot (always active)"]
    if parsed_args.annotation:
        panels.append("• Annotation table")
    if parsed_args.latitude and parsed_args.longitude:
        panels.append("• Geographic map")
    if parsed_args.time:
        panels.append("• Time histogram")

    print(f"\n{sep}")
    print("  🚀  interactivePCA")
    print(sep)
    print(f"\n  Open your browser and navigate to:")
    print(f"      {url}")
    print(f"\n  Active panels:")
    for panel in panels:
        print(f"      {panel}")
    print(f"\n  Press Ctrl+C to stop the server")
    print(f"{sep}\n")


def main(args=None):
    """
    Main entry point for interactivePCA CLI.
    
    Args:
        args: Optional list of command-line arguments
    """
    # Parse arguments
    parsed_args = parse_args(args)
    
    # Setup logging
    setup_logging(parsed_args)
    
    # Validate required arguments
    if not parsed_args.eigenvec:
        logging.error('Missing required argument: --eigenvec')
        sys.exit(1)
    
    if parsed_args.dev:
        logging.debug('Development mode activated.')
    
    # Import app module (lazy import to avoid circular dependency)
    try:
        from .app import create_app
        app = create_app(parsed_args)
        
        url = f"http://localhost:{parsed_args.server_port}"
        print_banner(parsed_args)
        
        if parsed_args.open_browser:
            import webbrowser
            webbrowser.open(url)
        
        app.run(debug=parsed_args.dev, port=parsed_args.server_port)
        
    except ImportError as e:
        logging.error(f"App module error: {e}")
        logging.error("Please ensure all dependencies are installed: pip install -e .")
        sys.exit(1)


if __name__ == '__main__':
    main()
