"""File and folder commands."""

import sys
import urllib.request

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import file_to_dict, folder_to_dict
from canvas_cli.input_helpers import confirm_destructive, write_result


def register(subparsers):
    p = subparsers.add_parser('files', help='List files')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.add_argument('--folder', type=int, help='Filter by folder ID')
    p.set_defaults(func=cmd_files)

    p = subparsers.add_parser('file', help='Get file details')
    p.add_argument('id', type=int, help='File ID')
    p.set_defaults(func=cmd_file)

    p = subparsers.add_parser('download', help='Download a file')
    p.add_argument('id', type=int, help='File ID')
    p.add_argument('--output', '-o', type=str, help='Output filename')
    p.set_defaults(func=cmd_download)

    p = subparsers.add_parser('folders', help='List folders')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_folders)

    p = subparsers.add_parser('upload-file', help='Upload a file to a folder')
    p.add_argument('--folder', type=int, required=True, help='Folder ID')
    p.add_argument('--file', type=str, required=True, help='Local file path')
    p.set_defaults(func=cmd_upload_file)

    p = subparsers.add_parser('create-folder', help='Create a folder')
    p.add_argument('--name', type=str, required=True)
    p.add_argument('--course', type=int, help='Create in course root')
    p.add_argument('--parent-folder', type=int, help='Create inside parent folder')
    p.set_defaults(func=cmd_create_folder)

    p = subparsers.add_parser('update-file', help='Update file metadata')
    p.add_argument('file_id', type=int)
    p.add_argument('--name', type=str, help='New display name')
    p.add_argument('--locked', type=str, choices=['true', 'false'])
    p.add_argument('--hidden', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_update_file)

    p = subparsers.add_parser('delete-file', help='Delete a file')
    p.add_argument('file_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_file)

    p = subparsers.add_parser('update-folder', help='Update folder metadata')
    p.add_argument('folder_id', type=int)
    p.add_argument('--name', type=str)
    p.add_argument('--locked', type=str, choices=['true', 'false'])
    p.add_argument('--hidden', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_update_folder)

    p = subparsers.add_parser('delete-folder', help='Delete a folder')
    p.add_argument('folder_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.add_argument('--force', action='store_true',
                   help='Delete even if folder is not empty')
    p.set_defaults(func=cmd_delete_folder)


def cmd_files(args):
    """List files for a course or folder."""
    canvas = get_canvas()
    result = []

    if args.folder:
        folder = canvas.get_folder(args.folder)
        files = folder.get_files()
        for f in files:
            result.append(file_to_dict(f))
    elif args.course:
        course = canvas.get_course(args.course)
        files = course.get_files()
        for f in files:
            result.append(file_to_dict(f))
    else:
        user = canvas.get_current_user()
        for course in user.get_courses(enrollment_state='active'):
            try:
                files = course.get_files()
                for f in files:
                    fdict = file_to_dict(f)
                    fdict['course_id'] = course.id
                    fdict['course_name'] = course.name
                    result.append(fdict)
            except Exception:
                pass

    output(result)


def cmd_file(args):
    """Get file details."""
    canvas = get_canvas()
    f = canvas.get_file(args.id)
    result = file_to_dict(f)
    output(result)


def cmd_download(args):
    """Download a file."""
    canvas = get_canvas()
    f = canvas.get_file(args.id)

    url = getattr(f, 'url', None)
    if not url:
        print("Error: No download URL available", file=sys.stderr)
        sys.exit(1)

    filename = args.output or getattr(f, 'display_name', getattr(f, 'filename', f'file_{args.id}'))

    print(f"Downloading to {filename}...", file=sys.stderr)
    urllib.request.urlretrieve(url, filename)
    print(f"Downloaded: {filename}", file=sys.stderr)
    write_result("downloaded", args.id, filename)


def cmd_folders(args):
    """List folders for a course."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            folders = course.get_folders()
            for folder in folders:
                fdict = folder_to_dict(folder)
                fdict['course_id'] = course.id
                fdict['course_name'] = course.name
                result.append(fdict)
        except Exception:
            pass

    output(result)


def cmd_upload_file(args):
    """Upload a file to a folder."""
    canvas = get_canvas()
    folder = canvas.get_folder(args.folder)
    success, result = folder.upload(args.file)
    if success:
        file_id = result.get('id') if isinstance(result, dict) else getattr(result, 'id', None)
        file_name = result.get('display_name', result.get('filename')) if isinstance(result, dict) else getattr(result, 'display_name', None)
        write_result("uploaded", file_id, file_name)
    else:
        print("Error: File upload failed.", file=sys.stderr)
        sys.exit(1)


def cmd_create_folder(args):
    """Create a folder."""
    canvas = get_canvas()
    if args.parent_folder:
        parent = canvas.get_folder(args.parent_folder)
        folder = parent.create_folder(args.name)
    elif args.course:
        course = canvas.get_course(args.course)
        folder = course.create_folder(args.name)
    else:
        print("Error: Provide --course or --parent-folder.", file=sys.stderr)
        sys.exit(1)
    write_result("created", folder.id, folder.name)


def cmd_update_file(args):
    """Update file metadata."""
    canvas = get_canvas()
    f = canvas.get_file(args.file_id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.locked is not None:
        kwargs['locked'] = args.locked == 'true'
    if args.hidden is not None:
        kwargs['hidden'] = args.hidden == 'true'
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    f.update(**kwargs)
    write_result("updated", f.id, getattr(f, 'display_name', None))


def cmd_delete_file(args):
    """Delete a file."""
    canvas = get_canvas()
    f = canvas.get_file(args.file_id)
    name = getattr(f, 'display_name', getattr(f, 'filename', str(args.file_id)))
    if not confirm_destructive(f"delete file '{name}' (ID {f.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    f.delete()
    write_result("deleted", f.id, name)


def cmd_update_folder(args):
    """Update folder metadata."""
    canvas = get_canvas()
    folder = canvas.get_folder(args.folder_id)
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.locked is not None:
        kwargs['locked'] = args.locked == 'true'
    if args.hidden is not None:
        kwargs['hidden'] = args.hidden == 'true'
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    folder.update(**kwargs)
    write_result("updated", folder.id, folder.name)


def cmd_delete_folder(args):
    """Delete a folder."""
    canvas = get_canvas()
    folder = canvas.get_folder(args.folder_id)
    if not confirm_destructive(f"delete folder '{folder.name}' (ID {folder.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    folder.delete(force=args.force)
    write_result("deleted", folder.id, folder.name)
