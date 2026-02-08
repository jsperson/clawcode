"""Enrollment and section commands."""

import sys
from canvas_cli.client import get_canvas
from canvas_cli.output import output
from canvas_cli.converters import user_to_dict
from canvas_cli.input_helpers import confirm_destructive, write_result


def register(subparsers):
    p = subparsers.add_parser('people', help='List people in a course')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.set_defaults(func=cmd_people)

    p = subparsers.add_parser('create-section', help='Create a course section')
    p.add_argument('course_id', type=int)
    p.add_argument('--name', type=str, required=True)
    p.add_argument('--start-at', type=str)
    p.add_argument('--end-at', type=str)
    p.set_defaults(func=cmd_create_section)

    p = subparsers.add_parser('edit-section', help='Edit a section')
    p.add_argument('section_id', type=int)
    p.add_argument('--name', type=str)
    p.add_argument('--start-at', type=str)
    p.add_argument('--end-at', type=str)
    p.set_defaults(func=cmd_edit_section)

    p = subparsers.add_parser('delete-section', help='Delete a section')
    p.add_argument('section_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_section)

    p = subparsers.add_parser('cross-list-section',
                              help='Cross-list a section to another course')
    p.add_argument('section_id', type=int)
    p.add_argument('new_course_id', type=int)
    p.set_defaults(func=cmd_cross_list_section)

    p = subparsers.add_parser('enroll-user', help='Enroll a user in a section')
    p.add_argument('section_id', type=int)
    p.add_argument('user_id', type=int)
    p.add_argument('--type', type=str, required=True,
                   choices=['StudentEnrollment', 'TeacherEnrollment',
                            'TaEnrollment', 'ObserverEnrollment',
                            'DesignerEnrollment'],
                   dest='enrollment_type')
    p.set_defaults(func=cmd_enroll_user)

    p = subparsers.add_parser('accept-enrollment', help='Accept an enrollment')
    p.add_argument('course_id', type=int)
    p.add_argument('enrollment_id', type=int)
    p.set_defaults(func=cmd_accept_enrollment)

    p = subparsers.add_parser('deactivate-enrollment',
                              help='Deactivate an enrollment')
    p.add_argument('course_id', type=int)
    p.add_argument('enrollment_id', type=int)
    p.add_argument('--task', type=str, default='deactivate',
                   choices=['conclude', 'delete', 'deactivate'])
    p.set_defaults(func=cmd_deactivate_enrollment)

    p = subparsers.add_parser('reactivate-enrollment',
                              help='Reactivate an enrollment')
    p.add_argument('course_id', type=int)
    p.add_argument('enrollment_id', type=int)
    p.set_defaults(func=cmd_reactivate_enrollment)


def cmd_people(args):
    """List people in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)

    result = []
    try:
        users = course.get_users(include=['enrollments'])
        for user in users:
            udict = user_to_dict(user)
            enrollments = getattr(user, 'enrollments', [])
            if enrollments:
                udict['role'] = enrollments[0].get('role', None)
                udict['enrollment_state'] = enrollments[0].get('enrollment_state', None)
            result.append(udict)
    except Exception as e:
        print(f"Error getting people: {e}", file=sys.stderr)

    result.sort(key=lambda x: x.get('sortable_name', ''))
    output(result)


def cmd_create_section(args):
    """Create a course section."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    kwargs = {'name': args.name}
    if args.start_at:
        kwargs['start_at'] = args.start_at
    if args.end_at:
        kwargs['end_at'] = args.end_at
    section = course.create_course_section(course_section=kwargs)
    write_result("created", section.id, section.name)


def cmd_edit_section(args):
    """Edit a section."""
    canvas = get_canvas()
    section = canvas.get_section(args.section_id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.start_at:
        kwargs['start_at'] = args.start_at
    if args.end_at:
        kwargs['end_at'] = args.end_at
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    section.edit(course_section=kwargs)
    write_result("updated", section.id, section.name)


def cmd_delete_section(args):
    """Delete a section."""
    canvas = get_canvas()
    section = canvas.get_section(args.section_id)
    if not confirm_destructive(
            f"delete section '{section.name}' (ID {section.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    section.delete()
    write_result("deleted", section.id, section.name)


def cmd_cross_list_section(args):
    """Cross-list a section to another course."""
    canvas = get_canvas()
    section = canvas.get_section(args.section_id)
    section.cross_list_section(args.new_course_id)
    write_result("cross_listed", section.id, section.name,
                 new_course_id=args.new_course_id)


def cmd_enroll_user(args):
    """Enroll a user in a section."""
    canvas = get_canvas()
    section = canvas.get_section(args.section_id)
    enrollment = section.enroll_user(
        args.user_id,
        enrollment={'type': args.enrollment_type},
    )
    write_result("enrolled", getattr(enrollment, 'id', None),
                 f"user {args.user_id}",
                 section_id=args.section_id,
                 enrollment_type=args.enrollment_type)


def cmd_accept_enrollment(args):
    """Accept an enrollment invitation."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    enrollments = course.get_enrollments()
    for e in enrollments:
        if e.id == args.enrollment_id:
            e.accept()
            write_result("accepted", e.id, f"enrollment {e.id}")
            return
    print(f"Error: Enrollment {args.enrollment_id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_deactivate_enrollment(args):
    """Deactivate (conclude/delete/deactivate) an enrollment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    enrollments = course.get_enrollments()
    for e in enrollments:
        if e.id == args.enrollment_id:
            e.deactivate(task=args.task)
            write_result("deactivated", e.id, f"enrollment {e.id}", task=args.task)
            return
    print(f"Error: Enrollment {args.enrollment_id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_reactivate_enrollment(args):
    """Reactivate an enrollment."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    enrollments = course.get_enrollments()
    for e in enrollments:
        if e.id == args.enrollment_id:
            e.reactivate()
            write_result("reactivated", e.id, f"enrollment {e.id}")
            return
    print(f"Error: Enrollment {args.enrollment_id} not found.", file=sys.stderr)
    sys.exit(1)
