"""Calendar event commands."""

import sys
from datetime import datetime, timedelta

from canvas_cli.client import get_canvas
from canvas_cli.output import output, format_datetime, html_to_text
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('calendar', help='Get calendar events')
    p.add_argument('--days', type=int, default=14)
    p.set_defaults(func=cmd_calendar)

    p = subparsers.add_parser('create-calendar-event', help='Create a calendar event')
    p.add_argument('--context', type=str, required=True,
                   help='Context code (e.g. course_12345 or user_12345)')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--start-at', type=str, required=True, help='Start datetime (ISO)')
    p.add_argument('--end-at', type=str, help='End datetime (ISO)')
    p.add_argument('--location-name', type=str)
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_create_calendar_event)

    p = subparsers.add_parser('edit-calendar-event', help='Edit a calendar event')
    p.add_argument('event_id', type=int)
    p.add_argument('--title', type=str)
    p.add_argument('--start-at', type=str)
    p.add_argument('--end-at', type=str)
    p.add_argument('--location-name', type=str)
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_edit_calendar_event)

    p = subparsers.add_parser('delete-calendar-event', help='Delete a calendar event')
    p.add_argument('event_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_calendar_event)


def cmd_calendar(args):
    """Get calendar events."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    days = args.days or 14
    start = datetime.now().date()
    end = start + timedelta(days=days)

    courses = list(user.get_courses(enrollment_state='active'))
    context_codes = [f"course_{c.id}" for c in courses]
    context_codes.append(f"user_{user.id}")

    result = []
    try:
        events = canvas.get_calendar_events(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            context_codes=context_codes,
        )
        for event in events:
            result.append({
                'id': event.id,
                'title': event.title,
                'start_at': format_datetime(getattr(event, 'start_at', None)),
                'end_at': format_datetime(getattr(event, 'end_at', None)),
                'type': getattr(event, 'type', None),
                'context_name': getattr(event, 'context_name', None),
                'description': html_to_text(getattr(event, 'description', None)),
                'html_url': getattr(event, 'html_url', None),
            })
    except Exception as e:
        print(f"Error getting calendar: {e}", file=sys.stderr)

    result.sort(key=lambda x: x.get('start_at') or '')
    output(result)


def cmd_create_calendar_event(args):
    """Create a calendar event."""
    canvas = get_canvas()
    event_data = {
        'context_code': args.context,
        'title': args.title,
        'start_at': args.start_at,
    }
    if args.end_at:
        event_data['end_at'] = args.end_at
    if args.location_name:
        event_data['location_name'] = args.location_name
    desc = resolve_body(args, 'description')
    if desc:
        event_data['description'] = desc
    event = canvas.create_calendar_event(calendar_event=event_data)
    write_result("created", event.id, event.title)


def cmd_edit_calendar_event(args):
    """Edit a calendar event."""
    canvas = get_canvas()
    event = canvas.get_calendar_event(args.event_id)
    kwargs = {}
    if args.title:
        kwargs['title'] = args.title
    if args.start_at:
        kwargs['start_at'] = args.start_at
    if args.end_at:
        kwargs['end_at'] = args.end_at
    if args.location_name:
        kwargs['location_name'] = args.location_name
    desc = resolve_body(args, 'description')
    if desc:
        kwargs['description'] = desc
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    event.edit(calendar_event=kwargs)
    write_result("updated", event.id, event.title)


def cmd_delete_calendar_event(args):
    """Delete a calendar event."""
    canvas = get_canvas()
    event = canvas.get_calendar_event(args.event_id)
    if not confirm_destructive(f"delete calendar event '{event.title}' (ID {event.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    event.delete()
    write_result("deleted", event.id, event.title)
