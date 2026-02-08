"""Submission commands."""

import sys
import json
from canvasapi.exceptions import ResourceDoesNotExist

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output, format_datetime
from canvas_cli.converters import submission_to_dict
from canvas_cli.input_helpers import confirm_destructive, write_result


def register(subparsers):
    p = subparsers.add_parser('submissions', help='Get my submissions')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_submissions)

    p = subparsers.add_parser('submission', help='Get submission details')
    p.add_argument('assignment_id', type=int, help='Assignment ID')
    p.set_defaults(func=cmd_submission)

    p = subparsers.add_parser('grade-submission', help='Grade a submission')
    p.add_argument('course_id', type=int)
    p.add_argument('assignment_id', type=int)
    p.add_argument('user_id', type=int)
    p.add_argument('--score', type=str, help='Score (number or letter grade)')
    p.add_argument('--comment', type=str, help='Text comment')
    p.add_argument('--excused', action='store_true')
    p.set_defaults(func=cmd_grade_submission)

    p = subparsers.add_parser('bulk-grade', help='Bulk grade submissions from file')
    p.add_argument('course_id', type=int)
    p.add_argument('assignment_id', type=int)
    p.add_argument('--grades-file', type=str, required=True,
                   help='JSON file: [{"user_id": N, "grade": "X"}, ...]')
    p.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    p.set_defaults(func=cmd_bulk_grade)

    p = subparsers.add_parser('submission-mark-read', help='Mark submission as read')
    p.add_argument('course_id', type=int)
    p.add_argument('assignment_id', type=int)
    p.add_argument('user_id', type=int)
    p.set_defaults(func=cmd_submission_mark_read)

    p = subparsers.add_parser('submission-mark-unread', help='Mark submission as unread')
    p.add_argument('course_id', type=int)
    p.add_argument('assignment_id', type=int)
    p.add_argument('user_id', type=int)
    p.set_defaults(func=cmd_submission_mark_unread)

    p = subparsers.add_parser('upload-submission-comment',
                              help='Upload file as submission comment')
    p.add_argument('course_id', type=int)
    p.add_argument('assignment_id', type=int)
    p.add_argument('user_id', type=int)
    p.add_argument('--file', type=str, required=True, help='File to upload')
    p.set_defaults(func=cmd_upload_submission_comment)


def cmd_submissions(args):
    """Get my submissions across courses."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            assignments = course.get_assignments(include=['submission'])
            for a in assignments:
                submission = getattr(a, 'submission', None)
                if submission:
                    sub_dict = {
                        'assignment_id': a.id,
                        'assignment_name': a.name,
                        'course_id': course.id,
                        'course_name': course.name,
                        'due_at': format_datetime(getattr(a, 'due_at', None)),
                        'score': submission.get('score'),
                        'grade': submission.get('grade'),
                        'submitted_at': format_datetime(submission.get('submitted_at')),
                        'workflow_state': submission.get('workflow_state'),
                        'late': submission.get('late', False),
                        'missing': submission.get('missing', False),
                    }
                    result.append(sub_dict)
        except Exception:
            pass

    result.sort(key=lambda x: x.get('due_at') or '9999')
    output(result)


def cmd_submission(args):
    """Get detailed submission for a specific assignment."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    for course in user.get_courses(enrollment_state='active'):
        try:
            assignment = course.get_assignment(args.assignment_id)
            submission = assignment.get_submission(user.id, include=['submission_comments'])
            result = submission_to_dict(submission, include_comments=True)
            result['assignment_name'] = assignment.name
            result['course_name'] = course.name
            output(result)
            return
        except ResourceDoesNotExist:
            continue
        except Exception:
            continue

    print(f"Error: Assignment {args.assignment_id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_grade_submission(args):
    """Grade a student's submission."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    submission = assignment.get_submission(args.user_id)

    kwargs = {}
    if args.score is not None:
        kwargs['submission'] = {'posted_grade': args.score}
    if args.excused:
        kwargs['submission'] = kwargs.get('submission', {})
        kwargs['submission']['excuse'] = True
    if args.comment:
        kwargs['comment'] = {'text_comment': args.comment}

    if not kwargs:
        print("Error: Provide --score, --comment, or --excused.", file=sys.stderr)
        sys.exit(1)

    submission.edit(**kwargs)
    write_result("graded", args.user_id, assignment.name,
                 assignment_id=assignment.id, score=args.score)


def cmd_bulk_grade(args):
    """Bulk grade submissions from a JSON file."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)

    with open(args.grades_file, 'r') as f:
        grades_data = json.load(f)

    if not confirm_destructive(
            f"bulk grade {len(grades_data)} submissions for '{assignment.name}'", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)

    # Build grade_data dict: {user_id: {"posted_grade": grade}}
    grade_data = {}
    for entry in grades_data:
        uid = str(entry['user_id'])
        grade_data[uid] = {'posted_grade': entry.get('grade', entry.get('score'))}

    result = assignment.submissions_bulk_update(grade_data=grade_data)
    write_result("bulk_graded", assignment.id, assignment.name,
                 count=len(grades_data))


def cmd_submission_mark_read(args):
    """Mark a submission as read."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    submission = assignment.get_submission(args.user_id)
    submission.mark_read()
    write_result("marked_read", args.user_id, assignment.name)


def cmd_submission_mark_unread(args):
    """Mark a submission as unread."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    submission = assignment.get_submission(args.user_id)
    submission.mark_unread()
    write_result("marked_unread", args.user_id, assignment.name)


def cmd_upload_submission_comment(args):
    """Upload a file as a submission comment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    assignment = course.get_assignment(args.assignment_id)
    submission = assignment.get_submission(args.user_id)
    result = submission.upload_comment(args.file)
    write_result("uploaded_comment", args.user_id, assignment.name, file=args.file)
