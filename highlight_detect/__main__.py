"""Allow running the package directly: python -m highlight_detect"""
from .error_handler import setup_logging, install_excepthook

# Initialize logging and install crash handler before anything else
setup_logging()
install_excepthook()

from .cli import main

main()
