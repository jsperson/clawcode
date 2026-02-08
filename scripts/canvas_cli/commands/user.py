"""User profile and preferences commands."""

import sys
from canvas_cli.client import get_canvas
from canvas_cli.output import output
from canvas_cli.converters import user_to_dict
from canvas_cli.input_helpers import write_result


def register(subparsers):
    p = subparsers.add_parser('profile', help='Get my profile')
    p.set_defaults(func=cmd_profile)

    p = subparsers.add_parser('edit-profile', help='Edit my profile')
    p.add_argument('--name', type=str)
    p.add_argument('--short-name', type=str)
    p.add_argument('--bio', type=str)
    p.add_argument('--title', type=str)
    p.add_argument('--time-zone', type=str)
    p.add_argument('--locale', type=str)
    p.set_defaults(func=cmd_edit_profile)

    p = subparsers.add_parser('update-user-settings', help='Update user settings')
    p.add_argument('--manual-mark-as-read', type=str, choices=['true', 'false'])
    p.add_argument('--collapse-global-nav', type=str, choices=['true', 'false'])
    p.add_argument('--hide-dashcard-color-overlays', type=str, choices=['true', 'false'])
    p.set_defaults(func=cmd_update_user_settings)

    p = subparsers.add_parser('update-color', help='Update dashboard color for an asset')
    p.add_argument('asset', type=str, help='Asset string (e.g. course_12345)')
    p.add_argument('hexcode', type=str, help='Hex color code (e.g. #FF0000)')
    p.set_defaults(func=cmd_update_color)

    p = subparsers.add_parser('add-favorite-course', help='Add a course to favorites')
    p.add_argument('course_id', type=int)
    p.set_defaults(func=cmd_add_favorite_course)

    p = subparsers.add_parser('add-favorite-group', help='Add a group to favorites')
    p.add_argument('group_id', type=int)
    p.set_defaults(func=cmd_add_favorite_group)

    p = subparsers.add_parser('create-planner-note', help='Create a planner note')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--details', type=str)
    p.add_argument('--todo-date', type=str, help='Date (ISO format)')
    p.add_argument('--course-id', type=int)
    p.set_defaults(func=cmd_create_planner_note)

    p = subparsers.add_parser('create-planner-override',
                              help='Create a planner override')
    p.add_argument('plannable_type', type=str,
                   help='Type (e.g. assignment, discussion_topic, quiz)')
    p.add_argument('plannable_id', type=int)
    p.add_argument('--marked-complete', action='store_true', default=False)
    p.add_argument('--dismissed', action='store_true', default=False)
    p.set_defaults(func=cmd_create_planner_override)

    p = subparsers.add_parser('create-communication-channel',
                              help='Create a communication channel')
    p.add_argument('--address', type=str, required=True, help='Email or phone')
    p.add_argument('--type', type=str, required=True,
                   choices=['email', 'sms', 'push'],
                   dest='channel_type')
    p.set_defaults(func=cmd_create_communication_channel)

    p = subparsers.add_parser('update-notification-preference',
                              help='Update notification preference')
    p.add_argument('channel_id', type=int, help='Communication channel ID')
    p.add_argument('notification', type=str, help='Notification name')
    p.add_argument('--frequency', type=str, required=True,
                   choices=['immediately', 'daily', 'weekly', 'never'])
    p.set_defaults(func=cmd_update_notification_preference)


def cmd_profile(args):
    """Get my profile info."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    result = user_to_dict(user)

    try:
        profile = user.get_profile()
        result.update({
            'bio': getattr(profile, 'bio', None),
            'primary_email': getattr(profile, 'primary_email', None),
            'login_id': getattr(profile, 'login_id', None),
            'time_zone': getattr(profile, 'time_zone', None),
        })
    except Exception:
        pass

    output(result)


def cmd_edit_profile(args):
    """Edit my profile."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    kwargs = {}
    if args.name:
        kwargs['name'] = args.name
    if args.short_name:
        kwargs['short_name'] = args.short_name
    if args.bio is not None:
        kwargs['bio'] = args.bio
    if args.title is not None:
        kwargs['title'] = args.title
    if args.time_zone:
        kwargs['time_zone'] = args.time_zone
    if args.locale:
        kwargs['locale'] = args.locale
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    user.edit(user=kwargs)
    write_result("updated", user.id, user.name)


def cmd_update_user_settings(args):
    """Update user settings."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    kwargs = {}
    if args.manual_mark_as_read is not None:
        kwargs['manual_mark_as_read'] = args.manual_mark_as_read == 'true'
    if args.collapse_global_nav is not None:
        kwargs['collapse_global_nav'] = args.collapse_global_nav == 'true'
    if args.hide_dashcard_color_overlays is not None:
        kwargs['hide_dashcard_color_overlays'] = args.hide_dashcard_color_overlays == 'true'
    if not kwargs:
        print("Error: No settings provided.", file=sys.stderr)
        sys.exit(1)
    user.update_settings(**kwargs)
    write_result("updated", user.id, "user settings")


def cmd_update_color(args):
    """Update dashboard color for an asset."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    hexcode = args.hexcode.lstrip('#')
    user.update_color(args.asset, hexcode)
    write_result("updated", args.asset, f"color #{hexcode}")


def cmd_add_favorite_course(args):
    """Add a course to favorites."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    user.add_favorite_course(args.course_id)
    write_result("added_favorite", args.course_id, f"course {args.course_id}")


def cmd_add_favorite_group(args):
    """Add a group to favorites."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    user.add_favorite_group(args.group_id)
    write_result("added_favorite", args.group_id, f"group {args.group_id}")


def cmd_create_planner_note(args):
    """Create a planner note."""
    canvas = get_canvas()
    kwargs = {'title': args.title}
    if args.details:
        kwargs['details'] = args.details
    if args.todo_date:
        kwargs['todo_date'] = args.todo_date
    if args.course_id:
        kwargs['course_id'] = args.course_id
    note = canvas.create_planner_note(**kwargs)
    write_result("created", getattr(note, 'id', None), args.title)


def cmd_create_planner_override(args):
    """Create a planner override."""
    canvas = get_canvas()
    override = canvas.create_planner_override(
        plannable_type=args.plannable_type,
        plannable_id=args.plannable_id,
        marked_complete=args.marked_complete,
        dismissed=args.dismissed,
    )
    write_result("created", getattr(override, 'id', None),
                 f"{args.plannable_type} {args.plannable_id}")


def cmd_create_communication_channel(args):
    """Create a communication channel."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    channel = user.create_communication_channel(
        communication_channel={
            'address': args.address,
            'type': args.channel_type,
        }
    )
    write_result("created", getattr(channel, 'id', None), args.address,
                 type=args.channel_type)


def cmd_update_notification_preference(args):
    """Update notification preference for a communication channel."""
    canvas = get_canvas()
    user = canvas.get_current_user()
    channels = user.get_communication_channels()
    target = None
    for ch in channels:
        if ch.id == args.channel_id:
            target = ch
            break
    if not target:
        print(f"Error: Communication channel {args.channel_id} not found.",
              file=sys.stderr)
        sys.exit(1)
    target.update_preference(
        notification=args.notification,
        frequency=args.frequency,
    )
    write_result("updated", args.channel_id, args.notification,
                 frequency=args.frequency)
