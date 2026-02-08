#!/usr/bin/env python3
"""Canvas LMS CLI for Newman University - thin shim.

This script delegates to the canvas_cli package.
All functionality lives in scripts/canvas_cli/.
"""

import os
import sys

# Ensure the scripts directory is on the path so canvas_cli can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from canvas_cli.cli import main

if __name__ == '__main__':
    main()
