"""Wiki page commands."""

import sys
from canvasapi.exceptions import ResourceDoesNotExist

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import page_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('pages', help='List wiki pages')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_pages)

    p = subparsers.add_parser('page', help='Get wiki page content')
    p.add_argument('course_id', type=int, help='Course ID')
    p.add_argument('title', type=str, help='Page title/URL')
    p.set_defaults(func=cmd_page)

    p = subparsers.add_parser('create-page', help='Create a wiki page')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--published', action='store_true', default=False)
    p.add_argument('--front-page', action='store_true', default=False)
    add_body_args(p)
    p.set_defaults(func=cmd_create_page)

    p = subparsers.add_parser('edit-page', help='Edit a wiki page')
    p.add_argument('course_id', type=int)
    p.add_argument('url_or_title', type=str, help='Page URL slug or title')
    p.add_argument('--title', type=str)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    add_body_args(p)
    p.set_defaults(func=cmd_edit_page)

    p = subparsers.add_parser('delete-page', help='Delete a wiki page')
    p.add_argument('course_id', type=int)
    p.add_argument('url_or_title', type=str, help='Page URL slug or title')
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_page)


def cmd_pages(args):
    """List wiki pages for courses."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            pages = course.get_pages()
            for p in pages:
                pdict = page_to_dict(p)
                pdict['course_id'] = course.id
                pdict['course_name'] = course.name
                result.append(pdict)
        except Exception:
            pass

    result.sort(key=lambda x: x.get('title', ''))
    output(result)


def cmd_page(args):
    """Get a specific wiki page."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)

    try:
        page = course.get_page(args.title)
        result = page_to_dict(page, include_body=True)
        result['course_name'] = course.name
        output(result)
    except ResourceDoesNotExist:
        print(f"Error: Page '{args.title}' not found in course {args.course_id}",
              file=sys.stderr)
        sys.exit(1)


def cmd_create_page(args):
    """Create a wiki page."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {
        'title': args.title,
        'published': args.published,
        'front_page': args.front_page,
    }
    body = resolve_body(args)
    if body:
        kwargs['body'] = body
    page = course.create_page(wiki_page=kwargs)
    write_result("created", page.url, page.title)


def cmd_edit_page(args):
    """Edit a wiki page."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    page = course.get_page(args.url_or_title)
    kwargs = {}
    if args.title:
        kwargs['title'] = args.title
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    body = resolve_body(args)
    if body:
        kwargs['body'] = body
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    page.edit(wiki_page=kwargs)
    write_result("updated", page.url, page.title)


def cmd_delete_page(args):
    """Delete a wiki page."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    page = course.get_page(args.url_or_title)
    if not confirm_destructive(f"delete page '{page.title}'", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    page.delete()
    write_result("deleted", page.url, page.title)
