"""Conversation/inbox commands."""

import sys
from canvas_cli.client import get_canvas
from canvas_cli.output import output
from canvas_cli.converters import conversation_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('inbox', help='Get inbox conversations')
    p.add_argument('--filter', type=str,
                   choices=['all', 'unread', 'starred', 'sent', 'archived'],
                   default='all')
    p.set_defaults(func=cmd_inbox)

    p = subparsers.add_parser('conversation', help='Get conversation with messages')
    p.add_argument('id', type=int, help='Conversation ID')
    p.set_defaults(func=cmd_conversation)

    p = subparsers.add_parser('create-conversation', help='Create a new conversation')
    p.add_argument('--recipients', type=int, nargs='+', required=True,
                   help='User IDs to send to')
    p.add_argument('--subject', type=str, required=True)
    p.add_argument('--group-conversation', action='store_true', default=False,
                   help='Create as group conversation')
    add_body_args(p)
    p.set_defaults(func=cmd_create_conversation)

    p = subparsers.add_parser('reply-conversation', help='Reply to a conversation')
    p.add_argument('id', type=int, help='Conversation ID')
    add_body_args(p)
    p.set_defaults(func=cmd_reply_conversation)

    p = subparsers.add_parser('add-recipients', help='Add recipients to a conversation')
    p.add_argument('id', type=int, help='Conversation ID')
    p.add_argument('--recipients', type=int, nargs='+', required=True)
    p.set_defaults(func=cmd_add_recipients)

    p = subparsers.add_parser('edit-conversation', help='Edit conversation properties')
    p.add_argument('id', type=int, help='Conversation ID')
    p.add_argument('--workflow-state', type=str,
                   choices=['read', 'unread', 'archived'])
    p.add_argument('--starred', type=str, choices=['true', 'false'])
    p.add_argument('--subject', type=str)
    p.set_defaults(func=cmd_edit_conversation)

    p = subparsers.add_parser('delete-conversation', help='Delete a conversation')
    p.add_argument('id', type=int, help='Conversation ID')
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_conversation)

    p = subparsers.add_parser('mark-all-conversations-read',
                              help='Mark all conversations as read')
    p.set_defaults(func=cmd_mark_all_conversations_read)


def cmd_inbox(args):
    """Get inbox conversations."""
    canvas = get_canvas()
    filter_type = args.filter or 'all'
    scope = None if filter_type == 'all' else filter_type

    result = []
    try:
        if scope:
            convs = canvas.get_conversations(scope=scope)
        else:
            convs = canvas.get_conversations()
        for conv in convs:
            result.append(conversation_to_dict(conv))
    except Exception as e:
        print(f"Error getting conversations: {e}", file=sys.stderr)

    output(result)


def cmd_conversation(args):
    """Get a specific conversation with messages."""
    canvas = get_canvas()
    try:
        conv = canvas.get_conversation(args.id)
        result = conversation_to_dict(conv, include_messages=True)
        output(result)
    except Exception as e:
        print(f"Error getting conversation: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_create_conversation(args):
    """Create a new conversation."""
    canvas = get_canvas()
    body = resolve_body(args)
    if not body:
        print("Error: --body, --body-file, or --body-stdin required.", file=sys.stderr)
        sys.exit(1)
    recipients = [str(r) for r in args.recipients]
    convs = canvas.create_conversation(
        recipients=recipients,
        body=body,
        subject=args.subject,
        group_conversation=args.group_conversation,
    )
    # create_conversation returns a list of conversations
    conv_list = list(convs) if hasattr(convs, '__iter__') else [convs]
    if conv_list:
        c = conv_list[0]
        cid = c.get('id') if isinstance(c, dict) else getattr(c, 'id', None)
        write_result("created", cid, args.subject)
    else:
        write_result("created", None, args.subject)


def cmd_reply_conversation(args):
    """Reply to a conversation."""
    canvas = get_canvas()
    body = resolve_body(args)
    if not body:
        print("Error: --body, --body-file, or --body-stdin required.", file=sys.stderr)
        sys.exit(1)
    conv = canvas.get_conversation(args.id)
    conv.add_message(body=body)
    write_result("replied", conv.id, getattr(conv, 'subject', None))


def cmd_add_recipients(args):
    """Add recipients to a conversation."""
    canvas = get_canvas()
    conv = canvas.get_conversation(args.id)
    recipients = [str(r) for r in args.recipients]
    conv.add_recipients(recipients)
    write_result("added_recipients", conv.id, getattr(conv, 'subject', None),
                 added=args.recipients)


def cmd_edit_conversation(args):
    """Edit conversation properties."""
    canvas = get_canvas()
    conv = canvas.get_conversation(args.id)
    kwargs = {}
    if args.workflow_state:
        kwargs['conversation'] = kwargs.get('conversation', {})
        kwargs['conversation']['workflow_state'] = args.workflow_state
    if args.starred is not None:
        kwargs['conversation'] = kwargs.get('conversation', {})
        kwargs['conversation']['starred'] = args.starred == 'true'
    if args.subject:
        kwargs['conversation'] = kwargs.get('conversation', {})
        kwargs['conversation']['subject'] = args.subject
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    conv.edit(**kwargs)
    write_result("updated", conv.id, getattr(conv, 'subject', None))


def cmd_delete_conversation(args):
    """Delete a conversation."""
    canvas = get_canvas()
    conv = canvas.get_conversation(args.id)
    if not confirm_destructive(
            f"delete conversation '{getattr(conv, 'subject', args.id)}'", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    conv.delete()
    write_result("deleted", conv.id, getattr(conv, 'subject', None))


def cmd_mark_all_conversations_read(args):
    """Mark all conversations as read."""
    canvas = get_canvas()
    canvas.conversations_mark_all_as_read()
    write_result("marked_all_read")
