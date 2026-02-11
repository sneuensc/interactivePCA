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
        
        # Run the app
        url = f"http://localhost:{parsed_args.server_port}"
        logging.info(f"Dashboard running at {url}")
        
        if parsed_args.open_browser:
            import webbrowser
            webbrowser.open(url)
        
        app.run(debug=parsed_args.dev, port=parsed_args.server_port)
        
    except ImportError:
        logging.error("App module not yet implemented. Please use the notebook directly.")
        sys.exit(1)


if __name__ == '__main__':
    main()
