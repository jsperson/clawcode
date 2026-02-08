"""Group commands."""

import sys
from canvas_cli.client import get_canvas
from canvas_cli.output import output
from canvas_cli.converters import group_to_dict, user_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('groups', help='List my groups')
    p.set_defaults(func=cmd_groups)

    p = subparsers.add_parser('group', help='Get group details')
    p.add_argument('id', type=int, help='Group ID')
    p.set_defaults(func=cmd_group)

    p = subparsers.add_parser('create-group', help='Create a group')
    p.add_argument('--name', type=str, required=True)
    p.add_argument('--description', type=str)
    p.add_argument('--is-public', action='store_true', default=False)
    p.add_argument('--join-level', type=str,
                   choices=['parent_context_auto_join', 'parent_context_request',
                            'invitation_only'],
                   default='invitation_only')
    p.set_defaults(func=cmd_create_group)

    p = subparsers.add_parser('edit-group', help='Edit a group')
    p.add_argument('id', type=int)
    p.add_argument('--name', type=str)
    p.add_argument('--description', type=str)
    p.add_argument('--join-level', type=str,
                   choices=['parent_context_auto_join', 'parent_context_request',
                            'invitation_only'])
    p.set_defaults(func=cmd_edit_group)

    p = subparsers.add_parser('delete-group', help='Delete a group')
    p.add_argument('id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_group)

    p = subparsers.add_parser('add-group-member', help='Add a member to a group')
    p.add_argument('group_id', type=int)
    p.add_argument('user_id', type=int)
    p.set_defaults(func=cmd_add_group_member)

    p = subparsers.add_parser('remove-group-member', help='Remove a member from a group')
    p.add_argument('group_id', type=int)
    p.add_argument('user_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_remove_group_member)

    p = subparsers.add_parser('group-create-discussion',
                              help='Create a discussion in a group')
    p.add_argument('group_id', type=int)
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--discussion-type', type=str, choices=['side_comment', 'threaded'],
                   default='threaded')
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_group_create_discussion)

    p = subparsers.add_parser('group-create-page', help='Create a page in a group')
    p.add_argument('group_id', type=int)
    p.add_argument('--title', type=str, required=True)
    add_body_args(p)
    p.set_defaults(func=cmd_group_create_page)

    p = subparsers.add_parser('group-create-folder', help='Create a folder in a group')
    p.add_argument('group_id', type=int)
    p.add_argument('--name', type=str, required=True)
    p.set_defaults(func=cmd_group_create_folder)


def cmd_groups(args):
    """List my groups."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    result = []
    try:
        groups = user.get_groups()
        for g in groups:
            result.append(group_to_dict(g))
    except Exception as e:
        print(f"Error getting groups: {e}", file=sys.stderr)

    output(result)


def cmd_group(args):
    """Get group details."""
    canvas = get_canvas()
    group = canvas.get_group(args.id)
    result = group_to_dict(group)

    try:
        members = group.get_users()
        result['members'] = [user_to_dict(m) for m in members]
    except Exception:
        result['members'] = []

    output(result)


def cmd_create_group(args):
    """Create a group."""
    canvas = get_canvas()
    group = canvas.create_group(
        name=args.name,
        description=args.description,
        is_public=args.is_public,
        join_level=args.join_level,
    )
    write_result("created", group.id, group.name)


def cmd_edit_group(args):
    """Edit a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.description is not None:
        kwargs['description'] = args.description
    if args.join_level:
        kwargs['join_level'] = args.join_level
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    group.edit(**kwargs)
    write_result("updated", group.id, group.name)


def cmd_delete_group(args):
    """Delete a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.id)
    if not confirm_destructive(f"delete group '{group.name}' (ID {group.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    group.delete()
    write_result("deleted", group.id, group.name)


def cmd_add_group_member(args):
    """Add a member to a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.group_id)
    membership = group.create_membership(args.user_id)
    write_result("added_member", args.user_id, group.name, group_id=group.id)


def cmd_remove_group_member(args):
    """Remove a member from a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.group_id)
    if not confirm_destructive(
            f"remove user {args.user_id} from group '{group.name}'", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    group.remove_user(args.user_id)
    write_result("removed_member", args.user_id, group.name, group_id=group.id)


def cmd_group_create_discussion(args):
    """Create a discussion topic in a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.group_id)
    kwargs = {
        'title': args.title,
        'discussion_type': args.discussion_type,
    }
    message = resolve_body(args, 'message')
    if message:
        kwargs['message'] = message
    topic = group.create_discussion_topic(**kwargs)
    write_result("created", topic.id, topic.title, group_id=group.id)


def cmd_group_create_page(args):
    """Create a wiki page in a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.group_id)
    kwargs = {'title': args.title}
    body = resolve_body(args)
    if body:
        kwargs['body'] = body
    page = group.create_page(wiki_page=kwargs)
    write_result("created", page.url, page.title, group_id=group.id)


def cmd_group_create_folder(args):
    """Create a folder in a group."""
    canvas = get_canvas()
    group = canvas.get_group(args.group_id)
    folder = group.create_folder(args.name)
    write_result("created", folder.id, folder.name, group_id=group.id)
