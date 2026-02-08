"""Input helpers for write operations."""

import sys
import json


def add_body_args(parser, field_name='body'):
    """Add mutually exclusive --body, --body-file, --body-stdin args."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f'--{field_name}', type=str, help=f'{field_name} text (inline)')
    group.add_argument(f'--{field_name}-file', type=str, help=f'Read {field_name} from file')
    group.add_argument(f'--{field_name}-stdin', action='store_true',
                       help=f'Read {field_name} from stdin')


def resolve_body(args, field_name='body'):
    """Resolve body content from --body, --body-file, or --body-stdin."""
    inline = getattr(args, field_name, None)
    if inline:
        return inline

    file_attr = field_name.replace('-', '_') + '_file'
    file_path = getattr(args, file_attr, None)
    if file_path:
        with open(file_path, 'r') as f:
            return f.read()

    stdin_attr = field_name.replace('-', '_') + '_stdin'
    if getattr(args, stdin_attr, False):
        return sys.stdin.read()

    return None


def confirm_destructive(action_desc, args):
    """Prompt for confirmation on destructive operations.

    Skips if --yes flag is set. Requires --yes when stdin is not a TTY.
    """
    if getattr(args, 'yes', False):
        return True

    if not sys.stdin.isatty():
        print(f"Error: Destructive operation requires --yes flag when not interactive.",
              file=sys.stderr)
        sys.exit(1)

    response = input(f"Are you sure you want to {action_desc}? [y/N] ")
    return response.strip().lower() in ('y', 'yes')


def write_result(action, obj_id=None, name=None, **extra):
    """Output a standardized write operation result to stdout."""
    result = {"action": action}
    if obj_id is not None:
        result["id"] = obj_id
    if name is not None:
        result["name"] = name
    result.update(extra)
    print(json.dumps(result, indent=2, default=str))
