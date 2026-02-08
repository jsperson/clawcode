"""Course commands."""

import sys
from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import course_to_dict
from canvas_cli.input_helpers import resolve_body, add_body_args, write_result


def register(subparsers):
    p = subparsers.add_parser('courses', help='List enrolled courses')
    p.set_defaults(func=cmd_courses)

    p = subparsers.add_parser('course', help='Get course details')
    p.add_argument('id', type=int, help='Course ID')
    p.set_defaults(func=cmd_course)

    p = subparsers.add_parser('course-update', help='Update course settings')
    p.add_argument('id', type=int, help='Course ID')
    p.add_argument('--name', type=str, help='Course name')
    p.add_argument('--course-code', type=str, help='Course code')
    p.add_argument('--default-view', type=str,
                   choices=['feed', 'wiki', 'modules', 'syllabus', 'assignments'])
    p.add_argument('--syllabus-body', type=str, help='Syllabus HTML body')
    p.add_argument('--grading-standard-id', type=int)
    p.set_defaults(func=cmd_course_update)

    p = subparsers.add_parser('course-update-settings', help='Update course settings flags')
    p.add_argument('id', type=int, help='Course ID')
    p.add_argument('--hide-final-grades', type=str, choices=['true', 'false'])
    p.add_argument('--hide-distribution-graphs', type=str, choices=['true', 'false'])
    p.add_argument('--lock-all-announcements', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_course_update_settings)

    p = subparsers.add_parser('create-rubric', help='Create a rubric in a course')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--criteria', type=str, required=True,
                   help='JSON array of criteria objects')
    p.set_defaults(func=cmd_create_rubric)

    p = subparsers.add_parser('create-assignment-group', help='Create assignment group')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('--name', type=str, required=True)
    p.add_argument('--position', type=int)
    p.add_argument('--group-weight', type=float)
    p.set_defaults(func=cmd_create_assignment_group)


def cmd_courses(args):
    """List enrolled courses."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    courses = user.get_courses(enrollment_state='active')
    result = [course_to_dict(course) for course in courses]
    result.sort(key=lambda x: x.get('name', ''))
    output(result)


def cmd_course(args):
    """Get detailed info for a specific course."""
    canvas = get_canvas()
    course = canvas.get_course(args.id, include=['syllabus_body', 'term', 'total_scores'])
    result = course_to_dict(course, detailed=True)
    output(result)


def cmd_course_update(args):
    """Update course properties."""
    canvas = get_canvas()
    course = canvas.get_course(args.id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.course_code:
        kwargs['course_code'] = args.course_code
    if args.default_view:
        kwargs['default_view'] = args.default_view
    if args.syllabus_body:
        kwargs['syllabus_body'] = args.syllabus_body
    if args.grading_standard_id:
        kwargs['grading_standard_id'] = args.grading_standard_id
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    course.update(course=kwargs)
    write_result("updated", course.id, course.name)


def cmd_course_update_settings(args):
    """Update course settings flags."""
    canvas = get_canvas()
    course = canvas.get_course(args.id)
    kwargs = {}
    if args.hide_final_grades is not None:
        kwargs['hide_final_grades'] = args.hide_final_grades == 'true'
    if args.hide_distribution_graphs is not None:
        kwargs['hide_distribution_graphs'] = args.hide_distribution_graphs == 'true'
    if args.lock_all_announcements is not None:
        kwargs['lock_all_announcements'] = args.lock_all_announcements == 'true'
    if not kwargs:
        print("Error: No settings provided.", file=sys.stderr)
        sys.exit(1)
    course.update_settings(**kwargs)
    write_result("updated", course.id, f"settings for course {course.id}")


def cmd_create_rubric(args):
    """Create a rubric in a course."""
    import json
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    criteria = json.loads(args.criteria)
    rubric = course.create_rubric(rubric={'title': args.title, 'criteria': criteria})
    # create_rubric returns a dict with 'rubric' key
    r = rubric.get('rubric', rubric) if isinstance(rubric, dict) else rubric
    rid = r.get('id') if isinstance(r, dict) else getattr(r, 'id', None)
    write_result("created", rid, args.title)


def cmd_create_assignment_group(args):
    """Create an assignment group in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    kwargs = {'name': args.name}
    if args.position is not None:
        kwargs['position'] = args.position
    if args.group_weight is not None:
        kwargs['group_weight'] = args.group_weight
    group = course.create_assignment_group(**kwargs)
    write_result("created", group.id, group.name)
