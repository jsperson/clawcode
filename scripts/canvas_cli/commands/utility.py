"""Utility commands (grades, todo, upcoming, notifications, search)."""

import sys
from datetime import datetime, timedelta

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output, format_datetime, html_to_text
from canvas_cli.converters import (
    assignment_to_dict, page_to_dict, discussion_to_dict, file_to_dict,
)


def register(subparsers):
    p = subparsers.add_parser('grades', help='Get grades')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_grades)

    p = subparsers.add_parser('todo', help='Get todo items')
    p.set_defaults(func=cmd_todo)

    p = subparsers.add_parser('upcoming', help='Get upcoming assignments')
    p.add_argument('--days', type=int, default=7)
    p.set_defaults(func=cmd_upcoming)

    p = subparsers.add_parser('notifications', help='Get notification summary')
    p.set_defaults(func=cmd_notifications)

    p = subparsers.add_parser('search', help='Search across courses')
    p.add_argument('query', type=str, help='Search query')
    p.set_defaults(func=cmd_search)


def cmd_grades(args):
    """Get grades for courses."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    courses = get_courses_list(canvas, args.course)

    result = []
    enrollments = list(user.get_enrollments(type=['StudentEnrollment']))

    for course in courses:
        try:
            for enrollment in enrollments:
                if enrollment.course_id == course.id:
                    grades = getattr(enrollment, 'grades', {})
                    result.append({
                        'course_id': course.id,
                        'course_name': course.name,
                        'current_score': grades.get('current_score'),
                        'current_grade': grades.get('current_grade'),
                        'final_score': grades.get('final_score'),
                        'final_grade': grades.get('final_grade'),
                    })
                    break
        except Exception:
            pass

    output(result)


def cmd_todo(args):
    """Get todo items."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    result = []
    try:
        todos = user.get_todo_items()
        for item in todos:
            assignment = getattr(item, 'assignment', None)
            result.append({
                'type': item.type,
                'assignment_id': assignment.get('id') if assignment else None,
                'assignment_name': assignment.get('name') if assignment else None,
                'course_id': getattr(item, 'course_id', None),
                'due_at': format_datetime(assignment.get('due_at')) if assignment else None,
                'html_url': getattr(item, 'html_url', None),
            })
    except Exception as e:
        print(f"Error getting todos: {e}", file=sys.stderr)

    output(result)


def cmd_upcoming(args):
    """Get upcoming assignments due in the next N days."""
    # Delegate to assignments command logic
    from canvas_cli.commands.assignments import cmd_assignments

    class FakeArgs:
        pass

    fake = FakeArgs()
    fake.upcoming = args.days or 7
    fake.course = None
    cmd_assignments(fake)


def cmd_notifications(args):
    """Get recent activity stream / notifications."""
    canvas = get_canvas()

    result = []
    try:
        summary = canvas.get_activity_stream_summary()
        # Bug fix: summary returns a list, not a dict
        for item in summary:
            if isinstance(item, dict):
                result.append({
                    'type': item.get('type'),
                    'count': item.get('count', 0),
                    'unread_count': item.get('unread_count', 0),
                })
    except Exception as e:
        print(f"Error getting notifications: {e}", file=sys.stderr)

    output(result)


def cmd_search(args):
    """Search across courses."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    query = args.query.lower()

    result = {
        'assignments': [],
        'pages': [],
        'discussions': [],
        'announcements': [],
        'files': [],
    }

    for course in user.get_courses(enrollment_state='active'):
        try:
            for a in course.get_assignments():
                if query in a.name.lower() or query in html_to_text(
                        getattr(a, 'description', '') or '').lower():
                    adict = assignment_to_dict(a)
                    adict['course_name'] = course.name
                    result['assignments'].append(adict)

            for p in course.get_pages():
                if query in p.title.lower():
                    pdict = page_to_dict(p)
                    pdict['course_name'] = course.name
                    result['pages'].append(pdict)

            for t in course.get_discussion_topics():
                if query in t.title.lower() or query in html_to_text(
                        getattr(t, 'message', '') or '').lower():
                    tdict = discussion_to_dict(t)
                    tdict['course_name'] = course.name
                    result['discussions'].append(tdict)

            for f in course.get_files():
                name = getattr(f, 'display_name', getattr(f, 'filename', ''))
                if query in name.lower():
                    fdict = file_to_dict(f)
                    fdict['course_name'] = course.name
                    result['files'].append(fdict)
        except Exception:
            pass

    output(result)
