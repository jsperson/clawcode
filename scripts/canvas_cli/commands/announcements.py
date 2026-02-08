"""Announcement commands."""

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import announcement_to_dict
from canvas_cli.input_helpers import add_body_args, resolve_body, write_result


def register(subparsers):
    p = subparsers.add_parser('announcements', help='Get announcements')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.add_argument('--limit', type=int, default=10)
    p.set_defaults(func=cmd_announcements)

    p = subparsers.add_parser('create-announcement', help='Create an announcement')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--title', type=str, required=True)
    add_body_args(p, 'message')
    p.set_defaults(func=cmd_create_announcement)


def cmd_announcements(args):
    """Get announcements."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)
    limit = args.limit or 10

    result = []
    for course in courses:
        try:
            announcements = course.get_discussion_topics(only_announcements=True)
            count = 0
            for a in announcements:
                if count >= limit:
                    break
                adict = announcement_to_dict(a)
                adict['course_name'] = course.name
                result.append(adict)
                count += 1
        except Exception:
            pass

    result.sort(key=lambda x: x.get('posted_at') or '', reverse=True)
    output(result[:limit])


def cmd_create_announcement(args):
    """Create an announcement in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {
        'title': args.title,
        'is_announcement': True,
    }
    message = resolve_body(args, 'message')
    if message:
        kwargs['message'] = message
    topic = course.create_discussion_topic(**kwargs)
    write_result("created", topic.id, topic.title)
