"""Module commands."""

import sys
from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import module_to_dict, module_item_to_dict
from canvas_cli.input_helpers import confirm_destructive, write_result


def register(subparsers):
    p = subparsers.add_parser('modules', help='List course modules')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_modules)

    p = subparsers.add_parser('module-items', help='Get module items')
    p.add_argument('module_id', type=int, help='Module ID')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.set_defaults(func=cmd_module_items)

    p = subparsers.add_parser('create-module', help='Create a module')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--name', type=str, required=True)
    p.add_argument('--position', type=int)
    p.add_argument('--unlock-at', type=str, help='Unlock date (ISO format)')
    p.add_argument('--require-sequential-progress', action='store_true', default=False)
    p.set_defaults(func=cmd_create_module)

    p = subparsers.add_parser('edit-module', help='Edit a module')
    p.add_argument('course_id', type=int)
    p.add_argument('module_id', type=int)
    p.add_argument('--name', type=str)
    p.add_argument('--position', type=int)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_edit_module)

    p = subparsers.add_parser('delete-module', help='Delete a module')
    p.add_argument('course_id', type=int)
    p.add_argument('module_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_module)

    p = subparsers.add_parser('create-module-item', help='Create an item in a module')
    p.add_argument('course_id', type=int)
    p.add_argument('module_id', type=int)
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--type', type=str, required=True,
                   choices=['File', 'Page', 'Discussion', 'Assignment', 'Quiz',
                            'SubHeader', 'ExternalUrl', 'ExternalTool'],
                   dest='item_type')
    p.add_argument('--content-id', type=int, help='ID of existing content item')
    p.add_argument('--external-url', type=str)
    p.add_argument('--position', type=int)
    p.set_defaults(func=cmd_create_module_item)

    p = subparsers.add_parser('edit-module-item', help='Edit a module item')
    p.add_argument('course_id', type=int)
    p.add_argument('module_id', type=int)
    p.add_argument('item_id', type=int)
    p.add_argument('--title', type=str)
    p.add_argument('--position', type=int)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_edit_module_item)

    p = subparsers.add_parser('delete-module-item', help='Delete a module item')
    p.add_argument('course_id', type=int)
    p.add_argument('module_id', type=int)
    p.add_argument('item_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_module_item)


def cmd_modules(args):
    """List modules for courses."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            modules = course.get_modules()
            for module in modules:
                mdict = module_to_dict(module)
                mdict['course_id'] = course.id
                mdict['course_name'] = course.name
                result.append(mdict)
        except Exception:
            pass

    result.sort(key=lambda x: (x.get('course_name', ''), x.get('position') or 999))
    output(result)


def cmd_module_items(args):
    """Get items in a module."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    module = course.get_module(args.module_id)

    result = []
    try:
        items = module.get_module_items()
        for item in items:
            result.append(module_item_to_dict(item))
    except Exception as e:
        print(f"Error getting module items: {e}", file=sys.stderr)

    result.sort(key=lambda x: x.get('position') or 999)
    output(result)


def cmd_create_module(args):
    """Create a module in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {'name': args.name}
    if args.position is not None:
        kwargs['position'] = args.position
    if args.unlock_at:
        kwargs['unlock_at'] = args.unlock_at
    if args.require_sequential_progress:
        kwargs['require_sequential_progress'] = True
    module = course.create_module(module=kwargs)
    write_result("created", module.id, module.name)


def cmd_edit_module(args):
    """Edit a module."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    module = course.get_module(args.module_id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.position is not None:
        kwargs['position'] = args.position
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    module.edit(module=kwargs)
    write_result("updated", module.id, module.name)


def cmd_delete_module(args):
    """Delete a module."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    module = course.get_module(args.module_id)
    if not confirm_destructive(f"delete module '{module.name}' (ID {module.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    module.delete()
    write_result("deleted", module.id, module.name)


def cmd_create_module_item(args):
    """Create an item in a module."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    module = course.get_module(args.module_id)
    kwargs = {
        'title': args.title,
        'type': args.item_type,
    }
    if args.content_id:
        kwargs['content_id'] = args.content_id
    if args.external_url:
        kwargs['external_url'] = args.external_url
    if args.position is not None:
        kwargs['position'] = args.position
    item = module.create_module_item(module_item=kwargs)
    write_result("created", item.id, item.title)


def cmd_edit_module_item(args):
    """Edit a module item."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    module = course.get_module(args.module_id)
    item = module.get_module_item(args.item_id)
    kwargs = {}
    if args.title:
        kwargs['title'] = args.title
    if args.position is not None:
        kwargs['position'] = args.position
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    item.edit(module_item=kwargs)
    write_result("updated", item.id, item.title)


def cmd_delete_module_item(args):
    """Delete a module item."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    module = course.get_module(args.module_id)
    item = module.get_module_item(args.item_id)
    if not confirm_destructive(f"delete module item '{item.title}' (ID {item.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    item.delete()
    write_result("deleted", item.id, item.title)
