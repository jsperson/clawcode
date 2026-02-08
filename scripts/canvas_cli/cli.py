"""Main CLI entry point for Canvas CLI."""

import sys
import argparse

try:
    from canvasapi.exceptions import Unauthorized
except ImportError:
    print("Error: canvasapi not installed. Run: pip3 install canvasapi", file=sys.stderr)
    sys.exit(1)

from canvas_cli.commands import register_all


def main():
    parser = argparse.ArgumentParser(
        description='Canvas LMS CLI for Newman University',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    register_all(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Unauthorized:
        print("Error: Invalid or expired Canvas token", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
