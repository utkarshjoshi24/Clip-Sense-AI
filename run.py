#!/usr/bin/env python
"""
run.py — Entry point for ClipSense PyInstaller bundle and local testing.
"""

from highlight_detect.error_handler import setup_logging, install_excepthook
from highlight_detect.cli import main

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    # Initialize logging and install crash handler before anything else
    setup_logging()
    install_excepthook()
    
    # Run the CLI
    main()
