"""Assignment commands."""

import sys
from datetime import datetime, timedelta
from canvasapi.exceptions import ResourceDoesNotExist

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output, format_datetime, html_to_text
from canvas_cli.converters import assignment_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('assignments', help='List assignments')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.add_argument('--upcoming', type=int, help='Only show assignments due in next N days')
    p.set_defaults(func=cmd_assignments)

    p = subparsers.add_parser('assignment', help='Get assignment details')
    p.add_argument('id', type=int, help='Assignment ID')
    p.set_defaults(func=cmd_assignment)

    p = subparsers.add_parser('create-assignment', help='Create an assignment')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--name', type=str, required=True, help='Assignment name')
    p.add_argument('--points-possible', type=float)
    p.add_argument('--due-at', type=str, help='Due date (ISO format)')
    p.add_argument('--unlock-at', type=str)
    p.add_argument('--lock-at', type=str)
    p.add_argument('--submission-types', type=str, nargs='+',
                   help='e.g. online_text_entry online_upload online_url')
    p.add_argument('--published', action='store_true', default=False)
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_create_assignment)

    p = subparsers.add_parser('edit-assignment', help='Edit an assignment')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('assignment_id', type=int, help='Assignment ID')
    p.add_argument('--name', type=str)
    p.add_argument('--points-possible', type=float)
    p.add_argument('--due-at', type=str)
    p.add_argument('--unlock-at', type=str)
    p.add_argument('--lock-at', type=str)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_edit_assignment)

    p = subparsers.add_parser('delete-assignment', help='Delete an assignment')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('assignment_id', type=int, help='Assignment ID')
    p.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    p.set_defaults(func=cmd_delete_assignment)

    p = subparsers.add_parser('submit-assignment', help='Submit an assignment')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('assignment_id', type=int, help='Assignment ID')
    p.add_argument('--type', type=str, required=True,
                   choices=['online_text_entry', 'online_url', 'online_upload'],
                   help='Submission type')
    p.add_argument('--url', type=str, help='URL for online_url submission')
    p.add_argument('--file', type=str, help='File path for online_upload')
    add_body_args(p)
    p.set_defaults(func=cmd_submit_assignment)


def cmd_assignments(args):
    """List assignments, optionally filtered by course or upcoming days."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    now = datetime.now().astimezone()
    cutoff = now + timedelta(days=args.upcoming) if args.upcoming else None

    for course in courses:
        try:
            assignments = course.get_assignments(order_by='due_at', include=['submission'])
            for a in assignments:
                adict = assignment_to_dict(a)
                adict['course_name'] = course.name

                if cutoff and adict['due_at']:
                    try:
                        due = datetime.fromisoformat(getattr(a, 'due_at', '').replace('Z', '+00:00'))
                        if due < now or due > cutoff:
                            continue
                    except Exception:
                        pass

                result.append(adict)
        except Exception:
            pass

    result.sort(key=lambda x: x.get('due_at') or '9999')
    output(result)


def cmd_assignment(args):
    """Get details for a specific assignment."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    for course in user.get_courses(enrollment_state='active'):
        try:
            assignment = course.get_assignment(args.id)
            result = assignment_to_dict(assignment, include_description=True)
            result['course_name'] = course.name
            output(result)
            return
        except ResourceDoesNotExist:
            continue
        except Exception:
            continue

    print(f"Error: Assignment {args.id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_create_assignment(args):
    """Create an assignment in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {'name': args.name}
    desc = resolve_body(args, 'description')
    if desc:
        kwargs['description'] = desc
    if args.points_possible is not None:
        kwargs['points_possible'] = args.points_possible
    if args.due_at:
        kwargs['due_at'] = args.due_at
    if args.unlock_at:
        kwargs['unlock_at'] = args.unlock_at
    if args.lock_at:
        kwargs['lock_at'] = args.lock_at
    if args.submission_types:
        kwargs['submission_types'] = args.submission_types
    kwargs['published'] = args.published

    assignment = course.create_assignment(assignment=kwargs)
    write_result("created", assignment.id, assignment.name)


def cmd_edit_assignment(args):
    """Edit an existing assignment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.points_possible is not None:
        kwargs['points_possible'] = args.points_possible
    if args.due_at:
        kwargs['due_at'] = args.due_at
    if args.unlock_at:
        kwargs['unlock_at'] = args.unlock_at
    if args.lock_at:
        kwargs['lock_at'] = args.lock_at
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    desc = resolve_body(args, 'description')
    if desc:
        kwargs['description'] = desc
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    assignment.edit(assignment=kwargs)
    write_result("updated", assignment.id, assignment.name)


def cmd_delete_assignment(args):
    """Delete an assignment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    if not confirm_destructive(f"delete assignment '{assignment.name}' (ID {assignment.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    assignment.delete()
    write_result("deleted", assignment.id, assignment.name)


def cmd_submit_assignment(args):
    """Submit an assignment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)

    submission = {'submission_type': args.type}

    if args.type == 'online_text_entry':
        body = resolve_body(args)
        if not body:
            print("Error: --body, --body-file, or --body-stdin required for text entry.", file=sys.stderr)
            sys.exit(1)
        submission['body'] = body
    elif args.type == 'online_url':
        if not args.url:
            print("Error: --url required for URL submission.", file=sys.stderr)
            sys.exit(1)
        submission['url'] = args.url
    elif args.type == 'online_upload':
        if not args.file:
            print("Error: --file required for file upload.", file=sys.stderr)
            sys.exit(1)
        # Upload file first, then submit
        result = assignment.upload_to_submission(args.file)
        # result is a tuple (success, file_dict)
        if result[0]:
            submission['file_ids'] = [result[1]['id']]
        else:
            print(f"Error: File upload failed.", file=sys.stderr)
            sys.exit(1)

    sub = assignment.submit(submission)
    write_result("submitted", getattr(sub, 'id', None), assignment.name,
                 assignment_id=assignment.id)
