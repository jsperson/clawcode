"""Discussion commands."""

import sys
from canvasapi.exceptions import ResourceDoesNotExist

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output, format_datetime, html_to_text
from canvas_cli.converters import discussion_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('discussions', help='List discussion topics')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_discussions)

    p = subparsers.add_parser('discussion', help='Get discussion with entries')
    p.add_argument('id', type=int, help='Discussion ID')
    p.set_defaults(func=cmd_discussion)

    p = subparsers.add_parser('create-discussion', help='Create a discussion topic')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--discussion-type', type=str, choices=['side_comment', 'threaded'],
                   default='threaded')
    p.add_argument('--published', action='store_true', default=False)
    p.add_argument('--pinned', action='store_true', default=False)
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_create_discussion)

    p = subparsers.add_parser('edit-discussion', help='Edit a discussion topic')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('--title', type=str)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    p.add_argument('--pinned', type=str, choices=['true', 'false'])
    p.add_argument('--locked', type=str, choices=['true', 'false'])
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_edit_discussion)

    p = subparsers.add_parser('delete-discussion', help='Delete a discussion topic')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_discussion)

    p = subparsers.add_parser('post-discussion-entry',
                              help='Post a top-level entry to a discussion')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_post_discussion_entry)

    p = subparsers.add_parser('reply-to-entry', help='Reply to a discussion entry')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('entry_id', type=int)
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_reply_to_entry)

    p = subparsers.add_parser('edit-entry', help='Edit a discussion entry')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('entry_id', type=int)
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_edit_entry)

    p = subparsers.add_parser('delete-entry', help='Delete a discussion entry')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('entry_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_entry)

    p = subparsers.add_parser('rate-entry', help='Rate a discussion entry')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('entry_id', type=int)
    p.add_argument('--rating', type=int, required=True, choices=[0, 1],
                   help='1 to like, 0 to unlike')
    p.set_defaults(func=cmd_rate_entry)

    p = subparsers.add_parser('subscribe-discussion', help='Subscribe to a discussion')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.set_defaults(func=cmd_subscribe_discussion)

    p = subparsers.add_parser('unsubscribe-discussion', help='Unsubscribe from a discussion')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.set_defaults(func=cmd_unsubscribe_discussion)

    p = subparsers.add_parser('mark-discussion-read', help='Mark discussion as read')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('--all', action='store_true', help='Mark all entries as read')
    p.set_defaults(func=cmd_mark_discussion_read)

    p = subparsers.add_parser('mark-discussion-unread', help='Mark discussion as unread')
    p.add_argument('course_id', type=int)
    p.add_argument('topic_id', type=int)
    p.add_argument('--all', action='store_true', help='Mark all entries as unread')
    p.set_defaults(func=cmd_mark_discussion_unread)


def cmd_discussions(args):
    """List discussion topics."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            topics = course.get_discussion_topics()
            for t in topics:
                tdict = discussion_to_dict(t)
                tdict['course_id'] = course.id
                tdict['course_name'] = course.name
                result.append(tdict)
        except Exception:
            pass

    result.sort(key=lambda x: x.get('last_reply_at') or x.get('posted_at') or '', reverse=True)
    output(result)


def cmd_discussion(args):
    """Get a full discussion with entries."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    for course in user.get_courses(enrollment_state='active'):
        try:
            topic = course.get_discussion_topic(args.id)
            result = discussion_to_dict(topic)
            result['course_name'] = course.name
            result['message_html'] = getattr(topic, 'message', None)

            try:
                full_topic = course.get_full_discussion_topic(args.id)
                view = full_topic.get('view', [])
                participants = {p['id']: p['display_name']
                                for p in full_topic.get('participants', [])}
                unread = set(full_topic.get('unread_entries', []))

                def parse_entry(e, depth=0):
                    entry = {
                        'id': e.get('id'),
                        'user_name': participants.get(e.get('user_id'), 'Unknown'),
                        'message': html_to_text(e.get('message')),
                        'created_at': format_datetime(e.get('created_at')),
                        'depth': depth,
                        'unread': e.get('id') in unread,
                    }
                    replies = e.get('replies', [])
                    if replies:
                        entry['replies'] = [parse_entry(r, depth+1) for r in replies]
                    return entry

                result['entries'] = [parse_entry(e) for e in view]
                result['unread_entry_ids'] = list(unread)
            except Exception as e:
                result['entries'] = []
                result['entries_error'] = str(e)

            output(result)
            return
        except ResourceDoesNotExist:
            continue
        except Exception:
            continue

    print(f"Error: Discussion {args.id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_create_discussion(args):
    """Create a discussion topic."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {
        'title': args.title,
        'discussion_type': args.discussion_type,
        'published': args.published,
        'pinned': args.pinned,
    }
    message = resolve_body(args, 'message')
    if message:
        kwargs['message'] = message
    topic = course.create_discussion_topic(**kwargs)
    write_result("created", topic.id, topic.title)


def cmd_edit_discussion(args):
    """Edit a discussion topic."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    topic = course.get_discussion_topic(args.topic_id)
    kwargs = {}
    if args.title:
        kwargs['title'] = args.title
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    if args.pinned is not None:
        kwargs['pinned'] = args.pinned == 'true'
    if args.locked is not None:
        kwargs['locked'] = args.locked == 'true'
    message = resolve_body(args, 'message')
    if message:
        kwargs['message'] = message
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    topic.update(**kwargs)
    write_result("updated", topic.id, topic.title)


def cmd_delete_discussion(args):
    """Delete a discussion topic."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    topic = course.get_discussion_topic(args.topic_id)
    if not confirm_destructive(f"delete discussion '{topic.title}' (ID {topic.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    topic.delete()
    write_result("deleted", topic.id, topic.title)


def _get_topic_and_entries(canvas, course_id, topic_id):
    """Helper to get topic and its entries."""
    course = canvas.get_course(course_id)
    topic = course.get_discussion_topic(topic_id)
    return course, topic


def cmd_post_discussion_entry(args):
    """Post a top-level entry to a discussion."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    message = resolve_body(args, 'message')
    if not message:
        print("Error: --message, --message-file, or --message-stdin required.", file=sys.stderr)
        sys.exit(1)
    entry = topic.post_entry(message=message)
    write_result("posted", getattr(entry, 'id', None), topic.title)


def cmd_reply_to_entry(args):
    """Reply to a discussion entry."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    message = resolve_body(args, 'message')
    if not message:
        print("Error: --message, --message-file, or --message-stdin required.", file=sys.stderr)
        sys.exit(1)
    entry = topic.get_entries([args.entry_id])
    # get_entries returns a list; grab the first
    entries_list = list(entry)
    if not entries_list:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)
    reply = entries_list[0].post_reply(message=message)
    write_result("replied", getattr(reply, 'id', None), topic.title,
                 parent_entry_id=args.entry_id)


def cmd_edit_entry(args):
    """Edit a discussion entry."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    message = resolve_body(args, 'message')
    if not message:
        print("Error: --message, --message-file, or --message-stdin required.", file=sys.stderr)
        sys.exit(1)
    entries_list = list(topic.get_entries([args.entry_id]))
    if not entries_list:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)
    entries_list[0].update(message=message)
    write_result("updated", args.entry_id, topic.title)


def cmd_delete_entry(args):
    """Delete a discussion entry."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    if not confirm_destructive(f"delete entry {args.entry_id} in '{topic.title}'", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    entries_list = list(topic.get_entries([args.entry_id]))
    if not entries_list:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)
    entries_list[0].delete()
    write_result("deleted", args.entry_id, topic.title)


def cmd_rate_entry(args):
    """Rate a discussion entry."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    entries_list = list(topic.get_entries([args.entry_id]))
    if not entries_list:
        print(f"Error: Entry {args.entry_id} not found.", file=sys.stderr)
        sys.exit(1)
    entries_list[0].rate(rating=args.rating)
    write_result("rated", args.entry_id, topic.title, rating=args.rating)


def cmd_subscribe_discussion(args):
    """Subscribe to a discussion topic."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    topic.subscribe()
    write_result("subscribed", topic.id, topic.title)


def cmd_unsubscribe_discussion(args):
    """Unsubscribe from a discussion topic."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    topic.unsubscribe()
    write_result("unsubscribed", topic.id, topic.title)


def cmd_mark_discussion_read(args):
    """Mark discussion topic or all entries as read."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    if getattr(args, 'all', False):
        topic.mark_entries_as_read()
        write_result("marked_all_entries_read", topic.id, topic.title)
    else:
        topic.mark_as_read()
        write_result("marked_read", topic.id, topic.title)


def cmd_mark_discussion_unread(args):
    """Mark discussion topic or all entries as unread."""
    canvas = get_canvas()
    course, topic = _get_topic_and_entries(canvas, args.course_id, args.topic_id)
    if getattr(args, 'all', False):
        topic.mark_entries_as_unread()
        write_result("marked_all_entries_unread", topic.id, topic.title)
    else:
        topic.mark_as_unread()
        write_result("marked_unread", topic.id, topic.title)
